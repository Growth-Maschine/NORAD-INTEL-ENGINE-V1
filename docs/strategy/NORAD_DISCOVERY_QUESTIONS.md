# NORAD 1 — Discovery Questions for BAT Stakeholders

**From:** Growth Machine (engineering team building NORAD)
**To:** BAT BD leadership + product sponsor
**Project:** NORAD 1 (BD intelligence engine — first tenant: BAT)
**Purpose:** Lock the open questions before we cut the v1 build estimate and start engineering.
**Format:** ~20 questions, grouped, with a one-line "why we're asking" attached to each.
**Read time:** 5 minutes. Response time: 30–45 minutes.

> Where you don't yet have a firm answer, our recommended default is shown in *italics* at the end of the question. Confirming the default is an acceptable answer.

---

## A. Product Paradigm & User Experience  *(critical — defines the whole UX)*

**A1. Should NORAD be a scheduled-batch system with a dashboard to browse, or an interactive search system where analysts type questions and get results back?**
*Why we're asking:* This is the single biggest design decision. The current plan is **scheduled-batch + browse** — twice a day the engine runs, BD opens the dashboard and reviews a pre-computed ranked list. The interactive ("type a query, get a synthesised answer") model needs an additional Natural Language Search layer (~$50–200/mo extra and 3–4 weeks added scope).
*Default if no answer:* **Scheduled-batch + browse for v1; Natural Language Search added in Phase 2.**

**A2. Where should opportunities be surfaced to the BD team — in the NORAD dashboard only, by daily email digest, in Slack/Teams, or all three?**
*Why we're asking:* Notification channels affect engagement. Most teams reach for email + dashboard; Slack/Teams adds a small connector but increases adoption.
*Default:* **Daily email digest at 9 AM ET + dashboard. Slack as a Phase 2 add.**

**A3. Is mobile access required for BD analysts, or is desktop-only acceptable for v1?**
*Why we're asking:* Mobile-friendly review-queue UI roughly doubles frontend QA time. Most BD review work is desktop.
*Default:* **Desktop-first; mobile-responsive read-only views; no mobile approvals in v1.**

---

## B. Volume, Cadence & Coverage Scope  *(drives infra + cost ceiling)*

**B1. What is the target number of qualified opportunities surfaced per week?**
*Why we're asking:* 5–10 per week is a *quality-over-quantity* engine; 30+ per week needs broader source coverage (LinkedIn, Reddit, trade shows) pulled into v1, which adds 3–4 weeks of work and $200–400/mo of variable cost.
*Default:* **8–12 qualified opportunities per week.**

**B2. Is twice-daily refresh acceptable, or is hourly refresh required?**
*Why we're asking:* Twice-daily fits the cadence of regulatory + trade-press signals (most update once a day). Hourly multiplies external API spend by ~6× with little signal lift for the categories we're monitoring.
*Default:* **Twice daily — 06:00 ET and 14:00 ET.**

**B3. How far back should we backfill historical signals on day 1?**
*Why we're asking:* 12 months of backfill costs roughly 30–60× a normal day of API calls (one-time) but lets BAT validate against companies they already know. Less than 6 months and there's no historical baseline to score against.
*Default:* **12 months of backfill across regulatory and filings; 6 months across trade press.**

---

## C. Geographic & Vertical Scope  *(drives entity universe and rubric)*

**C1. Confirm the geographic scope is Canada + US only for v1 — or should Mexico (or other Americas) be in scope?**
*Why we're asking:* Adding Mexico means Spanish-language signal handling, COFEPRIS regulatory connector, and another patent office — roughly 2–3 weeks of added work.
*Default:* **Canada + US only for v1. Mexico evaluated for Phase 2.**

**C2. Confirm the vertical is convenience-store + pharmacy-adjacent CPG (functional beverages, OTC, supplements, snacks). Are pet wellness, beauty, or other adjacent CPG categories in or out?**
*Why we're asking:* Each adjacent category needs its own source list and rubric tuning. We can include them, but the more we include, the noisier the signal becomes.
*Default:* **In: functional bev, OTC, supplements, snacks, immunity, sleep. Out: pet, beauty, household. Revisit at end of Q1 post-launch.**

**C3. Are public companies in scope, or only private?**
*Why we're asking:* Public companies have far better filing data (SEDAR+/EDGAR), so they tend to dominate scored lists. If BAT only wants private acquisition targets, we filter them out at scoring.
*Default:* **Both, but private targets are the default; public companies surfaced separately as "intelligence-only" cards.**

---

## D. Scoring Rubric & Red Flags  *(drives the heart of the engine)*

**D1. Are the 5 metrics and weights from the existing brief (Strategic Fit 30%, Revenue Potential 25%, Operational Synergy 20%, Regulatory Readiness 15%, Deal Accessibility 10%) final, or open to refinement once we see the first 50 scored examples?**
*Why we're asking:* Most rubrics need 1–2 rounds of tuning after seeing real outputs. We need to know if the rubric is a fixed input or a working hypothesis.
*Default:* **Working hypothesis. Lock after the 2-week silent pilot (see G3).**

**D2. What total score is the minimum threshold for an opportunity to enter the review queue (e.g., ≥ 65, ≥ 70, ≥ 75)?**
*Why we're asking:* The threshold directly controls weekly volume. Too low → review fatigue; too high → empty queue.
*Default:* **≥ 70 to enter the queue; ≥ 85 flagged as "Elite" with a separate alert.**

**D3. Are the red-flag rules (regulatory non-compliance, ownership by competitor, leadership instability) final, or should we add others specific to BAT (e.g., ESG concerns, geographic exclusions, related-party history)?**
*Why we're asking:* Red flags filter out otherwise-high-scoring companies. BAT-specific rules need to be captured before we lock the screen logic.
*Default:* **Use the rules in the brief. Hold a 30-min red-flag workshop in week 2 to confirm.**

**D4. Will BAT pre-load ~50 curated example companies (good fits + bad fits + obvious red flags) before launch?**
*Why we're asking:* Without gold-standard examples, the scoring model has a 4–6 week cold-start period of generic justifications. With them, the system is sharp from day one.
*Default:* **Yes — collected during weeks 3–4 of the build.**

---

## E. Outreach, Approvals & Identity  *(drives compliance and brand risk)*

**E1. Who is in the approval chain for outbound messages — BD lead alone, or BD + Marketing + (optionally) Legal?**
*Why we're asking:* Single-approver is faster (typical SLA 2 hours); multi-approver is safer (typical SLA 24 hours). Affects throughput.
*Default:* **BD analyst drafts → BD lead approves. Marketing review only required for messages targeting public companies or sensitive categories.**

**E2. From which sender identity does outreach leave the system — a corporate alias (e.g., partnerships@bat.com), or the individual BD analyst's mailbox?**
*Why we're asking:* Individual sender = better reply rates but requires per-user OAuth and reply routing. Corporate alias = simpler, slightly lower reply rates.
*Default:* **Individual analyst's mailbox via OAuth. Replies route to the originating analyst.**

**E3. Where should replies and outcomes be logged — back into NORAD, into HubSpot, or both?**
*Why we're asking:* Funnel analytics need a single source of truth. If HubSpot is the source of truth, NORAD reads from it; if NORAD is the source of truth, HubSpot is a passive log.
*Default:* **HubSpot is the source of truth for deals; NORAD writes opportunities + outreach logs into HubSpot, then reads back deal stage for funnel reporting.**

---

## F. Integrations, Identity & Data Residency  *(drives plumbing scope)*

**F1. Confirm HubSpot is the CRM. If so, which HubSpot pipeline + deal stage should NORAD write new opportunities into?**
*Why we're asking:* Writing into the wrong pipeline pollutes BAT's existing CRM analytics.
*Default:* **A new "NORAD Sourced" pipeline with stages: New → Contacted → Engaged → Qualified → Disqualified.**

**F2. Is single sign-on required (Microsoft / Okta / Google), or is the standard Clerk login (email + Google OAuth) acceptable for v1?**
*Why we're asking:* Enterprise SSO via SAML/SCIM is supported by Clerk but adds 1 week of integration + identity provider config on BAT's side.
*Default:* **Microsoft Entra (Azure AD) SSO — standard for BAT-style enterprises.**

**F3. Is there a data residency requirement (e.g., Canadian-resident data only, or PIPEDA-only hosting)?**
*Why we're asking:* If Canadian-only is required, we must use Canada-region Supabase + Vercel CA edge + Fly.io YYZ region. This is a one-week setup change, not a re-architecture, but it has to be locked before infra is provisioned.
*Default:* **No hard residency requirement; primary region us-east. Confirm this is acceptable to BAT InfoSec.**

---

## G. Compliance, Pilot & Success Criteria  *(drives go/no-go and definition of done)*

**G1. Who at BAT will sign off on outreach template wording for CASL (Canada) and CAN-SPAM (US) compliance?**
*Why we're asking:* Anti-spam compliance is BAT's legal responsibility, not the engine's. We need a named owner before any template ships.
*Default:* **BAT Legal + Marketing co-sign each template version.**

**G2. What does v1 success look like at the end of the first 90 days post-launch — what numbers would make BAT call this a win?**
*Why we're asking:* Without an explicit success definition, every team interprets "working" differently and project reviews become arguments. A clear target lets us tune to it.
*Default:* **(a) 8–12 qualified opportunities/wk surfaced; (b) ≥ 2 outreach conversations/wk; (c) ≥ 1 LOI or formal partnership conversation per quarter; (d) BD analyst time spent on prospecting drops by ≥ 50%.**

**G3. Will BAT commit to a 2-week silent pilot before turning on outreach? (Engine runs, generates ranked lists, BAT validates manually, no emails leave the system.)**
*Why we're asking:* The silent pilot is the safety net that catches scoring quirks and entity-resolution misses before any outbound mistake reaches a target company. It has been the single highest-ROI step in every system like this we've shipped.
*Default:* **Yes — weeks 11–12 of the build are the silent pilot; outbound enables in week 13 contingent on BAT sign-off.**

**G4. Who is the named BAT product owner for NORAD — the one person we go to for daily decisions during the build, and who owns it post-launch?**
*Why we're asking:* Every successful BD intelligence rollout we've done has had a single-named BAT owner. Without one, decisions stall and the system drifts. Steering committees are fine for governance, but daily decisions need a single person.
*Default:* **A senior BD analyst or BD ops lead; ~25% of their time during the build, ~10% ongoing.**

**G5. What is the monthly external API budget cap (so we can set guardrails before runaway-cost incidents)?**
*Why we're asking:* The system has built-in cost ledgers and per-tenant rate limits. Setting a hard cap means we can stop usage before it surprises Finance.
*Default:* **$1,000/mo soft cap → alerts at 80%; $1,500/mo hard cap → automatic throttle.**

---

## Summary — What Each Answer Unlocks

| Section | Unlocks |
|---|---|
| A. Product paradigm | Locks the v1 UX scope and confirms whether NLS is in or out |
| B. Volume + cadence | Drives infrastructure sizing and external API budget |
| C. Geographic + vertical | Defines the entity universe and source library |
| D. Rubric + red flags | Locks the heart of the scoring engine |
| E. Outreach + approvals | Defines the compliance + brand-safety workflow |
| F. Integrations + residency | Drives plumbing scope and infra region selection |
| G. Compliance + pilot + success | Defines go/no-go and the post-launch scorecard |

---

## How to Respond

For each question, the simplest response is one of:

- ✅ **Default works** — accept our recommendation as-is
- 🔄 **Different answer** — provide BAT's specific answer
- ❓ **Need to discuss** — flag for a 30-min working session

Please return responses within **5 business days** so we can lock the build estimate and start engineering on schedule.

---

*Prepared April 2026 by Growth Machine for BAT. Replies welcome by email or direct edit on this document.*
