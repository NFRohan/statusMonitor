from fastapi import FastAPI, HTTPException, Request
import redis
import json
import os

app = FastAPI()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_CHANNEL = "system_metrics"

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    redis_client.ping()
    print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except redis.ConnectionError:
    print(f"Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
    redis_client = None

@app.post("/ingest")
async def ingest_metrics(request: Request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Basic validation
    if "agent_id" not in data or "timestamp" not in data:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Publish to Redis
    if redis_client:
        try:
            redis_client.publish(REDIS_CHANNEL, json.dumps(data))
        except redis.ConnectionError:
            print("Error publishing to Redis")
            
            
    return {"status": "received"}

@app.get("/health")
def health():
    return {"status": "ok", "redis": "connected" if redis_client and redis_client.ping() else "disconnected"}
