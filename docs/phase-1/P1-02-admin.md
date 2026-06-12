# P1-02 — Core Product Objects (Admin Console)

| Field | Value |
|-------|-------|
| **Document ref** | P1-02-Admin |
| **Title** | Core Product Objects — Operator Console |
| **Version** | 1.1 |
| **Status** | Draft |
| **Last updated** | 2026-06-08 |
| **Audience** | Internal developers, operators |
| **Linear** | [GRO-267](https://linear.app/growthmaschine/issue/GRO-267) · Parent [GRO-265](https://linear.app/growthmaschine/issue/GRO-265) |
| **Workflow reference** | [P1-01-Admin](./P1-01-admin.md) |

---

## 1. Introduction

This document defines every main **thing** in the **NORAD Intel Engine Admin Console** (`apps/web`) and its backend (`apps/api`) — what it is, why it exists, and a realistic example.

It is the operator-facing half of **P1-02**. Analyst-application objects (Article, Pending Review, Watchlist) are in [P1-02-User](./P1-02-user.md). Both frontends share one backend; definitions are separate where UI labels differ.

**Per-object format:**

| Block | Purpose |
|-------|---------|
| **What** | Plain-language definition |
| **Why** | Why the product needs it |
| **Example** | Realistic NORAD scenario |
| **Not confused with** | Similar object — only when needed |
| **Backend** | Table, `source_kind`, or service (current repo) |
| **Where in UI** | Admin route or screen |
| **Status** | `Available` · `In progress` · `Planned` · `Not implemented` |

**AI Analysis** — §2 — is any LLM step in a pipeline, not a standalone persisted row type.

Relationships are answered in [P1-03](./P1-03.md).

**Dropped from product scope:** Today page (`/discover`), Discovery Clusters admin (`/discovery-clusters`), and their objects (`discovery_clusters`, `trend_articles`, `runs` · `discovery`) are legacy — not part of the target admin model. Web Discovery is the operator discovery path.

---

## 2. Cross-cutting concept — AI Analysis

| Attribute | Value |
|-----------|-------|
| **What** | Any pipeline step where Claude (Haiku or Sonnet) ranks, extracts, synthesises, or interprets data |
| **Why** | Converts raw Exa/Parallel/Diffbot output into scored articles, company cards, and signals |
| **Example** | Sonnet synthesises `CompanyCardV1` after engine fan-out; future Web Discovery post-run rank/summary |
| **Not confused with** | Exa vendor `summary`/`highlights` — vendor-side, not NORAD LLM |
| **Backend** | Logged in `engine_calls` where `vendor = anthropic` |
| **Status** | Available on Deep Research; **not** on Web Discovery post-run today (planned) |

| Pipeline | Stage | Model | Persisted to |
|----------|-------|-------|--------------|
| Web Discovery | Post-run | — | No NORAD LLM today (Exa only) — **planned** |
| Deep Research | Synthesise | Claude Sonnet 4.5 | `cards.card`, `signals` |

---

## 3. Object index

| # | Object | One-line meaning | Backend | Status |
|---|--------|------------------|---------|--------|
| 3.1 | Organization | Tenant owning all operator data | Planned | Planned |
| 3.2 | User | Person operating the console | — | Available |
| 3.3 | Web Discovery Cluster | Themed Exa search group | `web_discovery_clusters` | Available |
| 3.4 | Web Discovery Query | One Exa search in a cluster | `web_discovery_queries` | Available |
| 3.5 | Web Discovery Query Run | One execution of web discovery | `runs` · `web_discovery` | Available |
| 3.6 | Search Result | One Exa hit from a query run | `runs.engine_outputs` | Available |
| 3.7 | Deep Research Run | One company profiling execution | `runs` · `research` | Available |
| 3.8 | Company | Canonical company entity | `companies` | Available |
| 3.9 | Company Card | Versioned research profile blob | `cards` | Available |
| 3.10 | Research Signal | Structured signal on a card | `signals` | Available |
| 3.11 | Source | Citation backing card fields | `sources` | Available |
| 3.12 | Run Event | Pipeline stage log line | `run_events` | Available |
| 3.13 | Engine Call | One vendor API call audit row | `engine_calls` | Available |
| 3.14 | Research Config | Engine settings in app_kv | `app_kv` | Available |
| 3.15 | Web Result Escalation | Search result → deep research | via `runs` | Not implemented |

---

## 4. Platform objects

### 4.1 Organization

| | |
|--|--|
| **What** | Customer tenant owning clusters, runs, companies, and users |
| **Why** | Data isolation for multi-customer deployment |
| **Example** | BAT — all `web_discovery_clusters` and `companies` scoped to this org |
| **Not confused with** | **Company** (research target) |
| **Backend** | No `organizations` table today — single-tenant |
| **Where in UI** | Not exposed |
| **Status** | Planned |

### 4.2 User

| | |
|--|--|
| **What** | Operator running pipelines and reviewing results |
| **Why** | Audit trail; future permissions |
| **Example** | Operator triggers **Run All** on “Pouches” cluster |
| **Backend** | No auth user table — admin gate disabled in API |
| **Where in UI** | All admin routes |
| **Status** | Available (single-user tool) |

---

## 5. Web Discovery objects

### 5.1 Web Discovery Cluster

| | |
|--|--|
| **What** | Named group of Exa search queries the operator monitors |
| **Why** | Operators scope market intelligence by theme |
| **Example** | “Pouches” — keywords, geography, sources, signal priorities, paused/active |
| **Not confused with** | **Search Cluster** on analyst Settings ([P1-02-User §5.1](./P1-02-user.md)) — different UI label |
| **Backend** | `web_discovery_clusters` |
| **Where in UI** | `/discover-web` — list and command center |
| **Status** | Available |

### 5.2 Web Discovery Query

| | |
|--|--|
| **What** | One saved Exa search definition inside a Web Discovery Cluster |
| **Why** | Multiple search angles per theme |
| **Example** | “Nicotine pouch funding 2025 Canada” — search type, num results, content modes |
| **Not confused with** | **Web Discovery Query Run** — one execution |
| **Backend** | `web_discovery_queries` |
| **Where in UI** | Cluster → Queries tab → query editor |
| **Status** | Available |

### 5.3 Web Discovery Query Run

| | |
|--|--|
| **What** | One execution of one or all active queries in a cluster |
| **Why** | Produces fresh Exa hits for operator review |
| **Example** | **Run Query** on June 5 — single query; **Run All** — batch |
| **Not confused with** | **Deep Research Run** (§6.1) |
| **Backend** | `runs` where `source_kind = web_discovery` |
| **Where in UI** | Activity log → Results page; run selector for history |
| **Status** | Available |

### 5.4 Search Result

| | |
|--|--|
| **What** | One URL/document returned by Exa during a Web Discovery Query Run |
| **Why** | Raw material operators review before any analyst escalation |
| **Example** | PitchBook article URL, title, snippet, Exa score, highlights |
| **Not confused with** | **Article** on analyst News feed ([P1-02-User §5.3](./P1-02-user.md)) — enriched, scored news row |
| **Backend** | Slice of `runs.engine_outputs` per query |
| **Where in UI** | Web Discovery results page |
| **Status** | Available — post-run NORAD LLM not implemented |

---

## 6. Deep research objects

### 6.1 Deep Research Run

| | |
|--|--|
| **What** | One four-stage company profiling execution |
| **Why** | Produces one `CompanyCardV1` per target company |
| **Example** | Escalate from Web Discovery search result (target) or analyst +ADD |
| **Not confused with** | **Web Discovery Query Run** |
| **Backend** | `runs` + `services/research.py` · `source_kind = research` |
| **Where in UI** | Activity panel; `/runs/:id`; Companies profile history |
| **Status** | Available |

**Pipeline stages (reference):**

`Build input` → `Parallel + Exa + Diffbot fan-out` → `Sonnet synthesise` → `persist company/card/signals/sources`

### 6.2 Company

| | |
|--|--|
| **What** | Canonical company entity — name, domain, denormalised scores |
| **Why** | Stable id across multiple research runs and cards |
| **Example** | Ultra Pouches — domain takeultra.com — `canonical_card_id` pointer |
| **Not confused with** | **Company Card** (one research snapshot) |
| **Backend** | `companies` |
| **Where in UI** | `/companies` list and detail |
| **Status** | Available |

### 6.3 Company Card

| | |
|--|--|
| **What** | Versioned JSON research profile from one Deep Research Run |
| **Why** | Full `CompanyCardV1` contract with confidence and sources |
| **Example** | Card JSON — identity, funding, strategic fit, signals array |
| **Not confused with** | **Company Profile** on analyst UI — same data, analyst-facing label |
| **Backend** | `cards` — JSONB `card` column |
| **Where in UI** | Company detail sections; Research Evidence |
| **Status** | Available |

### 6.4 Research Signal

| | |
|--|--|
| **What** | One structured signal extracted into a Company Card |
| **Why** | Evidence-backed events for BD qualification |
| **Example** | GROWTH signal — “$11M Series A Jan 2026” — with source refs |
| **Not confused with** | **News Signal** on analyst feed ([P1-02-User §5.4](./P1-02-user.md)) |
| **Backend** | `signals` |
| **Where in UI** | Company detail → Signals section |
| **Status** | Available |

### 6.5 Source

| | |
|--|--|
| **What** | One citation row backing fields on a Company Card |
| **Why** | Traceability — confirmed fields require sources |
| **Example** | URL + title from Exa content used in synthesis |
| **Backend** | `sources` |
| **Where in UI** | Company detail → Sources section |
| **Status** | Available |

---

## 7. Pipeline infrastructure objects

### 7.1 Run Event

| | |
|--|--|
| **What** | One timestamped log line for a pipeline stage or milestone |
| **Why** | Live Activity feed and post-run audit |
| **Example** | `Stage 2 — Parallel OK ($2.500), Exa 5 reads ($0.028)` |
| **Backend** | `run_events` + `apps/api/logs/pipeline.jsonl` |
| **Where in UI** | Activity panel on research, web discovery |
| **Status** | Available |

### 7.2 Engine Call

| | |
|--|--|
| **What** | One audited vendor API call — request, response, cost, latency |
| **Why** | Cost control, debugging, compliance |
| **Example** | `vendor=anthropic`, `operation=synthesize_card`, `cost_usd=0.42` |
| **Backend** | `engine_calls` |
| **Where in UI** | Research Evidence expand; not a primary UI object |
| **Status** | Available |

### 7.3 Research Config

| | |
|--|--|
| **What** | Persisted engine settings — Parallel processor, Exa search type, timeouts |
| **Why** | Operators tune cost/quality without code changes |
| **Example** | Parallel `pro`, Exa `deep`, 5 results per query |
| **Backend** | `app_kv` keys e.g. `research_config` |
| **Where in UI** | Settings → Parallel / Exa / Diffbot |
| **Status** | Available |

---

## 8. Escalation objects

An **Escalation** is an operator **choice** that moves data into the next pipeline.

### 8.1 Web Result Escalation

| | |
|--|--|
| **What** | Operator promotes a Web Discovery Search Result into deep research or analyst review |
| **Why** | Completes Web Discovery workflow end state — primary admin discovery → research path |
| **Example** | Escalate Exa hit on company domain → `POST /api/research/runs` |
| **Not confused with** | Analyst **+ ADD Escalation** ([P1-02-User §8.1](./P1-02-user.md)) — different frontend, same research pipeline |
| **Backend** | Not implemented |
| **Where in UI** | Web Discovery results — target in [P1-01-Admin §3.2](./P1-01-admin.md) |
| **Status** | Not implemented |

---

## 9. Summary table

| Object | Meaning | Example |
|--------|---------|---------|
| Organization | Tenant | BAT |
| User | Operator | Console user |
| Web Discovery Cluster | Exa search theme | “Pouches” |
| Web Discovery Query | One Exa search | “Pouch funding Canada” |
| Web Discovery Query Run | One cluster/query execution | Run on June 5 |
| Search Result | One Exa hit | PitchBook URL + snippet |
| Deep Research Run | One company profile run | Escalate from result |
| Company | Canonical entity | takeultra.com |
| Company Card | Research JSON snapshot | CompanyCardV1 blob |
| Research Signal | Card signal row | Series A GROWTH |
| Source | Citation row | Exa URL ref |
| Run Event | Stage log line | Stage 2 OK |
| Engine Call | Vendor audit row | anthropic call |
| Research Config | Engine settings | Parallel pro |
| Web Result Escalation | Result → research | Escalate button |
| AI Analysis | LLM in pipeline | Sonnet synth (Web Discovery LLM planned) |

---

## 10. Relationship questions for P1-03

| # | Question |
|---|----------|
| 1 | Web Discovery Cluster ↔ analyst Search Cluster — merge or separate tables |
| 2 | Search Result ↔ analyst Article — transform pipeline or independent |
| 3 | Search Result ↔ analyst Article lifecycle — ingest path from Web Discovery to News feed |
| 4 | Company Card ↔ analyst Company Profile — 1:1 naming, version history |
| 5 | Deep Research Run ↔ Pending Review Item on user UI |
| 6 | Research Signal ↔ Company Signal on analyst UI |
| 7 | Run — single table for all `source_kind` values vs typed views |
| 8 | Company — merge pin/query rows into canonical company on complete |

**Answers:** [P1-03 §3](./P1-03.md#3-relationship-decisions-p1-02-11)

---

## 11. Completion checklist

| Item | Status |
|------|--------|
| All admin console objects defined | Done |
| Objects from P1-01-Admin covered | Done |
| Web Discovery vs Research runs separated | Done |
| Search Result vs analyst Article distinguished | Done |
| Today / Discovery Cluster objects removed (dropped) | Done |
| AI Analysis per pipeline documented | Done |
| Escalation objects per operator choice | Done |
| Backend table mapping included | Done |
| Relationship questions for P1-03 | Done |

---

## 12. Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Author | Huzaifa | 2026-06-08 | Draft |
| Reviewer | Shehrayar Haq | — | Pending |
