# NORAD — Deployment & Local Setup

Monorepo: FastAPI backend in `apps/api`, React/Vite frontend in `apps/web`.
Database is **GCP Cloud SQL Postgres**. Redis is optional (health probe only).

Research and web-discovery runs execute in the API process (`asyncio.create_task`) —
no separate worker service.

---

## Local clone (fresh machine)

```bash
git clone <repo-url> norad
cd norad

# Backend
cd apps/api
cp .env.example .env          # fill in real keys
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd apps/web
cp .env.example .env          # leave VITE_API_URL empty for local
npm install
npm run dev                   # http://localhost:5000
```

The Vite dev server proxies `/api` and `/health` to `http://127.0.0.1:8000`,
so you don't need to set `VITE_API_URL` locally.

---

## Deploy — Backend on Railway

1. **New Project → Deploy from GitHub repo.**
2. After import, open the service settings and set:
   - **Root Directory:** `apps/api`
   - **Watch Paths:** `apps/api/**` (optional, prevents rebuilds on frontend changes)
3. Railway autodetects Python via `requirements.txt` + `runtime.txt`. The
   start command + health check come from `apps/api/railway.toml`.
4. In the **Variables** tab, paste every var from `apps/api/.env.example`
   with real values. Critical ones:
   - `ANTHROPIC_API_KEY`, `PARALLEL_API_KEY`, `EXA_API_KEY`
   - `GCP_DATABASE_URL` — asyncpg URL (port **5432** + `sslmode=require`)
   - `GCP_DATABASE_URL_POOL`, `GCP_DATABASE_URL_DIRECT` — same host for DDL scripts
   - `REDIS_URL` (optional — enables Redis line in `/health/db`)
   - `CORS_ORIGINS` → JSON array containing your Vercel URL, e.g.
     `["https://norad.vercel.app"]`
   - `ENVIRONMENT=production`, `DEBUG=false`
5. Deploy. Railway assigns a `*.up.railway.app` URL — that's your API base.

---

## Deploy — Frontend on Vercel

1. **New Project → Import Git Repository.**
2. Configure:
   - **Root Directory:** `apps/web`
   - **Framework Preset:** Vite (auto-detected via `vercel.json`)
3. In **Environment Variables** set:
   - `VITE_API_URL` = your Railway backend URL (no trailing slash), e.g.
     `https://norad-api.up.railway.app`
4. Deploy. Note the assigned `*.vercel.app` URL and add it to the backend's
   `CORS_ORIGINS` env var on Railway, then redeploy the backend.

---

## Database schema

Database is **Cloud SQL Postgres** in GCP (`norad-498414`, `europe-west2`, instance `norad-pg-prod`).
Schema is applied manually — see
[`scripts/gcp-migration/README.md`](../scripts/gcp-migration/README.md) and
`apps/api/sql/` for incremental DDL.

---

## Health checks

- `GET /health` — app liveness (used by Railway healthcheck)
- `GET /health/db` — Postgres + Redis connectivity (use to verify env vars
  are correct after deploy)
