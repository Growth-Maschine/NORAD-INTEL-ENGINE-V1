# P1-04 — Required Fields

| Field | Value |
|-------|-------|
| **Document ref** | P1-04 |
| **Title** | Required Fields per Object — Admin Console & Analyst App |
| **Version** | 2.1 |
| **Status** | Draft |
| **Last updated** | 2026-06-16 |
| **Audience** | Internal developers, operators · BAT stakeholders, analysts (Part III) |
| **Linear** | [GRO-269](https://linear.app/growthmaschine/issue/GRO-269/40-define-required-fields-for-each-core-object) · Parent [GRO-265](https://linear.app/growthmaschine/issue/GRO-265) |
| **Object reference** | [P1-02-Admin](./P1-02-admin.md) · [P1-02-User](./P1-02-user.md) · [P1-03](./P1-03.md) |
| **Screen mapping** | [P1-05-Admin](./P1-05-admin.md) · [P1-05-User](./P1-05-user.md) |
| **Backend actions** | [P1-06](./P1-06.md) |

---

## 1. Introduction

Single field-level spec for the whole NORAD data model. Companion to [P1-03](./P1-03.md) (relationships).

| Part | Sections | Audience | Content |
|------|----------|----------|---------|
| **I — Admin Console** | §2–§8 | Operators, backend | Postgres columns, enums, FKs, implemented vs planned |
| **II — Schema diagrams** | §9 | Engineering | Master ER, flows, `runs` polymorphism, composite FKs |
| **III — Analyst App** | §10–§18 | BAT, product, analysts | Product-language fields, UI visibility, object flow |

Shared objects (`companies`, `cards`, `signals`, `runs`) appear in **both** Part I (full schema) and Part III (analyst-visible subset).

**Global conventions**

| Rule | Decision |
|------|----------|
| `organization_id` | **Omitted** until multi-tenant ships |
| Part I Notes | `Implemented` · `Planned` · `Gap` vs `apps/api/app/models/` |
| Part III Notes | `Available` · `In progress` · `Planned` (matches P1-02-User) |
| Non-table objects | Views and actions — fields on parent tables |
| AI Analysis | Not a table — fields on parent objects |

**Cluster · Query · Run — read this first**

Every discovery path uses the same three levels. Names differ by app; **do not swap them**.

| Level | Meaning | Operator (Admin console) | Analyst app (planned) |
|-------|---------|--------------------------|------------------------|
| **Cluster** | Themed group — holds many saved searches | **Discovery Cluster** · table `web_discovery_clusters` | **Search Cluster** · table `search_clusters` |
| **Query** | One saved Exa search inside a cluster | **Discovery Query** · table `web_discovery_queries` | **Search Query** · table `search_queries` |
| **Run** | One execution (Run Query or Run All) | **Discovery Run** · `runs` where `source_kind = web_discovery` | **Query Run** · same `runs` table, analyst `engines` metadata |

| Common mistake | Correct reading |
|----------------|-----------------|
| “Web query” | Means **Discovery Query** (operator) or **Search Query** (analyst) — never a cluster |
| “Cluster query” | The **Query** inside a **Cluster** — two words, two objects |
| “Web discovery cluster” | Product name is **Discovery Cluster**; `web_discovery_` is only the Postgres table prefix |

**Part I table columns**

| Column | Meaning |
|--------|---------|
| Field | Column or JSON path |
| Type | Postgres-oriented type |
| Required | Yes / No |
| Searchable | Yes / No |
| UI | Where shown, or Internal only |
| Notes | Enum values, FK, implemented status |

**Part III table columns**

| Column | Meaning |
|--------|---------|
| Field | Name of the stored attribute |
| Type | Data shape (text, number, date, list, etc.) |
| Required | Must be present for the object to be valid |
| Searchable | Can be used in search or filters |
| UI | Screen or control (`—` = not shown) |
| Notes | Status and short context |

---

## Part I — Admin Console (Operator)

Object definitions: [P1-02-Admin](./P1-02-admin.md). Workflows: [P1-01-Admin](./P1-01-admin.md).

---

## 2. Platform objects

### 2.1 Organization *(planned — MVP single-tenant)*

No table in MVP. Documented for post-MVP schema design.

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | Primary key · **Planned** |
| name | string(255) | Yes | Yes | Internal | Tenant display name · **Planned** |
| slug | string(120) | Yes | Yes | Internal | Unique tenant key · **Planned** |
| created_at | timestamptz | Yes | No | Internal | **Planned** |
| updated_at | timestamptz | Yes | No | Internal | **Planned** |

### 2.2 User *(planned — MVP single-user)*

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | **Planned** — no auth user table today |
| email | string(255) | Yes | Yes | Settings profile | **Planned** |
| display_name | string(120) | No | Yes | Sidebar profile | **Planned** |
| role | enum (`operator`, `admin`) | Yes | No | Internal | Admin console access · **Planned** |
| created_at | timestamptz | Yes | No | Internal | **Planned** |
| updated_at | timestamptz | Yes | No | Internal | **Planned** |

---

## 3. Operator discovery objects

Admin console only. Object names below are **product terms**; Postgres table names are in each section header.

### 3.1 Discovery Cluster

Table: `web_discovery_clusters` · **Implemented**

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| name | string(140) | Yes | Yes | Cluster list, command center header | |
| slug | string(160) | Yes | Yes | Internal | Unique; URL segment · **Implemented** |
| description | text | No | No | Cluster settings | |
| priority | enum (`P1 Critical`, `P2 Daily Intelligence`, `P3 Weekly Monitoring`) | Yes | Yes | Cluster list badge | Default `P2 Daily Intelligence` |
| is_active | boolean | Yes | Yes | Cluster list status | Paused clusters cannot run |
| include_keywords | JSON array[string] | Yes | No | Cluster settings | Scope tags |
| exclude_keywords | JSON array[string] | Yes | No | Cluster settings | |
| geography_focus | JSON array[string] | Yes | No | Cluster settings | |
| source_preferences | JSON array[string] | Yes | No | Cluster settings | |
| signal_priorities | JSON array[string] | Yes | No | Cluster settings | |
| query_count | integer | Yes | No | Cluster list stat | Denormalized · ≥ 0 |
| signal_count | integer | Yes | No | Cluster list stat | Denormalized · ≥ 0 · **Gap**: not populated today |
| last_run_at | timestamptz | No | Yes | Cluster list | Last successful run |
| created_at | timestamptz | Yes | No | Cluster metadata | |
| updated_at | timestamptz | Yes | No | Internal | |

### 3.2 Discovery Query

Table: `web_discovery_queries` · **Implemented** · belongs to exactly one Discovery Cluster (`cluster_id`)

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| cluster_id | UUID | Yes | No | Internal | FK → `web_discovery_clusters.id` CASCADE |
| label | string(160) | Yes | Yes | Query list, editor title | Display name for this query (not the Exa string) |
| search_query | text | Yes | Yes | Query editor | The Exa search string sent on Run |
| search_type | enum (`auto`, `fast`, `deep`, `deep-lite`, `deep-reasoning`, `instant`) | Yes | No | Query editor | Default `auto` |
| num_results | integer | Yes | No | Query editor | 1–100 · default 10 |
| is_active | boolean | Yes | Yes | Query list | Inactive skipped on Run All |
| content_highlights | boolean | Yes | No | Query editor | Exa contents mode |
| content_text | boolean | Yes | No | Query editor | |
| content_summary | boolean | Yes | No | Query editor | |
| structured_outputs | boolean | Yes | No | Query editor | **Gap**: stored, not executed |
| highlights_max_chars | integer | No | No | Query editor | |
| highlights_guiding_query | text | No | No | Query editor | |
| text_max_chars | integer | No | No | Query editor | |
| text_main_content_only | boolean | Yes | No | Query editor | |
| summary_max_chars | integer | No | No | Query editor | |
| system_prompt | text | No | No | Query editor | **Gap**: not executed post-run |
| output_schema | JSON object | No | No | Query editor | **Gap**: not executed post-run |
| livecrawl_timeout_ms | integer | Yes | No | Query editor | Default 10000 |
| max_age_hours | integer | No | No | Query editor | -1 = no limit |
| subpages | integer | Yes | No | Query editor | |
| extra_links | integer | Yes | No | Query editor | |
| extra_image_links | integer | Yes | No | Query editor | |
| subpage_target_keywords | JSON array[string] | Yes | No | Query editor | |
| category | string(80) | No | No | Query editor | Exa category filter |
| user_location | string(8) | No | No | Query editor | ISO country |
| include_domains | JSON array[string] | Yes | No | Query editor | |
| exclude_domains | JSON array[string] | Yes | No | Query editor | |
| published_after | date | No | No | Query editor | |
| published_before | date | No | No | Query editor | |
| crawled_after | date | No | No | Query editor | |
| crawled_before | date | No | No | Query editor | |
| content_moderation | boolean | Yes | No | Query editor | |
| stream_response | boolean | Yes | No | Internal | |
| additional_queries | JSON array[string] | Yes | No | Query editor | |
| created_at | timestamptz | Yes | No | Query metadata | |
| updated_at | timestamptz | Yes | No | Internal | |

### 3.3 Discovery Run

Table: `runs` where `source_kind = web_discovery` · **Implemented** · executes one or more Discovery Queries from a cluster

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| source_kind | string(32) | Yes | Yes | Internal | Always `web_discovery` for operator discovery |
| query | text | Yes | No | Activity log | Run label — cluster name or batch context |
| status | enum (`queued`, `researching`, `synthesizing`, `completed`, `failed`, `cancelled`) | Yes | Yes | Results page, Activity | Discovery runs: `queued` → `completed` / `failed` |
| progress_pct | integer | Yes | No | Activity | 0–100 |
| error | text | No | No | Results error banner | |
| engines | JSON object | Yes | No | Internal | Snapshot: `cluster_id`, `query_ids`, Exa config |
| engine_outputs | JSON object | Yes | No | Internal | Per-query result slices — see §3.4 |
| idempotency_key | string(64) | No | No | Internal | Unique when set |
| started_at | timestamptz | No | Yes | Activity, run selector | |
| completed_at | timestamptz | No | Yes | Run selector | |
| company_id | UUID | No | No | Internal | Null for discovery runs |
| card_id | UUID | No | No | Internal | Null for discovery runs |
| created_at | timestamptz | Yes | Yes | Run history | |
| updated_at | timestamptz | Yes | No | Internal | |

**`engine_outputs` slice per query (internal shape)**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| query_id | UUID | Yes | FK to `web_discovery_queries.id` |
| query_label | string | No | Denormalized |
| result_count | integer | Yes | |
| results | JSON array | Yes | Array of Search Result objects §3.4 |
| latency_ms | float | No | |
| cost_usd | float | No | |

### 3.4 Search Result

**Not a table row today** — object inside `runs.engine_outputs[].results[]`. Target: optional future `search_results` table; MVP keeps JSON embed.

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| url | text | Yes | Yes | Results page link | Primary identity |
| exa_id | string | No | No | Internal | Exa document id · **Implemented** |
| title | string | No | Yes | Results page title | |
| snippet | text | No | Yes | Results page excerpt | |
| published_date | string (ISO date) | No | Yes | Results metadata | |
| score | float | No | Yes | Results sort | Exa relevance |
| highlights | JSON array[string] | No | No | Results expand | |
| summary | text | No | Yes | Results expand | Exa vendor summary |
| text | text | No | No | Internal | Full body when content_text enabled |
| image | string (URL) | No | No | Results thumbnail | **Planned** UI |
| favicon | string (URL) | No | No | Results row | |
| author | string | No | No | Results metadata | |
| relevance_score | integer | No | Yes | Results sort | **Planned** — NORAD LLM 0–100 |
| relevance_reason | text | No | No | Results expand | **Planned** — NORAD LLM |
| extracted_signals | JSON array | No | Yes | Results signals column | **Planned** — post-run AI |
| source_run_id | UUID | Yes | No | Internal | Parent run · when promoted to row |
| source_query_id | UUID | Yes | No | Internal | Parent query |

---

## 4. Deep research objects

### 4.1 Deep Research Run

Table: `runs` where `source_kind = research` · **Implemented**

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| source_kind | string(32) | Yes | Yes | Internal | `research` (also `user_query` on older rows — same pipeline) |
| query | text | Yes | Yes | Companies Activity | Company name / URL input |
| status | enum (see §3.3) | Yes | Yes | Companies row pill | `researching` → `synthesizing` → `completed` |
| progress_pct | integer | Yes | No | Activity | |
| error | text | No | No | Activity error | |
| engines | JSON object | Yes | No | Internal | Parallel/Exa/Diffbot config snapshot |
| engine_outputs | JSON object | Yes | No | Research Evidence | Raw vendor payloads |
| company_id | UUID | No | Yes | Companies list | Set on complete |
| card_id | UUID | No | No | Internal | Set on complete |
| idempotency_key | string(64) | No | No | Internal | |
| started_at | timestamptz | No | Yes | Activity | |
| completed_at | timestamptz | No | Yes | Profile history | |
| created_at | timestamptz | Yes | Yes | Profile history | |
| updated_at | timestamptz | Yes | No | Internal | |

**Target provenance fields (in `engines` JSON today — optional dedicated columns later)**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| source_search_result_url | string | No | Operator escalate from Search Result · **Planned** |
| source_web_discovery_run_id | UUID | No | Parent Discovery Run · **Planned** |

### 4.2 Company

Table: `companies` · **Implemented**

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| company_name | string(255) | Yes | Yes | Companies list, detail header | |
| domain | string(255) | No | Yes | Company header | Lowercase apex; unique dedupe key |
| legal_entity_name | string(255) | No | Yes | Company detail | |
| website | text | No | No | Company detail | |
| logo_url | text | No | No | Company row | |
| industry | string(128) | No | Yes | Companies filter | Denormalized from canonical card |
| category | string(128) | No | Yes | Companies filter | |
| status | string(32) | No | Yes | Companies list | **Planned**: `watchlisted`, `saved`, etc. |
| headquarters_country | string(64) | No | Yes | Company detail | |
| canonical_card_id | UUID | No | No | Internal | Composite FK with `id` |
| is_watchlisted | boolean | No | Yes | Watchlist tab filter | **Planned** — or separate `watchlist_entries` |
| created_at | timestamptz | Yes | Yes | Company metadata | |
| updated_at | timestamptz | Yes | No | Internal | |

### 4.3 Company Card

Table: `cards` · **Implemented** · JSON contract: `CompanyCardV1` in `apps/api/app/schemas/`

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| company_id | UUID | Yes | No | Internal | FK → `companies.id` CASCADE |
| run_id | UUID | No | No | Internal | FK → `runs.id` SET NULL |
| schema_version | string(16) | Yes | No | Internal | Default `1.0` |
| card | JSONB | Yes | Yes (JSON) | Company detail tabs | Full `CompanyCardV1` — see schema, not duplicated here |
| score_overall | integer | No | Yes | Companies list sort | 0–100 denormalized |
| score_growth | integer | No | Yes | Internal | Sort/filter |
| score_momentum | integer | No | Yes | Internal | |
| score_fundraising | integer | No | Yes | Internal | |
| score_acquisition | integer | No | Yes | Internal | |
| score_partnership_fit | integer | No | Yes | Internal | |
| score_strategic_fit | integer | No | Yes | Internal | |
| score_risk | integer | No | Yes | Internal | |
| review_status | enum (`draft`, `accepted`, `rejected`, `archived`) | Yes | Yes | Pending review queue | `draft` = in analyst queue |
| reviewer_notes | text | No | No | Internal | |
| created_at | timestamptz | Yes | Yes | Profile history | |
| updated_at | timestamptz | Yes | No | Internal | |

**`card` JSONB** — document structure in `docs/backend-pipeline.md` and `apps/api/app/schemas/company_card.py`. P1-04 does not duplicate `Valued[]` blocks.

### 4.4 Research Signal

Table: `signals` · **Implemented** · Analyst label: Company Signal

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| company_id | UUID | Yes | Yes | Internal | FK → `companies.id` |
| card_id | UUID | Yes | No | Internal | Composite FK with company_id |
| type | enum (`growth`, `fundraising`, `acquisition`, `partnership`, `risk`, `strategic`) | Yes | Yes | Signals section | |
| subtype | string(64) | No | Yes | Signals section | |
| headline | text | Yes | Yes | Signals timeline | |
| evidence | text | No | Yes | Signals expand | |
| weight | integer | Yes | Yes | Signals sort | 1–10 |
| signal_date | date | No | Yes | Signals timeline | |
| source_refs | JSON array | Yes | No | Internal | `[source.local_id, ...]` |
| created_at | timestamptz | Yes | No | Internal | |
| updated_at | timestamptz | Yes | No | Internal | |

### 4.5 Source

Table: `sources` · **Implemented**

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| company_id | UUID | Yes | No | Internal | FK → `companies.id` |
| card_id | UUID | Yes | No | Internal | Composite FK |
| local_id | integer | Yes | No | Internal | Id inside `card.sources` array |
| url | text | Yes | Yes | Sources section | |
| title | text | No | Yes | Sources section | |
| type | string(64) | No | Yes | Sources section | |
| trust_tier | string(2) | No | Yes | Sources section | e.g. `A`, `B` |
| date_published | date | No | Yes | Sources section | |
| date_found | date | No | No | Internal | |
| last_checked | date | No | No | Internal | |
| snippet | text | No | Yes | Sources expand | |
| freshness_score | float | No | No | Internal | |
| created_at | timestamptz | Yes | No | Internal | |
| updated_at | timestamptz | Yes | No | Internal | |

---

## 5. Pipeline infrastructure objects

### 5.1 Run Event

Table: `run_events` · **Implemented**

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| run_id | UUID | Yes | No | Internal | FK → `runs.id` CASCADE |
| kind | string(48) | Yes | Yes | Activity feed | `stage_completed`, `engine_call`, `log`, … |
| message | text | Yes | Yes | Activity feed | |
| level | enum (`info`, `warning`, `error`) | Yes | No | Activity styling | |
| meta | JSON object | Yes | No | Internal | Stage stats, costs |
| created_at | timestamptz | Yes | No | Activity timestamp | |
| updated_at | timestamptz | Yes | No | Internal | |

### 5.2 Engine Call

Table: `engine_calls` · **Implemented**

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| run_id | UUID | No | Yes | Research Evidence | FK → `runs.id` SET NULL |
| vendor | enum (`exa`, `anthropic`, `parallel`, `diffbot`) | Yes | Yes | Evidence expand | |
| operation | string(64) | Yes | Yes | Evidence expand | e.g. `synthesize_card` |
| model | string(64) | No | No | Evidence expand | |
| processor | string(32) | No | No | Evidence expand | Parallel tier |
| units | integer | Yes | No | Internal | |
| input_tokens | integer | Yes | No | Evidence | |
| output_tokens | integer | Yes | No | Evidence | |
| cost_usd | float | Yes | Yes | Activity cost lines | |
| latency_ms | float | Yes | No | Evidence | |
| status | enum (`ok`, `error`, `timeout`) | Yes | Yes | Evidence | |
| error | text | No | No | Evidence | |
| request_snapshot | JSON object | Yes | No | Internal | Truncated · secrets stripped |
| response_snapshot | JSON object | Yes | No | Internal | Truncated |
| created_at | timestamptz | Yes | Yes | Evidence | |
| updated_at | timestamptz | Yes | No | Internal | |

### 5.3 Research Config

Store: `app_kv` key `research_config` · **Implemented** · Affects **deep research runs only**

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| parallel_processor | enum (`lite`, `base`, `core`, `pro`, `ultra`, `ultra2x`, `ultra4x`, `ultra8x`) | Yes | No | Settings → Parallel | |
| parallel_timeout_s | integer | Yes | No | Settings | 60–3600 |
| exa_search_type | enum (`auto`, `fast`, `neural`, `keyword`, `deep`) | Yes | No | Settings → Exa | |
| exa_deep_model | string | No | No | Settings → Exa | When search_type = deep |
| exa_num_results | integer | Yes | No | Settings → Exa | 1–50 |
| diffbot_enabled | boolean | Yes | No | Settings → Diffbot | |
| diffbot_score_threshold | float | Yes | No | Settings → Diffbot | 0.0–1.0 |

---

## 6. Run polymorphism note

All run types share `runs` columns (§3.3, §4.1). Discriminator: `source_kind`.

| `source_kind` | Product object | Status |
|---------------|----------------|--------|
| `web_discovery` | Discovery Run (operator or analyst Exa ingest) | **Implemented** |
| `research` | Deep Research Run | **Implemented** |
| `user_query` | Deep Research Run (older discriminator — same as `research`) | **Implemented** |

---

## 7. AI Analysis — fields on parent objects

Not a table. Post-pipeline LLM output columns:

| Parent | Field | Type | Required | UI | Status |
|--------|-------|------|----------|-----|--------|
| Search Result | relevance_score | integer | No | Results sort | **Planned** |
| Search Result | relevance_reason | text | No | Results expand | **Planned** |
| Search Result | extracted_signals | JSON array | No | Results signals | **Planned** |
| Company Card | card (synthesis) | JSONB | Yes | Company detail | **Implemented** — Sonnet |
| `engine_calls` | (audit row) | — | — | Research Evidence | **Implemented** per LLM call |

---

## 8. Non-table objects (actions and views)

### 8.1 Operator result escalation

**No table.** Operator action on a Search Result from a Discovery Run.

| Concept | Persisted as | Notes |
|---------|--------------|-------|
| Escalate click | New `runs` row `source_kind=research` | **Planned** — provenance in `engines` JSON |
| Source URL / company hint | `runs.query` + engines metadata | |

### 8.2 Pending Review Item *(analyst queue — documented for shared backend)*

**View** — not a table. Row appears when `cards.review_status = draft`.

| Field shown | Source table.column |
|-------------|---------------------|
| company_name | `companies.company_name` |
| domain | `companies.domain` |
| summary | `cards.card` JSON excerpt |
| origin_label | `engines` / article provenance · **Planned** |
| review_status | `cards.review_status` |
| run_id | `cards.run_id` |

---

## Part II — Database schema diagrams

Visual layer on top of Part I field tables and [P1-03](./P1-03.md) (relationships). Analyst product flow: **§18**.

---

## 9. Database schema diagrams

### 9.1 How to read

| Symbol / label | Meaning |
|----------------|---------|
| **Solid line** | FK exists (implemented) or planned in target schema |
| **Dotted line** | Logical link — JSON embed, view, or provenance |
| 🟢 | Table exists in repo |
| 🔵 | Planned — not migrated yet |
| ⬜ | View or derived — not a table |

**MVP:** No `organizations` or `organization_id` until multi-tenant. **Single `runs` table** — `source_kind` plus `engines` JSON discriminates operator Discovery Runs vs analyst Query Runs (both may use `web_discovery`).

### 9.2 Master schema — all tables (target)

```mermaid
erDiagram
    organizations {
        uuid id PK
        string name
        string slug UK
        timestamptz created_at
    }

    users {
        uuid id PK
        string email UK
        string display_name
        string role
        timestamptz created_at
    }

    web_discovery_clusters {
        uuid id PK
        string name
        string slug UK
        boolean is_active
        jsonb include_keywords
        jsonb signal_priorities
        timestamptz last_run_at
    }

    web_discovery_queries {
        uuid id PK
        uuid cluster_id FK
        string label
        text search_query
        string search_type
        int num_results
        boolean is_active
    }

    search_clusters {
        uuid id PK
        string name
        string slug UK
        jsonb include_keywords
        boolean is_active
        timestamptz last_run_at
    }

    search_queries {
        uuid id PK
        uuid cluster_id FK
        string name
        text query_text
        boolean is_active
    }

    articles {
        uuid id PK
        text url UK
        string title
        text summary
        timestamptz published_at
        uuid cluster_id FK
        uuid query_run_id FK
        int priority_score
        string status
    }

    article_signals {
        uuid id PK
        uuid article_id FK
        string signal_type
        int score
    }

    monitoring_rules {
        uuid id PK
        string name
        jsonb signal_types
        int min_score
        string target_surface
        boolean is_active
    }

    watchlist_entries {
        uuid id PK
        uuid company_id FK
        uuid user_id FK
        timestamptz promoted_at
    }

    runs {
        uuid id PK
        string source_kind
        text query
        string status
        int progress_pct
        jsonb engines
        jsonb engine_outputs
        uuid company_id FK
        uuid card_id FK
        timestamptz started_at
        timestamptz completed_at
    }

    companies {
        uuid id PK
        string company_name
        string domain UK
        uuid canonical_card_id FK
        boolean is_watchlisted
        string industry
    }

    cards {
        uuid id PK
        uuid company_id FK
        uuid run_id FK
        jsonb card
        string review_status
        int score_overall
    }

    signals {
        uuid id PK
        uuid company_id FK
        uuid card_id FK
        string type
        text headline
        int weight
        date signal_date
    }

    sources {
        uuid id PK
        uuid company_id FK
        uuid card_id FK
        int local_id
        text url
        string trust_tier
    }

    run_events {
        uuid id PK
        uuid run_id FK
        string kind
        text message
        jsonb meta
    }

    engine_calls {
        uuid id PK
        uuid run_id FK
        string vendor
        string operation
        float cost_usd
        string status
    }

    app_kv {
        string key PK
        jsonb value
    }

    organizations ||--o{ users : has
    organizations ||--o{ web_discovery_clusters : owns
    organizations ||--o{ search_clusters : owns
    organizations ||--o{ companies : owns
    organizations ||--o{ monitoring_rules : owns

    web_discovery_clusters ||--o{ web_discovery_queries : contains
    search_clusters ||--o{ search_queries : contains

    web_discovery_queries }o--o{ runs : executes
    search_queries }o--o{ runs : executes

    runs ||--o{ run_events : logs
    runs ||--o{ engine_calls : audits
    runs ||--o| companies : resolves
    runs ||--o| cards : produces

    companies ||--o{ cards : versions
    companies ||--o| cards : canonical_card
    companies ||--o{ signals : has
    companies ||--o{ sources : has
    companies ||--o{ watchlist_entries : watchlisted

    cards ||--o{ signals : extracts
    cards ||--o{ sources : cites

    search_clusters ||--o{ articles : ingests
    runs ||--o{ articles : ingests
    articles ||--o{ article_signals : tags

    users ||--o{ watchlist_entries : promoted_by
```

> `companies.canonical_card_id` and `signals` / `sources` use **composite FKs** with `(card_id, company_id)` — simplified above. See §9.6.

### 9.3 Implemented schema today

```mermaid
erDiagram
    web_discovery_clusters ||--o{ web_discovery_queries : cluster_id

    web_discovery_queries }o..o{ runs : "engine_outputs JSON only"

    runs ||--o{ run_events : run_id
    runs ||--o{ engine_calls : run_id
    runs }o--o| companies : company_id
    runs }o--o| cards : card_id

    companies ||--o{ cards : company_id
    companies |o--o| cards : "canonical_card_id composite"

    cards ||--o{ signals : "card_id plus company_id"
    cards ||--o{ sources : "card_id plus company_id"

    app_kv {
        string key PK
        jsonb value
    }
```

| Table | Status |
|-------|--------|
| `web_discovery_clusters` | 🟢 Live |
| `web_discovery_queries` | 🟢 Live |
| `runs` | 🟢 Live |
| `companies` | 🟢 Live |
| `cards` | 🟢 Live |
| `signals` | 🟢 Live |
| `sources` | 🟢 Live |
| `run_events` | 🟢 Live |
| `engine_calls` | 🟢 Live |
| `app_kv` | 🟢 Live |

### 9.4 Diagram by product area

#### Discovery (operator)

```mermaid
flowchart TB
    subgraph Tables["Postgres tables"]
        DC[Discovery Cluster<br/>web_discovery_clusters]
        DQ[Discovery Query<br/>web_discovery_queries]
        RUNS[(Discovery Run<br/>runs)]
    end

    subgraph JSON["Inside runs.engine_outputs"]
        SLICE["per-query slice"]
        SR["results array"]
        ITEM["Search Result objects"]
    end

    DC -->|cluster_id CASCADE| DQ
    DQ -->|Run Query / Run All| RUNS
    RUNS --> SLICE
    SLICE --> SR
    SR --> ITEM

    ITEM -.->|Escalate planned| RUNS2[(runs source_kind=research)]
```

Search Results are **not rows** — JSON inside `engine_outputs`. Optional future: `search_results` table.

#### Deep Research (shared)

```mermaid
flowchart TB
    RUNS[(runs source_kind=research)]
    CO[companies]
    CARD[cards]
    SIG[signals]
    SRC[sources]
    EV[run_events]
    EC[engine_calls]

    RUNS -->|company_id| CO
    RUNS -->|run_id| CARD
    CARD -->|company_id CASCADE| CO
    CO -->|canonical_card_id| CARD
    CARD --> SIG
    CARD --> SRC
    RUNS --> EV
    RUNS --> EC

    CARD -->|review_status=draft| PR[[Pending Review VIEW]]
    PR -->|Promote| WL[watchlist_entries planned]
```

#### Analyst News feed (planned)

```mermaid
flowchart TB
    SC[search_clusters]
    SQ[search_queries]
    RUNS[(runs source_kind=web_discovery)]
    ART[articles]
    NS[article_signals]
    MR[monitoring_rules]
    OPP[[Opportunity VIEW]]

    SC --> SQ
    SQ --> RUNS
    RUNS -->|ingest| ART
    ART --> NS
    MR -.->|filter| ART
    MR -.->|filter| OPP
    ART -.-> OPP

    WDR[(operator runs)] -.->|ingest path A planned| ART
```

#### Views and non-tables

```mermaid
flowchart LR
    subgraph Views["Not tables"]
        PR[Pending Review Item]
        OPP[Opportunity]
        ESC[Escalations]
        AI[AI Analysis output]
    end

    subgraph Parents["Parent storage"]
        CARD[cards.review_status]
        ART[articles]
        RUNS[runs.engine_outputs]
        CARD2[cards.card JSONB]
    end

    CARD -->|draft| PR
    ART --> OPP
    RUNS --> AI
    CARD2 --> AI
    ESC -.->|spawns| RUNS
```

| View / action | SQL / logic equivalent |
|---------------|------------------------|
| Pending Review | `cards.review_status = 'draft'` joined to `companies` |
| Watchlist | `companies.is_watchlisted` or `watchlist_entries` |
| Opportunity | Weekly query over `articles` + `signals` + `monitoring_rules` |
| Operator result escalate | `INSERT INTO runs (source_kind='research', engines→provenance)` |

### 9.5 `runs` polymorphism

```mermaid
flowchart TD
    RUNS[(runs)]

    RUNS --> WD[source_kind = web_discovery]
    RUNS --> RS[source_kind = research]
    RUNS --> UQ[source_kind = user_query]

    WD --> OPR[Operator Discovery Run]
    WD --> ANA[Analyst Query Run]

    OPR --> |engines.cluster_id| DC[Discovery Cluster]
    OPR --> |engines.query_ids| DQ[Discovery Query]
    OPR --> OUT1[engine_outputs → Search Results]

    ANA --> |engines.search_cluster_id planned| SC[Search Cluster]
    ANA --> |engines.search_query_id planned| SQ[Search Query]
    ANA --> OUT2[engine_outputs → Article candidates]

    RS --> OUT3[companies + cards + signals + sources]
    UQ --> OUT3
```

| `source_kind` | Who triggers | `engines` discriminator | Output |
|---------------|--------------|-------------------------|--------|
| `web_discovery` | Operator | `cluster_id`, `query_id(s)` | Search Results JSON |
| `web_discovery` | Analyst | `search_cluster_id`, `search_query_id` | Articles ingest |
| `research` | Escalate / +ADD / bookmark / API | `company_name`, provenance URLs | Company + Card |
| `user_query` | Same as `research` | Same | Company + Card |

### 9.6 Composite foreign keys

```mermaid
erDiagram
    companies {
        uuid id PK
        uuid canonical_card_id
    }
    cards {
        uuid id PK
        uuid company_id FK
    }
    signals {
        uuid card_id
        uuid company_id
    }
    sources {
        uuid card_id
        uuid company_id
    }

    cards ||--|| companies : company_id
    companies |o--|| cards : "canonical_card_id composite"
    cards ||--o{ signals : "card_id plus company_id composite"
    cards ||--o{ sources : "card_id plus company_id composite"
```

| Constraint | Prevents |
|------------|----------|
| `cards(company_id)` → `companies(id)` | Orphan cards |
| `(canonical_card_id, id)` → `cards(id, company_id)` | Canonical card from another company |
| `(card_id, company_id)` on signals/sources | Cross-company drift |

### 9.7 JSON embeds (not separate tables)

| Location | Contents | Future table? |
|----------|----------|---------------|
| `runs.engine_outputs` | Per-query Exa results, Search Result objects | Optional `search_results` |
| `runs.engines` | Run config + cluster/query provenance | Optional dedicated FK columns |
| `cards.card` | Full `CompanyCardV1` — see `apps/api/app/schemas/` | Stay JSONB |
| `articles.mentioned_companies` | Companies in story | Stay JSON or junction |
| `app_kv.value` | `research_config` | Stay KV |

### 9.8 End-to-end data flow

```mermaid
flowchart LR
    subgraph Operator["Admin console"]
        direction TB
        A1[Discovery Cluster]
        A2[Run Exa]
        A3[Search Results]
        A4[Escalate]
    end

    subgraph Analyst["Analyst app"]
        direction TB
        B1[Search Cluster]
        B2[Run ingest]
        B3[Articles / News]
        B4[+ ADD]
        B5[Pending Review]
        B6[Watchlist]
    end

    subgraph DB["Shared Postgres"]
        direction TB
        R[(runs)]
        C[(companies)]
        K[(cards)]
        S[(signals)]
    end

    A1 --> A2 --> R
    R --> A3
    A3 --> A4 --> R
    A4 --> C

    B1 --> B2 --> R
    R --> B3
    B3 --> B4 --> R
    R --> K
    K --> B5
    B5 --> B6 --> C
    K --> S

    A3 -.->|ingest planned| B3
```

---

## Part III — Analyst App (BAT)

Object definitions: [P1-02-User](./P1-02-user.md). Workflows: [P1-01-User](./P1-01-user.md). Full Postgres columns for shared objects: **Part I §4**.

---

## 10. Analyst — Platform objects

### 10.1 Organization *(planned)*

Single-tenant in the first release — one implicit organization, no separate org screen.

### 10.2 User

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | identifier | Yes | No | — | **Planned** |
| email | text | Yes | Yes | Settings profile | **Planned** |
| display_name | text | No | Yes | Sidebar | **Planned** |
| role | analyst / lead / admin | Yes | No | — | **Planned** |
| created_at | date-time | Yes | No | — | **Planned** |
| updated_at | date-time | Yes | No | — | **Planned** |

---

## 11. Analyst — Discovery and feed objects

Same **Cluster → Query → Run** pattern as §1 (operator uses **Discovery** names; analyst uses **Search** names). Analyst objects are **planned** unless marked otherwise.

### 11.1 Search Cluster

**Status:** Planned · Settings → Clusters · table `search_clusters`

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | identifier | Yes | No | — | |
| name | text | Yes | Yes | Cluster list, Settings | Theme label e.g. "NGP Canada" |
| slug | text | Yes | No | — | Short unique key |
| description | text | No | No | Cluster detail | |
| include_keywords | list of text | Yes | No | Cluster settings | Monitoring scope |
| exclude_keywords | list of text | No | No | Cluster settings | |
| geography | list of text | No | No | Cluster settings | |
| source_preferences | list of text | No | No | Cluster settings | |
| signal_types | list of text | No | No | Cluster settings | FUND, FDA, etc. |
| is_active | yes/no | Yes | Yes | Cluster list | |
| schedule | text | No | No | Cluster settings | Auto-run schedule · **Planned** |
| query_count | number | Yes | No | Cluster list | Count of queries in cluster |
| last_run_at | date-time | No | Yes | Cluster list | |
| created_at | date-time | Yes | No | Cluster metadata | |
| updated_at | date-time | Yes | No | — | |

### 11.2 Search Query

**Status:** Planned · table `search_queries` · one saved search inside a Search Cluster

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | identifier | Yes | No | — | |
| cluster | link to Search Cluster | Yes | No | — | Parent cluster — not a query |
| name | text | Yes | Yes | Query list | Short label for this search |
| query_text | text | Yes | Yes | Query editor | Exa search string |
| parameters | settings object | No | No | Query editor | Advanced search options · **Planned** |
| is_active | yes/no | Yes | Yes | Query list | |
| created_at | date-time | Yes | No | Query metadata | |
| updated_at | date-time | Yes | No | — | |

### 11.3 Query Run (analyst)

**Status:** Planned · one execution when analyst runs a Search Query · stored in `runs` (`source_kind = web_discovery`, analyst `engines` metadata)

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | identifier | Yes | No | — | |
| cluster | link to Search Cluster | Yes | No | — | Which cluster was run |
| query | link to Search Query | Yes | No | — | Which saved search was executed |
| status | running / completed / failed | Yes | No | — | |
| started_at | date-time | No | No | — | |
| completed_at | date-time | No | No | — | |
| error_message | text | No | No | — | Shown to ops if run fails |
| created_at | date-time | Yes | No | — | |

### 11.4 Article

**Status:** Planned · News feed, Signals page

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | identifier | Yes | No | — | |
| url | text | Yes | Yes | Article link | Unique |
| title | text | Yes | Yes | News row headline | |
| summary | text | No | Yes | Expanded article | AI or excerpt |
| body_text | text | No | Yes | Expanded article | |
| source_name | text | No | Yes | News row | Publisher |
| published_at | date-time | No | Yes | News row date | |
| ingested_at | date-time | Yes | No | — | When system added the story |
| cluster | link to Search Cluster | No | No | — | Which theme surfaced it |
| category_tag | text | No | Yes | News row tag | e.g. MED-NIC |
| priority_score | number | No | Yes | News row, Signals sort | 0–100 |
| mentioned_companies | list | No | Yes | Companies in story | Name, domain, excerpt per company |
| status | active / dismissed / archived | Yes | No | — | |
| created_at | date-time | Yes | No | — | |
| updated_at | date-time | Yes | No | — | |

### 11.5 News Signal

**Status:** Planned · stored on the Article or as linked signal rows

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | identifier | Yes | No | — | |
| article | link to Article | Yes | No | — | Parent story |
| signal_type | FUND / FDA / LEGAL / PARTNER / PRODUCT / … | Yes | Yes | News row, Signals tabs | |
| score | number | No | Yes | News row priority | 0–100 |
| headline | text | No | Yes | Signals table | Short label |
| created_at | date-time | Yes | No | — | |

### 11.6 Opportunity

**Status:** Planned · derived weekly digest on Home → Top (not a separate stored object)

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | identifier | Yes | No | — | |
| subtype | watchlist / industry | Yes | Yes | Top tab section | |
| company | link to Company | No | Yes | Watchlist opportunity card | Watchlist subtype only |
| article | link to Article | No | Yes | Industry opportunity card | Industry subtype only |
| signal_type | text | No | Yes | Opportunity card | |
| title | text | Yes | Yes | Opportunity heading | |
| bullets | list of text | Yes | No | Opportunity card body | |
| week_start | date | Yes | Yes | Top tab filter | Digest window |
| rule | link to Monitoring Rule | No | No | — | Rule that matched |

---

## 12. Analyst — Company intelligence objects

### 12.1 Company

**Status:** Available (partial) · shared with operator console — full schema: **Part I §4.2**

| Field | Analyst UI | Notes |
|-------|------------|-------|
| company_name | Companies list, Pending review, +ADD modal | **Available** |
| domain | Company header | **Available** |
| industry, category | Companies filters | **Available** |
| on_watchlist | Watchlist tab | **Planned** |

### 12.2 Company Profile

**Status:** Available · structured profile behind Overview, Signals, People, Financials tabs — full schema: **Part I §4.3**

| Field | Analyst UI | Notes |
|-------|------------|-------|
| review_status | Pending review queue | `draft` = awaiting promote/dismiss |
| fit_score | Pending review card, company header | Overall score 0–100 |
| profile_data | All profile tabs | Full company intelligence document |

### 12.3 Company Signal

**Status:** Available · timeline events on the company profile — full schema: **Part I §4.4**

---

## 13. Analyst — Decision objects

### 13.1 Pending Review Item

**Status:** Available · queue row — not a separate stored object; built from Company + Company Profile in draft state

| Field shown | Required | UI | Notes |
|-------------|----------|-----|-------|
| company_name | Yes | Queue row | |
| domain | No | Queue row | |
| fit_summary | No | Expanded card | Short excerpt from profile |
| fit_score | No | Queue row badge | |
| origin | No | Queue tab filter | bookmark · article +ADD · manual · **Planned:** operator escalate |
| created_at | Yes | Queue sort | When profile entered review |

### 13.2 Watchlist Entry

**Status:** Planned · company promoted from Pending Review to ongoing monitoring

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| company | link to Company | Yes | Yes | Watchlist tab | |
| promoted_at | date-time | Yes | Yes | Watchlist metadata | Set when analyst clicks Promote |
| promoted_by | user | No | No | — | **Planned** |
| monitoring_tier | text | No | No | — | Baseline screener label · **Planned** |

### 13.3 Manual Bookmark

**Status:** Available · analyst input from + Add company modal; triggers deep research

| Input field | Type | Required | UI | Notes |
|-------------|------|----------|-----|-------|
| company_name | text | Yes | + Add company modal | |
| website_url | text | No | + Add company modal | |
| notes | text | No | Modal | **Planned** |

---

## 14. Analyst — Escalation actions

**Status:** Available (partial) · actions, not stored objects — each choice updates Company / Profile state

| Escalation | Input | Effect |
|------------|-------|--------|
| **+ ADD** | Article + company name from story | Starts deep research → Company Profile enters Pending Review |
| **Promote** | Pending Review item | Profile accepted → company joins Watchlist |
| **Dismiss** | Pending Review item | Profile rejected → removed from queue |

---

## 15. Analyst — Monitoring Rule

**Status:** Planned · Settings → Monitoring rules

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | identifier | Yes | No | — | |
| name | text | Yes | Yes | Rules settings | |
| is_active | yes/no | Yes | Yes | Rules list | |
| signal_types | list of text | No | No | Rule editor | e.g. FDA, FUND |
| min_score | number | No | No | Rule editor | 0–100 |
| categories | list of text | No | No | Rule editor | |
| target_surface | signals tab / home top / watchlist digest | Yes | No | Rule editor | Where matched items appear |
| signals_tab_key | text | No | No | Rule editor | e.g. regulatory, filings |
| created_at | date-time | Yes | No | — | |
| updated_at | date-time | Yes | No | — | |

---

## 16. Analyst — AI Analysis (visible fields)

| Parent | Field | Type | UI | Status |
|--------|-------|------|-----|--------|
| Article | summary | text | Expanded article | **Planned** |
| Article | priority_score | integer | News row sort | **Planned** |
| News Signal | signal_type, score | — | Signals tabs | **Planned** |
| Company Profile | profile_data | structured document | Profile tabs | **Available** via deep research |

---

## 17. Analyst — How objects connect

Product-language flow (complements Part II ER diagrams):

```mermaid
flowchart TB
    SC[Search Cluster]
    SQ[Search Query]
    QR[Query Run]
    ART[Article]
    NS[News Signal]
    MR[Monitoring Rule]
    OPP[Opportunity]
    ADD[+ ADD]
    DR[Deep Research]
    CP[Company Profile]
    PR[Pending Review]
    WL[Watchlist]
    CO[Company]
    CS[Company Signal]

    SC --> SQ --> QR --> ART
    ART --> NS
    MR -.-> ART
    MR -.-> OPP
    ART -.-> OPP
    ART --> ADD --> DR --> CP
    CP -->|draft| PR --> WL
    WL --> CO
    CP --> CS
```

| Step | What happens |
|------|----------------|
| Run Search Query | System fetches new Articles into News and Signals |
| Monitoring Rule | Filters which Articles and Opportunities surface on Home |
| + ADD on Article | Deep research builds a Company Profile → Pending Review |
| Promote | Company joins Watchlist for ongoing monitoring |
| Watchlist | New Company Signals append on the profile over time |

Also: [P1-02-User §11](./P1-02-user.md#11-how-objects-connect-overview)

---

## 18. Completion checklist

| Item | Status |
|------|--------|
| Part I — field table for every P1-02-Admin object | Done |
| Part I — required / optional, types, UI, searchable | Done |
| Part II — database schema diagrams (§9) | Done |
| Part III — field table for every P1-02-User object | Done |
| Part III — analyst escalation + connection flow (§17) | Done |
| Shared objects cross-referenced Part I ↔ Part III | Done |
| CompanyCardV1 JSON deferred to `apps/api/app/schemas/` | Done |
| `organization_id` omitted per MVP decision | Done |

---

## 19. Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Author | Huzaifa | 2026-06-16 | Draft v2.1 |
| Reviewer | Shehrayar Haq | — | Pending |
