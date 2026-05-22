"""Brand intelligence endpoints — placeholder skeleton.

Will host endpoints for: surfacing brands from articles, running Parallel/Exa
deep research, retrieving cached profiles, and the BD intelligence feed.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("")
def list_brands() -> dict:
    return {"brands": [], "total": 0}
