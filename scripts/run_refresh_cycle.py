from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store, sync_catalog
from app.clients.sensor_hub import SensorHubClient
from app.config import get_settings
from app.harvest.history import HarvestHistoryStore
from app.resources.service import refresh_enabled_resources


def _client(settings):
    return SensorHubClient(
        base_url=settings.sensor_hub_base_url,
        username=settings.sensor_hub_username,
        password=settings.sensor_hub_password,
        timeout_seconds=settings.sensor_hub_timeout_seconds,
    )


async def run_cycle() -> int:
    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        print("REFRESH_CYCLE_FAILED: persistent catalog store is disabled")
        return 2

    history = HarvestHistoryStore(store)
    exit_code = 0

    provider_run_id = history.start("provider-sync", trigger="scheduled")
    try:
        async with _client(settings) as client:
            provider_stats = await sync_catalog(client, settings)
        provider_status = "partial" if int(provider_stats.get("provider_errors", 0)) else "ok"
        history.finish(provider_run_id, status=provider_status, summary=provider_stats)
        print("PROVIDER_SYNC", json.dumps(provider_stats, ensure_ascii=False, default=str))
        if provider_status != "ok":
            exit_code = 1
    except Exception as exc:
        history.finish(provider_run_id, status="error", error=str(exc))
        print(f"PROVIDER_SYNC_FAILED: {exc}")
        exit_code = 1

    resource_run_id = history.start("resource-refresh", trigger="scheduled")
    try:
        resource_stats = await refresh_enabled_resources(store, settings)
        resource_status = "partial" if int(resource_stats.get("errors", 0)) else "ok"
        history.finish(resource_run_id, status=resource_status, summary=resource_stats)
        print("RESOURCE_REFRESH", json.dumps(resource_stats, ensure_ascii=False, default=str))
        if resource_status != "ok":
            exit_code = 1
    except Exception as exc:
        history.finish(resource_run_id, status="error", error=str(exc))
        print(f"RESOURCE_REFRESH_FAILED: {exc}")
        exit_code = 1

    return exit_code


def main() -> int:
    return asyncio.run(run_cycle())


if __name__ == "__main__":
    raise SystemExit(main())
