-- 0012 — organizations, members, invites, API keys, access scoping, auth config, audit.
--
-- Apply with:
--   psql "$GCP_DATABASE_URL_POOL" -f apps/api/sql/0012_organizations.sql

BEGIN;

CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_organizations_name_nonempty CHECK (char_length(name) > 0),
    CONSTRAINT ck_organizations_domain_nonempty CHECK (char_length(domain) > 0),
    CONSTRAINT ck_organizations_status_enum CHECK (status IN ('active', 'suspended')),
    CONSTRAINT uq_organizations_domain UNIQUE (domain)
);

CREATE INDEX IF NOT EXISTS ix_organizations_status ON organizations (status);
CREATE INDEX IF NOT EXISTS ix_organizations_name ON organizations (name);

CREATE TABLE IF NOT EXISTS organization_auth_config (
    organization_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    mfa_enforced BOOLEAN NOT NULL DEFAULT FALSE,
    sso_only BOOLEAN NOT NULL DEFAULT FALSE,
    ip_allowlist_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    scim_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ip_allowlist JSONB NOT NULL DEFAULT '[]'::jsonb,
    sso_provider VARCHAR(64) NULL,
    sso_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_organization_auth_config_ip_allowlist_array CHECK (jsonb_typeof(ip_allowlist) = 'array')
);

CREATE TABLE IF NOT EXISTS organization_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL DEFAULT 'default',
    key_prefix VARCHAR(24) NOT NULL,
    key_hash VARCHAR(64) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ NULL,
    last_used_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_organization_api_keys_prefix_nonempty CHECK (char_length(key_prefix) > 0),
    CONSTRAINT ck_organization_api_keys_hash_nonempty CHECK (char_length(key_hash) = 64),
    CONSTRAINT uq_organization_api_keys_hash UNIQUE (key_hash)
);

CREATE INDEX IF NOT EXISTS ix_organization_api_keys_org_active
    ON organization_api_keys (organization_id)
    WHERE revoked_at IS NULL AND is_active = TRUE;

CREATE TABLE IF NOT EXISTS organization_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(320) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'staff',
    team VARCHAR(120) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deactivated_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_organization_members_email_nonempty CHECK (char_length(email) > 0),
    CONSTRAINT ck_organization_members_display_name_nonempty CHECK (char_length(display_name) > 0),
    CONSTRAINT ck_organization_members_role_enum CHECK (role IN ('staff', 'manager')),
    CONSTRAINT ck_organization_members_status_enum CHECK (status IN ('active', 'deactivated')),
    CONSTRAINT uq_organization_members_org_email UNIQUE (organization_id, email)
);

CREATE INDEX IF NOT EXISTS ix_organization_members_org_status
    ON organization_members (organization_id, status);

CREATE TABLE IF NOT EXISTS organization_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(320) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'staff',
    team VARCHAR(120) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ NULL,
    accepted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_organization_invites_email_nonempty CHECK (char_length(email) > 0),
    CONSTRAINT ck_organization_invites_display_name_nonempty CHECK (char_length(display_name) > 0),
    CONSTRAINT ck_organization_invites_role_enum CHECK (role IN ('staff', 'manager')),
    CONSTRAINT ck_organization_invites_status_enum CHECK (
        status IN ('pending', 'accepted', 'expired', 'cancelled')
    ),
    CONSTRAINT ck_organization_invites_token_hash_len CHECK (char_length(token_hash) = 64),
    CONSTRAINT uq_organization_invites_token_hash UNIQUE (token_hash)
);

CREATE INDEX IF NOT EXISTS ix_organization_invites_org_status
    ON organization_invites (organization_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_organization_invites_org_email_pending
    ON organization_invites (organization_id, lower(email))
    WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS organization_clusters (
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    cluster_id UUID NOT NULL REFERENCES web_discovery_clusters(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS ix_organization_clusters_cluster_id
    ON organization_clusters (cluster_id);

CREATE TABLE IF NOT EXISTS organization_companies (
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, company_id),
    CONSTRAINT uq_organization_companies_company_exclusive UNIQUE (company_id)
);

CREATE TABLE IF NOT EXISTS organization_audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NULL,
    actor_label VARCHAR(255) NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_organization_audit_events_title_nonempty CHECK (char_length(title) > 0)
);

CREATE INDEX IF NOT EXISTS ix_organization_audit_events_org_created
    ON organization_audit_events (organization_id, created_at DESC);

COMMIT;
