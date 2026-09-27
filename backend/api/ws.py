"""
WebSocket hub — all connected clients receive broadcast messages.
Used for live lineage graph node status updates.
"""
import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_clients: set[WebSocket] = set()

async def broadcast(payload: dict[str, Any]) -> None:
    """Send a JSON message to every connected WebSocket client."""
    if not _clients:
        return
    data = json.dumps(payload)
    dead = set()
    for ws in list(_clients):
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)

@router.websocket("/ws/status")
async def ws_status(websocket: WebSocket):
    await websocket.accept()
    _clients.add(websocket)
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
