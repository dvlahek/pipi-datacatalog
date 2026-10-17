# PiPi catalog database

PostgreSQL schema changes are versioned in `database/migrations`.

Current migrations:

- `001_catalog_core.sql` creates `catalog_datasets` and `catalog_distributions`
- `002_catalog_versions.sql` creates immutable `catalog_dataset_versions`

The migration runner also maintains `catalog_schema_migrations`, which records the migration version, file name, SHA-256 checksum and application time.

## Rules

1. Never edit an SQL migration after it has been applied to a database.
2. Add a new sequential migration for every schema change, for example `003_add_language.sql`.
3. At initialization the runner scans all migrations, applies only missing versions, and records their checksums.
4. If an already-applied migration file is changed later, initialization fails on the checksum mismatch instead of silently changing database history.

## Initialize a local PostgreSQL installation

Configure `.env` with the normal application connection:

```env
CATALOG_STORE_ENABLED=true
DATABASE_URL=postgresql+psycopg://pipi:pipi_dev@localhost:5432/pipi_catalog
```

If the target role/database do not exist yet, also provide a PostgreSQL admin connection in the local `.env`:

```env
DATABASE_ADMIN_URL=postgresql+psycopg://postgres:YOUR_LOCAL_ADMIN_PASSWORD@localhost:5432/postgres
```

Then run:

```bash
python scripts/init_database.py
```

If the database already exists, no admin connection is needed. The script simply applies pending migrations.

The FastAPI catalog store uses the same migration runner whenever the persistent store is initialized, so a later deployment automatically applies newly added migration files before normal catalog access.
