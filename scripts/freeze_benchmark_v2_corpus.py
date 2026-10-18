from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.profiles import catalog_snapshot_hash
from app.rag.store import RagStore


TARGET_QUERY_QUOTA = 60
MIN_DIVERSITY_RATIO = 0.40
FAMILIES = (
    "structured-data",
    "software-documentation",
    "institutional-documents",
    "open-data-catalogs",
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return _sha256_text(payload)


def _source_family(dataset: Any) -> str | None:
    identifier = str(dataset.identifier).casefold()
    source_system = str(dataset.source_system or "").casefold()
    dataset_type = str(dataset.dataset_type or "").casefold()

    if source_system == "sensor-hub" or identifier.startswith("urn:pipi:dataset:csv:"):
        return "structured-data"
    if source_system == "github" or dataset_type == "software-repository":
        return "software-documentation"
    if source_system == "foi-documents" or identifier.startswith("urn:pipi:dataset:foi-document:"):
        return "institutional-documents"
    if source_system.startswith("open-data:") or identifier.startswith("urn:pipi:dataset:open-data:"):
        return "open-data-catalogs"
    return None


def _git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> None:
    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    rag = RagStore(store)
    snapshot = catalog_snapshot_hash(store)
    protocol_path = ROOT / "config" / "rag_benchmark_v2_protocol.json"
    if not protocol_path.is_file():
        raise SystemExit(f"Benchmark protocol not found: {protocol_path}")
    protocol_sha256 = hashlib.sha256(protocol_path.read_bytes()).hexdigest()

    datasets = {dataset.identifier: dataset for dataset in store.list_datasets()}
    disabled = {
        str(resource.get("dataset_identifier") or "")
        for resource in store.list_resources()
        if not bool(resource.get("enabled")) and resource.get("dataset_identifier")
    }

    family_entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    family_chunk_counts: dict[str, int] = defaultdict(int)
    family_file_paths: dict[str, set[str]] = defaultdict(set)

    for status in sorted(rag.list_index_statuses(), key=lambda item: str(item.get("dataset_identifier") or "")):
        identifier = str(status.get("dataset_identifier") or "")
        if status.get("status") != "indexed" or identifier in disabled:
            continue
        dataset = datasets.get(identifier)
        if dataset is None:
            continue
        family = _source_family(dataset)
        if family not in FAMILIES:
            continue

        dataset_version = int(status.get("indexed_version") or 0)
        chunks = rag.list_chunks(identifier, dataset_version=dataset_version, limit=100000)
        document = dict(status.get("document") or {})
        versions = store.list_versions(identifier)
        current_version = versions[0] if versions else {}

        chunk_manifest: list[dict[str, Any]] = []
        for chunk in chunks:
            metadata = dict(chunk.get("metadata") or {})
            file_path = str(metadata.get("file_path") or "").strip()
            if file_path:
                family_file_paths[family].add(file_path)
            chunk_manifest.append(
                {
                    "chunk_index": int(chunk["chunk_index"]),
                    "char_start": int(chunk.get("char_start") or 0),
                    "char_end": int(chunk.get("char_end") or 0),
                    "text_sha256": _sha256_text(str(chunk.get("text") or "")),
                    "metadata_sha256": _sha256_json(metadata),
                }
            )

        family_chunk_counts[family] += len(chunk_manifest)
        family_entries[family].append(
            {
                "dataset_identifier": identifier,
                "dataset_version": dataset_version,
                "dataset_fingerprint": current_version.get("fingerprint"),
                "dataset_type": dataset.dataset_type,
                "source_system": dataset.source_system,
                "document": {
                    "media_type": document.get("media_type"),
                    "content_sha256": document.get("content_sha256"),
                    "extracted_text_sha256": document.get("extracted_text_sha256"),
                    "character_count": document.get("character_count"),
                    "chunk_count": document.get("chunk_count"),
                },
                "chunks": chunk_manifest,
            }
        )

    summaries: dict[str, dict[str, Any]] = {}
    capacity_ok = True
    for family in FAMILIES:
        entries = family_entries.get(family, [])
        if family == "software-documentation":
            diversity_units = len(family_file_paths.get(family, set()))
            diversity_label = "unique-files"
        else:
            diversity_units = len(entries)
            diversity_label = "datasets"
        ratio = diversity_units / TARGET_QUERY_QUOTA
        passed = diversity_units > 0 and ratio >= MIN_DIVERSITY_RATIO
        capacity_ok = capacity_ok and passed
        summaries[family] = {
            "dataset_count": len(entries),
            "chunk_count": family_chunk_counts.get(family, 0),
            "diversity_units": diversity_units,
            "diversity_unit": diversity_label,
            "ratio_to_query_quota": round(ratio, 6),
            "capacity_pass": passed,
        }

    if not capacity_ok:
        print("BENCHMARK_V2_CORPUS_FREEZE=REFUSED_CAPACITY_GATE")
        for family in FAMILIES:
            print(f"{family}: {summaries[family]}")
        raise SystemExit(2)

    corpus_payload = {
        "catalog_snapshot_hash": snapshot,
        "protocol_sha256": protocol_sha256,
        "families": {family: family_entries.get(family, []) for family in FAMILIES},
    }
    corpus_fingerprint = _sha256_json(corpus_payload)

    manifest = {
        "artifact": "pipi-benchmark-v2-frozen-corpus-manifest",
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "catalog_snapshot_hash": snapshot,
        "corpus_fingerprint_sha256": corpus_fingerprint,
        "protocol": {
            "path": "config/rag_benchmark_v2_protocol.json",
            "sha256": protocol_sha256,
        },
        "git_head": _git_head(),
        "privacy": {
            "contains_chunk_text": False,
            "note": "The manifest records identifiers, versions and hashes only; source/chunk text is not copied.",
        },
        "capacity_gate": {
            "minimum_diversity_ratio": MIN_DIVERSITY_RATIO,
            "target_queries_per_family": TARGET_QUERY_QUOTA,
            "passed": True,
            "families": summaries,
        },
        "corpus": corpus_payload["families"],
    }

    output = ROOT / "results" / f"benchmark_v2_frozen_corpus_{snapshot[:12]}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    total_datasets = sum(item["dataset_count"] for item in summaries.values())
    total_chunks = sum(item["chunk_count"] for item in summaries.values())

    print(f"CATALOG_SNAPSHOT={snapshot}")
    print(f"PROTOCOL_SHA256={protocol_sha256}")
    print(f"CORPUS_FINGERPRINT_SHA256={corpus_fingerprint}")
    print(f"FROZEN_DATASETS={total_datasets}")
    print(f"FROZEN_CHUNKS={total_chunks}")
    for family in FAMILIES:
        summary = summaries[family]
        print(
            f"FAMILY {family} datasets={summary['dataset_count']} "
            f"chunks={summary['chunk_count']} diversity={summary['diversity_units']} "
            f"ratio={summary['ratio_to_query_quota']:.3f}"
        )
    print(f"FROZEN_CORPUS_MANIFEST={output}")
    print("BENCHMARK_V2_CORPUS_FROZEN")


if __name__ == "__main__":
    main()
