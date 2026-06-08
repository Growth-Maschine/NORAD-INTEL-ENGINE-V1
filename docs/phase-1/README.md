# NORAD Phase 1 — Product Blueprint

| Field | Value |
|-------|-------|
| **Project** | NORAD Intel Engine |
| **Repository** | NORAD-INTEL-ENGINE-V1 |
| **Document set** | Phase 1 Product Blueprint |
| **Status** | In progress |
| **Owner** | huzaifa@growthmaschine.com |

---

## 1. Scope

This document set defines the product and data blueprint for the NORAD Intel Engine dashboard. It establishes the specification baseline prior to database redesign and backend implementation.

Each document records:

| Layer | Description |
|-------|-------------|
| Target state | Required product behaviour and data model |
| Current state | Implemented behaviour as verified in this repository |
| Gaps | Target requirements not yet implemented |

All current-state claims are verified against `apps/web`, `apps/api`, and `apps/api/sql`.

## 2. Document register

| Ref | Title | Version | Status |
|-----|-------|---------|--------|
| P1-00 | [Phase 1 Overview](./phase-1-overview.md) | 0.4 | Draft |
| P1-01 | Core User Workflow | 1.0 | Draft — primary flows documented |
| P1-01-Admin | [Core Operator Workflow — Admin Console](./P1-01-admin.md) | 2.3 | Draft |
| P1-01-User | [Core Analyst Workflow](./P1-01-user.md) | 1.6 | Draft |
| P1-02 | Core Product Objects | — | Not started |
| P1-03 | Object Relationships | — | Not started |
| P1-04 | Required Fields per Object | — | Not started |
| P1-05 | UI Screen Mapping | — | Not started |
| P1-06 | Backend Actions | — | Not started |
| P1-07 | MVP Scope Boundaries | — | Not started |

Documents are produced and approved in numerical order. P1-00 is the controlling overview.

## 3. Supporting references

| Path | Description |
|------|-------------|
| `docs/backend-pipeline.md` | Discovery and Research pipeline specification |
| `apps/web/src/App.tsx` | Frontend route definitions |
| `apps/web/src/lib/api.ts` | Frontend API client |
| `apps/api/app/routers/` | Backend endpoint definitions |
| `apps/api/app/models/` | Database model definitions |
