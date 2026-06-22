# NORAD API Contract Plan

Short roadmap for turning `apps/api` into a proper B2B API provider.  
**Internal admin** (web-discovery clusters, settings) and **external consumer** (BAT BFF, analyst UI) share one backend but different surfaces.

---

## Current state

| Already in place | Not yet |
|------------------|---------|
| FastAPI + `/api/*` routes | `/api/v1/` versioning |
| Pydantic response models | Consumer API keys + scopes |
| Auto OpenAPI at `/docs` | Published contract in CI |
| `CompanyCardV1` schema | RFC-style error envelope |
| Separate deploy (`apps/api` vs `apps/web`) | Request ID on every response |
| `X-Admin-Token` on settings writes + all 5 cluster routes | Idempotency header on research POST |
| | Route classification doc (this plan extends that) |

The monorepo stays. `apps/web` is one admin client; BAT and analyst UIs are other clients.

---

## Route surfaces

| Surface | Audience | Auth (target) | Example paths |
|---------|----------|---------------|---------------|
| **External v1** | BAT BFF, analyst read API | API key + scopes | `/api/v1/research/companies`, `/api/v1/research/runs` |
| **Internal admin** | Operator / admin frontends | `X-Admin-Token` | `/api/web-discovery/*`, `/api/settings/*` |
| **Platform** | Ops, health checks | None / internal only | `/health`, `/ready` |

Web-discovery **clusters** are **internal admin** — not part of BAT v1.

---

## Phased delivery

### Phase 0 — Admin integration (now)

**Goal:** Second admin frontend can call cluster APIs safely.

| Item | Detail |
|------|--------|
| Cluster CRUD | `GET/POST/PUT/DELETE` `/api/web-discovery/clusters` |
| Auth | `X-Admin-Token` on all 5 cluster routes when `DEBUG=false` |
| Docs | This file + cluster endpoint notes below |
| Out of scope | v1 prefix, API keys, idempotency |

**Cluster endpoints for testing**

| Method | Path | Auth (prod) |
|--------|------|-------------|
| `GET` | `/api/web-discovery/clusters` | `X-Admin-Token` |
| `GET` | `/api/web-discovery/clusters/{id}` | `X-Admin-Token` |
| `POST` | `/api/web-discovery/clusters` | `X-Admin-Token` |
| `PUT` | `/api/web-discovery/clusters/{id}` | `X-Admin-Token` |
| `DELETE` | `/api/web-discovery/clusters/{id}` | `X-Admin-Token` |

Env: `NORAD_ADMIN_TOKEN` (or `ADMIN_TOKEN`) on the API must match `X-Admin-Token` sent by the admin frontend. `DEBUG=true` skips the check (local dev).

---

### Phase 1 — API product MVP (before BAT)

**Goal:** Stable external contract for BAT BFF.

1. **`/api/v1/`** prefix on external routes; keep legacy paths during transition.
2. **API key auth** with scopes: `research:read`, `research:write` (and later analyst scopes).
3. **Request ID middleware** — `X-Request-Id` on every request/response.
4. **Structured errors** — consistent JSON error body + `request_id`.
5. **`Idempotency-Key`** on `POST /api/v1/research/runs` (DB column already exists).
6. **Route classification** — maintain list of external vs internal (see § Route surfaces).
7. **Export OpenAPI** — `docs/api/openapi.v1.yaml` (external); optional `openapi.admin.yaml` (internal).

**BAT v1 candidates (initial external surface):**

- `GET /api/v1/research/companies/{id}`
- `GET /api/v1/research/companies/{id}/profile-completeness`
- `GET /api/v1/research/cards/{id}`
- `POST /api/v1/research/runs` + `GET .../runs/{id}`
- `GET /api/v1/events/runs/{id}` (SSE) or webhooks (Phase 2)

---

### Phase 2 — Enterprise reliability

- Per-key **rate limiting** (Redis) + `429` / `Retry-After`
- **Cursor pagination** on list endpoints (`companies`, `feed`)
- **Webhooks** for run completion (alternative to SSE for server-side BFFs)
- **OpenAPI CI** — Spectral lint + oasdiff breaking-change checks
- Extend `require_admin` to remaining web-discovery writes (queries, runs)

---

### Phase 3 — Multi-tenant platform

- `organization_id` + tenant isolation
- OAuth2 client credentials (if required over API keys)
- Published SDKs + Postman collection
- Status page + versioned API changelog

---

## Middleware & cross-cutting stack

Request flow (target state). Items marked **live** exist today; others ship per phase.

| Order | Middleware / concern | Phase | Status | Mechanism |
|-------|----------------------|-------|--------|-----------|
| 1 | **CORS** | — | **Live** | `CORSMiddleware`; `CORS_ORIGINS` env |
| 2 | **Request ID** | 1 | Planned | Generate or accept `X-Request-Id`; echo on response; log correlation |
| 3 | **Access logging** | 1 | Planned | Structured JSON: method, path, status, latency_ms, request_id, client |
| 4 | **Consumer auth** | 1 | Planned | `Authorization: Bearer <api_key>` or `X-API-Key` on `/api/v1/*` |
| 5 | **Admin auth** | 0 | **Live** (partial) | `X-Admin-Token` + `require_admin` on all 5 cluster routes; settings writes |
| 6 | **Rate limiting** | 2 | Planned | Per API key (Redis); `429` + `Retry-After` + `RateLimit-*` headers |
| 7 | **Route handlers** | — | **Live** | FastAPI routers |
| 8 | **Error envelope** | 1 | Planned | Global exception handler; stable `error.type`, `error.code`, `request_id` |
| 9 | **Idempotency** | 1 | Planned | `Idempotency-Key` header on `POST /api/v1/research/runs` |
| 10 | **Version routing** | 1 | Planned | `/api/v1/*` external; legacy `/api/*` during transition |

BAT's Azure APIM may duplicate gateway duties (IP allow-list, JWT, rate limits). Origin-side middleware still applies so the API is safe when called directly.

---

## Auth model

| Client | Surface | Phase | Header / credential | Scopes (target) | Env / config |
|--------|---------|-------|---------------------|-----------------|--------------|
| Admin cluster routes (all 5) | Internal | 0 | `X-Admin-Token` | n/a | `NORAD_ADMIN_TOKEN` |
| Admin frontend (settings) | Internal | 0 | `X-Admin-Token` | n/a | `NORAD_ADMIN_TOKEN` |
| Admin frontend (queries/runs) | Internal | 2 | `X-Admin-Token` | n/a | extend `require_admin` |
| BAT BFF | External v1 | 1 | API key | `research:read`, `research:write` | `api_keys` table or env |
| Analyst UI | External v1 | 2+ | API key | `research:read`, `companies:read` (TBD) | per-tenant keys |

**Auth behaviour**

| Mode | `DEBUG=true` | `DEBUG=false` |
|------|--------------|---------------|
| Admin cluster routes | Open | `X-Admin-Token` required on all 5 endpoints |
| External v1 | n/a | API key required; invalid/missing → `401`; wrong scope → `403` |

**Target scopes (Phase 1+)**

| Scope | Allows |
|-------|--------|
| `research:read` | GET companies, cards, runs, profile-completeness, SSE |
| `research:write` | POST research runs, cancel run |
| `discovery:admin` | Internal only — web-discovery CRUD (admin token, not API key) |

---

## What we are not doing

- Separate backend repo (unless a second team needs it later)
- Exposing web-discovery cluster CRUD on external v1
- Letting the frontend own the contract — Pydantic schemas in `apps/api` remain source of truth

*Last updated: 2026-06-22*
