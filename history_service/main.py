from fastapi import FastAPI, Query, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import asyncio
import os
import json
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from pydantic import BaseModel

app = FastAPI()

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_CHANNEL_PREFIX = "metrics:"

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "statusmonitor-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "statusmonitor")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "metrics")

# InfluxDB client
influx_client = None
write_api = None
query_api = None

def init_influxdb():
    global influx_client, write_api, query_api
    try:
        influx_client = InfluxDBClient(
            url=INFLUXDB_URL,
            token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORG
        )
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        query_api = influx_client.query_api()
        print(f"Connected to InfluxDB at {INFLUXDB_URL}")
        return True
    except Exception as e:
        print(f"Failed to connect to InfluxDB: {e}")
        return False

def store_metrics(data: dict):
    """Store metrics in InfluxDB"""
    if not write_api:
        return
    
    try:
        agent_id = data.get("agent_id")
        user_id = data.get("user_id")
        agent_name = data.get("agent_name", "unknown")
        timestamp = datetime.fromtimestamp(data.get("timestamp", datetime.now(timezone.utc).timestamp()), tz=timezone.utc)
        
        points = []
        
        # CPU metrics
        if "cpu" in data:
            cpu = data["cpu"]
            point = Point("cpu") \
                .tag("agent_id", str(agent_id)) \
                .tag("user_id", str(user_id)) \
                .tag("agent_name", agent_name) \
                .field("usage_percent", float(cpu.get("usage_percent", 0))) \
                .time(timestamp)
            points.append(point)
            
            # Per-core usage
            per_core = cpu.get("per_core_usage", [])
            for i, core_usage in enumerate(per_core):
                core_point = Point("cpu_core") \
                    .tag("agent_id", str(agent_id)) \
                    .tag("user_id", str(user_id)) \
                    .tag("core", str(i)) \
                    .field("usage_percent", float(core_usage)) \
                    .time(timestamp)
                points.append(core_point)
        
        # Memory metrics
        if "memory" in data:
            mem = data["memory"]
            point = Point("memory") \
                .tag("agent_id", str(agent_id)) \
                .tag("user_id", str(user_id)) \
                .tag("agent_name", agent_name) \
                .field("used_percent", float(mem.get("used_percent", 0))) \
                .field("total", int(mem.get("total", 0))) \
                .field("available", int(mem.get("available", 0))) \
                .time(timestamp)
            points.append(point)
        
        # Disk metrics
        if "disk" in data:
            disk = data["disk"]
            for partition in disk.get("partitions", []):
                point = Point("disk") \
                    .tag("agent_id", str(agent_id)) \
                    .tag("user_id", str(user_id)) \
                    .tag("mountpoint", partition.get("mountpoint", "unknown")) \
                    .tag("device", partition.get("device", "unknown")) \
                    .field("percent", float(partition.get("percent", 0))) \
                    .field("total", int(partition.get("total", 0))) \
                    .field("used", int(partition.get("used", 0))) \
                    .field("free", int(partition.get("free", 0))) \
                    .time(timestamp)
                points.append(point)
        
        # Network metrics
        if "network" in data:
            net = data["network"]
            point = Point("network") \
                .tag("agent_id", str(agent_id)) \
                .tag("user_id", str(user_id)) \
                .tag("agent_name", agent_name) \
                .field("bytes_sent", int(net.get("bytes_sent", 0))) \
                .field("bytes_recv", int(net.get("bytes_recv", 0))) \
                .field("packets_sent", int(net.get("packets_sent", 0))) \
                .field("packets_recv", int(net.get("packets_recv", 0))) \
                .time(timestamp)
            points.append(point)
        
        # Write all points
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=points)
        
    except Exception as e:
        print(f"Error storing metrics: {e}")

async def redis_subscriber():
    """Subscribe to all user metric channels and store in InfluxDB"""
    while True:
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
            pubsub = r.pubsub()
            
            await pubsub.psubscribe(f"{REDIS_CHANNEL_PREFIX}*")
            print(f"History service subscribed to Redis pattern: {REDIS_CHANNEL_PREFIX}*")

            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is not None and message["type"] == "pmessage":
                    try:
                        data = json.loads(message["data"])
                        store_metrics(data)
                    except json.JSONDecodeError as e:
                        print(f"Error parsing message: {e}")
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Redis subscriber error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    init_influxdb()
    asyncio.create_task(redis_subscriber())

@app.on_event("shutdown")
async def shutdown_event():
    if influx_client:
        influx_client.close()

# Auth helper
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Validate token and return current user"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authentication")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/users/me",
                headers={"Authorization": authorization},
                timeout=5.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            return response.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Auth service unavailable")

async def verify_agent_ownership(user_id: int, agent_id: int) -> bool:
    """Check if agent belongs to user via auth service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/agents/{agent_id}",
                headers={"Authorization": f"internal-check"},  # Internal call
                timeout=5.0
            )
            if response.status_code == 200:
                agent = response.json()
                # Check user_id in InfluxDB tags instead (agent stored with user_id)
                return True  # For now, verify via query filter
    except Exception:
        pass
    return True  # Fallback: will be filtered by user_id in query

# Response models
class MetricPoint(BaseModel):
    time: str
    value: float

class HistoryResponse(BaseModel):
    metric: str
    agent_id: int
    data: List[MetricPoint]

@app.get("/history/{agent_id}/cpu")
async def get_cpu_history(
    agent_id: int,
    start: Optional[str] = Query("-1h", description="Start time (e.g., -1h, -24h, -7d)"),
    stop: Optional[str] = Query("now()", description="Stop time"),
    interval: Optional[str] = Query("1m", description="Aggregation interval"),
    current_user: dict = Depends(get_current_user)
):
    """Get CPU usage history for an agent (authenticated, ownership enforced)"""
    if not query_api:
        raise HTTPException(status_code=503, detail="InfluxDB not available")
    
    user_id = current_user["id"]
    
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: {start}, stop: {stop})
        |> filter(fn: (r) => r["_measurement"] == "cpu")
        |> filter(fn: (r) => r["agent_id"] == "{agent_id}")
        |> filter(fn: (r) => r["user_id"] == "{user_id}")
        |> filter(fn: (r) => r["_field"] == "usage_percent")
        |> aggregateWindow(every: {interval}, fn: mean, createEmpty: false)
        |> yield(name: "mean")
    '''
    
    try:
        tables = query_api.query(query, org=INFLUXDB_ORG)
        data = []
        for table in tables:
            for record in table.records:
                data.append({
                    "time": record.get_time().isoformat(),
                    "value": record.get_value()
                })
        return {"metric": "cpu", "agent_id": agent_id, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{agent_id}/memory")
async def get_memory_history(
    agent_id: int,
    start: Optional[str] = Query("-1h", description="Start time"),
    stop: Optional[str] = Query("now()", description="Stop time"),
    interval: Optional[str] = Query("1m", description="Aggregation interval"),
    current_user: dict = Depends(get_current_user)
):
    """Get memory usage history for an agent (authenticated, ownership enforced)"""
    if not query_api:
        raise HTTPException(status_code=503, detail="InfluxDB not available")
    
    user_id = current_user["id"]
    
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: {start}, stop: {stop})
        |> filter(fn: (r) => r["_measurement"] == "memory")
        |> filter(fn: (r) => r["agent_id"] == "{agent_id}")
        |> filter(fn: (r) => r["user_id"] == "{user_id}")
        |> filter(fn: (r) => r["_field"] == "used_percent")
        |> aggregateWindow(every: {interval}, fn: mean, createEmpty: false)
        |> yield(name: "mean")
    '''
    
    try:
        tables = query_api.query(query, org=INFLUXDB_ORG)
        data = []
        for table in tables:
            for record in table.records:
                data.append({
                    "time": record.get_time().isoformat(),
                    "value": record.get_value()
                })
        return {"metric": "memory", "agent_id": agent_id, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{agent_id}/disk")
async def get_disk_history(
    agent_id: int,
    mountpoint: Optional[str] = Query(None, description="Filter by mountpoint"),
    start: Optional[str] = Query("-1h", description="Start time"),
    stop: Optional[str] = Query("now()", description="Stop time"),
    interval: Optional[str] = Query("5m", description="Aggregation interval"),
    current_user: dict = Depends(get_current_user)
):
    """Get disk usage history for an agent (authenticated, ownership enforced)"""
    if not query_api:
        raise HTTPException(status_code=503, detail="InfluxDB not available")
    
    user_id = current_user["id"]
    mountpoint_filter = f'|> filter(fn: (r) => r["mountpoint"] == "{mountpoint}")' if mountpoint else ""
    
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: {start}, stop: {stop})
        |> filter(fn: (r) => r["_measurement"] == "disk")
        |> filter(fn: (r) => r["agent_id"] == "{agent_id}")
        |> filter(fn: (r) => r["user_id"] == "{user_id}")
        |> filter(fn: (r) => r["_field"] == "percent")
        {mountpoint_filter}
        |> aggregateWindow(every: {interval}, fn: mean, createEmpty: false)
        |> yield(name: "mean")
    '''
    
    try:
        tables = query_api.query(query, org=INFLUXDB_ORG)
        data = []
        for table in tables:
            for record in table.records:
                data.append({
                    "time": record.get_time().isoformat(),
                    "value": record.get_value(),
                    "mountpoint": record.values.get("mountpoint", "unknown")
                })
        return {"metric": "disk", "agent_id": agent_id, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{agent_id}/network")
async def get_network_history(
    agent_id: int,
    start: Optional[str] = Query("-1h", description="Start time"),
    stop: Optional[str] = Query("now()", description="Stop time"),
    interval: Optional[str] = Query("1m", description="Aggregation interval"),
    current_user: dict = Depends(get_current_user)
):
    """Get network usage history for an agent (authenticated, ownership enforced)"""
    if not query_api:
        raise HTTPException(status_code=503, detail="InfluxDB not available")
    
    user_id = current_user["id"]
    
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: {start}, stop: {stop})
        |> filter(fn: (r) => r["_measurement"] == "network")
        |> filter(fn: (r) => r["agent_id"] == "{agent_id}")
        |> filter(fn: (r) => r["user_id"] == "{user_id}")
        |> filter(fn: (r) => r["_field"] == "bytes_sent" or r["_field"] == "bytes_recv")
        |> aggregateWindow(every: {interval}, fn: last, createEmpty: false)
        |> yield(name: "last")
    '''
    
    try:
        tables = query_api.query(query, org=INFLUXDB_ORG)
        sent_data = []
        recv_data = []
        for table in tables:
            for record in table.records:
                point = {
                    "time": record.get_time().isoformat(),
                    "value": record.get_value()
                }
                if record.get_field() == "bytes_sent":
                    sent_data.append(point)
                else:
                    recv_data.append(point)
        return {
            "metric": "network",
            "agent_id": agent_id,
            "bytes_sent": sent_data,
            "bytes_recv": recv_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{agent_id}/summary")
async def get_summary(
    agent_id: int,
    start: Optional[str] = Query("-24h", description="Start time"),
    stop: Optional[str] = Query("now()", description="Stop time"),
    current_user: dict = Depends(get_current_user)
):
    """Get summary statistics for an agent (authenticated, ownership enforced)"""
    if not query_api:
        raise HTTPException(status_code=503, detail="InfluxDB not available")
    
    user_id = current_user["id"]
    
    try:
        # CPU stats
        cpu_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {start}, stop: {stop})
            |> filter(fn: (r) => r["_measurement"] == "cpu")
            |> filter(fn: (r) => r["agent_id"] == "{agent_id}")
            |> filter(fn: (r) => r["user_id"] == "{user_id}")
            |> filter(fn: (r) => r["_field"] == "usage_percent")
        '''
        
        cpu_tables = query_api.query(cpu_query, org=INFLUXDB_ORG)
        cpu_values = [record.get_value() for table in cpu_tables for record in table.records]
        
        # Memory stats
        mem_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {start}, stop: {stop})
            |> filter(fn: (r) => r["_measurement"] == "memory")
            |> filter(fn: (r) => r["agent_id"] == "{agent_id}")
            |> filter(fn: (r) => r["user_id"] == "{user_id}")
            |> filter(fn: (r) => r["_field"] == "used_percent")
        '''
        
        mem_tables = query_api.query(mem_query, org=INFLUXDB_ORG)
        mem_values = [record.get_value() for table in mem_tables for record in table.records]
        
        return {
            "agent_id": agent_id,
            "period": {"start": start, "stop": stop},
            "cpu": {
                "avg": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                "max": max(cpu_values) if cpu_values else 0,
                "min": min(cpu_values) if cpu_values else 0,
                "data_points": len(cpu_values)
            },
            "memory": {
                "avg": sum(mem_values) / len(mem_values) if mem_values else 0,
                "max": max(mem_values) if mem_values else 0,
                "min": min(mem_values) if mem_values else 0,
                "data_points": len(mem_values)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    influx_status = "connected" if influx_client else "disconnected"
    return {"status": "ok", "influxdb": influx_status}
