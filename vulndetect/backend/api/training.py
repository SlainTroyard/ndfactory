"""Training WebSocket + API"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

router = APIRouter(prefix="/ws", tags=["training"])

active_connections: dict = {}


@router.websocket("/experiments/{experiment_id}/training")
async def training_websocket(websocket: WebSocket, experiment_id: int):
    await websocket.accept()
    active_connections[experiment_id] = websocket
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        active_connections.pop(experiment_id, None)


async def push_training_update(experiment_id: int, data: dict):
    if experiment_id in active_connections:
        try:
            await active_connections[experiment_id].send_text(json.dumps(data))
        except Exception:
            active_connections.pop(experiment_id, None)
