"""Search router: keyword / semantic / hybrid + suggestions + filters."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    MemoryResult,
    SearchFilters,
    SearchRequest,
    SearchResponse,
)
from ..services.retrieval_service import retriever

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    filters = {
        k: v for k, v in {
            "track": req.track,
            "memory_type": req.memory_type,
            "status": req.status,
        }.items() if v
    }
    results = await retriever.search(
        req.query, strategy=req.strategy, limit=req.limit,
        min_score=req.min_score, **filters,
    )
    return SearchResponse(
        query=req.query,
        strategy=req.strategy,
        total=len(results),
        results=[MemoryResult(**r) for r in results],
    )


@router.get("/suggestions", response_model=list[str])
def suggestions(q: str = Query(..., min_length=1), limit: int = Query(8, ge=1, le=20)) -> list[str]:
    return retriever.get_suggestions(q, limit=limit)


@router.get("/filters", response_model=SearchFilters)
def filters() -> SearchFilters:
    data = retriever.get_filters()
    return SearchFilters(**data)
