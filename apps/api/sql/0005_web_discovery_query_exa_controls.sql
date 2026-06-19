-- 0005 — extend web_discovery_queries with Exa dashboard-like controls.
--
-- Apply with:
--   psql "$GCP_DATABASE_URL_POOL" -f apps/api/sql/0005_web_discovery_query_exa_controls.sql

BEGIN;

ALTER TABLE web_discovery_queries
    ADD COLUMN IF NOT EXISTS structured_outputs BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS highlights_max_chars INTEGER NULL,
    ADD COLUMN IF NOT EXISTS highlights_guiding_query TEXT NULL,
    ADD COLUMN IF NOT EXISTS text_max_chars INTEGER NULL,
    ADD COLUMN IF NOT EXISTS text_main_content_only BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS summary_max_chars INTEGER NULL;

ALTER TABLE web_discovery_queries
    DROP CONSTRAINT IF EXISTS ck_web_discovery_queries_highlights_max_chars_nonnegative,
    DROP CONSTRAINT IF EXISTS ck_web_discovery_queries_text_max_chars_nonnegative,
    DROP CONSTRAINT IF EXISTS ck_web_discovery_queries_summary_max_chars_nonnegative;

ALTER TABLE web_discovery_queries
    ADD CONSTRAINT ck_web_discovery_queries_highlights_max_chars_nonnegative
        CHECK (highlights_max_chars IS NULL OR highlights_max_chars >= 0),
    ADD CONSTRAINT ck_web_discovery_queries_text_max_chars_nonnegative
        CHECK (text_max_chars IS NULL OR text_max_chars >= 0),
    ADD CONSTRAINT ck_web_discovery_queries_summary_max_chars_nonnegative
        CHECK (summary_max_chars IS NULL OR summary_max_chars >= 0);

COMMIT;
