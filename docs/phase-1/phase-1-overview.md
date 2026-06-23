# P1-00 — Phase 1 Overview

| Field | Value |
|-------|-------|
| **Document ref** | P1-00 |
| **Title** | Phase 1 Overview — controlling specification |
| **Version** | 1.3 |
| **Last updated** | 2026-06-22 |
| **Status** | Active — source of truth for what is **built today** |

---

## 1. Purpose

This document is the **controlling overview** for the Phase 1 product blueprint. It describes what NORAD Intel Engine actually does in the current repository (`NORAD-INTEL-ENGINE-V1`), what is out of scope, and how the numbered P1 documents relate to each other.

Older Phase 1 drafts described a **Today page**, TrendHunter categories, analyst/admin split apps, and post-run LLM steps that were **not implemented**. Those references are retired. When a child document conflicts with this overview or with the code cited in §8, **the code wins** until the child document is revised.

---

## 2. Product summary

**NORAD** is a brand-intelligence and BD deal-sourcing engine for Growth Maschine. Operators:

1. Configure **Web Discovery clusters** (themed Exa search scopes).
2. Run **queries** inside a cluster to find web articles.
3. Review **enriched results** — executive summary, companies mentioned, full article text.
4. Trigger **Deep research** on a mentioned company to produce a **Company Card** (`CompanyCardV1`).
5. Monitor research on the **Companies** page and tune engines in **Settings**.

There is **one API** (`apps/api`) and **two operator-facing web clients**:

| Client | Role | Status |
|--------|------|--------|
| `apps/web` | Legacy operator console — Web Discovery, Companies, Settings | Built in this repo |
| **GM Admin Console** (separate frontend) | Organization / user / access management | UI built — **not wired** to API yet |

There is **no analyst-only frontend** in this repo yet. Analyst users are modeled under organizations (`organization_members`) for a future analyst app.

---

## 3. What is built vs planned

### 3.1 Built (Phase 1 — current)

| Area | Route / entry | Backend |
|------|---------------|---------|
| Dashboard | `/` | `GET /health/db` for system tile |
| Web Discovery — cluster list | `/discover-web` | `GET/POST /api/web-discovery/clusters` |
| Web Discovery — cluster hub | `/discover-web/clusters/:clusterId` | cluster + queries + runs |
| Web Discovery — query editor | `.../queries/new`, `.../queries/:queryId` | `POST/PUT /api/web-discovery/queries` |
| Web Discovery — results | `.../queries/:queryId/results` | `GET /api/web-discovery/queries/:id/results` |
| Research run log | `/runs/:id` | `GET /api/research/runs/:id`, SSE `/api/events/runs/:id` |
| Companies feed | `/companies` (Profiles tab) | `GET /api/research/feed` |
| Discovered companies | `/companies` (Discovered tab) | `GET /api/research/discovered` |
| Company profile | `/companies/:id` | `GET /api/research/companies/:id`, evidence API, **`GET .../profile-completeness`** |
| Settings | `/settings` | `GET/PUT /api/settings/research`, `GET /health/db` |
| **Organizations (GM admin)** | `/dashboard/organizations` (separate frontend) | `GET/POST /api/admin/organizations`, org detail tabs — see [ORG_USER_SETUP.md](../api/ORG_USER_SETUP.md) |

**Organization admin API** (`/api/admin/organizations/*`) is **built** — migration `0012`, `X-Admin-Token` in prod. GM staff only. Analyst SSO and read-path tenant enforcement are **deferred**.

**Pipelines (both run in the API process via `asyncio.create_task` — no separate worker):**

| Pipeline | `runs.source_kind` | Service |
|----------|-------------------|---------|
| Web Discovery | `web_discovery` | `app/services/web_discovery.py` |
| Deep Research | `research` | `app/services/research.py` |

**Persistence:**

| Table | Role |
|-------|------|
| `web_discovery_clusters` | Themed search scope (keywords, geography, priorities) |
| `web_discovery_queries` | One Exa search definition per cluster |
| `articles` | Deduplicated article store — `body_text`, Sonnet `summary`, `mentioned_companies` (each with `company_id` after enrich) |
| `runs` | One row per cluster/query run or research run |
| `run_events` | Append-only timeline (powers SSE Activity feeds) |
| `engine_calls` | Per-vendor request/response audit (cost, latency, JSONB payloads) |
| `companies` | Web Discovery mentions (`origin=web_discovery`) **and** Deep Research profiles (`origin=research`) |
| `cards`, `sources` | Deep research output (linked via `companies.canonical_card_id`) |
| `card_profile_parameters` | 44 must-have profile completeness rows per card — materialized at persist |
| `app_kv` | Research engine settings (`research_config`) |
| `organizations` | Customer tenant — name, domain, status |
| `organization_members` | Analyst users under an org (`staff` \| `manager`) |
| `organization_invites` | Pending invite before member row exists |
| `organization_api_keys` | Per-org integration key for analyst frontend (hashed at rest) |
| `organization_clusters` | M2M — which clusters an org can access |
| `organization_companies` | M2M — which companies belong to an org (**exclusive**: one company → one org) |
| `organization_auth_config` | SSO / MFA policy toggles (schema-first) |
| `organization_audit_events` | Org-scoped audit trail (Activity tab) |

**Database:** GCP Cloud SQL Postgres (`GCP_DATABASE_URL*`). Not Supabase.

**Cache:** Redis (`REDIS_URL`) is **optional** — used only for `/health/db` connectivity probe.

### 3.2 Sidebar — Phase 2 (UI shell only)

| Label | Route | Status |
|-------|-------|--------|
| Signals | `/signals` | Nav item marked **Soon** — no route, no API |
| Feeds | `/feeds` | Nav item marked **Soon** — no route, no API |

### 3.3 Retired (do not document as current behaviour)

| Removed | Notes |
|---------|--------|
| **Today page** | `/today`, Discover feed, trend articles UI |
| **`trend_articles` table** | Dropped in `sql/0007_drop_today_legacy.sql` |
| **`discovery_clusters` table** (legacy) | Old Today taxonomy; dropped in 0007 |
| **TrendHunter category picker** | `categories.py` removed |
| **arq background worker** | Pipelines run in-process; `Procfile` is API-only |
| **`signals` table** | Dropped in `sql/0011_drop_signals.sql` — BD signals/scores not persisted |
| **Fit scores / recommended actions in synthesis** | Stripped from Deep Research — future frontend owns BD layer |
| **`GET /brands`** | Placeholder removed |
| **Analyst-only app** | Single legacy app serves operator workflows; analyst app is separate (future) |

---

## 4. Web Discovery pipeline (minute detail)

**Trigger:** `POST /api/web-discovery/clusters/:clusterId/runs`

- Body `{}` → run **all active queries** in the cluster (batch).
- Body `{ "query_id": "<uuid>" }` → run **one query** only.

**Admission:** Max **5** in-flight runs where `source_kind = web_discovery` and `status ∈ {queued, researching, synthesizing}`.

**Per active query (sequential across queries in one run):**

| Step | What happens | Persisted |
|------|--------------|-----------|
| 1. Exa search | Search + optional contents (`content_highlights`, `content_text`, `content_summary` on query) | `engine_calls` (vendor `exa`) |
| 2. Dedup | Normalize URL; skip if `articles.url` already exists | `ingest_status: duplicate` on hit |
| 3. Consolidate | New hit → `articles` row with `body_text` (from Exa text, else joined highlights/snippet) | `articles` |
| 4. Sonnet enrich | Claude Sonnet `analyze_article` tool — executive summary + `mentioned_companies` | `articles.summary`, `articles.mentioned_companies` (with `company_id` per mention); **`companies` rows** (`origin=web_discovery`, FK `source_article_id`); mirrored in `runs.engine_outputs` |
| 5. Complete | Run `status → completed`, `engine_outputs.queries[]` holds per-query results | `runs` |

**Sonnet enrich:** Fixed system prompt + tool schema in `web_discovery.py`. Query-level `system_prompt` / `output_schema` fields on `web_discovery_queries` are **saved in DB but not executed** in this pipeline.

**Concurrency:** Up to **4** articles enriched in parallel per query (`ENRICH_CONCURRENCY = 4`).

**Results UI** (`WebDiscoveryQueryResults.tsx`) per source card:

| Block | Source |
|-------|--------|
| Executive summary | `articles.summary` (via results API hydration) |
| Companies in this story | `articles.mentioned_companies` (includes `company_id`) |
| **Deep research** button | Per company → `POST /api/research/runs` with optional `company_id` |
| Full article (collapsible) | `articles.body_text` (cleaned for display) |
| Source excerpts (Exa) | Shown **only** when no executive summary exists |

**Not implemented on results UI:** article-level Save, Dismiss, or Escalate buttons. `POST /api/web-discovery/articles/:id/dismiss` exists in API but has no frontend caller yet.

---

## 5. Deep Research pipeline (summary)

**Trigger:** `POST /api/research/runs` with `{ company_name, domain_hint?, company_id? }`

Typical entry from Web Discovery or **Companies → Discovered**: **Deep research** passes `company_id` when the mention row already exists.

**Admission:** Max **5** in-flight `source_kind = research` runs.

| Stage | Engines | Output |
|-------|---------|--------|
| 1 — Input | App | Company name, optional domain hint |
| 2 — Fan-out | Parallel + Exa + Diffbot (partial failure tolerated) | Structured brief + web content + entity graph |
| 3 — Synthesize | Claude Sonnet | `CompanyCardV1` fact blocks + `sources_and_confidence` (+ optional `strategic_fit.fit_summary`) |
| 4 — Persist | App | `companies`, `cards`, `sources`, `card_profile_parameters` |

Settings (`/settings`) affect **research only** — Parallel processor, Exa search type, Diffbot toggle/threshold. Stored in `app_kv.research_config`.

Full stage behaviour: `docs/backend-pipeline.md` and P1-01-Admin §3.

---

## 6. Navigation map

```
Sidebar
├── Dashboard          /
├── Web Discovery      /discover-web
│   ├── Cluster hub    /discover-web/clusters/:clusterId
│   ├── Query editor   .../queries/new | .../queries/:queryId
│   └── Results        .../queries/:queryId/results
├── Companies          /companies (Profiles | Discovered tabs) | /companies/:id
├── Signals (soon)     /signals — not wired
├── Feeds (soon)       /feeds — not wired
└── Settings           /settings

Run log (any pipeline) /runs/:id
```

---

## 7. Document register

Documents are maintained in order. **P1-00 (this file) is authoritative for scope.** Workflow detail lives in P1-01; object definitions in P1-02; etc.

| Ref | File | Subject | Status |
|-----|------|---------|--------|
| **P1-00** | [phase-1-overview.md](./phase-1-overview.md) | Controlling overview | **v1.3 — this document** |
| P1-01-Admin | [P1-01-admin.md](./P1-01-admin.md) | Operator workflows | v3.1 — revised 2026-06-16 |
| P1-01-User | [P1-01-user.md](./P1-01-user.md) | Analyst workflows (same app) | v2.1 — revised 2026-06-16 |
| P1-02-Admin | [P1-02-admin.md](./P1-02-admin.md) | Operator product objects | v2.2 — org tables added 2026-06-22 |
| P1-02-User | [P1-02-user.md](./P1-02-user.md) | Analyst product objects | v2.2 — org model added 2026-06-22 |
| P1-03 | [P1-03.md](./P1-03.md) | Object relationships | v2.2 — org scoping 2026-06-22 |
| P1-04-Admin | [P1-04-admin.md](./P1-04-admin.md) | Required fields | v3.3 — migration `0012`; **19 live tables** |
| P1-05-Admin | [P1-05-admin.md](./P1-05-admin.md) | Operator UI mapping | v2.2 — GM admin console screens 2026-06-22 |
| P1-05-User | [P1-05-user.md](./P1-05-user.md) | Analyst UI mapping | v2.1 — revised 2026-06-16 |
| P1-06 | [P1-06.md](./P1-06.md) | Backend actions | v2.2 — org admin APIs 2026-06-22 |
| — | [phase2test.md](./phase2test.md) | SQL acceptance tests | Legacy — includes Phase 2 tables (`article_signals`, watchlist) not in current repo; use with P1-04 §3.6 |

**Revision order (agreed):** P1-00 → P1-01-Admin + P1-01-User (paired) → P1-02 → … → P1-06.

**P1-01 pairing:** Admin §2 configures/runs Web Discovery; User §2 reads enriched results. Both §3 cover Deep research. Master end-to-end diagram: [P1-01-User §8](./P1-01-user.md).

---

## 8. Canonical code references

When verifying behaviour, use these files first:

| Concern | Path |
|---------|------|
| Frontend routes | `apps/web/src/App.tsx` |
| Sidebar nav | `apps/web/src/components/layout/Sidebar.tsx` |
| API client | `apps/web/src/lib/api.ts` |
| Web Discovery orchestration | `apps/api/app/services/web_discovery.py` |
| Web Discovery HTTP | `apps/api/app/routers/web_discovery.py` |
| Research orchestration | `apps/api/app/services/research.py` |
| Research HTTP | `apps/api/app/routers/research.py` |
| **Organization admin HTTP** | `apps/api/app/routers/admin_organizations.py` |
| Organization service | `apps/api/app/services/organizations.py` |
| ORM models | `apps/api/app/models/` |
| DDL | `apps/api/sql/` (apply with `norad_migrate` via `psql` or psycopg — see [ORG_USER_SETUP.md](../api/ORG_USER_SETUP.md)) |
| Legacy signals/scores reference | `docs/reference/legacy-signals-scores-suggestions.md` |
| Pipeline field guide | `docs/backend-pipeline.md` |

---

## 9. Approval

| Role | Name | Date |
|------|------|------|
| Author | Huzaifa | 2026-06-19 |
| Reviewer | — | — |
