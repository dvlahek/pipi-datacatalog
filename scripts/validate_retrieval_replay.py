from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.drift import replay_retrieval_run
from app.rag.profiles import (
    ensure_builtin_profiles,
    get_retrieval_profile,
    record_retrieval_run,
)
from app.rag.search import search_rag


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create one frozen retrieval run and immediately validate strict replay."
    )
    parser.add_argument("--query", default="runtime ownership")
    parser.add_argument("--profile", default="hybrid-e5-content-v1")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    ensure_builtin_profiles(store)
    profile = get_retrieval_profile(args.profile)
    payload = search_rag(
        store,
        settings,
        args.query,
        limit=args.limit,
        profile_id=profile.profile_id,
    )
    run_id = record_retrieval_run(
        store,
        query=args.query,
        profile=profile,
        retrieval=str(payload.get("retrieval") or "unknown"),
        top_k=args.limit,
        result=payload,
    )
    if run_id is None:
        raise SystemExit("Retrieval run persistence requires PostgreSQL.")

    replay = replay_retrieval_run(store, settings, run_id)
    drift = replay["drift"]

    print(f"Created run: {run_id}")
    print(f"Query: {args.query}")
    print(f"Profile: {profile.profile_id}  hash={profile.config_hash[:12]}")
    print(f"Catalog snapshot: {str(replay['catalog_snapshot_hash'])[:12]}")
    print(f"Exact ordered evidence reproduced: {replay['exact_evidence_reproduced']}")
    print(
        f"Retention@{drift['top_k']}={drift['retention_at_k']:.3f}  "
        f"Churn@{drift['top_k']}={drift['churn_at_k']:.3f}  "
        f"Jaccard@{drift['top_k']}={drift['jaccard_at_k']:.3f}"
    )
    print(f"Mean rank shift on shared evidence: {drift['mean_abs_rank_shift_common']}")

    if not replay["exact_evidence_reproduced"]:
        raise SystemExit("STRICT_REPLAY_FAIL")
    print("STRICT_REPLAY_PASS")


if __name__ == "__main__":
    main()
