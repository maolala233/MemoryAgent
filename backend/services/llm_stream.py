"""真正的 LLM 流式输出客户端：直接用 httpx 调 OpenAI 兼容 SSE。

mandol 自带的 OpenAICompatibleLLMProvider 没有 chat_stream 方法，
本模块提供不依赖 mandol 内部 LLM 的流式能力：
- 支持任意 LLMProfile
- 逐 token yield 字符串
- 失败回退到非流式
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List, Optional


async def stream_chat(
    *,
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    api_key: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    timeout_s: float = 60.0,
) -> AsyncIterator[Dict[str, str]]:
    """流式调用 OpenAI 兼容接口。

    注意：reasoning 模型（qwen3 / deepseek-r1 等）的 ``max_tokens`` 必须包含
    thinking + content 两部分。qwen3.5:9b 的 thinking 通常占 1500-3000 token，
    因此默认给 4096，避免只输出 thinking 不输出 content 时被截断。

    Yields:
        dict: ``{"kind": "thinking" | "token", "text": str}``
        - kind=thinking: 来自 ``delta.reasoning``（推理型模型如 qwen3、deepseek-r1）
        - kind=token: 来自 ``delta.content``（普通回答内容）
    """
    import httpx

    if not base_url or not model:
        raise ValueError("base_url 和 model 不能为空")
    # 兜底：reasoning 模型需要更大的 max_tokens，避免只输出 thinking 不输出 content
    effective_max_tokens = max_tokens if (max_tokens and max_tokens >= 2048) else 4096
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if max_tokens:
        body["max_tokens"] = max_tokens
    else:
        # 未指定时给 4096，避免 reasoning 模型 thinking 截断
        body["max_tokens"] = effective_max_tokens

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        async with client.stream("POST", url, json=body, headers=headers) as resp:
            if resp.status_code >= 400:
                txt = await resp.aread()
                raise RuntimeError(
                    f"LLM HTTP {resp.status_code}: {txt.decode('utf-8', errors='ignore')[:400]}"
                )
            buffer = ""
            async for chunk in resp.aiter_text():
                if not chunk:
                    continue
                buffer += chunk
                # 按行解析 SSE
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    # 1) 思考内容（reasoning models: qwen3 / deepseek-r1 等）
                    thinking = delta.get("reasoning")
                    if thinking:
                        yield {"kind": "thinking", "text": thinking}
                    # 2) 正常回答内容
                    content = delta.get("content")
                    if content:
                        yield {"kind": "token", "text": content}


async def stream_with_thinking_fallback(
    profile: Dict[str, Any],
    messages: List[Dict[str, str]],
) -> AsyncIterator[Dict[str, str]]:
    """流式调用 LLM，并对 qwen3 等模型做兜底。

    现象：部分 qwen3 部署把所有内容（包含最终 answer）都放在
    ``delta.reasoning`` 字段，``delta.content`` 始终为空。
    兜底：检测到 reasoning 中出现 ``</think>`` 分隔符后，
    将分隔符之后的内容切到 ``token`` 通道。

    Yields:
        dict: ``{"kind": "thinking" | "token", "text": str}``
    """
    buffer_pending = ""  # reasoning 中尚未切分到 token 的部分
    flush_done = False
    try:
        async for piece in stream_chat(
            base_url=profile.get("base_url"),
            model=profile.get("model"),
            messages=messages,
            api_key=profile.get("api_key"),
            temperature=float(profile.get("temperature", 0.3)),
            max_tokens=int(profile.get("max_tokens") or 1024),
            timeout_s=float(profile.get("timeout_s", 60)),
        ):
            kind = piece.get("kind")
            text = piece.get("text") or ""
            if kind == "token":
                # 一旦出现过 token，兜底逻辑可以关闭
                flush_done = True
                yield piece
            elif kind == "thinking":
                if flush_done:
                    yield piece
                    continue
                buffer_pending += text
                # 实时 yield 当前这段 thinking（前端可以流式展示推理过程）
                yield piece
                # 寻找 </think> 分隔符；找到则把分隔符之后切到 token 通道
                idx = buffer_pending.find("</think>")
                if idx >= 0:
                    tail = buffer_pending[idx + len("</think>"):]
                    buffer_pending = ""
                    flush_done = True
                    if tail:
                        yield {"kind": "token", "text": tail}
            else:
                yield piece
        return
    except Exception as exc:
        import traceback as _tb
        from ..utils.logger import warn
        warn(f"stream_with_thinking_fallback 出错: {exc}\n{_tb.format_exc()}")
        # 任意错误回退到原始 stream_or_fallback
        async for piece in stream_or_fallback_chat(profile, messages):
            yield piece
        return


async def stream_or_fallback_chat(
    profile: Dict[str, Any],
    messages: List[Dict[str, str]],
) -> AsyncIterator[Dict[str, str]]:
    """流式调用 LLM，失败时回退到非流式整段输出。

    Yields:
        dict: ``{"kind": "thinking" | "token", "text": str}``
    """
    base_url = profile.get("base_url")
    model = profile.get("model")
    api_key = profile.get("api_key")
    temperature = float(profile.get("temperature", 0.3))
    max_tokens = profile.get("max_tokens") or 1024
    timeout_s = float(profile.get("timeout_s", 60))

    try:
        async for piece in stream_chat(
            base_url=base_url,
            model=model,
            messages=messages,
            api_key=api_key,
            temperature=temperature,
            max_tokens=int(max_tokens),
            timeout_s=timeout_s,
        ):
            yield piece
        return
    except Exception as exc:
        # 回退：一次性调
        import httpx
        url = base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": int(max_tokens),
        }
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
            obj = r.json()
        content = (
            (obj.get("choices") or [{}])[0]
            .get("message", {})
            .get("content", "")
        ) or f"[LLM 调用失败，已回退]: {exc}"
        # 按字符切片流式 yield
        chunk = 8
        for i in range(0, len(content), chunk):
            yield {"kind": "token", "text": content[i : i + chunk]}


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中英文混合按字符/1.5 计）。"""
    if not text:
        return 0
    return max(1, int(len(text) / 1.5))


def messages_token_count(messages: List[Dict[str, str]]) -> int:
    return sum(estimate_tokens(m.get("content", "")) for m in messages) + 4 * len(messages)
