#!/usr/bin/env python3
"""Run the frozen C2 primary E5 retrieval contrast without touching the frozen corpus.

Modes:
  preflight  verify corpus/query SHA chains and freeze the logical retrieval input order
  embed      checkpoint content-v1, metadata-v1, and query E5 embeddings in .npy shards
  retrieve   run the two frozen hybrid profiles and freeze the 192 ordered top-10 lists
  status     report current checkpoint/freeze state

Confirmatory statistics are intentionally NOT computed here. Retrieval is frozen first.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "results" / "second_corpus_dataeuropa_v2_final_v2_9_100"
DEFAULT_QUERIES = ROOT / "results" / "second_corpus_queries_v1"
DEFAULT_OUT = ROOT / "results" / "second_corpus_retrieval_v1"
DEFAULT_CONFIG = ROOT / "config" / "second_corpus_retrieval_v1.json"
DEFAULT_ADAPTER = ROOT / "docs" / "second_corpus_v2_preretrieval_adapter_10_distribution_identity.md"
TOKEN_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)*", re.UNICODE)


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_sha(obj: object) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha_text(payload)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                raise RuntimeError(f"invalid JSONL {path}:{line_no}: {exc}") from exc
    return rows


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path: Path, obj: dict) -> None:
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    atomic_text(path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def verify_sha_manifest(path: Path) -> int:
    checked = 0
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                raise RuntimeError(f"invalid SHA manifest line {path}:{line_no}")
            expected, rel = parts
            rel = rel.strip().lstrip("*")
            target = Path(rel)
            if not target.is_absolute():
                target = ROOT / target
            if not target.is_file():
                raise RuntimeError(f"SHA manifest target missing: {target}")
            actual = sha_file(target)
            if actual != expected:
                raise RuntimeError(f"SHA mismatch {target}: expected={expected} actual={actual}")
            checked += 1
    return checked


def c1_profile_config(profile_id: str, input_profile: str) -> dict:
    return {
        "profile_id": profile_id,
        "version": 1,
        "mode": "hybrid",
        "embedding": {
            "provider": "multilingual-e5",
            "model": "intfloat/multilingual-e5-small",
            "revision": None,
            "dimensions": 384,
            "input_profile": input_profile,
        },
        "fusion": {"algorithm": "rrf-v1", "k": 60},
        "diversity": {"algorithm": "source-file-soft-cap-v1", "max_per_file": 2},
        "reranker": None,
    }


def validate_profile_hashes(config: dict) -> None:
    for profile in config["primary_profiles"]:
        actual = canonical_sha(c1_profile_config(profile["profile_id"], profile["input_profile"]))
        if actual != profile["config_hash"]:
            raise RuntimeError(
                f"C1 profile hash mismatch {profile['profile_id']}: expected={profile['config_hash']} actual={actual}"
            )


def normalized_url_path(dist: dict) -> str | None:
    value = str(dist.get("final_url") or dist.get("download_url") or "").strip()
    if not value:
        return None
    path = unquote(urlsplit(value).path or "")
    path = re.sub(r"/{2,}", "/", path).strip()
    return None if path in {"", "/"} else path


def distribution_identity(dataset_id: str, distribution_id: str, payload_sha256: str) -> tuple[str, str, str]:
    return (dataset_id, distribution_id, payload_sha256)


def chunk_identity(row: dict) -> tuple[str, str, str, int, str]:
    return (
        row["dataset_id"],
        row["distribution_id"],
        row["payload_sha256"],
        int(row["chunk_index"]),
        row["chunk_text_sha256"],
    )


def identity_hash(parts: tuple[object, ...]) -> str:
    return sha_text("\0".join(str(x) for x in parts))


def load_and_validate_inputs(corpus: Path, queries_dir: Path, config_path: Path) -> tuple[dict, list[dict], list[dict], list[dict]]:
    config = read_json(config_path)
    validate_profile_hashes(config)

    prequery_manifest = corpus / "SHA256SUMS.prequery.txt"
    query_manifest = queries_dir / "SHA256SUMS.query_freeze.txt"
    prequery_checked = verify_sha_manifest(prequery_manifest)
    query_checked = verify_sha_manifest(query_manifest)

    corpus_freeze_path = corpus / "corpus_freeze.json"
    selected_path = corpus / "selected_corpus_manifest.jsonl"
    chunks_path = corpus / "chunk_manifest.jsonl"
    query_freeze_path = queries_dir / "query_freeze.json"
    query_audit_path = queries_dir / "query_audit.json"
    queries_path = queries_dir / "queries.jsonl"

    corpus_freeze = read_json(corpus_freeze_path)
    query_freeze = read_json(query_freeze_path)
    if sha_file(corpus_freeze_path) != config["corpus"]["corpus_freeze_sha256"]:
        raise RuntimeError("corpus_freeze hash mismatch against C2 retrieval config")
    if sha_file(selected_path) != config["corpus"]["selected_corpus_manifest_sha256"]:
        raise RuntimeError("selected manifest hash mismatch against C2 retrieval config")
    if sha_file(chunks_path) != config["corpus"]["chunk_manifest_sha256"]:
        raise RuntimeError("chunk manifest hash mismatch against C2 retrieval config")
    if sha_file(queries_path) != config["queries"]["queries_sha256"]:
        raise RuntimeError("queries hash mismatch against C2 retrieval config")
    if sha_file(query_audit_path) != config["queries"]["query_audit_sha256"]:
        raise RuntimeError("query audit hash mismatch against C2 retrieval config")
    if query_freeze.get("status") != config["queries"]["query_status"]:
        raise RuntimeError("query freeze status mismatch")
    if query_freeze.get("retrieval_executed") is not False:
        raise RuntimeError("query artifact does not preserve the pre-retrieval boundary")
    if corpus_freeze.get("corpus_revision") != config["corpus"]["revision"]:
        raise RuntimeError("corpus revision mismatch")

    selected = read_jsonl(selected_path)
    physical_chunks = read_jsonl(chunks_path)
    queries = read_jsonl(queries_path)
    if len(selected) != int(config["corpus"]["theme_stratum_records"]):
        raise RuntimeError(f"selected row count mismatch: {len(selected)}")
    if len(physical_chunks) != int(config["corpus"]["physical_chunk_rows"]):
        raise RuntimeError(f"physical chunk row count mismatch: {len(physical_chunks)}")
    if len(queries) != int(config["queries"]["query_count"]):
        raise RuntimeError(f"query row count mismatch: {len(queries)}")
    qids = [q["query_id"] for q in queries]
    if len(qids) != len(set(qids)):
        raise RuntimeError("duplicate query IDs")

    config["_verified_prequery_entries"] = prequery_checked
    config["_verified_query_entries"] = query_checked
    return config, selected, physical_chunks, queries


def build_logical_chunks(selected: list[dict], physical_chunks: list[dict]) -> tuple[list[dict], dict]:
    dist_map: dict[tuple[str, str, str], dict] = {}
    expected_physical_counts: Counter[tuple[str, str, str]] = Counter()
    for dataset in selected:
        theme = dataset["theme"]
        dsid = dataset["dataset_id"]
        title = str(dataset.get("title") or "").strip()
        for dist in dataset.get("distributions", []):
            key = (theme, dsid, dist["distribution_id"])
            if key in dist_map:
                raise RuntimeError(f"duplicate selected distribution key: {key}")
            dist_map[key] = {
                "payload_sha256": dist["payload_sha256"],
                "title": title,
                "file_path": normalized_url_path(dist),
                "expected_chunk_count": int(dist["chunk_count"]),
            }

    logical: dict[tuple[str, str, str, int, str], dict] = {}
    for chunk in physical_chunks:
        dkey = (chunk["theme"], chunk["dataset_id"], chunk["distribution_id"])
        dist = dist_map.get(dkey)
        if dist is None:
            raise RuntimeError(f"chunk references unknown selected distribution: {dkey}")
        expected_physical_counts[dkey] += 1
        if chunk["chunk_text_sha256"] != sha_text(chunk["chunk_text"]):
            raise RuntimeError(f"chunk text hash mismatch: {dkey} chunk={chunk['chunk_index']}")
        row = {
            "dataset_id": chunk["dataset_id"],
            "distribution_id": chunk["distribution_id"],
            "payload_sha256": dist["payload_sha256"],
            "chunk_index": int(chunk["chunk_index"]),
            "chunk_text_sha256": chunk["chunk_text_sha256"],
            "chunk_text": chunk["chunk_text"],
            "dataset_title": dist["title"],
            "file_path": dist["file_path"],
            "theme_memberships": [chunk["theme"]],
        }
        key = chunk_identity(row)
        old = logical.get(key)
        if old is None:
            logical[key] = row
        else:
            if old["chunk_text"] != row["chunk_text"]:
                raise RuntimeError(f"fine identity has different text: {key}")
            if old["dataset_title"] != row["dataset_title"] or old["file_path"] != row["file_path"]:
                raise RuntimeError(f"fine identity has ambiguous metadata-v1 context: {key}")
            if chunk["theme"] not in old["theme_memberships"]:
                old["theme_memberships"].append(chunk["theme"])

    for key, dist in dist_map.items():
        got = expected_physical_counts[key]
        if got != dist["expected_chunk_count"]:
            raise RuntimeError(f"distribution chunk count mismatch {key}: got={got} expected={dist['expected_chunk_count']}")

    rows = sorted(logical.values(), key=chunk_identity)
    for index, row in enumerate(rows):
        row["logical_index"] = index
        row["theme_memberships"] = sorted(row["theme_memberships"])
        row["distribution_identity_sha256"] = identity_hash(
            distribution_identity(row["dataset_id"], row["distribution_id"], row["payload_sha256"])
        )
        row["logical_chunk_identity_sha256"] = identity_hash(chunk_identity(row))

    audit = {
        "physical_chunk_rows": len(physical_chunks),
        "logical_chunk_rows": len(rows),
        "cross_theme_exact_fine_identity_collapses": len(physical_chunks) - len(rows),
        "unique_dataset_ids_in_logical_universe": len({r["dataset_id"] for r in rows}),
        "unique_distribution_identities": len({r["distribution_identity_sha256"] for r in rows}),
    }
    return rows, audit


def logical_order_records(rows: list[dict]) -> list[dict]:
    return [
        {
            "logical_index": r["logical_index"],
            "dataset_id": r["dataset_id"],
            "distribution_id": r["distribution_id"],
            "payload_sha256": r["payload_sha256"],
            "chunk_index": r["chunk_index"],
            "chunk_text_sha256": r["chunk_text_sha256"],
            "distribution_identity_sha256": r["distribution_identity_sha256"],
            "logical_chunk_identity_sha256": r["logical_chunk_identity_sha256"],
            "theme_memberships": r["theme_memberships"],
            "dataset_title": r["dataset_title"],
            "file_path": r["file_path"],
        }
        for r in rows
    ]


def package_versions() -> dict:
    names = ["numpy", "sentence-transformers", "transformers", "torch", "huggingface-hub"]
    out = {}
    for name in names:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = None
    return out


def ensure_input_freeze(corpus: Path, queries_dir: Path, out: Path, config_path: Path, adapter_path: Path) -> tuple[dict, list[dict], list[dict], dict]:
    config, selected, physical_chunks, queries = load_and_validate_inputs(corpus, queries_dir, config_path)
    logical_rows, logical_audit = build_logical_chunks(selected, physical_chunks)

    out.mkdir(parents=True, exist_ok=True)
    logical_path = out / "logical_chunk_order.jsonl"
    records = logical_order_records(logical_rows)
    expected_text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records)
    if logical_path.exists():
        if logical_path.read_text(encoding="utf-8") != expected_text:
            raise RuntimeError("existing logical_chunk_order.jsonl differs from frozen inputs")
    else:
        atomic_text(logical_path, expected_text)

    freeze = {
        "artifact": "SECOND_CORPUS_C2_RETRIEVAL_INPUT_FREEZE_V1",
        "status": "FROZEN_BEFORE_PRIMARY_RETRIEVAL",
        "config_sha256": sha_file(config_path),
        "adapter_sha256": sha_file(adapter_path),
        "runner_script_sha256": sha_file(Path(__file__)),
        "prequery_sha_manifest_sha256": sha_file(corpus / "SHA256SUMS.prequery.txt"),
        "query_freeze_sha_manifest_sha256": sha_file(queries_dir / "SHA256SUMS.query_freeze.txt"),
        "corpus_freeze_sha256": sha_file(corpus / "corpus_freeze.json"),
        "query_freeze_sha256": sha_file(queries_dir / "query_freeze.json"),
        "queries_sha256": sha_file(queries_dir / "queries.jsonl"),
        "logical_chunk_order_sha256": sha_file(logical_path),
        "logical_audit": logical_audit,
        "profile_hashes": {p["profile_id"]: p["config_hash"] for p in config["primary_profiles"]},
        "verified_prequery_sha_entries": config["_verified_prequery_entries"],
        "verified_query_freeze_sha_entries": config["_verified_query_entries"],
        "retrieval_results_inspected": False,
    }
    freeze_path = out / "retrieval_input_freeze.json"
    if freeze_path.exists():
        old = read_json(freeze_path)
        if old != freeze:
            raise RuntimeError("RETRIEVAL_INPUT_FREEZE_CHANGED; refusing to continue")
    else:
        atomic_json(freeze_path, freeze)

    return config, logical_rows, queries, freeze


def metadata_document_text(row: dict) -> str:
    parts: list[str] = []
    if str(row.get("dataset_title") or "").strip():
        parts.append(f"Dataset title: {str(row['dataset_title']).strip()}")
    if str(row.get("file_path") or "").strip():
        parts.append(f"File path: {str(row['file_path']).strip()}")
    parts.append(f"Content:\n{row['chunk_text']}")
    return "\n".join(parts)


def atomic_npy(path: Path, array) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        import numpy as np
        np.save(f, array, allow_pickle=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def validate_npy(path: Path, expected_rows: int, dimensions: int) -> None:
    import numpy as np
    arr = np.load(path, allow_pickle=False)
    if arr.shape != (expected_rows, dimensions):
        raise RuntimeError(f"embedding shard shape mismatch {path}: {arr.shape}")
    if arr.dtype != np.float32:
        raise RuntimeError(f"embedding shard dtype mismatch {path}: {arr.dtype}")
    if not np.isfinite(arr).all():
        raise RuntimeError(f"non-finite embedding values: {path}")


def pgvector_roundtrip_check(array) -> None:
    import numpy as np
    flat = np.asarray(array, dtype=np.float32).ravel()
    if flat.size == 0:
        return
    step = max(1, flat.size // 4096)
    for value in flat[::step][:4096]:
        roundtrip = np.float32(float(format(float(value), ".10g")))
        if roundtrip != value:
            raise RuntimeError("float32 value does not round-trip through C1 .10g pgvector serialization")


def resolve_model_snapshot(model_id: str, contract: dict | None) -> tuple[Path, str]:
    from huggingface_hub import snapshot_download
    revision = None if contract is None else contract["resolved_model_revision"]
    path = Path(snapshot_download(repo_id=model_id, revision=revision)).resolve()
    parts = list(path.parts)
    resolved = path.name
    if "snapshots" in parts:
        pos = parts.index("snapshots")
        if pos + 1 < len(parts):
            resolved = parts[pos + 1]
    if contract is not None and resolved != contract["resolved_model_revision"]:
        raise RuntimeError(
            f"resolved model revision changed: expected={contract['resolved_model_revision']} actual={resolved}"
        )
    return path, resolved


def load_sentence_model(snapshot_path: Path, device: str):
    from sentence_transformers import SentenceTransformer
    kwargs = {} if device.strip().lower() in {"", "auto"} else {"device": device}
    return SentenceTransformer(str(snapshot_path), **kwargs)


def encode_float32(model, texts: list[str], batch_size: int, dimensions: int):
    import numpy as np
    encoded = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=batch_size,
    )
    arr = np.asarray(encoded, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.shape != (len(texts), dimensions):
        raise RuntimeError(f"unexpected embedding shape {arr.shape}; expected {(len(texts), dimensions)}")
    if not np.isfinite(arr).all():
        raise RuntimeError("non-finite E5 embedding")
    pgvector_roundtrip_check(arr)
    return arr


def embedding_shard_path(out: Path, profile: str, start: int, end: int) -> Path:
    return out / "embeddings" / profile / f"shard_{start:06d}_{end:06d}.npy"


def run_embed(corpus: Path, queries_dir: Path, out: Path, config_path: Path, adapter_path: Path, device: str) -> None:
    config, rows, queries, input_freeze = ensure_input_freeze(corpus, queries_dir, out, config_path, adapter_path)
    versions = package_versions()
    for required in ("numpy", "sentence-transformers", "huggingface-hub"):
        if versions.get(required) is None:
            raise RuntimeError(f"missing retrieval dependency: {required}")

    contract_path = out / "embedding_contract.json"
    old_contract = read_json(contract_path) if contract_path.exists() else None
    model_id = config["embedding"]["model"]
    snapshot_path, resolved_revision = resolve_model_snapshot(model_id, old_contract)
    model = load_sentence_model(snapshot_path, device)
    actual_device = str(getattr(model, "device", "unknown"))
    contract = {
        "artifact": "SECOND_CORPUS_C2_EMBEDDING_CONTRACT_V1",
        "input_freeze_sha256": sha_file(out / "retrieval_input_freeze.json"),
        "model": model_id,
        "declared_profile_revision": config["embedding"]["declared_profile_revision"],
        "resolved_model_revision": resolved_revision,
        "dimensions": int(config["embedding"]["dimensions"]),
        "normalize_embeddings": True,
        "document_prefix": "passage",
        "query_prefix": "query",
        "pgvector_component_serialization": config["embedding"]["pgvector_component_serialization"],
        "requested_device": device,
        "actual_device": actual_device,
        "package_versions": versions,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    if old_contract is not None:
        if old_contract != contract:
            raise RuntimeError("EMBEDDING_CONTRACT_CHANGED; refusing to mix embedding shards")
    else:
        atomic_json(contract_path, contract)

    dims = int(config["embedding"]["dimensions"])
    shard_size = int(config["embedding"]["checkpoint_rows_per_shard"])
    encode_batch = int(config["embedding"]["model_encode_batch_size"])

    profile_inputs = {
        "content-v1": lambda r: r["chunk_text"],
        "metadata-v1": metadata_document_text,
    }
    for profile_name, builder in profile_inputs.items():
        for start in range(0, len(rows), shard_size):
            end = min(len(rows), start + shard_size)
            path = embedding_shard_path(out, profile_name, start, end)
            if path.exists():
                validate_npy(path, end - start, dims)
                print(f"EMBED_SHARD_ALREADY_PASS profile={profile_name} rows={start}:{end}", flush=True)
                continue
            values = [f"passage: {builder(row)}" for row in rows[start:end]]
            arr = encode_float32(model, values, encode_batch, dims)
            atomic_npy(path, arr)
            validate_npy(path, end - start, dims)
            print(f"EMBED_SHARD_PASS profile={profile_name} rows={start}:{end}", flush=True)

    query_path = out / "embeddings" / "queries.npy"
    if query_path.exists():
        validate_npy(query_path, len(queries), dims)
    else:
        values = [f"query: {q['query_text']}" for q in queries]
        arr = encode_float32(model, values, encode_batch, dims)
        atomic_npy(query_path, arr)
        validate_npy(query_path, len(queries), dims)
        print(f"QUERY_EMBEDDINGS_PASS rows={len(queries)}", flush=True)

    profiles = {}
    for profile_name in profile_inputs:
        shards = []
        for start in range(0, len(rows), shard_size):
            end = min(len(rows), start + shard_size)
            path = embedding_shard_path(out, profile_name, start, end)
            validate_npy(path, end - start, dims)
            shards.append(
                {
                    "start": start,
                    "end": end,
                    "rows": end - start,
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha_file(path),
                }
            )
        profiles[profile_name] = {"rows": len(rows), "dimensions": dims, "shards": shards}

    manifest = {
        "artifact": "SECOND_CORPUS_C2_EMBEDDING_MANIFEST_V1",
        "status": "FROZEN_BEFORE_PRIMARY_RETRIEVAL",
        "input_freeze_sha256": sha_file(out / "retrieval_input_freeze.json"),
        "embedding_contract_sha256": sha_file(contract_path),
        "logical_chunk_order_sha256": sha_file(out / "logical_chunk_order.jsonl"),
        "query_count": len(queries),
        "logical_chunk_count": len(rows),
        "query_embeddings": {
            "path": str(query_path.relative_to(ROOT)),
            "sha256": sha_file(query_path),
            "rows": len(queries),
            "dimensions": dims,
        },
        "profiles": profiles,
        "retrieval_executed": False,
    }
    manifest_path = out / "embedding_manifest.json"
    if manifest_path.exists():
        if read_json(manifest_path) != manifest:
            raise RuntimeError("EMBEDDING_MANIFEST_CHANGED")
    else:
        atomic_json(manifest_path, manifest)
    print("C2_EMBEDDINGS_FROZEN", flush=True)
    print(json.dumps({
        "logical_chunk_count": len(rows),
        "query_count": len(queries),
        "resolved_model_revision": resolved_revision,
        "actual_device": actual_device,
        "embedding_manifest_sha256": sha_file(manifest_path),
    }, sort_keys=True), flush=True)


def verify_embedding_manifest(out: Path) -> dict:
    import numpy as np
    manifest_path = out / "embedding_manifest.json"
    contract_path = out / "embedding_contract.json"
    input_path = out / "retrieval_input_freeze.json"
    if not manifest_path.exists() or not contract_path.exists() or not input_path.exists():
        raise RuntimeError("embedding/input freeze incomplete; run --mode embed first")
    manifest = read_json(manifest_path)
    if manifest["input_freeze_sha256"] != sha_file(input_path):
        raise RuntimeError("embedding manifest input-freeze mismatch")
    if manifest["embedding_contract_sha256"] != sha_file(contract_path):
        raise RuntimeError("embedding contract hash mismatch")
    for profile in manifest["profiles"].values():
        for shard in profile["shards"]:
            path = ROOT / shard["path"]
            if sha_file(path) != shard["sha256"]:
                raise RuntimeError(f"embedding shard hash mismatch: {path}")
            arr = np.load(path, allow_pickle=False, mmap_mode="r")
            if arr.shape != (int(shard["rows"]), int(profile["dimensions"])):
                raise RuntimeError(f"embedding shard shape mismatch: {path}")
    q = manifest["query_embeddings"]
    qpath = ROOT / q["path"]
    if sha_file(qpath) != q["sha256"]:
        raise RuntimeError("query embedding hash mismatch")
    return manifest


def load_embedding_matrix(profile: dict):
    import numpy as np
    arrays = [np.load(ROOT / shard["path"], allow_pickle=False) for shard in profile["shards"]]
    arr = np.vstack(arrays).astype(np.float32, copy=False)
    if arr.shape != (int(profile["rows"]), int(profile["dimensions"])):
        raise RuntimeError(f"assembled embedding matrix shape mismatch: {arr.shape}")
    return arr


def normalize_lexical(value: str) -> str:
    return " ".join(value.casefold().split())


def lexical_candidates(query: str, normalized_texts: list[str], rows: list[dict], limit: int) -> list[dict]:
    tokens = [m.group(0).casefold() for m in TOKEN_RE.finditer(query) if m.group(0).strip()]
    if not tokens:
        return []
    normalized_query = normalize_lexical(query)
    ranked = []
    for idx, text in enumerate(normalized_texts):
        matched = sum(1 for token in tokens if token in text)
        if matched == 0:
            continue
        score = matched / len(tokens)
        if normalized_query and normalized_query in text:
            score += 0.25
        score = round(score, 6)
        ranked.append((score, idx))
    ranked.sort(key=lambda pair: (-pair[0], chunk_identity(rows[pair[1]])))
    return [
        {"idx": idx, "score": score, "lexical_rank": rank, "vector_rank": None, "vector_similarity": None}
        for rank, (score, idx) in enumerate(ranked[:limit], 1)
    ]


def vector_candidates(query_vector, matrix, norms, rows: list[dict], limit: int) -> list[dict]:
    import numpy as np
    q = np.asarray(query_vector, dtype=np.float32)
    qnorm = np.linalg.norm(q)
    if not float(qnorm):
        return []
    scores = (matrix @ q) / (norms * qnorm)
    # Rows are already sorted by logical chunk identity. Stable sorting therefore
    # supplies the frozen identity tie break for exactly equal cosine scores.
    order = np.argsort(-scores, kind="stable")[:limit]
    out = []
    for rank, idx in enumerate(order.tolist(), 1):
        out.append(
            {
                "idx": int(idx),
                "score": float(scores[idx]),
                "lexical_rank": None,
                "vector_rank": rank,
                "vector_similarity": float(scores[idx]),
            }
        )
    return out


def rrf_fuse(lexical: list[dict], vector: list[dict], rows: list[dict], candidate_limit: int, k: int) -> list[dict]:
    fused: dict[int, dict] = {}
    for rank, item in enumerate(lexical, 1):
        fused[item["idx"]] = {
            "idx": item["idx"],
            "score": 1.0 / (k + rank),
            "lexical_rank": rank,
            "vector_rank": None,
            "vector_similarity": None,
        }
    for rank, item in enumerate(vector, 1):
        rec = fused.setdefault(
            item["idx"],
            {"idx": item["idx"], "score": 0.0, "lexical_rank": None, "vector_rank": None, "vector_similarity": None},
        )
        rec["score"] += 1.0 / (k + rank)
        rec["vector_rank"] = rank
        rec["vector_similarity"] = item["vector_similarity"]
    ranked = sorted(
        fused.values(),
        key=lambda x: (-float(x["score"]), chunk_identity(rows[x["idx"]])),
    )[:candidate_limit]
    return ranked


def diversify(ranked: list[dict], rows: list[dict], top_k: int, cap: int) -> list[dict]:
    counts: Counter[tuple[str, str, str]] = Counter()
    selected: list[dict] = []
    deferred: list[dict] = []
    for item in ranked:
        row = rows[item["idx"]]
        source = distribution_identity(row["dataset_id"], row["distribution_id"], row["payload_sha256"])
        if counts[source] >= cap:
            deferred.append(item)
            continue
        selected.append(item)
        counts[source] += 1
        if len(selected) >= top_k:
            return selected[:top_k]
    for item in deferred:
        selected.append(item)
        if len(selected) >= top_k:
            break
    return selected[:top_k]


def evidence_record(rank: int, item: dict, rows: list[dict]) -> dict:
    row = rows[item["idx"]]
    return {
        "rank": rank,
        "dataset_id": row["dataset_id"],
        "distribution_id": row["distribution_id"],
        "payload_sha256": row["payload_sha256"],
        "chunk_index": row["chunk_index"],
        "chunk_text_sha256": row["chunk_text_sha256"],
        "distribution_identity_sha256": row["distribution_identity_sha256"],
        "logical_chunk_identity_sha256": row["logical_chunk_identity_sha256"],
        "theme_memberships": row["theme_memberships"],
        "score": round(float(item["score"]), 8),
        "lexical_rank": item.get("lexical_rank"),
        "vector_rank": item.get("vector_rank"),
        "vector_similarity": None if item.get("vector_similarity") is None else round(float(item["vector_similarity"]), 10),
    }


def run_retrieve(corpus: Path, queries_dir: Path, out: Path, config_path: Path, adapter_path: Path) -> None:
    import numpy as np
    config, rows, queries, input_freeze = ensure_input_freeze(corpus, queries_dir, out, config_path, adapter_path)
    manifest = verify_embedding_manifest(out)
    if int(manifest["logical_chunk_count"]) != len(rows) or int(manifest["query_count"]) != len(queries):
        raise RuntimeError("embedding manifest row counts do not match frozen retrieval inputs")

    final_path = out / "primary_retrieval_runs.jsonl"
    freeze_path = out / "retrieval_freeze.json"
    if final_path.exists() or freeze_path.exists():
        raise RuntimeError("PRIMARY_RETRIEVAL_ALREADY_FROZEN; refusing to mutate")

    query_emb_meta = manifest["query_embeddings"]
    query_vectors = np.load(ROOT / query_emb_meta["path"], allow_pickle=False).astype(np.float32, copy=False)
    matrices = {
        "content-v1": load_embedding_matrix(manifest["profiles"]["content-v1"]),
        "metadata-v1": load_embedding_matrix(manifest["profiles"]["metadata-v1"]),
    }
    norms = {name: np.linalg.norm(matrix, axis=1).astype(np.float32) for name, matrix in matrices.items()}
    if any(np.any(value == 0) for value in norms.values()):
        raise RuntimeError("zero-norm document embedding encountered")

    normalized_texts = [normalize_lexical(r["chunk_text"]) for r in rows]
    candidate_limit = int(config["retrieval"]["candidate_limit"])
    top_k = int(config["retrieval"]["top_k"])
    rrf_k = int(config["retrieval"]["rrf_k"])
    cap = int(config["retrieval"]["diversity_max_per_source"])
    profile_order = [p["profile_id"] for p in config["primary_profiles"]]
    profile_by_id = {p["profile_id"]: p for p in config["primary_profiles"]}
    input_hash = sha_file(out / "retrieval_input_freeze.json")
    embedding_hash = sha_file(out / "embedding_manifest.json")
    config_hash = sha_file(config_path)

    partial_path = out / "retrieval_runs.partial.jsonl"
    existing = read_jsonl(partial_path) if partial_path.exists() else []
    done: dict[tuple[str, str], dict] = {}
    for row in existing:
        key = (row["query_id"], row["profile_id"])
        if key in done:
            raise RuntimeError(f"duplicate partial retrieval run: {key}")
        if row.get("retrieval_input_freeze_sha256") != input_hash:
            raise RuntimeError(f"partial run input-freeze mismatch: {key}")
        if row.get("embedding_manifest_sha256") != embedding_hash:
            raise RuntimeError(f"partial run embedding-manifest mismatch: {key}")
        if row.get("retrieval_config_sha256") != config_hash:
            raise RuntimeError(f"partial run config mismatch: {key}")
        done[key] = row

    total = len(queries) * len(profile_order)
    print(f"C2_PRIMARY_RETRIEVAL_START queries={len(queries)} profiles={len(profile_order)} runs={total}", flush=True)
    print(f"RESUME_COMPLETED_RUNS={len(done)}", flush=True)
    for qidx, query in enumerate(queries):
        lex = lexical_candidates(query["query_text"], normalized_texts, rows, candidate_limit)
        for profile_id in profile_order:
            key = (query["query_id"], profile_id)
            if key in done:
                continue
            p = profile_by_id[profile_id]
            input_profile = p["input_profile"]
            vec = vector_candidates(query_vectors[qidx], matrices[input_profile], norms[input_profile], rows, candidate_limit)
            fused = rrf_fuse(lex, vec, rows, candidate_limit, rrf_k)
            final = diversify(fused, rows, top_k, cap)
            if len(final) != top_k:
                raise RuntimeError(f"retrieval returned {len(final)} != {top_k} for {key}")
            evidence = [evidence_record(rank, item, rows) for rank, item in enumerate(final, 1)]
            run = {
                "query_id": query["query_id"],
                "theme": query["theme"],
                "query_type": query["query_type"],
                "cell_replicate": int(query["cell_replicate"]),
                "query_text_sha256": query["query_text_sha256"],
                "source_dataset_ids": query["source_dataset_ids"],
                "source_multiplicity_Mq_from_frozen_sources": query["source_multiplicity_Mq_from_frozen_sources"],
                "profile_id": profile_id,
                "profile_hash": p["config_hash"],
                "candidate_limit": candidate_limit,
                "top_k": top_k,
                "rrf_k": rrf_k,
                "diversity_max_per_source": cap,
                "retrieval_input_freeze_sha256": input_hash,
                "embedding_manifest_sha256": embedding_hash,
                "retrieval_config_sha256": config_hash,
                "ordered_evidence": evidence,
            }
            append_jsonl(partial_path, run)
            done[key] = run
            print(f"RETRIEVAL_PASS {len(done)}/{total} query={query['query_id']} profile={profile_id}", flush=True)

    if len(done) != total:
        raise RuntimeError(f"retrieval checkpoint incomplete: {len(done)}/{total}")
    canonical_runs = [done[(q["query_id"], pid)] for pid in profile_order for q in queries]
    write_jsonl(final_path, canonical_runs)

    freeze = {
        "artifact": "SECOND_CORPUS_C2_PRIMARY_RETRIEVAL_FREEZE_V1",
        "status": "FROZEN_BEFORE_CONFIRMATORY_ANALYSIS",
        "retrieval_config_sha256": config_hash,
        "adapter_sha256": sha_file(adapter_path),
        "runner_script_sha256": sha_file(Path(__file__)),
        "retrieval_input_freeze_sha256": input_hash,
        "embedding_contract_sha256": sha_file(out / "embedding_contract.json"),
        "embedding_manifest_sha256": embedding_hash,
        "logical_chunk_order_sha256": sha_file(out / "logical_chunk_order.jsonl"),
        "queries_sha256": sha_file(queries_dir / "queries.jsonl"),
        "primary_retrieval_runs_sha256": sha_file(final_path),
        "run_count": len(canonical_runs),
        "ordered_evidence_slots": len(canonical_runs) * top_k,
        "query_count": len(queries),
        "logical_chunk_count": len(rows),
        "profile_ids": profile_order,
        "profile_hashes": {p["profile_id"]: p["config_hash"] for p in config["primary_profiles"]},
        "top_k": top_k,
        "candidate_limit": candidate_limit,
        "rrf_k": rrf_k,
        "statistics_executed": False,
    }
    atomic_json(freeze_path, freeze)

    hash_paths = [
        config_path,
        adapter_path,
        Path(__file__),
        corpus / "corpus_freeze.json",
        corpus / "SHA256SUMS.prequery.txt",
        queries_dir / "query_freeze.json",
        queries_dir / "queries.jsonl",
        queries_dir / "SHA256SUMS.query_freeze.txt",
        out / "retrieval_input_freeze.json",
        out / "logical_chunk_order.jsonl",
        out / "embedding_contract.json",
        out / "embedding_manifest.json",
        final_path,
        freeze_path,
    ]
    sums = out / "SHA256SUMS.retrieval.txt"
    atomic_text(sums, "".join(f"{sha_file(p)}  {p.relative_to(ROOT)}\n" for p in hash_paths))
    print("C2_PRIMARY_RETRIEVAL_FROZEN", flush=True)
    print(json.dumps(freeze, indent=2, sort_keys=True), flush=True)


def status(out: Path) -> dict:
    partial = read_jsonl(out / "retrieval_runs.partial.jsonl") if (out / "retrieval_runs.partial.jsonl").exists() else []
    embedding_manifest = read_json(out / "embedding_manifest.json") if (out / "embedding_manifest.json").exists() else None
    shard_count = 0
    if embedding_manifest:
        shard_count = sum(len(v["shards"]) for v in embedding_manifest.get("profiles", {}).values())
    return {
        "retrieval_input_freeze_exists": (out / "retrieval_input_freeze.json").exists(),
        "logical_chunk_order_exists": (out / "logical_chunk_order.jsonl").exists(),
        "embedding_contract_exists": (out / "embedding_contract.json").exists(),
        "embedding_manifest_exists": embedding_manifest is not None,
        "frozen_embedding_shards": shard_count,
        "partial_retrieval_runs": len(partial),
        "primary_retrieval_frozen": (out / "retrieval_freeze.json").exists(),
        "primary_retrieval_runs_exists": (out / "primary_retrieval_runs.jsonl").exists(),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["preflight", "embed", "retrieve", "status"], default="preflight")
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER)
    ap.add_argument("--device", default="auto")
    args = ap.parse_args()

    if args.mode == "status":
        print(json.dumps(status(args.out), indent=2, sort_keys=True))
        return

    config, rows, queries, freeze = ensure_input_freeze(
        args.corpus, args.queries, args.out, args.config, args.adapter
    )
    if args.mode == "preflight":
        print("C2_RETRIEVAL_PREFLIGHT_PASS")
        print(json.dumps({
            "logical_audit": freeze["logical_audit"],
            "query_count": len(queries),
            "profile_hashes": freeze["profile_hashes"],
            "verified_prequery_sha_entries": freeze["verified_prequery_sha_entries"],
            "verified_query_freeze_sha_entries": freeze["verified_query_freeze_sha_entries"],
            "package_versions": package_versions(),
            "retrieval_input_freeze_sha256": sha_file(args.out / "retrieval_input_freeze.json"),
        }, indent=2, sort_keys=True))
        return
    if args.mode == "embed":
        run_embed(args.corpus, args.queries, args.out, args.config, args.adapter, args.device)
        return
    if args.mode == "retrieve":
        run_retrieve(args.corpus, args.queries, args.out, args.config, args.adapter)
        return


if __name__ == "__main__":
    main()
