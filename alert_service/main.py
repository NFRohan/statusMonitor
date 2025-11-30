from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
import database
import redis
import json
import threading
import os
import time
from telegram_bot import send_telegram_message
import requests

app = FastAPI()

# Create tables
models.Base.metadata.create_all(bind=database.engine)

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")

# Cache for rules to avoid DB hits on every metric
# Structure: {agent_id: [rule1, rule2, ...]}
RULES_CACHE = {}
# Cache for recipients
# Structure: {user_id: chat_id}
RECIPIENTS_CACHE = {}
# Cooldown tracker: {rule_id: last_triggered_timestamp}
COOLDOWN_TRACKER = {}
COOLDOWN_SECONDS = 300  # 5 minutes cooldown

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authentication")
    
    try:
        # Verify token with auth service
        response = requests.get(
            f"{AUTH_SERVICE_URL}/users/me",
            headers={"Authorization": authorization}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication failed")

def refresh_caches():
    """Reload rules and recipients from DB to memory"""
    db = database.SessionLocal()
    try:
        # Refresh Rules
        rules = db.query(models.AlertRule).filter(models.AlertRule.enabled == True).all()
        new_rules_cache = {}
        for rule in rules:
            if rule.agent_id not in new_rules_cache:
                new_rules_cache[rule.agent_id] = []
            new_rules_cache[rule.agent_id].append({
                "id": rule.id,
                "metric_type": rule.metric_type,
                "condition": rule.condition,
                "threshold": rule.threshold,
                "user_id": rule.user_id
            })
        global RULES_CACHE
        RULES_CACHE = new_rules_cache

        # Refresh Recipients
        recipients = db.query(models.AlertRecipient).filter(models.AlertRecipient.enabled == True).all()
        new_recipients_cache = {}
        for recipient in recipients:
            if recipient.telegram_chat_id:
                new_recipients_cache[recipient.user_id] = recipient.telegram_chat_id
        global RECIPIENTS_CACHE
        RECIPIENTS_CACHE = new_recipients_cache
    finally:
        db.close()

def check_metrics(data):
    """Evaluate metrics against rules"""
    agent_id = str(data.get("agent_id"))
    user_id = data.get("user_id")
    
    if agent_id not in RULES_CACHE:
        return

    rules = RULES_CACHE[agent_id]
    
    for rule in rules:
        # Check cooldown
        last_triggered = COOLDOWN_TRACKER.get(rule["id"], 0)
        if time.time() - last_triggered < COOLDOWN_SECONDS:
            continue

        triggered = False
        current_value = 0
        
        # Extract value based on metric type
        if rule["metric_type"] == "cpu":
            current_value = data.get("cpu", {}).get("usage_percent", 0)
        elif rule["metric_type"] == "memory":
            current_value = data.get("memory", {}).get("usage_percent", data.get("memory", {}).get("percent", 0))
        elif rule["metric_type"] == "disk":
            current_value = data.get("disk", {}).get("usage_percent", data.get("disk", {}).get("percent", 0))
            
        # Evaluate condition
        if rule["condition"] == "gt" and current_value > rule["threshold"]:
            triggered = True
        elif rule["condition"] == "lt" and current_value < rule["threshold"]:
            triggered = True
            
        if triggered:
            # Send Alert
            chat_id = RECIPIENTS_CACHE.get(rule["user_id"])
            if chat_id:
                agent_name = data.get("agent_name", "Unknown Agent")
                msg = f"🚨 *Alert for {agent_name}*\n\n"
                msg += f"Metric: {rule['metric_type'].upper()}\n"
                msg += f"Current Value: {current_value:.1f}%\n"
                msg += f"Threshold: {'>' if rule['condition'] == 'gt' else '<'} {rule['threshold']}%\n"
                
                if send_telegram_message(chat_id, msg):
                    COOLDOWN_TRACKER[rule["id"]] = time.time()
                    
                    # Log to history (optional, async to not block)
                    # db = database.SessionLocal()
                    # history = models.AlertHistory(rule_id=rule["id"], agent_id=agent_id, message=msg)
                    # db.add(history)
                    # db.commit()
                    # db.close()

def redis_listener():
    """Background task to listen for metrics"""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
        pubsub = r.pubsub()
        pubsub.psubscribe("metrics:*")
        
        print("Started Redis listener for alerts")
        
        for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    data = json.loads(message["data"])
                    check_metrics(data)
                except Exception as e:
                    pass  # Silently ignore malformed messages
    except Exception as e:
        print(f"Redis listener failed: {e}")

@app.on_event("startup")
async def startup_event():
    refresh_caches()
    # Start Redis listener in background thread
    thread = threading.Thread(target=redis_listener, daemon=True)
    thread.start()

@app.get("/health")
def health():
    return {"status": "ok"}

# API Endpoints

@app.get("/rules", response_model=List[schemas.AlertRuleResponse])
def get_rules(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    return db.query(models.AlertRule).filter(models.AlertRule.user_id == current_user["id"]).all()

@app.post("/rules", response_model=schemas.AlertRuleResponse)
def create_rule(
    rule: schemas.AlertRuleCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    db_rule = models.AlertRule(**rule.dict(), user_id=current_user["id"])
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    refresh_caches()
    return db_rule

@app.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    rule = db.query(models.AlertRule).filter(
        models.AlertRule.id == rule_id,
        models.AlertRule.user_id == current_user["id"]
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(rule)
    db.commit()
    refresh_caches()
    return {"status": "deleted"}

@app.get("/recipient", response_model=Optional[schemas.AlertRecipientResponse])
def get_recipient(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    return db.query(models.AlertRecipient).filter(models.AlertRecipient.user_id == current_user["id"]).first()

@app.post("/recipient", response_model=schemas.AlertRecipientResponse)
def update_recipient(
    recipient: schemas.AlertRecipientCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    db_recipient = db.query(models.AlertRecipient).filter(models.AlertRecipient.user_id == current_user["id"]).first()
    if db_recipient:
        db_recipient.telegram_chat_id = recipient.telegram_chat_id
        db_recipient.enabled = recipient.enabled
    else:
        db_recipient = models.AlertRecipient(**recipient.dict(), user_id=current_user["id"])
        db.add(db_recipient)
    
    db.commit()
    db.refresh(db_recipient)
    refresh_caches()
    return db_recipient
