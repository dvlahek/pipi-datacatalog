-- Manual psql fallback for creating the PiPi catalog role/database.
-- The Python initializer is the normal path: python scripts/init_database.py
--
-- Example:
-- psql -U postgres -d postgres \
--   -v catalog_user=pipi \
--   -v catalog_password=pipi_dev \
--   -v catalog_db=pipi_catalog \
--   -f database/bootstrap/create_catalog_database.psql.sql
--
-- Do not put a real production password in this file.

SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L',
    :'catalog_user',
    :'catalog_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'catalog_user'
) \gexec

SELECT format(
    'CREATE DATABASE %I OWNER %I',
    :'catalog_db',
    :'catalog_user'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = :'catalog_db'
) \gexec

\connect :catalog_db

GRANT USAGE, CREATE ON SCHEMA public TO :"catalog_user";
