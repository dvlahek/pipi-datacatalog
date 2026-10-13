from __future__ import annotations

import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.profiles import catalog_snapshot_hash
from app.rag.store import RagStore


TARGETS = {
    "structured-data": 80,
    "software-documentation": 80,
    "institutional-documents": 80,
}
MIN_DIVERSITY_RATIO = 0.40


def source_family(dataset_identifier: str) -> str | None:
    value = dataset_identifier.casefold()
    if value.startswith("urn:pipi:dataset:csv:") or ":sensor-hub:" in value:
        return "structured-data"
    if value == "urn:pipi:dataset:resource:2":
        return "software-documentation"
    if value.startswith("urn:pipi:dataset:foi-document:"):
        return "institutional-documents"
    return None


def _median(values: list[int]) -> float:
    return statistics.median(values) if values else 0.0


def main() -> None:
    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    rag = RagStore(store)
    snapshot = catalog_snapshot_hash(store)
    statuses = rag.list_index_statuses()
    disabled_datasets = {
        str(resource.get("dataset_identifier") or "")
        for resource in store.list_resources()
        if not bool(resource.get("enabled")) and resource.get("dataset_identifier")
    }

    datasets_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unclassified: list[str] = []

    for status in statuses:
        identifier = str(status.get("dataset_identifier") or "")
        if status.get("status") != "indexed" or identifier in disabled_datasets:
            continue
        family = source_family(identifier)
        if family is None:
            unclassified.append(identifier)
            continue
        datasets_by_family[family].append(status)

    print(f"CATALOG_SNAPSHOT={snapshot}")
    print("Benchmark V2 corpus-capacity audit")
    print(f"MIN_DIVERSITY_RATIO={MIN_DIVERSITY_RATIO:.2f}")
    print()

    overall_pass = True
    for family in TARGETS:
        statuses_for_family = datasets_by_family.get(family, [])
        chunk_counts: list[int] = []
        file_paths: set[str] = set()
        dataset_rows: list[tuple[str, int]] = []

        for status in statuses_for_family:
            identifier = str(status["dataset_identifier"])
            chunks = rag.list_chunks(identifier, limit=100000)
            count = len(chunks)
            chunk_counts.append(count)
            dataset_rows.append((identifier, count))
            for chunk in chunks:
                metadata = chunk.get("metadata")
                if isinstance(metadata, dict):
                    path = str(metadata.get("file_path") or "").strip()
                    if path:
                        file_paths.add(path)

        total_chunks = sum(chunk_counts)
        nonempty_datasets = sum(1 for count in chunk_counts if count > 0)
        max_chunks = max(chunk_counts) if chunk_counts else 0
        min_chunks = min(chunk_counts) if chunk_counts else 0

        print(f"[{family}]")
        print(f"  target_queries={TARGETS[family]}")
        print(f"  indexed_datasets={len(statuses_for_family)}")
        print(f"  nonempty_datasets={nonempty_datasets}")
        print(f"  total_chunks={total_chunks}")
        print(f"  unique_file_paths={len(file_paths)}")
        print(
            "  chunks_per_dataset="
            f"min:{min_chunks} median:{_median(chunk_counts):.1f} max:{max_chunks}"
        )

        if dataset_rows:
            print("  largest_datasets:")
            for identifier, count in sorted(dataset_rows, key=lambda item: (-item[1], item[0]))[:5]:
                print(f"    {count:5d}  {identifier}")
        else:
            print("  largest_datasets: none")

        if family == "software-documentation":
            diversity_units = len(file_paths) if file_paths else total_chunks
            label = "unique files" if file_paths else "chunks"
        elif family == "institutional-documents":
            diversity_units = nonempty_datasets
            label = "documents"
        else:
            diversity_units = nonempty_datasets
            label = "datasets"

        ratio = diversity_units / TARGETS[family] if TARGETS[family] else 0.0
        print(f"  coarse_diversity_units={diversity_units} ({label}; ratio_to_query_quota={ratio:.2f})")
        if diversity_units == 0:
            flag = "FAIL_NO_EVIDENCE"
            overall_pass = False
        elif ratio < MIN_DIVERSITY_RATIO:
            flag = "FAIL_CAPACITY_EXPANSION_REQUIRED"
            overall_pass = False
        else:
            flag = "PASS_CAPACITY_GATE"
        print(f"  capacity_flag={flag}")
        print()

    if unclassified:
        counts = Counter(identifier.split(":")[3] if identifier.count(":") >= 3 else identifier for identifier in unclassified)
        print(f"UNCLASSIFIED_INDEXED_DATASETS={len(unclassified)}")
        print("  groups=" + ", ".join(f"{key}:{value}" for key, value in counts.most_common(10)))
    else:
        print("UNCLASSIFIED_INDEXED_DATASETS=0")

    print(f"DISABLED_DATASETS_EXCLUDED={len(disabled_datasets)}")
    print(f"CAPACITY_GATE={'PASS' if overall_pass else 'FAIL'}")
    print("AUDIT_NOTE=This is a pre-authoring capacity gate, not a benchmark result.")


if __name__ == "__main__":
    main()
