"""Mandol MemorySystem 适配服务。

基于真实 mandol 0.1.0 API，封装 MemorySystem 的生命周期、文档同步、
多视图检索、图谱操作、高阶记忆构建、智能问答与持久化能力，
作为前端与 mandol 底层能力之间的桥梁。
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..config.settings import settings
from ..utils.logger import info, warn

logger = logging.getLogger(__name__)

# 视图名称常量（对应 mandol 的记忆分组）
VIEWS = [
    "base_memory",
    "knowledge",
    "entity_relation",
    "event_causal",
    "emotional",
    "episodic",
    "procedural",
    "insights",
]

# 支持的关系类型
RELATIONSHIP_TYPES = [
    "PRECEDES", "FOLLOWS", "SEMANTIC_SIMILAR", "RELATED_TO",
    "COREF", "CAUSES", "CAUSED_BY", "INVOLVES",
    "EVIDENCED_BY", "ALIAS_OF",
]


def _unit_to_dict(unit) -> Dict[str, Any]:
    """将 MemoryUnit 转换为可序列化字典。"""
    return {
        "uid": str(unit.uid),
        "raw_data": unit.raw_data,
        "metadata": unit.metadata,
        "text": unit.raw_data.get("text_content", ""),
    }


def _hit_to_dict(hit) -> Dict[str, Any]:
    """将 SearchHit 转换为可序列化字典。"""
    unit = hit.unit
    return {
        "uid": str(unit.uid),
        "text": unit.raw_data.get("text_content", ""),
        "score": float(hit.final_score),
        "metadata": unit.metadata,
        "raw_data": unit.raw_data,
        "scores": {k: float(v) for k, v in hit.scores.items()},
        "ranks": dict(hit.ranks),
        "debug": dict(hit.debug) if hasattr(hit, "debug") else {},
    }


class MandolService:
    """Mandol MemorySystem 适配器。

    提供懒加载、线程安全的 MemorySystem 单例，并暴露文档同步、
    多视图检索、图谱遍历、高阶记忆构建、智能问答与持久化能力。
    """

    def __init__(self) -> None:
        self._system = None
        self._enabled = False
        self._lock = threading.RLock()
        self._init_attempted = False
        self._storage_root: Optional[str] = None
        self._save_in_progress = threading.Event()
        self._last_save_result: Optional[Dict[str, Any]] = None

    # ---------------- 生命周期 ----------------
    def initialize(self) -> bool:
        """标记为启用，实际初始化延迟到首次使用。"""
        if not settings.mandol_enabled:
            info("Mandol 集成已在配置中禁用")
            return False
        self._enabled = True
        self._init_attempted = False
        info("Mandol 集成已启用（懒加载，首次使用时初始化）")
        return True

    def _ensure_initialized(self) -> bool:
        """懒加载初始化底层 MemorySystem。"""
        if not self._enabled:
            return False
        if self._system is not None:
            return True
        with self._lock:
            if self._system is not None:
                return True
            if self._init_attempted:
                return False
            self._init_attempted = True
            try:
                return self._do_initialize()
            except Exception as exc:
                logger.exception("Mandol 初始化失败")
                warn(f"Mandol 初始化失败: {exc}")
                return False

    def _do_initialize(self) -> bool:
        """执行真正的初始化。

        集成 Neo4j 图数据库 + Milvus Lite 向量数据库 + 持久化。
        通过显式构造 store 注入到 SystemFactory.create，绕开默认的 in-memory 实现。
        """
        from mandol import MemorySystem, MemorySystemConfig
        from mandol.infrastructure.system_factory import SystemFactory

        cfg = self._build_config()
        storage_root = str(settings.mandol_storage_dir)
        Path(storage_root).mkdir(parents=True, exist_ok=True)
        self._storage_root = storage_root

        # 构建 LLM provider（mandol 默认从环境变量读取，这里显式传入）
        llm_provider = self._build_llm_provider()

        # 构建外部存储后端（Neo4j + Milvus Lite）
        graph_store = None
        unit_store = None
        try:
            graph_store = self._build_neo4j_graph_store()
            info("Mandol 使用 Neo4j GraphStore")
        except Exception as exc:
            warn(f"Neo4j GraphStore 初始化失败，回退到 InMemoryGraphStore: {exc}")
        try:
            unit_store = self._build_milvus_unit_store(cfg.embedder_dim)
            info(f"Mandol 使用 Milvus UnitStore (uri={settings.mandol_milvus_uri})")
        except Exception as exc:
            warn(f"Milvus UnitStore 初始化失败，回退到 InMemoryUnitStore: {exc}")

        # 尝试从已有快照加载，否则新建
        snapshot_file = Path(storage_root) / "snapshot.json"
        if snapshot_file.exists():
            try:
                self._system = MemorySystem.load(str(snapshot_file), llm_provider=llm_provider)
                info(f"已从快照加载 Mandol MemorySystem: {snapshot_file}")
            except Exception as exc:
                warn(f"加载快照失败，将新建系统: {exc}")
                self._system = SystemFactory.create(
                    config=cfg,
                    storage_root=storage_root,
                    enable_persistence=settings.mandol_enable_persistence,
                    auto_save_interval=settings.mandol_auto_save_interval,
                    llm_provider=llm_provider,
                    graph_store=graph_store,
                    unit_store=unit_store,
                )
        else:
            self._system = SystemFactory.create(
                config=cfg,
                storage_root=storage_root,
                enable_persistence=settings.mandol_enable_persistence,
                auto_save_interval=settings.mandol_auto_save_interval,
                llm_provider=llm_provider,
                graph_store=graph_store,
                unit_store=unit_store,
            )
            info(f"已创建新的 Mandol MemorySystem，存储目录: {storage_root}")
        return True

    def _build_neo4j_graph_store(self) -> Any:
        """构造 Neo4j GraphStore，从 settings 读取连接信息。"""
        from mandol.infrastructure.neo4j_graph_store import Neo4jGraphStore
        from mandol.infrastructure.config import Neo4jConfig

        cfg = Neo4jConfig(
            uri=settings.mandol_neo4j_uri,
            user=settings.mandol_neo4j_user,
            password=settings.mandol_neo4j_password,
            database=settings.mandol_neo4j_database,
        )
        return Neo4jGraphStore(config=cfg)

    def _build_milvus_unit_store(self, embedding_dim: int) -> Any:
        """构造 Milvus UnitStore（支持 milvus-lite 嵌入式，uri=file path）。"""
        from mandol.infrastructure.milvus_unit_store import MilvusUnitStore
        from mandol.infrastructure.config import MilvusConfig

        cfg = MilvusConfig(
            uri=settings.mandol_milvus_uri,
            user=settings.mandol_milvus_user,
            password=settings.mandol_milvus_password,
            db_name=settings.mandol_milvus_db,
            collection=settings.mandol_milvus_collection,
        )
        return MilvusUnitStore(
            config=cfg,
            embedding_dim=embedding_dim,
            auto_create_collection=True,
        )

    def _build_config(self) -> Any:
        """根据 settings 构建 MemorySystemConfig。"""
        from mandol import MemorySystemConfig

        return MemorySystemConfig(
            embedder_model=settings.mandol_embedder_model,
            embedder_device=settings.mandol_embedder_device,
            reranker_model=settings.mandol_reranker_model,
            reranker_device=settings.mandol_reranker_device,
            llm_model=settings.mandol_llm_model,
            embedder_dim=settings.mandol_embedder_dim,
            chunk_max_tokens=settings.mandol_chunk_max_tokens,
            session_time_gap_seconds=settings.mandol_session_time_gap_seconds,
            session_check_interval=settings.mandol_session_check_interval,
            session_max_pending=settings.mandol_session_max_pending,
            similarity_top_k=settings.mandol_similarity_top_k,
            similarity_threshold=settings.mandol_similarity_threshold,
            similarity_recent_window=settings.mandol_similarity_recent_window,
            bfs_expansion_per_seed=settings.mandol_bfs_expansion_per_seed,
            bfs_expansion_hops=settings.mandol_bfs_expansion_hops,
            max_context_units=settings.mandol_max_context_units,
            max_entities_per_llm=settings.mandol_max_entities_per_llm,
            max_events_per_llm=settings.mandol_max_events_per_llm,
            promote_threshold=settings.mandol_promote_threshold,
            use_unified_pipeline=settings.mandol_use_unified_pipeline,
            use_remote_embedder=settings.mandol_use_remote_embedder,
            use_remote_reranker=settings.mandol_use_remote_reranker,
            embedder_remote_base_url=settings.mandol_embedder_remote_base_url,
            embedder_remote_api_path=settings.mandol_embedder_remote_api_path,
            embedder_remote_timeout=settings.mandol_embedder_remote_timeout,
            reranker_remote_base_url=settings.mandol_reranker_remote_base_url,
            reranker_remote_api_path=settings.mandol_reranker_remote_api_path,
            reranker_remote_timeout=settings.mandol_reranker_remote_timeout,
        )

    def _build_llm_provider(self) -> Any:
        """根据 settings 构建 LLM provider，显式传入 api_key 和 base_url。"""
        from mandol.infrastructure.openai_compatible_llm_provider import OpenAICompatibleLLMProvider

        api_key = settings.mandol_llm_api_key or "ollama"
        base_url = settings.mandol_llm_base_url or "http://localhost:11434/v1"
        return OpenAICompatibleLLMProvider(
            model=settings.mandol_llm_model,
            api_key=api_key,
            base_url=base_url,
            timeout_s=300,
        )

    def reconfigure(self) -> bool:
        """重新配置并重建 MemorySystem（热重载）。"""
        with self._lock:
            self.shutdown()
            self._init_attempted = False
            self._system = None
            return self._ensure_initialized()

    def shutdown(self) -> None:
        """关闭并持久化状态。"""
        with self._lock:
            if self._system is None:
                return
            try:
                self.save()
            except Exception as exc:
                warn(f"Mandol 关闭时保存失败: {exc}")
            self._system = None
            self._init_attempted = False
            info("Mandol MemorySystem 已关闭")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def is_ready(self) -> bool:
        return self._system is not None

    @property
    def system(self):
        return self._system

    def _require(self):
        """要求系统已初始化，否则抛出异常。"""
        if not self._ensure_initialized():
            raise RuntimeError("Mandol 未启用或初始化失败")
        return self._system

    # ---------------- 文档同步 ----------------
    def add_text(
        self,
        uid: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        space_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """添加一条文本记忆到 MemorySystem。"""
        from mandol import MemoryUnit, Uid

        system = self._require()
        unit = MemoryUnit(
            uid=Uid(uid),
            raw_data={"text_content": text},
            metadata=metadata or {},
        )
        if space_name:
            system.semantic_map.create_space(space_name)
            system.semantic_map.add_unit(unit, space_names=[space_name], ensure_embedding=True)
        else:
            system.add(unit)
        return _unit_to_dict(unit)

    def add_many(
        self,
        items: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量添加文本记忆。

        每个 item 包含 uid、text、metadata（可选）、space_name（可选）。
        """
        from mandol import MemoryUnit, Uid

        system = self._require()
        units = []
        for it in items:
            unit = MemoryUnit(
                uid=Uid(it["uid"]),
                raw_data={"text_content": it["text"]},
                metadata=it.get("metadata", {}),
            )
            units.append(unit)
        system.add_many(units)
        # 可选地分配空间
        for it, unit in zip(items, units):
            sp = it.get("space_name")
            if sp:
                system.semantic_map.create_space(sp)
                system.semantic_map.add_unit_to_space(unit.uid, sp)
        return [_unit_to_dict(u) for u in units]

    def sync_document(
        self,
        rel_path: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """将文档内容同步为 Mandol 记忆单元。"""
        try:
            uid = f"doc:{rel_path}"
            self.add_text(uid, content, metadata={
                "type": "document",
                "source": "markdown_vault",
                "source_path": rel_path,
                **(metadata or {}),
            })
            info(f"已同步文档到 Mandol: {rel_path}")
            return True
        except Exception as exc:
            warn(f"同步文档到 Mandol 失败 {rel_path}: {exc}")
            return False

    def remove_unit(self, uid: str) -> bool:
        """删除一个记忆单元。"""
        from mandol import Uid
        system = self._require()
        try:
            system.semantic_map.delete_unit(Uid(uid))
            try:
                system.graph.delete_unit(Uid(uid))
            except Exception:
                pass
            return True
        except Exception as exc:
            warn(f"删除单元失败 {uid}: {exc}")
            return False

    def get_unit(self, uid: str) -> Optional[Dict[str, Any]]:
        """获取单个记忆单元。"""
        from mandol import Uid
        system = self._require()
        unit = system.semantic_map.get_unit(Uid(uid))
        return _unit_to_dict(unit) if unit else None

    def list_units(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出记忆单元。"""
        system = self._require()
        units = system.semantic_map.list_units()
        return [_unit_to_dict(u) for u in units[offset:offset + limit]]

    # ---------------- 高阶记忆构建 ----------------
    def build_high_level(self, mode: str = "auto") -> Dict[str, Any]:
        """触发高阶记忆构建（实体/事件抽取、摘要）。"""
        system = self._require()
        t0 = time.time()
        report = system.build_high_level(mode=mode)
        elapsed = time.time() - t0
        result = {
            "status": getattr(report, "status", "completed"),
            "mode": mode,
            "sessions_processed": getattr(report, "sessions_processed", 0),
            "units_processed": getattr(report, "units_processed", 0),
            "duration_seconds": round(elapsed, 3),
            "token_usage": self._safe_token_usage(report),
            "warnings": list(getattr(report, "warnings", []) or []),
            "error": getattr(report, "error_message", None),
        }
        info(f"高阶记忆构建完成: {result['status']}, "
             f"会话={result['sessions_processed']}, 单元={result['units_processed']}, "
             f"耗时={elapsed:.2f}s")
        return result

    def merge_cross_session_entities(self) -> Dict[str, Any]:
        """跨会话实体合并。"""
        system = self._require()
        t0 = time.time()
        system.merge_cross_session_entities()
        return {
            "status": "completed",
            "duration_seconds": round(time.time() - t0, 3),
        }

    def merge_cross_session_events(self) -> Dict[str, Any]:
        """跨会话事件合并。"""
        system = self._require()
        t0 = time.time()
        system.merge_cross_session_events()
        return {
            "status": "completed",
            "duration_seconds": round(time.time() - t0, 3),
        }

    # ---------------- 检索 ----------------
    def holistic_retrieve(
        self,
        query: str,
        top_k: int = 10,
        use_rerank: bool = True,
        skip_views: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """全记忆整体检索（自动处理四组、三路检索、RRF 融合、BFS 扩展、Rerank）。"""
        system = self._require()
        hits = system.holistic_retrieve(
            query,
            top_k=top_k,
            use_rerank=use_rerank,
            auto_build_if_empty=True,
            skip_views=skip_views,
        )
        return [_hit_to_dict(h) for h in hits]

    def retrieve_by_view(
        self,
        query: str,
        view: str,
        top_k: int = 10,
        use_rerank: bool = True,
    ) -> List[Dict[str, Any]]:
        """按语义视角检索（knowledge/entity_relation/event_causal 等）。"""
        system = self._require()
        hits = system.retrieve_by_view(
            query, view, top_k=top_k, use_rerank=use_rerank
        )
        return [_hit_to_dict(h) for h in hits]

    def retrieve_in_space(
        self,
        query: str,
        space_name: str,
        top_k: int = 10,
        use_rerank: bool = True,
    ) -> List[Dict[str, Any]]:
        """在指定空间范围内检索。"""
        system = self._require()
        hits = system.retrieve_in_space(
            query, space_name, top_k=top_k, use_rerank=use_rerank
        )
        return [_hit_to_dict(h) for h in hits]

    def search(
        self,
        query: str,
        top_k: int = 10,
        use_rerank: bool = True,
        skip_views: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """通用检索（等价于 holistic_retrieve）。"""
        system = self._require()
        hits = system.search(
            query,
            top_k=top_k,
            use_rerank=use_rerank,
            auto_build_if_empty=True,
            skip_views=skip_views,
        )
        return [_hit_to_dict(h) for h in hits]

    def search_by_text(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """纯向量文本检索（不含 rerank 与图扩展）。"""
        system = self._require()
        results = system.semantic_map.search_by_text(query, top_k=top_k)
        out = []
        for unit, score in results:
            d = _unit_to_dict(unit)
            d["score"] = float(score)
            out.append(d)
        return out

    # ---------------- 智能问答 ----------------
    def ask(
        self,
        query: str,
        top_k: int = 5,
        use_rerank: bool = True,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """基于记忆的智能问答，返回答案与检索命中。"""
        sys_obj = self._require()
        # 先检索命中
        hits = sys_obj.holistic_retrieve(
            query, top_k=top_k, use_rerank=use_rerank, auto_build_if_empty=True
        )
        hits_dicts = [_hit_to_dict(h) for h in hits]
        # 生成答案
        answer = sys_obj.ask_with_hits(
            query,
            hits,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return {
            "answer": answer,
            "hits": hits_dicts,
        }

    def ask_stream(
        self,
        query: str,
        top_k: int = 5,
        use_rerank: bool = True,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ):
        """流式问答生成器，yield ('hit', dict) 或 ('token', str) 或 ('done', dict)。"""
        sys_obj = self._require()
        hits = sys_obj.holistic_retrieve(
            query, top_k=top_k, use_rerank=use_rerank, auto_build_if_empty=True
        )
        for h in hits:
            yield ("hit", _hit_to_dict(h))
        # 使用 LLM 流式生成
        try:
            from mandol.ports.llm_provider import ChatMessage
            context_parts = []
            for i, h in enumerate(hits, 1):
                text = h.unit.raw_data.get("text_content", "")
                context_parts.append(f"[{i}] {text}")
            context = "\n\n".join(context_parts) if context_parts else "无相关记忆"
            prompt = f"基于以下记忆回答问题。\n\n记忆:\n{context}\n\n问题: {query}\n\n回答:"
            messages = []
            if system_prompt:
                messages.append(ChatMessage(role="system", content=system_prompt))
            messages.append(ChatMessage(role="user", content=prompt))
            full_text = ""
            for token in sys_obj.llm.chat_stream(
                messages,
                temperature=temperature,
                max_tokens=max_tokens or 1024,
            ):
                delta = token if isinstance(token, str) else getattr(token, "content", "")
                if delta:
                    full_text += delta
                    yield ("token", delta)
            yield ("done", {"answer": full_text})
        except Exception as exc:
            # 回退到非流式
            warn(f"流式生成失败，回退到非流式: {exc}")
            answer = sys_obj.ask(
                query, top_k=top_k, use_rerank=use_rerank,
                system_prompt=system_prompt, temperature=temperature,
                max_tokens=max_tokens,
            )
            yield ("token", answer)
            yield ("done", {"answer": answer})

    # ---------------- 空间管理 ----------------
    def _prune_dead_uids(self, system, sp) -> int:
        """清理空间 unit_uids 中已经不存在的 uid（幽灵引用）。

        当 MemoryUnit 被删除后，空间的 unit_uids 列表中可能仍然保留着
        旧 uid，造成 unit_count 与 /units 接口返回数量不一致。
        本方法会：
        1. 过滤掉 store 中不存在的 uid；
        2. 若发生删除则写回 store 并触发完整持久化（让下次启动也生效）。

        Returns:
            被移除的死引用数量。
        """
        if not sp.unit_uids:
            return 0
        store = system.semantic_map._store  # noqa: SLF001
        try:
            alive = [u for u in sp.unit_uids if store.get_unit(u) is not None]
        except Exception:
            return 0
        if len(alive) == len(sp.unit_uids):
            return 0
        dead = len(sp.unit_uids) - len(alive)
        sp.unit_uids = alive
        if hasattr(store, "upsert_spaces"):
            try:
                store.upsert_spaces([sp])
            except Exception:
                pass
        if hasattr(store, "flush"):
            try:
                store.flush()
            except Exception:
                pass
        # 触发完整持久化（写回原 snapshot.json 目录），下次启动也生效
        if hasattr(system, "save"):
            try:
                snapshot_path = (
                    Path(self._storage_root) / "snapshot.json"
                    if self._storage_root
                    else Path(settings.mandol_storage_dir) / "snapshot.json"
                )
                if snapshot_path.exists():
                    system.save(storage_path=str(snapshot_path))
                else:
                    system.save()
            except Exception:
                pass
        return dead

    def list_spaces(self, prune_ghost: bool = True) -> List[Dict[str, Any]]:
        """列出所有记忆空间。

        Args:
            prune_ghost: 是否在返回前自动清理空间中的死引用 unit_uids。
                默认为 True，可让 unit_count 与 /units 接口实际返回数量一致。
        """
        system = self._require()
        spaces = system.semantic_map.list_spaces()
        out = []
        for sp in spaces:
            if prune_ghost:
                self._prune_dead_uids(system, sp)
            # unit_count 使用递归总数（含子空间全部单元），
            # 与 /spaces/{name}/units（recursive=True）的展示保持一致
            recursive_count = self._count_units_recursive(system, sp)
            out.append({
                "name": str(sp.name),
                "unit_count": recursive_count,
                "child_spaces": [str(c) for c in sp.child_spaces],
                "summary": sp.summary_text,
                "metadata": sp.metadata,
            })
        return out

    def get_space(self, name: str, prune_ghost: bool = True) -> Optional[Dict[str, Any]]:
        """获取指定空间信息。

        Args:
            name: 空间名。
            prune_ghost: 是否在返回前自动清理空间中的死引用 unit_uids。
        """
        system = self._require()
        sp = system.semantic_map.get_space(name)
        if not sp:
            return None
        if prune_ghost:
            self._prune_dead_uids(system, sp)
        return {
            "name": str(sp.name),
            "unit_count": self._count_units_recursive(system, sp),
            "child_spaces": [str(c) for c in sp.child_spaces],
            "summary": sp.summary_text,
            "metadata": sp.metadata,
        }

    def _count_units_recursive(self, system, sp) -> int:
        """递归统计空间及其所有子空间下"实际存在"的单元数（去重）。"""
        try:
            units = system.semantic_map.get_units_in_spaces([str(sp.name)])
            return len(units)
        except Exception:
            return len(sp.unit_uids or [])

    def create_space(self, name: str) -> Dict[str, Any]:
        """创建记忆空间。"""
        system = self._require()
        sp = system.semantic_map.create_space(name)
        return {
            "name": str(sp.name),
            "unit_count": 0,
            "child_spaces": [],
        }

    def delete_space(self, name: str, cascade: bool = False) -> Dict[str, Any]:
        """删除记忆空间。"""
        system = self._require()
        system.semantic_map.delete_space(name, cascade=cascade)
        return {"name": name, "deleted": True, "cascade": cascade}

    def attach_child_space(self, parent: str, child: str) -> Dict[str, Any]:
        """挂载子空间。"""
        system = self._require()
        system.semantic_map.attach_child_space(parent, child, ensure_exists=True)
        return {"parent": parent, "child": child}

    def list_units_in_space(self, space_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """列出空间内的单元。"""
        from mandol import SpaceName
        system = self._require()
        units = system.semantic_map.get_units_in_spaces([space_name])
        return [_unit_to_dict(u) for u in units[:limit]]

    def add_unit_to_space(self, uid: str, space_name: str) -> Dict[str, Any]:
        """将单元添加到空间。"""
        from mandol import Uid
        system = self._require()
        system.semantic_map.add_unit_to_space(Uid(uid), space_name)
        return {"uid": uid, "space_name": space_name}

    def remove_unit_from_space(self, uid: str, space_name: str) -> Dict[str, Any]:
        """从空间移除单元（不删除单元本身）。

        SemanticMapService 没有 remove_unit_from_space，这里直接通过
        get_space 获取空间对象并调用 MemorySpace.remove_unit，
        然后写回 store 并触发完整持久化。
        """
        from mandol import Uid
        system = self._require()
        sp = system.semantic_map.get_space(space_name)
        if sp is None:
            raise KeyError(f"space not found: {space_name}")
        unit = system.semantic_map._store.get_unit(Uid(uid))  # noqa: SLF001
        if unit is None:
            raise KeyError(f"unit not found: {uid}")
        sp.remove_unit(uid)
        # 反向更新 unit.metadata["spaces"]
        try:
            spaces = list(unit.metadata.get("spaces", []) or [])
            if space_name in spaces:
                spaces = [s for s in spaces if s != space_name]
                if spaces:
                    unit.metadata["spaces"] = sorted(spaces)
                else:
                    unit.metadata.pop("spaces", None)
                unit.touch()
        except Exception:
            pass
        # 写回 store
        try:
            system.semantic_map._store.upsert_spaces([sp])  # noqa: SLF001
        except Exception:
            pass
        try:
            system.semantic_map._store.upsert_units([unit])  # noqa: SLF001
        except Exception:
            pass
        try:
            system.semantic_map._store.flush()  # noqa: SLF001
        except Exception:
            pass
        # 触发完整持久化（写回 snapshot.json）
        try:
            snapshot_path = (
                Path(self._storage_root) / "snapshot.json"
                if self._storage_root
                else Path(settings.mandol_storage_dir) / "snapshot.json"
            )
            if snapshot_path.exists():
                system.save(storage_path=str(snapshot_path))
            else:
                system.save()
        except Exception:
            pass
        return {"uid": uid, "space_name": space_name}

    # ---------------- 图谱操作 ----------------
    def add_relationship(
        self,
        source: str,
        target: str,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """添加关系边。"""
        system = self._require()
        system.graph.add_relationship(source, target, rel_type, **(properties or {}))
        return {"source": source, "target": target, "rel_type": rel_type}

    def get_relationship(
        self, source: str, target: str, rel_type: str
    ) -> Optional[Dict[str, Any]]:
        """查询关系。"""
        system = self._require()
        return system.graph.get_relationship(source, target, rel_type)

    def delete_relationship(
        self, source: str, target: str, rel_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """删除关系。"""
        system = self._require()
        system.graph.delete_relationship(source, target, rel_type)
        return {"source": source, "target": target, "rel_type": rel_type, "deleted": True}

    def list_relationships(self, uid: str, direction: str = "all") -> List[Dict[str, Any]]:
        """列出某单元的所有关系。"""
        from mandol import Uid
        system = self._require()
        edges = system.graph.get_edges_of_unit(Uid(uid), direction=direction)
        return [
            {
                "source": str(e.get("source", "")),
                "target": str(e.get("target", "")),
                "rel_type": e.get("rel_type") or e.get("relationship", ""),
                "properties": e.get("properties", {}),
            }
            for e in edges
        ]

    def get_explicit_neighbors(
        self, uid: str, rel_type: Optional[str] = None, direction: str = "out"
    ) -> List[Dict[str, Any]]:
        """获取显式邻居。"""
        from mandol import Uid
        system = self._require()
        units = system.graph.get_explicit_neighbors(
            [Uid(uid)], rel_type=rel_type, direction=direction
        )
        return [_unit_to_dict(u) for u in units]

    def get_implicit_neighbors(self, uid: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """获取隐式语义邻居。"""
        from mandol import Uid
        system = self._require()
        results = system.graph.get_implicit_neighbors([Uid(uid)], top_k=top_k)
        out = []
        for unit, score in results:
            d = _unit_to_dict(unit)
            d["score"] = float(score)
            out.append(d)
        return out

    def bfs_expand(
        self,
        seed_uids: List[str],
        per_seed: int = 3,
        hops: int = 1,
        rel_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """BFS 图扩展。"""
        from mandol import Uid
        system = self._require()
        # 获取种子单元
        seeds = []
        for uid in seed_uids:
            u = system.semantic_map.get_unit(Uid(uid))
            if u:
                seeds.append(u)
        if not seeds:
            return []
        units = system.graph.bfs_expand_units(
            seeds, per_seed=per_seed, hops=hops, rel_type=rel_type
        )
        return [_unit_to_dict(u) for u in units]

    def get_entity_subgraph(
        self, query: str, max_depth: int = 2, top_k: int = 10
    ) -> Dict[str, Any]:
        """获取实体子图。"""
        system = self._require()
        result = system.graph.retrieve_entity_subgraph(
            query, max_depth=max_depth, top_k=top_k
        )
        return self._subgraph_result_to_dict(result)

    def trace_evidence(self, uid: str, max_depth: int = 2, top_k: int = 10) -> Dict[str, Any]:
        """溯源链追踪。"""
        from mandol import Uid
        system = self._require()
        result = system.graph.trace_evidence(Uid(uid), max_depth=max_depth, top_k=top_k)
        return self._evidence_result_to_dict(result)

    def trace_coref(self, uid: str, max_depth: int = 2, top_k: int = 10) -> Dict[str, Any]:
        """共指链追踪。"""
        from mandol import Uid
        system = self._require()
        result = system.graph.trace_coref(Uid(uid), max_depth=max_depth, top_k=top_k)
        return self._coref_result_to_dict(result)

    def search_graph_relations(
        self,
        seed_nodes: Optional[List[str]] = None,
        relation_types: Optional[List[str]] = None,
        max_depth: int = 2,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """搜索图关系。"""
        system = self._require()
        results = system.graph.search_graph_relations(
            seed_nodes=seed_nodes,
            relation_types=relation_types,
            max_depth=max_depth,
            limit=limit,
        )
        return [
            {
                "source": str(s),
                "target": str(t),
                "properties": p,
            }
            for s, t, p in results
        ]

    # ---------------- 统计与监控 ----------------
    def get_stats(self) -> Dict[str, Any]:
        """获取 Mandol 记忆系统统计。"""
        if not self._ensure_initialized():
            return {"enabled": False}
        system = self._system
        try:
            sm = system.semantic_map
            all_units = sm.list_units()
            all_spaces = sm.list_spaces()
            # 按空间类型统计
            from mandol.application.legacy.multidim_semantic_graph import SpaceNamingPolicy
            naming = SpaceNamingPolicy()
            root = system._root if hasattr(system, "_root") else "root"
            counts = {}
            for label, fn in [
                ("base_memory", naming.base_memory),
                ("knowledge_entity", naming.knowledge_entity),
                ("episodic_event", naming.episodic_event),
                ("episodic_summary", naming.episodic_summary),
            ]:
                try:
                    sp = fn(root)
                    units = sm.get_units_in_spaces([sp])
                    counts[label] = len(units)
                except Exception:
                    counts[label] = 0
            token_usage = self._safe_get_token_usage()
            return {
                "enabled": True,
                "total_units": len(all_units),
                "total_spaces": len(all_spaces),
                "base_memory_count": counts.get("base_memory", 0),
                "entity_count": counts.get("knowledge_entity", 0),
                "event_count": counts.get("episodic_event", 0),
                "summary_count": counts.get("episodic_summary", 0),
                "token_usage": token_usage,
                "dirty": bool(getattr(system, "dirty", False)),
            }
        except Exception as exc:
            warn(f"获取 Mandol 统计失败: {exc}")
            return {"enabled": True, "error": str(exc)}

    def get_monitor(self) -> Dict[str, Any]:
        """获取监控信息。"""
        if not self._ensure_initialized():
            return {"enabled": False}
        system = self._system
        try:
            monitor = getattr(system, "monitor", None)
            if monitor is not None:
                return {"enabled": True, "monitor": str(monitor)}
            return {"enabled": True, "monitor": ""}
        except Exception as exc:
            return {"enabled": True, "error": str(exc)}

    # ---------------- 持久化 ----------------
    def save(self, storage_path: Optional[str] = None, wait: bool = False) -> Dict[str, Any]:
        """持久化记忆系统。

        为了避免大规模 snapshot 写入阻塞 API 请求，默认采用后台线程异步
        写入，立即返回。传入 ``wait=True`` 时同步等待。
        """
        if self._save_in_progress.is_set() and not wait:
            return {
                "status": "busy",
                "message": "snapshot 保存进行中",
                "path": str(storage_path or (Path(self._storage_root or settings.mandol_storage_dir) / "snapshot.json")),
            }

        system = self._require()
        path = storage_path or str(Path(self._storage_root or settings.mandol_storage_dir) / "snapshot.json")

        def _do_save() -> None:
            self._save_in_progress.set()
            try:
                t0 = time.time()
                result = system.save(path)
                self._last_save_result = {
                    "status": "saved",
                    "path": path,
                    "units": getattr(result, "units", 0) if result else 0,
                    "spaces": getattr(result, "spaces", 0) if result else 0,
                    "duration_seconds": round(time.time() - t0, 3),
                    "saved_at": datetime.utcnow().isoformat(timespec="seconds"),
                }
                info(f"Mandol 记忆已异步保存到 {path}, 耗时={self._last_save_result['duration_seconds']}s")
            except Exception as exc:
                self._last_save_result = {
                    "status": "failed",
                    "error": str(exc),
                    "path": path,
                }
                warn(f"异步保存失败: {exc}")
            finally:
                self._save_in_progress.clear()

        if wait:
            _do_save()
            return self._last_save_result or {"status": "saved", "path": path}
        else:
            threading.Thread(target=_do_save, daemon=True).start()
            return {"status": "pending", "path": path}

    def save_status(self) -> Dict[str, Any]:
        """查询最近一次 snapshot 保存状态。"""
        return {
            "in_progress": self._save_in_progress.is_set(),
            "last_result": self._last_save_result,
        }

    # ---------------- 外部存储状态 ----------------
    def external_store_status(self) -> Dict[str, Any]:
        """查询 Neo4j + Milvus 实际状态（节点/边/集合统计）。"""
        status: Dict[str, Any] = {
            "neo4j": {"available": False, "nodes": 0, "edges": 0, "rel_types": []},
            "milvus": {"available": False, "uri": settings.mandol_milvus_uri, "collection": settings.mandol_milvus_collection, "unit_count": 0},
            "snapshot": {"path": str(Path(self._storage_root or settings.mandol_storage_dir) / "snapshot.json"), "exists": False, "size_bytes": 0},
        }
        # Neo4j
        try:
            from neo4j import GraphDatabase
            d = GraphDatabase.driver(
                settings.mandol_neo4j_uri,
                auth=(settings.mandol_neo4j_user, settings.mandol_neo4j_password),
            )
            with d.session(database=settings.mandol_neo4j_database) as s:
                status["neo4j"]["nodes"] = s.run("MATCH (n) RETURN count(n) as c").single()["c"]
                status["neo4j"]["edges"] = s.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
                status["neo4j"]["rel_types"] = [r["relationshipType"] for r in s.run("CALL db.relationshipTypes()")]
            d.close()
            status["neo4j"]["available"] = True
        except Exception as exc:
            status["neo4j"]["error"] = str(exc)
        # Milvus
        try:
            from pymilvus import MilvusClient
            client = MilvusClient(uri=settings.mandol_milvus_uri)
            if client.has_collection(settings.mandol_milvus_collection):
                status["milvus"]["unit_count"] = client.get_collection_stats(settings.mandol_milvus_collection).get("row_count", 0)
                status["milvus"]["available"] = True
            client.close()
        except Exception as exc:
            status["milvus"]["error"] = str(exc)
        # Snapshot
        snap = Path(status["snapshot"]["path"])
        if snap.exists():
            status["snapshot"]["exists"] = True
            status["snapshot"]["size_bytes"] = snap.stat().st_size
        return status

    def load(self, storage_path: str) -> Dict[str, Any]:
        """从路径加载记忆系统。"""
        from mandol import MemorySystem
        with self._lock:
            self._system = MemorySystem.load(storage_path)
            self._storage_root = str(Path(storage_path).parent)
            info(f"已从 {storage_path} 加载 Mandol 记忆系统")
            return {"status": "loaded", "path": storage_path}

    def flush(self) -> Dict[str, Any]:
        """刷新缓存。"""
        system = self._require()
        try:
            system.flush()
        except Exception:
            pass
        return {"status": "flushed"}

    # ---------------- 辅助 ----------------
    def _safe_token_usage(self, report) -> Dict[str, int]:
        try:
            return dict(getattr(report, "token_usage", {}) or {})
        except Exception:
            return {}

    def _safe_get_token_usage(self) -> Dict[str, int]:
        try:
            return dict(self._system.get_token_usage() or {})
        except Exception:
            return {}

    def _subgraph_result_to_dict(self, result) -> Dict[str, Any]:
        """转换实体子图结果。"""
        out = {"nodes": [], "edges": [], "entities": [], "events": []}
        for attr in ["nodes", "edges", "entities", "events"]:
            val = getattr(result, attr, None)
            if val is None:
                continue
            if isinstance(val, list):
                out[attr] = [
                    _unit_to_dict(x) if hasattr(x, "uid") else (
                        dict(x) if hasattr(x, "__dict__") else str(x)
                    )
                    for x in val
                ]
            else:
                out[attr] = str(val)
        return out

    def _evidence_result_to_dict(self, result) -> Dict[str, Any]:
        out = {"chain": [], "summary": None}
        for attr in ["chain", "summary", "evidence", "entities", "events"]:
            val = getattr(result, attr, None)
            if val is None:
                continue
            if isinstance(val, list):
                out[attr] = [
                    _unit_to_dict(x) if hasattr(x, "uid") else (
                        dict(x) if hasattr(x, "__dict__") else str(x)
                    )
                    for x in val
                ]
            else:
                out[attr] = _unit_to_dict(val) if hasattr(val, "uid") else str(val)
        return out

    def _coref_result_to_dict(self, result) -> Dict[str, Any]:
        out = {"chain": [], "corefs": []}
        for attr in ["chain", "corefs", "entities", "traces"]:
            val = getattr(result, attr, None)
            if val is None:
                continue
            if isinstance(val, list):
                out[attr] = [
                    _unit_to_dict(x) if hasattr(x, "uid") else (
                        dict(x) if hasattr(x, "__dict__") else str(x)
                    )
                    for x in val
                ]
            else:
                out[attr] = str(val)
        return out


# 全局单例
mandol_service = MandolService()
