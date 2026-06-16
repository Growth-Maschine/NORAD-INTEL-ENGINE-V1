# P1-04 — Required Fields

| Field | Value |
|-------|-------|
| **Document ref** | P1-04 |
| **Title** | Required Fields per Object |
| **Version** | 2.2 |
| **Last updated** | 2026-06-16 |
| **Audience** | Internal developers, operators |
| **Linear** | [GRO-269](https://linear.app/growthmaschine/issue/GRO-269/40-define-required-fields-for-each-core-object) · Parent [GRO-265](https://linear.app/growthmaschine/issue/GRO-265) |
| **Object reference** | [P1-02-Admin](./P1-02-admin.md) · [P1-02-User](./P1-02-user.md) · [P1-03](./P1-03.md) |
| **Screen mapping** | [P1-05-Admin](./P1-05-admin.md) · [P1-05-User](./P1-05-user.md) |
| **Backend actions** | [P1-06](./P1-06.md) |

---

## 1. Introduction

Single field-level spec for the NORAD data model. Companion to [P1-03](./P1-03.md) (relationships). Analyst **screen labels** and workflows live in [P1-02-User](./P1-02-user.md) and [P1-01-User](./P1-01-user.md) — not duplicated here.

| Part | Sections | Content |
|------|----------|---------|
| **I — Field tables** | §2–§8 | Postgres columns, enums, FKs, field definitions |
| **II — Schema diagrams** | §9 | Master ER, flows, `runs` polymorphism |
| **III — Analyst consumption** | §10 | Read-only role — no duplicate field tables |

**Global conventions**

| Rule | Decision |
|------|----------|
| `organization_id` | **Omitted** until multi-tenant ships |
| Part I Notes | field notes vs models
| Non-table objects | Views and actions — fields on parent tables |
| AI Analysis | Not a table — fields on parent objects |

**Cluster · Query · Run**

One pipeline. **Admin UI** creates and edits Clusters and Queries. **Runs** execute on operator action now; **scheduled cron** will auto-run active clusters and ingest results into the analyst News feed. **Analysts read and monitor** — they do not create clusters or queries.

| Level | Product name | Postgres table / row |
|-------|--------------|----------------------|
| **Cluster** | Cluster | `web_discovery_clusters` |
| **Query** | Query | `web_discovery_queries` (`cluster_id` FK) |
| **Run** | Run | `runs` where `source_kind = web_discovery` |

| Label | `label` on Query | Display name in admin UI |
| Search string | `search_query` on Query | Exa text sent on Run — not the cluster name |

`web_discovery_` is the **Postgres table prefix only** — product language is Cluster / Query / Run.

**Table columns (Part I)**

| Column | Meaning |
|--------|---------|
| Field | Column or JSON path |
| Type | Postgres-oriented type |
| Required | Yes / No |
| Searchable | Yes / No |
| UI | Where shown, or Internal only |
| Notes | Enum values, FK, constraints |

---

## Part I — Field tables

Object definitions: [P1-02-Admin](./P1-02-admin.md). Workflows: [P1-01-Admin](./P1-01-admin.md).

---

## 2. Platform objects

### 2.1 Organization

No table in MVP. Documented for post-MVP schema design.

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | Primary key ·|
| name | string(255) | Yes | Yes | Internal | Tenant display name ·|
| slug | string(120) | Yes | Yes | Internal | Unique tenant key ·|
| created_at | timestamptz | Yes | No | Internal ||
| updated_at | timestamptz | Yes | No | Internal ||

### 2.2 User

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal ||
| email | string(255) | Yes | Yes | Settings profile ||
| display_name | string(120) | No | Yes | Sidebar profile ||
| role | enum (`operator`, `admin`) | Yes | No | Internal | Admin console access ·|
| created_at | timestamptz | Yes | No | Internal ||
| updated_at | timestamptz | Yes | No | Internal ||

---

## 3. Cluster, Query, and Run

Configured in **admin UI** only. Postgres table names below; product terms are Cluster / Query / Run.

### 3.1 Cluster

Table: `web_discovery_clusters`

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| name | string(140) | Yes | Yes | Cluster list, command center header | |
| slug | string(160) | Yes | Yes | Internal | Unique; URL segment |
| description | text | No | No | Cluster settings | |
| priority | enum (`P1 Critical`, `P2 Daily Intelligence`, `P3 Weekly Monitoring`) | Yes | Yes | Cluster list badge | Default `P2 Daily Intelligence` |
| is_active | boolean | Yes | Yes | Cluster list status | Paused clusters cannot run |
| include_keywords | JSON array[string] | Yes | No | Cluster settings | Scope tags |
| exclude_keywords | JSON array[string] | Yes | No | Cluster settings | |
| geography_focus | JSON array[string] | Yes | No | Cluster settings | |
| source_preferences | JSON array[string] | Yes | No | Cluster settings | |
| signal_priorities | JSON array[string] | Yes | No | Cluster settings | |
| query_count | integer | Yes | No | Cluster list stat | Denormalized · ≥ 0 |
| signal_count | integer | Yes | No | Cluster list stat | Denormalized · ≥ 0 |
| last_run_at | timestamptz | No | Yes | Cluster list | Last successful run |
| schedule | string | No | No | Cluster settings | Cron expression ·|
| created_at | timestamptz | Yes | No | Cluster metadata | |
| updated_at | timestamptz | Yes | No | Internal | |

### 3.2 Query

Table: `web_discovery_queries` · belongs to one Cluster (`cluster_id`)

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
| structured_outputs | boolean | Yes | No | Query editor ||
| highlights_max_chars | integer | No | No | Query editor | |
| highlights_guiding_query | text | No | No | Query editor | |
| text_max_chars | integer | No | No | Query editor | |
| text_main_content_only | boolean | Yes | No | Query editor | |
| summary_max_chars | integer | No | No | Query editor | |
| system_prompt | text | No | No | Query editor ||
| output_schema | JSON object | No | No | Query editor ||
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

### 3.3 Run

Table: `runs` where `source_kind = web_discovery` · executes one or more Queries (manual or cron)

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| source_kind | string(32) | Yes | Yes | Internal | Always `web_discovery` |
| query | text | Yes | No | Activity log | Run label — cluster name or batch context |
| status | enum (`queued`, `researching`, `synthesizing`, `completed`, `failed`, `cancelled`) | Yes | Yes | Results page, Activity | `queued` → `completed` / `failed` |
| progress_pct | integer | Yes | No | Activity | 0–100 |
| error | text | No | No | Results error banner | |
| engines | JSON object | Yes | No | Internal | Snapshot: `cluster_id`, `query_ids`, Exa config |
| engine_outputs | JSON object | Yes | No | Internal | Per-query result slices — see §3.4 |
| idempotency_key | string(64) | No | No | Internal | Unique when set |
| started_at | timestamptz | No | Yes | Activity, run selector | |
| completed_at | timestamptz | No | Yes | Run selector | |
| company_id | UUID | No | No | Internal | Null for cluster runs |
| card_id | UUID | No | No | Internal | Null for cluster runs |
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

**Embedded in run JSON** — object inside `runs.engine_outputs[].results[]`. Optional future `search_results` table; MVP keeps JSON embed.

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| url | text | Yes | Yes | Results page link | Primary identity |
| exa_id | string | No | No | Internal | Exa document id |
| title | string | No | Yes | Results page title | |
| snippet | text | No | Yes | Results page excerpt | |
| published_date | string (ISO date) | No | Yes | Results metadata | |
| score | float | No | Yes | Results sort | Exa relevance |
| highlights | JSON array[string] | No | No | Results expand | |
| summary | text | No | Yes | Results expand | Exa vendor summary |
| text | text | No | No | Internal | Full body when content_text enabled |
| image | string (URL) | No | No | Results thumbnail ||
| favicon | string (URL) | No | No | Results row | |
| author | string | No | No | Results metadata | |
| relevance_score | integer | No | Yes | Results sort ||
| relevance_reason | text | No | No | Results expand ||
| extracted_signals | JSON array | No | Yes | Results signals column ||
| source_run_id | UUID | Yes | No | Internal | Parent run · when promoted to row |
| source_query_id | UUID | Yes | No | Internal | Parent query |

### 3.5 Article

Table: `articles`

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| url | text | Yes | Yes | Analyst News row | Unique |
| title | string | Yes | Yes | News row headline | |
| summary | text | No | Yes | Expanded article | AI or excerpt |
| body_text | text | No | Yes | Expanded article | |
| source_name | string | No | Yes | News row | Publisher |
| published_at | timestamptz | No | Yes | News row date | |
| ingested_at | timestamptz | Yes | No | Internal | When ingest job added the story |
| cluster_id | UUID | No | No | Internal | FK → `web_discovery_clusters.id` — which cluster surfaced it |
| query_run_id | UUID | No | No | Internal | FK → `runs.id` — originating Run |
| category_tag | string | No | Yes | News row tag | e.g. MED-NIC |
| priority_score | integer | No | Yes | News row sort | 0–100 |
| mentioned_companies | JSON array | No | Yes | Companies in story | |
| status | enum (`active`, `dismissed`, `archived`) | Yes | No | Internal | |
| created_at | timestamptz | Yes | No | Internal | |
| updated_at | timestamptz | Yes | No | Internal | |

### 3.6 News Signal

Table: `article_signals`

| Field | Type | Required | Searchable | UI | Notes |
|-------|------|----------|------------|-----|-------|
| id | UUID | Yes | No | Internal | PK |
| article_id | UUID | Yes | No | Internal | FK → `articles.id` |
| signal_type | string | Yes | Yes | Analyst Signals tabs | FUND, FDA, LEGAL, … |
| score | integer | No | Yes | News row priority | 0–100 |
| headline | text | No | Yes | Signals table | |
| created_at | timestamptz | Yes | No | Internal | |

---

## 4. Deep research objects

### 4.1 Deep Research Run

Table: `runs` where `source_kind = research`

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

**Provenance fields** (in `engines` JSON; optional dedicated columns)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| source_search_result_url | string | No | Escalate from Search Result ·|
| source_run_id | UUID | No | Parent Run ·|

### 4.2 Company

Table: `companies`

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
| status | string(32) | No | Yes | Companies list ||
| headquarters_country | string(64) | No | Yes | Company detail | |
| canonical_card_id | UUID | No | No | Internal | Composite FK with `id` |
| is_watchlisted | boolean | No | Yes | Watchlist tab filter ||
| created_at | timestamptz | Yes | Yes | Company metadata | |
| updated_at | timestamptz | Yes | No | Internal | |

### 4.3 Company Card

Table: `cards` · JSON contract: `CompanyCardV1` in `apps/api/app/schemas/`

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

Table: `signals` · Analyst label: Company Signal

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

Table: `sources`

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

Table: `run_events`

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

Table: `engine_calls`

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

Store: `app_kv` key `research_config` · Affects **deep research runs only**

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

| `source_kind` | Product object |
| --------------- | ---------------- |
| `web_discovery` | Run (Exa cluster/query execution) |
| `research` | Deep Research Run |
| `user_query` | Deep Research Run (older discriminator — same as `research`) |

---

## 7. AI Analysis — fields on parent objects

Not a table. Post-pipeline LLM output columns:

| Parent | Field | Type | Required | UI |
| -------- | ------- | ------ | ---------- | ----- |
| Search Result | relevance_score | integer | No | Results sort |
| Search Result | relevance_reason | text | No | Results expand |
| Search Result | extracted_signals | JSON array | No | Results signals |
| Company Card | card (synthesis) | JSONB | Yes | Company detail |
| `engine_calls` | (audit row) | — | — | Research Evidence |

---

## 8. Non-table objects (actions and views)

### 8.1 Result escalation

**No table.** Admin action on a Search Result from a Run.

| Concept | Persisted as | Notes |
|---------|--------------|-------|
| Escalate click | New `runs` row `source_kind=research` ||
| Source URL / company hint | `runs.query` + engines metadata | |

### 8.2 Pending Review Item *(analyst queue — documented for shared backend)*

**View** — not a table. Row appears when `cards.review_status = draft`.

| Field shown | Source table.column |
|-------------|---------------------|
| company_name | `companies.company_name` |
| domain | `companies.domain` |
| summary | `cards.card` JSON excerpt |
| origin_label | `engines` / article provenance ·|
| review_status | `cards.review_status` |
| run_id | `cards.run_id` |

---

## Part II — Database schema diagrams

Visual layer on top of Part I field tables and [P1-03](./P1-03.md) (relationships).

---

## 9. Database schema diagrams

### 9.1 How to read

| Symbol / label | Meaning |
|----------------|---------|
| **Solid line** | FK exists or is defined in schema |
| **Dotted line** | Logical link — JSON embed, view, or provenance |
| 🟢 | Table exists in repo |
| 🔵 | not migrated yet |
| ⬜ | View or derived — not a table |

**MVP:** No `organizations` or `organization_id` until multi-tenant. **Single `runs` table** — `source_kind` discriminates Run vs deep research.

### 9.2 Master schema — all tables

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
    organizations ||--o{ companies : owns
    organizations ||--o{ monitoring_rules : owns

    web_discovery_clusters ||--o{ web_discovery_queries : contains

    web_discovery_queries }o--o{ runs : executes
    web_discovery_clusters ||--o{ articles : ingests

    runs ||--o{ articles : ingests

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

    runs ||--o{ articles : ingests
    articles ||--o{ article_signals : tags

    users ||--o{ watchlist_entries : promoted_by
```

> `companies.canonical_card_id` and `signals` / `sources` use **composite FKs** with `(card_id, company_id)` — simplified above. See §9.6.

### 9.3 Current schema

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

| Table |
| ------- |
| `web_discovery_clusters` |
| `web_discovery_queries` |
| `runs` |
| `companies` |
| `cards` |
| `signals` |
| `sources` |
| `run_events` |
| `engine_calls` |
| `app_kv` |

### 9.4 Diagram by product area

#### Cluster → Query → Run

```mermaid
flowchart TB
    subgraph Tables["Postgres tables"]
        CL[Cluster<br/>web_discovery_clusters]
        Q[Query<br/>web_discovery_queries]
        RUNS[(Run<br/>runs)]
    end

    subgraph JSON["Inside runs.engine_outputs"]
        SLICE["per-query slice"]
        SR["results array"]
        ITEM["Search Result objects"]
    end

    CL -->|cluster_id CASCADE| Q
    Q -->|Run Query / Run All / cron| RUNS
    RUNS --> SLICE
    SLICE --> SR
    SR --> ITEM

    ITEM -.->|Escalate| RUNS2[(runs source_kind=research)]
    RUNS -.->|ingest| ART[articles]
```

Search Results are **not rows** — JSON inside `engine_outputs`. **Articles** are ingested from Run output for the analyst News feed.

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
    PR -->|Promote| WL[watchlist_entries]
```

#### Analyst News feed

```mermaid
flowchart TB
    CL[Cluster]
    Q[Query]
    RUNS[(Run)]
    ART[articles]
    NS[article_signals]
    MR[monitoring_rules]
    OPP[[Opportunity VIEW]]

    CL --> Q
    Q -->|cron or manual| RUNS
    RUNS -->|ingest job| ART
    ART --> NS
    MR -.->|filter| ART
    MR -.->|filter| OPP
    ART -.-> OPP
```

Analysts **do not** create Clusters or Queries — they read **Articles** produced by scheduled or manual Runs.

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

    WD --> |engines.cluster_id| CL[Cluster]
    WD --> |engines.query_ids| Q[Query]
    WD --> OUT1[engine_outputs → Search Results]
    WD --> OUT2[ingest → articles]

    RS --> OUT3[companies + cards + signals + sources]
    UQ --> OUT3
```

| `source_kind` | Trigger | Output |
|---------------|---------|--------|
| `web_discovery` | Admin Run Query / Run All · cron | Search Results JSON · Articles ingest |
| `research` | Escalate / +ADD / bookmark / API | Company + Card |
| `user_query` | Same as `research` | Company + Card |

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
    subgraph Admin["Admin UI"]
        direction TB
        A1[Cluster + Query config]
        A2[Run Exa / cron]
        A3[Search Results]
        A4[Escalate]
    end

    subgraph Analyst["Analyst UI — read & act"]
        direction TB
        B1[News / Articles]
        B2[+ ADD]
        B3[Pending Review]
        B4[Watchlist]
    end

    subgraph DB["Shared Postgres"]
        direction TB
        R[(runs)]
        ART[(articles)]
        C[(companies)]
        K[(cards)]
    end

    A1 --> A2 --> R
    R --> A3
    R -.->|ingest| ART
    ART --> B1
    A3 --> A4 --> R
    A4 --> C
    B1 --> B2 --> R
    R --> K
    K --> B3
    B3 --> B4 --> C
```

---

## Part III — Analyst app (read-only)

Analysts **read and monitor** — they do **not** create Clusters, Queries, or Runs. Admin configures clusters; **cron** or manual runs execute Exa and ingest **Articles** (§3.5) into the News feed.

| Need | Where to look |
|------|----------------|
| Postgres columns | **Part I** (this doc) — single schema |
| Screen labels & analyst actions | [P1-02-User](./P1-02-user.md) |
| Workflows (+ADD, Promote, Pending Review) | [P1-01-User](./P1-01-user.md) |
| Screen → object mapping | [P1-05-User](./P1-05-user.md) |

| Object | Analyst role |
|--------|----------------|
| Cluster, Query, Run | Not managed in analyst UI |
| Article, News Signal | Read News / Signals feeds |
| Company, Company Card, Company Signal | Read profiles; Pending Review actions |
| Pending Review Item | View — `cards.review_status = draft` (§8.2) |

---

## 11. Completion checklist

| Item |
| ------ |
| Part I — field table for every P1-02-Admin object |
| Part I — Cluster / Query / Run single definition (§3) |
| Part I — Article + News Signal (§3.5–3.6) |
| Part II — database schema diagrams (§9) |
| No duplicate analyst field tables |
| Analyst read-only consumption noted (§10) |
| CompanyCardV1 JSON deferred to `apps/api/app/schemas/` |
| `organization_id` omitted per MVP decision |

---

## 12. Approval

| Role | Name | Date |
| ------ | ------ | ------ |
| Author | Huzaifa | 2026-06-16 |
| Reviewer | Shehrayar Haq | — |
