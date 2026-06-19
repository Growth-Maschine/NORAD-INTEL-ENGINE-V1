-- 0007 — remove Today page legacy tables (trend_articles + discovery_clusters).
--
-- Apply after deploying code that no longer references these tables:
--
--     psql "$GCP_DATABASE_URL_POOL" -f apps/api/sql/0007_drop_today_legacy.sql

BEGIN;

DROP TABLE IF EXISTS trend_articles;
DROP TABLE IF EXISTS discovery_clusters;

COMMIT;
