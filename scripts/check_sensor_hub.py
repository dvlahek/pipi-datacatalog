import asyncio
import sys
from pathlib import Path

# Allow this script to be executed directly from the repository root with
# `python scripts/check_sensor_hub.py` on Windows, Linux, and macOS.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.clients.sensor_hub import SensorHubClient
from app.config import get_settings


async def check() -> None:
    settings = get_settings()
    async with SensorHubClient(
        base_url=settings.sensor_hub_base_url,
        username=settings.sensor_hub_username,
        password=settings.sensor_hub_password,
        timeout_seconds=settings.sensor_hub_timeout_seconds,
    ) as client:
        sources = await client.list_sources()
        print(f"Sensor Hub reachable: {len(sources)} source(s) returned")


if __name__ == "__main__":
    asyncio.run(check())
