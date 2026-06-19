-- 0008 — articles table (Web Discovery ingest + Sonnet enrich output).
--
-- Apply with:
--   psql "$GCP_DATABASE_URL_POOL" -f apps/api/sql/0008_articles.sql

BEGIN;

CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    summary TEXT NULL,
    body_text TEXT NULL,
    source_name VARCHAR(255) NULL,
    published_at TIMESTAMPTZ NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cluster_id UUID NULL REFERENCES web_discovery_clusters(id) ON DELETE SET NULL,
    query_run_id UUID NULL REFERENCES runs(id) ON DELETE SET NULL,
    source_query_id UUID NULL REFERENCES web_discovery_queries(id) ON DELETE SET NULL,
    category_tag VARCHAR(80) NULL,
    priority_score INTEGER NULL,
    mentioned_companies JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_articles_title_nonempty CHECK (char_length(title) > 0),
    CONSTRAINT ck_articles_status_enum CHECK (status IN ('active', 'dismissed', 'archived')),
    CONSTRAINT ck_articles_priority_score_range CHECK (
        priority_score IS NULL OR (priority_score >= 0 AND priority_score <= 100)
    ),
    CONSTRAINT ck_articles_mentioned_companies_array CHECK (jsonb_typeof(mentioned_companies) = 'array'),
    CONSTRAINT ck_articles_source_metadata_object CHECK (jsonb_typeof(source_metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS ix_articles_cluster_id ON articles (cluster_id);
CREATE INDEX IF NOT EXISTS ix_articles_query_run_id ON articles (query_run_id);
CREATE INDEX IF NOT EXISTS ix_articles_source_query_id ON articles (source_query_id);
CREATE INDEX IF NOT EXISTS ix_articles_status ON articles (status);
CREATE INDEX IF NOT EXISTS ix_articles_published_at ON articles (published_at);
CREATE INDEX IF NOT EXISTS ix_articles_ingested_at ON articles (ingested_at);
CREATE INDEX IF NOT EXISTS ix_articles_status_ingested ON articles (status, ingested_at);

COMMIT;
