from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.providers.open_data_catalog import OpenDataCatalogProvider
from app.rag.profiles import catalog_snapshot_hash


async def _run(config_path: str | None) -> int:
    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required. Enable CATALOG_STORE_ENABLED.")

    provider = OpenDataCatalogProvider(
        config_path or settings.open_data_catalogs_config,
        default_timeout_seconds=settings.open_data_catalogs_timeout_seconds,
        allowed_ports=settings.allowed_resource_ports,
    )

    sources = provider.sources()
    if not sources:
        raise SystemExit("No enabled open-data catalogs are configured.")

    print("PiPi open-data catalog sync")
    print("Configured sources:")
    for source in sources:
        print(
            f"  {source.id}: type={source.type} max_datasets={source.max_datasets} url={source.url}"
        )
    print()

    datasets = await provider.datasets()
    counts = Counter(dataset.source_system for dataset in datasets)
    stats = store.upsert_datasets(datasets)
    snapshot = catalog_snapshot_hash(store)

    print(f"DISCOVERED={stats['discovered']}")
    print(f"INSERTED={stats['inserted']}")
    print(f"UPDATED={stats['updated']}")
    print(f"UNCHANGED={stats['unchanged']}")
    print(f"VERSIONS_CREATED={stats['versions_created']}")
    print(f"STORED_TOTAL={store.count_datasets()}")
    for source_system, count in sorted(counts.items()):
        print(f"SOURCE {source_system} datasets={count}")
    print(f"CATALOG_SNAPSHOT={snapshot}")
    print("OPEN_DATA_SYNC_OK")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Harvest configured CKAN/DCAT metadata into the versioned PiPi Data Space."
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Optional config path; defaults to OPEN_DATA_CATALOGS_CONFIG.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.config)))


if __name__ == "__main__":
    main()
