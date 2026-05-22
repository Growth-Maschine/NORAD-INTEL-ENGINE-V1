# NORAD

Brand intelligence and BD deal-sourcing engine. Built by Growth Maschine.

## Repo layout

```
norad/
├── apps/
│   ├── api/             FastAPI backend (Python 3.11, port 8000)
│   └── web/             React + Vite + TypeScript + Tailwind (port 5000)
├── docs/
│   ├── strategy/        Blueprint, plan, stack, cost research, discovery questions
│   ├── architecture/    BAT Azure architecture + NORAD trend-flow diagrams
│   ├── research/        Research-query templates (Parallel + Exa)
│   └── reports/         Client-deliverable .docx + .xlsx reports
├── scripts/             One-off generators (cost sheet, report DOCX builders)
└── attached_assets/     User uploads referenced by docs/scripts
```

## Running locally

### Backend

```bash
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

App at `http://localhost:5000`. Vite proxies `/api/*` → backend on `8000`.

## Stack

- **Backend:** FastAPI · pydantic v2 · pydantic-settings · uvicorn · httpx
- **Frontend:** React 18 · Vite 5 · TypeScript · Tailwind v3 · TanStack Query · React Router · lucide-react
