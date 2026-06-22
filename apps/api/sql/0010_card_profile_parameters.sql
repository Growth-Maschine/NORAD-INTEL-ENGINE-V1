-- 0010 — profile completeness parameters (one row per must-have param per card).
--
-- Apply with migrate user (owner), not norad_app:
--   psql "postgresql://norad_migrate:$GCP_SQL_MIGRATE_PASSWORD@HOST:5432/norad?sslmode=require" \
--     -f apps/api/sql/0010_card_profile_parameters.sql

BEGIN;

ALTER TABLE cards
    ADD COLUMN IF NOT EXISTS profile_completeness_pct INTEGER NULL;

ALTER TABLE cards
    ADD COLUMN IF NOT EXISTS profile_verified_count INTEGER NULL;

ALTER TABLE cards
    ADD COLUMN IF NOT EXISTS profile_uncertain_count INTEGER NULL;

ALTER TABLE cards
    ADD COLUMN IF NOT EXISTS profile_missing_count INTEGER NULL;

ALTER TABLE cards
    DROP CONSTRAINT IF EXISTS ck_cards_profile_completeness_pct_range;

ALTER TABLE cards
    ADD CONSTRAINT ck_cards_profile_completeness_pct_range
        CHECK (
            profile_completeness_pct IS NULL
            OR (profile_completeness_pct BETWEEN 0 AND 100)
        );

CREATE TABLE IF NOT EXISTS card_profile_parameters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    card_id UUID NOT NULL,
    param_key VARCHAR(64) NOT NULL,
    group_name VARCHAR(64) NOT NULL,
    sort_order INTEGER NOT NULL,
    label VARCHAR(128) NOT NULL,
    value JSONB NULL,
    confidence VARCHAR(16) NOT NULL DEFAULT 'unknown',
    basis TEXT NULL,
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    coverage_status VARCHAR(16) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_card_profile_parameters_card_company
        FOREIGN KEY (card_id, company_id)
        REFERENCES cards(id, company_id)
        ON DELETE CASCADE,
    CONSTRAINT uq_card_profile_parameters_card_param
        UNIQUE (card_id, param_key),
    CONSTRAINT ck_card_profile_parameters_confidence
        CHECK (confidence IN ('confirmed', 'estimated', 'inferred', 'unknown')),
    CONSTRAINT ck_card_profile_parameters_coverage_status
        CHECK (coverage_status IN ('verified', 'uncertain', 'missing'))
);

CREATE INDEX IF NOT EXISTS ix_card_profile_parameters_card_id
    ON card_profile_parameters (card_id);

CREATE INDEX IF NOT EXISTS ix_card_profile_parameters_company_id
    ON card_profile_parameters (company_id);

CREATE INDEX IF NOT EXISTS ix_card_profile_parameters_card_group
    ON card_profile_parameters (card_id, group_name, sort_order);

CREATE INDEX IF NOT EXISTS ix_card_profile_parameters_coverage
    ON card_profile_parameters (card_id, coverage_status);

COMMIT;
