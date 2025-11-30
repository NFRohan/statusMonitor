from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
import redis.asyncio as redis
import asyncio
import os
import json
import httpx
from typing import Dict, Set, Optional

app = FastAPI()

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")

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

async def validate_token(token: str) -> Optional[dict]:
    """Validate JWT token with auth service and return user info"""
    if not token:
        return None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/users/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"Token validation error: {e}")
    return None

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
    """Subscribe to all user channels and distribute messages with auto-reconnect"""
    while True:
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
            pubsub = r.pubsub()
            
            # Use pattern subscription to listen to all metrics:* channels
            await pubsub.psubscribe(f"{REDIS_CHANNEL_PREFIX}*")
            print(f"Subscribed to Redis pattern: {REDIS_CHANNEL_PREFIX}*")

            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is not None and message["type"] == "pmessage":
                    # Extract user_id from channel name (metrics:{user_id})
                    channel = message["channel"]
                    try:
                        user_id = int(channel.split(":")[-1])
                        data = json.loads(message["data"])
                        agent_id = data.get("agent_id")
                        await manager.send_to_user(user_id, message["data"], agent_id)
                    except (ValueError, json.JSONDecodeError) as e:
                        print(f"Error processing message: {e}")
                await asyncio.sleep(0.01)  # Small delay to prevent busy loop
        except Exception as e:
            print(f"Redis subscriber error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_subscriber())

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    agent_id: Optional[int] = Query(None)
):
    """
    WebSocket endpoint for receiving metrics.
    - token: Required, JWT access token for authentication
    - agent_id: Optional, filter to only receive metrics from a specific agent
    """
    # Validate token before accepting connection
    user = await validate_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    user_id = user["id"]
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
