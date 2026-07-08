"""Memory retrieval: keyword (FTS5), semantic (cosine), hybrid, and Mandol graph strategies."""
from __future__ import annotations

import math
from typing import Any, Dict, List

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
    # Mandol-powered strategies
    MANDOL = "mandol"          # Holistic multi-group retrieval
    GRAPH = "graph"            # Graph BFS expansion
    ENTITY = "entity"          # Entity view retrieval
    EVENT = "event"            # Event view retrieval
    CAUSAL = "causal"          # Causal chain tracing


class MemoryRetriever:
    """Unified retrieval API used by search router and agents.
    
    Supports both traditional Markdown+SQLite retrieval and advanced
    Mandol graph-based retrieval when enabled.
    """

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

    def _mandol_holistic_search(self, query: str, limit: int = 20, **filters) -> List[Dict[str, Any]]:
        """Retrieve using Mandol's multi-group holistic retrieval."""
        from .mandol_service import mandol_service
        if not mandol_service.is_enabled:
            warn("Mandol not enabled, falling back to hybrid search")
            return []
        
        use_rerank = filters.get("use_rerank", True)
        skip_views = filters.get("skip_views")
        
        hits = mandol_service.holistic_retrieve(
            query, top_k=limit, use_rerank=use_rerank, skip_views=skip_views
        )
        return self._convert_mandol_hits(hits)

    def _mandol_entity_search(self, query: str, limit: int = 20, **filters) -> List[Dict[str, Any]]:
        """Retrieve entities using Mandol's entity view."""
        from .mandol_service import mandol_service
        if not mandol_service.is_enabled:
            return []
        
        hits = mandol_service.retrieve_by_view(query, "entity_relation", top_k=limit, use_rerank=False)
        return self._convert_mandol_hits(hits, memory_type="entity")

    def _mandol_event_search(self, query: str, limit: int = 20, **filters) -> List[Dict[str, Any]]:
        """Retrieve events using Mandol's event view."""
        from .mandol_service import mandol_service
        if not mandol_service.is_enabled:
            return []
        
        hits = mandol_service.retrieve_by_view(query, "event_causal", top_k=limit, use_rerank=False)
        return self._convert_mandol_hits(hits, memory_type="event")

    def _mandol_graph_search(self, query: str, limit: int = 20, **filters) -> List[Dict[str, Any]]:
        """Retrieve using Mandol's graph BFS expansion."""
        from .mandol_service import mandol_service
        if not mandol_service.is_enabled:
            return []
        
        # First do a base retrieval to find seed entities
        hits = mandol_service.retrieve_by_view(query, "base_memory", top_k=5, use_rerank=False)
        if not hits:
            return []
        
        # Expand from seed entities
        all_results = self._convert_mandol_hits(hits)
        for hit in hits[:3]:  # Expand from top 3 seeds
            uid = hit.get("uid", "")
            if uid:
                subgraph = mandol_service.get_entity_subgraph(uid, hops=filters.get("hops", 2))
                for node in subgraph.get("nodes", []):
                    all_results.append({
                        "rel_path": f"graph:{node.get('uid', '')}",
                        "title": node.get("name", ""),
                        "snippet": node.get("text", "")[:240],
                        "score": 0.5,
                        "memory_type": node.get("type", "entity"),
                        "track": "graph",
                        "updated_at": None,
                    })
        
        return all_results[:limit]

    def _mandol_causal_search(self, query: str, limit: int = 20, **filters) -> List[Dict[str, Any]]:
        """Trace causal chains using Mandol."""
        from .mandol_service import mandol_service
        if not mandol_service.is_enabled:
            return []
        
        chain = mandol_service.get_causal_chain(
            query,
            max_hops=filters.get("max_hops", 3),
            direction=filters.get("direction", "both"),
        )
        
        results = []
        for step in chain.get("chain", []):
            results.append({
                "rel_path": f"causal:{step.get('event_uid', '')}",
                "title": step.get("event_name", ""),
                "snippet": step.get("description", "")[:240],
                "score": step.get("confidence", 0.5),
                "memory_type": "event",
                "track": "causal",
                "updated_at": None,
            })
        
        return results[:limit]

    def _convert_mandol_hits(self, hits: List[Dict[str, Any]], memory_type: str = "note") -> List[Dict[str, Any]]:
        """Convert Mandol SearchHit dicts to standard result format."""
        results = []
        for hit in hits:
            metadata = hit.get("metadata", {})
            
            # Try to find corresponding vault document
            rel_path = metadata.get("source_path", "")
            if not rel_path:
                rel_path = f"mandol:{hit.get('uid', 'unknown')}"
            
            results.append({
                "rel_path": rel_path,
                "title": metadata.get("entity_name") or metadata.get("event_name") or rel_path,
                "snippet": hit.get("text", "")[:240],
                "score": round(hit.get("score", 0.0), 4),
                "memory_type": metadata.get("type", memory_type),
                "track": metadata.get("track", "mandol"),
                "updated_at": metadata.get("updated_at"),
                "uid": hit.get("uid", ""),
                "mandol_metadata": metadata,
            })
        
        return results

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
            elif strategy == SearchStrategy.MANDOL:
                results = self._mandol_holistic_search(query, limit=limit, **filters)
            elif strategy == SearchStrategy.ENTITY:
                results = self._mandol_entity_search(query, limit=limit, **filters)
            elif strategy == SearchStrategy.EVENT:
                results = self._mandol_event_search(query, limit=limit, **filters)
            elif strategy == SearchStrategy.GRAPH:
                results = self._mandol_graph_search(query, limit=limit, **filters)
            elif strategy == SearchStrategy.CAUSAL:
                results = self._mandol_causal_search(query, limit=limit, **filters)
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
