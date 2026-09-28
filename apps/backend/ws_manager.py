"""WebSocket manager for real-time telemetry and event broadcasting."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("aeromind.websocket")


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self) -> None:
        # General connections (telemetry + events)
        self._connections: list[WebSocket] = []
        # Mission-specific connections
        self._mission_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(f"WebSocket connected: {len(self._connections)} total")

    async def connect_mission(self, websocket: WebSocket, mission_id: str) -> None:
        await websocket.accept()
        self._mission_connections.setdefault(mission_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
        for conns in self._mission_connections.values():
            if websocket in conns:
                conns.remove(websocket)
        logger.info(f"WebSocket disconnected: {len(self._connections)} remaining")

    async def broadcast(self, channel: str, data: dict[str, Any]) -> None:
        """Broadcast to all connected clients."""
        message = json.dumps({"channel": channel, "data": data}, default=str)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_mission(self, mission_id: str, channel: str, data: dict[str, Any]) -> None:
        """Broadcast to clients watching a specific mission."""
        message = json.dumps({"channel": channel, "data": data}, default=str)
        conns = self._mission_connections.get(mission_id, [])
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in conns:
                conns.remove(ws)

    async def broadcast_telemetry(self, telemetry_data: dict) -> None:
        """Broadcast telemetry update."""
        await self.broadcast("telemetry", telemetry_data)

    async def broadcast_event(self, event_data: dict) -> None:
        """Broadcast an event to all clients."""
        await self.broadcast("event", event_data)

    async def broadcast_approval_request(self, approval_data: dict) -> None:
        """Broadcast an approval request."""
        await self.broadcast("approval_request", approval_data)

    @property
    def connection_count(self) -> int:
        return len(self._connections)
