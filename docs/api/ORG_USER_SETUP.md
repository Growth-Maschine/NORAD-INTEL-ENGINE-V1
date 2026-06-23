# Organization & User Setup

Admin API for multi-tenant org management. Powers the new admin UI (`/dashboard/organizations`).

**Auth:** All `/api/admin/organizations/*` routes require `X-Admin-Token` when `DEBUG=false`.  
**Actor attribution:** Optional header `X-Actor-Label: you@growthmaschine.com` on write routes — stored as `created_by`, `invited_by`, `assigned_by`, etc. Defaults to `admin` when omitted.  
**Audience:** Growth Maschine staff only — not customer admins.

---

## Data model

| Table | Purpose |
|-------|---------|
| `organizations` | Tenant: name, domain (unique), status (`active` \| `suspended`) |
| `organization_auth_config` | SSO/security toggles (schema-first; wiring later) |
| `organization_api_keys` | One active integration key per org (hashed at rest) |
| `organization_members` | Analyst users: role (`staff` \| `manager`), team, status |
| `organization_invites` | Pending invite flow before member row exists |
| `organization_clusters` | M2M org ↔ `web_discovery_clusters` |
| `organization_companies` | Org ↔ `companies` — **exclusive** (`company_id` unique) |
| `organization_audit_events` | Activity tab / audit trail |

### Actor fields (who did what)

| Table | Fields |
|-------|--------|
| `organizations` | `created_by`, `updated_by` |
| `organization_members` | `created_by`, `updated_by`, `deactivated_by` |
| `organization_invites` | `invited_by` |
| `organization_api_keys` | `created_by`, `revoked_by` |
| `organization_auth_config` | `updated_by` |
| `organization_clusters` | `assigned_by` |
| `organization_companies` | `assigned_by` |
| `organization_audit_events` | `actor_label` (same value as `X-Actor-Label`) |

### Scoping rules

| Relationship | Rule |
|--------------|------|
| Org → clusters | Many (M2M) |
| Org → companies | Many |
| Cluster → orgs | Many |
| **Company → org** | **One only** |

### Display status

- `status` on org: `active` or `suspended` (admin-controlled).
- `display_status: provisioning` — computed when in-flight `runs` exist for org's clusters or companies (`queued`, `researching`, `synthesizing`).

---

## API surface

Base: `/api/admin/organizations`

### Organizations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List orgs (`search`, `status`, `offset`, `limit`) |
| `POST` | `/` | Create org + auto integration key (plaintext once in response) |
| `GET` | `/{id}/overview` | Summary cards + operational health |
| `PATCH` | `/{id}` | Update name, domain, status |
| `POST` | `/{id}/suspend` | Set status suspended |
| `POST` | `/{id}/sync` | Stub sync (audit event until IdP ships) |

### Access

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{id}/clusters` | List assigned clusters |
| `POST` | `/{id}/clusters` | `{ "cluster_id": "..." }` |
| `DELETE` | `/{id}/clusters/{cluster_id}` | Remove assignment |
| `GET` | `/{id}/companies` | List assigned companies |
| `POST` | `/{id}/companies` | `{ "company_id": "..." }` |
| `DELETE` | `/{id}/companies/{company_id}` | Remove assignment |

### Users & invites

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{id}/users` | Members (`status`, `role`, `team` filters) |
| `GET` | `/{id}/invites` | Invites (default `status=pending`) |
| `POST` | `/{id}/users` | Create invite — returns `accept_token` once |
| `POST` | `/{id}/invites/{invite_id}/resend` | Resend invite + new token |
| `PATCH` | `/{id}/users/{member_id}` | Edit name, role, team |
| `POST` | `/{id}/users/{member_id}/deactivate` | Deactivate member |

### Integration key

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{id}/integration-key` | Metadata only (prefix, never full key) |
| `POST` | `/{id}/integration-key/rotate` | Revoke old, issue new (plaintext once) |

### Security & activity

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{id}/security` | Policy toggles |
| `PATCH` | `/{id}/security` | Update MFA, SSO-only, SCIM, IP allowlist |
| `GET` | `/{id}/activity` | Audit events |

### Public (analyst onboarding)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/invites/accept` | `{ "token": "..." }` → creates member |

---

## Migration

```bash
psql "$GCP_DATABASE_URL_POOL" -f apps/api/sql/0012_organizations.sql
```

---

## Example curls

```bash
export API=http://localhost:8000
export ADMIN_TOKEN=your-norad-admin-token

# List organizations
curl -s "$API/api/admin/organizations" -H "X-Admin-Token: $ADMIN_TOKEN" | jq

# Create organization
curl -s -X POST "$API/api/admin/organizations" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Inc.","domain":"acme.inc","status":"active"}' | jq

# Assign cluster
curl -s -X POST "$API/api/admin/organizations/{ORG_ID}/clusters" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cluster_id":"{CLUSTER_ID}"}'

# Invite user
curl -s -X POST "$API/api/admin/organizations/{ORG_ID}/users" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"rene.wells@acme.inc","display_name":"Rene Wells","role":"manager","team":"Revenue"}' | jq

# Accept invite (analyst side)
curl -s -X POST "$API/api/invites/accept" \
  -H "Content-Type: application/json" \
  -d '{"token":"{ACCEPT_TOKEN}"}' | jq
```

---

## Deferred (schema ready, logic later)

- Email delivery for invites
- SSO / Entra wiring (`organization_auth_config`)
- Integration key expiry enforcement
- Role permission enforcement (`staff` vs `manager` identical today)
- Analyst UI session auth (org key + user)

*Last updated: 2026-06-22*
