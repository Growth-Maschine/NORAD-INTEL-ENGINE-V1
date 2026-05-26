# NORAD — Session Journal

One entry per working session. Newest at top. Keep entries to a paragraph or
two: what we built, what surprised us, what's next. The roadmap lives in
`PLAN.md`; this file is the "what actually happened, in what order" log
that a future agent reads to resume cleanly.

---

## 2026-05-26 — Diffbot integration · Steps 3 · 4 · 5 (completed)

**Built.** All remaining steps landed in a single commit on `apps/api/app/services/research.py`. Diffbot is now a first-class Stage 2 participant — the pipeline calls it on every research run (gated by `cfg.diffbot.enabled`), the synthesizer reads its entity record as a third evidence stream, and the SSE timeline narrates the call.

- **Step 3 (Stage 2 wiring).**
  - New `_stage2_diffbot(run_id, p, factory, cfg, *, url_hint)` — calls `enhance_organization`, logs to `engine_calls`, never raises. Master kill-switch: when `cfg.diffbot.enabled` is False it returns a synthetic miss without touching the network. Also applies `cfg.diffbot.score_threshold` — sub-threshold hits get downgraded to effective-miss for synthesis purposes (the `engine_calls` row is still written for auditing).
  - New `_derive_domain_from_exa(exa_bundle, company_name)` — picks the most-frequent non-blocklisted host across Exa contents, with a strong-prefer rule when the host's bare-name segment overlaps the company-name slug (verified by unit test: Stripe + LinkedIn/TechCrunch noise → `stripe.com`). Blocklist covers the usual aggregator suspects (LinkedIn, Wikipedia, TechCrunch, Crunchbase, etc.) so we don't accidentally treat press as the company's homepage.
  - Branched orchestration in `execute_research()` — if `p.domain_hint` is known, all three engines fan out concurrently via a single `asyncio.gather`. If not, Parallel is started as a detached task, we await Exa, derive a domain, then call Diffbot with the derived hint, then finally await Parallel. The detached Parallel task is cancelled in the error path so it can't outlive the run.
  - "All engines failed" guard updated: only `not parallel_ok and not exa_ok and not diffbot_ok` aborts the run; any one survivor is enough to synthesize.

- **Step 4 (synthesizer prompt + candidate registry).**
  - `_SYNTH_SYSTEM` rewritten to describe three evidence streams (was two). Added a hard rule: Diffbot origin URLs are first-party provenance and facts cited to them are eligible for `confidence="confirmed"`. Added a weighting hint: trust Diffbot more as `score → 1.0`, less as it approaches 0.5, prefer Exa below that.
  - New `_render_diffbot_evidence(resp)` — compact labelled summary (name, founders, employees, HQ, industries, top-10 competitors, origin URLs) instead of a raw JSON dump. Caps competitors at 10 because Diffbot returns 66 for Stripe (we'd burn the prompt budget otherwise). Handles HIT / MISS / ERROR / TIMEOUT uniformly so the user message stays structurally stable across runs.
  - New `_diffbot_origin_urls(entity)` — pulls origins from `origins` / `origin` / `allUris` / `homepageUri` in that order, dedupes, filters invalid scheme. Capped at 6.
  - `_build_candidate_sources()` now takes a `diffbot_resp` and injects Diffbot origins between the Exa pass and the Parallel passes, with the snippet labelled `"Diffbot origin (match score X.XX)"` so Claude can recognize them. Bumped `max_total` from 12 to 14 to absorb the new entries without crowding Exa/Parallel.
  - The user message gains a `DIFFBOT KG EVIDENCE` block and the closing paragraph now explicitly tells Claude to point `Valued.sources` at Diffbot-origin ids when citing Diffbot-attributed facts.

- **Step 5 (run timeline).** Four new event kinds, all carrying `stage=2` in meta:
  - `diffbot_lookup_started` — `{company_name, url_hint}`
  - `diffbot_lookup_completed` — `{score, hits, has_entity, status, latency_ms, score_threshold, below_threshold}` (level=warn when status != 'ok')
  - `diffbot_lookup_skipped` — emitted when `cfg.diffbot.enabled=False`
  - `diffbot_domain_derived` — emitted in the sequential branch when Exa yielded a usable host
  - Stage 2's existing `stage_started` / `stage_completed` banners now include Diffbot status, score, hits, and cost in their meta so the SSE feed can render a 3-engine summary without parsing inner events.

**Verified.**
- Module imports cleanly (`app.services.research` loads, all new symbols present, signatures correct).
- Helper unit tests passed against fixture data: `_derive_domain_from_exa` (positive, empty, blocklisted-only), `_diffbot_origin_urls` (dedupe + invalid-filter), `_render_diffbot_evidence` (HIT / MISS / ERROR with competitor cap honored), `_build_candidate_sources` (Diffbot origins land in the registry with the right label and tier).
- Lint clean.
- (Skipped a live full-pipeline run — would have cost a real Parallel pro task + Sonnet 4.5 synthesis. The Step-1 live Diffbot smoke test from yesterday already proved the underlying client; today's work is pure plumbing on top of that. Worth doing a paid end-to-end run on the first real `/research` request once the API is restarted.)

**Surprises / notes.**
- Diffbot wraps scalars as `{value, precision, str}` for a few fields (`foundingDate`, `nbEmployees`). Added `_fmt_field_str` / `_fmt_field_int` helpers to render them as flat strings/ints in the evidence block — otherwise the synthesizer sees `{value: 8500, precision: 0}` and treats employee count as a JSON object instead of a number.
- The sequential branch (no `domain_hint`) used to look like the obvious deadlock candidate. Pinning Parallel to an explicit `asyncio.create_task` with a try/finally cancel kept it from outliving the run on the error path. Worth remembering — `asyncio.gather` doesn't compose this case cleanly because we genuinely need Exa to finish first.
- `cfg.diffbot.score_threshold` defaults to 0.0 (everything passes), so for now the threshold is purely a future-tuning knob. When it's raised, sub-threshold responses still get a row in `engine_calls` (for audit), but the synthesizer is told it was a miss. This was intentional: hide low-quality matches from Claude without losing the cost-ledger evidence that we did pay for the call.

**Up next.** Diffbot integration is feature-complete. Backlog items now bubble up: per-fact freshness gating (Phase 6), Diffbot **Combine** API for `PeopleAndDecisionMap`, Diffbot **DQL Search** as an alternative Discovery source. See `PLAN.md` backlog.

---

## 2026-05-26 — Diffbot integration · Step 2

**Built.** Settings plumbing for the new engine — end-to-end, no orchestration
change yet (pipeline still ignores `diffbot.enabled`):

- `apps/api/app/services/settings.py` — new `DiffbotConfig` Pydantic block (`enabled: bool = True`, `score_threshold: float = Field(0.0, ge=0.0, le=1.0)`) added to `ResearchConfig`. Backward-compatible: older `app_kv` rows without a `diffbot` key still validate because Pydantic injects the default block at read time.
- `apps/api/app/routers/settings.py` — `DiffbotPatch` (extra="forbid") wired into `ResearchConfigPatch`. PUT `/api/settings/research` now accepts partial diffbot updates with the same deep-merge semantics as parallel/exa.
- `apps/api/sql/0002_app_kv_research_config_add_diffbot.sql` — idempotent `UPDATE ... value || jsonb_build_object(...)` guarded by `NOT (value ? 'diffbot')`. **Applied to Supabase** via asyncpg (no `psql` on this box); BEFORE row had `{parallel, exa}`, AFTER row has `{parallel, exa, diffbot:{enabled:true, score_threshold:0.0}}`.
- `apps/web/src/lib/api.ts` — `DiffbotConfig` interface + `diffbot?: Partial<DiffbotConfig>` on `ResearchConfigPatch`.
- `apps/web/src/pages/Settings.tsx` — new emerald-accent `EngineCard` ("Diffbot Knowledge Graph", `Network` icon, `lg:col-span-2`) with a small role=switch `Toggle` component for `enabled` and a clamped 0–1 number input for `score_threshold`. Save mutation now sends all three blocks. `EngineCard` extended to a third accent variant (`"emerald"`) without breaking existing call sites.

**Surprises / notes.**
- `0.0` score threshold is the *intentional default* — per PLAN.md the synthesizer is supposed to see every hit with its score attached; the threshold is exposed as an escape hatch for future tuning, not a Stage-2 gate.
- Pydantic-settings hated being handed a pre-shell-exported `CORS_ORIGINS` for the round-trip smoke test (interprets it as JSON, chokes). Skipped the in-process round-trip — the DB-level before/after dump was authoritative enough, and lint + types are clean.
- Vite dev server picked up the new card on hot reload without complaints; no extra wiring needed.

**Nothing in the live pipeline reads `cfg.diffbot.enabled` yet — that's Step 3.** Toggling the switch in the UI persists to `app_kv` but doesn't change run behavior until orchestration lands.

**Up next.** Step 3 — Stage 2 wiring: `_stage2_diffbot()` + `_derive_domain_from_exa()` helper + branched orchestration in `execute_research()` (parallel-fan-out when `domain_hint` known, sequential `Exa → derive → Diffbot` otherwise). First step that actually changes user-visible behavior. See `PLAN.md`.

---

## 2026-05-26 — Diffbot integration · Step 1

**Built.** Plumbing-only commit for the third research engine (Diffbot
Knowledge Graph) alongside Parallel + Exa:

- `apps/api/app/engines/diffbot_client.py` — async `httpx` wrapper around `GET /kg/v3/enhance` with `enhance_organization(name, url=None)` and `smoke_check()`. Token is stripped from the `request_params` snapshot before logging.
- `apps/api/app/engines/_pricing.py` — `DIFFBOT_PRICING_USD` (all $0, plan-bundled) + `diffbot_cost_usd(operation)`.
- `apps/api/app/engines/logging.py` — `log_diffbot_call(...)` writes one row per call to `engine_calls` with `meta: {score, esscore, hits, has_entity, kg_version}` so cost queries can filter without parsing JSONB.
- `apps/api/app/engines/__init__.py` — exports `DiffbotClient`, `DiffbotEnhanceResponse`, `get_diffbot_client`, `log_diffbot_call`.
- `apps/api/app/models/engine_call.py` — `VENDORS` tuple + `CheckConstraint` extended to include `'diffbot'`.
- `apps/api/sql/0001_engine_calls_add_diffbot_vendor.sql` — DDL to drop + re-add the constraint. **Applied to Supabase** via the session pooler.
- `apps/api/app/core/config.py` — `diffbot_api_key` setting.
- `apps/api/.env.example` — `DIFFBOT_API_KEY` placeholder.

**Smoke test (live).** `enhance(Stripe, url=stripe.com)` returned score
0.85, 1 hit, 2.4s latency. Pulled fullName, founders (John + Patrick
Collison), 8500 employees, founding date 2010, isPublic=false, 66
competitors. `engine_calls` row inserted cleanly with `vendor='diffbot'` —
the new constraint accepts it. Smoke check against "Diffbot" itself
scored 0.90.

**Surprises / notes.**
- Diffbot auth is query-string `token=…`, not a bearer header. Token sanitized out of `request_params` before snapshot.
- A successful 200 with `hits=0` is `status='ok'` but `succeeded=False`. The orchestrator should gate on `resp.succeeded`, not on `status` alone.
- `competitors` is a fat array (66 entries for Stripe) — when Step 4 builds the synthesizer prompt, we'll want to cap at top-N to keep prompt tokens reasonable.

**Nothing in the live pipeline calls Diffbot yet — pure plumbing, no behavior change for users.**

**Up next.** Step 2 — Settings plumbing (`DiffbotConfig` in
`services/settings.py`, router endpoint, frontend toggle in
`Settings.tsx`). Still no orchestration change. See `PLAN.md`.

---
