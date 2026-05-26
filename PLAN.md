# NORAD — Active Plan

> Single-user brand-intel + BD deal-sourcing engine. Monorepo: `apps/api`
> (FastAPI · Python 3.11 · async SQLAlchemy on Supabase Postgres) and
> `apps/web` (Vite · React · TS · Tailwind). Two pipelines: **Discovery**
> (find candidates) and **Research** (deep card per company). Every vendor
> call lands in `engine_calls`; live SSE feed reads from `run_events`.
> Full conventions in `.cursor/rules/norad-conventions.mdc`. Field guide:
> `docs/backend-pipeline.md`. Session-by-session log: `JOURNAL.md`.

---

## Current initiative — Diffbot Knowledge Graph integration

Add Diffbot KG (`Enhance` endpoint) as a **third research engine** alongside
Parallel + Exa. Every research run gets a structured org record with
~150 fields and origin URLs attached, so Claude can mark facts
`confidence=confirmed` with real source citations instead of demoting them
to `inferred`.

**Always-call + no gating.** The full Diffbot response (incl. match score)
goes to the synthesizer regardless of score; Claude decides how much to
weight it. Master on/off lives in `app_kv.research_config.diffbot.enabled`.

### Stage 2 fan-out (new sequencing)

- If `domain_hint` known up front → fan out all three in parallel (Parallel ‖ Exa ‖ Diffbot).
- If no `domain_hint` → fire Parallel + Exa concurrently, **wait for Exa**, derive a likely domain from Exa results, then call Diffbot with `url=<derived>`. Falls back to name-only Diffbot if Exa yielded no clean domain.

### Steps

| # | Scope | Status |
|---|---|---|
| 1 | Engine plumbing — `diffbot_client.py`, `log_diffbot_call`, `_pricing.diffbot_cost_usd`, `DIFFBOT_API_KEY` in config + `.env.example`, `engine_calls.vendor` constraint extended (`sql/0001_*.sql` applied to Supabase). Smoke-tested live (Stripe match score 0.85). | ✅ Done |
| 2 | Settings plumbing — `DiffbotConfig {enabled, score_threshold}` in `services/settings.py`; `routers/settings.py` exposes it; `app_kv` row migrated (`sql/0002_*.sql` applied to Supabase); frontend Diffbot card with toggle + threshold in `Settings.tsx`. | ✅ Done |
| 3 | Stage 2 wiring — `_stage2_diffbot()` + `_derive_domain_from_exa()` helper + branched orchestration in `execute_research()` (3-way fan-out when domain known, sequential Exa→derive→Diffbot otherwise). | ✅ Done |
| 4 | Synthesizer prompt — `DIFFBOT KG EVIDENCE` block in user msg, third stream described in `_SYNTH_SYSTEM` with Diffbot origins eligible for `confirmed`; candidate registry now seeds Diffbot origin URLs. | ✅ Done |
| 5 | Run timeline — `diffbot_lookup_started` / `_completed` / `_skipped` / `_domain_derived` events with `meta: {score, hits, has_entity, status, latency_ms, below_threshold}`. | ✅ Done |

**All 5 steps complete.** Diffbot is now a live participant in every research run (subject to the `enabled` toggle in `/settings`).

### Decisions already made

- Confidence threshold: **none** — show every Diffbot hit with score attached, let Claude weigh it.
- Cost ledger: Diffbot rows write `cost_usd = 0.0` (plan-bundled). Per-run total stays ~$2.95.
- No new DB tables — facts live inside `engine_calls.response_payload` (JSONB); when Claude promotes them, they become normal `Source` / `Signal` rows with the Diffbot **origin URL** (user clicks through to the original page, never to Diffbot).

### Open questions (defer until needed)

- Per-field freshness cap (e.g. don't trust 3-year-old revenue) — punt to Phase 6.
- Settings UI exposure of `score` per call on the Run timeline — punt to Phase 5+.

---

## Backlog (post-Diffbot)

- People graph via Diffbot **Combine** API for `PeopleAndDecisionMap` (weakest current block).
- Discovery via Diffbot **DQL Search** as an alternative source_kind to Exa+trendhunter.
- Per-fact freshness gating.
- arq worker swap-in (today: `asyncio.create_task` in routers — admission cap 5).
