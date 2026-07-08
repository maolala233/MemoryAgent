"""搜索路由：整合 Mandol 多视图检索与传统检索。

支持策略：
- hybrid / keyword / semantic：传统 Markdown + SQLite 检索
- mandol / holistic：Mandol 全记忆整体检索
- view：Mandol 按视图检索（knowledge/entity_relation/event_causal 等）
- space：Mandol 按空间检索
- graph：Mandol 图 BFS 扩展检索
- text：Mandol 纯向量文本检索
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import (
    MemoryResult,
    SearchFilters,
    SearchRequest,
    SearchResponse,
)
from ..services.retrieval_service import retriever
from ..services.mandol_service import mandol_service
from ..utils.logger import warn

router = APIRouter(prefix="/api/search", tags=["search"])


def _mandol_hit_to_result(hit: dict) -> MemoryResult:
    """将 Mandol 命中转换为 MemoryResult。"""
    metadata = hit.get("metadata", {}) or {}
    return MemoryResult(
        rel_path=metadata.get("source_path", "") or f"mandol:{hit.get('uid', '')}",
        title=metadata.get("entity_name") or metadata.get("event_name") or hit.get("uid", ""),
        snippet=(hit.get("text") or "")[:240],
        score=hit.get("score", 0.0),
        memory_type=metadata.get("type"),
        track=metadata.get("track", "mandol"),
        uid=hit.get("uid"),
        text=hit.get("text"),
        metadata=metadata,
        raw_data=hit.get("raw_data"),
        scores=hit.get("scores"),
        ranks=hit.get("ranks"),
    )


@router.post("", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    """统一搜索接口。"""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")

    strategy = (req.strategy or "hybrid").lower()
    results = []

    # Mandol 系列策略
    if strategy in ("mandol", "holistic") and mandol_service.is_enabled:
        try:
            hits = mandol_service.holistic_retrieve(
                req.query, top_k=req.limit, use_rerank=req.use_rerank,
                skip_views=req.skip_views,
            )
            results = [_mandol_hit_to_result(h) for h in hits]
        except Exception as exc:
            warn(f"Mandol holistic 检索失败: {exc}")

    elif strategy in ("entity", "entity_relation") and mandol_service.is_enabled:
        try:
            hits = mandol_service.retrieve_by_view(
                req.query, "entity_relation", top_k=req.limit, use_rerank=req.use_rerank,
            )
            results = [_mandol_hit_to_result(h) for h in hits]
        except Exception as exc:
            warn(f"Mandol entity 检索失败: {exc}")

    elif strategy in ("event", "causal", "event_causal") and mandol_service.is_enabled:
        try:
            hits = mandol_service.retrieve_by_view(
                req.query, "event_causal", top_k=req.limit, use_rerank=req.use_rerank,
            )
            results = [_mandol_hit_to_result(h) for h in hits]
        except Exception as exc:
            warn(f"Mandol event 检索失败: {exc}")

    elif strategy == "view" and mandol_service.is_enabled:
        if not req.view:
            raise HTTPException(status_code=400, detail="view 策略需要指定 view 参数")
        try:
            hits = mandol_service.retrieve_by_view(
                req.query, req.view, top_k=req.limit, use_rerank=req.use_rerank,
            )
            results = [_mandol_hit_to_result(h) for h in hits]
        except Exception as exc:
            warn(f"Mandol view 检索失败: {exc}")

    elif strategy == "space" and mandol_service.is_enabled:
        if not req.space_name:
            raise HTTPException(status_code=400, detail="space 策略需要指定 space_name 参数")
        try:
            hits = mandol_service.retrieve_in_space(
                req.query, req.space_name, top_k=req.limit, use_rerank=req.use_rerank,
            )
            results = [_mandol_hit_to_result(h) for h in hits]
        except Exception as exc:
            warn(f"Mandol space 检索失败: {exc}")

    elif strategy == "text" and mandol_service.is_enabled:
        try:
            hits = mandol_service.search_by_text(req.query, top_k=req.limit)
            results = [_mandol_hit_to_result(h) for h in hits]
        except Exception as exc:
            warn(f"Mandol text 检索失败: {exc}")

    elif strategy == "graph" and mandol_service.is_enabled:
        try:
            # 先检索种子，再 BFS 扩展
            seed_hits = mandol_service.holistic_retrieve(
                req.query, top_k=5, use_rerank=False,
            )
            results = [_mandol_hit_to_result(h) for h in seed_hits]
            seed_uids = [h.get("uid") for h in seed_hits if h.get("uid")]
            if seed_uids:
                expanded = mandol_service.bfs_expand(seed_uids, per_seed=3, hops=1)
                existing_uids = {r.uid for r in results if r.uid}
                for u in expanded:
                    if u.get("uid") not in existing_uids:
                        results.append(_mandol_hit_to_result({
                            "uid": u.get("uid"),
                            "text": u.get("text"),
                            "score": 0.5,
                            "metadata": u.get("metadata"),
                            "raw_data": u.get("raw_data"),
                        }))
            results = results[:req.limit]
        except Exception as exc:
            warn(f"Mandol graph 检索失败: {exc}")

    else:
        # 传统检索
        filters = {
            k: v for k, v in {
                "track": req.track,
                "memory_type": req.memory_type,
                "status": req.status,
            }.items() if v
        }
        results = await retriever.search(
            req.query, strategy=strategy, limit=req.limit,
            min_score=req.min_score, **filters,
        )
        results = [MemoryResult(**r) for r in results]

    # Fallback：如果 Mandol 策略返回 0 条结果，退回全息检索
    if not results and strategy in ("entity", "event", "causal", "entity_relation", "event_causal", "view", "space", "graph") and mandol_service.is_enabled:
        try:
            warn(f"策略 {strategy} 返回 0 条结果，fallback 到 holistic 检索")
            hits = mandol_service.holistic_retrieve(
                req.query, top_k=req.limit, use_rerank=req.use_rerank,
            )
            results = [_mandol_hit_to_result(h) for h in hits]
        except Exception as exc:
            warn(f"Fallback holistic 检索也失败: {exc}")

    # Fallback：如果传统检索返回 0 条，尝试 Mandol text 检索
    if not results and strategy in ("keyword", "semantic", "hybrid") and mandol_service.is_enabled:
        try:
            warn(f"传统检索 {strategy} 返回 0 条结果，fallback 到 Mandol text 检索")
            hits = mandol_service.search_by_text(req.query, top_k=req.limit)
            results = [_mandol_hit_to_result(h) for h in hits]
        except Exception as exc:
            warn(f"Fallback text 检索也失败: {exc}")

    if req.min_score > 0:
        results = [r for r in results if r.score >= req.min_score]

    return SearchResponse(
        query=req.query,
        strategy=strategy,
        total=len(results),
        results=results,
    )


@router.get("/suggestions", response_model=list[str])
def suggestions(q: str = Query(..., min_length=1), limit: int = Query(8, ge=1, le=20)) -> list[str]:
    """搜索建议。"""
    return retriever.get_suggestions(q, limit=limit)


@router.get("/filters", response_model=SearchFilters)
def filters() -> SearchFilters:
    """获取可用过滤器。"""
    data = retriever.get_filters()
    return SearchFilters(**data)
