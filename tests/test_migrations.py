from app.catalog.migrations import discover_migrations


def test_catalog_sql_migrations_are_ordered_and_unique() -> None:
    migrations = discover_migrations()

    assert [migration.version for migration in migrations] == [1, 2, 3]
    assert [migration.name for migration in migrations] == [
        "001_catalog_core.sql",
        "002_catalog_versions.sql",
        "003_resource_registry.sql",
    ]
    assert all(len(migration.checksum) == 64 for migration in migrations)
