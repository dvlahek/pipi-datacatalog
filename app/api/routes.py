from fastapi import APIRouter, HTTPException

from app.clients.sensor_hub import (
    SensorHubAuthenticationError,
    SensorHubClient,
    SensorHubConfigurationError,
    SensorHubError,
)
from app.config import get_settings
from app.harvesters.sensor_hub import SensorHubHarvester

router = APIRouter()


def _client() -> SensorHubClient:
    settings = get_settings()
    return SensorHubClient(
        base_url=settings.sensor_hub_base_url,
        username=settings.sensor_hub_username,
        password=settings.sensor_hub_password,
        timeout_seconds=settings.sensor_hub_timeout_seconds,
    )


def _raise_http(exc: SensorHubError) -> None:
    if isinstance(exc, SensorHubConfigurationError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, SensorHubAuthenticationError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name}


@router.get("/api/v1/providers/sensor-hub/status")
async def sensor_hub_status() -> dict[str, object]:
    settings = get_settings()
    return {
        "provider": "sensor-hub",
        "base_url": settings.sensor_hub_base_url,
        "configured": settings.sensor_hub_configured,
    }


@router.get("/api/v1/providers/sensor-hub/sources")
async def sensor_hub_sources() -> dict[str, object]:
    try:
        async with _client() as client:
            sources = await client.list_sources()
        return {"provider": "sensor-hub", "count": len(sources), "data": sources}
    except SensorHubError as exc:
        _raise_http(exc)


@router.post("/api/v1/harvest/sensor-hub/preview")
async def sensor_hub_harvest_preview() -> dict[str, object]:
    try:
        async with _client() as client:
            harvester = SensorHubHarvester(client)
            return await harvester.preview()
    except SensorHubError as exc:
        _raise_http(exc)
