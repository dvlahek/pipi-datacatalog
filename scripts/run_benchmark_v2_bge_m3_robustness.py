from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.embeddings import _embedding_inputs, reciprocal_rank_fusion
from app.rag.profiles import catalog_snapshot_hash
from app.rag.retrieval import diversify_ranked_results
from app.rag.store import RagStore

EXPECTED_SNAPSHOT = "068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419"
EXPECTED_CORPUS_FINGERPRINT = "f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6"
EXPECTED_CONFIRMATION_SHA256 = "c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5"
EXPECTED_QRELS_SHA256 = "a0946546b7b0109bfc8f0920b7cd8de6412c210cbe26ffb36f155f4a0a5637ad"
EXPECTED_CHUNKS = 3974

DEFAULT_PROTOCOL = ROOT / "config" / "rag_benchmark_v2_bge_m3_robustness.json"
DEFAULT_CASES = ROOT / "results" / f"benchmark_v2_confirmation_queries_frozen_{EXPECTED_CONFIRMATION_SHA256[:12]}.json"

MODEL_ID = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
DIMENSIONS = 1024
MAX_SEQ_LENGTH = 512
POOL_DEPTH = 20
EVAL_DEPTH = 10
CANDIDATE_DEPTH = 100
DIVERSITY_CAP = 2
RRF_K = 60

PROFILE_ORDER = (
    "vector-bge-m3-content-v1",
    "vector-bge-m3-metadata-v1",
    "hybrid-bge-m3-content-v1",
    "hybrid-bge-m3-metadata-v1",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def load_protocol(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("artifact") != "pipi-benchmark-v2-bge-m3-embedding-backbone-robustness-protocol":
        raise SystemExit("Unexpected BGE-M3 robustness protocol artifact.")
    frozen = payload.get("frozen_parent") or {}
    if frozen.get("catalog_snapshot_sha256") != EXPECTED_SNAPSHOT:
        raise SystemExit("Protocol snapshot mismatch.")
    if frozen.get("confirmation_cases_sha256") != EXPECTED_CONFIRMATION_SHA256:
        raise SystemExit("Protocol confirmation-query hash mismatch.")
    if frozen.get("final_qrels_sha256") != EXPECTED_QRELS_SHA256:
        raise SystemExit("Protocol qrels hash mismatch.")
    profile_ids = [item["profile_id"] for item in payload.get("profiles") or []]
    if tuple(profile_ids) != PROFILE_ORDER:
        raise SystemExit(f"Unexpected robustness profile order: {profile_ids}")
    return payload


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("artifact") != "pipi-benchmark-v2-confirmation-queries-frozen":
        raise SystemExit("Unexpected confirmation-query artifact.")
    if payload.get("catalog_snapshot_hash") != EXPECTED_SNAPSHOT:
        raise SystemExit("Confirmation-query snapshot mismatch.")
    if payload.get("corpus_fingerprint_sha256") != EXPECTED_CORPUS_FINGERPRINT:
        raise SystemExit("Confirmation-query corpus fingerprint mismatch.")
    if payload.get("confirmation_cases_sha256") != EXPECTED_CONFIRMATION_SHA256:
        raise SystemExit("Confirmation-query declared hash mismatch.")
    cases = list(payload.get("cases") or [])
    if len(cases) != 192:
        raise SystemExit(f"Expected 192 confirmation cases, got {len(cases)}.")
    return cases


def load_model(device: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit(
            "sentence-transformers is required. Install requirements-embeddings.txt first."
        ) from exc

    kwargs: dict[str, Any] = {"revision": MODEL_REVISION}
    if device.strip().lower() not in {"", "auto"}:
        kwargs["device"] = device
    model = SentenceTransformer(MODEL_ID, **kwargs)
    model.max_seq_length = MAX_SEQ_LENGTH
    return model


def encode(model, texts: list[str], *, batch_size: int, show_progress: bool) -> list[list[float]]:
    if not texts:
        return []
    encoded = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=show_progress,
    )
    rows = encoded.tolist()
    if rows and isinstance(rows[0], (int, float)):
        rows = [rows]
    vectors = [[float(x) for x in row] for row in rows]
    bad = [len(v) for v in vectors if len(v) != DIMENSIONS]
    if bad:
        raise SystemExit(
            f"BGE-M3 returned an unexpected vector dimension. Expected {DIMENSIONS}, got {bad[0]}."
        )
    return vectors


def embedding_identity(input_profile: str) -> str:
    return f"{MODEL_ID}@{MODEL_REVISION}#{input_profile}"


def prepare_embeddings(store, model, *, batch_size: int) -> dict[str, Any]:
    rag = RagStore(store)
    before = catalog_snapshot_hash(store)
    if before != EXPECTED_SNAPSHOT:
        raise SystemExit(
            f"BGE_M3_EMBED_REFUSED_SNAPSHOT_MISMATCH expected={EXPECTED_SNAPSHOT} actual={before}"
        )

    results: list[dict[str, Any]] = []
    for input_profile in ("content-v1", "metadata-v1"):
        identity = embedding_identity(input_profile)
        status_before = rag.embedding_status(identity)
        total = int(status_before["total_current_chunks"])
        if total != EXPECTED_CHUNKS:
            raise SystemExit(
                f"Current chunk count changed: expected {EXPECTED_CHUNKS}, got {total}."
            )

        rows = rag.list_current_chunks_for_embedding(identity, limit=EXPECTED_CHUNKS)
        print(
            f"EMBED_PROFILE={input_profile} IDENTITY={identity} "
            f"MISSING_BEFORE={status_before['missing']}"
        )

        embedded_now = 0
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            texts = _embedding_inputs(store, rag, batch, profile=input_profile)
            vectors = encode(model, texts, batch_size=batch_size, show_progress=False)
            written = rag.write_chunk_embeddings(
                [
                    {"chunk_id": int(row["chunk_id"]), "vector": vector}
                    for row, vector in zip(batch, vectors)
                ],
                model=identity,
                dimensions=DIMENSIONS,
                provider="sentence-transformers-bge-m3",
                base_model=MODEL_ID,
                revision=MODEL_REVISION,
                input_profile=input_profile,
            )
            embedded_now += int(written)
            done = min(start + len(batch), len(rows))
            if done == len(rows) or done % max(batch_size, 256) == 0:
                print(f"EMBED_PROGRESS {input_profile}={done}/{len(rows)}", flush=True)

        status_after = rag.embedding_status(identity)
        if not bool(status_after["complete"]):
            raise SystemExit(
                f"BGE-M3 embedding coverage incomplete for {input_profile}: {status_after}"
            )
        results.append(
            {
                "input_profile": input_profile,
                "embedding_identity": identity,
                "status_before": status_before,
                "embedded_now": embedded_now,
                "status_after": status_after,
            }
        )

    after = catalog_snapshot_hash(store)
    if after != before:
        raise SystemExit("Catalog snapshot changed while BGE-M3 embeddings were prepared.")

    return {
        "artifact": "pipi-benchmark-v2-bge-m3-embedding-preparation",
        "catalog_snapshot_hash": after,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "dimensions": DIMENSIONS,
        "normalize_embeddings": True,
        "query_instruction": None,
        "max_seq_length": MAX_SEQ_LENGTH,
        "profiles": results,
        "complete": all(bool(x["status_after"]["complete"]) for x in results),
    }


def safe_result(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return {
        "rank": int(item.get("rank") or 0),
        "dataset_identifier": str(item.get("dataset_identifier") or ""),
        "dataset_version": int(item.get("dataset_version") or 0),
        "chunk_index": int(item.get("chunk_index") or 0),
        "file_path": str(metadata.get("file_path") or "") or None,
        "text_sha256": sha256_text(str(item.get("text") or "")),
        "score": item.get("score"),
        "lexical_rank": item.get("lexical_rank"),
        "vector_rank": item.get("vector_rank"),
    }


def result_key(item: dict[str, Any]) -> tuple[str, int, int]:
    return (
        str(item.get("dataset_identifier") or ""),
        int(item.get("dataset_version") or 0),
        int(item.get("chunk_index") or 0),
    )


def vector_results(rag: RagStore, query_vector: list[float], identity: str) -> list[dict[str, Any]]:
    candidates = rag.vector_search(query_vector, model=identity, limit=CANDIDATE_DEPTH)
    diversified = diversify_ranked_results(
        candidates,
        limit=POOL_DEPTH,
        max_per_source=DIVERSITY_CAP,
    )
    original_rank = {result_key(item): rank for rank, item in enumerate(candidates, start=1)}
    results: list[dict[str, Any]] = []
    for rank, item in enumerate(diversified, start=1):
        row = dict(item)
        row["score"] = row.get("vector_similarity")
        row["vector_rank"] = original_rank[result_key(row)]
        row["lexical_rank"] = None
        row["rank"] = rank
        results.append(row)
    return results


def hybrid_results(
    rag: RagStore,
    query: str,
    query_vector: list[float],
    identity: str,
) -> list[dict[str, Any]]:
    lexical = rag.search_chunks(query, limit=CANDIDATE_DEPTH)
    vector = rag.vector_search(query_vector, model=identity, limit=CANDIDATE_DEPTH)
    fused = reciprocal_rank_fusion(lexical, vector, limit=CANDIDATE_DEPTH, k=RRF_K)
    diversified = diversify_ranked_results(
        fused,
        limit=POOL_DEPTH,
        max_per_source=DIVERSITY_CAP,
    )
    return [{"rank": rank, **item} for rank, item in enumerate(diversified, start=1)]


def read_qrels(path: Path) -> set[tuple[str, str, int, int]]:
    if sha256_file(path) != EXPECTED_QRELS_SHA256:
        raise SystemExit(
            "Final qrels SHA-256 mismatch. Use the frozen final confirmation qrels."
        )
    judged: set[tuple[str, str, int, int]] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"case_id", "dataset_identifier", "dataset_version", "chunk_index", "judgment"}
        if not required.issubset(reader.fieldnames or []):
            raise SystemExit(f"Unexpected qrels columns: {reader.fieldnames}")
        for row in reader:
            judged.add(
                (
                    row["case_id"],
                    row["dataset_identifier"],
                    int(row["dataset_version"]),
                    int(row["chunk_index"]),
                )
            )
    return judged


def coverage_audit(
    cases: list[dict[str, Any]],
    raw_results: dict[tuple[str, str], list[dict[str, Any]]],
    qrels_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    judged = read_qrels(qrels_path)
    novel_by_case: dict[str, dict[tuple[str, int, int], dict[str, Any]]] = defaultdict(dict)
    slots = 0
    judged_slots = 0
    profile_complete: dict[str, int] = defaultdict(int)

    for case in cases:
        case_id = str(case["case_id"])
        for profile_id in PROFILE_ORDER:
            top = raw_results[(case_id, profile_id)][:EVAL_DEPTH]
            slots += len(top)
            complete = True
            for item in top:
                key = result_key(item)
                qkey = (case_id, key[0], key[1], key[2])
                if qkey in judged:
                    judged_slots += 1
                    continue
                complete = False
                existing = novel_by_case[case_id].get(key)
                if existing is None:
                    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                    existing = {
                        "dataset_identifier": key[0],
                        "dataset_version": key[1],
                        "chunk_index": key[2],
                        "file_path": str(metadata.get("file_path") or "") or None,
                        "text": str(item.get("text") or ""),
                        "retrieved_by": {},
                    }
                    novel_by_case[case_id][key] = existing
                existing["retrieved_by"][profile_id] = int(item["rank"])
            if complete:
                profile_complete[profile_id] += 1

    pair_complete = {}
    for left, right, label in (
        ("vector-bge-m3-content-v1", "vector-bge-m3-metadata-v1", "vector"),
        ("hybrid-bge-m3-content-v1", "hybrid-bge-m3-metadata-v1", "hybrid"),
    ):
        count = 0
        for case in cases:
            case_id = str(case["case_id"])
            union: set[tuple[str, int, int]] = set()
            for profile_id in (left, right):
                union.update(
                    result_key(item)
                    for item in raw_results[(case_id, profile_id)][:EVAL_DEPTH]
                )
            if all((case_id, key[0], key[1], key[2]) in judged for key in union):
                count += 1
        pair_complete[label] = count

    pool_cases = []
    novel_total = 0
    for case in cases:
        case_id = str(case["case_id"])
        candidates = list(novel_by_case.get(case_id, {}).values())
        if not candidates:
            continue
        candidates.sort(
            key=lambda item: (
                min(item["retrieved_by"].values()),
                item["dataset_identifier"],
                item["dataset_version"],
                item["chunk_index"],
            )
        )
        novel_total += len(candidates)
        pool_cases.append(
            {
                "case_id": case_id,
                "source_family": case.get("source_family"),
                "query_type": case.get("query_type"),
                "language_relation": case.get("language_relation"),
                "information_need": case.get("information_need"),
                "query_text": case.get("query_text"),
                "query_language": case.get("query_language"),
                "target_evidence_language": case.get("target_evidence_language"),
                "candidates": candidates,
            }
        )

    audit = {
        "artifact": "pipi-benchmark-v2-bge-m3-qrels-coverage-audit",
        "evaluation_depth": EVAL_DEPTH,
        "top10_slots": slots,
        "already_judged_slots": judged_slots,
        "slot_coverage": 0.0 if slots == 0 else judged_slots / slots,
        "fully_judged_queries_by_profile": dict(profile_complete),
        "fully_judged_query_pairs": pair_complete,
        "unique_novel_top10_candidates": novel_total,
        "qrels_sha256": sha256_file(qrels_path),
        "policy": (
            "Do not compute qrels-based quality metrics until every novel top-10 candidate "
            "has a supplementary relevance judgment."
        ),
    }
    pool = {
        "artifact": "pipi-benchmark-v2-bge-m3-supplementary-judging-pool",
        "schema_version": 1,
        "status": "local-unjudged",
        "publication_safe": False,
        "contains_chunk_text": True,
        "relevance_scale": {
            "3": "directly answers the information need",
            "2": "clearly relevant supporting evidence but incomplete on its own",
            "1": "topically related but insufficient or weak evidence",
            "0": "irrelevant",
        },
        "cases": pool_cases,
    }
    return audit, pool


def run_retrieval(
    store,
    model,
    protocol: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    protocol_path: Path,
    batch_size: int,
    qrels_path: Path | None,
    output_dir: Path,
) -> None:
    rag = RagStore(store)
    before = catalog_snapshot_hash(store)
    if before != EXPECTED_SNAPSHOT:
        raise SystemExit(
            f"BGE_M3_RETRIEVAL_REFUSED_SNAPSHOT_MISMATCH expected={EXPECTED_SNAPSHOT} actual={before}"
        )

    for input_profile in ("content-v1", "metadata-v1"):
        status = rag.embedding_status(embedding_identity(input_profile))
        if not bool(status["complete"]) or int(status["embedded_current_model"]) != EXPECTED_CHUNKS:
            raise SystemExit(
                f"BGE-M3 vectors are incomplete for {input_profile}. Run --phase embed first."
            )

    profiles = {item["profile_id"]: item for item in protocol["profiles"]}
    safe_runs: list[dict[str, Any]] = []
    raw_results: dict[tuple[str, str], list[dict[str, Any]]] = {}
    total = len(cases) * len(PROFILE_ORDER)
    done = 0

    for case in cases:
        case_id = str(case["case_id"])
        query = str(case["query_text"])
        query_vector = encode(model, [query], batch_size=batch_size, show_progress=False)[0]

        content_identity = embedding_identity("content-v1")
        metadata_identity = embedding_identity("metadata-v1")

        for profile_id in PROFILE_ORDER:
            mode = profiles[profile_id]["config"]["mode"]
            input_profile = profiles[profile_id]["config"]["embedding"]["input_profile"]
            identity = content_identity if input_profile == "content-v1" else metadata_identity

            if mode == "vector":
                results = vector_results(rag, query_vector, identity)
                retrieval_name = f"pgvector-cosine-exact:{identity}"
            else:
                results = hybrid_results(rag, query, query_vector, identity)
                retrieval_name = f"hybrid-rrf-v1:lexical+pgvector:{identity}"

            if len(results) < EVAL_DEPTH:
                raise SystemExit(
                    f"Too few results for {case_id}/{profile_id}: {len(results)}"
                )

            raw_results[(case_id, profile_id)] = results
            safe_runs.append(
                {
                    "case_id": case_id,
                    "profile_id": profile_id,
                    "profile_hash": profiles[profile_id]["config_hash"],
                    "retrieval": retrieval_name,
                    "result_count": len(results),
                    "results": [safe_result(item) for item in results],
                }
            )

            done += 1
            if done == 1 or done % 40 == 0 or done == total:
                print(f"RETRIEVAL_PROGRESS={done}/{total}", flush=True)

    after = catalog_snapshot_hash(store)
    if after != before:
        raise SystemExit("Catalog snapshot changed during BGE-M3 robustness retrieval.")

    output_dir.mkdir(parents=True, exist_ok=True)
    protocol_hash = sha256_file(protocol_path)
    ledger = {
        "artifact": "pipi-benchmark-v2-bge-m3-robustness-retrieval-ledger",
        "schema_version": 1,
        "status": "post-hoc-robustness-retrieval-frozen-before-supplementary-judging",
        "catalog_snapshot_hash": before,
        "corpus_fingerprint_sha256": EXPECTED_CORPUS_FINGERPRINT,
        "confirmation_cases_sha256": EXPECTED_CONFIRMATION_SHA256,
        "robustness_protocol_sha256": protocol_hash,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "pool_depth_per_profile": POOL_DEPTH,
        "evaluation_depth": EVAL_DEPTH,
        "profiles": protocol["profiles"],
        "publication_safe": True,
        "contains_chunk_text": False,
        "runs": safe_runs,
    }
    ledger_path = output_dir / "benchmark_v2_bge_m3_robustness_retrieval_ledger.json"
    ledger_path.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(f"BGE_M3_RETRIEVAL_LEDGER={ledger_path}")
    print(f"BGE_M3_RETRIEVAL_LEDGER_SHA256={sha256_file(ledger_path)}")

    if qrels_path is not None:
        audit, pool = coverage_audit(cases, raw_results, qrels_path)
        audit["retrieval_ledger_sha256"] = sha256_file(ledger_path)
        audit_path = output_dir / "benchmark_v2_bge_m3_qrels_coverage_audit.json"
        pool_path = output_dir / "benchmark_v2_bge_m3_supplementary_judging_pool.json"
        audit_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        pool_path.write_text(
            json.dumps(pool, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"QRELS_SLOT_COVERAGE={audit['already_judged_slots']}/{audit['top10_slots']}")
        print(f"UNIQUE_NOVEL_TOP10_CANDIDATES={audit['unique_novel_top10_candidates']}")
        print(f"FULLY_JUDGED_VECTOR_PAIRS={audit['fully_judged_query_pairs']['vector']}/192")
        print(f"FULLY_JUDGED_HYBRID_PAIRS={audit['fully_judged_query_pairs']['hybrid']}/192")
        print(f"BGE_M3_QRELS_COVERAGE_AUDIT={audit_path}")
        print(f"BGE_M3_SUPPLEMENTARY_JUDGING_POOL={pool_path}")
        if audit["unique_novel_top10_candidates"] > 0:
            print("STOP_BEFORE_QUALITY_METRICS_SUPPLEMENTARY_JUDGING_REQUIRED")
        else:
            print("BGE_M3_TOP10_FULLY_COVERED_BY_FROZEN_QRELS")


def preflight(store, protocol_path: Path, cases_path: Path, qrels_path: Path | None) -> None:
    protocol = load_protocol(protocol_path)
    cases = load_cases(cases_path)
    snapshot = catalog_snapshot_hash(store)
    rag = RagStore(store)
    content_status = rag.embedding_status(embedding_identity("content-v1"))
    metadata_status = rag.embedding_status(embedding_identity("metadata-v1"))

    print("PIPI_BGE_M3_ROBUSTNESS_PREFLIGHT")
    print(f"CATALOG_SNAPSHOT={snapshot}")
    print(f"SNAPSHOT_MATCH={snapshot == EXPECTED_SNAPSHOT}")
    print(f"CASES={len(cases)}")
    print(f"ROBUSTNESS_PROTOCOL_SHA256={sha256_file(protocol_path)}")
    print(f"MODEL_ID={MODEL_ID}")
    print(f"MODEL_REVISION={MODEL_REVISION}")
    print(f"DIMENSIONS={DIMENSIONS}")
    print(f"MAX_SEQ_LENGTH={MAX_SEQ_LENGTH}")
    print(f"CONTENT_EMBEDDINGS={content_status}")
    print(f"METADATA_EMBEDDINGS={metadata_status}")
    if qrels_path is not None:
        print(f"QRELS={qrels_path}")
        print(f"QRELS_SHA256={sha256_file(qrels_path)}")
        print(f"QRELS_MATCH={sha256_file(qrels_path) == EXPECTED_QRELS_SHA256}")
    for item in protocol["profiles"]:
        print(f"PROFILE {item['profile_id']} HASH={item['config_hash']}")
    if snapshot != EXPECTED_SNAPSHOT:
        raise SystemExit(2)
    if qrels_path is not None and sha256_file(qrels_path) != EXPECTED_QRELS_SHA256:
        raise SystemExit(2)
    print("PIPI_BGE_M3_ROBUSTNESS_PREFLIGHT_PASS")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the frozen post-hoc BGE-M3 embedding-backbone robustness check."
    )
    parser.add_argument(
        "--phase",
        choices=("preflight", "embed", "retrieve", "all"),
        default="preflight",
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--qrels", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1.")
    if not args.protocol.is_file():
        raise SystemExit(f"Protocol not found: {args.protocol}")
    if not args.cases.is_file():
        raise SystemExit(f"Cases not found: {args.cases}")
    if args.qrels is not None and not args.qrels.is_file():
        raise SystemExit(f"Qrels not found: {args.qrels}")

    protocol = load_protocol(args.protocol)
    cases = load_cases(args.cases)
    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    if args.phase == "preflight":
        preflight(store, args.protocol, args.cases, args.qrels)
        return

    model = load_model(args.device)

    if args.phase in {"embed", "all"}:
        artifact = prepare_embeddings(store, model, batch_size=args.batch_size)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        path = args.output_dir / "benchmark_v2_bge_m3_embedding_preparation.json"
        artifact["robustness_protocol_sha256"] = sha256_file(args.protocol)
        path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"BGE_M3_EMBEDDING_PREPARATION={path}")
        print(f"BGE_M3_EMBEDDING_PREPARATION_SHA256={sha256_file(path)}")
        print("BGE_M3_EMBEDDINGS_READY")

    if args.phase in {"retrieve", "all"}:
        run_retrieval(
            store,
            model,
            protocol,
            cases,
            protocol_path=args.protocol,
            batch_size=args.batch_size,
            qrels_path=args.qrels,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":
    main()
