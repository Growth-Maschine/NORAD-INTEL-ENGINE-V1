# NORAD — Session Journal

One entry per working session. Newest at top. Keep entries to a paragraph or
two: what we built, what surprised us, what's next. The roadmap lives in
`PLAN.md`; this file is the "what actually happened, in what order" log
that a future agent reads to resume cleanly.

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
