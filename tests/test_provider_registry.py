import asyncio

from app.models.catalog import CanonicalDataset
from app.providers.registry import discover_from_providers


class GoodProvider:
    name = "good"

    async def datasets(self) -> list[CanonicalDataset]:
        return [
            CanonicalDataset(
                catalog_id="test:good:1",
                identifier="urn:pipi:dataset:test:good:1",
                title="Good dataset",
                description="Healthy provider dataset",
                publisher="PiPi",
                license="test",
                source_system="good",
            )
        ]


class FailingProvider:
    name = "broken"

    async def datasets(self) -> list[CanonicalDataset]:
        raise RuntimeError("provider unavailable")


def test_provider_failure_does_not_block_healthy_provider() -> None:
    datasets, statuses = asyncio.run(
        discover_from_providers([FailingProvider(), GoodProvider()])
    )

    assert [dataset.catalog_id for dataset in datasets] == ["test:good:1"]
    assert [status.name for status in statuses] == ["broken", "good"]
    assert statuses[0].status == "error"
    assert statuses[0].dataset_count == 0
    assert "provider unavailable" in (statuses[0].error or "")
    assert statuses[1].status == "ok"
    assert statuses[1].dataset_count == 1
    assert statuses[1].error is None
