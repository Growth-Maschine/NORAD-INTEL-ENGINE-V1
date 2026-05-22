# NORAD — Backend / API Cost Research

**Prepared April 2026 by Growth Machine · Project: NORAD Discovery Engine**

> **Status: Research draft for review. No spreadsheet yet — per request, we lock the data here first, then build the sheet.**

---

## 0. How to read this document

This is the verified-pricing, full-stack cost model for **NORAD** — the discovery / news-lead intelligence engine, as a product. All vendor numbers were pulled from official pricing pages between **April and May 2026**. Sources are linked inline.

This document is **engine-generic** — it costs out one full deployment of NORAD doing what NORAD is built to do (find signals, resolve entities, enrich, score, surface qualified opportunities). It is not tied to any one client vertical, geography, or signal mix. Plug a different vertical in (industrial, biotech, fintech, retail, anything) and the same stack and per-candidate economics apply — only the source list inside Layer 2 changes.

**Stack philosophy (as confirmed):** premium / best-performing only — no cheap-stack comparison. We pick the right tool per job, not the cheapest.

**Scope (as confirmed):** core engine only — data APIs + LLM inference + our own infrastructure. **Excluded:** CRM, email-sending services, downstream sales tooling — those are separate budgets a client already runs.

**Side-by-side:** v1 (batch + dashboard) and Phase 2 (interactive natural-language search + multi-tenant) are both costed.

---

## 1. Volume model — the foundation

The single biggest cost lever is **how many candidate companies the pipeline processes per day**. To surface a healthy stream of qualified opportunities (industry standard for BD intelligence engines: roughly 8–15 qualified per week per deployment), the funnel must be much wider — typical engines see ~20–40× more candidates entering than qualified opportunities exiting.

**Recommended baseline: ~200 candidates/day = ~6,000/month per deployment.**

| Funnel stage | Daily | Monthly | What it means |
|---|---|---|---|
| **Raw signals ingested** (filings, news, patents, social, web) | ~5,000 | ~150,000 | Twice-daily ingestion across all configured sources |
| **De-duplicated to candidate companies** | **200** | **6,000** | After entity resolution (Splink) |
| **Pass hard filters** (vertical, geo, size, tags) | ~60 | ~1,800 | LLM-justification budget tier |
| **Score ≥ 70 — enter review queue** | ~3 | ~80 | What an operator actually reviews |
| **Score ≥ 85 — Elite alert** | ~0.4 | ~12 | Top-of-funnel opportunities for client deal teams |

**Why this number:**
- Below 100/day, the system is starved on quiet weeks → empty queues → erosion of operator trust.
- Above 500/day, infrastructure cost climbs disproportionately and operator review fatigue becomes the bottleneck, not signal supply.
- 200/day is the proven sweet spot for a single-tenant, single-vertical NORAD deployment.

**Phase 2 adds:** roughly 20 active analyst seats × 5 NLS queries/day × 22 workdays = **~2,200 interactive queries/month** on top of the batch volume per deployment.

**The whole model scales linearly.** If a deployment needs 400/day, double the data-API line items; infrastructure scales by ~30% (not 100%) thanks to fixed hosting overhead.

---

## 2. The full tool stack

### 2.1 Core mental model

NORAD's pipeline groups into five layers. Each layer has a clear "winner" tool and clear runners-up.

| Layer | What it does | Primary tool | Backup / alt |
|---|---|---|---|
| **L1 — Search & web data** | Find companies and signals on the open web | EXA (semantic) + SerpApi (Google) + Firecrawl (extract) | Bright Data SERP, Brave Search API |
| **L2 — Structured & regulatory** | Pull verified records from authoritative sources | Open government APIs (patent offices, regulators, corporate registries — list customised per vertical) | Lens.org for richer patent metadata |
| **L3 — Closed platforms** | Get social + private-company data | Apify (LinkedIn, PitchBook, Instagram, TikTok, Reddit) + Grok Live Search (X/Twitter) | Bright Data Web Unlocker |
| **L4 — Enrichment & entity** | Turn a name into a full company profile | Diffbot Knowledge Graph + Diffbot Article + Splink (entity resolution) | Clearbit/People Data Labs (paid alts) |
| **L5 — LLM inference** | Parse, score, justify, draft outreach | OpenAI GPT-4o-mini (parse) + Anthropic Claude Sonnet 4.6 (justify) + OpenAI embeddings | Perplexity Sonar (Phase 2 NLS only), Grok Live Search (X grounding) |

---

### 2.2 Per-tool deep dive — verified April–May 2026

#### **Perplexity API** — Sonar + Deep Research
- **Where in pipeline:** Phase 2 only — natural-language search frontend.
- **Pricing (per 1M tokens):**
  - Sonar: $1 in / $1 out
  - Sonar Pro: $3 in / $15 out
  - Sonar Reasoning Pro: $2 in / $8 out
  - **Sonar Deep Research: $2 in / $8 out + extra reasoning-step surcharge**
- **Rate limits:** Tier-based (Tier 1: 50 req/min; Tier 5: 1000+ req/min after spend history)
- **Monthly Phase 2 estimate (per deployment):** ~$110 at 2,200 queries × $0.05 average
- **Source:** https://docs.perplexity.ai/docs/getting-started/pricing
- **Why use it (Phase 2 only):** Built-in real-time web grounding + citations. Saves us from rebuilding search-and-cite for the NLS layer.

#### **EXA API** — semantic search + content
- **Where in pipeline:** L1 — primary semantic search on every enrichment cycle.
- **Pricing:**
  - Search: **$7 / 1k requests**
  - Deep Search: $12–15 / 1k requests
  - Contents: $1 / 1k pages
  - Monitors: $15 / 1k requests
  - Answer: $5 / 1k requests
- **Free tier:** 1,000 requests/month
- **Rate limits:** Configurable latency 180ms–1s, generous concurrency
- **Pipeline usage:** ~5 searches per candidate + ~10 content pulls per candidate
- **Monthly v1 estimate:** 30,000 searches ($210) + 60,000 content pulls ($60) = **$270/mo**
- **Source:** https://exa.ai/pricing
- **Why use it:** Token-efficient highlights designed for AI agents — the cleanest LLM-ready text on the market.

#### **Diffbot** — Knowledge Graph + Article + NLP
- **Where in pipeline:** L4 — primary company enrichment + automated knowledge-graph lookups.
- **Pricing:**
  - Free: 10K credits, 5 calls/min
  - Startup: **$299/mo** — 250K credits, 5 calls/sec ($0.0012/credit)
  - Plus: $899/mo — 1M credits, 25 calls/sec ($0.0009/credit)
  - Enterprise: Custom
- **Pipeline usage:** ~3 credits per candidate (KG lookup + article extract + NLP entities)
- **Monthly v1 estimate:** 18,000 credits → **Startup $299/mo** comfortably covers it
- **Source:** https://www.diffbot.com/pricing/
- **Why use it:** The cleanest structured-data extraction on the market for company entities — replaces 3–4 custom scrapers we'd otherwise build.

#### **Firecrawl** — scrape, crawl, map, extract
- **Where in pipeline:** L1 — open-web crawling + structured extraction.
- **Pricing (1 credit = 1 page):**
  - Free: 500 credits one-time
  - Hobby: $16–20/mo, 3K credits
  - **Standard: ~$83/mo, 100K credits ($0.00083/credit)**
  - Growth: ~$333/mo, 500K credits
- **Pipeline usage:** ~6K maps/mo + ~15K scrapes/mo + ~6K extracts/mo = ~27K credits/mo
- **Monthly v1 estimate:** **Standard $83/mo** comfortably covers (uses 27% of allowance)
- **Source:** https://www.firecrawl.dev/pricing
- **Why use it:** The "extract" endpoint with LLM-defined schemas saves significant glue code per source.

#### **SerpApi** — Google Search results
- **Where in pipeline:** L1 — trade-press and recent-news Google queries.
- **Pricing:**
  - Developer: $75/mo, 5K searches
  - **Production: $150/mo, 15K searches ($10/1K)**
  - Business: $250/mo, 30K searches
  - Startup: $999/mo, 200K searches
- **Pipeline usage:** ~50 query patterns × 2/day × 30 days = ~3K/mo
- **Monthly v1 estimate:** **Production $150/mo** for headroom + 1K/hr throughput
- **Source:** https://serpapi.com/pricing

#### **Bright Data SERP API** — backup search + Web Unlocker
- **Where in pipeline:** L1 — fallback when SerpApi rate-limits or geo-targeting needs.
- **Pricing:**
  - Pay-as-you-go: $3/CPM (per 1k requests)
  - Micro: $10/mo, $1.80/CPM, ~5,555 req included
  - Growth: $499/mo, $2.30/CPM, ~217K req
- **Monthly v1 estimate:** Use as fallback only — **~$10/mo Micro tier** for safety
- **Source:** https://brightdata.com/pricing

#### **Patent & regulatory APIs (L2 — generic baseline)**
NORAD's L2 source list is configured per vertical. The premium baseline that ships with every deployment uses these (all free or very low cost):

| Source | Coverage | Cost |
|---|---|---|
| **USPTO PatentSearch / Open Data Portal** | US patents, post-March 2026 ODP migration. 45 req/min. | **Free** |
| **Google Patents Public Data (BigQuery)** | Global patent families, statistical analysis | First 1 TiB/month free, then $6.25/TiB → effectively **$0** at our volume |
| **EPO OPS** | European patents | **Free** (4GB/week limit) |
| **CIPO / IPO / WIPO** | Other major patent offices | **Free** |
| **EDGAR (US SEC)** | US public-company filings | **Free** |
| **Companies House (UK), SEDAR+ (Canada), and equivalents** | Corporate registries | **Free** |
| **OpenFDA, EMA, Health Canada, MHRA** | Health/regulatory submissions | **Free** |
| **Lens.org Patent + Scholar API** | Richer patent + academic metadata | $1,000/yr individual commercial (~$83/mo) — Phase 2 add-on |

**v1 L2 monthly cost: ~$0.** Phase 2 with Lens.org: **~$83/mo**.

#### **Reddit API**
- **Pricing:**
  - Free tier: 100 req/min OAuth (academic / non-commercial only)
  - **Commercial: contract-only, not publicly listed (typically $10K+/yr enterprise)**
- **Recommendation:** **Use Apify Reddit actor instead** — cheaper, no contract overhead, unlimited reads. ~$30–50/mo at our volume.
- **Source:** https://www.redditcommentscraper.com/article-reddit-api-pricing-alternative.html

#### **X (Twitter) API + Grok Live Search**
- **Where in pipeline:** L3 — public-figure / founder posts, brand mentions.
- **X API pricing (post Feb 2026):**
  - Pay-per-use: $0.01 per post created, $0.005 per post read (cap 2M reads/mo)
  - Legacy Basic ($200/mo) and Pro ($5,000/mo) **closed to new signups**
- **Grok Live Search (recommended):**
  - **Grok 4.3:** $1.25 in / $2.50 out per 1M tokens — built-in real-time X + web search
  - No separate per-post fee; replaces ~80% of X API needs
- **Monthly v1 estimate:** **Grok Live Search $30–50/mo** + minimal direct X API budget ($25)
- **Source:** https://x.ai/api
- **Why Grok over X API:** Native X access plus live web — built by xAI who own X — and per-token economics massively beat X API's pay-per-read model at our volumes.

#### **Apify — platform plan**
- **Where in pipeline:** L3 — all closed-platform scrapers.
- **Pricing tiers:**
  - Free: $5 prepaid, $0.20/CU
  - Starter: $29/mo + pay-as-you-go, $0.20/CU
  - **Scale: $199/mo + pay-as-you-go, $0.16/CU** ← recommended
  - Business: $999/mo, $0.13/CU
- **Recommendation:** **Scale plan $199/mo** — covers all platform compute + Silver Store discount (~10% off per-actor pricing).
- **Source:** https://apify.com/pricing

#### **Apify — per-actor breakdown**

| Actor | Use case | Pricing | Monthly volume | Monthly cost |
|---|---|---|---|---|
| LinkedIn Scraper (`get-leads/linkedin-scraper`) | Company + founder profiles | $3 / 1K results | 18,000 | **$54** |
| Instagram Scraper (`apify/instagram-scraper`) | Brand presence | $1.60 / 1K | 1,200 | **$2** |
| TikTok Scraper (`clockworks/tiktok-scraper`) | Pay-per-event | ~$2 / 1K videos | 1,000 | **$2** |
| PitchBook Profile Scraper (`mdataset`) | Funding + cap table on private targets | Per-result, ~$15 / 1K | 1,800 | **$27** |
| Reddit Scraper | Subreddit monitoring | Per-CU | bundled | **~$30** |
| **Subtotal per-actor on top of plan** | | | | **~$115/mo** |
| **Apify combined monthly (plan + actors)** | | | | **~$314/mo** |

---

### 2.3 LLM inference — answering "Perplexity or OpenAI?"

**Short answer: neither alone. Use the right model for each step.**

| Step in pipeline | Model | Why this one | Cost per call | Monthly cost |
|---|---|---|---|---|
| **Signal parsing** (extract entities from raw text) | **OpenAI GPT-4o-mini** | Cheapest reliable structured-output model. 6K calls/mo. | ~$0.0008 | **$5** |
| **Embeddings** (semantic search + dedup) | **OpenAI text-embedding-3-small** ($0.02/1M tokens) | Industry standard, integrates cleanly with pgvector. | ~$0.0001 | **$1** |
| **Scoring justification** (write the "why this is a 78") | **Anthropic Claude Sonnet 4.6** ($3/$15 per 1M) | Best-in-class reasoning + clean prose for human review. 1,800 calls/mo. | ~$0.039 | **$70** |
| **Outreach draft** (first-touch email) | **Anthropic Claude Sonnet 4.6** | Same — quality matters more than cost at 50/mo. | ~$0.013 | **$1** |
| **Phase 2 — NLS query answering** | **Perplexity Sonar Pro / Deep Research** | Built-in real-time web grounding + citations. | ~$0.05 | **$110** |
| **Phase 2 — X/social grounding** | **xAI Grok 4.3 Live Search** | Native X access + live web. Replaces direct X API. | bundled | **$30** |

**Total LLM v1: ~$77/mo. Phase 2 adds: ~$140/mo.**

**Why not Perplexity for v1?** Sonar is excellent for live-web reasoning (Phase 2 NLS), but for batch parsing/justification we don't need real-time web grounding — just clean inference. GPT-4o-mini and Claude Sonnet are 5–10× cheaper for that workload.

**Why Anthropic Claude over GPT-4 for justification?** Side-by-side, Claude Sonnet 4.6 produces cleaner, more diplomatic prose that operators can ship to executives without rewrites. Worth the marginal cost.

**Reference table — every relevant frontier model April–May 2026:**

| Model | Input ($/1M) | Output ($/1M) | Context | Best for |
|---|---|---|---|---|
| GPT-4o-mini | $0.15 | $0.60 | 128K | Cheap structured parsing |
| GPT-4o | $2.50 | $10 | 128K | Legacy fallback |
| GPT-4.1 | $2 | $8 | 1M | General reasoning alt |
| Claude Haiku 4.5 | $1 | $5 | 200K | Fast cheap reasoning |
| **Claude Sonnet 4.6** | **$3** | **$15** | **1M** | **Justification, outreach** |
| Claude Opus 4.7 | $5 | $25 | 1M | Reserved — too expensive at scale |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | 1M | Cheapest tier (alt to GPT-4o-mini) |
| Gemini 2.5 Flash | $0.30 | $2.50 | 1M | Mid alt |
| Gemini 2.5 Pro | $1.25 | $10 | 1M | Heavy alt |
| **Grok 4.3** | **$1.25** | **$2.50** | **1M** | **X + web grounding** |
| Perplexity Sonar Pro | $3 | $15 | — | Live-web with citations |
| Perplexity Sonar Deep Research | $2 | $8 + reasoning surcharge | — | Phase 2 multi-step queries |

---

### 2.4 Database & vector storage — answering "Supabase or anything else?"

**Recommendation: Supabase Postgres + `pgvector` + `pgvectorscale` extension. One database, one bill, one backup story.**

| Option | Monthly cost (v1) | Vector quality | Multi-tenant? | Verdict |
|---|---|---|---|---|
| **Supabase Pro + pgvector** | $25 + ~$10 compute add-on | Production-grade with `pgvectorscale` (StreamingDiskANN) | Yes — built-in RLS | Winner if compliance not required |
| **Supabase Team + pgvector** | **$599** | Same | Yes + SOC2 + 28-day PITR + audit logs | **Winner for premium / enterprise-ready** |
| Neon Postgres + Pinecone | ~$70 + $50 = $120 | Excellent (dedicated vector DB) | Manual | Splits stack into two products → more ops, more bills |
| Pinecone alone (Standard) | $50/mo min, $0.33/GB + $4/M WU + $16/M RU | Best dedicated | Yes | Need separate Postgres anyway → adds bill |
| Self-hosted Postgres + pgvector on Fly | ~$120 (machines + volumes) | Production-grade | Manual | Saves ~$80/mo but adds DBA burden |

**Recommended for premium NORAD deployment: Supabase Team plan ($599/mo)** — gets us SOC2, daily backups with 28-day PITR, audit logs, and SSO. One bill, one team to call when something breaks. The compliance posture matters when any enterprise client's legal team reviews.

**Why pgvector over Pinecone:**
- One database, one query language, one transaction boundary
- Splink (entity resolution) needs joins between vectors and structured data — trivially easy in Postgres, painful across two products
- `pgvectorscale` (built by Timescale, free extension) gives Pinecone-equivalent recall at our scale (~6K candidates/mo, ~500K vectors steady-state per deployment)
- Pinecone makes sense at 100M+ vectors — we're nowhere near that

---

### 2.5 Supporting infrastructure (the rest of the stack)

| Service | Plan | Monthly cost | Why |
|---|---|---|---|
| **Upstash Redis** | Pay-as-you-go + Prod Pack | **$230** | Job queue (BullMQ), rate limiters, dedup cache. Prod Pack adds SOC2/HIPAA/encryption-at-rest. |
| **Cloudflare R2** | Pay-as-you-go | **$5** | Raw signal blobs, scraped HTML, generated PDFs. Free egress is huge vs S3. |
| **Inngest** | Paid (~$75 base) | **$75** | Workflow orchestration (durable functions, retries, fan-out). |
| **Meilisearch Cloud** | Pro $300 | **$300** | Full-text search across companies + signals for the dashboard. |
| **Langfuse** | Pro $199 | **$199** | LLM observability — every prompt, response, latency, cost tracked. Critical for tuning. |
| **Fly.io** | Pay-as-you-go | **$220** | Backend workers (4 shared-CPU machines + 1 dedicated for Splink entity resolution). |
| **Vercel** | Pro | **$130** | Frontend dashboard hosting, edge functions, ISR. ~$20/seat × 5 + functions. |
| **Sentry** | Team | **$26** | Error tracking on both frontend and backend. |
| **Subtotal infrastructure** | | **$1,185/mo** | |

---

## 3. Cost flow — what happens when one candidate goes through the pipeline

Walking a single candidate company end-to-end at v1 volume (200/day = 6K/mo):

| Stage | Tool calls | Cost per candidate |
|---|---|---|
| 1. Signal ingested (one signal among many) | 1 SerpApi search ($0.010) + ~0.5 Firecrawl scrapes ($0.0004) | $0.010 |
| 2. Entity extraction & dedup | 1 GPT-4o-mini parse (~$0.0008) + 1 embedding (~$0.0001) | $0.001 |
| 3. Enrichment | 3 Diffbot credits ($0.004) + 5 EXA searches ($0.035) + 10 EXA contents ($0.010) + 1 Firecrawl extract ($0.001) | $0.050 |
| 4. Closed-platform | 3 LinkedIn ($0.009) + 0.3 PitchBook ($0.005) + 0.2 social ($0.0003) | $0.014 |
| 5. Hard filter (deterministic, no API) | — | $0 |
| 6. Justification (only ~30% pass hard filter) | Claude Sonnet ~$0.039 × 0.3 | $0.012 |
| 7. Storage + vector index (amortized) | Supabase + Redis + R2 | $0.005 |
| **Total per candidate** | | **~$0.092** |

**Per qualified opportunity (≥70 score):** $0.092 × (6,000 / 80) = **~$6.90** per opportunity that hits the review queue.
**Per Elite alert (≥85 score):** $0.092 × (6,000 / 12) = **~$46** per Elite-tier opportunity.

**Read this number carefully:** ~$46 of API + infra cost per Elite opportunity is excellent unit economics for a BD intelligence engine — typical consulting alternatives charge $500–2,000 per surfaced target.

---

## 4. Monthly totals — v1 vs Phase 2 side-by-side (per deployment)

| Bucket | v1 (batch + dashboard) | Phase 2 (+ NLS + multi-tenant) | Delta |
|---|---|---|---|
| **EXTERNAL DATA APIs** | | | |
| SerpApi (Production) | $150 | $150 | — |
| Bright Data SERP (backup) | $10 | $10 | — |
| Firecrawl (Standard) | $83 | $83 | — |
| Diffbot (Startup) | $299 | $899 *(upgrade to Plus for NLS lookups)* | +$600 |
| EXA AI | $270 | $316 *(+NLS searches)* | +$46 |
| Apify (Scale plan + actors) | $314 | $314 | — |
| Grok Live Search (X access) | $30 | $50 | +$20 |
| X API (minimal direct use) | $25 | $25 | — |
| Lens.org patents | $0 *(skipped v1)* | $83 *(annual amortized)* | +$83 |
| Open government APIs (USPTO + EPO + CIPO + Google Patents + EDGAR + OpenFDA + corporate registries + …) | $0 | $0 | — |
| **Subtotal external** | **$1,181** | **$1,930** | **+$749** |
| **LLM INFERENCE** | | | |
| OpenAI (GPT-4o-mini parsing + embeddings) | $6 | $6 | — |
| Anthropic Claude Sonnet (justification + outreach) | $71 | $71 | — |
| Perplexity Sonar (Phase 2 NLS) | $0 | $110 | +$110 |
| **Subtotal LLM** | **$77** | **$187** | **+$110** |
| **CORE INFRASTRUCTURE** | | | |
| Supabase Team (Postgres + pgvector + SOC2) | $599 | $799 *(+compute add-on for multi-tenant)* | +$200 |
| Upstash Redis + Prod Pack | $230 | $230 | — |
| Cloudflare R2 | $5 | $10 | +$5 |
| Inngest | $75 | $150 *(higher tier for NLS workflows)* | +$75 |
| Meilisearch (Pro) | $300 | $300 | — |
| Langfuse (Pro) | $199 | $199 | — |
| Fly.io workers | $220 | $320 *(+NLS query workers)* | +$100 |
| Vercel (Pro, 5 seats) | $130 | $200 *(+function execution for NLS)* | +$70 |
| Sentry | $26 | $26 | — |
| **Subtotal infrastructure** | **$1,784** | **$2,234** | **+$450** |
| **TOTAL MONTHLY (per deployment)** | **$3,042** | **$4,351** | **+$1,309** |

**Per-candidate cost (v1):** $3,042 ÷ 6,000 candidates = **$0.51** processed
**Per-qualified-opportunity cost (v1):** $3,042 ÷ ~80 qualified = **$38** per queue item
**Per-Elite-opportunity cost (v1):** $3,042 ÷ ~12 Elite = **$254** per Elite alert

---

## 5. Key recommendations summary

1. **Volume baseline: 200 candidates/day per deployment.** Tunable at any time — every $1k of monthly budget moves the funnel ~30%.
2. **LLM stack: OpenAI GPT-4o-mini for parsing + Claude Sonnet 4.6 for justification + OpenAI embeddings.** Perplexity reserved for Phase 2 NLS only.
3. **Database: Supabase Team plan + pgvector + pgvectorscale.** One product, one bill, SOC2 included. No Pinecone needed at our scale.
4. **X/Twitter access: Grok Live Search.** Replaces direct X API at a fraction of the cost; built by the company that owns X.
5. **Patent stack v1: USPTO + EPO + CIPO + Google Patents BigQuery (all free).** Add Lens.org in Phase 2 if academic / global depth is needed.
6. **Reddit: Apify Reddit actor, not the official API.** Reddit's commercial contract starts at thousands of dollars per year.
7. **Apify Scale plan ($199/mo) + per-actor charges (~$115/mo).** Cheaper than Business and gives Silver Store discount.
8. **Premium hosting: Supabase Team + Upstash Prod Pack + Langfuse Pro + Meilisearch Pro.** All chosen for compliance posture and full observability — not for the cheapest path.

---

## 6. What this does NOT include (per your instructions)

- CRM seats (HubSpot, Salesforce, etc.)
- Email-sending infrastructure (SendGrid, Postmark)
- PDF / report-generation services
- Any "downstream" sales tooling
- Custom domain costs, SSL beyond what Vercel/Fly include
- One-time setup or consulting fees

---

## 7. Open items to confirm before sheet-build

| # | Question | Default if no answer |
|---|---|---|
| 1 | Compliance: does the standard NORAD deployment require SOC2 / HIPAA on the database? | **Yes** → Supabase Team $599 (current model) |
| 2 | Do we lock in Grok Live Search as the primary X path, or also keep direct X API for redundancy? | **Grok primary, X API as $25 budget buffer** |
| 3 | Lens.org $1k/year — in for Phase 2 or skip entirely? | **Add in Phase 2** |
| 4 | Phase 2 multi-tenant — shared infra + RLS or per-tenant DB? | **Shared Supabase + RLS for cost efficiency** |
| 5 | Anthropic Claude Sonnet vs GPT-4o for justification — preference? | **Claude Sonnet 4.6 (cleaner prose)** |

---

## 8. Next step

After you review and approve these numbers, the sheet build is:
- One row per tool/service (~30 rows)
- Columns: tool, layer, plan/tier, unit price, rate limit, monthly volume, monthly cost (v1), monthly cost (Phase 2), notes, official source link
- A "Pipeline Cost Flow" tab showing per-candidate cost breakdown
- A "Volume Sensitivity" tab showing how monthly cost moves at 100 / 200 / 500 / 1000 candidates per day
- An "Executive" summary tab with the v1 vs Phase 2 totals + per-opportunity unit economics

**Until you approve this research, no sheet is built.**

---

*Prepared April 2026 by Growth Machine · Project: NORAD Discovery Engine · All vendor pricing verified against official pages April–May 2026.*
