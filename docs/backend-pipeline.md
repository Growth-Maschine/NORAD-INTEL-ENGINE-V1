# NORAD Backend Pipelines — Field Guide

This is the senior-dev reference for how the two backend pipelines actually
run, what each stage sends + receives, where to look when something is wrong,
and how to inspect end-to-end traces.

> TL;DR — every Claude/Parallel/Exa call writes a row to `engine_calls` with
> the FULL request + response payload (JSONB, truncated at 100KB), and every
> stage emit goes to BOTH the `run_events` DB table AND
> `apps/api/logs/pipeline.jsonl` so you can `tail -f` any run.

---

## 1. Two pipelines

| Pipeline      | Entry point                               | Service                       | Avg cost / run |
|---------------|-------------------------------------------|-------------------------------|----------------|
| **Discovery** | `POST /api/discovery/runs`                | `app/services/discovery.py`   | $0.10 - $0.20  |
| **Research**  | `POST /api/research/runs`                 | `app/services/research.py`    | $2.80 - $3.10  |

Both write to the same `runs`, `run_events`, and `engine_calls` tables; the
`pipeline` field in the JSONL log distinguishes them.

---

## 2. Discovery pipeline (Today page)

Goal: surface fresh trend articles + their extracted companies so the user has
a daily inbox of candidates to push into deep research.

```
Stage 1 — Exa search (trendhunter.com)        ~$0.005 × 2 queries
Stage 2 — dedup vs existing trend_articles    (free, DB only)
Stage 3 — Haiku 4.5 batch-rank up to 30 cands ~$0.001 / article
Stage 4 — Exa /contents on top 15             ~$0.005 × 15 = $0.075
Stage 5 — Sonnet 4.5 extract companies/summary~$0.01 / article
```

**Models:**
- Ranking → `claude-haiku-4-5` (cheap, fast, batch-friendly)
- Extraction → `claude-sonnet-4-5` (same model as research synth)

**Outputs:** Rows in `trend_articles` with `relevance_score`, `summary`,
`extracted_companies` (jsonb array of `{name, excerpt, hint_url}`).

**Where to debug:**
- `engine_calls WHERE run_id=… AND vendor='anthropic'` — every Haiku/Sonnet
  call with its full prompt + response
- `apps/api/logs/pipeline.jsonl | jq 'select(.pipeline=="discovery" and .run_id=="…")'`

---

## 3. Research pipeline (Deep Research / Company Card)

The expensive one. Produces ONE validated `CompanyCardV1` per company.

### Stage 1 — Article context (~free)
Loads the originating `TrendArticle` if `trend_article_id` was passed.
Binds the per-company excerpt the discovery stage extracted.

### Stage 2 — Fan-out (Parallel + Exa in parallel)

**Parallel Task API**
- Processor: `pro` ($2.50 flat) — overridable from `/settings`
- Input: `{company_name, domain_hint, instruction, article_context?}`
- Output schema: `_PARALLEL_RESEARCH_SCHEMA` — compact brief, NOT the full card
  - `minItems: 3` on `signals`
  - Includes hard "MUST contain 3-8 signals" description text
- Returns: structured JSON brief (identity, funding, signals, sources)

**Exa**
- 2 deep searches (`{company} overview product founders [site:domain]`,
  `{company} funding investors news 2024 2025`)
- Search type: `deep`, model: `deep-reasoning`, num_results: 10
- Then `/contents` on top 5 unique URLs
- Returns: list of `ExaContent` (url, title, full text, published_date)

Either engine alone is enough to continue. Both failing kills the run.

### Stage 3 — Claude synthesizer

- Model: `claude-sonnet-4-5`
- Tool: `synthesize_company_card` — input_schema = trimmed `CompanyCardV1`
  contract (Tier C fields stripped, see `get_contract_schema()`)
- System prompt: `_SYNTH_SYSTEM` in `research.py`. Hard rules:
  - Every `Valued` field with a non-null value MUST have non-unknown confidence
  - `confirmed` requires ≥1 source citation
  - `estimated`/`inferred` requires non-empty `basis` text
  - `signals` MUST contain ≥3 entries — with a list of fallback signal types
    for low-data companies (founder background, hiring, niche positioning,
    customer review themes, etc.)
  - `sources_and_confidence.sources` MUST contain ≥3 entries
- User message: target name + domain hint + (optional) article context +
  full Parallel JSON + Exa snippets (5 docs × 6000 chars cap)
- Returns: tool_input dict

**Retry-on-thin:** if signals < 3 OR sources < 3, fire ONE retry with the
previous response as context and explicit "you returned only X — please return
≥3" guidance. Logged as `synthesize_card_retry` operation + `synthesis_retry`
run_event. Retry result only accepted if it's strictly better.

### Stage 3.5 — Sanitizer

`_sanitize_card_dict` walks the tool output before Pydantic validation:
- normalizes `"high"` → `"confirmed"`, `"medium"` → `"estimated"`, `"low"` →
  `"inferred"` for per-field `Valued.confidence` (NB: this enum is different
  from the overall confidence enum which is `high|medium|low|unknown`)
- flips `value=X, confidence=unknown` → `inferred` (if basis exists) or drops
  the value (honest > wrong)
- adds boilerplate `"Derived from cited sources."` basis when sources exist
  but basis missing
- demotes `confirmed` without sources → `inferred` or `unknown`

### Stage 4 — Persist

Atomic transaction:
- Upsert `Company` (by run pin → domain → new) with denormalized columns
- Insert `Card` with full JSONB blob + extracted score columns
- Insert one `Source` row per `sources_and_confidence.sources` (preserves
  `local_id` for footnote refs)
- Insert one `Signal` row per signal (composite FK to ensure card_id alignment)
- Point `Company.canonical_card_id` at the new card

---

## 4. Logging + tracing — where to look

### A. `engine_calls` table (per-vendor I/O + cost)

Every Claude / Parallel / Exa call writes one row:
```sql
SELECT vendor, operation, status, latency_ms, cost_usd,
       request_payload, response_payload
FROM engine_calls
WHERE run_id = '<uuid>'
ORDER BY created_at;
```
- `request_payload` jsonb — what we sent (system, messages, tool meta, search query, etc.)
- `response_payload` jsonb — what we got back (Claude tool_calls, Parallel
  output_json + citations, Exa URLs + content sizes)
- Payloads > 100KB are stored as `{_truncated: true, _head: "…", _original_chars: N}`

### B. `run_events` table (state changes)

```sql
SELECT kind, level, message, meta, created_at
FROM run_events
WHERE run_id = '<uuid>' ORDER BY created_at;
```
Useful kinds:
- `run_started` / `run_completed` / `run_failed`
- `stage_started` / `stage_completed` (with `stage` int in meta)
- `synthesis_retry` / `synthesis_retry_done` (with `signals_returned`, `sources_returned`)
- `log` (warnings/errors)

### C. JSONL pipeline log (`apps/api/logs/pipeline.jsonl`)

One line per `emit()`, structured:
```json
{"ts":"…","pipeline":"research","stage":3,"run_id":"…","kind":"synthesis_retry","level":"warn","message":"…","meta":{…}}
```
Rotates at 10 MB × 5 files (default). Useful patterns:
```bash
# live tail
tail -f apps/api/logs/pipeline.jsonl | jq .

# replay one run end-to-end
jq -c 'select(.run_id=="<uuid>")' apps/api/logs/pipeline.jsonl

# find all retries today
jq -c 'select(.kind=="synthesis_retry")' apps/api/logs/pipeline.jsonl

# find all failed runs
jq -c 'select(.kind=="run_failed")' apps/api/logs/pipeline.jsonl
```

---

## 5. Debugging a bad card — playbook

**Symptom:** card has 0 signals / 0 sources / wrong facts.

1. Grab the `run_id` from the card row (`SELECT run_id FROM cards WHERE id=…`).
2. Pull `engine_calls` for that run — look at the synth row's
   `response_payload.tool_calls[0].input.signals` and
   `…sources_and_confidence.sources`. That's what Claude literally returned.
3. If signals/sources look thin, check for `synthesis_retry` run_event — if
   it fired, the retry result is in another `engine_calls` row with
   `operation='synthesize_card_retry'`.
4. Look at the synth row's `request_payload.messages[0].content` — that's
   the full user_msg Claude saw, including the Parallel JSON + Exa snippets.
   If the Parallel JSON has `signals: []`, the upstream brief was thin —
   look at the Parallel call's `response_payload.output_json`.
5. If Exa returned nothing useful, check the Exa rows'
   `response_payload.urls` + `…fetched[].chars` — were the pages even worth
   crawling?

---

## 6. Schemas + confidence enums

Two confidence enums exist and they are NOT the same. This catches people:

| Field                                          | Enum                                       |
|------------------------------------------------|--------------------------------------------|
| `Valued.confidence` (per field — every field) | `confirmed \| estimated \| inferred \| unknown` |
| `SourcesAndConfidence.overall_confidence`     | `high \| medium \| low \| unknown`           |

The UI hover chip in the company header uses the **overall** enum. Don't mix
them up when writing UI badges.

`Valued[T]` validator rules (enforced post-validate, `apps/api/app/schemas/common.py`):
- value set ⇒ confidence ≠ unknown
- confidence = confirmed ⇒ ≥1 source ref
- confidence = estimated/inferred ⇒ non-empty basis

---

## 7. Tunables — quick reference

`apps/api/app/services/research.py` (top of file):
- `PARALLEL_PROCESSOR = "pro"` — default, overridden by `app_kv.research_config.parallel.processor`
- `EXA_SEARCH_TYPE = "deep"`, `EXA_DEEP_MODEL = "deep-reasoning"`, `EXA_NUM_RESULTS = 10`
- `SYNTH_MODEL = "sonnet"` → alias for `claude-sonnet-4-5`
- `SYNTH_MAX_TOKENS = 16000`, `SYNTH_TIMEOUT_S = 300.0`
- `_SYNTH_MIN_SIGNALS = 3`, `_SYNTH_MIN_SOURCES = 3` (trigger retry below this)

All overridable per-environment without touching code via the Settings page →
`app_kv` row.

---

## 8. Files map

```
apps/api/app/
  services/
    research.py        — full research pipeline (Stages 1-4)
    discovery.py       — Today/funnel pipeline (Stages 1-5)
    run_events.py      — emit(), set_pipeline() — tees to JSONL + DB
    settings.py        — research_config loader
  engines/
    claude_client.py   — async Anthropic wrapper, request_payload snapshot
    parallel_client.py — Parallel Task API client
    exa_client.py      — Exa search + contents
    logging.py         — log_claude/exa/parallel_call → engine_calls
    _pricing.py        — vendor pricing constants + cost helpers
  core/
    pipeline_log.py    — JSONL file logger w/ rotation
  schemas/
    common.py          — Valued, Confidence enums, Source
    company_card.py    — CompanyCardV1 root + sub-blocks
  models/
    engine_call.py     — engine_calls table (now with payload columns)
    run_event.py       — run_events table
    …
```

---

## 8. Lesson: Parallel's JSON Schema is a SUBSET of the spec

**Date learned:** 2026-05-21
**Cost of lesson:** ~3 failed Stay Wyld runs ($0.30 each in synth tokens, plus
multiple wasted human iterations) — every run hit a Parallel 422 in ~100ms,
which the operator only noticed because the engine_calls row was the truth and
the run_events summary just said "Parallel FAIL" without surfacing the body.

**The trap:** added `"minItems": 3` to `_PARALLEL_RESEARCH_SCHEMA["signals"]`
to enforce the ≥3 signals contract at the engine level. Looks innocuous —
`minItems` is standard JSON Schema Draft-07. Parallel's task API rejected it:

```
422: {"error": "Unsupported keyword 'minItems' at path: properties.signals"}
```

**Confirmed-unsupported keywords (do not add to Parallel schemas):**
- `minItems`, `maxItems`, `uniqueItems`
- Almost certainly also: `minLength`, `maxLength`, `pattern`, `minimum`,
  `maximum`, `format`, `multipleOf`, `if/then/else`, `oneOf`, `anyOf`

**Stick to these:** `type`, `properties`, `required`, `additionalProperties`,
`items`, `description`, nullable via `"type": ["string", "null"]`.

**Enforce array-length contracts via:**
1. The schema's `description` field — phrase it as `"REQUIRED: at least N
   items"` so Parallel's planner reads it.
2. A downstream Python check in `research.py` (`len(signals) <
   _PARALLEL_MIN_SIGNALS`) that triggers the one-shot retry with a "you
   returned only X, please return ≥N" nudge.

**Debugging recipe when Parallel mysteriously returns `output_json: null`:**
```sql
SELECT error, left(response_payload::text, 800)
FROM engine_calls
WHERE run_id='…' AND vendor='parallel';
```
The 422 body always names the offending keyword + path — never guess, look.
