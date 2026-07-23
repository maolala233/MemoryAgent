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
from ..utils.logger import warn, info

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
def stats(force: bool = Query(False, description="是否绕过缓存")) -> MandolStatsResponse:
    """获取 Mandol 记忆系统统计（带 5s 进程内缓存）。"""
    data = mandol_service.get_stats(force=force)
    return MandolStatsResponse(**data)


@router.get("/stats/quick")
def stats_quick() -> dict:
    """轻量统计：仅返回各类计数（仪表盘首屏使用，避免 token_usage 等慢字段）。

    走与 /stats 相同的 5s 缓存；只取出 dashboard 卡片需要的字段。
    """
    data = mandol_service.get_stats()
    if not data or not data.get("enabled"):
        return {"enabled": False}
    return {
        "enabled": True,
        "total_units": data.get("total_units", 0),
        "total_spaces": data.get("total_spaces", 0),
        "base_memory_count": data.get("base_memory_count", 0),
        "entity_count": data.get("entity_count", 0),
        "event_count": data.get("event_count", 0),
        "summary_count": data.get("summary_count", 0),
        "dirty": data.get("dirty", False),
        # Token 用量取自 _compute_stats 内的进程内计数器（O(1)），不会拉慢首屏
        "token_usage": data.get("token_usage", {}),
    }


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
    q: Optional[str] = Query(None, description="关键词模糊搜索（text / uid / space_name）"),
) -> MandolUnitListResponse:
    """列出记忆单元；支持关键词模糊搜索（小白友好入口）。

    当传入 `q` 时，先按关键词全量召回（覆盖数据全集），再按 limit/offset 截断。
    避免因分页/默认 limit 把关键词所在单元排除在外。
    """
    _require_enabled()
    kw = (q or "").strip().lower()
    if kw:
        # 关键词检索：拉全量后过滤（数据规模有限，全量扫描可接受）
        all_items = _safe_call(mandol_service.list_units, limit=10000, offset=0)
        matched = [
            i for i in all_items
            if kw in (i.get("text") or "").lower()
            or kw in (i.get("uid") or "").lower()
            or kw in (i.get("space_name") or "").lower()
        ]
        # 支持分页
        total = len(matched)
        items = matched[offset: offset + limit]
        return MandolUnitListResponse(total=total, items=[MandolUnitInfo(**i) for i in items])
    items = _safe_call(mandol_service.list_units, limit=limit, offset=offset)
    # total 必须是"全量总数", 而不是分页后的 len(items)——
    # 否则前端"记忆单元 (100)"会和仪表盘上的"总计 175"对不上。
    # 通过 get_stats() 拿 total_units, 走 5s 进程内缓存, 不会拖慢接口。
    try:
        total = int(mandol_service.get_stats(force=False).get("total_units", len(items)))
    except Exception:
        total = len(items)
    return MandolUnitListResponse(total=total, items=[MandolUnitInfo(**i) for i in items])


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


@router.get("/spaces/{name:path}/units", response_model=MandolUnitListResponse)
def list_units_in_space(name: str, limit: int = Query(100, ge=1, le=1000)) -> MandolUnitListResponse:
    """列出空间内的单元。

    注意：本路由必须在 /spaces/{name:path} 之前声明，
    否则会被后者捕获并把 name 解析为 "<space>/units"。
    """
    _require_enabled()
    items = _safe_call(mandol_service.list_units_in_space, name, limit=limit)
    return MandolUnitListResponse(total=len(items), items=[MandolUnitInfo(**i) for i in items])


@router.get("/entities", response_model=MandolUnitListResponse)
def list_entities(limit: int = Query(500, ge=1, le=2000)) -> MandolUnitListResponse:
    """列出所有实体（knowledge_entity 空间）。"""
    _require_enabled()
    items = _safe_call(mandol_service.list_entities, limit=limit)
    return MandolUnitListResponse(total=len(items), items=[MandolUnitInfo(**i) for i in items])


@router.get("/events", response_model=MandolUnitListResponse)
def list_events(limit: int = Query(500, ge=1, le=2000)) -> MandolUnitListResponse:
    """列出所有事件（episodic_event 空间）。"""
    _require_enabled()
    items = _safe_call(mandol_service.list_events, limit=limit)
    return MandolUnitListResponse(total=len(items), items=[MandolUnitInfo(**i) for i in items])


@router.get("/summaries", response_model=MandolUnitListResponse)
def list_summaries(limit: int = Query(500, ge=1, le=2000)) -> MandolUnitListResponse:
    """列出所有摘要（episodic_summary 空间）。"""
    _require_enabled()
    items = _safe_call(mandol_service.list_summaries, limit=limit)
    return MandolUnitListResponse(total=len(items), items=[MandolUnitInfo(**i) for i in items])


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


@router.post("/graph/sync-neo4j", response_model=StatusResponse)
def sync_graph_to_neo4j() -> StatusResponse:
    """把 Mandol 内存图(NetworkX)同步到外部 Neo4j,供前端 neo4j tab 显示。

    Mandol 默认使用 InMemoryGraphStore(NetworkX),与外部 Neo4j 之间
    没有自动同步机制;前端 neo4j tab 直接查 Neo4j,所以会一直显示 0 节点。
    该接口读取 memory_system._graph_store 的全部节点/边,写入 Neo4j
    (使用 MERGE 去重,不会产生重复)。
    """
    _require_enabled()
    result = _safe_call(mandol_service.sync_graph_to_neo4j)
    return StatusResponse(
        status=result.get("status", "unknown"),
        message=f"nodes={result.get('nodes', 0)}, edges={result.get('edges', 0)}",
    )


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
    """触发高阶记忆构建（实体/事件抽取、摘要）。

    req.skip_summary 默认 True：跳过 summary 生成，直接用原文切片。
    """
    _require_enabled()
    data = _safe_call(
        mandol_service.build_high_level,
        mode=req.mode, skip_summary=req.skip_summary,
    )
    if data.get("error"):
        raise HTTPException(status_code=500, detail=data["error"])
    return BuildReportResponse(**data)


@router.get("/build-status")
def build_status() -> dict:
    """查询高阶记忆构建的实时状态（供前端轮询）。

    返回字段:
      - status: idle | running | completed | failed
      - message: 当前阶段的中文描述
      - started_at / finished_at: 时间戳
      - elapsed_seconds: 运行时长
      - result: 最近一次构建的最终报告
    """
    _require_enabled()
    return mandol_service.build_status()


@router.post("/build-async")
def build_high_level_async(req: BuildRequest) -> dict:
    """异步触发高阶记忆构建，立刻返回当前状态。

    实际工作在后台线程里跑；前端通过 /api/mandol/build-status 轮询进度。
    """
    _require_enabled()
    return mandol_service.build_high_level_async(
        mode=req.mode, skip_summary=req.skip_summary,
    )


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
    """持久化记忆系统（默认后台异步执行，避免阻塞 API）。"""
    _require_enabled()
    data = _safe_call(mandol_service.save, req.storage_path, wait=req.wait if hasattr(req, "wait") else False)
    return SnapshotResponse(**data)


@router.get("/save-status")
def save_snapshot_status() -> dict:
    """查询最近一次 snapshot 保存状态。"""
    _require_enabled()
    return mandol_service.save_status()


@router.get("/token-usage")
def get_token_usage() -> dict:
    """返回跨会话累计 token 用量 (build / chat / total)。

    与 /stats/quick 内嵌的 token_usage 一致, 但作为独立 endpoint 方便前端调试/刷新。
    数值持久化到 token_usage.json, 重启不丢。
    """
    _require_enabled()
    return {
        "enabled": True,
        "token_usage": mandol_service.get_cumulative_token_usage(),
    }


@router.post("/token-usage/reset", response_model=StatusResponse)
def reset_token_usage() -> StatusResponse:
    """清零跨会话 token 累计 (前端「重置用量」按钮 / 调试)。"""
    _require_enabled()
    mandol_service.reset_cumulative_token_usage()
    return StatusResponse(status="ok", message="token 用量已清零")


@router.get("/external-store-status")
def external_store_status(force: bool = Query(False, description="是否绕过缓存")) -> dict:
    """查询 Neo4j + Milvus + snapshot 实际状态（带 10s 进程内缓存）。"""
    _require_enabled()
    return mandol_service.external_store_status(force=force)


@router.get("/neo4j/entities/search")
def search_entities(
    q: str = Query(..., min_length=1, max_length=200, description="关键词（实体名/文本片段）"),
    limit: int = Query(15, ge=1, le=50),
    label: Optional[str] = Query(None, description="限定节点标签，如 Entity / Document / Event"),
) -> dict:
    """Neo4j 节点模糊搜索（用于前端图谱小白检索）。

    在 ``name`` / ``title`` / ``text`` 等常见文本字段上做大小写不敏感的子串匹配，
    返回 uid / label / 显示名 / 简短摘要，供前端下拉建议使用。
    """
    _require_enabled()
    from ..config.settings import settings as _s
    from neo4j import GraphDatabase as _GD
    d = _GD.driver(_s.mandol_neo4j_uri, auth=(_s.mandol_neo4j_user, _s.mandol_neo4j_password))
    try:
        with d.session(database=_s.mandol_neo4j_database) as sess:
            cypher = (
                "MATCH (n) "
                "WHERE ($label IS NULL OR $label IN labels(n)) "
                "  AND (toLower(coalesce(n.name, '')) CONTAINS toLower($q) "
                "    OR toLower(coalesce(n.title, '')) CONTAINS toLower($q) "
                "    OR toLower(coalesce(n.text, '')) CONTAINS toLower($q) "
                "    OR toLower(coalesce(n.uid, '')) CONTAINS toLower($q)) "
                "RETURN n.uid AS uid, labels(n) AS labels, "
                "       coalesce(n.name, n.title) AS display, "
                "       substring(coalesce(n.text, ''), 0, 120) AS snippet, "
                "       n._label AS mandol_type "
                "LIMIT $lim"
            )
            rows = [dict(r) for r in sess.run(cypher, q=q, label=label, lim=limit)]
            return {"items": rows, "count": len(rows), "q": q}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"实体搜索失败: {exc}")
    finally:
        d.close()


@router.get("/neo4j/subgraph")
def neo4j_subgraph(
    center_uid: Optional[str] = Query(None, description="中心节点 UID"),
    limit: int = Query(200, ge=1, le=2000),
    keyword: Optional[str] = Query(None, description="关键词（节点 name/title/text 模糊匹配）"),
) -> dict:
    """从 Neo4j 读取全图或子图（用于图谱可视化）。"""
    _require_enabled()
    from ..config.settings import settings as _s
    from neo4j import GraphDatabase as _GD
    d = _GD.driver(_s.mandol_neo4j_uri, auth=(_s.mandol_neo4j_user, _s.mandol_neo4j_password))
    try:
        with d.session(database=_s.mandol_neo4j_database) as sess:
            if center_uid:
                q_nodes = (
                    "MATCH (a {uid:$c})-[*1..2]-(b) "
                    "WITH collect(distinct a) + collect(distinct b) AS ns "
                    "UNWIND ns AS n RETURN DISTINCT n.uid AS uid, labels(n) AS labels, properties(n) AS props LIMIT $lim"
                )
                # 取出两跳内的节点，再匹配这些节点两两之间的边（更稳定）
                q_edges = (
                    "MATCH (a {uid:$c})-[*1..2]-(b) "
                    "WITH collect(distinct a) + collect(distinct b) AS ns "
                    "UNWIND ns AS n MATCH (n)-[r]-(m) WHERE m IN ns "
                    "RETURN DISTINCT id(r) AS id, n.uid AS s, m.uid AS t, "
                    "       type(r) AS type, properties(r) AS props LIMIT $lim"
                )
                nodes = [dict(r) for r in sess.run(q_nodes, c=center_uid, lim=limit)]
                edges = [dict(r) for r in sess.run(q_edges, c=center_uid, lim=limit)]
            elif keyword:
                # 关键词模糊匹配 — 在 name/title/text/uid 上做大小写不敏感子串匹配
                q_nodes = (
                    "MATCH (n) WHERE toLower(coalesce(n.name,'')) CONTAINS toLower($kw) "
                    "  OR toLower(coalesce(n.title,'')) CONTAINS toLower($kw) "
                    "  OR toLower(coalesce(n.text,'')) CONTAINS toLower($kw) "
                    "  OR toLower(coalesce(n.uid,'')) CONTAINS toLower($kw) "
                    "RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS props LIMIT $lim"
                )
                q_edges = (
                    "MATCH (a)-[r]->(b) WHERE toLower(coalesce(a.name,'')) CONTAINS toLower($kw) "
                    "  OR toLower(coalesce(b.name,'')) CONTAINS toLower($kw) "
                    "  OR toLower(coalesce(a.uid,'')) CONTAINS toLower($kw) "
                    "  OR toLower(coalesce(b.uid,'')) CONTAINS toLower($kw) "
                    "RETURN id(r) AS id, a.uid AS s, b.uid AS t, type(r) AS type, properties(r) AS props LIMIT $lim"
                )
                nodes = [dict(r) for r in sess.run(q_nodes, kw=keyword, lim=limit)]
                edges = [dict(r) for r in sess.run(q_edges, kw=keyword, lim=limit)]
                # 若只有 uid 匹配，补一次：拿到匹配节点直接相连的边
                if nodes and not edges:
                    uids = [n.get("uid") for n in nodes if n.get("uid")]
                    if uids:
                        q_edges2 = (
                            "MATCH (a)-[r]->(b) WHERE a.uid IN $uids OR b.uid IN $uids "
                            "RETURN id(r) AS id, a.uid AS s, b.uid AS t, type(r) AS type, properties(r) AS props LIMIT $lim"
                        )
                        edges = [dict(r) for r in sess.run(q_edges2, uids=uids, lim=limit)]
            else:
                nodes = [
                    dict(r) for r in sess.run(
                        "MATCH (n) RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS props LIMIT $lim",
                        lim=limit,
                    )
                ]
                edges = [
                    dict(r) for r in sess.run(
                        "MATCH (a)-[r]->(b) RETURN id(r) AS id, a.uid AS s, b.uid AS t, "
                        "type(r) AS type, properties(r) AS props LIMIT $lim",
                        lim=limit,
                    )
                ]
            return {"nodes": nodes, "edges": edges, "center": center_uid or keyword}
    finally:
        d.close()


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


# ─── 数据管理：细粒度清空接口（仪表盘使用）───────────────────────────
def _clear_resp(data: dict) -> StatusResponse:
    if data.get("error"):
        raise HTTPException(status_code=400, detail=data["error"])
    return StatusResponse(status="cleared", message=str(data.get("detail", data)))


@router.post("/clear-units", response_model=StatusResponse)
def clear_units() -> StatusResponse:
    """仅清空记忆单元（Milvus 向量 + Mandol 内存中单元 + Neo4j 关系）；
    实体 / 事件节点保留。"""
    _require_enabled()
    return _clear_resp(mandol_service.clear_units())


@router.post("/clear-spaces", response_model=StatusResponse)
def clear_spaces() -> StatusResponse:
    """仅清空记忆空间。仅在记忆单元为 0 时允许执行。"""
    _require_enabled()
    return _clear_resp(mandol_service.clear_spaces())


@router.post("/clear-entities", response_model=StatusResponse)
def clear_entities() -> StatusResponse:
    """仅清空 Neo4j 中的实体节点 + Mandol 内部实体集合。"""
    _require_enabled()
    return _clear_resp(mandol_service.clear_entities())


@router.post("/clear-events", response_model=StatusResponse)
def clear_events() -> StatusResponse:
    """仅清空 Neo4j 中的事件节点 + Mandol 内部事件集合。"""
    _require_enabled()
    return _clear_resp(mandol_service.clear_events())


@router.post("/clear-neo4j", response_model=StatusResponse)
def clear_neo4j() -> StatusResponse:
    """清空整个 Neo4j 图（节点 + 关系）。"""
    _require_enabled()
    return _clear_resp(mandol_service.clear_neo4j_only())


@router.post("/clear-milvus", response_model=StatusResponse)
def clear_milvus() -> StatusResponse:
    """清空 Milvus 向量集合。"""
    _require_enabled()
    return _clear_resp(mandol_service.clear_milvus_only())


@router.post("/clear-summaries", response_model=StatusResponse)
def clear_summaries() -> StatusResponse:
    """剥离 vault 文档 frontmatter 中的 summary 字段。"""
    return _clear_resp(mandol_service.clear_summaries())


@router.post("/clear-base-memories", response_model=StatusResponse)
def clear_base_memories() -> StatusResponse:
    """删除 data/vault/imports/ 下的所有解析文件。"""
    return _clear_resp(mandol_service.clear_base_memories())


@router.post("/clear-everything", response_model=StatusResponse)
def clear_everything() -> StatusResponse:
    """清空所有数据: Mandol 记忆 + Neo4j + Milvus + 基础记忆文件 + 摘要。

    改为后台线程异步执行, 立即返回 status=running,
    实际进度通过 /api/mandol/clear-status 轮询。
    修复: 同步执行需要 30+ 秒, 前端一直转圈像卡死。
    """
    _require_enabled()
    data = mandol_service.clear_all_async()
    if data.get("error"):
        raise HTTPException(status_code=500, detail=data["error"])
    return StatusResponse(
        status=data.get("status", "running"),
        message=data.get("message", "清空任务已启动, 后台执行中…"),
    )


@router.get("/clear-status")
def clear_status() -> dict:
    """查询清空任务的实时状态(供前端轮询)。"""
    _require_enabled()
    return mandol_service.clear_status()


@router.post("/clear-all", response_model=StatusResponse)
def clear_all() -> StatusResponse:
    """清空所有 Mandol 记忆数据：Neo4j 图 + Milvus 向量 + 本地快照 + 内存状态。

    用于在 prompt / embedding / 配置重大变更后彻底重建。
    完成后系统是空的，需重新调用 /ingest-vault + /build 才能继续问答。
    """
    _require_enabled()
    data = _safe_call(mandol_service.clear_all)
    if data.get("error"):
        raise HTTPException(status_code=500, detail=data["error"])
    return StatusResponse(
        status="cleared",
        message=(
            f"neo4j={'ok' if data.get('neo4j_cleared') else 'fail'} "
            f"milvus={'ok' if data.get('milvus_cleared') else 'fail'} "
            f"snapshot={'ok' if data.get('snapshot_removed') else 'fail'} "
            f"reinit={'ok' if data.get('system_reinitialized') else 'fail'}"
        ),
    )


@router.post("/reembed-all")
def reembed_all(only_zero: bool = True, batch_size: int = 32) -> dict:
    """重新计算所有单元的 embedding（修复零向量场景）。

    - only_zero=True: 只处理当前 embedding 全为 0 的 unit（增量修复）。
    - only_zero=False: 强制重算所有 unit。
    """
    _require_enabled()
    return _safe_call(mandol_service.reembed_all_units, only_zero=only_zero, batch_size=batch_size)


@router.post("/reconfigure", response_model=StatusResponse)
def reconfigure() -> StatusResponse:
    """热重载 Mandol 系统（应用新配置后重建）。"""
    _require_enabled()
    ok = mandol_service.reconfigure()
    if not ok:
        raise HTTPException(status_code=500, detail="重新配置失败")
    return StatusResponse(status="ok", message="Mandol 系统已重新配置")


@router.post("/ingest-vault", response_model=StatusResponse)
def ingest_vault(space_name: str = "default_base_memory",
                 max_tokens: int = 250, overlap: int = 40) -> StatusResponse:
    """一次性把 vault 目录所有 .md 分块后加入 Mandol 指定 space。

    跳过已存在的 chunk uid。完成后重建 faiss 索引。
    专用于修复 rescan 不推 Mandol 的历史遗漏。
    """
    _require_enabled()
    from backend.config.settings import settings as _s
    from backend.services.chunking_service import chunking_service
    import re, time as _t

    vault = _s.vault_dir
    if not vault.exists():
        raise HTTPException(status_code=404, detail=f"vault 目录不存在: {vault}")
    md_files = sorted(vault.rglob("*.md"))
    md_files = [p for p in md_files if not any(part.startswith(".") for part in p.parts)]
    sm = mandol_service._system.semantic_map  # noqa: SLF001
    sm.create_space(space_name)
    existing = {str(u.uid) for u in sm.list_units() if str(u.uid).startswith("doc:")}
    added = 0
    skipped = 0
    t0 = _t.time()
    for p in md_files:
        rel = p.relative_to(vault).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if text.startswith("---"):
            m = re.match(r"^---\n(.+?)\n---\n(.*)$", text, re.DOTALL)
            if m:
                text = m.group(2)
        if not text.strip():
            continue
        try:
            chunks = chunking_service.chunk_document(text, max_tokens=max_tokens, overlap=overlap)
        except Exception:
            chunks = []
        if not chunks:
            chunks = [type("C", (), {"text": text[:2000], "index": 0, "section": ""})()]
        for c in chunks:
            ctext = c.text if hasattr(c, "text") else c.get("text", "")
            idx = c.index if hasattr(c, "index") else 0
            sec = c.section if hasattr(c, "section") else ""
            if not ctext.strip():
                continue
            uid_str = f"doc:{rel}:chunk:{idx}"
            if uid_str in existing:
                skipped += 1
                continue
            from mandol import MemoryUnit, Uid
            unit = MemoryUnit(
                uid=Uid(uid_str),
                raw_data={"text_content": ctext},
                metadata={"rel_path": rel, "chunk_index": idx, "section": sec, "source": "vault_ingest"},
            )
            try:
                sm.add_unit(unit, space_names=[space_name], ensure_embedding=True)
                added += 1
            except Exception as e:
                warn(f"ingest add_unit fail {uid_str}: {e}")
    # 重建 faiss index
    try:
        sm.rebuild_index_from_store()
    except Exception as e:
        warn(f"ingest rebuild_index fail: {e}")
    # 重建 space 关联
    try:
        mandol_service.rebuild_spaces_from_units()
    except Exception as e:
        warn(f"ingest rebuild_spaces fail: {e}")
    return StatusResponse(
        status="ok",
        message=f"ingest done: files={len(md_files)} added={added} skipped={skipped} dur={_t.time()-t0:.1f}s",
    )
