# NORAD API

FastAPI backend for the NORAD brand intelligence engine.

## Run

```bash
cd apps/api
pip install -r requirements.txt
python scripts/dev.py
```

Uses port **8000** when free, otherwise the next available port (prints the URL).

## Endpoints

- `GET /`         — root info
- `GET /health`   — liveness probe
- `GET /ready`    — readiness probe
- `GET /brands`   — placeholder
- `GET /docs`     — interactive OpenAPI docs
- `GET /redoc`    — alternative docs

## Layout

```
app/
├── main.py          # FastAPI app factory + middleware + router mounting
├── core/
│   └── config.py    # Settings (env-driven, pydantic-settings)
└── routers/
    ├── health.py    # /health, /ready
    └── brands.py    # /brands (placeholder)
```
