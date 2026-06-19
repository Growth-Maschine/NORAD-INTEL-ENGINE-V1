-- 0003 — create discovery_clusters table + seed default cluster packs.
-- SUPERSEDED by 0007_drop_today_legacy.sql (Today page removed).
-- Kept for migration audit trail on databases that applied 0003 before 0007.
--
-- Apply with:
--
--     psql "$GCP_DATABASE_URL_POOL" -f apps/api/sql/0003_discovery_clusters.sql

BEGIN;

CREATE TABLE IF NOT EXISTS discovery_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL UNIQUE,
    group_name VARCHAR(120) NOT NULL DEFAULT 'Custom',
    description TEXT NULL,
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_discovery_clusters_name_nonempty CHECK (char_length(name) > 0),
    CONSTRAINT ck_discovery_clusters_slug_nonempty CHECK (char_length(slug) > 0),
    CONSTRAINT ck_discovery_clusters_keywords_array CHECK (jsonb_typeof(keywords) = 'array'),
    CONSTRAINT ck_discovery_clusters_sort_order_nonnegative CHECK (sort_order >= 0)
);

CREATE INDEX IF NOT EXISTS ix_discovery_clusters_slug ON discovery_clusters (slug);
CREATE INDEX IF NOT EXISTS ix_discovery_clusters_enabled ON discovery_clusters (is_enabled);
CREATE INDEX IF NOT EXISTS ix_discovery_clusters_default ON discovery_clusters (is_default);
CREATE INDEX IF NOT EXISTS ix_discovery_clusters_sort_order ON discovery_clusters (sort_order);
CREATE INDEX IF NOT EXISTS ix_discovery_clusters_group_sort ON discovery_clusters (group_name, sort_order);
CREATE UNIQUE INDEX IF NOT EXISTS uq_discovery_clusters_single_default
    ON discovery_clusters ((is_default))
    WHERE is_default = TRUE;

INSERT INTO discovery_clusters
    (name, slug, group_name, description, keywords, is_enabled, is_default, sort_order)
VALUES
    (
        'Nicotine Alternatives',
        'nicotine-alternatives',
        'Core Product & Industry',
        'Modern oral, smoke-free, and next-generation nicotine formats.',
        '[
          "nicotine pouch",
          "nicotine-free pouch",
          "oral nicotine",
          "smokeless nicotine",
          "tobacco-free nicotine",
          "synthetic nicotine",
          "nicotine delivery system",
          "nicotine replacement",
          "nicotine innovation",
          "heated tobacco",
          "heat-not-burn",
          "reduced risk product",
          "modern oral",
          "next generation nicotine",
          "vaping alternative",
          "smoke-free product",
          "nicotine wellness",
          "nicotine functional product",
          "oral stimulation product"
        ]'::jsonb,
        TRUE,
        TRUE,
        0
    ),
    (
        'Functional Beverage Trends',
        'functional-beverage-trends',
        'Core Product & Industry',
        'Performance, hydration, cognition, and recovery beverage signals.',
        '[
          "functional beverage",
          "nootropic drink",
          "adaptogen beverage",
          "hydration beverage",
          "wellness beverage",
          "energy alternative",
          "clean energy drink",
          "mushroom beverage",
          "protein hydration",
          "sleep beverage",
          "stress relief drink",
          "cognition beverage",
          "focus drink",
          "electrolyte innovation",
          "performance beverage",
          "recovery beverage",
          "metabolic beverage",
          "longevity beverage",
          "biohacking drink"
        ]'::jsonb,
        TRUE,
        FALSE,
        1
    ),
    (
        'Wellness & Health Products',
        'wellness-health-products',
        'Core Product & Industry',
        'Consumer wellness products, systems, and preventative-health themes.',
        '[
          "biohacking",
          "wellness technology",
          "functional wellness",
          "preventative health",
          "longevity product",
          "healthy aging",
          "sleep optimization",
          "stress reduction",
          "recovery technology",
          "cognitive enhancement",
          "hormone optimization",
          "metabolic health",
          "personalized wellness",
          "wellness stack",
          "consumer wellness trend",
          "wellness innovation"
        ]'::jsonb,
        TRUE,
        FALSE,
        2
    ),
    (
        'CPG / Consumer Product Discovery',
        'cpg-consumer-product-discovery',
        'Core Product & Industry',
        'Emerging CPG, DTC, challenger brands, and premiumization signals.',
        '[
          "emerging consumer brand",
          "disruptive consumer brand",
          "viral product",
          "premium consumer goods",
          "DTC brand",
          "challenger brand",
          "next-gen CPG",
          "innovative packaging",
          "sustainable packaging",
          "eco-conscious product",
          "convenience innovation",
          "premiumization trend",
          "lifestyle product",
          "subscription consumer product",
          "creator-led brand",
          "influencer-led product"
        ]'::jsonb,
        TRUE,
        FALSE,
        3
    )
ON CONFLICT (slug) DO NOTHING;

-- If no default exists (e.g. rows pre-existed), set the first by sort_order.
WITH first_row AS (
    SELECT id FROM discovery_clusters ORDER BY sort_order ASC, created_at ASC LIMIT 1
)
UPDATE discovery_clusters
SET is_default = TRUE
WHERE id IN (SELECT id FROM first_row)
  AND NOT EXISTS (
      SELECT 1 FROM discovery_clusters WHERE is_default = TRUE
  );

COMMIT;
