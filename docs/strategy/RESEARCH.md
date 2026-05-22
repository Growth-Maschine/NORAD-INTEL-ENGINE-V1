# Research — Competitors & Optimal Build

Companion to `PLAN.md`. Two parts: who's already doing this, and what the optimal technical build looks like in 2026.

---

## Part 1 — Competitor Landscape

### 1.1 The category exists and is hot

> 86% of organizations have integrated generative AI into M&A workflows; 65% within the past year. AI is cutting deal sourcing time by up to 40%. (Deloitte 2025 M&A Gen-AI Study, Bain 2025)
>
> 82% of private capital firms now use AI for deal sourcing research (Affinity 2026 survey).

So the BAT brief isn't first — this is now table stakes for PE / corp dev. That's good news (validated demand) and bad news (must differentiate).

### 1.2 Direct competitors

| Tier | Platform | What it does | Buyer | Pricing |
|---|---|---|---|---|
| **Tier 1 — Private-company discovery** | **Grata** | NLP plain-language search over 21M+ private companies, "autopilot" signals. Acquired Sourcescrub in Aug 2025. | PE, IB, Corp Dev | Enterprise (custom, ~$25k+/yr) |
|  | **Sourcescrub** *(now Grata)* | Conference tracking, growth signals, human-verified data | PE | Enterprise |
|  | **Inven** | AI-native deal sourcing, natural-language thesis search, 23M companies / 430M contacts, 93% match accuracy claim | 900+ M&A teams | Free trial → custom |
|  | **Cyndx** | All-in-one: sourcing + valuation + benchmarking | PE/VC | Enterprise |
| **Tier 2 — Relationship intelligence** | **Affinity** | CRM + relationship graph from email/calendar, deal-flow management | VC, PE, BD | $2k–$3k/seat/yr |
|  | **4Degrees** | Lighter Affinity competitor, relationship intelligence | VC, IB | $80–$200/seat/mo |
| **Tier 3 — Reference data (the giants)** | **PitchBook** | Cap tables, valuations, fund/deal data | PE/VC/IB | ~$20k+/yr |
|  | **CB Insights** | Mosaic Score, Market Maps, predictive analytics | Corp strategy | ~$60k+/yr |
|  | **Crunchbase** | Funding rounds, broad coverage | Sales, founders | $99/mo |
|  | **Capital IQ** | Public + private data | IB | Enterprise |
| **Tier 4 — AI-native challengers** | **Hebbia** | LLM workflows over docs/data for M&A | IB, PE | Enterprise |
|  | **MADiscover** | Dynamic M&A screening, market landscaping | Corp Dev | Custom |
|  | **FifthRow** | Marketplace of "autonomous AI apps" incl. M&A target ID | Strategy/consulting | Subscription |
|  | **Conceptor.ai** | M&A target ID + analysis | Boutique IB | Custom |
|  | **Midaxo** | M&A intelligence + lifecycle | Corp Dev | Enterprise |

### 1.3 Where the BAT use case slots in (the gap)

The big platforms are built for **PE / VC / IB sourcing thousands of deals/year**. They're priced for that, they screen at portfolio scale, and they're industry-generic.

The BAT brief is different on three axes:
1. **Corp dev for one strategic acquirer**, not a fund — only ~20–50 high-conviction deals matter per year
2. **Channel-specific intelligence** (convenience + pharmacy + regulatory) — none of the big players score against retail-shelf-fit, regulatory standing, or channel synergy out of the box
3. **End-to-end through outreach**, not just sourcing — Grata/Inven hand you a list; nobody auto-drafts the first-look email + deal card

**The opportunity:** a niche-agnostic engine that *any* corp dev team configures to their own channel, rubric, and red-flag rules. Grata won't build that — it's enterprise-priced and one-size-fits-all. Inven might, but they're focused on PE.

### 1.4 What competitors do well (steal these)
- **Natural-language search** over a structured signal store (Grata, Inven)
- **"Autopilot" / saved-search signal alerts** (Grata)
- **Relationship graphs from email/calendar** (Affinity) — defensible moat
- **Conference & event tracking** (Sourcescrub) — strong leading indicator
- **Mosaic-style composite scoring** (CB Insights) — pre-built indices

### 1.5 What none of them do (your differentiation)
- **Per-tenant configurable rubric + red flags** (everyone hardcodes)
- **End-to-end through human-approved outreach + deal card**
- **Regulatory / approval signals as first-class data** (FDA, Health Canada, SEDAR+, EDGAR — most platforms only have filings as PDFs)
- **Auditable provenance to source URL + timestamp** (table stakes for compliance use cases, missing from most)

---

## Part 2 — Optimal Build Research

### 2.1 The pipeline shape (5 layers, industry standard)

```
[ Scheduler ] → [ Fetcher / Scraper ] → [ Normalizer ] → [ Resolver ]  → [ Store ]
                                                                  ↓
                                          [ Scoring ] → [ Outreach ] → [ Frontend ]
```

This matches every reference architecture I found (Scrapfly 2026, Apify 2026, Bright Data 2026, Medium / Hugo Mar 2026). Don't reinvent.

### 2.2 Per-layer optimal choice (with reasoning)

#### Scheduler / Job Orchestration
**Winner: Inngest** for v1, **Temporal** if you outgrow it.

| | BullMQ | Inngest | Temporal |
|---|---|---|---|
| Model | Redis queue | Event-driven durable functions | Workflow engine |
| Serverless-friendly | ✗ needs persistent workers | ✓ | ~ |
| Step-level retry / replay | ✗ | ✓ | ✓ |
| TS DX | Good | Excellent | Heavier |
| Self-host needed | ✓ | Optional (SaaS default) | ✓ |
| Best for | High-volume queues | Multi-step durable jobs | Mission-critical, long-running |

**Why Inngest:** your pipeline is multi-step durable workflow (fetch → normalize → resolve → score), not a high-volume queue. Inngest checkpoints each step automatically; if normalization crashes you don't re-fetch. Built TS-first.

#### Fetching / Scraping
**Composite: Firecrawl + Bright Data + Apify + Exa.** Don't build your own.

| Tool | Best at | Cost signal |
|---|---|---|
| **Exa** | Semantic web discovery (find new things) | $7/1K standard searches |
| **Firecrawl** | Single page → clean markdown for LLM | $0.0008/page |
| **Bright Data SERP** | High-volume Google/SERP at lowest cost | $1/1K results at scale |
| **Apify** | Marketplace actors (Reddit, TikTok, LinkedIn) | $0.001–0.003/post |
| **Diffbot** | Structured company-entity enrichment | $0.001/lookup |

**Plus build proprietary connectors for free, stable sources** (these are moat ingredients):
- SEDAR+ (XML), SEC EDGAR (SGML), Health Canada NHP (REST), FDA OpenFDA (REST), USPTO/CIPO (bulk).
These cost $0/call once built and are your highest-signal data.

#### Normalization
LLM-as-parser **only for unstructured** (press releases, trade articles, PDFs). Use structured-output APIs (JSON schema enforcement) — not "please return JSON." Best models for this: **GPT-4o-mini, Claude Haiku, Gemini 2.5 Flash** — pick on cost.

#### Entity Resolution
**Splink (UK Ministry of Justice, MIT) + LLM tail.** Industry-validated, scales to 10s of millions on a single machine, supports DuckDB / Spark / Athena backends. Realistic accuracy: 90–93% with a few hundred labeled training pairs. Use LLM only on the ~10% uncertain residual. Don't write your own matcher.

#### Vector DB
**pgvector on Supabase/Neon for v1.**

| | pgvector + pgvectorscale | Qdrant |
|---|---|---|
| p95 latency | 60ms | 37ms |
| Throughput @ 99% recall | **471 QPS (11.4× better)** | 41 QPS |
| Cost @ 10M vectors | ~$75/mo | ~$150/mo |
| Best for | <10M vectors, Postgres-native | >10M vectors, sub-10ms latency |

**pgvectorscale** (Tigerdata extension) actually beats Qdrant on throughput now — surprised me. Stay on Postgres until you have a real reason to leave.

#### Agent Framework (TypeScript)
**Mastra** for the v1, with an exit ramp to **LangGraph** if graphs get complex.

| | LangGraph | Mastra | OpenAI Agents SDK | Inngest AgentKit |
|---|---|---|---|---|
| Lang | Py + TS | **TS-only** | Py + TS | TS-only |
| Models | Any | **3,300+ across 94 providers** | OpenAI-only | Via Vercel AI SDK |
| Pattern | Directed graph | Workflows + agents | Lightweight ReAct | Inngest-step agents |
| Best for | Complex branching | TS-native + model-flexible | OpenAI shops | Already using Inngest |

**Mastra wins because:** TS-native (no Python gymnastics), most model providers, and integrates cleanly with Inngest. If you end up needing complex stateful graphs (e.g., multi-agent debate), LangGraph is the migration path — concepts transfer.

#### Frontend
**Next.js 15 (App Router) + TS + Tailwind + shadcn/ui.**

For a B2B dashboard:
- **Next.js**: wins if you need both marketing site + dashboard + SSR for shareable deal-card pages. Most ecosystem support, hiring is easiest.
- **Vite + React + TanStack Router**: wins for *pure* authenticated dashboards (faster dev, smaller bundle). Skip if you need any public/SSR pages.
- **Remix**: wins for data-mutation-heavy nested routes. Smaller community, narrower fit here.

**Pick Next.js** because deal cards will be shareable URLs, and SSR matters there. Use `shadcn/ui` for the design system — same components everyone good is using in 2026, fully owned (not a dependency).

#### Data Layer
- **Postgres (Supabase or Neon)** — primary store
- **pgvector** — semantic search inside Postgres
- **Redis** — cache + queue + rate-limit counters
- **Object storage (S3 / R2)** — raw scraped payloads, generated PDFs
- **Meilisearch** — keyword + faceted search across signals (cheaper than Elastic, faster to set up)

#### Observability (non-negotiable from day 1)
- **Langfuse** — LLM call tracing, cost per-call, prompt versions
- **OpenTelemetry → Grafana / Honeycomb** — service tracing
- **Cost ledger table in Postgres** — every external API call → row with $cost, attributed per-tenant per-job. This is how you price the product later.

### 2.3 Recommended final stack (one screen)

```
Frontend:    Next.js 15 + TS + Tailwind + shadcn/ui + TanStack Query + Zod
Auth:        Clerk (multi-tenant, RBAC out of box)
API:         tRPC (internal) + OpenAPI (when external consumers come)
Backend:     Node.js + TS, pnpm + Turborepo monorepo
Workers:     Inngest (durable workflows) + BullMQ (high-volume sub-queues)
Agents:      Mastra + Vercel AI SDK + MCP tool servers
Models:      Router pattern — Haiku/4o-mini/Flash for parse, Sonnet/GPT-5/Gemini Pro for reasoning
Resolution:  Splink (Python microservice) + LLM tail for ambiguous
Scraping:    Exa + Firecrawl + Bright Data + Apify + Diffbot composed
Free sources: Custom connectors for SEDAR+, EDGAR, NHP, OpenFDA, USPTO/CIPO
Data:        Postgres (Supabase) + pgvector + Redis + S3/R2 + Meilisearch
Observability: Langfuse + OpenTelemetry + Grafana + cost-ledger table
Infra:       Fly.io or Railway for containers, GitHub Actions for CI/CD
```

### 2.4 Build vs Buy decision matrix

| Capability | Build | Buy | Verdict |
|---|---|---|---|
| Source registry / scheduler | ✓ | — | Build (config-driven) |
| Web scraping at scale | $$$$ | Firecrawl/Bright Data/Apify | **Buy** until $3K+/mo on one source |
| Regulatory feeds (EDGAR/SEDAR+/NHP) | Cheap, stable | — | **Build** — moat |
| Entity resolution | Hard | Splink (free, OSS) | **Use Splink** — don't write your own |
| Vector search | Free w/ Postgres | Pinecone $$$ | **Use pgvector** |
| Agent runtime | Hard | Mastra (free, OSS) | **Use Mastra** |
| LLM tracing | Hard | Langfuse (free OSS or hosted) | **Use Langfuse** |
| CRM | $$$$ | HubSpot/Pipedrive | **Buy + integrate** |

### 2.5 Three risks to design around now

1. **Source ToS / legal exposure** — LinkedIn, Instagram, TikTok scraping has real legal risk. Use Apify managed actors (they take some liability), aggressive caching, and never store full text at scale. Gate Instagram especially.
2. **Cost runaway from agents** — every agent gets `max_steps` + `max_cost_usd`, hard fail. Tool result caching (Redis, freshness-tiered: regulatory 24h, news 1h, social 15min, enrichment 30d). This is where margin lives.
3. **Eval drift** — without a golden-query eval set per agent, you'll silently regress every prompt change. Build the eval harness in week 1, not week 30.

---

## TL;DR

**Competitors:** Grata + Sourcescrub (now one), Inven, Cyndx own the PE deal-sourcing market. Affinity owns relationship intelligence. PitchBook/CB Insights/Crunchbase are the data utilities. **None target single-acquirer corp dev with configurable rubric + end-to-end outreach** — that's the opening.

**Build:** Next.js + TS frontend → Inngest-orchestrated TS backend → Mastra agents over MCP tools → Splink + pgvector for resolution → composed scraping (Firecrawl/Apify/Bright Data/Exa) + proprietary regulatory connectors → Postgres + Redis + S3 + Meili → Langfuse + OpenTelemetry from day 1.

**Differentiate:** configurable rubric + red flags, regulatory signals as first-class data, end-to-end through approved outreach, full auditable provenance.
