"""Mandol 路由：空间管理、单元CRUD、关系管理、图谱遍历、多视图检索、
智能问答、高阶记忆构建、跨会话合并、统计监控与持久化。

对应 Mandol 文档中的全部必要功能，提供前端友好的 REST 接口。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    BFSExpandRequest,
    BuildReportResponse,
    BuildRequest,
    EntitySubgraphRequest,
    LoadSnapshotRequest,
    MandolAskRequest,
    MandolAskResponse,
    MandolMonitorResponse,
    MandolRetrieveRequest,
    MandolRetrieveResponse,
    MandolSearchHit,
    MandolStatsResponse,
    MandolUnitBatchCreateRequest,
    MandolUnitCreateRequest,
    MandolUnitInfo,
    MandolUnitListResponse,
    MergeResponse,
    NeighborsRequest,
    RelationshipCreateRequest,
    RelationshipDeleteRequest,
    RelationshipInfo,
    RelationshipListResponse,
    SaveSnapshotRequest,
    SnapshotResponse,
    SpaceAttachRequest,
    SpaceCreateRequest,
    SpaceInfo,
    SpaceListResponse,
    StatusResponse,
    SubgraphResponse,
    TraceRequest,
    TraceResponse,
    UnitSpaceRequest,
)
from ..services.mandol_service import RELATIONSHIP_TYPES, VIEWS, mandol_service
from ..utils.logger import warn

router = APIRouter(prefix="/api/mandol", tags=["mandol"])


def _require_enabled() -> None:
    if not mandol_service.is_enabled:
        raise HTTPException(status_code=503, detail="Mandol 记忆引擎未启用")


def _safe_call(func, *args, **kwargs):
    """安全调用 mandol 服务，捕获异常转为 HTTP 错误。"""
    try:
        return func(*args, **kwargs)
    except RuntimeError as exc:
        warn(f"Mandol RuntimeError: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        warn(f"Mandol 调用失败: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# =====================================================================
# 元数据接口
# =====================================================================
@router.get("/views", response_model=List[str])
def list_views() -> List[str]:
    """获取支持的检索视图列表。"""
    return VIEWS


@router.get("/relationship-types", response_model=List[str])
def list_relationship_types() -> List[str]:
    """获取支持的关系类型列表。"""
    return RELATIONSHIP_TYPES


# =====================================================================
# 统计与监控
# =====================================================================
@router.get("/stats", response_model=MandolStatsResponse)
def stats() -> MandolStatsResponse:
    """获取 Mandol 记忆系统统计。"""
    data = mandol_service.get_stats()
    return MandolStatsResponse(**data)


@router.get("/monitor", response_model=MandolMonitorResponse)
def monitor() -> MandolMonitorResponse:
    """获取监控信息。"""
    data = mandol_service.get_monitor()
    return MandolMonitorResponse(**data)


# =====================================================================
# 记忆单元 CRUD
# =====================================================================
@router.get("/units", response_model=MandolUnitListResponse)
def list_units(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> MandolUnitListResponse:
    """列出记忆单元。"""
    _require_enabled()
    items = _safe_call(mandol_service.list_units, limit=limit, offset=offset)
    return MandolUnitListResponse(total=len(items), items=[MandolUnitInfo(**i) for i in items])


@router.get("/units/{uid:path}", response_model=MandolUnitInfo)
def get_unit(uid: str) -> MandolUnitInfo:
    """获取单个记忆单元。"""
    _require_enabled()
    item = _safe_call(mandol_service.get_unit, uid)
    if not item:
        raise HTTPException(status_code=404, detail=f"单元不存在: {uid}")
    return MandolUnitInfo(**item)


@router.post("/units", response_model=MandolUnitInfo, status_code=201)
def create_unit(req: MandolUnitCreateRequest) -> MandolUnitInfo:
    """添加一条文本记忆。"""
    _require_enabled()
    item = _safe_call(
        mandol_service.add_text,
        uid=req.uid, text=req.text, metadata=req.metadata, space_name=req.space_name,
    )
    return MandolUnitInfo(**item)


@router.post("/units/batch", response_model=List[MandolUnitInfo], status_code=201)
def create_units_batch(req: MandolUnitBatchCreateRequest) -> List[MandolUnitInfo]:
    """批量添加文本记忆。"""
    _require_enabled()
    items = [
        {"uid": it.uid, "text": it.text, "metadata": it.metadata, "space_name": it.space_name}
        for it in req.items
    ]
    results = _safe_call(mandol_service.add_many, items)
    return [MandolUnitInfo(**i) for i in results]


@router.delete("/units/{uid:path}", response_model=StatusResponse)
def delete_unit(uid: str) -> StatusResponse:
    """删除记忆单元。"""
    _require_enabled()
    ok = _safe_call(mandol_service.remove_unit, uid)
    if not ok:
        raise HTTPException(status_code=404, detail=f"删除失败: {uid}")
    return StatusResponse(status="deleted", message=uid)


# =====================================================================
# 空间管理
# =====================================================================
@router.get("/spaces", response_model=SpaceListResponse)
def list_spaces() -> SpaceListResponse:
    """列出所有记忆空间。"""
    _require_enabled()
    items = _safe_call(mandol_service.list_spaces)
    return SpaceListResponse(total=len(items), items=[SpaceInfo(**i) for i in items])


@router.get("/spaces/{name:path}", response_model=SpaceInfo)
def get_space(name: str) -> SpaceInfo:
    """获取指定空间信息。"""
    _require_enabled()
    item = _safe_call(mandol_service.get_space, name)
    if not item:
        raise HTTPException(status_code=404, detail=f"空间不存在: {name}")
    return SpaceInfo(**item)


@router.post("/spaces", response_model=SpaceInfo, status_code=201)
def create_space(req: SpaceCreateRequest) -> SpaceInfo:
    """创建记忆空间。"""
    _require_enabled()
    item = _safe_call(mandol_service.create_space, req.name)
    return SpaceInfo(**item)


@router.delete("/spaces/{name:path}", response_model=StatusResponse)
def delete_space(name: str, cascade: bool = Query(False)) -> StatusResponse:
    """删除记忆空间。"""
    _require_enabled()
    _safe_call(mandol_service.delete_space, name, cascade=cascade)
    return StatusResponse(status="deleted", message=name)


@router.post("/spaces/attach", response_model=StatusResponse)
def attach_child_space(req: SpaceAttachRequest) -> StatusResponse:
    """挂载子空间。"""
    _require_enabled()
    _safe_call(mandol_service.attach_child_space, req.parent, req.child)
    return StatusResponse(status="ok", message=f"{req.child} -> {req.parent}")


@router.get("/spaces/{name:path}/units", response_model=MandolUnitListResponse)
def list_units_in_space(name: str, limit: int = Query(100, ge=1, le=1000)) -> MandolUnitListResponse:
    """列出空间内的单元。"""
    _require_enabled()
    items = _safe_call(mandol_service.list_units_in_space, name, limit=limit)
    return MandolUnitListResponse(total=len(items), items=[MandolUnitInfo(**i) for i in items])


@router.post("/spaces/add-unit", response_model=StatusResponse)
def add_unit_to_space(req: UnitSpaceRequest) -> StatusResponse:
    """将单元添加到空间。"""
    _require_enabled()
    _safe_call(mandol_service.add_unit_to_space, req.uid, req.space_name)
    return StatusResponse(status="ok")


@router.post("/spaces/remove-unit", response_model=StatusResponse)
def remove_unit_from_space(req: UnitSpaceRequest) -> StatusResponse:
    """从空间移除单元。"""
    _require_enabled()
    _safe_call(mandol_service.remove_unit_from_space, req.uid, req.space_name)
    return StatusResponse(status="ok")


# =====================================================================
# 关系管理
# =====================================================================
@router.post("/relationships", response_model=StatusResponse, status_code=201)
def create_relationship(req: RelationshipCreateRequest) -> StatusResponse:
    """添加关系边。"""
    _require_enabled()
    _safe_call(mandol_service.add_relationship, req.source, req.target, req.rel_type, req.properties)
    return StatusResponse(status="created", message=f"{req.source} --[{req.rel_type}]--> {req.target}")


@router.get("/relationships", response_model=RelationshipListResponse)
def list_relationships(
    uid: str = Query(...),
    direction: str = Query("all", pattern="^(all|out|in)$"),
) -> RelationshipListResponse:
    """列出某单元的所有关系。"""
    _require_enabled()
    items = _safe_call(mandol_service.list_relationships, uid, direction=direction)
    return RelationshipListResponse(
        uid=uid, direction=direction,
        relationships=[RelationshipInfo(**i) for i in items],
    )


@router.delete("/relationships", response_model=StatusResponse)
def delete_relationship(req: RelationshipDeleteRequest) -> StatusResponse:
    """删除关系。"""
    _require_enabled()
    _safe_call(mandol_service.delete_relationship, req.source, req.target, req.rel_type)
    return StatusResponse(status="deleted")


# =====================================================================
# 图谱遍历
# =====================================================================
@router.post("/graph/explicit-neighbors", response_model=List[MandolUnitInfo])
def explicit_neighbors(req: NeighborsRequest) -> List[MandolUnitInfo]:
    """获取显式邻居（沿关系边）。"""
    _require_enabled()
    items = _safe_call(
        mandol_service.get_explicit_neighbors,
        req.uid, rel_type=req.rel_type, direction=req.direction,
    )
    return [MandolUnitInfo(**i) for i in items]


@router.post("/graph/implicit-neighbors", response_model=List[MandolUnitInfo])
def implicit_neighbors(req: NeighborsRequest) -> List[MandolUnitInfo]:
    """获取隐式语义邻居（向量相似）。"""
    _require_enabled()
    items = _safe_call(mandol_service.get_implicit_neighbors, req.uid, top_k=req.top_k)
    return [MandolUnitInfo(**i) for i in items]


@router.post("/graph/bfs-expand", response_model=List[MandolUnitInfo])
def bfs_expand(req: BFSExpandRequest) -> List[MandolUnitInfo]:
    """BFS 图扩展。"""
    _require_enabled()
    items = _safe_call(
        mandol_service.bfs_expand,
        req.seed_uids, per_seed=req.per_seed, hops=req.hops, rel_type=req.rel_type,
    )
    return [MandolUnitInfo(**i) for i in items]


@router.post("/graph/entity-subgraph", response_model=SubgraphResponse)
def entity_subgraph(req: EntitySubgraphRequest) -> SubgraphResponse:
    """获取实体子图。"""
    _require_enabled()
    data = _safe_call(mandol_service.get_entity_subgraph, req.query, req.max_depth, req.top_k)
    return SubgraphResponse(**data)


@router.post("/graph/trace-evidence", response_model=TraceResponse)
def trace_evidence(req: TraceRequest) -> TraceResponse:
    """溯源链追踪。"""
    _require_enabled()
    data = _safe_call(mandol_service.trace_evidence, req.uid, req.max_depth, req.top_k)
    return TraceResponse(**data)


@router.post("/graph/trace-coref", response_model=TraceResponse)
def trace_coref(req: TraceRequest) -> TraceResponse:
    """共指链追踪。"""
    _require_enabled()
    data = _safe_call(mandol_service.trace_coref, req.uid, req.max_depth, req.top_k)
    return TraceResponse(**data)


@router.get("/graph/relations", response_model=List[dict])
def search_graph_relations(
    seed_nodes: Optional[List[str]] = Query(None),
    relation_types: Optional[List[str]] = Query(None),
    max_depth: int = Query(2, ge=1, le=5),
    limit: int = Query(50, ge=1, le=500),
) -> List[dict]:
    """搜索图关系。"""
    _require_enabled()
    return _safe_call(
        mandol_service.search_graph_relations,
        seed_nodes=seed_nodes, relation_types=relation_types,
        max_depth=max_depth, limit=limit,
    )


# =====================================================================
# 多视图检索
# =====================================================================
@router.post("/retrieve", response_model=MandolRetrieveResponse)
def retrieve(req: MandolRetrieveRequest) -> MandolRetrieveResponse:
    """统一检索接口：根据参数自动选择 holistic / view / space / text 模式。"""
    _require_enabled()
    if req.view:
        hits = _safe_call(
            mandol_service.retrieve_by_view,
            req.query, req.view, top_k=req.top_k, use_rerank=req.use_rerank,
        )
        mode = f"view:{req.view}"
    elif req.space_name:
        hits = _safe_call(
            mandol_service.retrieve_in_space,
            req.query, req.space_name, top_k=req.top_k, use_rerank=req.use_rerank,
        )
        mode = f"space:{req.space_name}"
    else:
        hits = _safe_call(
            mandol_service.holistic_retrieve,
            req.query, top_k=req.top_k, use_rerank=req.use_rerank, skip_views=req.skip_views,
        )
        mode = "holistic"
    return MandolRetrieveResponse(
        query=req.query, mode=mode, total=len(hits),
        results=[MandolSearchHit(**h) for h in hits],
    )


@router.post("/retrieve/text", response_model=MandolRetrieveResponse)
def retrieve_text(req: MandolRetrieveRequest) -> MandolRetrieveResponse:
    """纯向量文本检索（不含 rerank 与图扩展）。"""
    _require_enabled()
    hits = _safe_call(mandol_service.search_by_text, req.query, top_k=req.top_k)
    return MandolRetrieveResponse(
        query=req.query, mode="text", total=len(hits),
        results=[MandolSearchHit(**h) for h in hits],
    )


# =====================================================================
# 智能问答
# =====================================================================
@router.post("/ask", response_model=MandolAskResponse)
def ask(req: MandolAskRequest) -> MandolAskResponse:
    """基于记忆的智能问答（检索 + LLM 生成）。"""
    _require_enabled()
    data = _safe_call(
        mandol_service.ask,
        req.query, top_k=req.top_k, use_rerank=req.use_rerank,
        system_prompt=req.system_prompt, temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    return MandolAskResponse(
        answer=data["answer"],
        hits=[MandolSearchHit(**h) for h in data["hits"]],
    )


# =====================================================================
# 高阶记忆构建 & 跨会话合并
# =====================================================================
@router.post("/build", response_model=BuildReportResponse)
def build_high_level(req: BuildRequest) -> BuildReportResponse:
    """触发高阶记忆构建（实体/事件抽取、摘要）。"""
    _require_enabled()
    data = _safe_call(mandol_service.build_high_level, mode=req.mode)
    if data.get("error"):
        raise HTTPException(status_code=500, detail=data["error"])
    return BuildReportResponse(**data)


@router.post("/merge/entities", response_model=MergeResponse)
def merge_entities() -> MergeResponse:
    """跨会话实体合并。"""
    _require_enabled()
    data = _safe_call(mandol_service.merge_cross_session_entities)
    return MergeResponse(**data)


@router.post("/merge/events", response_model=MergeResponse)
def merge_events() -> MergeResponse:
    """跨会话事件合并。"""
    _require_enabled()
    data = _safe_call(mandol_service.merge_cross_session_events)
    return MergeResponse(**data)


# =====================================================================
# 持久化
# =====================================================================
@router.post("/save", response_model=SnapshotResponse)
def save_snapshot(req: SaveSnapshotRequest) -> SnapshotResponse:
    """持久化记忆系统。"""
    _require_enabled()
    data = _safe_call(mandol_service.save, req.storage_path)
    return SnapshotResponse(**data)


@router.post("/load", response_model=SnapshotResponse)
def load_snapshot(req: LoadSnapshotRequest) -> SnapshotResponse:
    """从路径加载记忆系统。"""
    _require_enabled()
    data = _safe_call(mandol_service.load, req.storage_path)
    return SnapshotResponse(status=data["status"], path=data["path"])


@router.post("/flush", response_model=StatusResponse)
def flush() -> StatusResponse:
    """刷新缓存。"""
    _require_enabled()
    _safe_call(mandol_service.flush)
    return StatusResponse(status="flushed")


@router.post("/reconfigure", response_model=StatusResponse)
def reconfigure() -> StatusResponse:
    """热重载 Mandol 系统（应用新配置后重建）。"""
    _require_enabled()
    ok = mandol_service.reconfigure()
    if not ok:
        raise HTTPException(status_code=500, detail="重新配置失败")
    return StatusResponse(status="ok", message="Mandol 系统已重新配置")
