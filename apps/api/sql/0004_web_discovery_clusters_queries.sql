-- 0004 — add web_discovery_clusters + web_discovery_queries tables.
--
-- Apply with:
--   psql "$SUPABASE_DATABASE_URL_pool" -f apps/api/sql/0004_web_discovery_clusters_queries.sql

BEGIN;

CREATE TABLE IF NOT EXISTS web_discovery_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(140) NOT NULL,
    slug VARCHAR(160) NOT NULL UNIQUE,
    description TEXT NULL,
    priority VARCHAR(32) NOT NULL DEFAULT 'P2 Daily Intelligence',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    include_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    exclude_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    geography_focus JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_preferences JSONB NOT NULL DEFAULT '[]'::jsonb,
    signal_priorities JSONB NOT NULL DEFAULT '[]'::jsonb,
    query_count INTEGER NOT NULL DEFAULT 0,
    signal_count INTEGER NOT NULL DEFAULT 0,
    last_run_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_web_discovery_clusters_name_nonempty CHECK (char_length(name) > 0),
    CONSTRAINT ck_web_discovery_clusters_slug_nonempty CHECK (char_length(slug) > 0),
    CONSTRAINT ck_web_discovery_clusters_priority_enum CHECK (
        priority IN ('P1 Critical', 'P2 Daily Intelligence', 'P3 Weekly Monitoring')
    ),
    CONSTRAINT ck_web_discovery_clusters_include_keywords_array CHECK (jsonb_typeof(include_keywords) = 'array'),
    CONSTRAINT ck_web_discovery_clusters_exclude_keywords_array CHECK (jsonb_typeof(exclude_keywords) = 'array'),
    CONSTRAINT ck_web_discovery_clusters_geography_focus_array CHECK (jsonb_typeof(geography_focus) = 'array'),
    CONSTRAINT ck_web_discovery_clusters_source_preferences_array CHECK (jsonb_typeof(source_preferences) = 'array'),
    CONSTRAINT ck_web_discovery_clusters_signal_priorities_array CHECK (jsonb_typeof(signal_priorities) = 'array'),
    CONSTRAINT ck_web_discovery_clusters_query_count_nonnegative CHECK (query_count >= 0),
    CONSTRAINT ck_web_discovery_clusters_signal_count_nonnegative CHECK (signal_count >= 0)
);

CREATE INDEX IF NOT EXISTS ix_web_discovery_clusters_slug ON web_discovery_clusters (slug);
CREATE INDEX IF NOT EXISTS ix_web_discovery_clusters_is_active ON web_discovery_clusters (is_active);
CREATE INDEX IF NOT EXISTS ix_web_discovery_clusters_priority ON web_discovery_clusters (priority);
CREATE INDEX IF NOT EXISTS ix_web_discovery_clusters_last_run_at ON web_discovery_clusters (last_run_at);

CREATE TABLE IF NOT EXISTS web_discovery_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES web_discovery_clusters(id) ON DELETE CASCADE,
    label VARCHAR(160) NOT NULL,
    search_query TEXT NOT NULL,
    search_type VARCHAR(32) NOT NULL DEFAULT 'auto',
    num_results INTEGER NOT NULL DEFAULT 10,
    content_highlights BOOLEAN NOT NULL DEFAULT TRUE,
    content_text BOOLEAN NOT NULL DEFAULT FALSE,
    content_summary BOOLEAN NOT NULL DEFAULT FALSE,
    livecrawl_timeout_ms INTEGER NOT NULL DEFAULT 10000,
    max_age_hours INTEGER NULL,
    subpages INTEGER NOT NULL DEFAULT 0,
    extra_links INTEGER NOT NULL DEFAULT 0,
    extra_image_links INTEGER NOT NULL DEFAULT 0,
    subpage_target_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    category VARCHAR(80) NULL,
    user_location VARCHAR(8) NULL,
    include_domains JSONB NOT NULL DEFAULT '[]'::jsonb,
    exclude_domains JSONB NOT NULL DEFAULT '[]'::jsonb,
    published_after DATE NULL,
    published_before DATE NULL,
    crawled_after DATE NULL,
    crawled_before DATE NULL,
    content_moderation BOOLEAN NOT NULL DEFAULT FALSE,
    stream_response BOOLEAN NOT NULL DEFAULT FALSE,
    additional_queries JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_web_discovery_queries_label_nonempty CHECK (char_length(label) > 0),
    CONSTRAINT ck_web_discovery_queries_search_query_nonempty CHECK (char_length(search_query) > 0),
    CONSTRAINT ck_web_discovery_queries_search_type_enum CHECK (
        search_type IN ('auto', 'fast', 'deep', 'deep-lite', 'deep-reasoning', 'instant')
    ),
    CONSTRAINT ck_web_discovery_queries_num_results_range CHECK (num_results >= 1 AND num_results <= 100),
    CONSTRAINT ck_web_discovery_queries_livecrawl_timeout_nonnegative CHECK (livecrawl_timeout_ms >= 0),
    CONSTRAINT ck_web_discovery_queries_subpages_nonnegative CHECK (subpages >= 0),
    CONSTRAINT ck_web_discovery_queries_extra_links_nonnegative CHECK (extra_links >= 0),
    CONSTRAINT ck_web_discovery_queries_extra_image_links_nonnegative CHECK (extra_image_links >= 0),
    CONSTRAINT ck_web_discovery_queries_max_age_valid CHECK (max_age_hours IS NULL OR max_age_hours >= -1),
    CONSTRAINT ck_web_discovery_queries_subpage_target_keywords_array CHECK (jsonb_typeof(subpage_target_keywords) = 'array'),
    CONSTRAINT ck_web_discovery_queries_include_domains_array CHECK (jsonb_typeof(include_domains) = 'array'),
    CONSTRAINT ck_web_discovery_queries_exclude_domains_array CHECK (jsonb_typeof(exclude_domains) = 'array'),
    CONSTRAINT ck_web_discovery_queries_additional_queries_array CHECK (jsonb_typeof(additional_queries) = 'array')
);

CREATE INDEX IF NOT EXISTS ix_web_discovery_queries_cluster_id ON web_discovery_queries (cluster_id);
CREATE INDEX IF NOT EXISTS ix_web_discovery_queries_is_active ON web_discovery_queries (is_active);
CREATE INDEX IF NOT EXISTS ix_web_discovery_queries_cluster_created ON web_discovery_queries (cluster_id, created_at);

COMMIT;
