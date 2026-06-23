# Phase 2 — GCP Database Schema Verification

> **2026-06-16 update:** The live Phase 1 schema has **11 tables** — the research `signals` table was **dropped** (`0011_drop_signals.sql`). Scenarios below that reference `signals`, composite FKs on `signals`, or 49 profile-completeness params are **legacy** — use [P1-04-admin.md §9.3](./P1-04-admin.md#93-current-schema-live--11-tables) as the current checklist. Profile completeness is **44 parameters** per card.


| Field                      | Value                                                                            |
| -------------------------- | -------------------------------------------------------------------------------- |
| **Project**                | NORAD Intel Engine                                                               |
| **Repository**             | NORAD-INTEL-ENGINE-V1                                                            |
| **Purpose**                | Verify the new GCP Cloud SQL Postgres instance before connecting the Phase 2 API |
| **Schema source of truth** | [P1-04-admin.md](./P1-04-admin.md) · `apps/api/app/models/`                      |


---

## What you are checking

Schema verification means confirming the database was created correctly **before** you point the FastAPI backend at it.

You are checking:

```text
Did we create the right tables?
Do the columns exist?
Are required fields actually required?
Are relationships / foreign keys working?
Are indexes created?
Can we insert a full fake NORAD workflow?
```

Run these checks in **Cloud SQL Studio** (GCP Console) or with `psql` from Cloud Shell / your machine. Cloud SQL Studio is easier if you are not familiar with Postgres.

**References:** [Cloud SQL Studio docs](https://cloud.google.com/sql/docs/postgres/manage-data-using-studio) · [Postgres `information_schema](https://www.postgresql.org/docs/current/infoschema-key-column-usage.html)`

### How to record results

After each step below, fill in the **Documentation — paste your results** block:

- Mark **Pass** or **Fail** (or **N/A** if you skipped the step).
- Paste query output, error messages, or a note like `see screenshot: gcp-step-2-tables.png`.
- Call out anything unexpected — extra tables, missing columns, wrong types.


| Verification run   |     |
| ------------------ | --- |
| **GCP instance**   |     |
| **Database name**  |     |
| **Tested by**      |     |
| **Date started**   |     |
| **Date completed** |     |


---

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Cloud SQL instance name, database name selected, and confirmation you can run queries (or screenshot of the query editor).

```text
(paste here)

```

---

## Step 2 — Check that all expected tables exist

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

### Must exist (core + analyst target schema)

These tables power the admin console, deep research pipeline, and analyst feed per [P1-04 §9](./P1-04-admin.md#93-current-schema):

```text
web_discovery_clusters
web_discovery_queries
runs
run_events
engine_calls
companies
cards
signals
sources
articles
article_signals
app_kv
```

### Should exist if the full Phase 2 schema was applied

```text
monitoring_rules
```

`companies.is_watchlisted` (column on `companies`, not a separate table) is the **MVP watchlist** mechanism. A separate `watchlist_entries` table is optional post-MVP — see Step 13.

### Not expected in MVP (post-MVP)

These were documented in older P1-04 diagrams. **Updated 2026-06-22:** `organizations` and related tables (`organization_members`, etc.) **are live** — migration `0012`. Generic `users` and `watchlist_entries` remain post-MVP:

```text
users                    # generic user table — NOT organization_members
watchlist_entries
```

There is no `search_clusters` or `search_queries` in NORAD — those belong to a different project.

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Full output of the `SELECT table_name …` query. Note any **missing** required tables, **unexpected** legacy tables, or **extra** tables not in this doc.

```text

app_kv
cards
companies
discovery_clusters
engine_calls
run_events
runs
signals
sources
trend_articles
web_discovery_clusters
web_discovery_queries


```

**Missing tables:**

```text
articles
article_signals
organizations
users
watchlist_entries
```

**Unexpected / legacy tables found:**

```text

```

---

## Step 3 — Check columns for each important table

Run this for one table at a time (replace `TABLE_NAME`):

```sql
SELECT
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'TABLE_NAME'
ORDER BY ordinal_position;
```

Repeat for:

```text
web_discovery_clusters
web_discovery_queries
runs
articles
article_signals
companies
cards
signals
sources
run_events
engine_calls
app_kv
monitoring_rules        -- if present
```

### What to verify

```text
Does every required field exist?
Are required fields marked NOT NULL?
Are IDs UUIDs?
Are created_at / updated_at present?
Are JSON fields stored as jsonb?
```

### Expected columns — `web_discovery_clusters`

```text
id
name
slug
description
priority
is_active
include_keywords
exclude_keywords
geography_focus
source_preferences
signal_priorities
query_count
signal_count
last_run_at
created_at
updated_at
```

`priority` must accept: `P1 Critical`, `P2 Daily Intelligence`, `P3 Weekly Monitoring`.

### Expected columns — `web_discovery_queries`

Minimum set (plus Exa control columns from migrations 0005–0006):

```text
id
cluster_id
label
search_query
search_type
num_results
is_active
content_highlights
content_text
content_summary
structured_outputs
text_main_content_only
livecrawl_timeout_ms
subpages
extra_links
extra_image_links
subpage_target_keywords
include_domains
exclude_domains
content_moderation
stream_response
additional_queries
system_prompt          -- migration 0006
output_schema          -- migration 0006
created_at
updated_at
```

`search_type` must accept: `auto`, `fast`, `deep`, `deep-lite`, `deep-reasoning`, `instant`.

### Expected columns — `runs`

Single polymorphic table — `source_kind` discriminates web discovery vs deep research ([P1-04 §6](./P1-04-admin.md#6-run-polymorphism-note)):

```text
id
query
source_kind
idempotency_key
status
progress_pct
error
engines
engine_outputs
started_at
completed_at
company_id
card_id
created_at
updated_at
```

`source_kind` values: `web_discovery` (cluster runs), `research` / `user_query` (deep research).

`status` values: `queued`, `researching`, `synthesizing`, `completed`, `failed`, `cancelled`.

### Expected columns — `articles`

Analyst News feed ([P1-04 §3.5](./P1-04-admin.md#35-article)):

```text
id
url
title
summary
body_text
source_name
published_at
ingested_at
cluster_id
query_run_id          -- FK → runs.id (NOT query_id)
category_tag
priority_score
mentioned_companies
status
created_at
updated_at
```

`status` values: `active`, `dismissed`, `archived`.

### Expected columns — `article_signals`

Analyst Signals tabs ([P1-04 §3.6](./P1-04-admin.md#36-news-signal)):

```text
id
article_id
signal_type
score
headline
created_at
```

### Expected columns — `companies`

```text
id
company_name          -- NOT "name"
domain
legal_entity_name
website
logo_url
industry
category
status
headquarters_country
canonical_card_id
is_watchlisted        -- MVP watchlist flag (may be added in Phase 2 migration)
created_at
updated_at
```

### Expected columns — `cards`

```text
id
company_id
run_id
schema_version
card                  -- JSONB CompanyCardV1
score_overall
score_growth
score_momentum
score_fundraising
score_acquisition
score_partnership_fit
score_strategic_fit
score_risk
review_status
reviewer_notes
created_at
updated_at
```

`review_status` values: `draft`, `accepted`, `rejected`, `archived`.  
`draft` = Pending Review queue.

### Expected columns — `signals` (research / company signals)

```text
id
company_id
card_id
type
subtype
headline
evidence
weight
signal_date
source_refs
created_at
updated_at
```

`type` values: `growth`, `fundraising`, `acquisition`, `partnership`, `risk`, `strategic`.

### Expected columns — `sources`

```text
id
company_id
card_id
local_id
url
title
type
trust_tier
date_published
date_found
last_checked
snippet
freshness_score
created_at
updated_at
```

### Expected columns — `engine_calls`

Column names in the running API use `request_payload` / `response_payload` (see `apps/api/app/models/engine_call.py`). If your GCP DDL used `request_snapshot` / `response_snapshot` from an older draft, flag that mismatch — the API expects the model names.

```text
id
run_id
vendor
operation
model
processor
units
input_tokens
output_tokens
cost_usd
latency_ms
status
error
request_payload       -- or request_snapshot (must match API)
response_payload      -- or response_snapshot (must match API)
meta
created_at
updated_at
```

`vendor` values: `exa`, `anthropic`, `parallel`, `diffbot`.

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Column query output for each table (or one section per table). Flag any column name mismatches — especially `engine_calls` payload column names.

```text
(paste here — web_discovery_clusters)

[
  {
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": "gen_random_uuid()"
  },
  {
    "column_name": "name",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "slug",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "description",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "priority",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": "'P2 Daily Intelligence'::character varying"
  },
  {
    "column_name": "is_active",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "true"
  },
  {
    "column_name": "include_keywords",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "column_name": "exclude_keywords",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "column_name": "geography_focus",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "column_name": "source_preferences",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "column_name": "signal_priorities",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "column_name": "query_count",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "column_name": "signal_count",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "column_name": "last_run_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  }
]
```

```text
(paste here — web_discovery_queries)

[
  {
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": "gen_random_uuid()"
  },
  {
    "column_name": "cluster_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "label",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "search_query",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "search_type",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": "'auto'::character varying"
  },
  {
    "column_name": "num_results",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "10"
  },
  {
    "column_name": "content_highlights",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "true"
  },
  {
    "column_name": "content_text",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "false"
  },
  {
    "column_name": "content_summary",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "false"
  },
  {
    "column_name": "livecrawl_timeout_ms",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "10000"
  },
  {
    "column_name": "max_age_hours",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "subpages",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "column_name": "extra_links",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "column_name": "extra_image_links",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "column_name": "subpage_target_keywords",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "column_name": "category",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "user_location",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "include_domains",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "column_name": "exclude_domains",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "column_name": "published_after",
    "data_type": "date",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "published_before",
    "data_type": "date",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "crawled_after",
    "data_type": "date",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "crawled_before",
    "data_type": "date",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "content_moderation",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "false"
  },
  {
    "column_name": "stream_response",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "false"
  },
  {
    "column_name": "additional_queries",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "column_name": "is_active",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "true"
  },
  {
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "structured_outputs",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "false"
  },
  {
    "column_name": "highlights_max_chars",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "highlights_guiding_query",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "text_max_chars",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "text_main_content_only",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "true"
  },
  {
    "column_name": "summary_max_chars",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "system_prompt",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "output_schema",
    "data_type": "jsonb",
    "is_nullable": "YES",
    "column_default": ""
  }
]

```

```text
(paste here — runs)

[
  {
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "query",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "source_kind",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": "'user_query'::character varying"
  },
  {
    "column_name": "idempotency_key",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "status",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": "'queued'::character varying"
  },
  {
    "column_name": "progress_pct",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "column_name": "error",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "engines",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'{}'::jsonb"
  },
  {
    "column_name": "engine_outputs",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'{}'::jsonb"
  },
  {
    "column_name": "started_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "completed_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "company_id",
    "data_type": "uuid",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "card_id",
    "data_type": "uuid",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  }
]
```

```text
(paste here — articles)

```

```text
(paste here — article_signals)

```

```text
(paste here — companies)

[
  {
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "domain",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "company_name",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "legal_entity_name",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "website",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "logo_url",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "industry",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "category",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "status",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "headquarters_country",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "canonical_card_id",
    "data_type": "uuid",
    "is_nullable": "YES",
    "column_default": ""
  }
]

```

```text
(paste here — cards)

[
  {
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "company_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "run_id",
    "data_type": "uuid",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "schema_version",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": "'1.0'::character varying"
  },
  {
    "column_name": "card",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "score_overall",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "score_growth",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "score_momentum",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "score_fundraising",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "score_acquisition",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "score_partnership_fit",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "score_strategic_fit",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "score_risk",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "review_status",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": "'draft'::character varying"
  },
  {
    "column_name": "reviewer_notes",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  }
]

```

```text
(paste here — signals)
[
  {
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "company_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "card_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "type",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "subtype",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "headline",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "evidence",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "weight",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "5"
  },
  {
    "column_name": "signal_date",
    "data_type": "date",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "source_refs",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  }
]

```

```text
(paste here — sources)

[
  {
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "company_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "card_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "local_id",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "url",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "title",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "type",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "trust_tier",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "date_published",
    "data_type": "date",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "date_found",
    "data_type": "date",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "last_checked",
    "data_type": "date",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "snippet",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "freshness_score",
    "data_type": "double precision",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  }
]

```

```text
(paste here — run_events)

[
  {
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "run_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "kind",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "message",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "level",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": "'info'::character varying"
  },
  {
    "column_name": "meta",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'{}'::jsonb"
  },
  {
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  }
]

```

```text
(paste here — engine_calls)

[
  {
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "run_id",
    "data_type": "uuid",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "vendor",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "operation",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "model",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "processor",
    "data_type": "character varying",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "units",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "1"
  },
  {
    "column_name": "input_tokens",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "column_name": "output_tokens",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "column_name": "cost_usd",
    "data_type": "double precision",
    "is_nullable": "NO",
    "column_default": "'0'::double precision"
  },
  {
    "column_name": "latency_ms",
    "data_type": "double precision",
    "is_nullable": "NO",
    "column_default": "'0'::double precision"
  },
  {
    "column_name": "status",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": "'ok'::character varying"
  },
  {
    "column_name": "error",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "meta",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'{}'::jsonb"
  },
  {
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "request_payload",
    "data_type": "jsonb",
    "is_nullable": "YES",
    "column_default": ""
  },
  {
    "column_name": "response_payload",
    "data_type": "jsonb",
    "is_nullable": "YES",
    "column_default": ""
  }
]

```

```text
(paste here — app_kv)

[
  {
    "column_name": "key",
    "data_type": "character varying",
    "is_nullable": "NO",
    "column_default": ""
  },
  {
    "column_name": "value",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'{}'::jsonb"
  },
  {
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  }
]
```

**Columns missing or wrong:**

```text

```

---

## Step 4 — Check primary keys

```sql
SELECT
  tc.table_name,
  kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
WHERE tc.constraint_type = 'PRIMARY KEY'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name;
```

Every main table should have an `id` primary key except `app_kv`, which uses `key` as its primary key.

Expected examples:

```text
web_discovery_clusters    id
web_discovery_queries     id
runs                      id
articles                  id
article_signals           id
companies                 id
cards                     id
signals                   id
sources                   id
run_events                id
engine_calls              id
app_kv                    key
```

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Full primary-key query output. Note any table missing an `id` PK (or `key` on `app_kv`).

```text
[
  {
    "table_name": "app_kv",
    "column_name": "key"
  },
  {
    "table_name": "cards",
    "column_name": "id"
  },
  {
    "table_name": "companies",
    "column_name": "id"
  },
  {
    "table_name": "discovery_clusters",
    "column_name": "id"
  },
  {
    "table_name": "engine_calls",
    "column_name": "id"
  },
  {
    "table_name": "run_events",
    "column_name": "id"
  },
  {
    "table_name": "runs",
    "column_name": "id"
  },
  {
    "table_name": "signals",
    "column_name": "id"
  },
  {
    "table_name": "sources",
    "column_name": "id"
  },
  {
    "table_name": "trend_articles",
    "column_name": "id"
  },
  {
    "table_name": "web_discovery_clusters",
    "column_name": "id"
  },
  {
    "table_name": "web_discovery_queries",
    "column_name": "id"
  }
]

```

---

## Step 5 — Check foreign keys

NORAD relationships ([P1-03](./P1-03.md), [P1-04 §9.6](./P1-04-admin.md#96-composite-foreign-keys)):

```text
web_discovery_queries.cluster_id        → web_discovery_clusters.id
articles.cluster_id                       → web_discovery_clusters.id
articles.query_run_id                     → runs.id
article_signals.article_id              → articles.id
runs.company_id                           → companies.id
runs.card_id                              → cards.id
cards.company_id                          → companies.id
cards.run_id                              → runs.id
signals.company_id                        → companies.id
signals.(card_id, company_id)             → cards.(id, company_id)   -- composite
sources.company_id                        → companies.id
sources.(card_id, company_id)             → cards.(id, company_id)   -- composite
companies.(canonical_card_id, id)         → cards.(id, company_id)   -- composite
run_events.run_id                         → runs.id
engine_calls.run_id                       → runs.id
```

```sql
SELECT
  tc.table_name AS child_table,
  kcu.column_name AS child_column,
  ccu.table_name AS parent_table,
  ccu.column_name AS parent_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
 AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY child_table, child_column;
```

Confirm child tables point at the correct parents. Pay special attention to the **composite** FKs on `signals`, `sources`, and `companies.canonical_card_id`.

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Full foreign-key query output. Confirm composite FKs exist for `signals`, `sources`, and `companies.canonical_card_id`.

```text
No rows to display

```

**Missing or incorrect FKs:**

```text

```

---

## Step 6 — Check indexes

```sql
SELECT
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
```

Look for indexes on common filter / sort fields:

```text
web_discovery_clusters.slug
web_discovery_clusters.is_active
web_discovery_clusters.priority
web_discovery_queries.cluster_id
runs.status
runs.source_kind
runs.created_at
runs.(status, created_at)              -- ix_runs_status_created
articles.url                           -- unique
articles.cluster_id
articles.query_run_id
articles.published_at
articles.priority_score
companies.domain
companies.company_name
cards.review_status
cards.company_id
cards.score_overall
signals.company_id
signals.type
run_events.run_id
engine_calls.run_id
engine_calls.vendor
```

Missing indexes will not block MVP but will slow list pages later.

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Full index list (or note missing indexes from the checklist above).

```text
[
  {
    "tablename": "app_kv",
    "indexname": "app_kv_pkey",
    "indexdef": "CREATE UNIQUE INDEX app_kv_pkey ON public.app_kv USING btree (key)"
  },
  {
    "tablename": "cards",
    "indexname": "cards_pkey",
    "indexdef": "CREATE UNIQUE INDEX cards_pkey ON public.cards USING btree (id)"
  },
  {
    "tablename": "cards",
    "indexname": "ix_cards_company_created",
    "indexdef": "CREATE INDEX ix_cards_company_created ON public.cards USING btree (company_id, created_at)"
  },
  {
    "tablename": "cards",
    "indexname": "ix_cards_company_id",
    "indexdef": "CREATE INDEX ix_cards_company_id ON public.cards USING btree (company_id)"
  },
  {
    "tablename": "cards",
    "indexname": "ix_cards_review_status",
    "indexdef": "CREATE INDEX ix_cards_review_status ON public.cards USING btree (review_status)"
  },
  {
    "tablename": "cards",
    "indexname": "ix_cards_run_id",
    "indexdef": "CREATE INDEX ix_cards_run_id ON public.cards USING btree (run_id)"
  },
  {
    "tablename": "cards",
    "indexname": "ix_cards_score_overall",
    "indexdef": "CREATE INDEX ix_cards_score_overall ON public.cards USING btree (score_overall)"
  },
  {
    "tablename": "cards",
    "indexname": "uq_cards_id_company",
    "indexdef": "CREATE UNIQUE INDEX uq_cards_id_company ON public.cards USING btree (id, company_id)"
  },
  {
    "tablename": "companies",
    "indexname": "companies_pkey",
    "indexdef": "CREATE UNIQUE INDEX companies_pkey ON public.companies USING btree (id)"
  },
  {
    "tablename": "companies",
    "indexname": "ix_companies_category",
    "indexdef": "CREATE INDEX ix_companies_category ON public.companies USING btree (category)"
  },
  {
    "tablename": "companies",
    "indexname": "ix_companies_company_name",
    "indexdef": "CREATE INDEX ix_companies_company_name ON public.companies USING btree (company_name)"
  },
  {
    "tablename": "companies",
    "indexname": "ix_companies_domain",
    "indexdef": "CREATE UNIQUE INDEX ix_companies_domain ON public.companies USING btree (domain)"
  },
  {
    "tablename": "companies",
    "indexname": "ix_companies_industry",
    "indexdef": "CREATE INDEX ix_companies_industry ON public.companies USING btree (industry)"
  },
  {
    "tablename": "companies",
    "indexname": "ix_companies_industry_category",
    "indexdef": "CREATE INDEX ix_companies_industry_category ON public.companies USING btree (industry, category)"
  },
  {
    "tablename": "discovery_clusters",
    "indexname": "discovery_clusters_pkey",
    "indexdef": "CREATE UNIQUE INDEX discovery_clusters_pkey ON public.discovery_clusters USING btree (id)"
  },
  {
    "tablename": "discovery_clusters",
    "indexname": "discovery_clusters_slug_key",
    "indexdef": "CREATE UNIQUE INDEX discovery_clusters_slug_key ON public.discovery_clusters USING btree (slug)"
  },
  {
    "tablename": "discovery_clusters",
    "indexname": "ix_discovery_clusters_default",
    "indexdef": "CREATE INDEX ix_discovery_clusters_default ON public.discovery_clusters USING btree (is_default)"
  },
  {
    "tablename": "discovery_clusters",
    "indexname": "ix_discovery_clusters_enabled",
    "indexdef": "CREATE INDEX ix_discovery_clusters_enabled ON public.discovery_clusters USING btree (is_enabled)"
  },
  {
    "tablename": "discovery_clusters",
    "indexname": "ix_discovery_clusters_group_sort",
    "indexdef": "CREATE INDEX ix_discovery_clusters_group_sort ON public.discovery_clusters USING btree (group_name, sort_order)"
  },
  {
    "tablename": "discovery_clusters",
    "indexname": "ix_discovery_clusters_slug",
    "indexdef": "CREATE INDEX ix_discovery_clusters_slug ON public.discovery_clusters USING btree (slug)"
  },
  {
    "tablename": "discovery_clusters",
    "indexname": "ix_discovery_clusters_sort_order",
    "indexdef": "CREATE INDEX ix_discovery_clusters_sort_order ON public.discovery_clusters USING btree (sort_order)"
  },
  {
    "tablename": "discovery_clusters",
    "indexname": "uq_discovery_clusters_single_default",
    "indexdef": "CREATE UNIQUE INDEX uq_discovery_clusters_single_default ON public.discovery_clusters USING btree (is_default) WHERE (is_default = true)"
  },
  {
    "tablename": "engine_calls",
    "indexname": "engine_calls_pkey",
    "indexdef": "CREATE UNIQUE INDEX engine_calls_pkey ON public.engine_calls USING btree (id)"
  },
  {
    "tablename": "engine_calls",
    "indexname": "ix_engine_calls_run_id",
    "indexdef": "CREATE INDEX ix_engine_calls_run_id ON public.engine_calls USING btree (run_id)"
  },
  {
    "tablename": "engine_calls",
    "indexname": "ix_engine_calls_vendor",
    "indexdef": "CREATE INDEX ix_engine_calls_vendor ON public.engine_calls USING btree (vendor)"
  },
  {
    "tablename": "engine_calls",
    "indexname": "ix_engine_calls_vendor_created",
    "indexdef": "CREATE INDEX ix_engine_calls_vendor_created ON public.engine_calls USING btree (vendor, created_at)"
  },
  {
    "tablename": "run_events",
    "indexname": "ix_run_events_kind",
    "indexdef": "CREATE INDEX ix_run_events_kind ON public.run_events USING btree (kind)"
  },
  {
    "tablename": "run_events",
    "indexname": "ix_run_events_run_created",
    "indexdef": "CREATE INDEX ix_run_events_run_created ON public.run_events USING btree (run_id, created_at)"
  },
  {
    "tablename": "run_events",
    "indexname": "ix_run_events_run_id",
    "indexdef": "CREATE INDEX ix_run_events_run_id ON public.run_events USING btree (run_id)"
  },
  {
    "tablename": "run_events",
    "indexname": "run_events_pkey",
    "indexdef": "CREATE UNIQUE INDEX run_events_pkey ON public.run_events USING btree (id)"
  },
  {
    "tablename": "runs",
    "indexname": "ix_runs_company_id",
    "indexdef": "CREATE INDEX ix_runs_company_id ON public.runs USING btree (company_id)"
  },
  {
    "tablename": "runs",
    "indexname": "ix_runs_idempotency_key",
    "indexdef": "CREATE UNIQUE INDEX ix_runs_idempotency_key ON public.runs USING btree (idempotency_key)"
  },
  {
    "tablename": "runs",
    "indexname": "ix_runs_status",
    "indexdef": "CREATE INDEX ix_runs_status ON public.runs USING btree (status)"
  },
  {
    "tablename": "runs",
    "indexname": "ix_runs_status_created",
    "indexdef": "CREATE INDEX ix_runs_status_created ON public.runs USING btree (status, created_at)"
  },
  {
    "tablename": "runs",
    "indexname": "runs_pkey",
    "indexdef": "CREATE UNIQUE INDEX runs_pkey ON public.runs USING btree (id)"
  },
  {
    "tablename": "signals",
    "indexname": "ix_signals_card_id",
    "indexdef": "CREATE INDEX ix_signals_card_id ON public.signals USING btree (card_id)"
  },
  {
    "tablename": "signals",
    "indexname": "ix_signals_company_date",
    "indexdef": "CREATE INDEX ix_signals_company_date ON public.signals USING btree (company_id, signal_date)"
  },
  {
    "tablename": "signals",
    "indexname": "ix_signals_company_id",
    "indexdef": "CREATE INDEX ix_signals_company_id ON public.signals USING btree (company_id)"
  },
  {
    "tablename": "signals",
    "indexname": "ix_signals_type",
    "indexdef": "CREATE INDEX ix_signals_type ON public.signals USING btree (type)"
  },
  {
    "tablename": "signals",
    "indexname": "ix_signals_type_weight",
    "indexdef": "CREATE INDEX ix_signals_type_weight ON public.signals USING btree (type, weight)"
  },
  {
    "tablename": "signals",
    "indexname": "signals_pkey",
    "indexdef": "CREATE UNIQUE INDEX signals_pkey ON public.signals USING btree (id)"
  },
  {
    "tablename": "sources",
    "indexname": "ix_sources_card_id",
    "indexdef": "CREATE INDEX ix_sources_card_id ON public.sources USING btree (card_id)"
  },
  {
    "tablename": "sources",
    "indexname": "ix_sources_card_local",
    "indexdef": "CREATE INDEX ix_sources_card_local ON public.sources USING btree (card_id, local_id)"
  },
  {
    "tablename": "sources",
    "indexname": "ix_sources_company_id",
    "indexdef": "CREATE INDEX ix_sources_company_id ON public.sources USING btree (company_id)"
  },
  {
    "tablename": "sources",
    "indexname": "sources_pkey",
    "indexdef": "CREATE UNIQUE INDEX sources_pkey ON public.sources USING btree (id)"
  },
  {
    "tablename": "trend_articles",
    "indexname": "ix_trend_articles_category",
    "indexdef": "CREATE INDEX ix_trend_articles_category ON public.trend_articles USING btree (category)"
  },
  {
    "tablename": "trend_articles",
    "indexname": "ix_trend_articles_category_pubdate",
    "indexdef": "CREATE INDEX ix_trend_articles_category_pubdate ON public.trend_articles USING btree (category, published_date)"
  },
  {
    "tablename": "trend_articles",
    "indexname": "ix_trend_articles_discovery_run_id",
    "indexdef": "CREATE INDEX ix_trend_articles_discovery_run_id ON public.trend_articles USING btree (discovery_run_id)"
  },
  {
    "tablename": "trend_articles",
    "indexname": "ix_trend_articles_published_date",
    "indexdef": "CREATE INDEX ix_trend_articles_published_date ON public.trend_articles USING btree (published_date)"
  },
  {
    "tablename": "trend_articles",
    "indexname": "ix_trend_articles_status",
    "indexdef": "CREATE INDEX ix_trend_articles_status ON public.trend_articles USING btree (status)"
  },
  {
    "tablename": "trend_articles",
    "indexname": "ix_trend_articles_status_pubdate",
    "indexdef": "CREATE INDEX ix_trend_articles_status_pubdate ON public.trend_articles USING btree (status, published_date)"
  },
  {
    "tablename": "trend_articles",
    "indexname": "ix_trend_articles_url",
    "indexdef": "CREATE UNIQUE INDEX ix_trend_articles_url ON public.trend_articles USING btree (url)"
  },
  {
    "tablename": "trend_articles",
    "indexname": "trend_articles_pkey",
    "indexdef": "CREATE UNIQUE INDEX trend_articles_pkey ON public.trend_articles USING btree (id)"
  },
  {
    "tablename": "web_discovery_clusters",
    "indexname": "ix_web_discovery_clusters_is_active",
    "indexdef": "CREATE INDEX ix_web_discovery_clusters_is_active ON public.web_discovery_clusters USING btree (is_active)"
  },
  {
    "tablename": "web_discovery_clusters",
    "indexname": "ix_web_discovery_clusters_last_run_at",
    "indexdef": "CREATE INDEX ix_web_discovery_clusters_last_run_at ON public.web_discovery_clusters USING btree (last_run_at)"
  },
  {
    "tablename": "web_discovery_clusters",
    "indexname": "ix_web_discovery_clusters_priority",
    "indexdef": "CREATE INDEX ix_web_discovery_clusters_priority ON public.web_discovery_clusters USING btree (priority)"
  },
  {
    "tablename": "web_discovery_clusters",
    "indexname": "ix_web_discovery_clusters_slug",
    "indexdef": "CREATE INDEX ix_web_discovery_clusters_slug ON public.web_discovery_clusters USING btree (slug)"
  },
  {
    "tablename": "web_discovery_clusters",
    "indexname": "web_discovery_clusters_pkey",
    "indexdef": "CREATE UNIQUE INDEX web_discovery_clusters_pkey ON public.web_discovery_clusters USING btree (id)"
  },
  {
    "tablename": "web_discovery_clusters",
    "indexname": "web_discovery_clusters_slug_key",
    "indexdef": "CREATE UNIQUE INDEX web_discovery_clusters_slug_key ON public.web_discovery_clusters USING btree (slug)"
  },
  {
    "tablename": "web_discovery_queries",
    "indexname": "ix_web_discovery_queries_cluster_created",
    "indexdef": "CREATE INDEX ix_web_discovery_queries_cluster_created ON public.web_discovery_queries USING btree (cluster_id, created_at)"
  },
  {
    "tablename": "web_discovery_queries",
    "indexname": "ix_web_discovery_queries_cluster_id",
    "indexdef": "CREATE INDEX ix_web_discovery_queries_cluster_id ON public.web_discovery_queries USING btree (cluster_id)"
  },
  {
    "tablename": "web_discovery_queries",
    "indexname": "ix_web_discovery_queries_is_active",
    "indexdef": "CREATE INDEX ix_web_discovery_queries_is_active ON public.web_discovery_queries USING btree (is_active)"
  },
  {
    "tablename": "web_discovery_queries",
    "indexname": "web_discovery_queries_pkey",
    "indexdef": "CREATE UNIQUE INDEX web_discovery_queries_pkey ON public.web_discovery_queries USING btree (id)"
  }
]

```

**Indexes missing (warnings only):**

```text

```

---

## Step 7 — Test that required fields are actually required

Pick `name` on `web_discovery_clusters`:

```sql
INSERT INTO web_discovery_clusters (
  id,
  slug,
  is_active,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'test-missing-name',
  true,
  now(),
  now()
);
```

**Expected:** `ERROR` — `name` is NOT NULL (and likely fails `ck_web_discovery_clusters_name_nonempty`).

If it succeeds, the database allows incomplete cluster rows.

Similarly test `company_name` on `companies`:

```sql
INSERT INTO companies (id, domain, created_at, updated_at)
VALUES (gen_random_uuid(), 'orphan.example', now(), now());
```

**Expected:** `ERROR` — `company_name` is required.

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Error message from the bad `web_discovery_clusters` insert and the bad `companies` insert. Both should fail.

**Cluster insert (missing `name`):**

```text
Execution failed. All statements are aborted. Details: pq: null value in column "name" of relation "web_discovery_clusters" violates not-null constraint

```

**Company insert (missing `company_name`):**

```text
Execution failed. All statements are aborted. Details: pq: null value in column "company_name" of relation "companies" violates not-null constraint

```

---

## Step 8 — Test cluster → query relationship

Create a test cluster:

```sql
INSERT INTO web_discovery_clusters (
  id,
  name,
  slug,
  description,
  priority,
  is_active,
  include_keywords,
  exclude_keywords,
  geography_focus,
  source_preferences,
  signal_priorities,
  query_count,
  signal_count,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'Test Cluster',
  'test-cluster-schema-verify',
  'Temporary schema verification cluster',
  'P2 Daily Intelligence',
  true,
  '["nicotine pouch"]'::jsonb,
  '["cigarettes"]'::jsonb,
  '["Canada"]'::jsonb,
  '["news", "web"]'::jsonb,
  '["PRODUCT", "REGULATORY"]'::jsonb,
  0,
  0,
  now(),
  now()
)
RETURNING id;
```

Copy the returned `id`, then insert a query:

```sql
INSERT INTO web_discovery_queries (
  id,
  cluster_id,
  label,
  search_query,
  search_type,
  num_results,
  is_active,
  content_highlights,
  content_text,
  content_summary,
  structured_outputs,
  text_main_content_only,
  livecrawl_timeout_ms,
  subpages,
  extra_links,
  extra_image_links,
  subpage_target_keywords,
  include_domains,
  exclude_domains,
  content_moderation,
  stream_response,
  additional_queries,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'PASTE_CLUSTER_ID_HERE',
  'Test Query',
  'new nicotine-free pouch brands in Canada',
  'auto',
  10,
  true,
  true,
  false,
  false,
  false,
  true,
  10000,
  0,
  0,
  0,
  '[]'::jsonb,
  '[]'::jsonb,
  '[]'::jsonb,
  false,
  false,
  '[]'::jsonb,
  now(),
  now()
)
RETURNING id;
```

**Expected:** Both inserts succeed. Save both IDs for Step 10.

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** `RETURNING id` values from cluster and query inserts.


| ID             | Value                                |
| -------------- | ------------------------------------ |
| **CLUSTER_ID** | 4d7b55a9-2a9c-4368-b1b0-0d9b0f1dbba0 |
| **QUERY_ID**   | 66dc61bb-878a-4959-baa3-161f4c69ee16 |


```text
(output in table above)

```

---

## Step 9 — Test that bad relationships fail

```sql
INSERT INTO web_discovery_queries (
  id,
  cluster_id,
  label,
  search_query,
  search_type,
  num_results,
  is_active,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  gen_random_uuid(),
  'Bad Query',
  'this should fail',
  'auto',
  10,
  true,
  now(),
  now()
);
```

**Expected:** `ERROR` — foreign key violation on `cluster_id`.

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Error message from the insert with a fake `cluster_id`. Insert must **not** succeed.

```text
Execution failed. All statements are aborted. Details: pq: insert or update on table "web_discovery_queries" violates foreign key constraint "web_discovery_queries_cluster_id_fkey"

```

---

## Step 10 — Insert one full fake NORAD workflow

This is the most important check. It proves the schema supports the real product flow:

```text
Admin cluster
→ Admin query
→ Web discovery run (source_kind = web_discovery)
→ Article (ingested from run)
→ Article signal
→ Deep research run (source_kind = research) — simulates +ADD
→ Company
→ Card (review_status = draft)
→ Research signal + source
→ Watchlist flag
```

Use the cluster and query IDs from Step 8, or create fresh ones. Run as a single transaction where your client supports it.

### 10a — Web discovery run

```sql
INSERT INTO runs (
  id,
  query,
  source_kind,
  status,
  progress_pct,
  engines,
  engine_outputs,
  started_at,
  completed_at,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'Test Cluster batch — schema verify',
  'web_discovery',
  'completed',
  100,
  jsonb_build_object(
    'cluster_id', 'PASTE_CLUSTER_ID_HERE',
    'query_ids', jsonb_build_array('PASTE_QUERY_ID_HERE')
  ),
  '{}'::jsonb,
  now(),
  now() - interval '2 minutes',
  now(),
  now()
)
RETURNING id;
```

Save as `RUN_WD_ID`.

### 10b — Article + article signal

```sql
INSERT INTO articles (
  id,
  url,
  title,
  summary,
  source_name,
  published_at,
  ingested_at,
  cluster_id,
  query_run_id,
  category_tag,
  priority_score,
  mentioned_companies,
  status,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'https://example.com/schema-verify-nicotine-pouch-story',
  'Schema Verify — New pouch brand launches in Canada',
  'Temporary test article for GCP schema verification.',
  'Example News',
  now() - interval '1 day',
  now(),
  'PASTE_CLUSTER_ID_HERE',
  'RUN_WD_ID',
  'MED-NIC',
  78,
  '[]'::jsonb,
  'active',
  now(),
  now()
)
RETURNING id;
```

Save as `ARTICLE_ID`.

```sql
INSERT INTO article_signals (
  id,
  article_id,
  signal_type,
  score,
  headline,
  created_at
)
VALUES (
  gen_random_uuid(),
  'ARTICLE_ID',
  'PRODUCT',
  78,
  'New nicotine-free pouch SKU',
  now()
);
```

### 10c — Company (before card — breaks circular FK)

```sql
INSERT INTO companies (
  id,
  company_name,
  domain,
  industry,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'Schema Verify Co',
  'schemaverify.example',
  'Consumer Goods',
  now(),
  now()
)
RETURNING id;
```

Save as `COMPANY_ID`.

### 10d — Deep research run

```sql
INSERT INTO runs (
  id,
  query,
  source_kind,
  status,
  progress_pct,
  engines,
  engine_outputs,
  company_id,
  started_at,
  completed_at,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'Schema Verify Co — schemaverify.example',
  'research',
  'completed',
  100,
  jsonb_build_object('provenance', 'schema_verify_test'),
  '{}'::jsonb,
  'COMPANY_ID',
  now() - interval '5 minutes',
  now(),
  now(),
  now()
)
RETURNING id;
```

Save as `RUN_RS_ID`.

### 10e — Card (Pending Review)

```sql
INSERT INTO cards (
  id,
  company_id,
  run_id,
  schema_version,
  card,
  score_overall,
  review_status,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'COMPANY_ID',
  'RUN_RS_ID',
  '1.0',
  '{"identity": {"company_name": {"value": "Schema Verify Co", "confidence": "confirmed"}}}'::jsonb,
  72,
  'draft',
  now(),
  now()
)
RETURNING id;
```

Save as `CARD_ID`.

### 10f — Wire canonical card + run.card_id

```sql
UPDATE companies
SET canonical_card_id = 'CARD_ID', updated_at = now()
WHERE id = 'COMPANY_ID';

UPDATE runs
SET card_id = 'CARD_ID', updated_at = now()
WHERE id = 'RUN_RS_ID';
```

**Expected:** Both updates succeed (composite FK `(canonical_card_id, id) → cards(id, company_id)` holds).

Result: Statement executed successfully

### 10g — Research signal + source

```sql
INSERT INTO signals (
  id,
  company_id,
  card_id,
  type,
  headline,
  weight,
  source_refs,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'COMPANY_ID',
  'CARD_ID',
  'growth',
  'Schema verify — revenue growth signal',
  7,
  '[1]'::jsonb,
  now(),
  now()
);

INSERT INTO sources (
  id,
  company_id,
  card_id,
  local_id,
  url,
  title,
  trust_tier,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'COMPANY_ID',
  'CARD_ID',
  1,
  'https://schemaverify.example/about',
  'Company website',
  'A',
  now(),
  now()
);
```

Result: Statement executed successfully

### 10h — Watchlist (MVP)

If `companies.is_watchlisted` exists:

```sql
UPDATE companies
SET is_watchlisted = true, updated_at = now()
WHERE id = 'COMPANY_ID';
```

Result: Execution failed. All statements are aborted. Details: pq: column "is_watchlisted" of relation "companies" does not exist

If instead you have a `watchlist_entries` table:

```sql
INSERT INTO watchlist_entries (id, company_id, promoted_at, created_at, updated_at)
VALUES (gen_random_uuid(), 'COMPANY_ID', now(), now(), now());
```

Result: Execution failed. All statements are aborted. Details: pq: relation "watchlist_entries" does not exist

**Minimum records created:**

```text
1 web_discovery_cluster
1 web_discovery_query
1 run (source_kind = web_discovery)
1 article linked to cluster + query_run_id
1 article_signal
1 company
1 run (source_kind = research)
1 card (review_status = draft)
1 signal + 1 source (composite FK to card)
1 watchlist representation (flag or entry)
```

If all inserts succeed, the schema is usable for Phase 2 API wiring.

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** IDs returned from each sub-step and any error messages. All sub-steps (10a–10h) should succeed.


| ID             | Value                                |
| -------------- | ------------------------------------ |
| **RUN_WD_ID**  | f62f39b9-4c46-4e86-9f24-f8b763a73d17 |
| **ARTICLE_ID** |                                      |
| **COMPANY_ID** | 3efc1a49-2d41-40ff-b92b-b4d4c794647d |
| **RUN_RS_ID**  | a53f54fd-1256-4e26-875b-a39447d56f5d |
| **CARD_ID**    | 51e79efb-33fb-46d4-a71e-b7a02b12927b |


```text
(paste insert / update output here)

```

**Sub-step that failed (if any):**

```text
10b and 10h
```

---

## Step 11 — Analyst feed can read admin-run articles

Analysts do **not** create clusters or queries — they read `articles` produced by operator runs ([P1-01-user §7](./P1-01-user.md), [P1-06 §II.1](./P1-06.md#ii1-articles-news--signals)).

```sql
SELECT
  a.id,
  a.title,
  a.url,
  a.priority_score,
  a.status,
  a.category_tag,
  c.name AS cluster_name,
  r.status AS run_status,
  r.source_kind
FROM articles a
LEFT JOIN web_discovery_clusters c ON a.cluster_id = c.id
LEFT JOIN runs r ON a.query_run_id = r.id
ORDER BY a.ingested_at DESC
LIMIT 20;
```

**Expected:** At least one row from Step 10 with `source_kind = web_discovery` and `status = active`.

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Query result rows — confirm article joins to cluster and run.

```text
Execution failed. All statements are aborted. Details: pq: relation "articles" does not exist

```

---

## Step 12 — Pending Review (no separate table)

Pending Review is a **view** over `cards.review_status = 'draft'` joined to `companies` ([P1-04 §8.2](./P1-04-admin.md#82-pending-review-item-analyst-queue--documented-for-shared-backend)).

```sql
SELECT
  cards.id AS card_id,
  companies.company_name,
  companies.domain,
  cards.score_overall,
  cards.review_status,
  cards.run_id,
  cards.created_at
FROM cards
JOIN companies ON cards.company_id = companies.id
WHERE cards.review_status = 'draft'
ORDER BY cards.created_at DESC;
```

**Expected:** The Step 10 card appears with `review_status = draft`.

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Pending review query output — at least one `draft` card for Schema Verify Co.

```text
[
  {
    "card_id": "51e79efb-33fb-46d4-a71e-b7a02b12927b",
    "company_name": "Schema Verify Co",
    "domain": "schemaverify.example",
    "score_overall": "72",
    "review_status": "draft",
    "run_id": "a53f54fd-1256-4e26-875b-a39447d56f5d",
    "created_at": "2026-06-18T00:51:32.612027Z"
  }
]

```

---

## Step 13 — Watchlist

MVP path — filter on `companies.is_watchlisted`:

```sql
SELECT
  companies.id,
  companies.company_name,
  companies.domain,
  companies.industry,
  companies.is_watchlisted,
  companies.updated_at
FROM companies
WHERE companies.is_watchlisted = true
ORDER BY companies.updated_at DESC;
```

**Expected:** `Schema Verify Co` appears after Step 10h.

If using `watchlist_entries` instead:

```sql
SELECT
  watchlist_entries.id,
  companies.company_name,
  companies.domain,
  watchlist_entries.promoted_at
FROM watchlist_entries
JOIN companies ON watchlist_entries.company_id = companies.id
ORDER BY watchlist_entries.promoted_at DESC;
```

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Watchlist query output (`is_watchlisted` or `watchlist_entries` — note which path you used).

**Path used:** ☐ `companies.is_watchlisted` · ☐ `watchlist_entries`

```text
Execution failed. All statements are aborted. Details: pq: column companies.is_watchlisted does not exist

Execution failed. All statements are aborted. Details: pq: relation "watchlist_entries" does not exist
```





---

## Step 14 — Optional: pipeline infrastructure smoke

### Run events

```sql
INSERT INTO run_events (id, run_id, kind, message, level, meta, created_at, updated_at)
VALUES (
  gen_random_uuid(),
  'f62f39b9-4c46-4e86-9f24-f8b763a73d17',
  'log',
  'Schema verify — run event test',
  'info',
  '{}'::jsonb,
  now(),
  now()
);
```

### Engine call audit row

Adjust payload column names to match your DDL (`request_payload` vs `request_snapshot`):

```sql
INSERT INTO engine_calls (
  id,
  run_id,
  vendor,
  operation,
  units,
  input_tokens,
  output_tokens,
  cost_usd,
  latency_ms,
  status,
  request_payload,
  response_payload,
  meta,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  'RUN_WD_ID',
  'exa',
  'search',
  1,
  0,
  0,
  0.01,
  420.5,
  'ok',
  '{"q": "schema verify"}'::jsonb,
  '{"results": []}'::jsonb,
  '{}'::jsonb,
  now(),
  now()
);
```

### App KV research config

```sql
SELECT key, jsonb_object_keys(value) AS top_level_keys
FROM app_kv
WHERE key = 'research_config';
```

**Expected:** One row (may be seeded empty `{}` until Settings is used).

### Documentation — paste your results


| Field         | Value                   |
| ------------- | ----------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A |
| **Tested by** |                         |
| **Date**      |                         |


**What to paste:** Confirm `run_events` insert, `engine_calls` insert, and `app_kv` select all succeeded (or note which failed).

**Run event insert:**

```text
Statement executed successfully

```

**Engine call insert:**

```text
Statement executed successfully
```

**App KV select:**

```text
[
  {
    "key": "research_config",
    "top_level_keys": "exa"
  },
  {
    "key": "research_config",
    "top_level_keys": "diffbot"
  },
  {
    "key": "research_config",
    "top_level_keys": "parallel"
  }
]

```

---

## Step 15 — Clean up test data (optional)

After verification, delete test rows in dependency order:

```sql
-- Replace IDs with your Step 8–10 values
DELETE FROM article_signals WHERE article_id = 'ARTICLE_ID';
DELETE FROM articles WHERE id = 'ARTICLE_ID';
DELETE FROM engine_calls WHERE run_id IN ('RUN_WD_ID', 'RUN_RS_ID');
DELETE FROM run_events WHERE run_id IN ('RUN_WD_ID', 'RUN_RS_ID');
DELETE FROM sources WHERE company_id = 'COMPANY_ID';
DELETE FROM signals WHERE company_id = 'COMPANY_ID';
UPDATE companies SET canonical_card_id = NULL, is_watchlisted = false WHERE id = 'COMPANY_ID';
DELETE FROM cards WHERE id = 'CARD_ID';
DELETE FROM runs WHERE id IN ('RUN_WD_ID', 'RUN_RS_ID');
DELETE FROM companies WHERE id = 'COMPANY_ID';
DELETE FROM web_discovery_queries WHERE cluster_id = 'PASTE_CLUSTER_ID_HERE';
DELETE FROM web_discovery_clusters WHERE slug = 'test-cluster-schema-verify';
```

### Documentation — paste your results


| Field         | Value                               |
| ------------- | ----------------------------------- |
| **Result**    | ☐ Pass · ☐ Fail · ☐ N/A · ☐ Skipped |
| **Tested by** |                                     |
| **Date**      |                                     |


**What to paste:** Confirmation cleanup ran without FK errors, or paste any error if delete failed.

```text
(paste here)

```

---

## What to Look out for

Screenshots or query output for:

```text
1. List of all tables
2. Columns for each important table (Step 3)
3. Primary key check
4. Foreign key check (including composite FKs)
5. Index list
6. Successful cluster → query insert
7. Failed insert with fake cluster_id
8. Successful full workflow insert (Step 10)
9. Analyst article feed query (Step 11)
10. Pending review query (Step 12)
11. Watchlist query (Step 13)
```

---

## Pass / fail checklist

The GCP schema **passes** if:

```text
✓ All required tables exist (Step 2 — must exist list)
✓ discovery_clusters / trend_articles are not used for new features
✓ articles + article_signals exist (analyst feed)
✓ Required fields reject blank / missing values (Step 7)
✓ Foreign keys prevent bad relationships (Step 9)
✓ Composite FKs on signals / sources / canonical_card_id work (Step 10f–10g)
✓ Indexes exist for major filters (Step 6 — warnings only)
✓ Full fake workflow inserts succeed (Step 10)
✓ Analyst feed query returns admin-run articles (Step 11)
✓ Pending Review works via cards.review_status = draft (Step 12)
✓ Watchlist works via companies.is_watchlisted or watchlist_entries (Step 13)
✓ engine_calls column names match apps/api models (Step 3 note)
```

If all of that passes, you are ready for the next step:

```text
Point apps/api at the GCP Cloud SQL connection string and run smoke tests.
```

### Documentation — overall sign-off


| Field              | Value           |
| ------------------ | --------------- |
| **Overall result** | ☐ Pass · ☐ Fail |
| **Signed off by**  |                 |
| **Date**           |                 |


**Summary / blockers:**

```text
(paste final notes here)

```

**Steps that failed (if any):**

```text

```

---

## Hardening gates before seed data and API contracts

Use this section as a strict go/no-go gate after completing Steps 1-15.

### Recommended run order (deterministic)

Run in this order and stop immediately on the first Critical failure:

```text
1) Gate A (Critical) - required constraints exist
2) Gate B (Critical) - FK delete behavior
3) Gate C (Critical) - unique constraints enforced
4) Step 10 full manual flow (if not already completed)
5) Gate D (High) - full flow integrity assertions
6) Negative tests (must fail)
7) Cloud SQL operational checks
8) Pre-seed / pre-API readiness checklist sign-off
```

Fail-fast rule:

```text
If any Critical gate fails, do not proceed to seed data or API contracts.
Fix schema/migration first, then rerun from Gate A.
```

### Gate A (Critical) - required constraints must exist

```sql
WITH required(conname) AS (
  VALUES
    ('ck_web_discovery_clusters_priority_enum'),
    ('ck_web_discovery_queries_search_type_enum'),
    ('ck_web_discovery_queries_num_results_range'),
    ('ck_runs_progress_pct_range'),
    ('ck_engine_calls_vendor'),
    ('ck_engine_calls_status'),
    ('ck_engine_calls_cost_nonneg'),
    ('ck_signals_weight_range'),
    ('uq_cards_id_company'),
    ('fk_signals_card_company'),
    ('fk_sources_card_company'),
    ('fk_companies_canonical_card')
)
SELECT r.conname AS missing_constraint
FROM required r
LEFT JOIN pg_constraint c ON c.conname = r.conname
WHERE c.oid IS NULL;
```

Expected: `0 rows`.

### Documentation - paste your results


| Field         | Value               |
| ------------- | ------------------- |
| **Result**    | [ ] Pass · [ ] Fail |
| **Tested by** |                     |
| **Date**      |                     |


```text
No rows to display
```

---

### Gate B (Critical) - verify FK delete behavior

```sql
SELECT
  c.conname,
  c.conrelid::regclass AS child_table,
  c.confrelid::regclass AS parent_table,
  CASE c.confdeltype
    WHEN 'a' THEN 'NO ACTION'
    WHEN 'r' THEN 'RESTRICT'
    WHEN 'c' THEN 'CASCADE'
    WHEN 'n' THEN 'SET NULL'
    WHEN 'd' THEN 'SET DEFAULT'
  END AS on_delete
FROM pg_constraint c
WHERE c.contype = 'f'
  AND c.conname IN (
    'fk_signals_card_company',
    'fk_sources_card_company',
    'fk_companies_canonical_card'
  )
ORDER BY c.conname;
```

Expected:

- `fk_signals_card_company = CASCADE`
- `fk_sources_card_company = CASCADE`
- `fk_companies_canonical_card = SET NULL`

### Documentation - paste your results


| Field         | Value               |
| ------------- | ------------------- |
| **Result**    | [ ] Pass · [ ] Fail |
| **Tested by** |                     |
| **Date**      |                     |


```text
[
  {
    "conname": "fk_companies_canonical_card",
    "child_table": "companies",
    "parent_table": "cards",
    "on_delete": "SET NULL"
  },
  {
    "conname": "fk_signals_card_company",
    "child_table": "signals",
    "parent_table": "cards",
    "on_delete": "CASCADE"
  },
  {
    "conname": "fk_sources_card_company",
    "child_table": "sources",
    "parent_table": "cards",
    "on_delete": "CASCADE"
  }
]
```

---

### Gate C (Critical) - unique constraints are enforced

```sql
WITH required AS (
  SELECT 'web_discovery_clusters'::text AS tablename, 'slug'::text AS col UNION ALL
  SELECT 'companies', 'domain' UNION ALL
  SELECT 'articles', 'url' UNION ALL
  SELECT 'runs', 'idempotency_key'
),
present AS (
  SELECT
    t.relname AS tablename,
    a.attname AS col
  FROM pg_index i
  JOIN pg_class t ON t.oid = i.indrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(i.indkey)
  WHERE n.nspname = 'public'
    AND i.indisunique = true
)
SELECT r.*
FROM required r
LEFT JOIN present p
  ON p.tablename = r.tablename
 AND p.col = r.col
WHERE p.tablename IS NULL;
```

Expected: `0 rows`.

### Documentation - paste your results


| Field         | Value               |
| ------------- | ------------------- |
| **Result**    | [ ] Pass · [ ] Fail |
| **Tested by** |                     |
| **Date**      |                     |


```text
[
  {
    "tablename": "articles",
    "col": "url"
  }
]
```

---

### Gate D (High) - full flow integrity assertions

Run this after Step 10 inserts:

```sql
WITH
c AS (
  SELECT id FROM web_discovery_clusters WHERE slug = 'test-cluster-schema-verify'
),
q AS (
  SELECT id, cluster_id FROM web_discovery_queries WHERE cluster_id = (SELECT id FROM c)
),
r_wd AS (
  SELECT id FROM runs
  WHERE source_kind='web_discovery'
    AND query ILIKE '%schema verify%'
  ORDER BY created_at DESC LIMIT 1
),
a AS (
  SELECT id, cluster_id, query_run_id
  FROM articles
  WHERE url='https://example.com/schema-verify-nicotine-pouch-story'
),
asig AS (
  SELECT id, article_id FROM article_signals WHERE article_id = (SELECT id FROM a)
),
co AS (
  SELECT id, canonical_card_id, is_watchlisted
  FROM companies
  WHERE domain='schemaverify.example'
),
r_rs AS (
  SELECT id, company_id, card_id
  FROM runs
  WHERE source_kind IN ('research','user_query')
    AND company_id=(SELECT id FROM co)
  ORDER BY created_at DESC LIMIT 1
),
cd AS (
  SELECT id, company_id, run_id, review_status
  FROM cards
  WHERE company_id=(SELECT id FROM co)
  ORDER BY created_at DESC LIMIT 1
),
sg AS (
  SELECT id FROM signals
  WHERE company_id=(SELECT id FROM co) AND card_id=(SELECT id FROM cd)
),
src AS (
  SELECT id FROM sources
  WHERE company_id=(SELECT id FROM co) AND card_id=(SELECT id FROM cd)
)
SELECT
  (SELECT count(*)=1 FROM c) AS cluster_ok,
  (SELECT count(*)>=1 FROM q) AS query_ok,
  (SELECT count(*)=1 FROM r_wd) AS wd_run_ok,
  (SELECT count(*)=1 FROM a WHERE cluster_id=(SELECT id FROM c) AND query_run_id=(SELECT id FROM r_wd)) AS article_ok,
  (SELECT count(*)>=1 FROM asig) AS article_signal_ok,
  (SELECT count(*)=1 FROM co) AS company_ok,
  (SELECT count(*)=1 FROM r_rs WHERE company_id=(SELECT id FROM co)) AS research_run_ok,
  (SELECT count(*)=1 FROM cd WHERE run_id=(SELECT id FROM r_rs) AND review_status='draft') AS card_pending_review_ok,
  (SELECT count(*)>=1 FROM sg) AS signal_ok,
  (SELECT count(*)>=1 FROM src) AS source_ok,
  (SELECT canonical_card_id=(SELECT id FROM cd) FROM co) AS canonical_card_link_ok,
  (SELECT card_id=(SELECT id FROM cd) FROM r_rs) AS run_card_link_ok,
  (SELECT is_watchlisted FROM co) AS watchlist_flag_ok;
```

Expected: every output column returns `true`.

### Documentation - paste your results


| Field         | Value               |
| ------------- | ------------------- |
| **Result**    | [ ] Pass · [ ] Fail |
| **Tested by** |                     |
| **Date**      |                     |


```text
(paste output here)
```

---

## Negative tests (must fail)

These probes confirm enum and range checks are active.

```sql
-- invalid cluster priority (should fail)
INSERT INTO web_discovery_clusters (
  id,name,slug,priority,is_active,include_keywords,exclude_keywords,geography_focus,source_preferences,signal_priorities,query_count,signal_count,created_at,updated_at
) VALUES (
  gen_random_uuid(),'x','bad-priority-' || substring(md5(random()::text),1,8),
  'P0',
  true,'[]'::jsonb,'[]'::jsonb,'[]'::jsonb,'[]'::jsonb,'[]'::jsonb,0,0,now(),now()
);

```

```sql
-- invalid query search_type (should fail)
INSERT INTO web_discovery_queries (
  id,cluster_id,label,search_query,search_type,num_results,is_active,
  content_highlights,content_text,content_summary,structured_outputs,text_main_content_only,
  livecrawl_timeout_ms,subpages,extra_links,extra_image_links,subpage_target_keywords,
  include_domains,exclude_domains,content_moderation,stream_response,additional_queries,created_at,updated_at
)
VALUES (
  gen_random_uuid(), (SELECT id FROM web_discovery_clusters ORDER BY created_at DESC LIMIT 1),
  'bad','bad','turbo',10,true,true,false,false,false,true,10000,0,0,0,
  '[]'::jsonb,'[]'::jsonb,'[]'::jsonb,false,false,'[]'::jsonb,now(),now()
);
```

```sql
-- invalid run progress_pct (should fail)
INSERT INTO runs (
  id,query,source_kind,status,progress_pct,engines,engine_outputs,created_at,updated_at
) VALUES (
  gen_random_uuid(),'bad','research','queued',101,'{}'::jsonb,'{}'::jsonb,now(),now()
);
```

```sql
-- invalid signal weight (should fail)
INSERT INTO signals (
  id,company_id,card_id,type,headline,weight,source_refs,created_at,updated_at
)
VALUES (
  gen_random_uuid(),
  (SELECT id FROM companies ORDER BY created_at DESC LIMIT 1),
  (SELECT id FROM cards ORDER BY created_at DESC LIMIT 1),
  'growth','bad weight',11,'[]'::jsonb,now(),now()
);
```

### Documentation - paste your results


| Field         | Value               |
| ------------- | ------------------- |
| **Result**    | [ ] Pass · [ ] Fail |
| **Tested by** |                     |
| **Date**      |                     |


```text
(Execution failed. All statements are aborted. Details: pq: new row for relation "web_discovery_clusters" violates check constraint "ck_web_discovery_clusters_priority_enum"

Execution failed. All statements are aborted. Details: pq: new row for relation "web_discovery_queries" violates check constraint "ck_web_discovery_queries_search_type_enum"

Execution failed. All statements are aborted. Details: pq: new row for relation "runs" violates check constraint "ck_runs_progress_pct_range"

Execution failed. All statements are aborted. Details: pq: new row for relation "signals" violates check constraint "ck_signals_weight_range"
```

---

## Cloud SQL operational checks

```sql
-- required for gen_random_uuid()
SELECT extname FROM pg_extension WHERE extname = 'pgcrypto';
```

```sql
SHOW TimeZone;
SHOW transaction_isolation;
SHOW statement_timeout;
SHOW lock_timeout;
```

```sql
SELECT conname, convalidated
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
  AND convalidated = false;
```

Expected:

- `pgcrypto` present
- sane timeout/isolation values documented
- `convalidated = false` returns `0 rows`

### Documentation - paste your results


| Field         | Value               |
| ------------- | ------------------- |
| **Result**    | [ ] Pass · [ ] Fail |
| **Tested by** |                     |
| **Date**      |                     |


```text
pgcrypto
UTC
no rows to display
```

---

## Pre-seed and pre-API contract readiness checklist

Proceed only when all items below are checked:

```text
[ ] Gate A passed (required constraints exist)
[ ] Gate B passed (FK delete behavior correct)
[ ] Gate C passed (unique constraints enforced)
[ ] Gate D passed (full flow integrity all true)
[ ] Negative tests failed as expected
[ ] Cloud SQL operational checks passed
[ ] Step 10 full manual flow succeeds end-to-end:
    cluster -> query -> run -> article -> signal -> company -> card -> pending review -> watchlist
```

---

## Related docs


| Doc                                | Use                                           |
| ---------------------------------- | --------------------------------------------- |
| [P1-04-admin.md](./P1-04-admin.md) | Field tables + ER diagrams                    |
| [P1-03.md](./P1-03.md)             | Object relationships                          |
| [P1-06.md](./P1-06.md)             | API actions that will read/write these tables |
| `apps/api/sql/`                    | Versioned DDL applied to Postgres             |
| `apps/api/app/models/`             | ORM definitions the API expects               |


