from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.embeddings import backfill_current_embeddings, get_embedding_provider
from app.rag.profiles import catalog_snapshot_hash, get_retrieval_profile, settings_for_profile
from app.rag.store import RagStore


EXPECTED_CORPUS_CHUNKS = 3974
PROFILE_IDS = (
    "vector-e5-content-v1",
    "vector-e5-metadata-v1",
)


def _progress(label: str):
    last = {"value": -1}

    def report(done: int, total: int) -> None:
        if total <= 0:
            return
        pct = int((100 * done) / total)
        bucket = pct // 10
        if bucket != last["value"] or done == total:
            last["value"] = bucket
            print(f"{label}_PROGRESS={done}/{total} ({pct}%)", flush=True)

    return report


def main() -> None:
    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    rag = RagStore(store)
    snapshot_before = catalog_snapshot_hash(store)
    print("PiPi Benchmark V2 embedding preparation")
    print(f"CATALOG_SNAPSHOT_BEFORE={snapshot_before}")
    print(f"EXPECTED_CURRENT_CHUNKS={EXPECTED_CORPUS_CHUNKS}")

    results: list[dict[str, object]] = []

    for profile_id in PROFILE_IDS:
        profile = get_retrieval_profile(profile_id)
        profile_settings = settings_for_profile(settings, profile)
        provider = get_embedding_provider(profile_settings)
        status_before = rag.embedding_status(provider.name)

        print()
        print(f"PROFILE={profile_id}")
        print(f"PROFILE_HASH={profile.config_hash}")
        print(f"EMBEDDING_IDENTITY={provider.name}")
        print(
            "STATUS_BEFORE="
            f"embedded:{status_before['embedded_current_model']} "
            f"total:{status_before['total_current_chunks']} "
            f"missing:{status_before['missing']}"
        )

        if int(status_before["total_current_chunks"]) != EXPECTED_CORPUS_CHUNKS:
            raise SystemExit(
                f"Current chunk count changed before embedding {profile_id}: "
                f"expected {EXPECTED_CORPUS_CHUNKS}, got {status_before['total_current_chunks']}."
            )

        result = backfill_current_embeddings(
            store,
            profile_settings,
            limit=EXPECTED_CORPUS_CHUNKS,
            progress=_progress(profile_id.replace("-", "_").upper()),
        )
        status_after = rag.embedding_status(provider.name)
        print(
            "STATUS_AFTER="
            f"embedded:{status_after['embedded_current_model']} "
            f"total:{status_after['total_current_chunks']} "
            f"missing:{status_after['missing']} "
            f"complete:{status_after['complete']}"
        )

        results.append(
            {
                "profile_id": profile_id,
                "profile_hash": profile.config_hash,
                "embedding_identity": provider.name,
                "input_profile": profile.embedding_input_profile,
                "attempted": int(result["attempted"]),
                "embedded": int(result["embedded"]),
                "status_before": status_before,
                "status_after": status_after,
            }
        )

    snapshot_after = catalog_snapshot_hash(store)
    if snapshot_after != snapshot_before:
        raise SystemExit(
            "Catalog snapshot changed while embeddings were being prepared; "
            "do not use this run as a frozen benchmark state."
        )

    complete = all(
        bool(item["status_after"]["complete"])
        and int(item["status_after"]["total_current_chunks"]) == EXPECTED_CORPUS_CHUNKS
        and int(item["status_after"]["embedded_current_model"]) == EXPECTED_CORPUS_CHUNKS
        for item in results
    )

    artifact = {
        "artifact": "pipi-benchmark-v2-embedding-preparation",
        "catalog_snapshot_hash": snapshot_after,
        "expected_current_chunks": EXPECTED_CORPUS_CHUNKS,
        "profiles": results,
        "complete": complete,
    }
    output = ROOT / "results" / f"benchmark_v2_embedding_preparation_{snapshot_after[:12]}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    print()
    print(f"CATALOG_SNAPSHOT_AFTER={snapshot_after}")
    for item in results:
        status = item["status_after"]
        print(
            f"COVERAGE {item['profile_id']}="
            f"{status['embedded_current_model']}/{status['total_current_chunks']} "
            f"missing={status['missing']} complete={status['complete']}"
        )
    print(f"EMBEDDING_PREPARATION_ARTIFACT={output}")
    print("BENCHMARK_V2_EMBEDDINGS_READY" if complete else "BENCHMARK_V2_EMBEDDINGS_INCOMPLETE")

    if not complete:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
