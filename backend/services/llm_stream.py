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
    disable_thinking: bool = False,
) -> AsyncIterator[Dict[str, str]]:
    """流式调用 OpenAI 兼容接口。

    注意：reasoning 模型（qwen3 / deepseek-r1 等）的 ``max_tokens`` 必须包含
    thinking + content 两部分。qwen3.5:9b 的 thinking 通常占 1500-3000 token，
    因此默认给 4096，避免只输出 thinking 不输出 content 时被截断。

    ``disable_thinking=True`` 时, 在请求体加 ``chat_template_kwargs``:
    Qwen 系列模型会读 ``enable_thinking=false`` 来关闭 thinking,
    deepseek-r1 等也可能支持 (取决于部署版本).
    关闭 thinking 后, 模型直接走 ``delta.content``, 不再产生
    ``delta.reasoning``, 也就不会陷入 thinking 死循环.

    Yields:
        dict: ``{"kind": "thinking" | "token", "text": str}``
        - kind=thinking: 来自 ``delta.reasoning``（推理型模型如 qwen3、deepseek-r1）
        - kind=token: 来自 ``delta.content``（普通回答内容）
    """
    import httpx

    if not base_url or not model:
        raise ValueError("base_url 和 model 不能为空")
    # 兜底: reasoning 模型需要更大的 max_tokens, 避免只输出 thinking 不输出 content
    # qwen3.5:9b 在长 prompt 下 thinking 平均 10000-12000 token, response 100-700 token,
    # 总需求 10000-13000 token. 给 8192 较稳, 太小会卡死 thinking 跑不出来.
    effective_max_tokens = max_tokens if (max_tokens and max_tokens >= 4096) else 8192
    # 端点选择: ollama 用原生 /api/generate (字段是 thinking/response, 能正常输出答案)
    # OpenAI 兼容 /v1/chat/completions 在 ollama+qwen3.5 上有 bug: 一直只输出 reasoning 不出 content
    is_ollama = "11434" in (base_url or "")
    if is_ollama:
        url = base_url.rstrip("/").replace("/v1", "") + "/api/generate"
    else:
        url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body: Dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "stream": True,
    }
    if is_ollama:
        # ollama 原生 /api/generate 用 prompt 字段 (合并 system+user)
        prompt_parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                prompt_parts.append(f"### System:\n{content}\n\n")
            elif role == "user":
                prompt_parts.append(f"### User:\n{content}\n\n")
            elif role == "assistant":
                prompt_parts.append(f"### Assistant:\n{content}\n\n")
        prompt_parts.append("### Assistant:\n")
        body["prompt"] = "".join(prompt_parts)
        # ollama 原生 thinking 控制: 通过 prompt 末尾加 /no_think 或在 system 里加
        if disable_thinking:
            body["prompt"] = body["prompt"] + "/no_think "
        # options
        opts: Dict[str, Any] = {}
        if max_tokens:
            opts["num_predict"] = int(max_tokens)
        else:
            opts["num_predict"] = effective_max_tokens
        opts["temperature"] = temperature
        body["options"] = opts
    else:
        body["messages"] = messages
        if max_tokens:
            body["max_tokens"] = max_tokens
        else:
            # 未指定时给 4096，避免 reasoning 模型 thinking 截断
            body["max_tokens"] = effective_max_tokens
        if disable_thinking:
            # Qwen3 / deepseek-r1 等支持 chat_template_kwargs 控制 thinking
            body["chat_template_kwargs"] = {"enable_thinking": False}
            # 关闭 thinking 后, thinking 不再占 token, 给 2048 就够
            body["max_tokens"] = min(int(body["max_tokens"]), 2048)

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
                    if not line:
                        continue
                    if is_ollama:
                        # ollama 原生 API: 每行是 JSON 对象 {response, thinking, done}
                        if not line.startswith("{"):
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        thinking = obj.get("thinking")
                        if thinking:
                            yield {"kind": "thinking", "text": thinking}
                        content = obj.get("response")
                        if content:
                            yield {"kind": "token", "text": content}
                        if obj.get("done"):
                            return
                    else:
                        # OpenAI 兼容: data: {...} 格式
                        if not line.startswith("data:"):
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
                        # 注意: ollama 部署的 reasoning 模型可能 content="" 但 reasoning 有最终答案
                        content = delta.get("content")
                        if content is not None and content != "":
                            yield {"kind": "token", "text": content}


async def stream_with_thinking_fallback(
    profile: Dict[str, Any],
    messages: List[Dict[str, str]],
    disable_thinking: bool = False,
) -> AsyncIterator[Dict[str, str]]:
    """流式调用 LLM，并对 qwen3 等模型做兜底。

    现象：部分 qwen3 部署把所有内容（包含最终 answer）都放在
    ``delta.reasoning`` 字段，``delta.content`` 始终为空。
    兜底：检测到 reasoning 中出现 ``</think>`` 分隔符后，
    将分隔符之后的内容切到 ``token`` 通道。

    【防止 thinking 过度】reasoning 模型 (qwen3.5 / deepseek-r1) 在长
    上下文下极易陷入「thinking 反复推敲 → max_tokens 全部花在 thinking
    上 → 永远不输出 content」的死循环。
    本函数**保留完整 thinking** (不截断流), 而是采用「续接」策略:
    1) 第一轮完整接收 stream, 累计 thinking
    2) 若第一轮 thinking >= max_thinking_chars 且**完全没产出** content,
       自动构造一条「请立即停止推理」消息发起第二轮 (max_tokens 缩到
       2048 强制 LLM 短思考)
    3) 把两轮 thinking + 第二轮 content 全部 yield 给调用方
       (调用方完全无感, 看不到续接过程)

    重复检测: 仅在 thinking 中检测到「最近 200 字在 buffer 中出现 ≥ 2
    次」时才视为死循环, 此时直接 yield ``_loop_aborted`` 让 chat 端做
    兜底 (极少见, 正常续接已能解决大部分过度思考问题)。

    Yields:
        dict: ``{"kind": "thinking" | "token" | "_loop_aborted", "text": str}``
    """
    # 防过度思考参数 (可由 profile 覆盖)
    # 兜底阈值: thinking 累计到此长度强制收尾, 避免真死循环卡死前端
    # 设为 15000 - qwen3.5 在长 prompt (含 2000+ 字记忆) 下 thinking 约 9000-12000c
    # 短问题约 2000-3000c, 长问题 9000-13000c, 15000 是平衡点
    # 再大就纯死循环 (LLM 重复输出), 再小就提前截断把思考过程当答案
    max_thinking_chars = int(profile.get("max_thinking_chars", 15000))
    # disable_thinking 模式: ollama 不响应 /no_think, thinking 仍然会累积,
    # 跟默认模式一样给足阈值让 LLM 跑完. 真死循环 (重复检测) 仍会截断.
    repeat_window = 200   # 重复检测窗口
    repeat_min = 2        # 至少出现 N 次算重复

    base_url = profile.get("base_url")
    model = profile.get("model")
    api_key = profile.get("api_key")
    temperature = float(profile.get("temperature", 0.3))
    max_tokens = int(profile.get("max_tokens") or 4096)
    timeout_s = float(profile.get("timeout_s", 60))

    # ============ 第一轮: 边流边检测, 触发条件立刻 break + 续接 ============
    full_thinking = ""
    full_content = ""
    flush_done = False
    nudge_triggered = False
    # 如果用户要求关闭 thinking, 在 system prompt 里加 /no_think 引导 (双保险)
    # ollama 部署可能不响应 chat_template_kwargs, 但 system prompt 仍然有效
    _effective_messages = list(messages)
    if disable_thinking and _effective_messages and _effective_messages[0].get("role") == "system":
        _effective_messages[0] = {
            **(_effective_messages[0]),
            "content": (_effective_messages[0].get("content") or "")
                       + "\n\n[/no_think] 不要再展示思考/推理过程, 直接给出最终答案。"
        }
    try:
        async for piece in stream_chat(
            base_url=base_url, model=model, messages=_effective_messages,
            api_key=api_key, temperature=temperature,
            max_tokens=max_tokens, timeout_s=timeout_s,
            disable_thinking=disable_thinking,
        ):
            kind = piece.get("kind")
            text = piece.get("text") or ""

            if kind == "token":
                flush_done = True
                full_content += text
                yield piece
            elif kind == "thinking":
                # 重复检测 (用于真正的死循环, 而不是单纯长度过长)
                if len(full_thinking) >= repeat_window * (repeat_min + 1):
                    tail = full_thinking[-repeat_window:]
                    prior = full_thinking[:-repeat_window]
                    if prior.count(tail) >= repeat_min:
                        # 真正死循环, 兜底让 chat 端拼记忆原文
                        yield {"kind": "_loop_aborted",
                               "text": f"检测到 thinking 死循环 (重复 ≥ {repeat_min + 1} 次)"}
                        return
                full_thinking += text
                yield piece
                # 【关键】保留 thinking 完整不切分, 但 ollama+qwen3.5 把完整 answer
                # 放进 reasoning 字段, content 永远是空, 而且 LLM 不出 stop token
                # 导致 stream 一直跑直到 max_tokens. 解决方案:
                # - 默认模式: 把已积累的 reasoning 当 content yield (LLM 总是先思考后写答案, 答案在 reasoning 末尾)
                # - disable_thinking 模式: ollama 不响应 chat_template_kwargs, 等也没用,
                #   不 yield, 让 chat.py 兜底 (从记忆原文拼答案)
                if (not flush_done and not nudge_triggered
                        and len(full_thinking) >= max_thinking_chars):
                    nudge_triggered = True
                    from ..utils.logger import info as _info
                    if disable_thinking:
                        _info(f"disable_thinking 模式: thinking 已超 {max_thinking_chars}c 仍未出 content, "
                              f"放弃 LLM 输出, 让 chat.py 兜底 (从记忆原文拼答案)")
                        # 关键: 不 yield thinking 当 content, 也不设 full_content
                        # 让 chat.py 走到 5.5 兜底分支 (用 _format_context 拼正经答案)
                        break
                    _info(f"thinking 超阈值 {max_thinking_chars}c, 强制收尾: "
                          f"用已积累 reasoning 末尾作为 content yield")
                    # 默认模式: 完整 reasoning 末尾就是答案, 不切分不剥字符
                    full_content = full_thinking
                    flush_done = True
                    yield {"kind": "token", "text": full_thinking}
                    # 立即结束第一轮
                    break
            else:
                yield piece
    except Exception as exc:
        import traceback as _tb
        from ..utils.logger import warn
        warn(f"stream_with_thinking_fallback 第一轮出错: {exc}\n{_tb.format_exc()}")
        async for piece in stream_or_fallback_chat(profile, messages):
            yield piece
        return
    # 注: 已删除"续接第二轮"逻辑.
    # 原因: ollama+qwen3.5 把 answer 放进 reasoning, content 永远是空.
    # 第一轮 thinking 累计超阈值时, 已把整段 reasoning 一次性 yield 为 token,
    # 不需要再发起第二轮 (第二轮 LLM 仍然只 thinking 不出 content, 是死路).


async def stream_or_fallback_chat(
    profile: Dict[str, Any],
    messages: List[Dict[str, str]],
    disable_thinking: bool = False,
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
            disable_thinking=disable_thinking,
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
