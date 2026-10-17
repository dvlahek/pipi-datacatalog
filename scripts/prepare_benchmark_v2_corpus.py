from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.profiles import catalog_snapshot_hash
from app.rag.service import RagIndexError, index_catalog_dataset, index_registered_resource
from app.rag.store import RagStore
from app.resources.github import parse_github_repository_url


def _selection_hash(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def _is_foi(dataset: Any) -> bool:
    return dataset.source_system == "foi-documents" or str(dataset.identifier).startswith(
        "urn:pipi:dataset:foi-document:"
    )


async def _run(*, foi_target: int, delay_seconds: float, output: Path | None) -> int:
    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    rag = RagStore(store)
    before_snapshot = catalog_snapshot_hash(store)
    datasets_by_id = {dataset.identifier: dataset for dataset in store.list_datasets()}

    print("PiPi Benchmark V2 corpus preparation")
    print(f"CATALOG_SNAPSHOT_BEFORE={before_snapshot}")
    print()

    software_attempts: list[dict[str, Any]] = []
    enabled_resources = [resource for resource in store.list_resources() if bool(resource.get("enabled"))]
    github_resources: list[dict[str, Any]] = []
    for resource in enabled_resources:
        dataset_identifier = str(resource.get("dataset_identifier") or "")
        dataset = datasets_by_id.get(dataset_identifier)
        source_url = str(resource.get("source_url") or "")
        if (dataset is not None and dataset.source_system == "github") or parse_github_repository_url(source_url):
            github_resources.append(resource)

    print(f"SOFTWARE_GITHUB_RESOURCES={len(github_resources)}")
    for resource in github_resources:
        resource_id = int(resource["id"])
        dataset_identifier = str(resource.get("dataset_identifier") or "")
        status_before = rag.index_status(dataset_identifier) if dataset_identifier else {"status": "not_indexed"}
        row: dict[str, Any] = {
            "resource_id": resource_id,
            "dataset_identifier_before": dataset_identifier or None,
            "status_before": status_before.get("status"),
        }
        if status_before.get("status") == "indexed":
            row["action"] = "kept"
            print(f"SOFTWARE_KEEP resource={resource_id} status=indexed")
        else:
            try:
                result = await index_registered_resource(store, resource_id, settings)
                final_identifier = str(result.get("dataset_identifier") or dataset_identifier)
                status_after = rag.index_status(final_identifier) if final_identifier else {"status": "unknown"}
                row.update(
                    {
                        "action": "reindexed",
                        "dataset_identifier_after": final_identifier or None,
                        "status_after": status_after.get("status"),
                        "chunk_count": result.get("chunk_count"),
                    }
                )
                print(
                    f"SOFTWARE_REINDEX resource={resource_id} status={status_after.get('status')} "
                    f"chunks={result.get('chunk_count')}"
                )
            except Exception as exc:
                row.update({"action": "failed", "error": str(exc)})
                print(f"SOFTWARE_FAIL resource={resource_id} error={exc}")
        software_attempts.append(row)

    print()
    datasets = [dataset for dataset in store.list_datasets() if _is_foi(dataset)]
    foi_rows: list[dict[str, Any]] = []
    for dataset in datasets:
        status = rag.index_status(dataset.identifier)
        foi_rows.append(
            {
                "identifier": dataset.identifier,
                "title": dataset.title,
                "status": status.get("status"),
                "selection_hash": _selection_hash(dataset.identifier),
            }
        )

    indexed_initial = [row for row in foi_rows if row["status"] == "indexed"]
    candidates = sorted(
        [row for row in foi_rows if row["status"] != "indexed"],
        key=lambda row: (row["selection_hash"], row["identifier"]),
    )
    print(f"FOI_CATALOGED={len(foi_rows)}")
    print(f"FOI_INDEXED_BEFORE={len(indexed_initial)}")
    print(f"FOI_TARGET={foi_target}")
    print(f"FOI_CANDIDATES={len(candidates)}")

    foi_attempts: list[dict[str, Any]] = []
    indexed_count = len(indexed_initial)
    for row in candidates:
        if indexed_count >= foi_target:
            break
        identifier = str(row["identifier"])
        attempt = {
            "identifier": identifier,
            "title": row["title"],
            "selection_hash": row["selection_hash"],
        }
        try:
            result = await index_catalog_dataset(store, identifier, settings)
            status_after = rag.index_status(identifier)
            success = status_after.get("status") == "indexed"
            attempt.update(
                {
                    "status": "indexed" if success else str(status_after.get("status")),
                    "chunk_count": result.get("chunk_count"),
                    "dataset_version": result.get("dataset_version"),
                }
            )
            if success:
                indexed_count += 1
            print(
                f"FOI_{'OK' if success else 'REVIEW'} {indexed_count:02d}/{foi_target} "
                f"{identifier} chunks={result.get('chunk_count')}"
            )
        except (RagIndexError, Exception) as exc:
            attempt.update({"status": "failed", "error": str(exc)})
            print(f"FOI_FAIL {identifier} error={exc}")
        foi_attempts.append(attempt)
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    final_foi_indexed = sum(
        1 for dataset in store.list_datasets() if _is_foi(dataset) and rag.index_status(dataset.identifier).get("status") == "indexed"
    )
    after_snapshot = catalog_snapshot_hash(store)

    manifest = {
        "artifact": "pipi-benchmark-v2-corpus-preparation",
        "catalog_snapshot_before": before_snapshot,
        "catalog_snapshot_after": after_snapshot,
        "software_attempts": software_attempts,
        "foi": {
            "target": foi_target,
            "indexed_before": len(indexed_initial),
            "indexed_after": final_foi_indexed,
            "selection_method": "ascending SHA-256(dataset_identifier), independent of retrieval output",
            "attempts": foi_attempts,
        },
    }
    if output is None:
        output = ROOT / "results" / f"benchmark_v2_corpus_preparation_{after_snapshot[:12]}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    software_ok = all(item.get("action") in {"kept", "reindexed"} and item.get("status_after", "indexed") == "indexed" for item in software_attempts)
    foi_ok = final_foi_indexed >= foi_target

    print()
    print(f"FOI_INDEXED_AFTER={final_foi_indexed}")
    print(f"CATALOG_SNAPSHOT_AFTER={after_snapshot}")
    print(f"PREPARATION_ARTIFACT={output}")
    print(f"SOFTWARE_READY={'YES' if software_ok and github_resources else 'NO'}")
    print(f"FOI_READY={'YES' if foi_ok else 'NO'}")
    print(f"BENCHMARK_V2_CORPUS_PREPARATION={'PASS' if software_ok and github_resources and foi_ok else 'PARTIAL'}")
    return 0 if software_ok and github_resources and foi_ok else 2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore software evidence and deterministically expand FOI evidence for Benchmark V2."
    )
    parser.add_argument("--foi-target", type=int, default=40)
    parser.add_argument("--delay-seconds", type=float, default=0.25)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                foi_target=max(1, int(args.foi_target)),
                delay_seconds=max(0.0, float(args.delay_seconds)),
                output=args.output,
            )
        )
    )


if __name__ == "__main__":
    main()
