"""LLM Profile 路由：管理多模型服务源。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from ..services import llm_profiles as profiles_svc

router = APIRouter(prefix="/api/llm", tags=["llm"])


class LLMProfilePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = None
    name: str = ""
    provider: str = "openai"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    temperature: float = 0.3
    max_tokens: int = 1024
    timeout_s: int = 60
    enabled: bool = True
    is_default: bool = False


@router.get("/profiles")
def list_profiles() -> List[Dict[str, Any]]:
    """列出所有 LLM profile（api_key 脱敏）。"""
    profiles_svc.ensure_default_profile()
    return profiles_svc.list_profiles()


@router.post("/profiles")
def upsert_profile(payload: LLMProfilePayload) -> Dict[str, Any]:
    """新建或更新 LLM profile。"""
    if not payload.model:
        raise HTTPException(status_code=400, detail="model 不能为空")
    if not payload.base_url:
        raise HTTPException(status_code=400, detail="base_url 不能为空")
    item = profiles_svc.upsert_profile(payload.model_dump())
    return item


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str) -> Dict[str, Any]:
    ok = profiles_svc.delete_profile(profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"profile 不存在: {profile_id}")
    return {"status": "ok", "deleted": profile_id}


@router.post("/profiles/{profile_id}/default")
def set_default(profile_id: str) -> Dict[str, Any]:
    """将该 profile 标记为默认。"""
    p = profiles_svc.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"profile 不存在: {profile_id}")
    p["is_default"] = True
    item = profiles_svc.upsert_profile(p)
    return item


@router.post("/profiles/{profile_id}/test")
def test_profile(profile_id: str) -> Dict[str, Any]:
    """连通性测试：用该 profile 发送一个最小 chat 请求。"""
    import httpx

    p = profiles_svc.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"profile 不存在: {profile_id}")
    if not p.get("base_url") or not p.get("model"):
        return {"ok": False, "error": "base_url/model 不能为空"}
    headers = {"Content-Type": "application/json"}
    if p.get("api_key"):
        headers["Authorization"] = f"Bearer {p['api_key']}"
    url = p["base_url"].rstrip("/") + "/chat/completions"
    body = {
        "model": p["model"],
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    try:
        with httpx.Client(timeout=float(p.get("timeout_s", 30))) as client:
            r = client.post(url, json=body, headers=headers)
        ok = r.status_code < 400
        snippet = (r.text or "")[:300]
        return {"ok": ok, "status": r.status_code, "snippet": snippet}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
