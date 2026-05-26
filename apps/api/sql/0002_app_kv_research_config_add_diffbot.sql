-- 0002 — seed the `diffbot` block into the existing `app_kv.research_config` row.
--
-- The Pydantic schema in services/settings.py is forward-compatible (older
-- rows without `diffbot` get the default block injected at read time), so
-- this migration is purely for DB hygiene: it makes `app_kv` reflect the
-- shape the API now returns, so anyone querying the row directly sees the
-- full schema. Idempotent — re-applying does nothing.
--
-- Apply with:
--
--     psql "$SUPABASE_DATABASE_URL_pool" -f apps/api/sql/0002_app_kv_research_config_add_diffbot.sql

BEGIN;

UPDATE app_kv
SET value = value || jsonb_build_object(
        'diffbot',
        jsonb_build_object(
            'enabled', true,
            'score_threshold', 0.0
        )
    )
WHERE key = 'research_config'
  AND NOT (value ? 'diffbot');

COMMIT;
