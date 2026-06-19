-- 0006 — add system prompt + output schema controls for web_discovery_queries.
--
-- Apply with:
--   psql "$GCP_DATABASE_URL_POOL" -f apps/api/sql/0006_web_discovery_query_prompt_schema.sql

BEGIN;

ALTER TABLE web_discovery_queries
    ADD COLUMN IF NOT EXISTS system_prompt TEXT NULL,
    ADD COLUMN IF NOT EXISTS output_schema JSONB NULL;

ALTER TABLE web_discovery_queries
    DROP CONSTRAINT IF EXISTS ck_web_discovery_queries_output_schema_object;

ALTER TABLE web_discovery_queries
    ADD CONSTRAINT ck_web_discovery_queries_output_schema_object
        CHECK (output_schema IS NULL OR jsonb_typeof(output_schema) IN ('object', 'null'));

COMMIT;
