# P1-02 — Core Product Objects (Operator)

| Field | Value |
|-------|-------|
| **Document ref** | P1-02-Admin |
| **Title** | Core Product Objects — Operator perspective |
| **Version** | 2.0 |
| **Last updated** | 2026-06-19 |
| **Audience** | Internal developers, operators |
| **Controlling doc** | [P1-00 Overview](./phase-1-overview.md) |
| **Paired doc** | [P1-02-User](./P1-02-user.md) — same objects, analyst reading labels |
| **Workflow reference** | [P1-01-Admin](./P1-01-admin.md) |
| **Linear** | [GRO-267](https://linear.app/growthmaschine/issue/GRO-267) · Parent [GRO-265](https://linear.app/growthmaschine/issue/GRO-265) |

---

## 1. Introduction

This document defines every main **thing** in NORAD Intel Engine (`apps/web` + `apps/api`) from the **operator** perspective — what it is, why it exists, and a realistic example.

NORAD is **one application**. There is no separate admin console binary. This doc focuses on objects the operator configures, runs, and audits. The analyst-facing names for the same persisted rows are in [P1-02-User](./P1-02-user.md).

**Per-object format:**

| Block | Purpose |
|-------|---------|
| **What** | Plain-language definition |
| **Why** | Why the product needs it |
| **Example** | Realistic NORAD scenario |
| **Backend** | Table, `source_kind`, or service (current repo) |
| **Where in UI** | Route or screen |

**AI Analysis** (§2) is any LLM step in a pipeline — not a separate persisted row type.

Relationships are answered in [P1-03](./P1-03.md).

### 1.1 Section pairing (Admin ↔ User)

| Topic | This doc (Operator) | [P1-02-User](./P1-02-user.md) |
|-------|---------------------|-------------------------------|
| Web Discovery scope | Cluster, Query, Run | — (operator configures) |
| Enriched story | Article | Article / result card |
| Company intelligence | Company Card, Signal | Company Profile, Company Signal |
| Deep research trigger | Deep research action | Deep research action |

---

## 2. Cross-cutting concept — AI Analysis

| Attribute | Value |
|-----------|-------|
| **What** | Any pipeline step where Claude reads, extracts, or synthesises data |
| **Why** | Converts raw Exa / Parallel / Diffbot output into analyst-ready summaries and company cards |
| **Example** | Sonnet writes `executive_summary` and `mentioned_companies` after Exa ingest; Sonnet synthesises `CompanyCardV1` after engine fan-out |
| **Backend** | Logged in `engine_calls` where `vendor = anthropic` |

| Pipeline | Stage | Model | Persisted to |
|----------|-------|-------|--------------|
| Web Discovery | Enrich (per new article) | Claude Sonnet | `articles.summary`, `articles.mentioned_companies` (+ `company_id` each); **`companies` rows** (`origin=web_discovery`, `source_article_id`); mirrored in `runs.engine_outputs` |
| Deep Research | Synthesise | Claude Sonnet 4.5 | `cards.card`, `signals` |

**Not executed today:** per-query `system_prompt` / `output_schema` on `web_discovery_queries` — saved in DB only.

---

## 3. Object index

| # | Object | One-line meaning | Backend |
| --- | -------- | ------------------ | --------- |
| 3.1 | Organization | Tenant owning all data | — (deferred) |
| 3.2 | User | Person operating the app | — (no auth table) |
| 3.3 | Cluster | Themed Exa search group | `web_discovery_clusters` |
| 3.4 | Query | One Exa search in a cluster | `web_discovery_queries` |
| 3.5 | Run | One cluster/query execution | `runs` · `source_kind = web_discovery` |
| 3.6 | Search Result | One Exa hit from a run (run-scoped view) | slice of `runs.engine_outputs` |
| 3.7 | Article | Deduplicated ingested web story | `articles` |
| 3.8 | Deep Research Run | One company profiling execution | `runs` · `source_kind = research` |
| 3.9 | Company | Canonical company entity | `companies` |
| 3.10 | Company Card | Versioned research profile blob | `cards` |
| 3.11 | Research Signal | Structured signal on a card | `signals` |
| 3.12 | Source | Citation backing card fields | `sources` |
| 3.13 | Run Event | Pipeline stage log line | `run_events` |
| 3.14 | Engine Call | One vendor API call audit row | `engine_calls` |
| 3.15 | Research Config | Engine settings in `app_kv` | `app_kv` |
| 3.16 | Deep research trigger | User action: result → research run | via `POST /api/research/runs` |

---

## 4. Platform objects

### 4.1 Organization

| | |
|--|--|
| **What** | Customer tenant owning clusters, runs, companies, and users |
| **Why** | Data isolation for multi-customer deployment |
| **Example** | BAT — all `web_discovery_clusters` and `companies` scoped to this org |
| **Backend** | Single-tenant — no `organizations` table yet |
| **Where in UI** | Not exposed |

### 4.2 User

| | |
|--|--|
| **What** | Operator or analyst using the same app |
| **Why** | Future audit trail and permissions |
| **Example** | Operator triggers **Run All** on “Pouches” cluster |
| **Backend** | No auth user table — admin gate disabled in API |
| **Where in UI** | All routes |

---

## 5. Cluster, Query, Run, and Article

### 5.1 Cluster

| | |
|--|--|
| **What** | Named group of Exa search queries the operator monitors |
| **Why** | Operators scope market intelligence by theme |
| **Example** | “Pouches” — keywords, geography, sources, signal priorities, paused/active |
| **Backend** | `web_discovery_clusters` |
| **Where in UI** | `/discover-web` — list and command center |

### 5.2 Query

| | |
|--|--|
| **What** | One saved Exa search definition inside a Cluster |
| **Why** | Multiple search angles per theme |
| **Example** | “Nicotine pouch funding 2025 Canada” — search type, num results, content modes (`content_highlights`, `content_text`, `content_summary`) |
| **Backend** | `web_discovery_queries` |
| **Where in UI** | Cluster → Queries tab → query editor |

### 5.3 Run

| | |
|--|--|
| **What** | One execution of one or all active queries in a cluster |
| **Why** | Produces fresh Exa hits, ingests new articles, runs Sonnet enrich |
| **Example** | **Run Query** on June 5 — single query; **Run All** — batch |
| **Backend** | `runs` where `source_kind = web_discovery` |
| **Where in UI** | Activity log → Results page; run selector for history; `/runs/:id` |

**Pipeline (reference):** `Exa search → dedup → articles → Sonnet enrich → complete`

### 5.4 Search Result

| | |
|--|--|
| **What** | One URL/document returned by Exa during a Run — run-scoped JSON in `engine_outputs` |
| **Why** | Operator reviews what Exa returned for a specific run; API hydrates enrich fields from `articles` when `article_id` is set |
| **Example** | PitchBook article URL, title, snippet, Exa score, `executive_summary`, `mentioned_companies` |
| **Backend** | Slice of `runs.engine_outputs.queries[].results[]`; enrich fields from `articles` via results API |
| **Where in UI** | `/discover-web/.../queries/:queryId/results` |

A Search Result is **not** the same row as an Article. Duplicate URLs reuse the existing Article's summary (`ingest_status: duplicate`).

### 5.5 Article

| | |
|--|--|
| **What** | One deduplicated web story ingested from a Web Discovery run — canonical store for body text and Sonnet enrich |
| **Why** | URL-level dedup; durable enrichment survives across runs |
| **Example** | “Ultra Pouches raises $11M…” — `body_text`, Sonnet `summary`, `mentioned_companies[]` |
| **Backend** | `articles` — unique on `url`; FKs to `cluster_id`, `query_run_id`, `source_query_id` |
| **Where in UI** | Query results card — Executive summary, Companies in this story, Full article |

---

## 6. Deep research objects

### 6.1 Deep Research Run

| | |
|--|--|
| **What** | One four-stage company profiling execution |
| **Why** | Produces one `CompanyCardV1` per target company |
| **Example** | **Deep research** on “Ultra Pouches” from a Web Discovery result card |
| **Backend** | `runs` + `services/research.py` · `source_kind = research` (or legacy `user_query`) |
| **Where in UI** | Activity panel; `/runs/:id`; Companies feed and profile history |

**Pipeline stages (reference):**

`Build input` → `Parallel + Exa + Diffbot fan-out` → `Sonnet synthesise` → `persist company/card/signals/sources`

Runs in-process via `asyncio.create_task` — no separate worker.

### 6.2 Company

| | |
|--|--|
| **What** | Canonical company entity — name, domain, denormalised scores; **or** a lightweight Web Discovery mention before full profile |
| **Why** | Stable id from first Sonnet mention through Deep Research completion |
| **Example** | Ultra Pouches — first appears as `origin=web_discovery` from an article; after Deep Research → `origin=research`, `canonical_card_id` set |
| **Backend** | `companies` — unique on `domain` (nullable); unique on `(source_article_id, normalized_name)` for discovery rows |
| **Where in UI** | `/companies` **Profiles** tab (research feed) and **Discovered** tab (mention rows); `/companies/:id` detail |

### 6.3 Company Card

| | |
|--|--|
| **What** | Versioned JSON research profile from one Deep Research Run |
| **Why** | Full `CompanyCardV1` contract with confidence and sources |
| **Example** | Card JSON — identity, funding, strategic fit, signals array |
| **Backend** | `cards` — JSONB `card` column; `review_status` (`draft` default) |
| **Where in UI** | Company detail sections; Research Evidence |

Analyst label for the same row: **Company Profile** ([P1-02-User](./P1-02-user.md)).

### 6.4 Research Signal

| | |
|--|--|
| **What** | One structured signal extracted into a Company Card |
| **Why** | Evidence-backed events for BD qualification |
| **Example** | GROWTH signal — “$11M Series A Jan 2026” — with source refs |
| **Backend** | `signals` |
| **Where in UI** | Company detail → Signals section |

Analyst label: **Company Signal**.

### 6.5 Source

| | |
|--|--|
| **What** | One citation row backing fields on a Company Card |
| **Why** | Traceability — confirmed fields require sources |
| **Example** | URL + title from Exa content used in synthesis |
| **Backend** | `sources` — composite FK with `cards(id, company_id)` |
| **Where in UI** | Company detail → Sources section; Research Evidence expand |

---

## 7. Pipeline infrastructure objects

### 7.1 Run Event

| | |
|--|--|
| **What** | One timestamped log line for a pipeline stage or milestone |
| **Why** | Live Activity feed and post-run audit |
| **Example** | `Enrich — 3/5 articles analyzed` or `Stage 2 — Parallel OK ($2.500)` |
| **Backend** | `run_events` + `apps/api/logs/pipeline.jsonl` |
| **Where in UI** | Activity panel on research and cluster runs; `/runs/:id` SSE feed |

### 7.2 Engine Call

| | |
|--|--|
| **What** | One audited vendor API call — request, response, cost, latency |
| **Why** | Cost control, debugging, compliance |
| **Example** | `vendor=anthropic`, `operation=analyze_article`, `cost_usd=0.04` |
| **Backend** | `engine_calls` |
| **Where in UI** | Research Evidence expand |

### 7.3 Research Config

| | |
|--|--|
| **What** | Persisted engine settings — Parallel processor, Exa search type, Diffbot toggle |
| **Why** | Operators tune Deep Research cost/quality without code changes |
| **Example** | Parallel `pro`, Exa `deep`, 5 results per query |
| **Backend** | `app_kv` key `research_config` |
| **Where in UI** | `/settings` → Parallel / Exa / Diffbot |

**Scope:** Research pipeline only. Web Discovery Exa params live on each Query row.

---

## 8. User actions (not persisted row types)

These are **choices** that spawn runs or update state. None are standalone tables.

### 8.1 Deep research trigger

| | |
|--|--|
| **What** | User starts Deep Research from a company mentioned in a Web Discovery result or the **Discovered** tab |
| **Why** | Primary discovery → research path |
| **Example** | Click **Deep research** on “Ultra Pouches” in Companies in this story → `POST /api/research/runs` |
| **Backend** | New `runs` row · `source_kind = research` |
| **Where in UI** | Query results — [P1-01-Admin §2.6](./P1-01-admin.md), [P1-01-User §2](./P1-01-user.md) |

**Also triggers Deep Research:** Companies page manual add, direct API call with `company_name` + optional `domain_hint`.

**Not implemented on results UI:** article-level Save, Dismiss (API `POST .../articles/:id/dismiss` exists; no frontend caller).

---

## 9. Summary table

| Object | Meaning | Example |
|--------|---------|---------|
| Organization | Tenant | BAT |
| User | App user | Console user |
| Cluster | Exa search theme | “Pouches” |
| Query | One Exa search | “Pouch funding Canada” |
| Run | One cluster/query execution | Run on June 5 |
| Search Result | One Exa hit (run-scoped) | PitchBook URL + snippet |
| Article | Deduplicated ingested story | Summary + companies + body |
| Deep Research Run | One company profile run | Deep research from result |
| Company | Canonical entity | takeultra.com |
| Company Card | Research JSON snapshot | CompanyCardV1 blob |
| Research Signal | Card signal row | Series A GROWTH |
| Source | Citation row | Exa URL ref |
| Run Event | Stage log line | Enrich 3/5 OK |
| Engine Call | Vendor audit row | anthropic call |
| Research Config | Engine settings | Parallel pro |
| Deep research trigger | Result → research | Deep research button |
| AI Analysis | LLM in pipeline | Sonnet enrich; Sonnet synth |

---

## 10. Relationship questions for P1-03

| # | Question |
|---|----------|
| 1 | Search Result ↔ Article — same row or separate? |
| 2 | Article lifecycle — when is a row created vs reused? |
| 3 | Company Card ↔ Company Profile — same data? |
| 4 | Deep Research Run ↔ Pending Review (Phase 2) |
| 5 | Research Signal ↔ Company Signal |
| 6 | Run — single table for all `source_kind` values |
| 7 | Company — merge on complete; domain dedupe |
| 8 | Results API — hydration from `articles` |

**Answers:** [P1-03 §3](./P1-03.md#3-relationship-decisions-p1-02-10)

---

## 11. Phase 2 — planned objects (not built)

Do not document these as current behaviour. Listed for naming continuity with legacy P1 drafts.

| Object | Notes |
|--------|-------|
| Pending Review Item | Queue view on `cards.review_status = draft` — no UI |
| Watchlist Entry | `companies.is_watchlisted` mentioned in phase2test — no UI |
| News Signal | Feed signal on Article — no News feed |
| Opportunity | Weekly digest card — no Home Top |
| Monitoring Rule | Signal filter rules — no Settings UI |
| Promote / Dismiss (card) | `review_status` accepts/rejects — no UI |

---

## 12. Completion checklist

| Item |
| ------ |
| All operator objects defined for current app |
| Objects from P1-01-Admin covered |
| Cluster vs Research runs separated |
| Search Result vs Article distinguished |
| Article + Sonnet enrich documented |
| AI Analysis per pipeline documented |
| Deep research trigger (not “Escalate”) |
| Backend table mapping included |
| Phase 2 objects explicitly deferred |
| Relationship questions for P1-03 |

---

## 13. Approval

| Role | Name | Date |
| ------ | ------ | ------ |
| Author | Huzaifa | 2026-06-19 |
| Reviewer | Shehrayar Haq | — |
