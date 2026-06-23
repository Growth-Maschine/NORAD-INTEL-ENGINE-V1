# NORAD API

FastAPI backend for the NORAD brand intelligence engine.

## Run

```bash
cd apps/api
pip install -r requirements.txt
python dev.py
```

Uses port **8000** when free, otherwise the next available port (prints the URL).

Research and web-discovery runs execute in-process (`asyncio.create_task`) — no
separate worker process.

## Key endpoints

| Path | Purpose |
|------|---------|
| `GET /health`, `/ready`, `/health/db` | Liveness + DB/Redis probes |
| `GET /api/research/*` | Company research pipeline |
| `GET /api/web-discovery/*` | Exa search → articles → Sonnet enrich |
| `GET /api/events/runs/:id` | SSE live feed for a run |
| `GET /api/settings/*` | Pipeline config (`app_kv`) |
| `GET /docs` | OpenAPI |

## Layout

```
app/                     # Runtime — imported by uvicorn
├── main.py              # FastAPI app + router mounting + SPA fallback
├── core/                # config, db, redis, pipeline log, orphan sweeper
├── engines/             # Exa, Claude, Parallel, Diffbot clients
├── models/              # SQLAlchemy ORM (source of truth)
├── routers/             # HTTP surface
├── schemas/             # CompanyCardV1 contract
├── services/            # research, web_discovery, run_events, settings
├── maintenance/         # Manual DB jobs (not loaded at API startup)
└── utils/
sql/                     # Versioned DDL — apply with psql
tests/                   # Pytest suite
dev.py                   # Local uvicorn launcher
```

**Maintenance jobs** (run from `apps/api`):

```bash
python -m app.maintenance.backfill_card_profile_parameters
```

DDL workflow: see `docs/backend-pipeline.md` and `apps/api/sql/`.  
GCP ops: see `ops/gcp-migration/README.md`.
