# NORAD — Pipeline & Toolset

> The clearest possible view of **how the engine actually runs**, and **exactly which tool does what** for the NORAD (BAT BD intelligence) use case.

> Companion to: `PLAN.md` (architecture), `RESEARCH.md` (competitor + tooling research), `STACK.md` (frontend + backend stack).

---

## 1. The One-Sentence Mental Model

> **The engine is an always-on factory. Agents are specialists called in for two specific moments: making sense of unstructured text, and writing the score narrative.**

Engine does ~97% of the work in plain code. Agents handle the ~3% that genuinely needs a language model.

---

## 2. The Pipeline — Eight Stages, In Order

```
┌──────────┐   ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ 1. CRON  │ → │ 2. PULL │ → │ 3. CLEAN │ → │ 4. DEDUP │ → │ 5. ID  │ → │ 6. SCORE │ → │ 7. DRAFT │ → │ 8. QUEUE │
│ trigger  │   │ sources │   │ normalize│   │  & store │   │resolve │   │  + flag  │   │ outreach │   │ for human│
└──────────┘   └─────────┘   └──────────┘   └──────────┘   └────────┘   └──────────┘   └──────────┘   └──────────┘
   ENGINE        ENGINE      ENGINE+AGENT     ENGINE        ENGINE     ENGINE+AGENT     ENGINE         ENGINE
                            (unstructured)                              (justification)  (template)
```

| # | Stage | What happens | Engine or Agent? |
|---|---|---|---|
| 1 | **Cron Trigger** | Scheduler fires twice a day (e.g. 6 AM + 6 PM ET) | Engine |
| 2 | **Pull** | Each source connector fetches new items since last run | Engine |
| 3 | **Clean / Normalize** | Raw payloads → canonical schema. Structured = pure code. **Unstructured (articles, PDFs) = agent for parsing only.** | Engine + **Agent** (only for unstructured) |
| 4 | **Dedupe + Store Raw** | Hash-check against `raw_events`; new ones get written | Engine |
| 5 | **Entity Resolve** | "Is this company already in our DB?" Deterministic match → Splink probabilistic. Uncertain ones go to **human review queue**, not an agent. | **Engine only** |
| 6 | **Score + Red-Flag** | Apply weighted rubric (deterministic math). Apply red-flag rules (deterministic). **Agent writes the prose justification under each metric.** | Engine + **Agent** (justification text only) |
| 7 | **Draft Outreach** | Survivors get a templated draft email + deal card pre-filled with entity facts and score. **Human writes the actual outreach text.** | Engine (template fill) — *human writes the words* |
| 8 | **Queue for Approval** | Drop into BD review queue. Human reviews, edits, approves, sends. | Engine |

**Total agent calls per signal:** typically **2** — one for unstructured parsing (Stage 3, only when the source is an article/PDF), one for the justification narrative on each surviving opportunity (Stage 6). Structured-feed signals (most of them) trigger only **1** agent call total.

**Two agent locations only:**
- **Stage 3 — Clean/Normalize** (unstructured payloads only)
- **Stage 6 — Score + Red-Flag** (prose justification only; numbers stay deterministic)

---

## 3. Stage-by-Stage Detail (with the exact tool)

### Stage 1 — Cron Trigger
- **Tool:** Inngest (cron schedules: `0 6 * * *` and `0 18 * * *` ET)
- **What it does:** Kicks off one durable workflow per active source. Each workflow is checkpointed step-by-step, so if a step fails it retries from there — not from the start.

### Stage 2 — Pull (Source Connectors)
Two flavors of connector. Both speak the same internal interface:
```ts
interface Connector {
  id: string;
  fetchSince(date: Date): Promise<RawEvent[]>;
}
```

> **Note:** Social platform sources (LinkedIn, Reddit, TikTok, Instagram) are **deferred to Phase 2**. Real legal exposure + mediocre signal-to-noise for M&A specifically. v1 focuses on regulatory, trade press, and filings — the highest-signal sources.

#### 2A — Build (proprietary, free, stable) — the moat
| NORAD Source | Tool / Approach |
|---|---|
| **Health Canada NHP database** | Direct REST call (public API) |
| **FDA — GRAS, NDI, OTC monograph** | OpenFDA API + scrape pages OpenFDA misses |
| **SEDAR+** (Canadian filings) | Direct XML download (free) |
| **SEC EDGAR** (US filings, S-1, 8-K) | EDGAR full-text search + SGML parse (free) |
| **CIPO** (Canadian patents) | Bulk download (free) |
| **USPTO** (US patents) | Bulk download (free) |

These are the **moat** sources — zero variable cost, stable schemas, highest signal. Build them at v1.

#### 2B — Buy (compose third-party tools)
| NORAD Source | Tool |
|---|---|
| **Trade press** (Convenience Store News, CSP, Pharmacy Practice+, Drug Store News, Chain Drug Review) | **Firecrawl** (URL → clean markdown) + **Exa** (find new articles by topic) |
| **Press wires** (Newswire, CNW, GlobeNewswire, PR Newswire) | **Firecrawl** + **Exa** |
| **Distributor announcements** (UNFI, KeHE, McKesson, Sobeys/Voilà) | **Firecrawl** of their newsroom pages |
| **General brand mentions** (functional beverages, OTC, snacking) | **Bright Data SERP API** for Google queries; **Exa** for semantic discovery |
| **Company entity enrichment** (size, HQ, web presence) | **Diffbot** Knowledge Graph |

### Stage 3 — Clean / Normalize *(Agent location #1)*
**Two paths depending on source type:**

| Path | When | Tool | Cost |
|---|---|---|---|
| **Structured** | NHP REST, EDGAR XML, OpenFDA JSON, SEDAR+ XML, USPTO/CIPO bulk | Plain TS parser, **Zod** validation | $0 |
| **Unstructured** | Trade press articles, PR wires, distributor press releases, PDFs | **Agent: GPT-4o-mini** with structured-output JSON Schema enforcement | ~$0.001 per page |

The agent here is a *parser*, not a thinker. It takes a blob of article text and returns the same canonical schema as the structured path. Strict JSON schema. No "judgment" allowed. No retries on shape mismatch.

**Output (both paths):** every signal lands in `normalized_events` with the same shape:
```ts
{
  entityName: string;
  entityType: 'company' | 'product' | 'brand';
  eventType: 'approval' | 'filing' | 'launch' | 'patent' | 'press' | ...;
  eventDate: Date;
  jurisdiction: 'CA' | 'US';
  sourceUrl: string;
  fetchedAt: Date;
  rawText: string;
  metadata: Record<string, unknown>;
}
```

### Stage 4 — Dedupe + Store Raw
- **Tool:** Postgres (Supabase) + content hash check
- **What it does:** every raw payload hashed; already-seen hashes skipped. Raw payload itself stored in **Cloudflare R2** (cheap object storage); pointer stored in `raw_events` table. This gives full provenance — every signal traces back to its original source URL + timestamp + raw bytes.

### Stage 5 — Entity Resolve *(Engine only — no agent)*
"Is this company already in our DB?"

Two-stage cascade:

| Sub-stage | Tool | Cost | Handles |
|---|---|---|---|
| 5a — Deterministic | Plain TS — normalize names, strip suffixes (Inc., Ltd., Corp.), block on first letters | $0 | ~70% of cases (clean exact matches) |
| 5b — Probabilistic | **Splink** (Python microservice) — Fellegi-Sunter model with Jaro-Winkler comparisons | $0 (compute only) | another ~20% (close fuzzy matches) |
| 5c — Uncertain residual | Land in `entity_review_queue` for **human review** | $0 | the residual ~10% (hard cases) |

Embeddings for semantic matching ("The Vitamin Shoppe" = "Vitamin Shoppe Inc.") via **OpenAI text-embedding-3-small**, stored in **pgvector + pgvectorscale**. These boost Splink's accuracy without invoking an agent.

**No LLM at this stage.** The 10% Splink can't decide become a human-review task — surfaced in the UI, BD analyst confirms or splits. Each confirmed pair becomes a labeled training example that improves Splink's model over time.

**Output:** the `entities` table grows with resolved master records. Each `normalized_event` is linked to the right entity via `entity_links`.

### Stage 6 — Score + Red-Flag *(Agent location #2)*
**Deterministic part (engine, plain TS):**
```
totalScore = Σ ( metric_band(1–20) × weight )

Strategic Fit         × 30%
Revenue Potential     × 25%
Operational Synergy   × 20%
Regulatory Readiness  × 15%
Deal Accessibility    × 10%
```
Each metric band (1–5 / 6–10 / 11–15 / 16–20) is determined by **rule-based feature extraction** from the entity's signals. No LLM here. Examples:
- *Regulatory Readiness*: "Has NHP license? Full approval? Warning letters?" → mapped to band by rules
- *Deal Accessibility*: "Recent funding round? Founder-led? Distress signal?" → mapped to band by rules

**Red-flag override (deterministic):**
- Notice of Non-Compliance from Health Canada → score drops to <20
- FDA Stay of Marketing Order → score drops to <20
- Banned ingredient mentioned → score drops to <20
- Sustained negative sentiment threshold breached → score drops to <20

**Justification narrative (agent):** for each metric, the agent (**GPT-4o-mini**) writes a short paragraph explaining *why* the band was assigned, citing the underlying signals by ID. The number is deterministic; only the prose is generated. Same for any red flag fired — the rule trips deterministically, the agent just explains it in plain English.

```
Strategic Fit:        Band 14/20
  └─ "Northern Wellness's nootropic line aligns directly with BAT's
      stated functional-beverage thesis. Three SKUs are already listed
      in two Quebec convenience chains (signals #4821, #4822)."
```

### Stage 7 — Draft Outreach *(Engine only — template-filled, human writes the words)*
Only for opportunities where: `score ≥ threshold AND noRedFlags`.

The engine **builds the scaffolding** — no agent involved:

- **Email skeleton** auto-populated with entity name, top 3 cited signals, score, justification text from Stage 6, BD analyst's name. The actual prose is written by the human in the review queue UI.
- **Deal card** auto-populated as a one-page PDF (via React-PDF) with: company facts (from Diffbot enrichment), score breakdown, justifications from Stage 6, source URL list.

This keeps full control over voice + tone with the BD team for v1.

> **Phase 2 option:** add a Composer Agent that drafts the email prose against a tenant-defined voice profile. Easy to bolt on once v1 is in production and we have real BD feedback on what good outreach looks like.

### Stage 8 — Queue for Approval
- Skeleton email + auto-filled deal card land in **`outreach_drafts`** + **`deal_cards`** tables
- Surfaced on `/review-queue` page in the frontend
- BD analyst writes the email body, reviews the deal card, edits anything
- Approval chain (BAT-configurable: BD lead → Marketing → Director)
- On final approval → CRM sync (HubSpot or Pipedrive) + send via SendGrid
- Audit log entry written for every state change

---

## 4. The NORAD Toolset — Single-Page Reference

### Pipeline Tools
| Layer | Tool | Used For |
|---|---|---|
| Scheduler | **Inngest** | Cron triggers, durable workflows, step retries |
| Sub-queues | **BullMQ on Redis (Upstash)** | Fan-out within a workflow step |
| Validation | **Zod** | Schema enforcement at every external boundary |

### Source Connectors — Buy
| Tool | What for | Cost (approx) |
|---|---|---|
| **Exa AI** | Semantic discovery — "find new articles about X" | $7 / 1K standard searches |
| **Firecrawl** | URL → clean markdown for LLM parsing | $0.0008 / page |
| **Bright Data SERP API** | High-volume Google searches | $1–1.50 / 1K results |
| **Diffbot** | Company entity enrichment | $0.001 / lookup |

### Source Connectors — Build (proprietary, free) — the moat
| Source | Approach |
|---|---|
| Health Canada NHP | REST API |
| OpenFDA (GRAS, NDI, OTC) | REST API |
| SEDAR+ | XML download |
| SEC EDGAR | SGML full-text |
| CIPO patents | Bulk download |
| USPTO patents | Bulk download |

### LLM & Agents (only two locations)
| Where | Role | Model | Why this model |
|---|---|---|---|
| **Stage 3 — Clean/Normalize** | Parse unstructured text → canonical schema | **GPT-4o-mini** | Cheap + fast + reliable structured-output |
| **Stage 6 — Score + Red-Flag** | Write prose justification under each metric | **GPT-4o-mini** | Cheap + reliable; bigger model not needed for short narrative |

| Supporting tool | Role |
|---|---|
| **Mastra** | Agent runtime (TS-native) |
| **Vercel AI SDK** | Model abstraction |
| **OpenAI text-embedding-3-small** | Embeddings for semantic name matching |
| **Langfuse** | Trace every agent call, cost per call |

### Entity Resolution
| Tool | Role |
|---|---|
| **Splink** (Python microservice) | Probabilistic record linkage |
| **pgvector + pgvectorscale** | Embedding storage & nearest-neighbor |
| **Human review queue (UI)** | Resolves ~10% ambiguous tail (no agent) |

### Storage
| Tool | Use |
|---|---|
| **Postgres 16 (Supabase)** | Primary OLTP — entities, events, scores, configs |
| **pgvector + pgvectorscale** | Vectors inside Postgres |
| **Redis 7 (Upstash)** | Cache, queues, rate-limit counters |
| **Cloudflare R2** | Raw scraped payloads, generated PDFs |
| **Meilisearch** | Keyword + faceted search on Discover page |

### Frontend (NORAD BD dashboard)
| Tool | Use |
|---|---|
| **Next.js 15 (App Router) + TS** | Framework |
| **Tailwind CSS + shadcn/ui** | Design system |
| **TanStack Query + TanStack Table** | Server state + data grids |
| **React Hook Form + Zod** | Forms |
| **Recharts / Tremor** | Dashboard charts |
| **Clerk** | Auth, multi-tenant orgs (BAT = one org), RBAC |
| **tRPC** | Internal API — fully typed |

### Cross-Cutting
| Tool | Use |
|---|---|
| **Doppler / Infisical** | Secrets vault |
| **OpenTelemetry → Grafana** | Service tracing & metrics |
| **Langfuse** | LLM tracing & cost per call |
| **Cost Ledger table in Postgres** | Every external API call attributed per-tenant per-job |
| **Audit Log table in Postgres** | Append-only state change log |

### Outbound & Integrations
| Tool | Use |
|---|---|
| **HubSpot** (or Pipedrive) | CRM via OAuth |
| **SendGrid** (or Postmark) | Email send for approved outreach |
| **React-PDF** | Deal card PDF generation |

### Hosting & Ops
| Tool | Use |
|---|---|
| **Fly.io** (or Railway) | Container hosting for `api`, `worker`, `resolver-py` |
| **Vercel** | Hosting for Next.js frontend |
| **Supabase** | Managed Postgres |
| **Upstash** | Managed Redis |
| **GitHub Actions** | CI/CD |
| **Terraform** | IaC |

---

## 5. The NORAD Walkthrough — One Real Example

**Scenario:** Health Canada publishes a new NHP approval at 8:55 AM ET for a functional beverage company called "Northern Wellness Inc."

| Time | Stage | What happens | Tool involved |
|---|---|---|---|
| 6:00 PM previous day | — | Last cron run completed; engine remembers `last_seen_at` per source | Inngest |
| 6:00 AM | Cron fires | Inngest triggers `health-canada-nhp` workflow | Inngest |
| 6:00:01 | Pull | Connector hits NHP REST API for entries since `last_seen_at` → finds 12 new approvals incl. Northern Wellness | Custom connector (build) |
| 6:00:02 | Clean | NHP is **structured** → no agent. Zod-validated parser produces canonical event | Plain TS + Zod |
| 6:00:03 | Dedupe | Hashes checked vs `raw_events`; all 12 are new | Postgres |
| 6:00:04 | Resolve | Splink looks for "Northern Wellness Inc." in entities. Finds "Northern Wellness Co." with 0.78 confidence — borderline | Splink |
| 6:00:05 | Resolve (cont.) | Below auto-merge threshold → drops into `entity_review_queue` for BD analyst to confirm later. Meanwhile event linked tentatively. | Engine + UI queue |
| 6:00:06 | Score | Rubric runs: Strategic Fit 14, Revenue 11, Operational 13, Regulatory 18, Deal Accessibility 12 → weighted total 73/100 | Plain TS |
| 6:00:06 | Red-flag check | No notices of non-compliance, no banned ingredients → clean | Plain TS |
| 6:00:07 | Justification | GPT-4o-mini writes one short paragraph per metric citing the underlying signal IDs | Mastra + GPT-4o-mini |
| 6:00:08 | Threshold check | Score 73 ≥ tenant threshold of 60 → passes | Plain TS |
| 6:00:09 | Draft scaffolding | Engine builds skeleton email + auto-fills deal card PDF | Plain TS + React-PDF |
| 6:00:10 | Queue | Draft + deal card lands in `/review-queue` | Postgres + Next.js |
| 9:32 AM | Human review | BD analyst confirms entity merge in queue, writes the email body, hits approve | Frontend |
| 9:33 AM | Send + log | SendGrid sends; HubSpot logs the contact + opportunity | SendGrid + HubSpot |
| 9:33 AM | Audit | Every state change written to `audit_log` | Postgres |

**Total cost of this signal end-to-end:** roughly **$0.003** (one short justification agent call). Engine work itself is sub-cent. Unstructured signals (a press article, say) add ~$0.001 for the parse step → still well under a penny per signal.

---

## 6. The Three Numbers to Watch

| Metric | Target | Why |
|---|---|---|
| **Cost per signal end-to-end** | < $0.05 | Anything higher and the unit economics break |
| **% of signals reaching the review queue** | 5–15% | Higher means filters too loose; lower means rubric too strict |
| **% entity matches Splink can auto-decide** | > 90% | If lower, the human review queue grows faster than the analyst can clear it |

Track these in the cost-ledger UI from week 1.

---

## 7. What NORAD Actually Sees in the UI (v1)

| Page | What's there |
|---|---|
| `/discover` | Newsfeed of every signal, filterable by source, date, jurisdiction, entity type. Like a curated industry briefing. |
| `/opportunities` | Scored & ranked list of companies/products that survived both filters. |
| `/opportunities/:id` | Full detail: who/what/where, all signals attributed to them, the score breakdown with AI-written justification, the auto-filled deal card, links to source URLs. |
| `/review-queue` | (a) Pending entity-match confirmations from Stage 5. (b) Drafted outreach scaffolding + deal card waiting for human-written email body and approval. |
| `/sources` | Add/remove/test sources, set refresh cadence. |
| `/rubric` | Drag-and-drop weights, edit metric bands. |
| `/red-flags` | Add/edit hard-stop rules. |
| `/voice` | (Phase 2) Tone-of-voice + email + deal-card templates for auto-drafting. |
| `/settings` | Approval workflow, alert tiers, CRM connection. |
| `/audit` | Append-only history of every state change. |

---

## 8. Summary in 30 Seconds

1. **Cron fires twice a day.**
2. **Engine pulls from ~10 sources** — six built free (regulatory + filings + patents), four bought (trade press, wires, web search, enrichment). **No social platforms in v1.**
3. **Engine cleans + dedupes + stores** — all plain code for structured feeds; an LLM parser used only for unstructured articles/PDFs.
4. **Splink resolves entities** in pure code; uncertain ~10% lands in a human review queue (no agent).
5. **Engine scores + red-flag-checks** with deterministic math/rules. An LLM writes the prose narrative under each metric.
6. **Engine pre-fills** an outreach skeleton + deal card PDF for every survivor. Human writes the email body.
7. **BD team reviews & approves** in the UI.
8. **Approved outreach is sent** + logged to CRM + audit log.

**Two agent locations. That's it.** Stage 3 (parse unstructured) and Stage 6 (write justification). Everything else is the engine. Together they turn the firehose of public signals into a small, ranked, ready-to-act list of deals — twice a day, every day.
