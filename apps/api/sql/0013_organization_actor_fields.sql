-- 0013 — actor attribution on organization tables (created_by, invited_by, etc.)
--
-- Apply with:
--   psql "$GCP_DATABASE_URL_POOL" -f apps/api/sql/0013_organization_actor_fields.sql

BEGIN;

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(255) NOT NULL DEFAULT 'admin',
    ADD COLUMN IF NOT EXISTS updated_by VARCHAR(255) NULL;

ALTER TABLE organization_members
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(255) NOT NULL DEFAULT 'admin',
    ADD COLUMN IF NOT EXISTS updated_by VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS deactivated_by VARCHAR(255) NULL;

ALTER TABLE organization_invites
    ADD COLUMN IF NOT EXISTS invited_by VARCHAR(255) NOT NULL DEFAULT 'admin';

ALTER TABLE organization_api_keys
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(255) NOT NULL DEFAULT 'admin',
    ADD COLUMN IF NOT EXISTS revoked_by VARCHAR(255) NULL;

ALTER TABLE organization_auth_config
    ADD COLUMN IF NOT EXISTS updated_by VARCHAR(255) NULL;

ALTER TABLE organization_clusters
    ADD COLUMN IF NOT EXISTS assigned_by VARCHAR(255) NOT NULL DEFAULT 'admin';

ALTER TABLE organization_companies
    ADD COLUMN IF NOT EXISTS assigned_by VARCHAR(255) NOT NULL DEFAULT 'admin';

ALTER TABLE organizations
    ADD CONSTRAINT ck_organizations_created_by_nonempty
        CHECK (char_length(created_by) > 0);

ALTER TABLE organization_members
    ADD CONSTRAINT ck_organization_members_created_by_nonempty
        CHECK (char_length(created_by) > 0);

ALTER TABLE organization_invites
    ADD CONSTRAINT ck_organization_invites_invited_by_nonempty
        CHECK (char_length(invited_by) > 0);

ALTER TABLE organization_api_keys
    ADD CONSTRAINT ck_organization_api_keys_created_by_nonempty
        CHECK (char_length(created_by) > 0);

ALTER TABLE organization_clusters
    ADD CONSTRAINT ck_organization_clusters_assigned_by_nonempty
        CHECK (char_length(assigned_by) > 0);

ALTER TABLE organization_companies
    ADD CONSTRAINT ck_organization_companies_assigned_by_nonempty
        CHECK (char_length(assigned_by) > 0);

COMMIT;
