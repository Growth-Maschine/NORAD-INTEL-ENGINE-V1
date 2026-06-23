# NORAD

Brand intelligence and BD deal-sourcing engine. Built by Growth Maschine.

## Repo layout

```
norad/
├── apps/
│   ├── api/             FastAPI backend (Python 3.11, port 8000)
│   │   └── scripts/     Dev launcher + DB maintenance scripts
│   └── web/             React + Vite + TypeScript + Tailwind (port 5000)
├── docs/
│   ├── strategy/        Blueprint, plan, stack, cost research
│   ├── architecture/    BAT Azure architecture
│   ├── phase-1/         Product specs and test plans
│   ├── research/        Research-query templates (Parallel + Exa)
│   └── reports/         Client-deliverable .docx + .xlsx reports
├── ops/                 GCP / deploy helpers (not runtime code)
└── .local/              Gitignored — Cursor one-offs, local exports
```

## Running locally

Use **two terminals**. If a port is already in use, dev servers pick the next free one automatically.

### Backend (API)

```bash
cd apps/api
pip install -r requirements.txt
python scripts/dev.py
```

Opens on **8000** when free, otherwise **8001**, **8002**, … — the terminal prints the URL.  
API docs: `http://127.0.0.1:<port>/docs`

### Frontend (web)

```bash
cd apps/web
npm install
npm run dev
```

Opens on **5000** when free, otherwise **5001**, **5002**, … — Vite prints the URL in the terminal.  
`/api` is proxied to `http://127.0.0.1:8000` (keep API on 8000 for local dev, or set `VITE_API_URL` in `apps/web/.env.local`).

### One-liners (from repo root)

```bash
cd apps/api && python scripts/dev.py
cd apps/web && npm run dev
```

## Stack

- **Backend:** FastAPI · pydantic v2 · pydantic-settings · uvicorn · httpx
- **Frontend:** React 18 · Vite 5 · TypeScript · Tailwind v3 · TanStack Query · React Router · lucide-react
