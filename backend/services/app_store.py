"""使用远程 Milvus 存储应用配置项与缓存 KV 数据。

设计上把应用层的配置/缓存与 Mandol 记忆单元隔离在不同的 collection，
以避免 schema 冲突。当远程 Milvus 不可用时回退到本地 JSON 文件。

Collection 结构（统一）：
- codex_config: 应用配置项（key, value, scope, updated_at, value_vec）
- codex_cache:  任意 KV 缓存（key, value, ttl, updated_at, value_vec）

其中 value_vec 字段保存 value 字符串的 embedding 向量，便于按语义检索
历史配置/缓存记录（可选，目前先做存储不做语义检索）。
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.settings import settings
from ..utils.logger import info, warn

# 本地回退存储
_LOCAL_CONFIG_PATH = Path("data/app_config.json")
_LOCAL_CACHE_PATH = Path("data/app_cache.json")

_LOCK = threading.RLock()
_CLIENT = None
_CLIENT_LOCK = threading.Lock()
_EMBEDDING_DIM = 384  # 与 MilvusUnitStore 默认一致


# ------------------- 客户端 -------------------
def _get_milvus_client():
    """懒加载 pymilvus 客户端。返回 None 表示不可用（回退到本地）。"""
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is not None:
            return _CLIENT
        if not settings.app_milvus_remote_enabled:
            return None
        try:
            from pymilvus import MilvusClient  # type: ignore
        except Exception as exc:
            warn(f"pymilvus 未安装，应用配置将回退到本地: {exc}")
            return None
        try:
            uri = settings.app_milvus_uri or "http://localhost:19530"
            client = MilvusClient(
                uri=uri,
                user=settings.app_milvus_user or None,
                password=settings.app_milvus_password or None,
                db_name=settings.app_milvus_db or "default",
                token=settings.app_milvus_token or None,
                secure=settings.app_milvus_secure,
            )
            # 探测可用性
            client.list_collections()
            _CLIENT = client
            info(f"已连接远程 Milvus: {uri}")
            return _CLIENT
        except Exception as exc:
            warn(f"连接远程 Milvus 失败，将回退到本地: {exc}")
            return None


def _ensure_collection(client, name: str) -> None:
    if client.has_collection(name):
        return
    client.create_collection(
        collection_name=name,
        dimension=_EMBEDDING_DIM,
        primary_field_name="key",
        vector_field_name="value_vec",
        id_type="string",
        metric_type="COSINE",
        enable_dynamic_field=True,
    )


def _vectorize(text: str) -> List[float]:
    """把 value 字符串编码为向量；失败则返回零向量。"""
    if not text:
        return [0.0] * _EMBEDDING_DIM
    try:
        from .mandol_service import mandol_service
        if mandol_service.is_enabled:
            mandol_service._ensure_initialized()
            system = mandol_service.system
            if system is not None:
                embedder = system.semantic_map.get_embedder()
                if embedder is not None:
                    vec = embedder.embed([text])
                    arr = vec[0] if vec else None
                    if arr is not None and len(arr) >= _EMBEDDING_DIM:
                        return [float(x) for x in arr[:_EMBEDDING_DIM]]
    except Exception:
        pass
    # fallback: 伪向量（重复归一化 hash），仅保证维度
    h = abs(hash(text)) % (10 ** 8)
    base = (h % 1000) / 1000.0
    return [base] * _EMBEDDING_DIM


# ------------------- 配置项 -------------------
def put_config(key: str, value: Any, scope: str = "global") -> bool:
    """写入配置项。value 必须是 JSON 可序列化对象。"""
    payload = json.dumps(value, ensure_ascii=False, default=str)
    record = {
        "key": key,
        "value": payload,
        "scope": scope,
        "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "value_vec": _vectorize(payload),
    }
    client = _get_milvus_client()
    if client is not None:
        try:
            _ensure_collection(client, settings.app_milvus_config_collection)
            client.upsert(
                collection_name=settings.app_milvus_config_collection,
                data=[record],
            )
            return True
        except Exception as exc:
            warn(f"Milvus 写入配置失败: {exc}")
    # 回退到本地
    with _LOCK:
        data: Dict[str, Any] = {}
        if _LOCAL_CONFIG_PATH.exists():
            try:
                data = json.loads(_LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[key] = {"value": value, "scope": scope,
                     "updated_at": record["updated_at"]}
        _LOCAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LOCAL_CONFIG_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    return True


def get_config(key: str, default: Any = None) -> Any:
    """读取配置项，反序列化为 Python 对象。"""
    client = _get_milvus_client()
    if client is not None:
        try:
            _ensure_collection(client, settings.app_milvus_config_collection)
            res = client.get(
                collection_name=settings.app_milvus_config_collection,
                ids=[key],
            )
            if res and len(res) > 0:
                return json.loads(res[0].get("value", "null"))
        except Exception as exc:
            warn(f"Milvus 读取配置失败: {exc}")
    # 回退到本地
    if _LOCAL_CONFIG_PATH.exists():
        try:
            data = json.loads(_LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
            rec = data.get(key)
            if rec is not None:
                return rec.get("value", default)
        except Exception:
            pass
    return default


def list_config(prefix: str = "") -> Dict[str, Any]:
    """列出所有配置项（按前缀过滤）。"""
    client = _get_milvus_client()
    out: Dict[str, Any] = {}
    if client is not None:
        try:
            _ensure_collection(client, settings.app_milvus_config_collection)
            res = client.query(
                collection_name=settings.app_milvus_config_collection,
                filter="",
                output_fields=["key", "value", "scope", "updated_at"],
                limit=10000,
            )
            for rec in res or []:
                k = rec.get("key", "")
                if prefix and not k.startswith(prefix):
                    continue
                try:
                    out[k] = {
                        "value": json.loads(rec.get("value", "null")),
                        "scope": rec.get("scope", "global"),
                        "updated_at": rec.get("updated_at", ""),
                    }
                except Exception:
                    continue
            return out
        except Exception as exc:
            warn(f"Milvus 列出配置失败: {exc}")
    if _LOCAL_CONFIG_PATH.exists():
        try:
            data = json.loads(_LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
            for k, v in data.items():
                if prefix and not k.startswith(prefix):
                    continue
                out[k] = v
        except Exception:
            pass
    return out


def delete_config(key: str) -> bool:
    client = _get_milvus_client()
    if client is not None:
        try:
            _ensure_collection(client, settings.app_milvus_config_collection)
            client.delete(
                collection_name=settings.app_milvus_config_collection,
                ids=[key],
            )
            return True
        except Exception as exc:
            warn(f"Milvus 删除配置失败: {exc}")
    with _LOCK:
        if _LOCAL_CONFIG_PATH.exists():
            try:
                data = json.loads(_LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
                if key in data:
                    del data[key]
                    _LOCAL_CONFIG_PATH.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8",
                    )
                    return True
            except Exception:
                pass
    return False


# ------------------- 缓存 -------------------
def cache_get(key: str) -> Optional[Any]:
    client = _get_milvus_client()
    if client is not None:
        try:
            _ensure_collection(client, settings.app_milvus_cache_collection)
            res = client.get(
                collection_name=settings.app_milvus_cache_collection,
                ids=[key],
            )
            if res and len(res) > 0:
                rec = res[0]
                ttl = int(rec.get("ttl", 0))
                if ttl > 0:
                    updated = rec.get("updated_at", "")
                    try:
                        ts = datetime.fromisoformat(updated).timestamp()
                        if time.time() - ts > ttl:
                            client.delete(
                                collection_name=settings.app_milvus_cache_collection,
                                ids=[key],
                            )
                            return None
                    except Exception:
                        pass
                return json.loads(rec.get("value", "null"))
        except Exception as exc:
            warn(f"Milvus 缓存读取失败: {exc}")
    if _LOCAL_CACHE_PATH.exists():
        try:
            data = json.loads(_LOCAL_CACHE_PATH.read_text(encoding="utf-8"))
            rec = data.get(key)
            if rec is None:
                return None
            ttl = int(rec.get("ttl", 0))
            if ttl > 0:
                try:
                    ts = datetime.fromisoformat(rec.get("updated_at", "")).timestamp()
                    if time.time() - ts > ttl:
                        return None
                except Exception:
                    pass
            return rec.get("value")
        except Exception:
            return None
    return None


def cache_set(key: str, value: Any, ttl: int = 0) -> bool:
    payload = json.dumps(value, ensure_ascii=False, default=str)
    record = {
        "key": key,
        "value": payload,
        "ttl": int(ttl),
        "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "value_vec": _vectorize(payload),
    }
    client = _get_milvus_client()
    if client is not None:
        try:
            _ensure_collection(client, settings.app_milvus_cache_collection)
            client.upsert(
                collection_name=settings.app_milvus_cache_collection,
                data=[record],
            )
            return True
        except Exception as exc:
            warn(f"Milvus 缓存写入失败: {exc}")
    with _LOCK:
        data: Dict[str, Any] = {}
        if _LOCAL_CACHE_PATH.exists():
            try:
                data = json.loads(_LOCAL_CACHE_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[key] = record
        _LOCAL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LOCAL_CACHE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    return True


def cache_clear(prefix: str = "") -> int:
    """清空缓存；可选按前缀。返回删除条数。"""
    n = 0
    client = _get_milvus_client()
    if client is not None:
        try:
            _ensure_collection(client, settings.app_milvus_cache_collection)
            res = client.query(
                collection_name=settings.app_milvus_cache_collection,
                filter="",
                output_fields=["key"],
                limit=100000,
            )
            ids = [r.get("key") for r in res or []
                   if r.get("key") and (not prefix or r.get("key", "").startswith(prefix))]
            if ids:
                client.delete(
                    collection_name=settings.app_milvus_cache_collection,
                    ids=ids,
                )
                n = len(ids)
            return n
        except Exception as exc:
            warn(f"Milvus 清空缓存失败: {exc}")
    with _LOCK:
        if not _LOCAL_CACHE_PATH.exists():
            return 0
        try:
            data = json.loads(_LOCAL_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return 0
        if not prefix:
            n = len(data)
            _LOCAL_CACHE_PATH.unlink(missing_ok=True)
            return n
        keys = [k for k in data if k.startswith(prefix)]
        for k in keys:
            del data[k]
        _LOCAL_CACHE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return len(keys)


# ------------------- 健康检查 -------------------
def healthcheck() -> Dict[str, Any]:
    """返回 Milvus 配置/缓存的连接状态。"""
    client = _get_milvus_client()
    return {
        "remote_enabled": settings.app_milvus_remote_enabled,
        "uri": settings.app_milvus_uri,
        "connected": client is not None,
        "config_collection": settings.app_milvus_config_collection,
        "cache_collection": settings.app_milvus_cache_collection,
        "fallback_path": str(_LOCAL_CONFIG_PATH),
    }
