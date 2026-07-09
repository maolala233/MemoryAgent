"""LLM Profile 管理：支持多模型服务源（OpenAI 兼容接口）。

profile 存储为 JSON 文件，路径由 settings.llm_profiles_path 指定。
每个 profile 描述一个 LLM 服务端点（API key、base_url、model 等），
前端可增删改；chat 路由根据 profile_id 选择对应 provider。
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.settings import settings

_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _profiles_path() -> Path:
    path = Path(settings.llm_profiles_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_all() -> List[Dict[str, Any]]:
    p = _profiles_path()
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f) or []
    except Exception:
        return []


def _write_all(profiles: List[Dict[str, Any]]) -> None:
    p = _profiles_path()
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    tmp.replace(p)


def list_profiles() -> List[Dict[str, Any]]:
    """列出所有 profile（api_key 脱敏为 ***）。"""
    with _LOCK:
        items = _read_all()
    out = []
    for p in items:
        d = dict(p)
        if d.get("api_key"):
            d["api_key"] = "***"
        out.append(d)
    return out


def get_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    """按 id 获取 profile（包含完整 api_key）。"""
    with _LOCK:
        for p in _read_all():
            if p.get("id") == profile_id:
                return dict(p)
    return None


def upsert_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    """新建或更新 profile。

    - 若 payload 含 id：按 id 更新；若 api_key 为 "***" 表示不修改。
    - 若 payload 不含 id：自动生成 id。
    - 必填：name, base_url, model
    """
    with _LOCK:
        items = _read_all()
        pid = payload.get("id") or f"llm_{uuid.uuid4().hex[:8]}"
        idx = next((i for i, p in enumerate(items) if p.get("id") == pid), -1)
        existing = items[idx] if idx >= 0 else {}
        api_key = payload.get("api_key", existing.get("api_key", ""))
        # 客户端传 "***" 表示保留原值
        if api_key == "***":
            api_key = existing.get("api_key", "")
        new_item = {
            "id": pid,
            "name": payload.get("name") or existing.get("name") or "未命名",
            "provider": payload.get("provider", existing.get("provider", "openai")),
            "base_url": payload.get("base_url", existing.get("base_url", "")),
            "model": payload.get("model", existing.get("model", "")),
            "api_key": api_key,
            "temperature": float(payload.get("temperature", existing.get("temperature", 0.3))),
            "max_tokens": int(payload.get("max_tokens", existing.get("max_tokens", 1024))),
            "timeout_s": int(payload.get("timeout_s", existing.get("timeout_s", 60))),
            "enabled": bool(payload.get("enabled", existing.get("enabled", True))),
            "is_default": bool(payload.get("is_default", existing.get("is_default", False))),
            "updated_at": _now_iso(),
            "created_at": existing.get("created_at") or _now_iso(),
        }
        if idx >= 0:
            items[idx] = new_item
        else:
            items.append(new_item)
        # 若该 profile 标记为默认，清除其它默认
        if new_item["is_default"]:
            for p in items:
                if p.get("id") != pid:
                    p["is_default"] = False
        _write_all(items)
        resp = dict(new_item)
        if resp.get("api_key"):
            resp["api_key"] = "***"
        return resp


def delete_profile(profile_id: str) -> bool:
    with _LOCK:
        items = _read_all()
        new_items = [p for p in items if p.get("id") != profile_id]
        if len(new_items) == len(items):
            return False
        _write_all(new_items)
        return True


def get_default_profile() -> Optional[Dict[str, Any]]:
    """获取默认 profile（is_default=True），否则返回第一个 enabled 的。"""
    with _LOCK:
        items = _read_all()
    for p in items:
        if p.get("is_default") and p.get("enabled", True):
            return dict(p)
    for p in items:
        if p.get("enabled", True):
            return dict(p)
    return None


def ensure_default_profile() -> Optional[Dict[str, Any]]:
    """确保至少有一个可用的 profile；首次启动根据 settings.mandol_llm_* 自动创建一个。"""
    with _LOCK:
        items = _read_all()
    if items:
        return None
    base = {
        "id": "llm_default",
        "name": "默认模型",
        "provider": "openai",
        "base_url": settings.mandol_llm_base_url or "",
        "model": settings.mandol_llm_model or "gpt-4o-mini",
        "api_key": settings.mandol_llm_api_key or "",
        "temperature": 0.3,
        "max_tokens": 1024,
        "timeout_s": 60,
        "enabled": True,
        "is_default": True,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    with _LOCK:
        _write_all([base])
    return base
