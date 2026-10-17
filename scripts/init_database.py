from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.database import DatabaseBootstrapError, initialize_postgres_database
from app.catalog.migrations import MigrationError
from app.config import get_settings


def main() -> int:
    settings = get_settings()
    if not settings.database_url:
        print("DATABASE_URL is not configured in .env")
        return 2

    try:
        result = initialize_postgres_database(
            settings.database_url,
            admin_url=settings.database_admin_url,
        )
    except (DatabaseBootstrapError, MigrationError) as exc:
        print(f"DATABASE_INIT_FAILED: {exc}")
        return 1

    print("DATABASE_INIT_OK")
    print(f"CURRENT_SCHEMA_VERSION={result['current_version']}")
    print(f"APPLIED_NOW={result['applied_now']}")
    print(f"MIGRATION_COUNT={result['migration_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
