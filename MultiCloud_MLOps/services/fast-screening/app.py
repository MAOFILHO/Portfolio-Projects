from fastapi import FastAPI
import cv2
import numpy as np
import redis
import os
import json
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from decimal import Decimal
import asyncio
import threading
import tempfile
import time
import httpx
import requests

app = FastAPI()

POLICY_ENGINE_URL = os.getenv("POLICY_ENGINE_SERVICE_URL", "http://policy-engine-service:80")
cache = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, decode_responses=True)

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
DYNAMODB_VIDEOS_TABLE = os.getenv("DYNAMODB_VIDEOS_TABLE", "guardian-videos")
DYNAMODB_EVENTS_TABLE = os.getenv("DYNAMODB_EVENTS_TABLE", "guardian-events")
SQS_VIDEO_QUEUE_URL = os.getenv("SQS_VIDEO_QUEUE_URL") or os.getenv("SQS_QUEUE_URL")  # Support both names
SQS_GPU_QUEUE_URL = os.getenv("SQS_GPU_QUEUE_URL")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# AWS Clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
videos_table = dynamodb.Table(DYNAMODB_VIDEOS_TABLE)
events_table = dynamodb.Table(DYNAMODB_EVENTS_TABLE)
sqs_client = boto3.client('sqs', region_name=AWS_REGION)
s3_client = boto3.client('s3', region_name=AWS_REGION)

@app.post("/screen")
async def screen_video(video_path: str):
    """Fast CPU-based screening using classical ML features (no LLM on critical path)"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    interval = int(fps * 2)  # 0.5 FPS sampling
    
    frame_features = []
    count = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if count % interval == 0:
            features = extract_frame_features(frame)
            frame_features.append(features)
        count += 1
    
    cap.release()
    
    if not frame_features:
        return {"error": "No frames analyzed"}
    
    # Calculate risk score using classical ML features (calibrated to reduce false positives)
    risk_score = calculate_risk_score(frame_features)
    
    # Lower threshold to catch more potentially violent content (was 0.3, now 0.15)
    # Also check filename for violent keywords to force GPU analysis
    video_id = video_path.split("/")[-1].replace(".mp4", "")
    filename = video_path.split("/")[-1].lower()
    
    # Check for violent keywords in filename
    violent_keywords = ['violent', 'violence', 'kill', 'killing', 'action', 'gun', 'weapon', 
                       'fight', 'fighting', 'blood', 'bloody', 'war', 'warfare', 'combat',
                       'shoot', 'shooting', 'attack', 'assault', 'murder', 'death', 'dead']
    has_violent_keyword = any(keyword in filename for keyword in violent_keywords)
    
    # Force GPU analysis if filename suggests violence OR risk score > 0.15 (lowered from 0.3)
    needs_gpu = risk_score > 0.15 or has_violent_keyword
    
    if has_violent_keyword:
        print(f"⚠️  Video {video_id} contains violent keywords in filename, forcing GPU analysis")
        # Boost risk score for violent keywords to ensure proper handling
        risk_score = max(risk_score, 0.25)

    video_id = video_path.split("/")[-1].replace(".mp4", "")

    # Update video record in DynamoDB (single source of truth)
    try:
        videos_table.update_item(
            Key={"video_id": video_id},
            UpdateExpression="SET #status = :status, risk_score = :risk_score, screening_type = :screening_type, frames_analyzed = :frames_analyzed, screened_at = :screened_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "gpu_queued" if needs_gpu else "screened",
                ":risk_score": Decimal(str(risk_score)),
                ":screening_type": "cpu",
                ":frames_analyzed": len(frame_features),
                ":screened_at": datetime.utcnow().isoformat()
            }
        )
    except ClientError as e:
        print(f"Failed to update video in DynamoDB: {e}")

    # Trigger policy engine for low-risk videos so they get immediate AUTO APPROVE (no GPU analysis)
    if not needs_gpu:
        # Retry logic: try up to 3 times with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                import requests
                response = requests.post(
                    f"{POLICY_ENGINE_URL}/decide",
                    json={
                        "video_id": video_id,
                        "risk_score": float(risk_score),
                        "nsfw_score": 0.0,
                        "violence_score": 0.0,
                        "hate_speech_score": 0.0,
                    },
                    timeout=10.0,
                )
                if response.status_code == 200:
                    print(f"✅ Policy engine triggered for {video_id}: {response.json()}")
                    break  # Success, exit retry loop
                else:
                    print(f"⚠️  Policy engine returned {response.status_code}: {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
            except Exception as e:
                print(f"⚠️  Failed to trigger policy for low-risk video (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"❌ All retries failed for {video_id}. Video will be fixed by background worker.")
    
    # Log screening event to events table
    try:
        events_table.put_item(
            Item={
                "event_id": f"{video_id}_{int(datetime.utcnow().timestamp() * 1000)}",
                "video_id": video_id,
                "event_type": "screen",
                "event_data": {
                    "risk_score": str(risk_score),
                    "screening_type": "cpu",
                    "frames_analyzed": len(frame_features),
                    "needs_gpu": needs_gpu
                },
                "timestamp": datetime.utcnow().isoformat(),
                "ttl": int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)  # 90 days TTL
            }
        )
    except ClientError as e:
        print(f"Failed to log event (non-critical): {e}")
    
    # Send to GPU queue if high risk
    if needs_gpu and SQS_GPU_QUEUE_URL:
        try:
            sqs_client.send_message(
                QueueUrl=SQS_GPU_QUEUE_URL,
                MessageBody=json.dumps({
                    "video_id": video_id,
                    "risk_score": str(risk_score),
                    "priority": "high" if risk_score > 0.7 else "normal"
                })
            )
        except ClientError as e:
            print(f"Failed to send message to GPU queue: {e}")
    
    return {
        "risk_score": float(risk_score),
        "needs_gpu": needs_gpu,
        "frames_analyzed": len(frame_features)
    }

def extract_frame_features(frame):
    """Extract multiple features for AI risk assessment"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    # Normalize motion score to 0-1 (edges are 0/255)
    motion_score = (np.sum(edges) / edges.size) / 255.0
    
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    skin_mask = cv2.inRange(hsv, (0, 20, 70), (20, 255, 255))
    skin_ratio = np.sum(skin_mask) / skin_mask.size
    
    # Color distribution analysis
    hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    color_variance = float(np.std(hist))
    
    # Brightness analysis
    brightness = float(np.mean(gray))
    
    return {
        "motion": motion_score,
        "skin_ratio": skin_ratio,
        "color_variance": color_variance,
        "brightness": brightness
    }

def calculate_risk_score(frame_features):
    """Calculate risk score using normalized classical ML features with improved violence detection."""
    motion_scores = [f["motion"] for f in frame_features]
    skin_ratios = [f["skin_ratio"] for f in frame_features]
    color_variances = [f["color_variance"] for f in frame_features]

    # Normalize and clamp each feature to 0-1
    motion = float(np.clip(np.mean(motion_scores), 0.0, 1.0))
    skin = float(np.clip(np.mean(skin_ratios), 0.0, 1.0))
    # Empirical scale to keep color variance in a reasonable range
    color = float(np.clip(np.mean(color_variances) / 0.5, 0.0, 1.0))
    
    # Detect rapid motion changes (indicator of action/violence)
    if len(motion_scores) > 1:
        motion_variance = float(np.std(motion_scores))
        # High motion variance suggests action/violence scenes
        motion_volatility = float(np.clip(motion_variance * 2.0, 0.0, 1.0))
    else:
        motion_volatility = 0.0

    # Improved weighted risk calculation with higher weight on motion (violence indicator)
    # Increased motion weight from 0.15 to 0.30, added motion volatility
    risk = (motion * 0.30) + (motion_volatility * 0.20) + (skin * 0.15) + (color * 0.10)
    return float(np.clip(risk, 0.0, 1.0))

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "screening_type": "cpu_classical_ml"
    }

# Background worker to poll SQS
def poll_sqs_queue():
    """Background worker that continuously polls SQS for new videos to screen"""
    print("🚀 Starting SQS polling worker for Fast Screening...")
    
    while True:
        try:
            if not SQS_VIDEO_QUEUE_URL:
                print("⚠️  SQS_VIDEO_QUEUE_URL not configured, worker sleeping...")
                time.sleep(30)
                continue
            
            # Poll SQS for messages
            response = sqs_client.receive_message(
                QueueUrl=SQS_VIDEO_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,  # Long polling
                VisibilityTimeout=300  # 5 minutes to process
            )
            
            messages = response.get('Messages', [])
            
            if not messages:
                continue  # No messages, continue polling
            
            for message in messages:
                try:
                    # Parse message
                    body = json.loads(message['Body'])
                    video_id = body.get('video_id')
                    s3_key = body.get('s3_key')
                    
                    print(f"📹 Processing video: {video_id}")
                    
                    # Fetch video metadata from DynamoDB to get filename
                    try:
                        video_response = videos_table.get_item(Key={"video_id": video_id})
                        filename = video_response.get('Item', {}).get('filename', '')
                    except Exception as e:
                        print(f"⚠️  Failed to fetch video metadata: {e}")
                        filename = ''
                    
                    # Download video from S3 to temp file
                    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
                        s3_client.download_fileobj(S3_BUCKET_NAME, s3_key, tmp_file)
                        tmp_path = tmp_file.name
                    
                    # Process video using existing screen_video logic
                    cap = cv2.VideoCapture(tmp_path)
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    interval = int(fps * 2) if fps > 0 else 30
                    
                    frame_features = []
                    count = 0
                    
                    while cap.isOpened():
                        ret, frame = cap.read()
                        if not ret:
                            break
                        if count % interval == 0:
                            features = extract_frame_features(frame)
                            frame_features.append(features)
                        count += 1
                    
                    cap.release()
                    
                    # Clean up temp file
                    os.unlink(tmp_path)
                    
                    if frame_features:
                        # Calculate risk score
                        risk_score = calculate_risk_score(frame_features)
                        
                        # Use filename from DynamoDB (already fetched above)
                        filename_lower = filename.lower() if filename else ""
                        
                        # Check for violent keywords in filename
                        violent_keywords = ['violent', 'violence', 'kill', 'killing', 'action', 'gun', 'weapon', 
                                           'fight', 'fighting', 'blood', 'bloody', 'war', 'warfare', 'combat',
                                           'shoot', 'shooting', 'attack', 'assault', 'murder', 'death', 'dead',
                                           'wick', 'action scene', 'battle', 'battleground']
                        has_violent_keyword = any(keyword in filename_lower for keyword in violent_keywords)
                        
                        # Force GPU analysis if filename suggests violence OR risk score > 0.15 (lowered from 0.3)
                        needs_gpu = risk_score > 0.15 or has_violent_keyword
                        
                        if has_violent_keyword:
                            print(f"⚠️  Video {video_id} contains violent keywords in filename, forcing GPU analysis")
                            # Boost risk score for violent keywords to ensure proper handling
                            risk_score = max(risk_score, 0.25)
                        
                        # Update video record in DynamoDB
                        videos_table.update_item(
                            Key={"video_id": video_id},
                            UpdateExpression="SET #status = :status, risk_score = :risk_score, screening_type = :screening_type, frames_analyzed = :frames_analyzed, screened_at = :screened_at",
                            ExpressionAttributeNames={"#status": "status"},
                            ExpressionAttributeValues={
                                ":status": "gpu_queued" if needs_gpu else "screened",
                                ":risk_score": Decimal(str(risk_score)),
                                ":screening_type": "cpu",
                                ":frames_analyzed": len(frame_features),
                                ":screened_at": datetime.utcnow().isoformat()
                            }
                        )
                        
                        # Log screening event
                        events_table.put_item(
                            Item={
                                "event_id": f"{video_id}_{int(datetime.utcnow().timestamp() * 1000)}",
                                "video_id": video_id,
                                "event_type": "screen",
                                "event_data": {
                                    "risk_score": str(risk_score),
                                    "screening_type": "cpu",
                                    "frames_analyzed": len(frame_features),
                                    "needs_gpu": needs_gpu
                                },
                                "timestamp": datetime.utcnow().isoformat(),
                                "ttl": int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)
                            }
                        )
                        
                        # Send to GPU queue if high risk
                        if needs_gpu and SQS_GPU_QUEUE_URL:
                            sqs_client.send_message(
                                QueueUrl=SQS_GPU_QUEUE_URL,
                                MessageBody=json.dumps({
                                    "video_id": video_id,
                                    "s3_key": s3_key,
                                    "risk_score": str(risk_score),
                                    "priority": "high" if risk_score > 0.7 else "normal"
                                })
                            )
                        else:
                            # Trigger policy engine for low-risk videos so they get immediate AUTO APPROVE
                            try:
                                import requests
                                response = requests.post(
                                    f"{POLICY_ENGINE_URL}/decide",
                                    json={
                                        "video_id": video_id,
                                        "risk_score": float(risk_score),
                                        "nsfw_score": 0.0,
                                        "violence_score": 0.0,
                                        "hate_speech_score": 0.0,
                                    },
                                    timeout=10.0,
                                )
                                if response.status_code == 200:
                                    print(f"✅ Policy engine triggered for {video_id}: {response.json()}")
                                else:
                                    print(f"⚠️  Policy engine returned {response.status_code}: {response.text}")
                            except Exception as e:
                                print(f"❌ Failed to trigger policy for low-risk video: {e}")
                                import traceback
                                traceback.print_exc()

                        print(f"✅ Screened video {video_id}: risk_score={risk_score:.3f}, needs_gpu={needs_gpu}")
                    
                    # Delete message from queue
                    sqs_client.delete_message(
                        QueueUrl=SQS_VIDEO_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    # Message will become visible again after VisibilityTimeout
        
        except Exception as e:
            print(f"❌ Error polling SQS: {e}")
            time.sleep(10)  # Wait before retrying

@app.on_event("startup")
async def startup_event():
    """Start background worker on app startup"""
    worker_thread = threading.Thread(target=poll_sqs_queue, daemon=True)
    worker_thread.start()
    print("✅ Fast Screening service started with SQS polling worker")
