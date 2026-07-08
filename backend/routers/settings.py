"""设置路由：模型配置（LLM/embedder/reranker）+ Mandol 系统参数动态配置。

支持前端动态配置并热重载 Mandol 系统。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, HTTPException

from ..config.settings import settings
from ..services.config_loader import get_models_config, save_models_config
from ..services.mandol_service import mandol_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


class LLMConfig(BaseModel):
    model: str = "gpt-4o-mini"
    base_url: str = ""
    api_key: str = ""
    temperature: float = 0.3
    max_tokens: int = 1024


class EmbedderConfig(BaseModel):
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    device: str = "cpu"
    dimension: int = 384
    use_remote: bool = False
    remote_base_url: str = ""
    remote_api_path: str = "/v1/embeddings"
    remote_timeout: int = 60


class RerankerConfig(BaseModel):
    model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    device: str = "cpu"
    use_remote: bool = False
    remote_base_url: str = ""
    remote_api_path: str = "/v1/rerank"
    remote_timeout: int = 60


class SystemParams(BaseModel):
    chunk_max_tokens: int = 512
    session_time_gap_seconds: int = 1800
    session_check_interval: int = 20
    session_max_pending: int = 100
    similarity_top_k: int = 5
    similarity_threshold: float = 0.7
    similarity_recent_window: int = 20
    bfs_expansion_per_seed: int = 3
    bfs_expansion_hops: int = 1
    max_context_units: int = 20
    max_entities_per_llm: int = 50
    max_events_per_llm: int = 50
    promote_threshold: int = 100
    use_unified_pipeline: bool = True


class MandolConfigRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    storage_dir: str = ""
    enable_persistence: bool = True
    auto_save_interval: int = 300
    llm: LLMConfig = LLMConfig()
    embedder: EmbedderConfig = EmbedderConfig()
    reranker: RerankerConfig = RerankerConfig()
    system: SystemParams = SystemParams()


class SettingsConfigRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mandol: MandolConfigRequest = MandolConfigRequest()


@router.get("/config")
def get_config():
    """获取当前配置。"""
    return {
        "mandol": {
            "enabled": settings.mandol_enabled,
            "storage_dir": str(settings.mandol_storage_dir),
            "enable_persistence": settings.mandol_enable_persistence,
            "auto_save_interval": settings.mandol_auto_save_interval,
            "llm": {
                "model": settings.mandol_llm_model,
                "base_url": settings.mandol_llm_base_url,
                "api_key": "***" if settings.mandol_llm_api_key else "",
                "temperature": 0.3,
                "max_tokens": 1024,
            },
            "embedder": {
                "model": settings.mandol_embedder_model,
                "device": settings.mandol_embedder_device,
                "dimension": settings.mandol_embedder_dim,
                "use_remote": settings.mandol_use_remote_embedder,
                "remote_base_url": settings.mandol_embedder_remote_base_url,
                "remote_api_path": settings.mandol_embedder_remote_api_path,
                "remote_timeout": settings.mandol_embedder_remote_timeout,
            },
            "reranker": {
                "model": settings.mandol_reranker_model,
                "device": settings.mandol_reranker_device,
                "use_remote": settings.mandol_use_remote_reranker,
                "remote_base_url": settings.mandol_reranker_remote_base_url,
                "remote_api_path": settings.mandol_reranker_remote_api_path,
                "remote_timeout": settings.mandol_reranker_remote_timeout,
            },
            "system": {
                "chunk_max_tokens": settings.mandol_chunk_max_tokens,
                "session_time_gap_seconds": settings.mandol_session_time_gap_seconds,
                "session_check_interval": settings.mandol_session_check_interval,
                "session_max_pending": settings.mandol_session_max_pending,
                "similarity_top_k": settings.mandol_similarity_top_k,
                "similarity_threshold": settings.mandol_similarity_threshold,
                "similarity_recent_window": settings.mandol_similarity_recent_window,
                "bfs_expansion_per_seed": settings.mandol_bfs_expansion_per_seed,
                "bfs_expansion_hops": settings.mandol_bfs_expansion_hops,
                "max_context_units": settings.mandol_max_context_units,
                "max_entities_per_llm": settings.mandol_max_entities_per_llm,
                "max_events_per_llm": settings.mandol_max_events_per_llm,
                "promote_threshold": settings.mandol_promote_threshold,
                "use_unified_pipeline": settings.mandol_use_unified_pipeline,
            },
        },
        "is_ready": mandol_service.is_ready,
    }


@router.post("/config")
def update_config(req: SettingsConfigRequest):
    """更新配置并热重载 Mandol 系统。"""
    try:
        import json as _json
        from logging import getLogger as _getLogger
        _getLogger("codex_memory").info(f"收到配置请求: {_json.dumps(req.model_dump(), default=str)[:500]}")
        m = req.mandol
        # 基础配置
        settings.mandol_enabled = m.enabled
        if m.storage_dir:
            settings.mandol_storage_dir = m.storage_dir
        settings.mandol_enable_persistence = m.enable_persistence
        settings.mandol_auto_save_interval = m.auto_save_interval

        # LLM
        settings.mandol_llm_model = m.llm.model
        settings.mandol_llm_base_url = m.llm.base_url
        if m.llm.api_key and m.llm.api_key != "***":
            settings.mandol_llm_api_key = m.llm.api_key

        # Embedder
        settings.mandol_embedder_model = m.embedder.model
        settings.mandol_embedder_device = m.embedder.device
        settings.mandol_embedder_dim = m.embedder.dimension
        settings.mandol_use_remote_embedder = m.embedder.use_remote
        settings.mandol_embedder_remote_base_url = m.embedder.remote_base_url
        settings.mandol_embedder_remote_api_path = m.embedder.remote_api_path
        settings.mandol_embedder_remote_timeout = m.embedder.remote_timeout

        # Reranker
        settings.mandol_reranker_model = m.reranker.model
        settings.mandol_reranker_device = m.reranker.device
        settings.mandol_use_remote_reranker = m.reranker.use_remote
        settings.mandol_reranker_remote_base_url = m.reranker.remote_base_url
        settings.mandol_reranker_remote_api_path = m.reranker.remote_api_path
        settings.mandol_reranker_remote_timeout = m.reranker.remote_timeout

        # 系统参数
        s = m.system
        settings.mandol_chunk_max_tokens = s.chunk_max_tokens
        settings.mandol_session_time_gap_seconds = s.session_time_gap_seconds
        settings.mandol_session_check_interval = s.session_check_interval
        settings.mandol_session_max_pending = s.session_max_pending
        settings.mandol_similarity_top_k = s.similarity_top_k
        settings.mandol_similarity_threshold = s.similarity_threshold
        settings.mandol_similarity_recent_window = s.similarity_recent_window
        settings.mandol_bfs_expansion_per_seed = s.bfs_expansion_per_seed
        settings.mandol_bfs_expansion_hops = s.bfs_expansion_hops
        settings.mandol_max_context_units = s.max_context_units
        settings.mandol_max_entities_per_llm = s.max_entities_per_llm
        settings.mandol_max_events_per_llm = s.max_events_per_llm
        settings.mandol_promote_threshold = s.promote_threshold
        settings.mandol_use_unified_pipeline = s.use_unified_pipeline

        # 更新启用状态
        if m.enabled and not mandol_service.is_enabled:
            mandol_service.initialize()
        elif not m.enabled and mandol_service.is_enabled:
            mandol_service.shutdown()

        return {"status": "ok", "message": "配置已保存。如需应用模型变更，请点击「热重载」按钮。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconfigure")
def reconfigure():
    """手动触发 Mandol 热重载。"""
    try:
        ok = mandol_service.reconfigure()
        if not ok:
            raise HTTPException(status_code=500, detail="重新配置失败")
        return {"status": "ok", "message": "Mandol 系统已重新配置"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers/test")
def test_providers():
    """测试模型提供者连通性。"""
    result = {"llm": False, "embedder": False, "reranker": False}
    if not mandol_service.is_enabled:
        return result
    try:
        # 触发初始化
        mandol_service._ensure_initialized()
        system = mandol_service.system
        if system is None:
            return result
        if system.llm is not None:
            result["llm"] = True
        if system.semantic_map.get_embedder() is not None:
            result["embedder"] = True
        if system.semantic_map.get_reranker() is not None:
            result["reranker"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return result
