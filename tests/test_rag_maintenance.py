from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.rag import maintenance


class FakeStore:
    def list_resources(self):
        return [
            {
                "id": 1,
                "enabled": False,
                "dataset_identifier": "urn:test:stale-disabled",
            }
        ]


class FakeRagStore:
    def __init__(self, _store):
        pass

    def list_index_statuses(self):
        return [
            {
                "dataset_identifier": "urn:test:current",
                "status": "indexed",
                "catalog_version": 1,
                "indexed_version": 1,
            },
            {
                "dataset_identifier": "urn:test:new",
                "status": "not_indexed",
                "catalog_version": 1,
                "indexed_version": None,
            },
            {
                "dataset_identifier": "urn:test:stale-a",
                "status": "stale",
                "catalog_version": 2,
                "indexed_version": 1,
            },
            {
                "dataset_identifier": "urn:test:stale-b",
                "status": "stale",
                "catalog_version": 3,
                "indexed_version": 2,
            },
            {
                "dataset_identifier": "urn:test:stale-disabled",
                "status": "stale",
                "catalog_version": 2,
                "indexed_version": 1,
            },
        ]


@pytest.mark.asyncio
async def test_reindex_stale_only_respects_disabled_resources_and_limit(monkeypatch):
    calls: list[str] = []

    async def fake_index(_store, dataset_identifier, _settings):
        calls.append(dataset_identifier)
        return {"dataset_version": 2, "chunk_count": 4}

    monkeypatch.setattr(maintenance, "RagStore", FakeRagStore)
    monkeypatch.setattr(maintenance, "index_catalog_dataset", fake_index)

    settings = SimpleNamespace(rag_auto_reindex_enabled=True, rag_auto_reindex_limit=1)
    result = await maintenance.reindex_stale_datasets(FakeStore(), settings)

    assert calls == ["urn:test:stale-a"]
    assert result["candidates"] == 3
    assert result["attempted"] == 1
    assert result["reindexed"] == 1
    assert result["skipped_disabled"] == 1
    assert result["deferred"] == 1
    assert result["errors"] == 0


@pytest.mark.asyncio
async def test_reindex_stale_can_be_disabled(monkeypatch):
    class ShouldNotConstruct:
        def __init__(self, _store):
            raise AssertionError("RagStore should not be constructed when maintenance is disabled")

    monkeypatch.setattr(maintenance, "RagStore", ShouldNotConstruct)
    settings = SimpleNamespace(rag_auto_reindex_enabled=False, rag_auto_reindex_limit=10)

    result = await maintenance.reindex_stale_datasets(FakeStore(), settings)

    assert result["status"] == "disabled"
    assert result["attempted"] == 0
