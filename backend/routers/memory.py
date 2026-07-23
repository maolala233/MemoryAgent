"""Memory vault router: CRUD, list, stats, rescan."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    MemoryCreateRequest,
    MemoryDoc,
    MemoryDocResponse,
    MemoryListResponse,
    MemoryUpdateRequest,
    RescanResponse,
    StatsOverview,
    StatusResponse,
)
from ..services.memory_service import memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/stats", response_model=StatsOverview)
def stats() -> StatsOverview:
    return StatsOverview(**memory_service.get_stats())


@router.post("/rescan", response_model=RescanResponse)
def rescan() -> RescanResponse:
    return RescanResponse(**memory_service.rescan_vault())


@router.get("/open-loops")
def open_loops() -> list[dict]:
    return memory_service.get_open_loops()


@router.get("", response_model=MemoryListResponse)
def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    track: Optional[str] = None,
    memory_type: Optional[str] = None,
    status: Optional[str] = None,
    project_id: Optional[str] = None,
    has_open_loop: Optional[bool] = None,
    include_deleted: bool = Query(False, description="默认隐藏软删除文档, 仅在管理场景下打开"),
) -> MemoryListResponse:
    total, docs = memory_service.list_documents(
        skip=skip, limit=limit, track=track, memory_type=memory_type,
        status=status, project_id=project_id, has_open_loop=has_open_loop,
        include_deleted=include_deleted,
    )
    return MemoryListResponse(total=total, items=[MemoryDoc(**d) for d in docs])


@router.post("", response_model=MemoryDocResponse, status_code=201)
def create_document(req: MemoryCreateRequest) -> MemoryDocResponse:
    try:
        doc = memory_service.create_document(
            req.rel_path, req.content,
            memory_type=req.memory_type, track=req.track,
            project_id=req.project_id, summary=req.summary,
            keywords=req.keywords,
        )
        return MemoryDocResponse(**doc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{doc_path:path}", response_model=MemoryDocResponse)
def get_document(doc_path: str) -> MemoryDocResponse:
    try:
        doc = memory_service.get_document(doc_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not doc:
        raise HTTPException(status_code=404, detail=f"Memory not found: {doc_path}")
    return MemoryDocResponse(**doc)


@router.put("/{doc_path:path}", response_model=MemoryDocResponse)
def update_document(doc_path: str, req: MemoryUpdateRequest) -> MemoryDocResponse:
    try:
        doc = memory_service.update_document(
            doc_path, content=req.content, memory_type=req.memory_type,
            track=req.track, status=req.status, summary=req.summary,
            keywords=req.keywords,
        )
        return MemoryDocResponse(**doc)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Memory not found: {doc_path}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{doc_path:path}", response_model=StatusResponse)
def delete_document(doc_path: str, soft: bool = True) -> StatusResponse:
    try:
        memory_service.delete_document(doc_path, soft=soft)
        return StatusResponse(status="deleted", message=doc_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
