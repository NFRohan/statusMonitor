from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
import redis.asyncio as redis
import asyncio
import os
import json
from typing import Dict, Set, Optional

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_CHANNEL_PREFIX = "metrics:"

class ConnectionManager:
    def __init__(self):
        # Map: user_id -> set of (websocket, agent_id_filter)
        self.user_connections: Dict[int, Set[tuple]] = {}
        # Map: websocket -> (user_id, agent_id_filter)
        self.connection_info: Dict[WebSocket, tuple] = {}

    async def connect(self, websocket: WebSocket, user_id: int, agent_id: Optional[int] = None):
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add((websocket, agent_id))
        self.connection_info[websocket] = (user_id, agent_id)
        print(f"Client connected: user_id={user_id}, agent_id_filter={agent_id}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connection_info:
            user_id, agent_id = self.connection_info[websocket]
            if user_id in self.user_connections:
                self.user_connections[user_id].discard((websocket, agent_id))
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            del self.connection_info[websocket]
            print(f"Client disconnected: user_id={user_id}")

    async def send_to_user(self, user_id: int, message: str, agent_id: int):
        """Send message to all connections for a user, filtering by agent_id if specified"""
        if user_id not in self.user_connections:
            return
        
        for websocket, agent_id_filter in list(self.user_connections[user_id]):
            # Send if no filter, or if agent_id matches filter
            if agent_id_filter is None or agent_id_filter == agent_id:
                try:
                    await websocket.send_text(message)
                except Exception:
                    pass

    def get_subscribed_user_ids(self) -> Set[int]:
        """Get all user IDs that have active connections"""
        return set(self.user_connections.keys())

manager = ConnectionManager()

async def redis_subscriber():
    """Subscribe to all user channels and distribute messages"""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        pubsub = r.pubsub()
        
        # Use pattern subscription to listen to all metrics:* channels
        await pubsub.psubscribe(f"{REDIS_CHANNEL_PREFIX}*")
        print(f"Subscribed to Redis pattern: {REDIS_CHANNEL_PREFIX}*")

        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                # Extract user_id from channel name (metrics:{user_id})
                channel = message["channel"]
                try:
                    user_id = int(channel.split(":")[-1])
                    data = json.loads(message["data"])
                    agent_id = data.get("agent_id")
                    await manager.send_to_user(user_id, message["data"], agent_id)
                except (ValueError, json.JSONDecodeError) as e:
                    print(f"Error processing message: {e}")
    except Exception as e:
        print(f"Redis subscriber error: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_subscriber())

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int = Query(...),
    agent_id: Optional[int] = Query(None)
):
    """
    WebSocket endpoint for receiving metrics.
    - user_id: Required, the user ID to receive metrics for
    - agent_id: Optional, filter to only receive metrics from a specific agent
    """
    await manager.connect(websocket, user_id, agent_id)
    try:
        while True:
            # Keep the connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@app.get("/health")
def health():
    total_connections = sum(len(conns) for conns in manager.user_connections.values())
    return {
        "status": "ok",
        "total_connections": total_connections,
        "users_connected": len(manager.user_connections)
    }
