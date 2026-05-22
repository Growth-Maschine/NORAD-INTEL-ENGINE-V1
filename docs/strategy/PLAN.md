# BD Intelligence Engine — Technical Plan

> A configurable, niche-agnostic deal-sourcing engine. Continuously watches public sources, deduplicates and scores opportunities against a per-tenant rubric, kills hard red flags, and drafts ready-to-review outreach for whatever survives.

---

## 1. Product Shape

Three things, exposed as APIs and as a UI:

| Surface | What it does |
|---|---|
| **Discovery** | Find new opportunities matching a tenant's filters. |
| **Screening** | Score an opportunity against a configurable weighted rubric + red-flag rules. |
| **Outreach** | Draft a personalized email + one-page deal card for human approval. |

Everything **configurable per tenant**: source list, refresh cadence, rubric metrics & weights, red-flag triggers, score threshold, alert tiers, tone-of-voice, deal-card template, approval workflow.

---

## 2. Architecture at a Glance

```
Frontend (React + Vite + TS)
        │
        ▼
API Gateway (auth · rate limit · tenant routing)
        │
        ▼
Application Services  ── Discovery · Screening · Outreach · Config · CRM Sync
        │
        ▼
Agent Orchestration   ── Research · Adjudicator · Composer · Source-Discovery
        │
        ▼
MCP Tool Servers      ── signals · enrichment · regulatory · social · scoring · templates
        │
        ▼
Engine Core           ── Source Registry · Scheduler · Ingestion · Normalize · Entity Resolution
        │
        ▼
Data Layer            ── Postgres · pgvector · Redis · Object Storage · Search Index
        │
        ▼
External Sources      ── Regulatory · Filings · Trade press · Patents · Social · Distributors
```

Cross-cutting: **Observability**, **Cost Ledger**, **Audit Log**, **Config Service**, **Secrets Vault**.

---

## 3. Tech Stack

### Frontend
| Layer | Choice | Why |
|---|---|---|
| Framework | **React 18 + Vite + TypeScript** | Fast DX, mature ecosystem |
| Styling | **Tailwind + shadcn/ui** | Senior-grade components without bespoke CSS |
| State / data | **TanStack Query + Zustand** | Server-cache + light client state |
| API | **tRPC** (or OpenAPI client) | End-to-end types for our own services |
| Forms | **React Hook Form + Zod** | Same schemas as backend |
| Auth | **Clerk** or **Auth.js** | SSO, RBAC, multi-tenant out of the box |
| Charts | **Recharts** + **TanStack Table** | Dashboards & queues |

### Backend Engine
| Layer | Choice | Why |
|---|---|---|
| Runtime | **Node.js + TypeScript** (monorepo via pnpm + Turborepo) | One language top-to-bottom |
| API | **Fastify + tRPC** (or NestJS if team prefers) | Schema-first, fast |
| Validation | **Zod** everywhere | Single source of truth for shapes |
| Queue / workers | **BullMQ on Redis** | Rate-limit-aware, retries, fan-out |
| Durable workflows | **Inngest** (or Temporal) | Multi-step ingestion pipelines, retries |
| Agents | **Mastra** | TS-native agent framework |
| Tool protocol | **MCP** servers per domain | Swappable LLMs, future external consumers |
| LLM access | **Vercel AI SDK** + model router | Cheap/small for parse, big for reason |
| Entity resolution | **Splink** (Python microservice) + LLM tail | Proven at scale |
| Search | **Postgres FTS + Meilisearch** | Faceted + fuzzy |
| Scrape orchestration | Compose **Exa, Firecrawl, Bright Data, Apify, Diffbot, Perplexity** | Buy before build until volume justifies |

### Data
| Store | Use |
|---|---|
| **Postgres** (Supabase or Neon) | Entities, events, scores, tenants, configs |
| **pgvector** | Semantic dedup + similarity |
| **Redis** | Cache, queues, rate-limit counters |
| **Object storage** (S3 / R2) | Raw scraped payloads, generated PDFs |
| **Meilisearch** | Keyword + faceted search across signals |

### Cross-Cutting
- **Observability**: Langfuse (LLM traces) + OpenTelemetry + Grafana
- **Cost Ledger**: every external API call written to a `usage_events` table with $cost, attributed per-tenant per-job
- **Audit**: every signal traces to source URL + fetched_at
- **Config Service**: per-tenant JSON configs versioned in Postgres, hot-reloaded
- **Secrets**: Doppler / Infisical / cloud-native secret manager

### Infra
- **Hosting**: containerized services on Fly.io, Railway, or AWS ECS
- **CI/CD**: GitHub Actions → blue/green deploys
- **IaC**: Terraform for managed services

---

## 4. The Configurability Surface

This is the product moat. Every item below is **tenant-configurable via UI or API**:

| Config | Stored as | UI |
|---|---|---|
| Source list (which to watch, cadence, auth) | `tenant_sources` table | Source Manager screen |
| Rubric (metrics, weights, thresholds 1–20 bands) | `tenant_rubrics` (JSON, versioned) | Rubric Builder (drag weights) |
| Red-flag rules (regex / structured triggers) | `tenant_red_flags` | Red-Flag Editor |
| Score threshold + alert tiers (urgent/watch/archive) | `tenant_thresholds` | Settings |
| Outreach tone profile + email template | `tenant_voice_profile` (markdown + JSON) | Voice & Templates |
| Deal-card template (sections, branding) | `tenant_card_template` | Template Editor |
| Approval workflow (single / dual / role-based) | `tenant_approval_chain` | Workflow Settings |
| CRM destination (HubSpot, Pipedrive, Salesforce) | OAuth + field map | Integrations |

Rule: **no business logic is hardcoded** — every filter, weight, and template is data, not code.

---

## 5. Where Agents Live (and where they don't)

| Stage | Approach | Why |
|---|---|---|
| Source registry | **Source Discovery Agent** (weekly, ReAct) | Find new sources to watch |
| Ingestion | Pure workers, no LLM | Stable plumbing |
| Normalization | LLM-as-parser **only for unstructured** | Structured outputs, no agent loop |
| Entity resolution | Splink first, **Adjudicator Agent** on uncertain tail (~10%) | Cheap until needed |
| Discovery query | **Research Agent** (plan → tool-call → synthesize) | Genuine reasoning over signals |
| Screening | Deterministic rubric apply, **Justification Agent** writes narrative | Numbers stay reproducible |
| Outreach | **Composer Agent** with reflection loop | Tone + context-aware drafting |

Guardrails on every agent: max steps, max $ per call, structured outputs, tool-result caching, full trace.

---

## 6. Data Model (high-level)

```
tenants ──┬── tenant_sources
          ├── tenant_rubrics (versioned JSON)
          ├── tenant_red_flags
          ├── tenant_voice_profile
          └── tenant_users / tenant_roles

sources ──── raw_events ──► normalized_events ──► entities ──► entity_links
                                                      │
                                                      ├── signals (typed events per entity)
                                                      ├── scores (per rubric_version)
                                                      ├── flags (red-flag hits)
                                                      └── embeddings (pgvector)

opportunities ──┬── outreach_drafts
                ├── deal_cards
                ├── approvals (chain + status)
                └── crm_sync_log

usage_events  ── per external API call (tenant, job, $cost)
audit_log     ── append-only, every state change
```

---

## 7. API Surface (sketch)

```
POST /v1/discovery/search           # filters → ranked opportunities
POST /v1/discovery/watch            # save as standing query
GET  /v1/opportunities/:id

POST /v1/screening/score            # entity_id + rubric_version → scored result
GET  /v1/screening/red-flags/:id

POST /v1/outreach/generate          # opportunity_id → draft email + deal card
POST /v1/outreach/:id/approve
POST /v1/outreach/:id/send

GET  /v1/config/sources
PUT  /v1/config/rubric
PUT  /v1/config/red-flags
PUT  /v1/config/voice
```

All multi-tenant, all schema-validated, all logged to audit.

---

## 8. Phased Build Plan

| Phase | Weeks | Deliverable |
|---|---|---|
| **0 — Foundations** | 1–2 | Monorepo, auth, multi-tenant scaffolding, Postgres + Redis, observability |
| **1 — Engine v0** | 3–6 | Source registry, ingestion workers, normalization, entity resolution, signal store. **CLI-only**, prove it ingests cleanly. |
| **2 — Screening + Discovery API** | 7–9 | Rubric engine, red-flag engine, search API, basic UI for browsing signals |
| **3 — Outreach + Approval** | 10–12 | Composer agent, deal-card generator, review queue UI, approval chain, CRM sync |
| **4 — Configurability UI** | 13–15 | Source Manager, Rubric Builder, Red-Flag Editor, Voice & Templates |
| **5 — Hardening** | 16+ | Cost ledger UI, alert tiers, evals harness, customer onboarding |

First customer (BAT) goes live at end of Phase 4. Niche-agnostic claim becomes provable when a 2nd tenant ships with zero engine changes — only config.

---

## 9. Critical Non-Negotiables

1. **Everything is per-tenant config, never hardcoded.**
2. **Human-in-the-loop on every outbound.** Engine drafts; humans send.
3. **Full audit trail** — every signal links to its source + fetch timestamp.
4. **Cost ledger from day 1** — you can't price what you can't measure.
5. **Eval harness from day 1** — golden queries per agent, regression-tested on every prompt/model change.
6. **Cache aggressively.** Freshness-tiered: regulatory 24h, news 1h, social 15min, enrichment 30d. This is where margin lives.

---

## 10. Open Decisions (need a call)

- Multi-tenant model: **shared schema with `tenant_id`** (cheaper) vs **schema-per-tenant** (stricter isolation).
- Self-host vs managed Postgres / Redis / vector.
- Build proprietary scrapers for free regulatory sources (EDGAR, SEDAR+, NHP) **at v1** for moat — or defer to Phase 5.
- Mastra vs LangGraph for agent runtime (Mastra recommended for TS-native fit).
- tRPC vs OpenAPI for the public API (tRPC for our own UI; OpenAPI when we expose to external consumers).
