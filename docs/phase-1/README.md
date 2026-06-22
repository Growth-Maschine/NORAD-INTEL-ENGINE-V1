# NORAD Phase 1 — Product Blueprint

| Field | Value |
|-------|-------|
| **Project** | NORAD Intel Engine |
| **Repository** | NORAD-INTEL-ENGINE-V1 |
| **Document set** | Phase 1 Product Blueprint |
| **Owner** | huzaifa@growthmaschine.com |

---

## 1. Scope

This document set defines product behaviour and data model for the NORAD Intel Engine dashboard **as implemented in this repository**.

**Start here:** [P1-00 Phase 1 Overview](./phase-1-overview.md) — controlling scope, built vs planned, pipeline summary, and revision status of every child document.

Each child document defines required product behaviour. When a child doc conflicts with P1-00 or with the code paths listed in P1-00 §8, treat the conflict as a **documentation bug** to fix in the child doc.

---

## 2. Document register

| Ref | Title | File | Version | Status |
|-----|-------|------|---------|--------|
| P1-00 | **Phase 1 Overview** | [phase-1-overview.md](./phase-1-overview.md) | 1.2 | Current |
| P1-01-Admin | Core Operator Workflow | [P1-01-admin.md](./P1-01-admin.md) | 3.1 | Current — paired with User |
| P1-01-User | Core Analyst Workflow | [P1-01-user.md](./P1-01-user.md) | 2.1 | Current — paired with Admin |
| P1-02-Admin | Core Product Objects (Admin) | [P1-02-admin.md](./P1-02-admin.md) | 2.1 | Current — paired with User |
| P1-02-User | Core Product Objects | [P1-02-user.md](./P1-02-user.md) | 2.1 | Current — paired with Admin |
| P1-03 | Object Relationships | [P1-03.md](./P1-03.md) | 2.1 | Current |
| P1-04-Admin | Required Fields | [P1-04-admin.md](./P1-04-admin.md) | 3.2 | Current |
| P1-05-Admin | UI Screen Mapping (Admin) | [P1-05-admin.md](./P1-05-admin.md) | 2.1 | Current |
| P1-05-User | UI Screen Mapping (Analyst) | [P1-05-user.md](./P1-05-user.md) | 2.1 | Current |
| P1-06 | Backend Actions | [P1-06.md](./P1-06.md) | 2.1 | Current |
| — | Phase 2 SQL tests | [phase2test.md](./phase2test.md) | — | Legacy scenarios |

**Revision order:** P1-00 → P1-01 (Admin + User, paired) → P1-02 → P1-03 → P1-04 → P1-05 → P1-06.

---

## 3. Supporting references

| Path | Description |
|------|-------------|
| [docs/backend-pipeline.md](../backend-pipeline.md) | Web Discovery + Research pipeline implementation guide |
| `apps/web/src/App.tsx` | Frontend route definitions |
| `apps/web/src/lib/api.ts` | Frontend API client |
| `apps/api/app/routers/` | Backend HTTP surface |
| `apps/api/app/models/` | Database models (source of truth) |
| `apps/api/sql/` | Versioned DDL |
| [docs/reference/legacy-signals-scores-suggestions.md](../reference/legacy-signals-scores-suggestions.md) | Retired BD signals/scores (pre-2026-06-16) |
