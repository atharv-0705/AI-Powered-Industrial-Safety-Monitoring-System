"""
Low-Latency WebSocket Streaming Transport (SRS §2.1, FR-21, Week 10 deliverable).

Streams real-time CV pipeline telemetry, bounding boxes, risk scores,
violation alerts, and live video frames to connected frontend clients.
Supports bidirectional control commands from the React dashboard.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("safety-ai-mvp.websocket")
router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections for low-latency broadcast."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast_json(self, data: dict[str, Any]):
        """Broadcasts a JSON telemetry payload to all connected clients."""
        if not self.active_connections:
            return

        dead_connections = set()
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                dead_connections.add(connection)

        for dead in dead_connections:
            self.disconnect(dead)

    async def broadcast_frame_and_telemetry(
        self,
        frame_jpeg_bytes: bytes,
        telemetry: dict[str, Any],
    ):
        """Broadcasts live frame with synchronized telemetry packet."""
        if not self.active_connections:
            return

        # Base64 encode keyframe for web canvas rendering
        b64_frame = base64.b64encode(frame_jpeg_bytes).decode("utf-8")
        packet = {
            "type": "FRAME_UPDATE",
            "frame": f"data:image/jpeg;base64,{b64_frame}",
            "telemetry": telemetry,
        }
        await self.broadcast_json(packet)


manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    return manager


@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    """Primary bidirectional streaming endpoint for the frontend dashboard."""
    await manager.connect(websocket)
    try:
        # Send initial handshake connection confirmation
        await websocket.send_json({
            "type": "HANDSHAKE",
            "status": "connected",
            "message": "Connected to Multimodal Safety AI live stream.",
        })

        while True:
            # Receive client ping, zone update, or control commands
            raw_text = await websocket.receive_text()
            try:
                cmd = json.loads(raw_text)
                cmd_type = cmd.get("type", "ping").lower()

                if cmd_type == "ping":
                    await websocket.send_json({"type": "PONG", "timestamp": cmd.get("timestamp")})
                else:
                    logger.debug(f"Received client command: {cmd_type}")
                    await websocket.send_json({"type": "ACK", "command": cmd_type})
            except json.JSONDecodeError:
                await websocket.send_json({"type": "PONG"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        manager.disconnect(websocket)
