from fastapi import FastAPI, HTTPException, Request, Header
from typing import Optional
from aiokafka import AIOKafkaProducer
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

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = "metrics"
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")

# Kafka producer (initialized at startup)
kafka_producer: Optional[AIOKafkaProducer] = None

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

@app.on_event("startup")
async def startup_event():
    """Initialize Kafka producer on startup"""
    global kafka_producer
    
    print(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}...")
    kafka_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all'  # Wait for all replicas to acknowledge
    )
    
    # Retry connection with backoff
    max_retries = 10
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            await kafka_producer.start()
            print(f"Connected to Kafka at {KAFKA_BOOTSTRAP_SERVERS}")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Kafka connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                import asyncio
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)
            else:
                print(f"Failed to connect to Kafka after {max_retries} attempts")
                kafka_producer = None

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup Kafka producer on shutdown"""
    global kafka_producer
    if kafka_producer:
        await kafka_producer.stop()
        print("Kafka producer stopped")

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
    
    # Publish to Kafka
    if not kafka_producer:
        raise HTTPException(status_code=503, detail="Metrics broker unavailable")
    
    try:
        # Use agent_id as partition key to ensure ordering per agent
        await kafka_producer.send_and_wait(
            topic=KAFKA_TOPIC,
            key=str(token_info["agent_id"]),
            value=data
        )
    except Exception as e:
        print(f"Error publishing to Kafka: {e}")
        raise HTTPException(status_code=503, detail="Failed to publish metrics")
            
    return {"status": "received"}

@app.get("/health")
def health():
    kafka_status = "connected" if kafka_producer else "disconnected"
    return {
        "status": "ok",
        "kafka": kafka_status
    }
