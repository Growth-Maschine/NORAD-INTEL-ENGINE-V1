# GCP Cloud SQL — ops scripts

NORAD Postgres runs on **Cloud SQL** (`norad-pg-prod`, `europe-west2`, database `norad`).

One-time migration (provision, dump, restore) is **complete**. This folder only keeps **reusable ops** scripts.

## Instance

| Field | Value |
|-------|-------|
| Project | `norad-498414` |
| Region | `europe-west2` |
| Instance | `norad-pg-prod` |
| Connection name | `norad-498414:europe-west2:norad-pg-prod` |
| App user | `norad_app` |
| Password | Secret Manager `norad-db-password` + `apps/api/.env` |

## Scripts

| Script | When |
|--------|------|
| `05-print-railway-env.sh` | Paste `GCP_DATABASE_URL*` into Railway (API + worker) |
| `06-harden-network.sh` | After Cloud Run cutover — clear public authorized networks |

Setup: `cp config.env.example config.env` and set `GCP_PROJECT`.

Railway cutover details: [RAILWAY_CUTOVER.md](./RAILWAY_CUTOVER.md).

## Schema changes (ongoing)

Apply DDL from repo root:

```bash
psql "$GCP_DATABASE_URL_POOL" -f apps/api/sql/0007_example.sql
```

Local DDL via Auth Proxy (optional):

```bash
cloud-sql-proxy norad-498414:europe-west2:norad-pg-prod --port 15432
# point GCP_DATABASE_URL* at 127.0.0.1:15432
```
