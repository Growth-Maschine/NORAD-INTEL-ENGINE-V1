# NORAD 1 — Project Blueprint

**Audience:** Internal builder reference
**Date:** April 2026
**Status:** Locked plan for v1 build (BAT use case)

---

## 1. The BAT Use Case in One Page

**Problem.** BAT's BD team manually scans regulatory filings, trade press, patents and distributor news to find emerging convenience-store and pharmacy-retail brands worth acquiring or partnering with. The work is slow, inconsistent across analysts, and most signals are missed because no human can read every newsletter, every NHP licence change, and every patent filing in two countries.

**What NORAD does.** Twice a day, NORAD pulls public signals from regulatory databases, public filings, patents, and trade press across Canada and the US. It cleans them up, links every signal to the right company, scores every company against BAT's acquisition rubric, removes the regulatory red flags, and produces a small ranked list of acquisition or partnership targets.

**Who uses it.** BAT's BD analysts and BD leadership. Marketing approves the outreach copy.

**What they get.**

- A live **Discover** feed of every signal, with source URL and date.
- A ranked **Opportunities** list of scored companies (0–100, 5-metric breakdown, plain-English justification, red flags called out).
- An **auto-filled deal card** (one-page PDF) per opportunity.
- A **draft outreach pack** (subject + opener + talking points) for the analyst to finalise.
- A **Review Queue** where every outbound message is approved by a human before it leaves the system.

**Hard rules.**

1. Nothing sends automatically. Every email is human-approved.
2. Every signal links back to its public source.
3. Every score has an auditable reason.
4. Multi-tenant from day one — BAT is the first tenant, not the only one.

---

## 2. Core Tools — What, Why, and Indicative Cost

> Pricing below is **indicative as of April 2026**, pulled from each vendor's published pricing page. Final cost depends on negotiated volume tier. v1 estimates assume one tenant (BAT) and modest discovery volume (~5K–20K external API calls per day).

### 2.1 Frontend — what BAT's analysts actually click on

| # | Tool | Role | Why this and not alternatives | Indicative cost (v1) |
|---|---|---|---|---|
| 1 | **Next.js 15** (App Router) | Frontend framework | Server-side rendering means deal-card URLs are shareable; React Server Components scale to large signal tables; biggest hiring pool. Vite has no SSR; Remix is smaller community. | Included with Vercel |
| 2 | **TypeScript** | Language end-to-end | Same language as backend → schemas are shared, no drift between client and server. | Free |
| 3 | **Tailwind CSS + shadcn/ui** | Styling + UI components | shadcn copies components into the repo (no library lock-in); Tailwind is industry default. | Free |
| 4 | **Clerk** | Auth, multi-tenant orgs, RBAC | Saves 4+ weeks of identity work; orgs map directly to tenants. | **$0/mo** (free up to 50K MAU; $25/mo Pro after) |
| 5 | **tRPC** | Internal typed API | End-to-end types between frontend and backend, zero codegen. | Free |

### 2.2 Backend — the engine

| # | Tool | Role | Why | Indicative cost (v1) |
|---|---|---|---|---|
| 6 | **Node.js 22 LTS + TypeScript** | Runtime | One language top-to-bottom; massive ecosystem. | Free |
| 7 | **Fastify** | HTTP server | Faster, smaller, schema-first compared with Express. | Free |
| 8 | **Drizzle ORM** | Database access | TypeScript-native, no runtime overhead, no surprise migrations. | Free |
| 9 | **Inngest** | Durable workflow engine | Step-level retries, replay, cron + event triggers, TypeScript-native. The right tool for "fetch → clean → resolve → score → notify" pipelines. | **$0/mo** (free tier: 50K function runs/mo); **$20/mo Basic** later |

### 2.3 AI / Agent layer (used at only 2 sites)

| # | Tool | Role | Why | Indicative cost (v1) |
|---|---|---|---|---|
| 10 | **Mastra** | TypeScript agent framework | Built on Vercel AI SDK; designed for production agents with memory + workflows; pure TS so it lives in the same monorepo. | Free (open source) |
| 11 | **OpenAI GPT-4o-mini** | The only LLM — used for the unstructured-doc parser (Stage 3) and the score justification writer (Stage 6) | Best $/quality on the market in its tier. We don't need a frontier model for these two narrow jobs. | **$0.15 / 1M input tokens, $0.60 / 1M output tokens.** Estimated **~$30–100/mo at v1 volume** |
| 12 | **OpenAI text-embedding-3-small** | Embeddings for semantic name matching | Best $/quality; same vendor → one API key, one billing relationship. | **$0.02 / 1M tokens** → ~$5/mo at v1 volume |

### 2.4 Entity Resolution — the hardest data problem in the system

| # | Tool | Role | Why | Indicative cost (v1) |
|---|---|---|---|---|
| 13 | **Splink** (Python microservice) | Probabilistic record linkage — figures out that "Northern Wellness Inc", "Northern Wellness LLC" and "NorthernWell" are the same company | Industry-validated (UK Ministry of Justice maintainer), MIT licence, scales to tens of millions of records. The right tool for this exact job. | Free (open source); ~$10–30/mo of Fly.io compute to run it |
| 14 | **pgvector + pgvectorscale** (inside Postgres) | Vector similarity for semantic name matching | 11.4× throughput vs vanilla pgvector; lives inside Postgres so no second database to operate. | Free (extension of Postgres) |

### 2.5 Data stores

| # | Tool | Role | Why | Indicative cost (v1) |
|---|---|---|---|---|
| 15 | **Postgres 16 on Supabase** | Primary OLTP database — entities, events, scores, configs, users | Supabase gives us managed Postgres + RLS for hard tenant isolation + storage + auth-friendly. Scales cleanly. | **$25/mo Pro** (8 GB DB included) |
| 16 | **Redis 7 on Upstash** | Cache, queues (BullMQ), rate-limit counters | Pay-per-use, no idle cost, serverless. Avoids managing a Redis box. | **$5–20/mo PAYG** at v1 volume ($0.20 per 100K commands) |
| 17 | **Cloudflare R2** | Object storage for raw scraped payloads + generated PDFs | **Zero egress fees** (huge over time vs S3), $0.015/GB/mo storage, 10 GB free. | **~$5/mo** at v1 volume |

### 2.6 Bought source connectors — the four "outside-world" tools

| # | Tool | Role | Why | Indicative cost (v1) |
|---|---|---|---|---|
| 18 | **Exa** | Semantic web search — *"find me URLs about emerging Canadian functional-beverage launches in the last 7 days"* | AI-native search engine; understands meaning not just keywords. Replaces months of building our own crawler. | **$7 per 1,000 searches** (1K free/mo) → ~$10–50/mo at v1 |
| 19 | **Firecrawl** | URL → clean markdown. Handles JavaScript-rendered pages, login walls, dynamic content. | Without it we'd parse raw HTML soup. The dominant tool for LLM-ready extraction. | **$83/mo Standard** (100K pages/mo) — recommended for production fan-out |
| 20 | **Bright Data SERP API** | High-volume Google searches — *"Northern Wellness Inc news 2026"* | Cheapest at scale; failed requests aren't billed. Different job from Exa: returns Google's actual ranking, not semantic discovery. | **$1.80–$3.00 per 1K requests** → ~$10–50/mo at v1 (Micro plan with $10/mo commit) |
| 21 | **Diffbot Knowledge Graph** | Company entity enrichment — give it a name, get back HQ, size, founders, web presence, product line | Pre-built, structured, instantly fills in the metadata we'd otherwise scrape. | **$299/mo Startup** (250K credits/mo) |

### 2.7 Built-in source connectors — free and high-signal

These are not products we pay for — they are public APIs / bulk downloads we wrap in our own connector code. They become the **moat** of the system because no one else bothers to build them.

| # | Source | Country | Data | Cost |
|---|---|---|---|---|
| 22 | **Health Canada NHP** | CA | Natural Health Product approvals, licence changes, Notices of Non-Compliance | Free public REST API |
| 23 | **OpenFDA** | US | GRAS, NDI, OTC monograph status, Warning Letters, Import Refusals | Free public REST API |
| 24 | **SEDAR+** | CA | Public-company filings | Free XML download |
| 25 | **SEC EDGAR** | US | S-1, 10-K, 8-K, M&A disclosures | Free SGML feed |
| 26 | **USPTO + CIPO** | US + CA | Patent filings (formula tech, packaging IP, brand IP) | Free bulk download |

### 2.8 Outbound — what leaves the system

| # | Tool | Role | Why | Indicative cost (v1) |
|---|---|---|---|---|
| 27 | **SendGrid** | Email send for human-approved outreach | Mature, reliable deliverability, generous quota. | **~$20/mo Essentials** (50K emails/mo) |
| 28 | **HubSpot** | CRM sync (analyst → CRM) | Enterprise standard; free CRM tier covers 1M contacts. Integration itself is free. | **$0/mo** (uses BAT's existing HubSpot account; free CRM tier) |
| 29 | **React-PDF** | Generate the one-page deal card | Pure React, no headless browser to operate, deterministic output. | Free |

### 2.9 Observability + secrets + hosting

| # | Tool | Role | Why | Indicative cost (v1) |
|---|---|---|---|---|
| 30 | **Langfuse** | LLM tracing — every model call logged with cost, latency, prompt version | Non-negotiable from day 1. Without it, agent regressions go silent. | **$29/mo Core** (100K units/mo, unlimited users) |
| 31 | **Doppler** | Secrets vault | Free for 3 users; clean SDK; no rotating env files in repo. | **$0/mo** (free tier) |
| 32 | **Vercel** | Frontend hosting (Next.js) | Built for Next.js, edge network, painless deploys. | **$20/mo Pro** (1 seat, $20 usage credit included) |
| 33 | **Fly.io** | Backend container hosting (api, worker, resolver-py) | Pay-per-second, runs containers globally, no AWS-tax learning curve. | **~$30–60/mo** at v1 (3 small machines + storage + bandwidth) |

---

## 3. Indicative Monthly Cost Summary (v1, one tenant)

| Bucket | Monthly cost (low end → high end) |
|---|---|
| AI (LLM + embeddings) | $35 – $105 |
| Bought source connectors (Exa + Firecrawl + Bright Data + Diffbot) | $402 – $482 |
| Data stores (Supabase + Upstash + R2) | $35 – $50 |
| Outbound (SendGrid; HubSpot integration is free) | $20 |
| Observability + secrets (Langfuse + Doppler) | $29 |
| Hosting (Vercel + Fly.io) | $50 – $80 |
| Auth (Clerk free tier under 50K MAU) | $0 |
| Workflow engine (Inngest free tier) | $0 |
| **Total at v1 scale** | **~$570 – $770 / month** |

**At second-tenant onboarding:** add ~$50–150/mo per tenant (mostly variable Diffbot + Exa usage). The fixed costs (hosting, auth, observability) are amortised.

---

## 4. Why Perplexity Sonar API Is **Not** in v1 (and When It Earns Its Slot)

**What Sonar does:** Sonar is a "ask a natural-language question, get a grounded answer with citations" service. Pricing: $1/$1 per 1M tokens (Sonar base), $3/$15 per 1M tokens (Sonar Pro).

**Why it's not in v1.** We already produce the same outcome by composing tools we have:

```
Exa (find URLs) → Firecrawl (extract clean text) → GPT-4o-mini (synthesise + cite)
```

That stack gives us:

- Full control over the prompt and output schema (Sonar's output is opaque).
- Lower per-call cost at our volume (Sonar Pro output is $15/1M vs GPT-4o-mini at $0.60/1M).
- Visibility into every retrieved source (we own the URL list; Sonar surfaces citations but doesn't let us audit the retrieval step).

**When Sonar earns a slot.** Phase 2, when we add a **Natural Language Search (NLS)** feature on the Discover page — *"show me emerging functional beverage brands with regulatory tailwind in Quebec"* — and we want a synthesised, cited answer back without writing the orchestration ourselves. Sonar saves us 2–4 weeks of agent-glue code for that one feature.

**Verdict:** Phase 2 add-on, not v1. Estimated added cost: **~$50–200/mo** depending on NLS adoption.

---

## 5. The Sweet Spot — How NORAD Extends Beyond BAT

The whole system is designed around one principle: **BAT is the first tenant, not the only one.** Adding more sources, more tools, and more niches later is configuration and connector work, not a re-architecture.

### 5.1 The 3-layer architecture that makes this possible

```
┌────────────────────────────────────────────────────┐
│ TENANT-SPECIFIC CONFIG (JSON in database)          │
│ Sources · Rubric · Red flags · Voice · Workflow    │   ← edited daily, by users
├────────────────────────────────────────────────────┤
│ DOMAIN ADAPTERS (pluggable code modules)           │
│ Source connectors · Scrapers · AI providers · CRMs │   ← changes monthly, by devs
├────────────────────────────────────────────────────┤
│ ENGINE CORE (rarely touched)                       │
│ Pipeline · Resolver · Scoring math · Workflows     │   ← changes quarterly
└────────────────────────────────────────────────────┘
```

### 5.2 Adding a new source (e.g. Statistics Canada, CRA charity DB, job postings)

Every source implements one interface:

```ts
interface Connector {
  fetchSince(date: Date): Promise<RawEvent[]>;
}
```

**One new file. 50–200 lines. No engine changes.** The source then appears automatically in the Source Manager UI for tenants to toggle on/off.

### 5.3 Adding a new tool (e.g. swap GPT-4o-mini for Gemini Flash, or Firecrawl for a successor)

The system uses an adapter pattern at every external boundary. Swap one config / one adapter file. The agents and pipelines don't know or care which model is behind them.

### 5.4 Adding a new niche (e.g. fintech VC firm, pharma corp dev, healthcare scout)

**None of the niche-specific logic is in code.** It all lives in per-tenant configuration:

| What's niche-specific | Where it lives |
|---|---|
| Which sources to monitor | `tenant_configs.sources` (JSON) |
| Rubric weights & metric definitions | `tenant_configs.rubric` (JSON) |
| Red-flag rules | `tenant_configs.red_flags` (JSON) |
| Tone of voice for outreach | `tenant_configs.voice` (JSON) |
| Approval workflow chain | `tenant_configs.approval_workflow` (JSON) |

**Onboarding a new tenant = a few hours of config work in the UI. Zero engineering work** (assuming the source library already covers their niche).

### 5.5 Future tools and sources we can plug in later

| Category | Future additions (not v1) |
|---|---|
| Social signals | LinkedIn (exec moves), Reddit (community discovery), TikTok / Instagram (DTC brand discovery) |
| Discovery breadth | Trade-show attendee lists, conference speaker lists, job postings (Greenhouse / Lever) |
| Web intelligence | SimilarWeb (traffic), Wappalyzer (tech stack) |
| AI capability | Perplexity Sonar (NLS), Claude / GPT-5 routing for complex synthesis, vision models for label scanning |
| CRM | Salesforce, Pipedrive (alongside HubSpot) |
| Distributor data | UNFI portal, KeHE portal, McKesson (often gated → partnership required) |
| Analyst overlays | Crunchbase, PitchBook (M&A history), Owler (private-co revenue estimates) |

Each one slots in via the same Connector interface. No re-architecture.

---

## 6. What Is Deferred (and Why That's a Choice, Not an Oversight)

| Deferred to | Why deferred |
|---|---|
| **LinkedIn / Reddit / Trade-show data** → Phase 2 | Legally tricky and/or requires Bright Data residential or Phantombuster; bigger engineering and compliance lift. Source coverage is good enough for v1 with regulatory + filings + patents + trade press. |
| **Perplexity Sonar (NLS)** → Phase 2 | We already do its job by composing Exa + Firecrawl + GPT-4o-mini at lower cost. Add Sonar only when we ship the NL Search UX. |
| **Two-way HubSpot sync** → v1.5 | One-way push (NORAD → HubSpot) ships in v1. Bidirectional sync (read existing CRM contacts → avoid double-outreach) is finicky and a known follow-up. |
| **Meilisearch** → Optional v1 add | Postgres full-text search works at v1 volumes. Add Meilisearch when Discover page latency demands it. |
| **Terraform for full IaC** → v1.5 | Manual provisioning of Vercel + Supabase + Upstash + Fly.io is fine for one tenant; Terraform pays off at 3+ environments. |

---

## 7. Honest Confidence Score

| Area | Confidence | Note |
|---|---|---|
| Architecture & extensibility | 9/10 | Proven 3-layer pattern; niche-agnostic by design. |
| Stack choices | 8.5/10 | All boring, battle-tested tools with clean escape hatches. |
| Source coverage for BAT v1 | 7/10 | Strong on regulatory/filings/patents; missing social (LinkedIn/Reddit/trade shows) until Phase 2. |
| Time-to-value | 7.5/10 | Entity resolution + scoring tuning needs 4–6 weeks to sharpen post-launch. |
| Future expansion (more niches/tools) | 9/10 | This is the design's strongest property. |
| **Overall** | **~8 / 10** | Strong v1 plan with two known soft spots that are explicit, not hidden. |

**To raise confidence to 9.5/10 before build starts:**

1. Confirm BAT's weekly target volume of qualified opportunities (5–10/wk vs 30+/wk).
2. Pre-load 50 BAT-curated example companies as gold-standard scoring data.
3. Plan a 2-week silent pilot (engine runs, no outreach goes out, BAT validates ranked lists).
4. Decide whether to pull LinkedIn signals into v1 (legal + cost call).

---

## 8. Companion Files

| File | Purpose |
|---|---|
| `PLAN.md` | Architecture & data-model deep-dive |
| `RESEARCH.md` | Competitor + tooling research underlying every choice |
| `STACK.md` | Full stack spec with frontend/backend layouts and schema sketch |
| `NORAD_PIPELINE.md` | The 8-stage pipeline with agent placement |
| `NORAD_BLUEPRINT.md` | **This document — the executive blueprint** |

---

*Prepared April 2026 by **Growth Machine** for **BAT** · Project: NORAD 1. All vendor pricing pulled from official pricing pages; confirm current rates at vendor sign-up.*
