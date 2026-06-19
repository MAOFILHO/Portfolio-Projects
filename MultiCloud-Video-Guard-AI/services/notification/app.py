from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from decimal import Decimal

app = FastAPI()

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
DYNAMODB_EVENTS_TABLE = os.getenv("DYNAMODB_EVENTS_TABLE", "guardian-events")

# AWS Clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
events_table = dynamodb.Table(DYNAMODB_EVENTS_TABLE)

class Notification(BaseModel):
    video_id: str
    decision: str
    webhook_url: str

@app.post("/notify")
async def send_notification(notification: Notification):
    result = {"status": "failed", "error": "unknown"}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                notification.webhook_url,
                json={
                    "video_id": notification.video_id,
                    "decision": notification.decision
                },
                timeout=5.0
            )
            result = {"status": "sent", "code": response.status_code}
        except Exception as e:
            result = {"status": "failed", "error": str(e)}
    
    # Log notification event to events table
    try:
        events_table.put_item(
            Item={
                "event_id": f"{notification.video_id}_{int(datetime.utcnow().timestamp() * 1000)}",
                "video_id": notification.video_id,
                "event_type": "notify",
                "event_data": {
                    "decision": notification.decision,
                    "webhook_url": notification.webhook_url,
                    "status": result["status"],
                    "response_code": result.get("code", "N/A")
                },
                "timestamp": datetime.utcnow().isoformat(),
                "ttl": int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)  # 90 days TTL
            }
        )
    except ClientError as e:
        print(f"Failed to log event (non-critical): {e}")
    
    return result

@app.get("/health")
async def health():
    return {"status": "healthy"}
