"""系统管理路由：本地模型管理、远程 Milvus 配置/缓存、实体详情等。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from ..services import app_store, model_store
from ..services.mandol_service import mandol_service
from ..services.entity_extractor import entity_extractor

router = APIRouter(prefix="/api/system", tags=["system"])


# ---------------- 本地模型管理 ----------------
@router.get("/models/local")
def list_local_models() -> Dict[str, Any]:
    return model_store.list_local_models()


@router.get("/models/current")
def get_current_models() -> Dict[str, Any]:
    return model_store.current_models()


class SelectModelRequest(BaseModel):
    kind: str  # "embedder" | "reranker"
    path: str


@router.post("/models/select-local")
def select_local_model(req: SelectModelRequest) -> Dict[str, Any]:
    res = model_store.select_local_model(req.kind, req.path)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "选择失败"))
    return res


class ClearModelRequest(BaseModel):
    kind: str


@router.post("/models/clear-local")
def clear_local_model(req: ClearModelRequest) -> Dict[str, Any]:
    return model_store.clear_local_model(req.kind)


class OfflineModeRequest(BaseModel):
    enabled: bool


@router.post("/models/offline")
def set_offline_mode(req: OfflineModeRequest) -> Dict[str, Any]:
    return model_store.set_offline_mode(req.enabled)


# ---------------- 远程 Milvus 配置/缓存 ----------------
@router.get("/app-store/health")
def app_store_health() -> Dict[str, Any]:
    return app_store.healthcheck()


class ConfigPutRequest(BaseModel):
    key: str
    value: Any
    scope: str = "global"


@router.post("/app-store/config")
def put_config(req: ConfigPutRequest) -> Dict[str, Any]:
    ok = app_store.put_config(req.key, req.value, req.scope)
    return {"ok": ok, "key": req.key}


@router.get("/app-store/config/{key}")
def get_config(key: str) -> Dict[str, Any]:
    value = app_store.get_config(key)
    return {"key": key, "value": value}


@router.get("/app-store/config")
def list_config(prefix: str = "") -> Dict[str, Any]:
    return {"items": app_store.list_config(prefix)}


@router.delete("/app-store/config/{key}")
def delete_config(key: str) -> Dict[str, Any]:
    ok = app_store.delete_config(key)
    return {"ok": ok, "key": key}


class CacheSetRequest(BaseModel):
    key: str
    value: Any
    ttl: int = 0


@router.post("/app-store/cache")
def cache_set(req: CacheSetRequest) -> Dict[str, Any]:
    ok = app_store.cache_set(req.key, req.value, ttl=req.ttl)
    return {"ok": ok, "key": req.key}


@router.get("/app-store/cache/{key}")
def cache_get(key: str) -> Dict[str, Any]:
    return {"key": key, "value": app_store.cache_get(key)}


@router.delete("/app-store/cache")
def cache_clear(prefix: str = "") -> Dict[str, Any]:
    n = app_store.cache_clear(prefix)
    return {"deleted": n}


# ---------------- 实体抽取 ----------------
class ExtractRequest(BaseModel):
    text: str
    max_chars: int = 6000


@router.post("/extract/entities")
def extract_entities(req: ExtractRequest) -> Dict[str, Any]:
    """对一段文本运行 LLM 实体/关系/事件抽取（不写入 Mandol）。"""
    result = entity_extractor.extract(req.text, max_chars=req.max_chars)
    return {
        "entities": result.get("entities", []),
        "relations": result.get("relations", []),
        "events": result.get("events", []),
        "stats": entity_extractor.last_stats,
    }


class ExtractStoreRequest(BaseModel):
    text: str
    source_doc: str = ""
    project_id: Optional[str] = None
    space_name: Optional[str] = None


@router.post("/extract/entities-and-store")
def extract_and_store(req: ExtractStoreRequest) -> Dict[str, Any]:
    """抽取并写入 Mandol 记忆单元（同步触发 build_high_level）。"""
    return entity_extractor.extract_and_store(
        text=req.text,
        source_doc=req.source_doc,
        project_id=req.project_id,
        space_name=req.space_name,
    )


# ---------------- 实体/事件详情 ----------------
@router.get("/entity/{uid}")
def get_entity_detail(uid: str) -> Dict[str, Any]:
    """根据 UID 读取实体/事件的详细内容。"""
    if not mandol_service.is_enabled:
        raise HTTPException(status_code=503, detail="Mandol 未启用")
    try:
        mandol_service._ensure_initialized()
        unit = mandol_service.get_unit(uid)
        if not unit:
            raise HTTPException(status_code=404, detail=f"实体不存在: {uid}")
        # 尝试通过 Neo4j 拿到关联
        edges: List[Dict[str, Any]] = []
        try:
            system = mandol_service._require()
            neighbors = system.graph.get_neighbors(uid, max_hops=1)
            for n in neighbors or []:
                edges.append({
                    "source": n.source.uid,
                    "target": n.target.uid,
                    "relation": getattr(n, "relation_type", None) or getattr(n, "type", ""),
                })
        except Exception:
            pass
        return {"unit": unit, "edges": edges}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
