-- 0009 — link Web Discovery article mentions to companies rows.
--
-- Apply with migrate user (owner), not norad_app:
--   psql "postgresql://norad_migrate:$GCP_SQL_MIGRATE_PASSWORD@HOST:5432/norad?sslmode=require" \
--     -f apps/api/sql/0009_companies_web_discovery_origin.sql

BEGIN;

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS origin VARCHAR(32) NOT NULL DEFAULT 'research';

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS source_article_id UUID NULL
        REFERENCES articles(id) ON DELETE SET NULL;

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS discovery_role VARCHAR(64) NULL;

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS discovery_context TEXT NULL;

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS normalized_name VARCHAR(255) NULL;

UPDATE companies SET origin = 'research' WHERE origin IS NULL;

ALTER TABLE companies
    DROP CONSTRAINT IF EXISTS ck_companies_origin;

ALTER TABLE companies
    ADD CONSTRAINT ck_companies_origin
        CHECK (origin IN ('web_discovery', 'research'));

CREATE INDEX IF NOT EXISTS ix_companies_source_article_id
    ON companies (source_article_id);

CREATE INDEX IF NOT EXISTS ix_companies_origin
    ON companies (origin);

CREATE INDEX IF NOT EXISTS ix_companies_normalized_name
    ON companies (normalized_name);

CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_article_normalized_name
    ON companies (source_article_id, normalized_name)
    WHERE source_article_id IS NOT NULL AND normalized_name IS NOT NULL;

COMMIT;
