from __future__ import annotations

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.catalog.migrations import MigrationError, run_migrations


class DatabaseBootstrapError(RuntimeError):
    pass


def _kwargs(database_url: str) -> dict[str, object]:
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise DatabaseBootstrapError("Database bootstrap supports PostgreSQL URLs only.")
    return {
        "host": url.host or "localhost",
        "port": url.port or 5432,
        "dbname": url.database,
        "user": url.username,
        "password": url.password,
    }


def _bootstrap_with_admin(database_url: str, admin_url: str) -> None:
    target = make_url(database_url)
    database_name = target.database
    database_user = target.username
    database_password = target.password or ""

    if not database_name or not database_user:
        raise DatabaseBootstrapError(
            "DATABASE_URL must include both target database name and username."
        )

    admin_kwargs = _kwargs(admin_url)
    with psycopg.connect(**admin_kwargs, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (database_user,))
            if cursor.fetchone() is None:
                cursor.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(database_user),
                        sql.Literal(database_password),
                    )
                )

            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
            if cursor.fetchone() is None:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(database_name),
                        sql.Identifier(database_user),
                    )
                )

            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(database_name),
                    sql.Identifier(database_user),
                )
            )

    admin_target = make_url(admin_url).set(database=database_name)
    with psycopg.connect(**_kwargs(admin_target.render_as_string(hide_password=False)), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
                    sql.Identifier(database_user)
                )
            )


def initialize_postgres_database(
    database_url: str,
    *,
    admin_url: str | None = None,
) -> dict[str, object]:
    """Ensure the catalog database exists and apply all pending schema migrations.

    Existing databases need no admin credentials. If the target database or role is
    missing, DATABASE_ADMIN_URL can be used to create them before migrations run.
    """

    try:
        return run_migrations(database_url)
    except psycopg.OperationalError as exc:
        if not admin_url:
            raise DatabaseBootstrapError(
                "Cannot connect to the catalog database. If it does not exist yet, "
                "set DATABASE_ADMIN_URL to a PostgreSQL admin connection or run "
                "scripts/init_database.py with that setting."
            ) from exc

    _bootstrap_with_admin(database_url, admin_url)
    try:
        return run_migrations(database_url)
    except (psycopg.Error, MigrationError) as exc:
        raise DatabaseBootstrapError(
            f"Catalog database exists but schema migration failed: {exc}"
        ) from exc
