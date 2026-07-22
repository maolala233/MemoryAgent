"""Mandol MemorySystem 适配服务。

基于真实 mandol 0.1.0 API，封装 MemorySystem 的生命周期、文档同步、
多视图检索、图谱操作、高阶记忆构建、智能问答与持久化能力，
作为前端与 mandol 底层能力之间的桥梁。
"""
from __future__ import annotations

import logging
import os
import threading
import time
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..config.settings import settings
from ..utils.logger import info, warn

# Milvus Lite 在 milvus.db 上加文件锁（fcntl.flock），同进程内多客户端会冲突。
# 进程级单例锁 + MandolService._milvus_client 单例字段，保证 status 查询与
# Mandol 内部 UnitStore 不会相互阻塞。
_MILVUS_CLIENT_LOCK = threading.Lock()

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


def _unit_to_dict(unit, space_name: Optional[str] = None) -> Dict[str, Any]:
    """将 MemoryUnit 转换为可序列化字典。"""
    return {
        "uid": str(unit.uid),
        "raw_data": unit.raw_data,
        "metadata": unit.metadata,
        "text": unit.raw_data.get("text_content", ""),
        "space_name": space_name,
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
        # 高阶构建状态：供前端轮询 (后端 /api/mandol/build-status)
        self._build_in_progress = threading.Event()
        self._build_progress_message: str = ""
        self._build_started_at: float = 0.0
        self._build_finished_at: float = 0.0
        self._last_build_result: Optional[Dict[str, Any]] = None
        # 仪表盘缓存：避免每次刷新都触发 list_units() / Neo4j count / Milvus 探测
        self._stats_cache: Optional[Dict[str, Any]] = None
        self._stats_cache_ts: float = 0.0
        # === 跨会话 token 累计 (持久化到 token_usage.json) ===
        # 区分 build / chat, 既能监控构建期抽取的开销,也能监控在线问答的消耗。
        # 关键：内存里累计 → save 时持久化 → 重启后从文件恢复, 避免每次启动清零。
        self._cumulative_token_usage: Dict[str, Dict[str, int]] = {
            "build": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "chat": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "total": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        self._token_usage_lock = threading.RLock()
        self._token_usage_file: Optional[Path] = None
        # build_high_level 完成后, 用它与 get_token_usage() 当前值做差分,
        # 避免把同一份 token 累加多次
        self._last_build_baseline: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }
        self._external_cache: Optional[Dict[str, Any]] = None
        self._external_cache_ts: float = 0.0
        self._spaces_cache: Optional[List[Dict[str, Any]]] = None
        self._spaces_cache_ts: float = 0.0

    # 进程内单例：MilvusUnitStore 持有 milvus.db 的 fcntl 锁，重复创建会冲突
    _unit_store: Optional[Any] = None

    # 空间列表缓存 TTL（秒）：list_spaces 需要遍历所有空间并 prune/统计，
    # 即便优化后仍要打多次 Milvus/Neo4j。短 TTL 即可显著降低重复点击
    # /api/mandol/spaces 造成的开销，同时保证数据不会太陈旧。
    _SPACES_CACHE_TTL: float = 5.0

    # 缓存 TTL（秒）：仪表盘刷新频繁时仍能保证 5s 内一致
    _STATS_CACHE_TTL: float = 5.0
    _EXTERNAL_CACHE_TTL: float = 10.0

    def _invalidate_dashboard_caches(self) -> None:
        """数据变更时清除仪表盘缓存。"""
        self._stats_cache = None
        self._stats_cache_ts = 0.0
        self._external_cache = None
        self._external_cache_ts = 0.0

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

        # 尝试从已有快照加载，否则新建。兼容旧版本 bug: 如果 snapshot
        # 是空的但外部 UnitStore(Milvus) 里还有数据，跳过空快照，避免 load
        # 时 reset_state() 先清掉可恢复的 Milvus 数据。
        snapshot_file = Path(storage_root) / "snapshot.json"
        should_load_snapshot = snapshot_file.exists()
        if should_load_snapshot and unit_store is not None:
            try:
                unit_count_in_snapshot = self._snapshot_unit_count(snapshot_file)
                unit_count_in_store = len(unit_store.list_units() or [])
                if unit_count_in_snapshot == 0 and unit_count_in_store > 0:
                    should_load_snapshot = False
                    warn(
                        f"检测到空 snapshot 但 Milvus 中有 {unit_count_in_store} 条 unit，"
                        "跳过 snapshot 加载并从外部存储恢复"
                    )
            except Exception as exc:
                warn(f"检查 snapshot/Milvus 状态失败，继续按 snapshot 加载: {exc}")

        if should_load_snapshot:
            try:
                self._system = MemorySystem.load(
                    str(snapshot_file),
                    llm_provider=llm_provider,
                    graph_store=graph_store,
                    unit_store=unit_store,
                )
                info(f"已从快照加载 Mandol MemorySystem: {snapshot_file}")
                # 加载完后,验证外部后端是否就位(防止被 fallback 到 InMemory 后又误传 Neo4j/Milvus)
                if graph_store is not None:
                    info(f"  图后端: {type(self._system._graph_store).__name__}")
                if unit_store is not None:
                    _us = getattr(self._system, "_unit_store", None)
                    if _us is None:
                        _us = getattr(getattr(self._system, "_semantic_map", None), "_store", None)
                    if _us is not None:
                        info(f"  单元后端: {type(_us).__name__}")
                    else:
                        info("  单元后端: (unknown)")
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

        # === 兜底: 从 unit metadata 反向重建 space 注册表 ===
        # Mandol 用 MilvusUnitStore, 其 _spaces 只在内存 dict 不持久化;
        # 重启或回退后, list_spaces() 返回空, get_units_in_spaces() 拿不到任何 unit,
        # 导致 holistic 检索 0 命中. 这里从 unit.metadata["spaces"] 重建 _spaces.
        try:
            n = self.rebuild_spaces_from_units()
            if n:
                info(f"已从 unit metadata 重建 {n} 个 space 关联")
        except Exception as exc:
            warn(f"重建 space 关联失败: {exc}")

        # 加载跨会话 token 累计 (build / chat / total), 持久化到 token_usage.json
        # 关键: 不能放在 _ensure_initialized 前面, 因为 _token_usage_path 需要
        # storage_root, 而 storage_root 在 _do_initialize 末尾才确定。
        self._load_cumulative_token_usage()

        return True

    def _snapshot_unit_count(self, snapshot_path: Path) -> int:
        """Return persisted unit count from a Mandol snapshot directory/file."""
        units_path = snapshot_path / "data" / "units.json"
        if not units_path.exists():
            return 0
        try:
            payload = json.loads(units_path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            return 0
        units = payload.get("units") or []
        return len(units) if isinstance(units, list) else 0

    def rebuild_spaces_from_units(self) -> int:
        """从 unit.metadata["spaces"] 反向重建 MilvusUnitStore._spaces 注册表。

        Returns:
            重建的 (space, unit) 关联数量。
        """
        from mandol import SpaceName, Uid

        system = self._require()
        store = system.semantic_map._store  # noqa: SLF001
        all_units = system.semantic_map.list_units()
        if not all_units:
            return 0

        # 收集 (space_name, uid) 关系, 同一个 (space, uid) 只写一次
        # 避免重复 add_unit 触发 MemorySpace 内部 set 报错
        pairs: set[tuple[str, str]] = set()
        spaces_index: dict[str, set[str]] = {}
        for u in all_units:
            raw_spaces = (u.metadata or {}).get("spaces", []) or []
            if isinstance(raw_spaces, str):
                raw_spaces = [raw_spaces]
            for sname in raw_spaces:
                sname = str(sname)
                uid = str(u.uid)
                if (sname, uid) in pairs:
                    continue
                pairs.add((sname, uid))
                spaces_index.setdefault(sname, set()).add(uid)

        if not spaces_index:
            return 0

        # 按 space_name 创建 MemorySpace 并填充 unit_uids
        for sname, uids in spaces_index.items():
            existing = store.get_space(SpaceName(sname))
            if existing is None:
                space = system.semantic_map.create_space(sname)
            else:
                space = existing
            for uid in uids:
                try:
                    space.add_unit(Uid(uid))
                except Exception:
                    # 重复添加时 set 已存在, 静默跳过
                    pass
            store.upsert_spaces([space])

        # 重建 faiss 向量索引 (从 unit.embedding 重新装载)
        # 否则 _index.search() 拿不到任何结果, 即使 candidate 集不为空
        try:
            system.semantic_map.rebuild_index_from_store()
            info("rebuild_spaces_from_units: faiss index 已重建")
        except Exception as exc:
            warn(f"重建 faiss index 失败: {exc}")

        info(f"rebuild_spaces_from_units: 重建 {len(spaces_index)} 个 space, 共 {len(pairs)} 条 unit 关联")
        return len(pairs)


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
        """构造 Milvus UnitStore（支持 milvus-lite 嵌入式，uri=file path 或远程 server）。

        进程内单例缓存 — 避免 reset / reload 时多次实例化导致 fcntl 锁冲突。
        """
        if MandolService._unit_store is not None:
            return MandolService._unit_store
        from mandol.infrastructure.milvus_unit_store import MilvusUnitStore
        from mandol.infrastructure.config import MilvusConfig

        uri = settings.mandol_milvus_uri
        # 关闭远程时回退到嵌入式
        if not settings.mandol_milvus_remote_enabled:
            local_path = Path("data/mandol/milvus.db")
            local_path.parent.mkdir(parents=True, exist_ok=True)
            uri = str(local_path)

        cfg = MilvusConfig(
            uri=uri,
            user=settings.mandol_milvus_user,
            password=settings.mandol_milvus_password,
            db_name=settings.mandol_milvus_db,
            collection=settings.mandol_milvus_collection,
        )
        store = MilvusUnitStore(
            config=cfg,
            embedding_dim=embedding_dim,
            auto_create_collection=True,
        )
        MandolService._unit_store = store
        return store

    def _build_config(self) -> Any:
        """根据 settings 构建 MemorySystemConfig。"""
        from mandol import MemorySystemConfig

        # 决定 embedder / reranker 实际使用的模型标识：
        # 优先使用本地路径，否则使用远端/默认模型名
        embedder_id = settings.mandol_embedder_local_path or settings.mandol_embedder_model
        reranker_id = settings.mandol_reranker_local_path or settings.mandol_reranker_model

        # 设置 HuggingFace 离线环境变量（仅当开启 offline_only 时）
        import os
        if settings.mandol_embedder_offline_only or settings.mandol_reranker_offline_only or settings.hf_offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

        return MemorySystemConfig(
            embedder_model=embedder_id,
            embedder_device=settings.mandol_embedder_device,
            reranker_model=reranker_id,
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
        """根据 settings 构建 LLM provider，显式传入 api_key 和 base_url。

        LLM_TIMEOUT_S 环境变量可临时覆盖默认 300s 超时（用于长上下文/慢模型）。
        """
        from mandol.infrastructure.openai_compatible_llm_provider import OpenAICompatibleLLMProvider
        import os

        api_key = settings.mandol_llm_api_key or "ollama"
        base_url = settings.mandol_llm_base_url or "http://localhost:11434/v1"
        # LLM_TIMEOUT_S 环境变量优先：默认 300s；用户可临时拉大到 600/900
        try:
            timeout_s = int(os.getenv("LLM_TIMEOUT_S", "300"))
        except (TypeError, ValueError):
            timeout_s = 300
        return OpenAICompatibleLLMProvider(
            model=settings.mandol_llm_model,
            api_key=api_key,
            base_url=base_url,
            timeout_s=timeout_s,
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
            if self._system is None and MandolService._unit_store is None:
                return
            try:
                self.save()
            except Exception as exc:
                warn(f"Mandol 关闭时保存失败: {exc}")
            self._system = None
            self._init_attempted = False
            # 释放 Milvus UnitStore 单例，否则下次 initialize 重建时会因
            # 旧 fcntl 锁未释放而 DataDirLockedError
            MandolService._unit_store = None
            MandolService._milvus_client = None
            info("Mandol MemorySystem 已关闭")

    def clear_all(self, reinit: bool = False) -> Dict[str, Any]:
        """清空所有 Mandol 记忆数据：Neo4j 图 + Milvus 向量 + 本地快照 + 内存状态。

        用于在 prompt/embedding 等重大变更后彻底重建。完成后调用方需重新 ingest + build。
        返回清空统计 + 重建后空系统状态(仅当 reinit=True 时包含 system_reinitialized)。

        reinit=False 时不重建空系统,避免 30+ 秒的同步阻塞(前端会卡住);
        下次访问 Mandol 时会懒加载重新初始化。
        """
        import shutil

        with self._lock:
            stats: Dict[str, Any] = {
                "neo4j_cleared": 0,
                "milvus_cleared": 0,
                "persistence_cleared": False,
                "system_reinitialized": False,
            }
            if not self._ensure_initialized():
                return {"error": "Mandol 未启用或未初始化", **stats}

            # 0) 关键: 先释放系统对象(并关闭其 Milvus 单例),
            #    否则快照目录可能仍被句柄持有, 导致后续 rmtree 失败.
            try:
                self._system = None
                self._init_attempted = False
                MandolService._unit_store = None
                MandolService._milvus_client = None
            except Exception:
                pass

            # 1) 清空 Neo4j 图(节点 + 关系)
            try:
                # 通过本地驱动直连, 绕开已释放的 in-memory store
                from neo4j import GraphDatabase
                from backend.config.settings import settings as _s
                driver = GraphDatabase.driver(
                    _s.mandol_neo4j_uri, auth=(_s.mandol_neo4j_user, _s.mandol_neo4j_password)
                )
                with driver.session(database=_s.mandol_neo4j_database) as session:
                    result = session.run("MATCH (n) DETACH DELETE n RETURN count(n) AS c")
                    cnt = result.single()["c"]
                driver.close()
                stats["neo4j_cleared"] = int(cnt)
                info(f"✓ Neo4j 节点 + 关系已清空 ({cnt} 节点)")
            except Exception as exc:
                warn(f"清空 Neo4j 失败: {exc}")
                stats["neo4j_error"] = str(exc)

            # 2) 清空 Milvus 向量集合(直连)
            try:
                from pymilvus import MilvusClient
                from backend.config.settings import settings as _s
                _client = MilvusClient(uri=_s.mandol_milvus_uri)
                coll = _s.mandol_milvus_collection
                if _client.has_collection(coll):
                    _client.drop_collection(coll)
                _client.close()
                stats["milvus_cleared"] = 1
                info(f"✓ Milvus 集合 {coll} 已 drop")
            except Exception as exc:
                warn(f"清空 Milvus 失败: {exc}")
                stats["milvus_error"] = str(exc)

            # 3) 删除本地全部持久化文件 + 目录
            #    注意: Mandol 实际把 snapshot.json 当作「目录」使用
            #         (snapshot.json/{config,manifest,data,state}.json),
            #         老代码用 p.is_file() + p.unlink() 会全部静默失败,
            #         导致 data/mandol/snapshot.json/data/{graph,units,...}.json
            #         残留 → 重新 init 时被 _do_initialize 加载,「清空后还在」。
            try:
                storage_root = Path(self._storage_root or settings.mandol_storage_dir)
                if not storage_root.exists():
                    storage_root.mkdir(parents=True, exist_ok=True)

                # 3a) 顶层：snapshot.json (是目录!) + 其他顶层 json / .bak / .tmp
                for name in [
                    "snapshot.json", "snapshot.json.tmp", "snapshot.json.bak",
                    "manifest.json", "token_usage.json",
                ]:
                    p = storage_root / name
                    if p.is_file():
                        p.unlink()
                    elif p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)

                # 3b) data/ 子目录（含 graph / sessions / units / spaces）
                data_dir = storage_root / "data"
                if data_dir.is_dir():
                    shutil.rmtree(data_dir, ignore_errors=True)

                # 3c) state/ 子目录（processed_state.json）
                state_dir = storage_root / "state"
                if state_dir.is_dir():
                    shutil.rmtree(state_dir, ignore_errors=True)

                # 3d) 兜底: 任何遗留的 *.json / *.bak / *.tmp 都清掉
                for pattern in ("*.json", "*.bak", "*.tmp"):
                    for p in storage_root.glob(pattern):
                        try:
                            if p.is_file():
                                p.unlink()
                            elif p.is_dir():
                                shutil.rmtree(p, ignore_errors=True)
                        except Exception:
                            pass

                stats["persistence_cleared"] = True
                info(f"✓ 持久化已删除: {storage_root}")
            except Exception as exc:
                warn(f"删除持久化失败: {exc}")
                stats["persistence_error"] = str(exc)

            # 4) 可选: 重新初始化为空系统(默认关闭,避免 30+ 秒同步阻塞)
            if reinit:
                try:
                    self._invalidate_dashboard_caches()
                    ok = self._do_initialize()
                    stats["system_reinitialized"] = ok
                    if ok:
                        info("✓ Mandol 已重新初始化为空系统")
                except Exception as exc:
                    warn(f"重新初始化失败: {exc}")
                    stats["reinit_error"] = str(exc)

            return stats

    # ─── 清空任务后台状态(供 /clear-status 轮询) ─────────────────────
    _clear_state: Dict[str, Any] = {
        "status": "idle",        # idle | running | completed | failed
        "started_at": None,
        "finished_at": None,
        "elapsed_seconds": 0.0,
        "message": "",
        "result": None,
    }
    _clear_lock = threading.Lock()

    def clear_status(self) -> Dict[str, Any]:
        """返回当前清空任务的状态(供前端轮询)。"""
        with self._clear_lock:
            state = dict(self._clear_state)
            if state["status"] == "running" and state["started_at"]:
                state["elapsed_seconds"] = round(
                    time.time() - float(state["started_at"]), 1
                )
            return state

    def clear_all_async(self) -> Dict[str, Any]:
        """异步触发清空, 立即返回当前状态(实际工作在后台线程跑)。

        修复: 同步 clear_everything 在 reinit 时会被 _do_initialize 阻塞
        30+ 秒, 前端一直转圈像卡死。改为后台线程 + 状态轮询。
        """
        if not self._enabled:
            return {"error": "Mandol 未启用"}
        with self._clear_lock:
            if self._clear_state["status"] == "running":
                return dict(self._clear_state)
            self._clear_state = {
                "status": "running",
                "started_at": time.time(),
                "finished_at": None,
                "elapsed_seconds": 0.0,
                "message": "正在清空 Mandol + Neo4j + Milvus + 本地快照…",
                "result": None,
            }

        def _runner() -> None:
            try:
                # 1) 清空 Mandol + Neo4j + Milvus + 全部持久化文件
                result = self.clear_all(reinit=False)
                if result.get("error"):
                    raise RuntimeError(result["error"])

                # 2) 删除基础记忆文件 + 剥离 summary
                fs_stats: Dict[str, Any] = {"files_removed": 0, "summary_stripped": 0, "errors": []}
                try:
                    import shutil
                    import re
                    vault_imports = settings.vault_dir / "imports"
                    if vault_imports.is_dir():
                        for child in list(vault_imports.iterdir()):
                            try:
                                if child.is_dir():
                                    shutil.rmtree(child, ignore_errors=True)
                                    fs_stats["files_removed"] += 1
                                elif child.is_file():
                                    child.unlink()
                                    fs_stats["files_removed"] += 1
                            except Exception as exc:  # noqa: BLE001
                                fs_stats["errors"].append(f"{child}: {exc}")
                    for md_file in settings.vault_dir.rglob("*.md"):
                        try:
                            text = md_file.read_text(encoding="utf-8")
                            if text.startswith("---"):
                                new_text = re.sub(
                                    r"^summary:\s*.*?\n",
                                    "",
                                    text,
                                    count=1,
                                    flags=re.MULTILINE,
                                )
                                if new_text != text:
                                    md_file.write_text(new_text, encoding="utf-8")
                                    fs_stats["summary_stripped"] += 1
                        except Exception as exc:  # noqa: BLE001
                            fs_stats["errors"].append(f"strip {md_file}: {exc}")
                except Exception as exc:  # noqa: BLE001
                    fs_stats["errors"].append(str(exc))

                result["file_system"] = fs_stats

                # 3) 删除原始上传文件 + SQLite 记忆数据库
                extra_stats: Dict[str, Any] = {"uploads_removed": 0, "db_removed": False, "errors": []}
                try:
                    data_root = Path(settings.vault_dir).parent  # 即 data/
                    uploads_dir = data_root / "uploads"
                    if uploads_dir.is_dir():
                        for child in list(uploads_dir.iterdir()):
                            try:
                                if child.is_file():
                                    child.unlink()
                                    extra_stats["uploads_removed"] += 1
                                elif child.is_dir():
                                    shutil.rmtree(child, ignore_errors=True)
                                    extra_stats["uploads_removed"] += 1
                            except Exception as exc:  # noqa: BLE001
                                extra_stats["errors"].append(f"upload {child}: {exc}")
                    for db_name in ("memory.db", "memory.db-journal", "memory.db-wal", "memory.db-shm"):
                        dbp = data_root / db_name
                        if dbp.is_file():
                            try:
                                dbp.unlink()
                                extra_stats["db_removed"] = True
                            except Exception as exc:  # noqa: BLE001
                                extra_stats["errors"].append(f"db {dbp}: {exc}")
                except Exception as exc:  # noqa: BLE001
                    extra_stats["errors"].append(str(exc))

                result["file_system"].update(extra_stats)

                # 4) 立即失效仪表盘缓存, 下次刷新拿真实空状态
                self._invalidate_dashboard_caches()

                with self._clear_lock:
                    self._clear_state.update({
                        "status": "completed",
                        "finished_at": time.time(),
                        "elapsed_seconds": round(time.time() - float(self._clear_state["started_at"]), 1),
                        "message": (
                            f"清空完成: neo4j={result.get('neo4j_cleared', 0)} "
                            f"milvus={result.get('milvus_cleared', 0)} "
                            f"files_removed={fs_stats['files_removed']} "
                            f"uploads_removed={extra_stats['uploads_removed']} "
                            f"summary_stripped={fs_stats['summary_stripped']}"
                        ),
                        "result": result,
                    })
                info(f"✓ 清空全部完成: {self._clear_state['message']}")
            except Exception as exc:
                logger.exception("clear_all_async failed")
                with self._clear_lock:
                    self._clear_state.update({
                        "status": "failed",
                        "finished_at": time.time(),
                        "elapsed_seconds": round(
                            time.time() - float(self._clear_state["started_at"]), 1
                        ),
                        "message": f"清空失败: {exc}",
                    })

        threading.Thread(target=_runner, daemon=True, name="mandol-clear").start()
        return self.clear_status()

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def is_ready(self) -> bool:
        return self._system is not None

    @property
    def system(self):
        return self._system

    def warmup(self) -> bool:
        """启动期预热：强制完成底层 MemorySystem 初始化（同步加载模型/快照）。

        目的：避免 /api/chat/stream 首请求时阻塞事件循环（导致 SSE 5s+ 延迟，
        Next.js 代理超时返回 500）。
        """
        if not self._enabled:
            return False
        return self._ensure_initialized()

    # ─── 仪表盘细粒度清空接口 ───────────────────────────────────
    def _check_initialized(self) -> Optional[Dict[str, Any]]:
        """检查系统是否就绪，未就绪返回错误 dict（不抛异常）。"""
        if not self._ensure_initialized() or self._system is None:
            return {"error": "Mandol 未启用或未初始化"}
        return None

    def _count_system_units(self) -> int:
        """统计 semantic_map 内的单元总数。"""
        try:
            system = self._system
            sem_map = getattr(system, "_semantic_map", None)
            if sem_map is None:
                return 0
            units = sem_map.list_units() or []
            return len(units)
        except Exception:
            return 0

    def clear_units(self) -> Dict[str, Any]:
        """仅清空记忆单元（Milvus 向量 + 内存中的单元 + Neo4j 关系）；
        实体 / 事件节点本身保留。"""
        with self._lock:
            err = self._check_initialized()
            if err:
                return err
            system = self._system
            sem_map = getattr(system, "_semantic_map", None)
            removed = 0
            try:
                if sem_map is not None:
                    for u in list(sem_map.list_units() or []):
                        try:
                            sem_map.delete_unit(u.uid)
                            removed += 1
                        except Exception as exc:  # noqa: BLE001
                            warn(f"删除单元 {u.uid} 失败: {exc}")
            except Exception as exc:  # noqa: BLE001
                warn(f"枚举单元失败: {exc}")
            # 同步清理 Milvus（drop+重建空 collection，保留 schema）
            milvus_ok = False
            try:
                from pymilvus import MilvusClient
                _client = MilvusClient(uri=settings.mandol_milvus_uri)
                coll = settings.mandol_milvus_collection
                if _client.has_collection(coll):
                    _client.drop_collection(coll)
                milvus_ok = True
                _client.close()
            except Exception as exc:  # noqa: BLE001
                warn(f"清空 Milvus 失败: {exc}")
            # 保存快照
            try:
                system.save()
            except Exception as exc:  # noqa: BLE001
                warn(f"保存快照失败: {exc}")
            self._invalidate_dashboard_caches()
            return {"detail": f"units_removed={removed} milvus={'ok' if milvus_ok else 'fail'}"}

    def clear_spaces(self) -> Dict[str, Any]:
        """仅清空记忆空间。仅在记忆单元为 0 时允许执行。"""
        with self._lock:
            err = self._check_initialized()
            if err:
                return err
            if self._count_system_units() > 0:
                return {"error": "请先清空记忆单元后再清空记忆空间"}
            system = self._system
            sem_map = getattr(system, "_semantic_map", None)
            removed = 0
            try:
                if sem_map is not None:
                    for sp in list(sem_map.list_spaces() or []):
                        try:
                            sem_map.delete_space(sp.name, cascade=True)
                            removed += 1
                        except Exception as exc:  # noqa: BLE001
                            warn(f"删除空间 {sp.name} 失败: {exc}")
            except Exception as exc:  # noqa: BLE001
                warn(f"枚举空间失败: {exc}")
            try:
                system.save()
            except Exception as exc:  # noqa: BLE001
                warn(f"保存快照失败: {exc}")
            self._invalidate_dashboard_caches()
            return {"detail": f"spaces_removed={removed}"}

    def clear_entities(self) -> Dict[str, Any]:
        """清空 Neo4j 中所有实体节点 + Mandol 内部实体集合。"""
        with self._lock:
            err = self._check_initialized()
            if err:
                return err
            system = self._system
            removed = 0
            # Neo4j
            try:
                from neo4j import GraphDatabase
                driver = GraphDatabase.driver(
                    settings.mandol_neo4j_uri,
                    auth=(settings.mandol_neo4j_user, settings.mandol_neo4j_password),
                )
                with driver.session(database=settings.mandol_neo4j_database) as sess:
                    result = sess.run(
                        "MATCH (n) WHERE n.uid STARTS WITH 'entity:' "
                        "DETACH DELETE n RETURN count(n) AS c"
                    )
                    removed = int(result.single()["c"])
                driver.close()
            except Exception as exc:  # noqa: BLE001
                warn(f"清空实体(Neo4j)失败: {exc}")
            # 内存实体集合
            try:
                all_entities = getattr(system, "_all_entities", None)
                if isinstance(all_entities, list):
                    all_entities.clear()
            except Exception as exc:  # noqa: BLE001
                warn(f"清空内存实体失败: {exc}")
            try:
                system.save()
            except Exception as exc:  # noqa: BLE001
                warn(f"保存快照失败: {exc}")
            self._invalidate_dashboard_caches()
            return {"detail": f"entities_removed={removed}"}

    def clear_events(self) -> Dict[str, Any]:
        """清空 Neo4j 中所有事件节点 + Mandol 内部事件集合。"""
        with self._lock:
            err = self._check_initialized()
            if err:
                return err
            system = self._system
            removed = 0
            try:
                from neo4j import GraphDatabase
                driver = GraphDatabase.driver(
                    settings.mandol_neo4j_uri,
                    auth=(settings.mandol_neo4j_user, settings.mandol_neo4j_password),
                )
                with driver.session(database=settings.mandol_neo4j_database) as sess:
                    result = sess.run(
                        "MATCH (n) WHERE n.uid STARTS WITH 'event:' "
                        "DETACH DELETE n RETURN count(n) AS c"
                    )
                    removed = int(result.single()["c"])
                driver.close()
            except Exception as exc:  # noqa: BLE001
                warn(f"清空事件(Neo4j)失败: {exc}")
            try:
                all_events = getattr(system, "_all_events", None)
                if isinstance(all_events, list):
                    all_events.clear()
            except Exception as exc:  # noqa: BLE001
                warn(f"清空内存事件失败: {exc}")
            try:
                system.save()
            except Exception as exc:  # noqa: BLE001
                warn(f"保存快照失败: {exc}")
            self._invalidate_dashboard_caches()
            return {"detail": f"events_removed={removed}"}

    def clear_neo4j_only(self) -> Dict[str, Any]:
        """清空整个 Neo4j 图（节点 + 关系）。"""
        with self._lock:
            removed = 0
            try:
                from neo4j import GraphDatabase
                driver = GraphDatabase.driver(
                    settings.mandol_neo4j_uri,
                    auth=(settings.mandol_neo4j_user, settings.mandol_neo4j_password),
                )
                with driver.session(database=settings.mandol_neo4j_database) as sess:
                    result = sess.run("MATCH (n) DETACH DELETE n RETURN count(n) AS c")
                    removed = int(result.single()["c"])
                driver.close()
            except Exception as exc:  # noqa: BLE001
                return {"error": f"Neo4j 清空失败: {exc}"}
            return {"detail": f"neo4j_removed={removed}"}

    def clear_milvus_only(self) -> Dict[str, Any]:
        """清空 Milvus 向量集合（drop collection）。"""
        with self._lock:
            try:
                from pymilvus import MilvusClient
                _client = MilvusClient(uri=settings.mandol_milvus_uri)
                coll = settings.mandol_milvus_collection
                if _client.has_collection(coll):
                    _client.drop_collection(coll)
                _client.close()
            except Exception as exc:  # noqa: BLE001
                return {"error": f"Milvus 清空失败: {exc}"}
            return {"detail": "milvus=cleared"}

    def clear_summaries(self) -> Dict[str, Any]:
        """剥离 vault 文档 frontmatter 中的 summary 字段。"""
        import re
        stripped = 0
        errors: list = []
        try:
            for md_file in settings.vault_dir.rglob("*.md"):
                try:
                    text = md_file.read_text(encoding="utf-8")
                    if not text.startswith("---"):
                        continue
                    new_text = re.sub(
                        r"^summary:\s*.*?\n",
                        "",
                        text,
                        count=1,
                        flags=re.MULTILINE,
                    )
                    if new_text != text:
                        md_file.write_text(new_text, encoding="utf-8")
                        stripped += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"strip {md_file}: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
        return {"detail": f"summaries_stripped={stripped} errors={len(errors)}"}

    def clear_base_memories(self) -> Dict[str, Any]:
        """删除 data/vault/imports/ 下所有解析文件。"""
        import shutil
        removed = 0
        errors: list = []
        try:
            vault_imports = settings.vault_dir / "imports"
            if vault_imports.is_dir():
                for child in list(vault_imports.iterdir()):
                    try:
                        if child.is_dir():
                            shutil.rmtree(child, ignore_errors=True)
                            removed += 1
                        elif child.is_file():
                            child.unlink()
                            removed += 1
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{child}: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
        return {"detail": f"dirs_removed={removed} errors={len(errors)}"}

    def clear_everything(self) -> Dict[str, Any]:
        """清空所有数据：Mandol 记忆 + Neo4j + Milvus + 基础记忆文件 + 摘要。"""
        # 1) 复用 clear_all 完成 Mandol + Neo4j + Milvus
        result = self.clear_all()
        if result.get("error"):
            return result
        # 2) 删除基础记忆文件（data/vault/imports）
        fs_stats: Dict[str, Any] = {"files_removed": 0, "summary_stripped": 0, "errors": []}
        try:
            import shutil
            import re
            vault_imports = settings.vault_dir / "imports"
            if vault_imports.is_dir():
                for child in list(vault_imports.iterdir()):
                    try:
                        if child.is_dir():
                            shutil.rmtree(child, ignore_errors=True)
                            fs_stats["files_removed"] += 1
                        elif child.is_file():
                            child.unlink()
                            fs_stats["files_removed"] += 1
                    except Exception as exc:  # noqa: BLE001
                        fs_stats["errors"].append(f"{child}: {exc}")
            # 3) 剥离 vault 文件 frontmatter 中的 summary 字段
            for md_file in settings.vault_dir.rglob("*.md"):
                try:
                    text = md_file.read_text(encoding="utf-8")
                    if text.startswith("---"):
                        new_text = re.sub(
                            r"^summary:\s*.*?\n",
                            "",
                            text,
                            count=1,
                            flags=re.MULTILINE,
                        )
                        if new_text != text:
                            md_file.write_text(new_text, encoding="utf-8")
                            fs_stats["summary_stripped"] += 1
                except Exception as exc:  # noqa: BLE001
                    fs_stats["errors"].append(f"strip {md_file}: {exc}")
        except Exception as exc:  # noqa: BLE001
            fs_stats["errors"].append(str(exc))

        result["detail"] = (
            f"{result.get('detail', '')} "
            f"files_removed={fs_stats['files_removed']} "
            f"summary_stripped={fs_stats['summary_stripped']}"
        )
        result["file_system"] = fs_stats
        return result

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
        self._invalidate_dashboard_caches()
        self._spaces_cache = None
        self._spaces_cache_ts = 0.0
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
        self._invalidate_dashboard_caches()
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
            self._invalidate_dashboard_caches()
            self._spaces_cache = None
            self._spaces_cache_ts = 0.0
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

    def reembed_all_units(self, only_zero: bool = True, batch_size: int = 32) -> Dict[str, Any]:
        """对存量单元重新计算 embedding 并写回。

        适用场景：之前因为缺少 sentence-transformers 等导致
        StaticEmbeddingProvider 退化为零向量，vector search 形同虚设。
        本方法会：
        1. 遍历所有 unit（按 batch 拉取，避免一次拉全表 OOM）；
        2. 对 embedding 全为 0（或缺省）的 unit 用当前 embedder 重新编码；
        3. 写回 unit store 并刷新 vector index。

        Args:
            only_zero: 仅处理当前 embedding 为零向量的 unit（增量修复）。
            batch_size: 一次处理的批大小，sentence-transformers CPU 推理建议 8-32。
        """
        from mandol import Uid
        import numpy as np

        system = self._require()
        # 优先使用 unit store 的批量接口（避免对每个 uid 都打一次网络）。
        store = system.semantic_map._store  # noqa: SLF001
        all_units = system.semantic_map.list_units()
        if not all_units:
            return {"scanned": 0, "reembedded": 0, "skipped": 0}

        def _is_zero(vec) -> bool:
            if vec is None:
                return True
            arr = np.asarray(vec, dtype=np.float32)
            return float(arr.sum()) == 0.0

        scanned = 0
        reembedded = 0
        skipped = 0
        # 按 batch 处理：先收集要重算的 unit，再统一 encode
        pending = []
        zero_count = 0
        no_text_count = 0
        non_zero_count = 0
        for u in all_units[:3]:
            cur = getattr(u, "embedding", None)
            arr = np.asarray(cur, dtype=np.float32) if cur is not None else None
            warn(f"[probe] uid={u.uid} cur_type={type(cur).__name__} cur_len={len(cur) if cur is not None and hasattr(cur, '__len__') else 'NA'} arr_sum={float(arr.sum()) if arr is not None and arr.size else 'NA'} raw_data_text_len={len((u.raw_data or {}).get('text_content', ''))}")

        for u in all_units:
            scanned += 1
            cur = getattr(u, "embedding", None)
            if only_zero and not _is_zero(cur):
                non_zero_count += 1
                skipped += 1
                continue
            zero_count += 1
            text = (u.raw_data or {}).get("text_content", "") or ""
            if not text:
                no_text_count += 1
                skipped += 1
                continue
            pending.append(u)
        warn(f"[reembed] scanned={scanned} pending={len(pending)} non_zero={non_zero_count} zero={zero_count} no_text={no_text_count}")

        for i in range(0, len(pending), batch_size):
            batch = pending[i : i + batch_size]
            texts = [(u.raw_data or {}).get("text_content", "") for u in batch]
            try:
                # 优先使用 semantic_map 的 embedder（MemorySystem 上没有
                # `embedder` 这个公共属性）。
                embedder = getattr(system.semantic_map, "_embedder", None)  # noqa: SLF001
                if embedder is None:
                    raise RuntimeError("system.semantic_map._embedder is None")
                new_vecs = embedder.embed_text(texts)
            except Exception as exc:
                import traceback as _tb
                warn(f"embed_text 失败 (batch {i // batch_size}): {exc}\n{_tb.format_exc()}")
                skipped += len(batch)
                continue
            for u, vec in zip(batch, new_vecs):
                u.embedding = vec
            try:
                store.upsert_units(batch)
            except Exception as exc:
                warn(f"upsert_units 失败 (batch {i // batch_size}): {exc}")
                continue
            reembedded += len(batch)

        # 重建 vector index（让新 embedding 立刻可被 ANN 检索到）
        try:
            vi = getattr(system, "_abi", None)  # noqa: SLF001
            if vi is not None and hasattr(vi, "clear"):
                vi.clear()
            units_with_vec = [u for u in all_units if getattr(u, "embedding", None) is not None]
            if vi is not None and hasattr(vi, "upsert"):
                vi.upsert([(u.uid, u.embedding) for u in units_with_vec])
        except Exception as exc:
            warn(f"vector index 重建失败: {exc}")

        # 失效相关缓存
        self._invalidate_dashboard_caches()
        self._spaces_cache = None
        self._spaces_cache_ts = 0.0
        return {"scanned": scanned, "reembedded": reembedded, "skipped": skipped}

    def _list_units_in_kind_space(self, kind: str, limit: int = 500) -> List[Dict[str, Any]]:
        """按类型(knowledge_entity / episodic_event / ...) 列出对应空间内的单元。"""
        from mandol.application.legacy.multidim_semantic_graph import SpaceNamingPolicy
        system = self._require()
        naming = SpaceNamingPolicy()
        root = str(getattr(system, "_root", "root"))
        method = getattr(naming, kind, None)
        if method is None:
            return []
        try:
            space = method(root)
            units = system.semantic_map.get_units_in_spaces([space])
        except Exception as exc:
            warn(f"读取空间 {kind} 失败: {exc}")
            return []
        space_name = str(space)
        return [_unit_to_dict(u, space_name=space_name) for u in units[:limit]]

    def list_entities(self, limit: int = 500) -> List[Dict[str, Any]]:
        """列出所有实体（knowledge_entity 空间）。"""
        return self._list_units_in_kind_space("knowledge_entity", limit=limit)

    def list_events(self, limit: int = 500) -> List[Dict[str, Any]]:
        """列出所有事件（episodic_event 空间）。"""
        return self._list_units_in_kind_space("episodic_event", limit=limit)

    def list_summaries(self, limit: int = 500) -> List[Dict[str, Any]]:
        """列出所有摘要（episodic_summary 空间）。"""
        return self._list_units_in_kind_space("episodic_summary", limit=limit)

    # ---------------- 高阶记忆构建 ----------------
    def build_high_level(
        self, mode: str = "auto", skip_summary: bool = True
    ) -> Dict[str, Any]:
        """触发高阶记忆构建（实体/事件抽取、摘要）。

        默认 skip_summary=True：跳过 summary 生成，直接使用原文切片
        作为高阶记忆。实体/事件抽取仍照常进行。
        """
        system = self._require()
        t0 = time.time()
        # 记录 build 前的实体/事件数,用于计算本次新增/去重
        try:
            stats_before = system.get_fact_stats()
        except Exception:
            stats_before = {"entity_count": 0, "event_count": 0}
        report = system.build_high_level(mode=mode, skip_summary=skip_summary)
        elapsed = time.time() - t0
        # 累计本次构建的 token 用量 (与 chat 分离, 便于监控构建期开销)
        try:
            usage = self._safe_get_token_usage()
            if usage and (usage.get("total_tokens") or 0) > 0:
                # 注意: get_token_usage() 返回的是本进程从启动到现在的累计
                # 不能直接当作增量 (否则会重复计算)。所以这里用 last_build_baseline
                # 做差分, 第一次 build 用现在的值作为基线
                with self._token_usage_lock:
                    base = self._last_build_baseline
                    delta_p = max(0, int(usage.get("prompt_tokens") or 0) - base["prompt_tokens"])
                    delta_c = max(0, int(usage.get("completion_tokens") or 0) - base["completion_tokens"])
                    self._last_build_baseline = {
                        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                        "completion_tokens": int(usage.get("completion_tokens") or 0),
                    }
                if delta_p > 0 or delta_c > 0:
                    self.add_build_tokens(delta_p, delta_c)
        except Exception as exc:  # noqa: BLE001
            warn(f"累计 build token 用量失败(忽略): {exc}")
        # 高阶抽取完成后,立即 flush 图存储(Mandol 的 Neo4jGraphStore 会把关系
        # 缓存在 _pending_upserts 里,只有 flush() 才会真正写入 Neo4j;否则下次
        # 读图 / 持久化到 graph.json 时取不到这些关系)。
        try:
            system.flush()
        except Exception as exc:  # noqa: BLE001
            warn(f"Mandol 高级构建后 flush 失败(忽略): {exc}")
        try:
            save_result = self.save(wait=True)
            if save_result.get("status") == "failed":
                warn(f"Mandol 高级构建后 snapshot 保存失败: {save_result.get('error')}")
        except Exception as exc:  # noqa: BLE001
            warn(f"Mandol 高级构建后 snapshot 保存失败(忽略): {exc}")
        # Mandol 默认使用 InMemoryGraphStore(NetworkX),与外部 Neo4j 之间
        # 没有自动同步,这里把内存图同步到 Neo4j,供前端 neo4j tab 可视化。
        try:
            sync_report = self.sync_graph_to_neo4j()
            result_extra = sync_report
        except Exception as exc:  # noqa: BLE001
            warn(f"同步 Mandol 内存图到 Neo4j 失败(忽略): {exc}")
            result_extra = {"status": "error", "error": str(exc)}
        self._invalidate_dashboard_caches()
        # 实体/事件统计 (本次 build 新增)
        try:
            stats_after = system.get_fact_stats()
        except Exception:
            stats_after = stats_before
        entities_added = max(0, stats_after["entity_count"] - stats_before["entity_count"])
        events_added = max(0, stats_after["event_count"] - stats_before["event_count"])
        result = {
            "status": getattr(report, "status", "completed"),
            "mode": mode,
            "sessions_processed": getattr(report, "sessions_processed", 0),
            "units_processed": getattr(report, "units_processed", 0),
            "duration_seconds": round(elapsed, 3),
            "token_usage": self._safe_token_usage(report),
            "warnings": list(getattr(report, "warnings", []) or []),
            "error": getattr(report, "error_message", None),
            "neo4j_sync": result_extra,
            # ---- 抽取结果 (供前端展示) ----
            "extraction": {
                "entity_count": stats_after["entity_count"],
                "event_count": stats_after["event_count"],
                "entities_added": entities_added,
                "events_added": events_added,
                "entities_extracted": stats_after.get("entities_extracted", 0),
                "events_extracted": stats_after.get("events_extracted", 0),
                "entities_deduped": stats_after.get("entities_deduped", 0),
                "events_deduped": stats_after.get("events_deduped", 0),
                "total_units": getattr(report, "units_processed", 0),
            },
        }
        info(f"高阶记忆构建完成: {result['status']}, "
             f"会话={result['sessions_processed']}, 单元={result['units_processed']}, "
             f"实体={stats_after['entity_count']}, 事件={stats_after['event_count']}, "
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
            auto_build_if_empty=False,
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
            auto_build_if_empty=False,
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
            query, top_k=top_k, use_rerank=use_rerank, auto_build_if_empty=False
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
        # 累计 chat token 用量 (非流式分支 /api/chat 走的路径):
        # ask_with_hits 没返回 usage, 只能本地估算, 用于仪表盘监控真实开销。
        # prompt 估算: 拼接 system + context(检索到的 hit 文本) + query
        try:
            from .llm_stream import estimate_tokens as _est_tok
            _ctx_parts = []
            for _i, _h in enumerate(hits, 1):
                _t = _h.unit.raw_data.get("text_content", "") if hasattr(_h, "unit") else ""
                _ctx_parts.append(f"[{_i}] {_t}")
            _ctx = "\n".join(_ctx_parts) if _ctx_parts else ""
            _sys = system_prompt or ""
            _prompt_tokens = _est_tok(_sys) + _est_tok(_ctx) + _est_tok(query)
            _completion_tokens = _est_tok(answer or "")
            self.add_chat_tokens(_prompt_tokens, _completion_tokens)
        except Exception as _exc:  # noqa: BLE001
            warn(f"ask() 累计 chat token 失败(忽略): {_exc}")
        # ⭐ 兜底: gemma4:12b 等模型只输出 reasoning 不输出 content 时,
        # 退化到流式调用（流式会正确分离 thinking/content）。
        if not (answer or "").strip():
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
                if full_text.strip():
                    answer = full_text
            except Exception as exc:
                warn(f"流式兜底生成失败: {exc}")
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
            query, top_k=top_k, use_rerank=use_rerank, auto_build_if_empty=False
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
            # 优先用批量接口，一次网络往返即可验证所有 uid；
            # 否则退化为逐个 get_unit（仍可工作，只是慢很多）。
            try:
                alive = [u for u in store.get_units(list(sp.unit_uids)) if u is not None]
            except AttributeError:
                alive = [u for u in sp.unit_uids if store.get_unit(u) is not None]
            # 注意：alive 只包含"被取到"的 unit；不在结果中的视为死引用。
            alive_uids = {str(u.uid) for u in alive}
            if len(alive_uids) == len(sp.unit_uids):
                return 0
            # 保持原顺序，仅保留仍存在的 uid
            new_uids = [u for u in sp.unit_uids if str(u) in alive_uids]
            dead = len(sp.unit_uids) - len(new_uids)
            sp.unit_uids = new_uids
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
        except Exception:
            return 0
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
        import time as _time
        now = _time.monotonic()
        if (
            self._spaces_cache is not None
            and (now - self._spaces_cache_ts) < self._SPACES_CACHE_TTL
        ):
            return list(self._spaces_cache)
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
        self._spaces_cache = list(out)
        self._spaces_cache_ts = now
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
        """递归统计空间及其所有子空间下"实际存在"的单元数（去重）。

        注意：本方法假定 _prune_dead_uids 已被调用过（list_spaces 中
        prune_ghost=True 的默认流程即是），因此直接统计
        get_all_unit_uids() 的长度即可，无需再走一次 Milvus 网络 IO。
        """
        try:
            return len(sp.get_all_unit_uids(recursive=True))
        except Exception:
            return len(sp.unit_uids or [])

    def create_space(self, name: str) -> Dict[str, Any]:
        """创建记忆空间。"""
        system = self._require()
        sp = system.semantic_map.create_space(name)
        self._invalidate_dashboard_caches()
        self._spaces_cache = None
        self._spaces_cache_ts = 0.0
        return {
            "name": str(sp.name),
            "unit_count": 0,
            "child_spaces": [],
        }

    def delete_space(self, name: str, cascade: bool = False) -> Dict[str, Any]:
        """删除记忆空间。"""
        system = self._require()
        system.semantic_map.delete_space(name, cascade=cascade)
        self._invalidate_dashboard_caches()
        self._spaces_cache = None
        self._spaces_cache_ts = 0.0
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
        return [_unit_to_dict(u, space_name=str(space_name)) for u in units[:limit]]

    def add_unit_to_space(self, uid: str, space_name: str) -> Dict[str, Any]:
        """将单元添加到空间。"""
        from mandol import Uid
        system = self._require()
        system.semantic_map.add_unit_to_space(Uid(uid), space_name)
        self._spaces_cache = None
        self._spaces_cache_ts = 0.0
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
        self._spaces_cache = None
        self._spaces_cache_ts = 0.0
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
        """获取实体子图。

        当向量检索（embedder）不可用时，回退到文本关键词匹配。
        """
        system = self._require()
        result = system.graph.retrieve_entity_subgraph(
            query, max_depth=max_depth, top_k=top_k
        )
        # 检查结果是否有效（embedder 降级为 zero embeddings 时可能返回无关结果）
        center = getattr(result, "center_entity", None)
        needs_fallback = not center
        if center:
            # 验证返回的 center 是否真的与查询相关
            q_lower = query.lower()
            c_uid = str(center.uid).lower()
            c_raw = str(center.raw_data.get("text_content", "")).lower()
            if q_lower not in c_uid and q_lower not in c_raw:
                needs_fallback = True
        if needs_fallback:
            # 回退：对所有 unit 做文本关键词匹配，再取图邻居
            from mandol import Uid
            from mandol.retrieval.types import EntitySubgraphResult, RelationshipInfo
            from collections import deque

            all_units = system.semantic_map.list_units()
            q_lower = query.lower()
            matched = []
            for u in all_units:
                uid_str = str(u.uid).lower()
                raw_text = str(u.raw_data.get("text_content", "")).lower()
                if q_lower in uid_str or q_lower in raw_text:
                    matched.append(u)
                if len(matched) >= top_k:
                    break

            if matched:
                center = matched[0]
                center_uid = Uid(str(center.uid))
                neighbors = list(matched[1:])
                relationships: list = []
                seen = {center_uid}
                for u in neighbors:
                    seen.add(Uid(str(u.uid)))

                # BFS 扩展邻居
                queue = deque([(center_uid, 0)])
                while queue and len(neighbors) < top_k:
                    current, depth = queue.popleft()
                    if depth >= max_depth:
                        continue
                    # 分别查 out 和 in 方向（Neo4j 不支持 "both"）
                    hop_uids = list(system.graph._graph.get_neighbors(current, direction="out"))
                    hop_uids += list(system.graph._graph.get_neighbors(current, direction="in"))
                    for n_uid in hop_uids:
                        if n_uid in seen:
                            continue
                        seen.add(n_uid)
                        n_unit = system.semantic_map.get_unit(n_uid)
                        if n_unit:
                            neighbors.append(n_unit)
                            queue.append((n_uid, depth + 1))
                            if len(neighbors) >= top_k:
                                break

                # 收集边：遍历所有边，筛选涉及的 unit
                matched_uids = {str(center_uid)} | {str(Uid(str(u.uid))) for u in neighbors}
                for s_uid, t_uid, etype, props in system.graph._graph.get_all_edges():
                    s_str, t_str = str(s_uid), str(t_uid)
                    if s_str in matched_uids or t_str in matched_uids:
                        relationships.append(RelationshipInfo(
                            source_uid=s_uid,
                            target_uid=t_uid,
                            rel_type=etype,
                            properties=props or {},
                        ))

                result = EntitySubgraphResult(
                    center_entity=center,
                    neighbors=neighbors,
                    relationships=relationships,
                    depth_map={str(center_uid): 0},
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
    def get_stats(self, force: bool = False) -> Dict[str, Any]:
        """获取 Mandol 记忆系统统计（带 5s 进程内缓存，避免仪表盘反复全量扫描）。"""
        if not self._ensure_initialized():
            return {"enabled": False}
        now = time.time()
        if (
            not force
            and self._stats_cache is not None
            and (now - self._stats_cache_ts) < self._STATS_CACHE_TTL
        ):
            return self._stats_cache
        result = self._compute_stats()
        self._stats_cache = result
        self._stats_cache_ts = now
        return result

    def _compute_stats(self) -> Dict[str, Any]:
        """实际执行统计计算（不读缓存）。"""
        system = self._system
        if system is None:
            return {"enabled": False}
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

            neo4j_entity_count = 0
            neo4j_event_count = 0
            try:
                from neo4j import GraphDatabase
                _driver = GraphDatabase.driver(
                    settings.mandol_neo4j_uri,
                    auth=(settings.mandol_neo4j_user, settings.mandol_neo4j_password)
                )
                with _driver.session(database=settings.mandol_neo4j_database) as _sess:
                    e_result = _sess.run(
                        "MATCH (n) WHERE n.entity_type IS NOT NULL OR labels(n) <> ['MemoryUnit'] "
                        "AND NOT n.entity_type IS NULL RETURN count(n) AS cnt"
                    )
                    rec = e_result.single()
                    if rec:
                        neo4j_entity_count = int(rec["cnt"])

                    ev_result = _sess.run(
                        "MATCH (n) WHERE n.event_type IS NOT NULL RETURN count(n) AS cnt"
                    )
                    rec = ev_result.single()
                    if rec:
                        neo4j_event_count = int(rec["cnt"])
                _driver.close()
            except Exception as _neo4j_exc:
                pass

            final_entity_count = max(counts.get("knowledge_entity", 0), neo4j_entity_count)
            final_event_count = max(counts.get("episodic_event", 0), neo4j_event_count)
            # 仪表盘 token 卡片: 用累计值 (build + chat + total), 不再只是当前 build session
            # 这样能反映「全平台」的真实 LLM 开销, 且重启不丢
            by_phase = self.get_cumulative_token_usage()
            total = by_phase.get("total") or {}
            return {
                "enabled": True,
                "total_units": len(all_units),
                "total_spaces": len(all_spaces),
                "base_memory_count": counts.get("base_memory", 0),
                "entity_count": final_entity_count,
                "event_count": final_event_count,
                "summary_count": counts.get("episodic_summary", 0),
                # 顶层保持旧形状: {prompt, completion, total} = 三个总和
                "token_usage": dict(total),
                # 新增: 分阶段 (build/chat/total), 供前端卡片区分
                "token_usage_by_phase": by_phase,
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
                # 写盘后清缓存，外部存储的 size_bytes 才会更新
                self._invalidate_dashboard_caches()

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
    # Milvus Lite 会在 milvus.db 上加文件锁，同一进程内多次创建连接会被
    # fcntl.flock 拒绝（DataDirLockedError）。把 MilvusClient 缓存为单例，
    # 跨 external_store_status 调用复用，避免与 Mandol 内部 UnitStore 冲突。
    _milvus_client: Optional[Any] = None

    def _get_milvus_client(self) -> Any:
        """获取（或懒加载）进程内共享 MilvusClient；用于状态查询。"""
        if MandolService._milvus_client is not None:
            return MandolService._milvus_client
        with _MILVUS_CLIENT_LOCK:
            if MandolService._milvus_client is None:
                from pymilvus import MilvusClient
                MandolService._milvus_client = MilvusClient(uri=settings.mandol_milvus_uri)
        return MandolService._milvus_client

    def external_store_status(self, force: bool = False, timeout: float = 3.0) -> Dict[str, Any]:
        """查询 Neo4j + Milvus 实际状态（带 10s 进程内缓存）。

        仪表盘每次刷新都会调用此接口；为避免反复连接 Neo4j/Milvus，
        加 TTL 缓存。``force=True`` 可绕过缓存。
        Neo4j/Milvus 任一探测超过 ``timeout`` 秒也会快速失败并返回错误信息，
        避免仪表盘长时间转圈。
        """
        now = time.time()
        if (
            not force
            and self._external_cache is not None
            and (now - self._external_cache_ts) < self._EXTERNAL_CACHE_TTL
        ):
            return self._external_cache

        status: Dict[str, Any] = {
            "neo4j": {"available": False, "nodes": 0, "edges": 0, "rel_types": []},
            "milvus": {"available": False, "uri": settings.mandol_milvus_uri, "collection": settings.mandol_milvus_collection, "unit_count": 0},
            "snapshot": {"path": str(Path(self._storage_root or settings.mandol_storage_dir) / "snapshot.json"), "exists": False, "size_bytes": 0},
        }
        # Neo4j（带超时：网络异常时不再阻塞仪表盘）
        try:
            from neo4j import GraphDatabase
            d = GraphDatabase.driver(
                settings.mandol_neo4j_uri,
                auth=(settings.mandol_neo4j_user, settings.mandol_neo4j_password),
                connection_timeout=timeout,
                max_connection_lifetime=timeout * 2,
            )
            with d.session(database=settings.mandol_neo4j_database) as s:
                status["neo4j"]["nodes"] = s.run("MATCH (n) RETURN count(n) as c").single()["c"]
                status["neo4j"]["edges"] = s.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
                status["neo4j"]["rel_types"] = [r["relationshipType"] for r in s.run("CALL db.relationshipTypes()")]
            d.close()
            status["neo4j"]["available"] = True
        except Exception as exc:
            status["neo4j"]["error"] = str(exc)
        # Milvus（复用进程内单例 client，避免与 UnitStore 的 fcntl 锁冲突）
        try:
            client = self._get_milvus_client()
            if client.has_collection(settings.mandol_milvus_collection):
                # 注: Milvus Lite 的 get_collection_stats() 不可靠, row_count 经常返回 0
                # 即使集合里其实有几百条记录。改用 query + id>"" 真实统计, 并取 max(row_count, real_count)
                real_count = 0
                try:
                    real_count = len(client.query(
                        settings.mandol_milvus_collection,
                        filter='uid != ""',
                        output_fields=['uid'],
                        limit=10000,
                    ))
                except Exception:
                    pass
                stats_count = 0
                try:
                    stats_count = int(client.get_collection_stats(
                        settings.mandol_milvus_collection
                    ).get("row_count", 0) or 0)
                except Exception:
                    pass
                status["milvus"]["unit_count"] = max(stats_count, real_count)
                status["milvus"]["available"] = True
        except Exception as exc:
            status["milvus"]["error"] = str(exc)
        # Snapshot
        try:
            snap = Path(status["snapshot"]["path"])
            if snap.exists():
                status["snapshot"]["exists"] = True
                status["snapshot"]["size_bytes"] = snap.stat().st_size
        except Exception as exc:
            status["snapshot"]["error"] = str(exc)

        self._external_cache = status
        self._external_cache_ts = now
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

    def build_status(self) -> Dict[str, Any]:
        """查询高阶记忆构建的实时状态（供前端轮询）。

        Returns
        -------
        dict
            - status: idle | running | completed | failed
            - message: 当前阶段的中文描述
            - started_at / finished_at: 时间戳
            - elapsed_seconds: 已运行时长（running 时持续累加）
            - result: 最近一次构建的最终结果(含 extraction / neo4j_sync 等)
        """
        now = time.time()
        if self._build_in_progress.is_set():
            return {
                "status": "running",
                "message": self._build_progress_message or "正在构建...",
                "started_at": self._build_started_at,
                "finished_at": 0.0,
                "elapsed_seconds": round(now - self._build_started_at, 1) if self._build_started_at else 0.0,
                "result": None,
            }
        # 已结束
        if self._last_build_result is None:
            return {
                "status": "idle",
                "message": "",
                "started_at": 0.0,
                "finished_at": 0.0,
                "elapsed_seconds": 0.0,
                "result": None,
            }
        ok = self._last_build_result.get("status") not in ("failed", "error")
        return {
            "status": "completed" if ok else "failed",
            "message": self._last_build_result.get("message") or (
                "构建完成" if ok else "构建失败"
            ),
            "started_at": self._build_started_at,
            "finished_at": self._build_finished_at,
            "elapsed_seconds": round(self._build_finished_at - self._build_started_at, 1)
                if self._build_finished_at and self._build_started_at else 0.0,
            "result": self._last_build_result,
        }

    def build_high_level_async(
        self, mode: str = "auto", skip_summary: bool = True
    ) -> Dict[str, Any]:
        """异步触发高阶记忆构建，立刻返回当前状态。

        实际工作在后台线程里跑；前端通过 /api/mandol/build-status 轮询进度。
        避免 /api/documents/{id}/save 长时间阻塞导致前端 "卡住" 错觉。
        """
        if self._build_in_progress.is_set():
            return {
                "status": "busy",
                "message": "已有构建任务在运行",
                "build_status": self.build_status(),
            }

        def _worker() -> None:
            self._build_in_progress.set()
            self._build_started_at = time.time()
            self._build_progress_message = "正在抽取实体与事件..."
            try:
                # phase 1: 主体抽取 (耗时最长, 通常 60-180s)
                result = self.build_high_level(mode=mode, skip_summary=skip_summary)
                # phase 2: 已完成, 写最终状态
                self._last_build_result = {
                    "status": "completed",
                    "message": "高阶记忆构建完成",
                    "report": result,
                }
            except Exception as exc:  # noqa: BLE001
                warn(f"异步高阶构建失败: {exc}")
                self._last_build_result = {
                    "status": "failed",
                    "message": str(exc),
                    "error": str(exc),
                }
            finally:
                self._build_finished_at = time.time()
                self._build_in_progress.clear()
                self._build_progress_message = ""

        threading.Thread(target=_worker, daemon=True).start()
        return {"status": "started", "build_status": self.build_status()}

    def sync_graph_to_neo4j(self) -> Dict[str, Any]:
        """把 Mandol 内存图(NetworkX)同步到外部 Neo4j,供前端 neo4j tab 可视化。

        Mandol 默认使用 InMemoryGraphStore(NetworkX),与外部 Neo4j 之间
        没有自动同步机制;前端 neo4j tab 直接查 Neo4j,所以会一直显示 0 节点。
        该方法读取 memory_system._graph_store 的全部节点/边,写入 Neo4j
        (使用 MERGE 去重,不会产生重复)。
        """
        system = self._require()
        from ..config.settings import settings
        from neo4j import GraphDatabase

        graph_store = getattr(system, "_graph_store", None)
        if graph_store is None:
            return {"status": "no-graph", "nodes": 0, "edges": 0}

        # 1) 读取内存图所有节点/边
        # 兼容两种图存储:InMemoryGraphStore(NetworkX, _g) 与 Neo4jGraphStore(无 _g)
        nodes = []
        edges = []
        try:
            g = getattr(graph_store, "_g", None)
            if g is not None:
                nodes = list(g.nodes(data=True))
                edges = list(g.edges(data=True))
            else:
                # Neo4jGraphStore: 通过 get_all_edges 拿边,节点从边端点聚合
                all_edges = graph_store.get_all_edges()
                seen = {}
                for source, target, rel_type, props in all_edges:
                    seen[str(source)] = (str(source), props or {})
                    seen[str(target)] = (str(target), {})
                    edges.append((str(source), str(target), {"type": rel_type, **(props or {})}))
                nodes = list(seen.values())
        except Exception as exc:  # noqa: BLE001
            warn(f"读取内存图失败: {exc}")
            return {"status": "error", "error": str(exc), "nodes": 0, "edges": 0}

        # 1.5) 把 semantic_map 里所有 unit 也补进 nodes(仅 entity/event/summary/chunk 之类)
        # 这样即便它们没出现在图的边上(例如还没生成语义关系),也能在 Neo4j 里看见
        try:
            sem_map = getattr(system, "_semantic_map", None)
            if sem_map is not None and hasattr(sem_map, "list_units"):
                existing_uids = {str(uid) for uid, _ in nodes}
                for u in sem_map.list_units():
                    uid_str = str(getattr(u, "uid", "") or "")
                    if not uid_str or uid_str in existing_uids:
                        continue
                    raw = getattr(u, "raw_data", {}) or {}
                    # 只把 entity / event / summary / chunk 这四类有展示价值的拉进来
                    if not (
                        uid_str.startswith("entity:")
                        or uid_str.startswith("event:")
                        or uid_str.startswith("doc:")
                        or (uid_str.startswith("sess_") and "summary" in uid_str)
                    ):
                        continue
                    # 把一些基础展示字段先压进 attrs,后面 enrich 会再覆盖一次
                    display = {}
                    name = raw.get("entity_name") or raw.get("event_name") or raw.get("title") or raw.get("name")
                    if name:
                        display["name"] = str(name)
                    for k in ("entity_type", "event_subtype", "subtype", "type"):
                        if raw.get(k):
                            display["type"] = str(raw.get(k))
                            break
                    if raw.get("description") or raw.get("desc"):
                        display["description"] = str(raw.get("description") or raw.get("desc"))
                    nodes.append((uid_str, display))
                    existing_uids.add(uid_str)
        except Exception as exc:  # noqa: BLE001
            warn(f"补全 semantic_map 节点失败: {exc}")

        # 2) 写入 Neo4j
        driver = GraphDatabase.driver(
            settings.mandol_neo4j_uri,
            auth=(settings.mandol_neo4j_user, settings.mandol_neo4j_password),
        )
        node_count = 0
        edge_count = 0
        try:
            with driver.session(database=settings.mandol_neo4j_database) as sess:
                # 节点:仅以 uid 作主键,顺手把 name/title/text 等常见展示字段带上
                for uid, attrs in nodes:
                    uid_str = str(uid)
                    # 过滤掉不可序列化的属性(例如 _g 这种内部对象)
                    props = {"uid": uid_str}
                    for k, v in (attrs or {}).items():
                        if k.startswith("_") or v is None:
                            continue
                        try:
                            import json as _json
                            _json.dumps(v)
                            props[k] = v
                        except (TypeError, ValueError):
                            props[k] = str(v)
                    sess.run(
                        "MERGE (n {uid:$uid}) SET n += $props",
                        uid=uid_str,
                        props=props,
                    )
                    node_count += 1

                # 边:用 uid 定位端点,按 rel_type 区分
                for source, target, data in edges:
                    s = str(source)
                    t = str(target)
                    rel = str(data.get("type", "RELATED_TO")) if isinstance(data, dict) else "RELATED_TO"
                    edge_props = {}
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if k in ("type",) or v is None or k.startswith("_"):
                                continue
                            try:
                                import json as _json
                                _json.dumps(v)
                                edge_props[k] = v
                            except (TypeError, ValueError):
                                edge_props[k] = str(v)
                    sess.run(
                        f"MERGE (a {{uid:$s}}) MERGE (b {{uid:$t}}) "
                        f"MERGE (a)-[r:{rel}]->(b) SET r += $props",
                        s=s, t=t, props=edge_props,
                    )
                    edge_count += 1
        finally:
            driver.close()

        # 4) 回填:从 semantic_map 把 entity/event/summary 的可读属性写进 Neo4j 节点
        # 仅当 graph_store 是 Neo4jGraphStore 时才执行,避免对内存图做无谓的二次写入
        from ..config.settings import settings as _settings
        try:
            from neo4j import GraphDatabase as _Gdb
            _drv = _Gdb.driver(
                _settings.mandol_neo4j_uri,
                auth=(_settings.mandol_neo4j_user, _settings.mandol_neo4j_password),
            )
        except Exception:
            _drv = None
        if _drv is not None:
            try:
                self._enrich_neo4j_nodes(_drv)
            finally:
                _drv.close()

        info(f"已同步 Mandol 内存图到 Neo4j: nodes={node_count}, edges={edge_count}")
        return {"status": "synced", "nodes": node_count, "edges": edge_count}

    # ------------------------------------------------------------------
    # 用 semantic_map 里的 unit 数据,补全 Neo4j 节点的展示属性 + labels
    # ------------------------------------------------------------------
    def _enrich_neo4j_nodes(self, driver) -> None:
        """根据 unit 类型,把 entity_name / event_name / 摘要 / chunk 文本等
        字段写到 Neo4j 节点的属性里,并打上 Neo4j labels,让前端 Browser
        不再看到一堆 "uid-only" 的空节点。"""
        from ..config.settings import settings as _settings

        system = self._require()
        sem_map = getattr(system, "_semantic_map", None)
        if sem_map is None or not hasattr(sem_map, "list_units"):
            return

        try:
            units = sem_map.list_units()
        except Exception as exc:  # noqa: BLE001
            warn(f"读取 semantic_map 失败: {exc}")
            return

        # 单元显示名/类型从 raw_data 里取 (Mandol 在生成 unit 时会把
        # entity_name / entity_type / event_name / text_content 等塞进 raw_data)
        enriched = 0
        with driver.session(database=_settings.mandol_neo4j_database) as sess:
            for u in units:
                uid_str = str(getattr(u, "uid", "") or "")
                if not uid_str:
                    continue
                raw = getattr(u, "raw_data", {}) or {}
                meta = getattr(u, "metadata", {}) or {}
                text_content = (
                    raw.get("text_content")
                    or raw.get("description")
                    or raw.get("summary")
                    or ""
                )
                # 兼容 Mandol 把全部内容塞 text_content 的情况
                if not text_content and isinstance(raw, dict):
                    # 兜底:把 dict 拍平成一行字符串
                    try:
                        import json as _json
                        text_content = _json.dumps(raw, ensure_ascii=False)[:400]
                    except Exception:
                        text_content = str(raw)[:400]

                # 类别/标签推断
                labels: list = []
                props: dict = {"uid": uid_str}
                preview = (text_content or "").strip()
                if preview:
                    props["preview"] = preview[:300]

                if uid_str.startswith("entity:"):
                    name = raw.get("entity_name") or raw.get("name") or ""
                    etype = raw.get("entity_type") or raw.get("type") or ""
                    desc = raw.get("description") or raw.get("desc") or ""
                    props["name"] = name
                    props["type"] = etype
                    props["description"] = desc
                    labels.append("Entity")
                    if etype:
                        labels.append(str(etype).strip())
                elif uid_str.startswith("event:"):
                    name = raw.get("event_name") or raw.get("name") or ""
                    subtype = raw.get("subtype") or raw.get("event_subtype") or ""
                    desc = raw.get("description") or raw.get("desc") or ""
                    props["name"] = name
                    props["subtype"] = subtype
                    props["description"] = desc
                    labels.append("Event")
                    if subtype:
                        labels.append(str(subtype).strip())
                elif uid_str.startswith("doc:"):
                    labels.append("Chunk")
                elif uid_str.startswith("sess_") and "summary" in uid_str:
                    labels.append("Summary")
                else:
                    # 会话/其他单元
                    labels.append("Unit")

                # Neo4j label 名要合法(字母数字下划线),把中文/特殊字符替成 _
                import re as _re
                safe_labels = [
                    _re.sub(r"[^A-Za-z0-9_]", "_", lbl) for lbl in labels
                ]
                # label 必须写在 ( 之后: MERGE (n:L1:L2 {uid:$uid}) ...
                label_clause = (
                    ":" + ":".join(safe_labels) if safe_labels else ""
                )
                q = f"MERGE (n{label_clause} {{uid:$uid}}) SET n += $props"
                sess.run(q, uid=uid_str, props=props)
                enriched += 1

        info(f"Neo4j 节点回填完成: enriched={enriched}")

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

    # ---------------- Token 累计持久化 ----------------
    def _token_usage_path(self) -> Path:
        """token_usage.json 存放位置: 与 snapshot.json 同目录, 但独立文件。
        独立的好处: 不污染 snapshot, 可以热更新, 重置不影响主数据。
        """
        if self._token_usage_file is not None:
            return self._token_usage_file
        root = self._storage_root or str(settings.mandol_storage_dir)
        Path(root).mkdir(parents=True, exist_ok=True)
        self._token_usage_file = Path(root) / "token_usage.json"
        return self._token_usage_file

    def _load_cumulative_token_usage(self) -> None:
        """从 token_usage.json 加载累计值, 保证重启不丢。"""
        path = self._token_usage_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError) as exc:
            warn(f"token_usage.json 读取失败(忽略, 用默认值): {exc}")
            return
        for bucket in ("build", "chat", "total"):
            sub = data.get(bucket) or {}
            with self._token_usage_lock:
                for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    self._cumulative_token_usage[bucket][k] = int(sub.get(k) or 0)
        info(
            f"已从 token_usage.json 恢复累计: "
            f"build={self._cumulative_token_usage['build']['total_tokens']}, "
            f"chat={self._cumulative_token_usage['chat']['total_tokens']}, "
            f"total={self._cumulative_token_usage['total']['total_tokens']}"
        )

    def _save_cumulative_token_usage(self) -> None:
        """把当前累计值原子地写到 token_usage.json。"""
        path = self._token_usage_path()
        with self._token_usage_lock:
            snapshot = {
                "build": dict(self._cumulative_token_usage["build"]),
                "chat": dict(self._cumulative_token_usage["chat"]),
                "total": dict(self._cumulative_token_usage["total"]),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        try:
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, path)
        except OSError as exc:
            warn(f"token_usage.json 写入失败(忽略, 不影响主流程): {exc}")

    def add_chat_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        """在线问答每完成一轮, 累加 token 用量 + 落盘。"""
        if prompt_tokens <= 0 and completion_tokens <= 0:
            return
        with self._token_usage_lock:
            for k, v in (
                ("prompt_tokens", int(prompt_tokens)),
                ("completion_tokens", int(completion_tokens)),
                ("total_tokens", int(prompt_tokens) + int(completion_tokens)),
            ):
                self._cumulative_token_usage["chat"][k] += v
                self._cumulative_token_usage["total"][k] += v
        self._save_cumulative_token_usage()
        # 仪表盘缓存的 token_usage 也要失效, 否则 stats 5s 缓存不刷新
        self._invalidate_dashboard_caches()

    def add_build_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        """高阶构建每完成一个 session, 累加 token 用量 + 落盘。
        与 add_chat_tokens 分离, 方便监控构建期的 LLM 开销。
        """
        if prompt_tokens <= 0 and completion_tokens <= 0:
            return
        with self._token_usage_lock:
            for k, v in (
                ("prompt_tokens", int(prompt_tokens)),
                ("completion_tokens", int(completion_tokens)),
                ("total_tokens", int(prompt_tokens) + int(completion_tokens)),
            ):
                self._cumulative_token_usage["build"][k] += v
                self._cumulative_token_usage["total"][k] += v
        self._save_cumulative_token_usage()
        self._invalidate_dashboard_caches()

    def get_cumulative_token_usage(self) -> Dict[str, Dict[str, int]]:
        """获取当前累计, 包括 build/chat/total 三个 bucket。"""
        with self._token_usage_lock:
            return {
                "build": dict(self._cumulative_token_usage["build"]),
                "chat": dict(self._cumulative_token_usage["chat"]),
                "total": dict(self._cumulative_token_usage["total"]),
            }

    def reset_cumulative_token_usage(self) -> Dict[str, Dict[str, int]]:
        """清零累计值 (前端重置按钮 / 调试用)。"""
        with self._token_usage_lock:
            for bucket in ("build", "chat", "total"):
                for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    self._cumulative_token_usage[bucket][k] = 0
        self._save_cumulative_token_usage()
        self._invalidate_dashboard_caches()
        return self.get_cumulative_token_usage()

    def _subgraph_result_to_dict(self, result) -> Dict[str, Any]:
        """转换实体子图结果。

        EntitySubgraphResult 的字段为 center_entity / neighbors / relationships / depth_map，
        需要映射到前端期望的 nodes / edges / entities / events。
        """
        nodes: list = []
        edges: list = []

        # 兼容旧格式（直接有 nodes/edges 属性）
        legacy_nodes = getattr(result, "nodes", None)
        legacy_edges = getattr(result, "edges", None)

        if legacy_nodes is not None and isinstance(legacy_nodes, list):
            nodes = legacy_nodes
        else:
            # EntitySubgraphResult: center_entity + neighbors
            center = getattr(result, "center_entity", None)
            if center is not None:
                nodes.append(center)
            neighbors = getattr(result, "neighbors", None)
            if neighbors and isinstance(neighbors, list):
                for n in neighbors:
                    if n not in nodes:
                        nodes.append(n)

        if legacy_edges is not None and isinstance(legacy_edges, list):
            edges = legacy_edges
        else:
            # EntitySubgraphResult: relationships -> edges
            rels = getattr(result, "relationships", None)
            if rels and isinstance(rels, list):
                for r in rels:
                    if hasattr(r, "source_uid"):
                        edges.append({
                            "source": str(r.source_uid),
                            "target": str(r.target_uid),
                            "relationship": r.rel_type,
                        })
                    elif hasattr(r, "source"):
                        edges.append({
                            "source": str(getattr(r, "source", "")),
                            "target": str(getattr(r, "target", "")),
                            "relationship": getattr(r, "relation_type", getattr(r, "type", "RELATED")),
                        })

        # entities / events 分类
        entities = []
        events = []
        for n in nodes:
            uid_str = str(getattr(n, "uid", ""))
            if uid_str.startswith("entity:"):
                entities.append(_unit_to_dict(n) if hasattr(n, "uid") else str(n))
            elif uid_str.startswith("event:"):
                events.append(_unit_to_dict(n) if hasattr(n, "uid") else str(n))

        node_dicts = [
            _unit_to_dict(x) if hasattr(x, "uid") else (
                dict(x) if hasattr(x, "__dict__") else str(x)
            )
            for x in nodes
        ]

        return {"nodes": node_dicts, "edges": edges, "entities": entities, "events": events}

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
