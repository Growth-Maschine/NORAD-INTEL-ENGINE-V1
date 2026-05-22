"""Settings API — global research-engine configuration.

GET /api/settings/research        → current config
PUT /api/settings/research        → merge partial config into stored value
GET /api/settings/research/options → enum values for UI dropdowns

In dev (`settings.debug=True`) anyone can read/write. In prod we require the
same admin header used by /research routes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.services.settings import (
    EXA_DEEP_MODELS,
    EXA_SEARCH_TYPES,
    PARALLEL_PROCESSORS,
    ResearchConfig,
    get_research_config,
    update_research_config,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Admin gate. In dev (`debug=True`) anyone passes; in prod we require
    a shared bearer matching `NORAD_ADMIN_TOKEN`. Fail-closed: if the
    token isn't configured at all in prod, return 503 instead of opening up.
    """
    s = get_settings()
    if s.debug:
        return
    expected = s.admin_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_token not configured",
        )
    if x_admin_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="admin token required"
        )


# Typed partial patches — invalid payloads now yield 422 (not 500).
class ParallelPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processor: str | None = Field(default=None)
    timeout_s: int | None = Field(default=None, ge=30, le=3600)


class ExaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search_type: str | None = Field(default=None)
    deep_model: str | None = Field(default=None)
    num_results: int | None = Field(default=None, ge=1, le=50)


class ResearchConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parallel: ParallelPatch | None = None
    exa: ExaPatch | None = None


class ResearchOptionsOut(BaseModel):
    parallel_processors: list[str]
    exa_search_types: list[str]
    exa_deep_models: list[str]


@router.get("/research", response_model=ResearchConfig)
async def get_research(session: AsyncSession = Depends(get_session)) -> ResearchConfig:
    return await get_research_config(session)


@router.put("/research", response_model=ResearchConfig)
async def put_research(
    patch: ResearchConfigPatch,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin),
) -> ResearchConfig:
    body = patch.model_dump(exclude_none=True)
    # Cross-field enum validation (we accept any string at the schema level so
    # we can return a friendly per-field error; here we surface 422 explicitly).
    if "parallel" in body and "processor" in body["parallel"]:
        if body["parallel"]["processor"] not in PARALLEL_PROCESSORS:
            raise HTTPException(422, detail=f"invalid parallel.processor")
    if "exa" in body:
        if "search_type" in body["exa"] and body["exa"]["search_type"] not in EXA_SEARCH_TYPES:
            raise HTTPException(422, detail="invalid exa.search_type")
        if "deep_model" in body["exa"] and body["exa"]["deep_model"] not in EXA_DEEP_MODELS:
            raise HTTPException(422, detail="invalid exa.deep_model")
    return await update_research_config(session, body)


@router.get("/research/options", response_model=ResearchOptionsOut)
async def get_options() -> ResearchOptionsOut:
    return ResearchOptionsOut(
        parallel_processors=list(PARALLEL_PROCESSORS),
        exa_search_types=list(EXA_SEARCH_TYPES),
        exa_deep_models=list(EXA_DEEP_MODELS),
    )
