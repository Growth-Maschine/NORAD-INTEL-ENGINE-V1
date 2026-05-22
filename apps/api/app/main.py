"""FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

In production (Replit autoscale) we serve the built Vite SPA from the same
origin so the frontend's relative `/api/*` calls just work — no CORS, no
separate static host.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.orphan_sweeper import sweep_orphan_runs
from app.routers import brands, discovery, engines, events, health, research, schemas
from app.routers import settings as settings_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # On startup: any run still in queued/researching/synthesizing for more
    # than 30 minutes is dead (the worker process died with it). Mark them
    # failed so the UI stops claiming "1 running" against a zombie.
    try:
        await sweep_orphan_runs(get_session_factory(), cutoff_minutes=30)
    except Exception:  # pragma: no cover - never block boot on sweeper
        logger.exception("orphan_sweeper crashed on startup; continuing")
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── routers
    app.include_router(health.router)
    app.include_router(engines.router)
    app.include_router(events.router)
    app.include_router(brands.router)
    app.include_router(schemas.router)
    app.include_router(discovery.router)
    app.include_router(research.router)
    app.include_router(settings_router.router)

    # ── Frontend (production)
    # In production the Vite build is sitting at apps/web/dist. We mount it
    # under "/" so visiting the app root returns index.html and any /assets/*
    # request is served by StaticFiles. All `/api/*` requests still route to
    # the routers above because FastAPI matches routes before the catch-all.
    #
    # In dev the dist folder doesn't exist yet — we fall back to a tiny JSON
    # at "/" so the old behavior is preserved (`curl localhost:8000` works).
    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if web_dist.is_dir():
        assets_dir = web_dist / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )

        @app.get("/", include_in_schema=False)
        def _spa_root() -> FileResponse:
            return FileResponse(web_dist / "index.html")

        # SPA history fallback. Anything that isn't an API/health/docs path
        # and isn't a real file in dist gets the SPA shell so client-side
        # routing (/companies, /settings, /today/run/...) works on refresh.
        @app.get("/{full_path:path}", include_in_schema=False)
        def _spa_catch_all(full_path: str, request: Request):
            # Never intercept API surface or auto-docs
            reserved = ("api/", "health", "docs", "redoc", "openapi.json")
            if any(full_path.startswith(p) for p in reserved):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            # Serve a real file if it exists (e.g. /favicon.ico, /robots.txt)
            candidate = web_dist / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(web_dist / "index.html")
    else:
        @app.get("/")
        def root() -> dict:
            return {
                "name": settings.app_name,
                "version": settings.app_version,
                "docs": "/docs",
            }

    return app


app = create_app()
