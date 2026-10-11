from __future__ import annotations

from typing import Any

import httpx


class SensorHubError(RuntimeError):
    """Base error for Sensor Hub integration failures."""


class SensorHubConfigurationError(SensorHubError):
    """Raised when required Sensor Hub configuration is missing."""


class SensorHubAuthenticationError(SensorHubError):
    """Raised when Sensor Hub rejects authentication."""


class SensorHubUpstreamError(SensorHubError):
    """Raised when Sensor Hub returns an unexpected response."""


class SensorHubClient:
    """Small asynchronous client for the PiPi Sensor Hub REST API."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str | None,
        password: str | None,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.username = username
        self.password = password
        self._access_token: str | None = None
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_seconds,
            transport=transport,
        )

    async def __aenter__(self) -> "SensorHubClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def authenticate(self, *, force: bool = False) -> str:
        if self._access_token and not force:
            return self._access_token

        if not self.username or not self.password:
            raise SensorHubConfigurationError(
                "Sensor Hub username and password are required."
            )

        try:
            response = await self._client.post(
                "auth/tokens",
                json={"username": self.username, "password": self.password},
            )
        except httpx.HTTPError as exc:
            raise SensorHubUpstreamError(
                f"Could not reach Sensor Hub authentication endpoint: {exc}"
            ) from exc

        if response.status_code == 401:
            raise SensorHubAuthenticationError(
                "Sensor Hub rejected the configured username or password."
            )

        if response.is_error:
            raise SensorHubUpstreamError(
                f"Sensor Hub authentication returned HTTP {response.status_code}."
            )

        try:
            payload = response.json()
            token = payload["data"]["access_token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise SensorHubUpstreamError(
                "Sensor Hub authentication response did not contain data.access_token."
            ) from exc

        if not isinstance(token, str) or not token:
            raise SensorHubUpstreamError(
                "Sensor Hub authentication returned an empty access token."
            )

        self._access_token = token
        return token

    async def get_page(
        self,
        resource: str,
        *,
        page: int = 1,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = await self.authenticate()
        query = dict(params or {})
        query["page"] = page

        response = await self._get_with_token(resource, query, token)
        if response.status_code == 401:
            token = await self.authenticate(force=True)
            response = await self._get_with_token(resource, query, token)

        if response.is_error:
            raise SensorHubUpstreamError(
                f"Sensor Hub {resource} returned HTTP {response.status_code}."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SensorHubUpstreamError(
                f"Sensor Hub {resource} did not return valid JSON."
            ) from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise SensorHubUpstreamError(
                f"Sensor Hub {resource} response did not contain a data array."
            )

        return payload

    async def get_all(
        self,
        resource: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1

        while True:
            payload = await self.get_page(resource, page=page, params=params)
            items.extend(payload["data"])

            raw_total_pages = payload.get("total_pages", 1)
            try:
                total_pages = max(1, int(raw_total_pages))
            except (TypeError, ValueError) as exc:
                raise SensorHubUpstreamError(
                    f"Sensor Hub {resource} returned an invalid total_pages value."
                ) from exc

            if page >= total_pages:
                break
            page += 1

        return items

    async def list_locations(self) -> list[dict[str, Any]]:
        return await self.get_all("locations")

    async def list_sources(self) -> list[dict[str, Any]]:
        return await self.get_all("sources")

    async def list_deployments(self) -> list[dict[str, Any]]:
        return await self.get_all("deployments")

    async def list_properties(self) -> list[dict[str, Any]]:
        return await self.get_all("properties")

    async def list_deployment_properties(self) -> list[dict[str, Any]]:
        return await self.get_all("deployment-properties")

    async def _get_with_token(
        self,
        resource: str,
        params: dict[str, Any],
        token: str,
    ) -> httpx.Response:
        try:
            return await self._client.get(
                resource.lstrip("/"),
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            raise SensorHubUpstreamError(
                f"Could not reach Sensor Hub {resource}: {exc}"
            ) from exc
