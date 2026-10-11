import asyncio

import httpx

from app.clients.sensor_hub import SensorHubClient


def test_list_sources_authenticates_and_follows_pagination() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v1/auth/tokens":
            return httpx.Response(
                201,
                json={
                    "data": {
                        "access_token": "test-token",
                        "token_type": "Bearer",
                        "expires_at": "2026-10-12T00:00:00Z",
                    }
                },
            )

        if request.method == "GET" and request.url.path == "/api/v1/sources":
            assert request.headers["Authorization"] == "Bearer test-token"
            page = int(request.url.params["page"])
            if page == 1:
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": 1,
                                "type": "sensor",
                                "code": "sensor-1",
                                "name": "Sensor 1",
                            }
                        ],
                        "page": 1,
                        "total_pages": 2,
                        "results_page": 1,
                        "results_total": 2,
                    },
                )
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 2,
                            "type": "web_service",
                            "code": "service-1",
                            "name": "Service 1",
                        }
                    ],
                    "page": 2,
                    "total_pages": 2,
                    "results_page": 1,
                    "results_total": 2,
                },
            )

        return httpx.Response(404)

    async def run() -> list[dict[str, object]]:
        transport = httpx.MockTransport(handler)
        async with SensorHubClient(
            base_url="https://sensor.example/api/v1",
            username="test-user",
            password="test-password",
            transport=transport,
        ) as client:
            return await client.list_sources()

    sources = asyncio.run(run())

    assert [source["id"] for source in sources] == [1, 2]
