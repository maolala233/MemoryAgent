"""WebSocket connection manager for broadcasting vault updates."""
from __future__ import annotations

import asyncio
import json
from typing import List, Optional

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def send_to_client(self, websocket: WebSocket, message: dict) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)

    async def broadcast(self, message: dict, exclude: Optional[WebSocket] = None) -> None:
        if not self._connections:
            return
        dead: List[WebSocket] = []
        tasks = []
        for ws in self._connections:
            if ws is exclude:
                continue
            tasks.append(self._safe_send(ws, message, dead))
        if tasks:
            await asyncio.gather(*tasks)
        for ws in dead:
            self.disconnect(ws)

    async def _safe_send(self, ws: WebSocket, message: dict, dead: List[WebSocket]) -> None:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)

    def get_active_connections(self) -> int:
        return len(self._connections)


ws_manager = ConnectionManager()
