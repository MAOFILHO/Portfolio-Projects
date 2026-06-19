from fastapi import FastAPI, UploadFile, HTTPException
import boto3
from botocore.exceptions import ClientError
import os
import uuid
import json
import io
from datetime import datetime
from decimal import Decimal

app = FastAPI()

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "guardian-videos")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
DYNAMODB_VIDEOS_TABLE = os.getenv("DYNAMODB_VIDEOS_TABLE", "guardian-videos")
DYNAMODB_EVENTS_TABLE = os.getenv("DYNAMODB_EVENTS_TABLE", "guardian-events")

# AWS Clients
s3_client = boto3.client('s3', region_name=AWS_REGION)
sqs_client = boto3.client('sqs', region_name=AWS_REGION)
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
videos_table = dynamodb.Table(DYNAMODB_VIDEOS_TABLE)
events_table = dynamodb.Table(DYNAMODB_EVENTS_TABLE)

ALLOWED_TYPES = ["video/mp4", "video/quicktime", "video/x-msvideo"]
MAX_SIZE = 500 * 1024 * 1024  # 500MB

@app.post("/upload")
async def upload_video(file: UploadFile):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Invalid format. Use MP4, MOV, or AVI")
    
    video_id = str(uuid.uuid4())
    s3_key = f"videos/{video_id}.mp4"
    
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "File too large. Max 500MB")
    
    # Upload to S3
    try:
        s3_client.upload_fileobj(
            io.BytesIO(content),
            S3_BUCKET,
            s3_key,
            ExtraArgs={'ContentType': file.content_type}
        )
    except ClientError as e:
        raise HTTPException(500, f"Failed to upload to S3: {str(e)}")
    
    # Save to DynamoDB (videos table - single source of truth)
    try:
        videos_table.put_item(
            Item={
                "video_id": video_id,
                "filename": file.filename,
                "s3_key": s3_key,
                "size": Decimal(str(len(content))),
                "status": "uploaded",
                "uploaded_at": datetime.utcnow().isoformat(),
                # Initialize scores (will be updated by screening/analysis services)
                "risk_score": Decimal("0.0"),
                "nsfw_score": Decimal("0.0"),
                "violence_score": Decimal("0.0"),
                "final_score": Decimal("0.0"),
                "decision": "pending",
                "human_reviewed": False
            }
        )
    except ClientError as e:
        raise HTTPException(500, f"Failed to save to DynamoDB: {str(e)}")
    
    # Log event to events table (audit log)
    try:
        events_table.put_item(
            Item={
                "event_id": f"{video_id}_{int(datetime.utcnow().timestamp() * 1000)}",
                "video_id": video_id,
                "event_type": "upload",
                "event_data": {
                    "filename": file.filename,
                    "size": str(len(content)),
                    "s3_key": s3_key
                },
                "timestamp": datetime.utcnow().isoformat(),
                "ttl": int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)  # 90 days TTL
            }
        )
    except ClientError as e:
        print(f"Failed to log event (non-critical): {e}")
    
    # Send message to SQS
    try:
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps({
                "video_id": video_id,
                "s3_key": s3_key,
                "size": len(content)
            })
        )
    except ClientError as e:
        raise HTTPException(500, f"Failed to send message to SQS: {str(e)}")
    
    return {"job_id": video_id, "status": "queued"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
