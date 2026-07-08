"""聊天路由：基于 Mandol 的溯源问答 + WebSocket 流式输出。

优先使用 Mandol 的 ask/ask_with_hits 能力，当 Mandol 未启用时
回退到传统 agent_service。
"""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from ..models.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    MemoryResult,
)
from ..services.agent_service import agent_service
from ..services.mandol_service import mandol_service
from ..utils.logger import warn
from ..database import db

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _hit_to_memory_result(hit: dict) -> MemoryResult:
    """将 Mandol 检索命中转换为 MemoryResult。"""
    metadata = hit.get("metadata", {}) or {}
    return MemoryResult(
        rel_path=metadata.get("source_path", "") or f"mandol:{hit.get('uid', '')}",
        title=metadata.get("entity_name") or metadata.get("event_name") or hit.get("uid", ""),
        snippet=(hit.get("text") or "")[:240],
        score=hit.get("score", 0.0),
        memory_type=metadata.get("type"),
        uid=hit.get("uid"),
        text=hit.get("text"),
        metadata=metadata,
        raw_data=hit.get("raw_data"),
        scores=hit.get("scores"),
        ranks=hit.get("ranks"),
    )


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """智能问答：优先使用 Mandol ask，回退到 agent_service。"""
    # 优先使用 Mandol
    if mandol_service.is_enabled:
        try:
            data = mandol_service.ask(
                req.message,
                top_k=req.top_k,
                use_rerank=req.use_rerank,
                system_prompt=req.system_prompt,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
            memories = [_hit_to_memory_result(h) for h in data.get("hits", [])]
            # 保存到聊天历史
            db.save_message("mandol", "user", req.message)
            db.save_message("mandol", "assistant", data["answer"],
                            memories=[m.model_dump() for m in memories])
            return ChatResponse(
                response=data["answer"],
                memories_used=memories,
                status="ok",
            )
        except Exception as exc:
            warn(f"Mandol 问答失败，回退到 agent: {exc}")

    # 回退到传统 agent
    try:
        context = [m.model_dump() for m in req.context]
        result = await agent_service.run_agent(req.agent, req.message, context=context)
        return ChatResponse(
            response=result["response"],
            memories_used=[MemoryResult(**m) for m in result.get("memories", [])],
            thinking=result.get("thinking"),
            status="ok",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/history/{agent_id}")
def history(agent_id: str, limit: int = 50) -> List[dict]:
    """获取聊天历史。"""
    return db.load_history(agent_id, limit=limit)


@router.websocket("/stream/{agent_id}")
async def stream_chat(websocket: WebSocket, agent_id: str) -> None:
    """WebSocket 流式聊天：先推送检索命中，再流式输出答案。"""
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "content": "无效的 JSON"})
                continue
            message = payload.get("message", "").strip()
            if not message:
                await websocket.send_json({"type": "error", "content": "消息为空"})
                continue

            top_k = payload.get("top_k", 5)
            use_rerank = payload.get("use_rerank", True)
            system_prompt = payload.get("system_prompt")
            temperature = payload.get("temperature", 0.3)
            max_tokens = payload.get("max_tokens")

            # 优先使用 Mandol 流式
            if mandol_service.is_enabled:
                try:
                    full_text = ""
                    memories = []
                    async for event in _stream_mandol(
                        message, top_k=top_k, use_rerank=use_rerank,
                        system_prompt=system_prompt, temperature=temperature,
                        max_tokens=max_tokens,
                    ):
                        evt_type, content = event
                        if evt_type == "hit":
                            memories.append(content)
                            await websocket.send_json({
                                "type": "memories",
                                "content": content,
                            })
                        elif evt_type == "token":
                            full_text += content
                            await websocket.send_json({
                                "type": "chunk",
                                "content": content,
                            })
                        elif evt_type == "done":
                            await websocket.send_json({
                                "type": "done",
                                "content": "",
                                "memories": memories,
                            })
                            # 保存历史
                            db.save_message(agent_id, "user", message)
                            db.save_message(agent_id, "assistant", full_text,
                                            memories=memories)
                    continue
                except Exception as exc:
                    warn(f"Mandol 流式问答失败，回退到 agent: {exc}")

            # 回退到传统 agent 流式
            context = payload.get("context") or []
            try:
                async for event in agent_service.stream_agent(agent_id, message, context=context):
                    if event["type"] == "memories":
                        await websocket.send_json({
                            "type": "memories",
                            "content": event["content"],
                        })
                    elif event["type"] == "thinking":
                        await websocket.send_json({
                            "type": "thinking",
                            "content": event["content"],
                        })
                    elif event["type"] == "chunk":
                        await websocket.send_json({
                            "type": "chunk",
                            "content": event["content"],
                        })
                    elif event["type"] == "done":
                        await websocket.send_json({
                            "type": "done",
                            "content": "",
                            "memories": event.get("memories", []),
                        })
            except ValueError as exc:
                await websocket.send_json({"type": "error", "content": str(exc)})
    except WebSocketDisconnect:
        return


async def _stream_mandol(
    query: str,
    top_k: int = 5,
    use_rerank: bool = True,
    system_prompt: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
):
    """将同步的 mandol_service.ask_stream 包装为异步迭代器。"""
    import asyncio
    loop = asyncio.get_event_loop()
    # 在线程中运行同步生成器
    gen = mandol_service.ask_stream(
        query, top_k=top_k, use_rerank=use_rerank,
        system_prompt=system_prompt, temperature=temperature,
        max_tokens=max_tokens,
    )

    # 使用队列桥接同步生成器与异步迭代
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    def _run():
        try:
            for evt_type, content in gen:
                loop.call_soon_threadsafe(queue.put_nowait, (evt_type, content))
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, (None, sentinel))

    import threading
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    while True:
        evt_type, content = await queue.get()
        if evt_type is None and content is sentinel:
            break
        if evt_type == "error":
            raise RuntimeError(content)
        yield (evt_type, content)
