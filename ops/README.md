# Ops

Infrastructure and deployment helpers — **not** imported by the runtime app.

| Path | Purpose |
|------|---------|
| [`gcp-migration/`](gcp-migration/README.md) | Cloud SQL ops (Railway env vars, network hardening) |

Schema DDL lives in [`apps/api/sql/`](../apps/api/sql/). Apply with `psql` — see `gcp-migration/README.md`.

Local-only artifacts (secrets, dumps, proxy binary) stay gitignored under `gcp-migration/config.env`, etc.
