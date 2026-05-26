-- 0001 — extend engine_calls.vendor check constraint to allow 'diffbot'.
--
-- The schema is managed directly against Supabase (no Alembic). Apply with:
--
--     psql "$SUPABASE_DATABASE_URL_pool" -f apps/api/sql/0001_engine_calls_add_diffbot_vendor.sql
--
-- Postgres can't ALTER a CHECK constraint in place; we DROP + re-ADD it.
-- Wrapped in a transaction so an interrupted apply doesn't leave the table
-- without any vendor constraint.

BEGIN;

ALTER TABLE engine_calls DROP CONSTRAINT IF EXISTS ck_engine_calls_vendor;

ALTER TABLE engine_calls ADD CONSTRAINT ck_engine_calls_vendor
    CHECK (vendor IN ('exa', 'anthropic', 'parallel', 'diffbot'));

COMMIT;
