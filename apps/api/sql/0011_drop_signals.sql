-- Drop research signals table — BD signal timeline moved to future frontend.
-- Apply:
--   psql "$SUPABASE_DATABASE_URL_pool" -f apps/api/sql/0011_drop_signals.sql
-- (use norad_migrate / migrate role, not norad_app)

DROP TABLE IF EXISTS signals CASCADE;
