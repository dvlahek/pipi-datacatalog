from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.metadata_index import index_catalog_metadata_dataset, metadata_index_family
from app.rag.profiles import catalog_snapshot_hash


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Index metadata-first PiPi datasets into RAG without downloading payload data. "
            "By default this covers Sensor Hub and harvested open-data catalog datasets."
        )
    )
    parser.add_argument(
        "--family",
        action="append",
        choices=["structured-data", "open-data-catalogs"],
        default=None,
        help="Optional family filter; may be supplied more than once.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of datasets to index after filtering; 0 means all.",
    )
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required. Enable CATALOG_STORE_ENABLED.")

    requested = set(args.family or ["structured-data", "open-data-catalogs"])
    candidates = [
        dataset
        for dataset in store.list_datasets()
        if metadata_index_family(dataset) in requested
    ]
    candidates.sort(key=lambda dataset: dataset.identifier)
    if args.limit > 0:
        candidates = candidates[: args.limit]

    print("PiPi metadata-first RAG indexing")
    print(f"CATALOG_SNAPSHOT={catalog_snapshot_hash(store)}")
    print("FAMILIES=" + ",".join(sorted(requested)))
    print(f"CANDIDATES={len(candidates)}")

    counts: Counter[str] = Counter()
    chunks = 0
    failures: list[tuple[str, str]] = []
    for dataset in candidates:
        family = metadata_index_family(dataset)
        try:
            result = index_catalog_metadata_dataset(store, dataset, settings)
        except Exception as exc:
            failures.append((dataset.identifier, str(exc)))
            continue
        counts[str(family)] += 1
        chunks += int(result.get("chunk_count") or 0)

    for family in sorted(counts):
        print(f"INDEXED {family} datasets={counts[family]}")
    print(f"TOTAL_INDEXED={sum(counts.values())}")
    print(f"TOTAL_CHUNKS={chunks}")
    print(f"FAILED={len(failures)}")
    for identifier, error in failures[:20]:
        print(f"ERROR {identifier}: {error}")
    if len(failures) > 20:
        print(f"ERRORS_TRUNCATED={len(failures) - 20}")

    if failures:
        raise SystemExit("METADATA_RAG_INDEX_PARTIAL_FAILURE")
    print("METADATA_RAG_INDEX_OK")


if __name__ == "__main__":
    main()
