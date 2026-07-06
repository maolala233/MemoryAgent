"""Memory retrieval: keyword (FTS5), semantic (cosine), and hybrid strategies."""
from __future__ import annotations

import asyncio
import math
from typing import Any, Dict, List, Optional

from ..database import db
from ..utils.logger import perf, warn
from .cache_service import cache
from .config_loader import get_retrieval_config
from .llm_adapter import get_embedding_provider
from .memory_service import memory_service


class SearchStrategy:
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    NONE = "none"


class MemoryRetriever:
    """Unified retrieval API used by search router and agents."""

    def __init__(self) -> None:
        self._embedding = get_embedding_provider()
        self._cfg = get_retrieval_config()

    def keyword_search(self, query: str, limit: int = 20, **filters) -> List[Dict[str, Any]]:
        return db.search_keyword(query, limit=limit, **filters)

    async def semantic_search(self, query: str, limit: int = 20,
                              min_score: float = 0.15, **filters) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        try:
            query_vec = await self._embedding.embed(query)
        except Exception as exc:
            warn(f"Semantic embed failed: {exc}")
            return []
        scored = []
        for rel_path, vec in db.iter_vectors(status=filters.get("status")):
            score = _cosine(query_vec, vec)
            if score >= min_score:
                scored.append((rel_path, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:limit]
        if not scored:
            return []
        results: List[Dict[str, Any]] = []
        for rel_path, score in scored:
            doc = memory_service.get_document(rel_path) or {}
            if filters.get("track") and doc.get("track") != filters["track"]:
                continue
            if filters.get("memory_type") and doc.get("memory_type") != filters["memory_type"]:
                continue
            results.append(
                {
                    "rel_path": rel_path,
                    "title": doc.get("title") or rel_path,
                    "snippet": (doc.get("summary") or (doc.get("content") or "")[:200])[:240],
                    "score": round(score, 4),
                    "memory_type": doc.get("memory_type"),
                    "track": doc.get("track"),
                    "updated_at": doc.get("updated_at"),
                }
            )
        return results

    async def hybrid_search(self, query: str, limit: int = 20, **filters) -> List[Dict[str, Any]]:
        kw_weight = self._cfg.get("strategies", {}).get("hybrid", {}).get("keyword_weight", 0.55)
        sem_weight = 1.0 - kw_weight
        kw = self.keyword_search(query, limit=limit * 2, **filters)
        sem = await self.semantic_search(query, limit=limit * 2, **filters)
        merged: Dict[str, Dict[str, Any]] = {}
        for r in kw:
            merged[r["rel_path"]] = {**r, "score": r["score"] * kw_weight}
        for r in sem:
            if r["rel_path"] in merged:
                merged[r["rel_path"]]["score"] += r["score"] * sem_weight
                # enrich snippet if missing
                if not merged[r["rel_path"]].get("snippet") and r.get("snippet"):
                    merged[r["rel_path"]]["snippet"] = r["snippet"]
            else:
                merged[r["rel_path"]] = {**r, "score": r["score"] * sem_weight}
        ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:limit]

    async def search(self, query: str, strategy: str = "hybrid",
                     limit: int = 20, min_score: float = 0.0,
                     **filters) -> List[Dict[str, Any]]:
        strategy = (strategy or "hybrid").lower()
        with perf.track(f"search.{strategy}"):
            if strategy == SearchStrategy.KEYWORD:
                results = self.keyword_search(query, limit=limit, **filters)
            elif strategy == SearchStrategy.SEMANTIC:
                results = await self.semantic_search(query, limit=limit, **filters)
            elif strategy == SearchStrategy.HYBRID:
                results = await self.hybrid_search(query, limit=limit, **filters)
            elif strategy == SearchStrategy.NONE:
                results = []
            else:
                results = await self.hybrid_search(query, limit=limit, **filters)
        if min_score > 0:
            results = [r for r in results if r.get("score", 0) >= min_score]
        perf.track_search(query, 0.0, len(results))
        return results

    def get_suggestions(self, prefix: str, limit: int = 8) -> List[str]:
        return db.get_suggestions(prefix, limit=limit)

    def get_filters(self) -> Dict[str, List[str]]:
        cached = cache.get("search:filters")
        if cached:
            return cached
        filters = db.get_filters()
        cache.set("search:filters", filters, ttl=3600)
        return filters


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


retriever = MemoryRetriever()
