from fastapi import FastAPI, HTTPException, Request, Header
from typing import Optional
import redis
import json
import os
import httpx

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
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")
REDIS_CHANNEL_PREFIX = "metrics:"  # metrics:{user_id}

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    redis_client.ping()
    print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except redis.ConnectionError:
    print(f"Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
    redis_client = None

async def validate_agent_token(token: str) -> dict:
    """Validate agent token with auth service"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/agents/validate-token",
                params={"token": token}
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error validating token: {e}")
    return {"valid": False}

@app.post("/ingest")
async def ingest_metrics(
    request: Request,
    x_agent_token: Optional[str] = Header(None, alias="X-Agent-Token")
):
    # Validate agent token
    if not x_agent_token:
        raise HTTPException(status_code=401, detail="Missing agent token")
    
    token_info = await validate_agent_token(x_agent_token)
    if not token_info.get("valid"):
        raise HTTPException(status_code=401, detail="Invalid agent token")
    
    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Basic validation
    if "timestamp" not in data:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Add agent info to the data
    data["agent_id"] = token_info["agent_id"]
    data["agent_name"] = token_info["agent_name"]
    data["user_id"] = token_info["user_id"]
    
    # Publish to user-specific Redis channel
    if not redis_client:
        raise HTTPException(status_code=503, detail="Metrics storage unavailable")
    
    try:
        user_channel = f"{REDIS_CHANNEL_PREFIX}{token_info['user_id']}"
        redis_client.publish(user_channel, json.dumps(data))
    except redis.ConnectionError as e:
        print(f"Error publishing to Redis: {e}")
        raise HTTPException(status_code=503, detail="Failed to store metrics")
            
    return {"status": "received"}

@app.get("/health")
def health():
    return {"status": "ok", "redis": "connected" if redis_client and redis_client.ping() else "disconnected"}
