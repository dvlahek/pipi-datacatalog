from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.profiles import catalog_snapshot_hash
from app.rag.store import RagStore


EXPECTED_SNAPSHOT = "068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419"
PREVIEW_CHARS = 420


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_family(dataset: Any) -> str | None:
    identifier = str(dataset.identifier).casefold()
    source_system = str(dataset.source_system or "").casefold()
    dataset_type = str(dataset.dataset_type or "").casefold()

    if source_system == "sensor-hub" or identifier.startswith("urn:pipi:dataset:csv:"):
        return "structured-data"
    if source_system == "github" or dataset_type == "software-repository":
        return "software-documentation"
    if source_system == "foi-documents" or identifier.startswith("urn:pipi:dataset:foi-document:"):
        return "institutional-documents"
    if source_system.startswith("open-data:") or identifier.startswith("urn:pipi:dataset:open-data:"):
        return "open-data-catalogs"
    return None


def _preview(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= PREVIEW_CHARS:
        return compact
    return compact[: PREVIEW_CHARS - 1].rstrip() + "…"


def _slug(value: str) -> str:
    return {
        "structured-data": "structured",
        "software-documentation": "software",
        "institutional-documents": "institutional",
        "open-data-catalogs": "opendata",
        "exact-lookup": "exact",
        "semantic-paraphrase": "semantic",
        "topic-discovery": "topic",
        "entity-document-lookup": "entity",
        "relation-comparison": "relation",
        "constraint-filtered-lookup": "constraint",
        "development": "dev",
        "confirmation": "conf",
    }.get(value, value.replace("-", "_"))


def _make_slots(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    design = protocol["source_family_by_query_type"]
    query_types = list(design["query_type_order"])
    source_families = list(protocol["source_families"].keys())
    slots: list[dict[str, Any]] = []

    for split in ("development", "confirmation"):
        matrix = design[split]
        for family in source_families:
            counts = matrix[family]
            for query_type, count in zip(query_types, counts):
                for position in range(1, int(count) + 1):
                    if split == "development":
                        language_relation = "cross-language" if position == 1 else "same-language"
                        double_annotation = False
                    else:
                        language_relation = "cross-language" if position <= 2 else "same-language"
                        # Exactly two confirmation queries per cell: one cross-language
                        # and one same-language case, as preregistered by Amendment 1.
                        double_annotation = position in {1, 3}

                    case_id = (
                        f"v2-{_slug(split)}-{_slug(family)}-"
                        f"{_slug(query_type)}-{position:02d}"
                    )
                    slots.append(
                        {
                            "case_id": case_id,
                            "split": split,
                            "source_family": family,
                            "query_type": query_type,
                            "cell_position": position,
                            "language_relation": language_relation,
                            "double_annotation": double_annotation,
                            "information_need": None,
                            "query_text": None,
                            "query_language": None,
                            "target_evidence_language": None,
                            "target_dataset_identifiers": [],
                            "target_file_paths": [],
                            "target_chunk_hints": [],
                            "authoring_status": "empty",
                            "notes": None,
                        }
                    )

    return slots


def _inventory(store: Any, rag: RagStore) -> dict[str, Any]:
    datasets = {dataset.identifier: dataset for dataset in store.list_datasets()}
    disabled = {
        str(resource.get("dataset_identifier") or "")
        for resource in store.list_resources()
        if not bool(resource.get("enabled")) and resource.get("dataset_identifier")
    }

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for status in sorted(
        rag.list_index_statuses(),
        key=lambda item: str(item.get("dataset_identifier") or ""),
    ):
        identifier = str(status.get("dataset_identifier") or "")
        if status.get("status") != "indexed" or identifier in disabled:
            continue
        dataset = datasets.get(identifier)
        if dataset is None:
            continue
        family = _source_family(dataset)
        if family is None:
            continue

        version = int(status.get("indexed_version") or 0)
        chunks = rag.list_chunks(identifier, dataset_version=version, limit=100000)
        document = dict(status.get("document") or {})

        row: dict[str, Any] = {
            "dataset_identifier": identifier,
            "dataset_version": version,
            "title": dataset.title,
            "description": dataset.description,
            "publisher": dataset.publisher,
            "dataset_type": dataset.dataset_type,
            "source_system": dataset.source_system,
            "source_url": document.get("source_url"),
            "chunk_count": len(chunks),
        }

        if family == "software-documentation":
            file_chunks: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for chunk in chunks:
                metadata = dict(chunk.get("metadata") or {})
                path = str(metadata.get("file_path") or "").strip()
                if not path:
                    path = "<unknown-file>"
                file_chunks[path].append(chunk)
            files: list[dict[str, Any]] = []
            for path in sorted(file_chunks):
                current = sorted(file_chunks[path], key=lambda item: int(item["chunk_index"]))
                samples = [
                    {
                        "chunk_index": int(item["chunk_index"]),
                        "preview": _preview(str(item.get("text") or "")),
                    }
                    for item in current[:2]
                ]
                files.append(
                    {
                        "file_path": path,
                        "chunk_count": len(current),
                        "sample_chunks": samples,
                    }
                )
            row["files"] = files
        else:
            row["sample_chunks"] = [
                {
                    "chunk_index": int(item["chunk_index"]),
                    "preview": _preview(str(item.get("text") or "")),
                }
                for item in sorted(chunks, key=lambda item: int(item["chunk_index"]))[:3]
            ]

        by_family[family].append(row)

    return {family: by_family.get(family, []) for family in (
        "structured-data",
        "software-documentation",
        "institutional-documents",
        "open-data-catalogs",
    )}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create the preregistered Benchmark V2 query-authoring scaffold and a local "
            "corpus inventory without executing retrieval."
        )
    )
    parser.add_argument("--expected-snapshot", default=EXPECTED_SNAPSHOT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    snapshot = catalog_snapshot_hash(store)
    if snapshot != args.expected_snapshot:
        raise SystemExit(
            "QUERY_AUTHORING_REFUSED_SNAPSHOT_MISMATCH\n"
            f"expected={args.expected_snapshot}\nactual={snapshot}"
        )

    protocol_path = ROOT / "config" / "rag_benchmark_v2_protocol.json"
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    protocol_sha256 = _sha256_bytes(protocol_bytes)

    frozen_manifest_path = ROOT / "results" / f"benchmark_v2_frozen_corpus_{snapshot[:12]}.json"
    if not frozen_manifest_path.is_file():
        raise SystemExit(f"Frozen corpus manifest not found: {frozen_manifest_path}")
    frozen_manifest = json.loads(frozen_manifest_path.read_text(encoding="utf-8"))
    if frozen_manifest.get("catalog_snapshot_hash") != snapshot:
        raise SystemExit("Frozen corpus manifest snapshot does not match the current catalog snapshot.")
    if (frozen_manifest.get("protocol") or {}).get("sha256") != protocol_sha256:
        raise SystemExit("Frozen corpus manifest protocol hash does not match the current protocol file.")

    slots = _make_slots(protocol)
    split_counts = defaultdict(int)
    language_counts = defaultdict(int)
    double_count = 0
    for slot in slots:
        split_counts[slot["split"]] += 1
        language_counts[slot["language_relation"]] += 1
        double_count += int(bool(slot["double_annotation"]))

    expected = protocol["splits"]
    if len(slots) != int(expected["total"]):
        raise SystemExit(f"Slot count mismatch: generated {len(slots)} expected {expected['total']}")
    if split_counts["development"] != int(expected["development"]):
        raise SystemExit("Development slot count does not match protocol.")
    if split_counts["confirmation"] != int(expected["confirmation"]):
        raise SystemExit("Confirmation slot count does not match protocol.")
    if language_counts["cross-language"] != int(protocol["language_relation"]["total"]["cross-language"]):
        raise SystemExit("Cross-language slot count does not match protocol.")
    if double_count != int(protocol["relevance"]["annotation"]["double_annotation_minimum_confirmation_queries"]):
        raise SystemExit("Double-annotation slot count does not match protocol.")

    rag = RagStore(store)
    inventory = _inventory(store, rag)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    template_path = args.output_dir / f"benchmark_v2_query_authoring_template_{snapshot[:12]}.json"
    inventory_path = args.output_dir / f"benchmark_v2_authoring_inventory_{snapshot[:12]}.json"

    template = {
        "artifact": "pipi-benchmark-v2-query-authoring-template",
        "schema_version": 1,
        "catalog_snapshot_hash": snapshot,
        "corpus_fingerprint_sha256": frozen_manifest.get("corpus_fingerprint_sha256"),
        "protocol_sha256": protocol_sha256,
        "rules": [
            "This scaffold was created without running lexical, vector or hybrid retrieval.",
            "Author information needs from frozen corpus evidence only; do not inspect retrieval output while wording confirmation cases.",
            "Development cases are authored and validated first; confirmation wording is frozen before confirmatory retrieval is viewed.",
            "Pilot P1 queries must not be copied into the V2 confirmation split.",
        ],
        "cases": slots,
    }
    template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    inventory_payload = {
        "artifact": "pipi-benchmark-v2-local-authoring-inventory",
        "schema_version": 1,
        "catalog_snapshot_hash": snapshot,
        "corpus_fingerprint_sha256": frozen_manifest.get("corpus_fingerprint_sha256"),
        "protocol_sha256": protocol_sha256,
        "publication_safe": False,
        "note": (
            "Local authoring aid only. It contains short source-text previews so information needs can be "
            "written from evidence without looking at retrieval rankings. Do not commit this artifact."
        ),
        "families": inventory,
    }
    inventory_path.write_text(
        json.dumps(inventory_payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    family_counts = {family: len(rows) for family, rows in inventory.items()}
    print(f"CATALOG_SNAPSHOT={snapshot}")
    print(f"CORPUS_FINGERPRINT_SHA256={frozen_manifest.get('corpus_fingerprint_sha256')}")
    print(f"PROTOCOL_SHA256={protocol_sha256}")
    print(
        f"SLOTS={len(slots)} development={split_counts['development']} "
        f"confirmation={split_counts['confirmation']}"
    )
    print(
        f"LANGUAGE cross-language={language_counts['cross-language']} "
        f"same-language={language_counts['same-language']}"
    )
    print(f"DOUBLE_ANNOTATION_CONFIRMATION={double_count}")
    for family in (
        "structured-data",
        "software-documentation",
        "institutional-documents",
        "open-data-catalogs",
    ):
        print(f"INVENTORY {family} datasets={family_counts.get(family, 0)}")
    print(f"AUTHORING_TEMPLATE={template_path}")
    print(f"AUTHORING_INVENTORY={inventory_path}")
    print("RETRIEVAL_EXECUTED=NO")
    print("BENCHMARK_V2_QUERY_AUTHORING_READY")


if __name__ == "__main__":
    main()
