from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.drift import replay_retrieval_run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Strictly replay one recorded PiPi retrieval run on the same frozen profile and catalog snapshot."
    )
    parser.add_argument("run_id", type=int)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    try:
        payload = replay_retrieval_run(store, settings, args.run_id)
    except (KeyError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return

    drift = payload["drift"]
    print(f"Source run: {payload['source_run_id']}")
    print(f"Profile: {payload['profile_id']}  hash={payload['profile_hash'][:12]}")
    print(f"Catalog snapshot: {payload['catalog_snapshot_hash'][:12]}")
    print(f"Exact ordered evidence reproduced: {payload['exact_evidence_reproduced']}")
    print(
        f"Retention@{drift['top_k']}={drift['retention_at_k']:.3f}  "
        f"Churn@{drift['top_k']}={drift['churn_at_k']:.3f}  "
        f"Jaccard@{drift['top_k']}={drift['jaccard_at_k']:.3f}"
    )
    print(f"Mean rank shift on shared evidence: {drift['mean_abs_rank_shift_common']}")


if __name__ == "__main__":
    main()
