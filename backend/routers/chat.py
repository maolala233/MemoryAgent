"""Chat router: synchronous chat + WebSocket streaming."""
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
from ..database import db

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
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
    return db.load_history(agent_id, limit=limit)


@router.websocket("/stream/{agent_id}")
async def stream_chat(websocket: WebSocket, agent_id: str) -> None:
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "content": "Invalid JSON"})
                continue
            message = payload.get("message", "").strip()
            context = payload.get("context") or []
            if not message:
                await websocket.send_json({"type": "error", "content": "Empty message"})
                continue
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
