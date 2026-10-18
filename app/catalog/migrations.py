from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import psycopg
import sqlparse
from sqlalchemy.engine import make_url


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str


_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"


def _connection_kwargs(database_url: str) -> dict[str, object]:
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise MigrationError("PostgreSQL migrations require a postgresql DATABASE_URL.")
    return {
        "host": url.host or "localhost",
        "port": url.port or 5432,
        "dbname": url.database,
        "user": url.username,
        "password": url.password,
    }


def discover_migrations(directory: Path = _MIGRATIONS_DIR) -> list[Migration]:
    migrations: list[Migration] = []
    for path in sorted(directory.glob("[0-9][0-9][0-9]_*.sql")):
        prefix, _, remainder = path.name.partition("_")
        if not prefix.isdigit() or not remainder:
            continue
        content = path.read_bytes()
        migrations.append(
            Migration(
                version=int(prefix),
                name=path.name,
                path=path,
                checksum=hashlib.sha256(content).hexdigest(),
            )
        )

    versions = [item.version for item in migrations]
    if len(versions) != len(set(versions)):
        raise MigrationError("Duplicate database migration version detected.")
    return migrations


def _statements(sql_text: str) -> Iterable[str]:
    for statement in sqlparse.split(sql_text):
        cleaned = statement.strip()
        if cleaned:
            yield cleaned


def run_migrations(database_url: str) -> dict[str, object]:
    migrations = discover_migrations()
    applied_now: list[int] = []

    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS catalog_schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    checksum CHAR(64) NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                "SELECT version, checksum FROM catalog_schema_migrations ORDER BY version"
            )
            applied = {int(version): str(checksum) for version, checksum in cursor.fetchall()}

        for migration in migrations:
            previous_checksum = applied.get(migration.version)
            if previous_checksum is not None:
                if previous_checksum != migration.checksum:
                    raise MigrationError(
                        "Applied migration checksum changed for "
                        f"{migration.name}. Do not edit applied migrations; add a new one."
                    )
                continue

            sql_text = migration.path.read_text(encoding="utf-8")
            with connection.transaction():
                with connection.cursor() as cursor:
                    for statement in _statements(sql_text):
                        cursor.execute(statement)
                    cursor.execute(
                        """
                        INSERT INTO catalog_schema_migrations(version, name, checksum)
                        VALUES (%s, %s, %s)
                        """,
                        (migration.version, migration.name, migration.checksum),
                    )
            applied_now.append(migration.version)

    current_version = migrations[-1].version if migrations else 0
    return {
        "current_version": current_version,
        "applied_now": applied_now,
        "migration_count": len(migrations),
    }
