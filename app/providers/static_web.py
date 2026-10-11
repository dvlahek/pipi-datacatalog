from __future__ import annotations

from app.models.catalog import (
    CatalogDistribution,
    CatalogLocation,
    CatalogSource,
    CanonicalDataset,
)


class StaticWebProvider:
    """Small provider for manually registered public web resources."""

    name = "static-web"

    async def datasets(self) -> list[CanonicalDataset]:
        return [self._varazdin_webcam()]

    @staticmethod
    def _varazdin_webcam() -> CanonicalDataset:
        identifier = "urn:pipi:dataset:webcam:whatsupcams:hr_varazdin1"
        stream_url = "https://cdn-006.whatsupcams.com/hls/hr_varazdin1.m3u8"
        snapshot_url = "https://cdn.whatsupcams.com/snapshot/hr_varazdin1.jpg"
        discovery_url = (
            "https://services.whatsupcams.com/streams/hr_varazdin1?jsonp=true"
        )
        service_id = "urn:pipi:dataservice:whatsupcams:hr_varazdin1"

        return CanonicalDataset(
            catalog_id="webcam:whatsupcams:hr_varazdin1",
            identifier=identifier,
            title="WhatsUpCams Varaždin live webcam",
            description=(
                "Public live webcam stream for Varaždin, registered in the PiPi "
                "catalog as an external video dataset. The catalog stores metadata "
                "and access links only and does not copy the video stream."
            ),
            publisher="WhatsUpCams",
            license="unknown",
            dataset_type="live-video-stream",
            source_system="whatsupcams",
            external_id="hr_varazdin1",
            keywords=[
                "Varaždin",
                "webcam",
                "camera",
                "live video",
                "HLS",
                "video stream",
            ],
            source=CatalogSource(
                id="hr_varazdin1",
                code="hr_varazdin1",
                name="WhatsUpCams Varaždin webcam",
                provider="WhatsUpCams",
            ),
            location=CatalogLocation(
                id="varazdin",
                name="Varaždin",
            ),
            distributions=[
                CatalogDistribution(
                    identifier=f"{identifier}:distribution:hls",
                    title="Live HLS video stream",
                    access_url=stream_url,
                    media_type="application/vnd.apple.mpegurl",
                    source_media_type="application/x-mpegURL",
                    format="HLS",
                    access_service_identifier=service_id,
                    endpoint_url=stream_url,
                    endpoint_description=discovery_url,
                    kind="live-stream",
                    is_live=True,
                ),
                CatalogDistribution(
                    identifier=f"{identifier}:distribution:snapshot",
                    title="Current camera snapshot",
                    access_url=snapshot_url,
                    media_type="image/jpeg",
                    format="JPEG",
                    kind="snapshot",
                    is_live=False,
                ),
            ],
            extensions={
                "webcam": {
                    "stream_discovery_url": discovery_url,
                    "snapshot_url": snapshot_url,
                }
            },
        )
