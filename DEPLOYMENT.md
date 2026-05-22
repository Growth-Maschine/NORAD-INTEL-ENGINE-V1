# NORAD — Deployment & Local Setup

Monorepo: FastAPI backend in `apps/api`, React/Vite frontend in `apps/web`.
Database is hosted Supabase Postgres; cache/queue is Upstash Redis.

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

To process research/discovery runs you also need the arq worker:

```bash
cd apps/api
arq app.workers.settings.WorkerSettings
```

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
   - `SUPABASE_DATABASE_URL` (use the **pooled** asyncpg URL on port 6543)
   - `REDIS_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`
   - `CORS_ORIGINS` → JSON array containing your Vercel URL, e.g.
     `["https://norad.vercel.app"]`
   - `ENVIRONMENT=production`, `DEBUG=false`
5. Deploy. Railway assigns a `*.up.railway.app` URL — that's your API base.

### Optional: arq worker as a second Railway service

Background jobs (Today feed, research runs) need the arq worker. Add a
second service in the same Railway project:

- Same repo, root dir `apps/api`
- Override start command: `arq app.workers.settings.WorkerSettings`
- Share the same env vars (use Railway's "shared variables")

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

The schema lives in Supabase and is managed manually (no Alembic — see
`replit.md`). For a fresh Supabase project, replay the existing DDL by
connecting via `psql "$SUPABASE_DATABASE_URL_pool"` and creating these
tables: `runs`, `cards`, `companies`, `signals`, `sources`, `engine_calls`,
`run_events`, `trend_articles`, `app_kv`. Models in `apps/api/app/models/`
are the source of truth for column shapes.

---

## Health checks

- `GET /health` — app liveness (used by Railway healthcheck)
- `GET /health/db` — Postgres + Redis connectivity (use to verify env vars
  are correct after deploy)
