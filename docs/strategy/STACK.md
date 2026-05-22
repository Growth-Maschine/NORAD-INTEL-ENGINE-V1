# Build Spec — Frontend & Backend Stack

> Companion to `PLAN.md` (architecture) and `RESEARCH.md` (competitor + tooling research).
> This document is the **concrete stack design** — every line is a decision, with the *why* attached. Designed to be picked up by a new senior engineer on day one.

---

## 0. Validation of Tools from the Source Brief

The B2B signal-aggregation blueprint nominated the following tools. I cross-checked every one against current (Q2 2026) pricing, status, and alternatives. Verdict:

| Tool from brief | Status | My call |
|---|---|---|
| **Exa AI** (semantic web search) | ✅ Pricing accurate, still best-in-class for neural search | **Keep** |
| **Firecrawl** (page → markdown) | ✅ Pricing accurate, dominant for LLM-ready extraction | **Keep** |
| **Bright Data SERP** | ✅ Cheapest at scale, pricing accurate | **Keep** |
| **Apify** (Reddit/TikTok/LinkedIn actors) | ✅ Marketplace + managed proxies, correct | **Keep** |
| **Perplexity Sonar** (grounded synthesis) | ✅ Pricing accurate | **Keep, but used sparingly** — most synthesis can be done in-house with our own retrieval + a cheaper model |
| **Diffbot KG** (entity enrichment) | ✅ Correct | **Keep** |
| **Splink** (entity resolution) | ✅ Active, MIT, UK MoJ-maintained, current version 4.x | **Keep — primary** |
| **dedupe** (Python active learning) | ✅ MIT, useful for training-data phase | **Keep — secondary** |
| **Zingg** (Spark) | ✅ Correct | **Skip until >50M records** |
| **pgvector on Supabase** | ✅ Correct, but **add `pgvectorscale`** — 11.4× throughput vs vanilla, beats Qdrant in 2026 benchmarks | **Keep + add pgvectorscale** |
| **BullMQ on Redis** | ✅ Correct for sub-queues | **Keep — for fan-out within a workflow step** |
| **Inngest / Temporal** | ✅ Correct | **Pick Inngest** for v1 (TS-native, durable steps); Temporal only if mission-critical SLAs |
| **Zod boundary validation** | ✅ Standard | **Mandatory at every external boundary** |
| **GPT-4o / Claude Sonnet** for LLM judgment | ✅ Correct, but route by task | **Use a model router** — small/cheap for parse, big for reason |
| **text-embedding-3-small** | ✅ Still best $/quality at $0.02/1M | **Keep** |
| **Apify Reddit Scraper** | ✅ Correct | **Keep** |
| **Data365** (Reddit alt) | ✅ Active | **Backup only** |
| **Brandwatch / Meltwater** (TikTok partners) | ✅ Still gating partners | **Roadmap — not v1** |

**Tools the brief did NOT mention but we should add:**

| Addition | Why |
|---|---|
| **Mastra** (TS-native agent framework) | TS-only, supports 3,300+ models, integrates cleanly with Inngest |
| **Langfuse** (LLM observability) | Trace every LLM call, cost per call, prompt versions — non-negotiable from day 1 |
| **Meilisearch** (keyword + faceted search) | Postgres FTS isn't enough for "browse signals" UX; Meili is fast, cheap, simple |
| **Clerk** (auth + multi-tenant + RBAC) | Saves 4+ weeks of identity work |
| **shadcn/ui** + Tailwind | Owned components, no UI library lock-in |
| **TanStack Query + TanStack Table** | Server-cache + the only data-grid that scales for review queues |
| **Zod + tRPC** | End-to-end type safety, single source of truth for schemas |

---

## 1. Frontend Stack

### 1.1 Choice
**Next.js 15 (App Router) + TypeScript**

### 1.2 Why this and not alternatives
| Option | Verdict |
|---|---|
| **Next.js 15** ✅ | Best ecosystem, SSR for shareable deal-card URLs, RSC for big data tables, easiest to hire for |
| Vite + React | Lighter, faster dev — but no SSR; deal cards need to be sharable links → Next wins |
| Remix | Strong for mutation-heavy nested routes; smaller community, narrower fit here |

### 1.3 Frontend tooling
| Layer | Tool | Why |
|---|---|---|
| Language | **TypeScript** | Same language as backend — share Zod schemas |
| Framework | **Next.js 15** | App Router + React Server Components |
| Styling | **Tailwind CSS** | Industry default; zero CSS files |
| UI components | **shadcn/ui** | Copied into your repo — you own them, no version churn |
| Forms | **React Hook Form + Zod** | Schemas reused from backend |
| Data fetching | **TanStack Query** | Server-state cache, retry, background refetch |
| Tables (review queue) | **TanStack Table** | Headless — pairs with shadcn |
| Charts | **Recharts** or **Tremor** | Tremor for dashboard tiles, Recharts for custom |
| State (light) | **Zustand** | Simple client store; don't reach for Redux |
| Auth | **Clerk** | SSO, RBAC, multi-tenant org switching out of the box |
| API client | **tRPC** | End-to-end types from backend with zero codegen |
| Routing | Next.js file-based | Standard |
| Testing | **Vitest + Playwright** | Unit + E2E |

### 1.4 Frontend pages (v1)
```
/                         — Marketing landing (public)
/login, /signup           — Clerk
/app                      — Authenticated shell
  /discover               — Newsfeed of signals (filter, search, save)
  /opportunities          — Scored opportunity list
    /opportunities/:id    — Detail page (signals, score, deal card preview)
  /review-queue           — Pending outreach approvals
  /sources                — Source manager (add/edit/test sources, cadence)
  /rubric                 — Rubric builder (drag weights, edit bands)
  /red-flags              — Red-flag rule editor
  /voice                  — Tone profile + email/deal-card templates
  /settings               — Approval workflow, alert tiers, integrations
  /audit                  — Audit log viewer
```

---

## 2. Backend Stack

### 2.1 Runtime & language
**Node.js 22 LTS + TypeScript** for everything except the entity-resolution service (Python, because Splink is Python).

### 2.2 Service layout
```
apps/
  web/                   — Next.js frontend
  api/                   — Fastify + tRPC HTTP server
  worker/                — Inngest workers (durable workflows)
  resolver-py/           — Python microservice wrapping Splink
packages/
  schemas/               — Zod schemas, shared client + server
  db/                    — Drizzle ORM + migrations
  agents/                — Mastra agent definitions
  mcp/                   — MCP server implementations
  connectors/            — Source connectors (per-source modules)
  scoring/               — Rubric engine (pure TS, deterministic)
  core/                  — Cost ledger, audit, config service
infra/
  docker/                — Dockerfiles per service
  terraform/             — IaC for managed services
```
Monorepo via **pnpm + Turborepo**.

### 2.3 HTTP API layer
| Layer | Tool | Why |
|---|---|---|
| HTTP server | **Fastify** | Fast, schema-first, smaller surface than Express |
| Internal API | **tRPC** | Frontend ↔ backend, zero codegen, fully typed |
| Public API (later) | **OpenAPI 3.1 via Fastify** | Generated from Zod schemas; for external consumers in Phase 5 |
| Validation | **Zod** at every boundary | Same schemas client + server |
| Auth middleware | **Clerk SDK** | JWT verification, user + org context |
| Rate limiting | `@fastify/rate-limit` + Redis | Per-tenant limits |

### 2.4 Job / workflow orchestration
**Two-tier model:**

| Tier | Tool | Purpose |
|---|---|---|
| **Durable workflows** | **Inngest** | Multi-step pipelines (fetch → normalize → resolve → score → notify). Step-level retries + replay. Cron triggers. |
| **High-volume sub-queues** | **BullMQ on Redis** | Inside one workflow step, fan out 500 page fetches with rate-limit-aware workers. |

Inngest owns the *workflow*, BullMQ owns the *fan-out within a step*. This matches the source brief and is the cleanest split.

### 2.5 Agent layer
| Component | Tool | Notes |
|---|---|---|
| Agent runtime | **Mastra** (TS) | Orchestrates plan → tool-call → reflect loops |
| Tool protocol | **Model Context Protocol (MCP)** | Each domain capability is an MCP server: `mcp-signals`, `mcp-enrichment`, `mcp-regulatory`, `mcp-social`, `mcp-scoring`, `mcp-outreach` |
| Model routing | **Vercel AI SDK** + custom router | Cheap models (Haiku, 4o-mini, Gemini Flash) for parse/classify; smart models (Claude Sonnet, GPT-5, Gemini Pro) for plan/reason |
| Embeddings | OpenAI **text-embedding-3-small** | Best $/quality |
| Tracing | **Langfuse** | Every call logged with cost, latency, prompt version |
| Guardrails | Custom | `max_steps`, `max_cost_usd`, structured-output enforcement on every agent |

**Where agents actually run** (not everywhere — judgment points only):
- **Source-Discovery Agent** — finds new sources to watch (weekly)
- **Adjudicator Agent** — entity-resolution tail (~10% of comparisons Splink can't decide)
- **Research Agent** — handles fuzzy Discovery API queries (plan → search → synthesize)
- **Justification Agent** — writes per-metric narrative on top of the deterministic score
- **Composer Agent** — drafts outreach email + deal card with reflection loop

Everything else (ingestion, normalization for structured sources, score arithmetic) is **deterministic code** — no LLM in the hot path.

### 2.6 Entity resolution service
- **Python microservice** (FastAPI) wrapping **Splink 4.x**
- Communicates with TS workers over HTTP (or gRPC if latency demands)
- Three-stage cascade as the source brief specifies: deterministic blocking → Splink probabilistic → LLM adjudicator on the uncertain ~10%
- Backed by DuckDB locally / Postgres in prod
- Active-learning UI (review-queue page) feeds labeled pairs back to Splink

### 2.7 Source connectors
Two classes of connector — both speak the same internal interface (`Connector.fetch(since: Date) → RawEvent[]`):

| Class | Approach | Examples |
|---|---|---|
| **Composed (buy)** | Wrap Exa / Firecrawl / Bright Data / Apify / Diffbot | Trade press, social, generic web |
| **Proprietary (build)** | Direct API / bulk download against stable, free sources | SEDAR+ (XML), SEC EDGAR (SGML), Health Canada NHP (REST), OpenFDA (REST), USPTO/CIPO (bulk) |

Build the proprietary ones at v1. They're zero variable cost, stable schemas, highest-signal data, and become the moat.

### 2.8 Scoring engine
Pure TypeScript, **deterministic**, no LLM:
```
score(entity, signals[], rubric, redFlags) → {
  totalScore: number
  perMetricBreakdown: Array<{ metric, raw, weight, weighted }>
  redFlagsTriggered: RedFlag[]
  bandLabel: 'Low Fit' | 'Developing' | 'Strong' | 'Elite'
}
```
The Justification Agent writes the prose *after* the deterministic score is computed.

### 2.9 Outreach generator
- Composer Agent reads tenant's voice profile + opportunity context
- Generates email draft + deal card (Markdown → HTML/PDF via `@react-pdf/renderer`)
- One self-critique pass against the tone-of-voice guidelines
- Posts to review queue — never sends until human approves

---

## 3. Data Layer

| Store | Use | Hosted on |
|---|---|---|
| **Postgres 16** | Primary OLTP — entities, events, scores, configs, users | **Supabase** (or Neon) |
| **pgvector + pgvectorscale** | Semantic dedup + similarity search | Same Postgres |
| **Redis 7** | Cache, BullMQ queues, rate-limit counters | **Upstash** or self-host |
| **Object Storage** | Raw scraped payloads, generated PDFs | **Cloudflare R2** (cheap egress) |
| **Meilisearch** | Keyword + faceted search across signals | Self-host (single binary) |

### 3.1 Schema sketch (Drizzle ORM)
```
tenants                → tenant_users, tenant_roles
tenant_configs         → versioned JSON: sources, rubric, red_flags, voice
sources                → registry of all source definitions
raw_events             → immutable raw payloads, hash-deduped
normalized_events      → canonical schema after parsing
entities               → resolved master records
entity_aliases         → known alternate names per entity
entity_links           → which raw_events belong to which entity
signals                → typed events per entity (filing, approval, mention)
scores                 → per opportunity, per rubric_version
flags                  → red-flag hits per opportunity
opportunities          → candidates that passed both filters
outreach_drafts        → generated drafts awaiting approval
deal_cards             → generated one-pagers
approvals              → approval chain + status
crm_sync_log           → outbound to HubSpot/Pipedrive/Salesforce
usage_events           → cost ledger — every external API call with $cost
audit_log              → append-only state changes
embeddings (pgvector)  → entity name + description vectors
```

---

## 4. Cross-Cutting Services

| Concern | Tool / Pattern |
|---|---|
| **Auth & multi-tenant** | Clerk (orgs = tenants) + Postgres RLS for hard isolation |
| **Secrets** | Doppler or Infisical |
| **LLM observability** | Langfuse (self-hosted or cloud) |
| **Service observability** | OpenTelemetry → Grafana Cloud (or Honeycomb) |
| **Cost ledger** | `usage_events` table — every external call attributed `tenant_id` + `job_id` + `$cost` |
| **Audit log** | `audit_log` append-only — every state change |
| **Config service** | `tenant_configs` JSON in Postgres, versioned, hot-reloaded via Redis pubsub |
| **Eval harness** | Custom — golden queries per agent, run on every prompt/model change |
| **CI/CD** | GitHub Actions → Docker → Fly.io (or Railway) blue/green |
| **IaC** | Terraform for managed services |

---

## 5. Environment & Secrets

```
# Clerk
CLERK_SECRET_KEY
CLERK_PUBLISHABLE_KEY

# Postgres (Supabase)
DATABASE_URL
DIRECT_DATABASE_URL          # for migrations bypassing pooler

# Redis (Upstash)
REDIS_URL

# Object storage
R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET

# Meilisearch
MEILI_HOST, MEILI_MASTER_KEY

# LLMs
OPENAI_API_KEY
ANTHROPIC_API_KEY
GOOGLE_API_KEY               # Gemini

# Scrapers / data
EXA_API_KEY
FIRECRAWL_API_KEY
BRIGHTDATA_API_KEY, BRIGHTDATA_ZONE
APIFY_TOKEN
DIFFBOT_TOKEN
PERPLEXITY_API_KEY

# Workflow
INNGEST_EVENT_KEY, INNGEST_SIGNING_KEY

# Observability
LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS
```

---

## 6. The Critical Decisions (one screen)

| Decision | Pick | Why |
|---|---|---|
| Frontend framework | **Next.js 15** | SSR for shareable deal-card URLs + best ecosystem |
| UI components | **shadcn/ui + Tailwind** | Owned, no lock-in |
| Auth | **Clerk** | Multi-tenant + RBAC out of box |
| Internal API | **tRPC** | End-to-end types |
| Backend runtime | **Node.js 22 + TS** | One language top-to-bottom |
| Workflow engine | **Inngest** | Durable steps, TS-native, cron + event triggers |
| Sub-queues | **BullMQ on Redis** | Fan-out within workflow steps |
| Agent runtime | **Mastra** | TS-native, model-flexible, MCP-friendly |
| Tool protocol | **MCP** | Swappable LLMs, future external consumers |
| Entity resolution | **Splink (Python service)** + LLM tail | Industry-validated, scales |
| Vector DB | **pgvector + pgvectorscale on Postgres** | 11.4× throughput in 2026, lowest cost |
| Primary DB | **Postgres 16 (Supabase)** | RLS for tenant isolation |
| Cache / queues | **Redis 7 (Upstash)** | Standard |
| Object storage | **Cloudflare R2** | Cheap egress |
| Search index | **Meilisearch** | Faceted + fuzzy, simple ops |
| Scraping | **Exa + Firecrawl + Bright Data + Apify + Diffbot** | Compose, don't build |
| Free regulatory | **Build proprietary connectors** for SEDAR+, EDGAR, NHP, OpenFDA, USPTO/CIPO | Moat ingredient |
| LLM observability | **Langfuse** | Day-1 |
| Service observability | **OpenTelemetry → Grafana** | Day-1 |
| CRM | **HubSpot / Pipedrive** via OAuth | Buy, integrate |
| Hosting | **Fly.io** (containers) + **Supabase** (DB) + **Upstash** (Redis) | Fast to ship, scales |

---

## 7. What Gets Built First (one-week chunks)

| Week | Deliverable |
|---|---|
| **1–2** | Monorepo scaffold, Clerk auth, Postgres + Drizzle, Inngest set up, observability wired |
| **3–4** | First two source connectors (one composed via Firecrawl, one proprietary against EDGAR), `raw_events` → `normalized_events` pipeline working end-to-end via Inngest |
| **5–6** | Splink resolver service + adjudicator agent on the tail, entities table populated, basic Discover page in Next.js showing real signals |
| **7–8** | Rubric engine (deterministic) + red-flag engine, Opportunities page with scored list, Source Manager + Rubric Builder UIs |
| **9–10** | Composer agent (outreach + deal card), Review Queue page, approval chain, CRM sync stub |
| **11–12** | Voice & template editor, alert tiers, audit log UI, cost-ledger UI, eval harness |
| **13+** | Hardening, customer onboarding, second-tenant proof of niche-agnostic claim |

---

## 8. Three Things to Get Right or Pay Forever

1. **Schemas as the contract.** Every external boundary parsed through Zod. One change to a Zod schema regenerates types end-to-end. This is what makes a TS monorepo worth doing.
2. **Cost ledger from row 1.** Every external call writes `usage_events` with `tenant_id`, `job_id`, `$cost`. Without this you can't price the product, you can't bill, and you can't catch runaway agents.
3. **Eval harness from week 1.** Golden queries per agent, regression-tested on every prompt or model change. Skip this and you'll silently regress every Friday afternoon for the rest of the project's life.
