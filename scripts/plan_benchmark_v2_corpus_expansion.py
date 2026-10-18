from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.profiles import catalog_snapshot_hash
from app.rag.store import RagStore


def _hash_rank(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def _dataset_row(dataset: Any, rag: RagStore) -> dict[str, Any]:
    status = rag.index_status(dataset.identifier)
    return {
        "identifier": dataset.identifier,
        "title": dataset.title,
        "source_system": dataset.source_system,
        "dataset_type": dataset.dataset_type,
        "rag_status": status.get("status"),
        "catalog_version": status.get("catalog_version"),
        "indexed_version": status.get("indexed_version"),
        "selection_hash": _hash_rank(dataset.identifier),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan deterministic corpus expansion for PiPi Retrieval Benchmark V2 without inspecting retrieval results."
    )
    parser.add_argument("--foi-target", type=int, default=40)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    rag = RagStore(store)
    snapshot = catalog_snapshot_hash(store)
    datasets = store.list_datasets()

    sensor = [
        _dataset_row(dataset, rag)
        for dataset in datasets
        if dataset.source_system == "sensor-hub" or dataset.dataset_type == "sensor-observation"
    ]
    foi = [
        _dataset_row(dataset, rag)
        for dataset in datasets
        if dataset.source_system == "foi-documents"
        or str(dataset.identifier).startswith("urn:pipi:dataset:foi-document:")
    ]

    sensor.sort(key=lambda row: row["identifier"])
    foi.sort(key=lambda row: (row["selection_hash"], row["identifier"]))

    foi_indexed = [row for row in foi if row["rag_status"] == "indexed"]
    foi_not_indexed = [row for row in foi if row["rag_status"] != "indexed"]
    foi_needed = max(0, args.foi_target - len(foi_indexed))
    foi_attempt_order = foi_not_indexed[: max(foi_needed, min(len(foi_not_indexed), args.foi_target * 2))]

    manifest = {
        "artifact": "pipi-benchmark-v2-corpus-expansion-plan",
        "catalog_snapshot_hash": snapshot,
        "sensor_hub": {
            "cataloged": len(sensor),
            "indexed": sum(1 for row in sensor if row["rag_status"] == "indexed"),
            "metadata_index_required": [row for row in sensor if row["rag_status"] != "indexed"],
        },
        "foi_documents": {
            "cataloged": len(foi),
            "indexed": len(foi_indexed),
            "target_indexed": args.foi_target,
            "additional_successes_needed": foi_needed,
            "selection_method": "ascending SHA-256(dataset_identifier), independent of retrieval output",
            "already_indexed": foi_indexed,
            "deterministic_attempt_order": foi_attempt_order,
        },
        "rules": [
            "Sensor Hub uses metadata-only RAG evidence for metadata-first datasets; raw observation streams are not text-embedded.",
            "FOI candidate selection must not use retrieval-profile outcomes.",
            "If an FOI candidate fails to resolve or index, record the failure and continue in deterministic hash order.",
        ],
    }

    output = args.output
    if output is None:
        output = ROOT / "results" / f"benchmark_v2_corpus_expansion_plan_{snapshot[:12]}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    print(f"CATALOG_SNAPSHOT={snapshot}")
    print(f"SENSOR_HUB_CATALOGED={len(sensor)}")
    print(f"SENSOR_HUB_INDEXED={sum(1 for row in sensor if row['rag_status'] == 'indexed')}")
    print(f"SENSOR_HUB_METADATA_INDEX_REQUIRED={sum(1 for row in sensor if row['rag_status'] != 'indexed')}")
    print(f"FOI_CATALOGED={len(foi)}")
    print(f"FOI_INDEXED={len(foi_indexed)}")
    print(f"FOI_TARGET={args.foi_target}")
    print(f"FOI_ADDITIONAL_SUCCESSES_NEEDED={foi_needed}")
    print(f"FOI_DETERMINISTIC_CANDIDATES_SHOWN={len(foi_attempt_order)}")
    print(f"EXPANSION_PLAN_ARTIFACT={output}")
    print()
    print("FIRST_FOI_CANDIDATES")
    for row in foi_attempt_order[:10]:
        print(f"  {row['selection_hash'][:12]}  {row['identifier']}  ::  {row['title']}")
    print()
    print("NEXT_STEP=Implement metadata indexing for Sensor Hub, then deterministically index FOI candidates until the target succeeds.")


if __name__ == "__main__":
    main()
