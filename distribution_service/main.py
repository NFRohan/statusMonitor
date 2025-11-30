from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import redis.asyncio as redis
import asyncio
import os
import json
from typing import List

app = FastAPI()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_CHANNEL = "system_metrics"

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Handle disconnected clients that weren't cleanly removed
                pass

manager = ConnectionManager()

async def redis_subscriber():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(REDIS_CHANNEL)
        print(f"Subscribed to Redis channel: {REDIS_CHANNEL}")

        async for message in pubsub.listen():
            if message["type"] == "message":
                await manager.broadcast(message["data"])
    except Exception as e:
        print(f"Redis subscriber error: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_subscriber())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection open. We don't expect messages from client, but we need to await something.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@app.get("/health")
def health():
    return {"status": "ok", "connections": len(manager.active_connections)}
