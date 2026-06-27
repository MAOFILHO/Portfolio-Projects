from fastapi import FastAPI, HTTPException, BackgroundTasks
import torch
import torchvision.transforms as transforms
from transformers import CLIPProcessor, CLIPModel
import cv2
import numpy as np
from PIL import Image
import os
from datetime import datetime
from decimal import Decimal
from openai import AzureOpenAI
import base64
import io
import requests
import json
from typing import Optional
import threading
import time
import asyncio

app = FastAPI()

# Device setup
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Azure OpenAI client (optional, for explanation generation only - off critical path)
AZURE_OPENAI_ENABLED = os.getenv("AZURE_OPENAI_ENABLED", "false").lower() == "true"
client = None
if AZURE_OPENAI_ENABLED:
    try:
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
    except Exception as e:
        print(f"Azure OpenAI initialization failed (non-critical): {e}")
        client = None

# CLIP model for content understanding
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
clip_model.eval()

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
DYNAMODB_VIDEOS_TABLE = os.getenv("DYNAMODB_VIDEOS_TABLE", "guardian-videos")
DYNAMODB_EVENTS_TABLE = os.getenv("DYNAMODB_EVENTS_TABLE", "guardian-events")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "guardian-videos")
SQS_GPU_QUEUE_URL = os.getenv("SQS_GPU_QUEUE_URL")
POLICY_ENGINE_URL = os.getenv("POLICY_ENGINE_SERVICE_URL", "http://policy-engine-service:80")

# AWS Clients
import boto3
from botocore.exceptions import ClientError
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
s3_client = boto3.client('s3', region_name=AWS_REGION)
sqs_client = boto3.client('sqs', region_name=AWS_REGION)
videos_table = dynamodb.Table(DYNAMODB_VIDEOS_TABLE)
events_table = dynamodb.Table(DYNAMODB_EVENTS_TABLE)

# Model endpoints
NSFW_ENDPOINT = os.getenv("NSFW_MODEL_ENDPOINT")
VIOLENCE_ENDPOINT = os.getenv("VIOLENCE_MODEL_ENDPOINT")
ENDPOINT_KEY = os.getenv("MODEL_ENDPOINT_KEY")

transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

@app.post("/analyze")
async def analyze_video(video_id: str, background_tasks: BackgroundTasks):
    """Deep analysis with CLIP and Azure OpenAI (CPU/GPU agnostic)"""
    # Download video from S3
    s3_key = f"videos/{video_id}.mp4"
    local_path = f"/tmp/{video_id}.mp4"
    
    try:
        s3_client.download_file(S3_BUCKET, s3_key, local_path)
    except ClientError as e:
        raise HTTPException(404, f"Video not found in S3: {str(e)}")
    
    cap = cv2.VideoCapture(local_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    interval = int(fps)  # 1 FPS for GPU
    
    frames_data = []
    count = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if count % interval == 0:
            frame_analysis = await analyze_frame_with_ai(frame, count // interval)
            frames_data.append(frame_analysis)
        count += 1
    
    cap.release()
    
    # Aggregate scores (CRITICAL PATH - deterministic ML inference)
    nsfw_scores = [f["nsfw_score"] for f in frames_data]
    violence_scores = [f["violence_score"] for f in frames_data]
    
    # Use 90th percentile to catch more content while reducing false positives
    # This is better than 75th percentile for detecting actual problematic content
    nsfw_avg = float(np.percentile(nsfw_scores, 90)) if nsfw_scores else 0.0
    violence_avg = float(np.percentile(violence_scores, 90)) if violence_scores else 0.0
    
    # Light scaling only if custom models are not available (CLIP scores are already calibrated)
    # If custom models were used, scores are already properly calibrated
    has_custom_models = any(f.get("custom_nsfw", 0) > 0 or f.get("custom_violence", 0) > 0 for f in frames_data)
    if not has_custom_models:
        # CLIP-only mode - apply light scaling (was 0.5, now 0.75 for better accuracy)
        nsfw_avg = nsfw_avg * 0.75
        violence_avg = violence_avg * 0.75
    
    # Save to DynamoDB immediately (critical path)
    try:
        videos_table.update_item(
            Key={"video_id": video_id},
            UpdateExpression="SET nsfw_score = :nsfw, violence_score = :violence, screening_type = :type, analyzed_at = :timestamp, frames_analyzed = :frames, model_version = :version",
            ExpressionAttributeValues={
                ":nsfw": Decimal(str(nsfw_avg)),
                ":violence": Decimal(str(violence_avg)),
                ":type": "cpu",
                ":timestamp": datetime.utcnow().isoformat(),
                ":frames": len(frames_data),
                ":version": os.getenv("MODEL_VERSION", "v1.0.0")
            }
        )
        
        videos_table.update_item(
            Key={"video_id": video_id},
            UpdateExpression="SET #status = :status, nsfw_score = :nsfw, violence_score = :violence",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "analyzed",
                ":nsfw": Decimal(str(nsfw_avg)),
                ":violence": Decimal(str(violence_avg))
            }
        )
    except ClientError as e:
        print(f"Failed to update DynamoDB: {e}")
    
    # Clean up local file
    try:
        os.remove(local_path)
    except:
        pass
    
    # Trigger policy engine decision with risk_score from fast-screening + deep-vision scores
    try:
        video_resp = videos_table.get_item(Key={"video_id": video_id})
        risk_from_screening = 0.0
        if "Item" in video_resp:
            r = video_resp["Item"].get("risk_score")
            if r is not None:
                risk_from_screening = float(r)
        requests.post(
            f"{POLICY_ENGINE_URL}/decide",
            json={
                "video_id": video_id,
                "risk_score": risk_from_screening,
                "nsfw_score": nsfw_avg,
                "violence_score": violence_avg,
                "hate_speech_score": 0.0
            },
            timeout=10
        )
    except Exception as e:
        print(f"Policy engine trigger failed (non-critical): {e}")

    # Generate AI explanation asynchronously (OFF CRITICAL PATH - optional enhancement)
    if AZURE_OPENAI_ENABLED and client:
        # Fire and forget - don't block response
        background_tasks.add_task(generate_explanation_async, video_id, frames_data, nsfw_avg, violence_avg)
    
    return {
        "nsfw_score": nsfw_avg,
        "violence_score": violence_avg,
        "frames_analyzed": len(frames_data),
        "explanation_available": AZURE_OPENAI_ENABLED
    }

async def analyze_frame_with_ai(frame, frame_num):
    """Analyve frame using improved CLIP-based detection (works without external model endpoints)"""
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    # First, detect if content is animated/cartoon (to reduce false positives)
    animation_labels = [
        "real life video, live action, actual people, real world",
        "animated cartoon, animation, drawn characters, animated content",
        "computer graphics, CGI, digital animation, rendered content"
    ]
    
    animation_inputs = clip_processor(text=animation_labels, images=img, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        animation_outputs = clip_model(**animation_inputs)
        animation_logits = animation_outputs.logits_per_image
        animation_probs = animation_logits.softmax(dim=1).cpu().numpy()[0]
    
    # Check if content is animated (probability of animated/cartoon/CGI)
    is_animated = float(animation_probs[1] + animation_probs[2]) > 0.5
    
    # Enhanced CLIP-based content classification with better prompts
    # More specific labels for better accuracy
    nsfw_labels = [
        "safe content, normal scene, everyday activity",
        "explicit sexual content, adult material, pornography",
        "partial nudity, revealing clothing, suggestive content",
        "naked person, full nudity, exposed body parts"
    ]
    
    violence_labels = [
        "safe content, peaceful scene, normal activity",
        "violence, fighting, physical assault, combat",
        "weapons, guns, knives, firearms, dangerous objects",
        "blood, injury, wound, gore, violence aftermath"
    ]
    
    # Analyze NSFW content
    nsfw_inputs = clip_processor(text=nsfw_labels, images=img, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        nsfw_outputs = clip_model(**nsfw_inputs)
        nsfw_logits = nsfw_outputs.logits_per_image
        nsfw_probs = nsfw_logits.softmax(dim=1).cpu().numpy()[0]
    
    # Analyze Violence content
    violence_inputs = clip_processor(text=violence_labels, images=img, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        violence_outputs = clip_model(**violence_inputs)
        violence_logits = violence_outputs.logits_per_image
        violence_probs = violence_logits.softmax(dim=1).cpu().numpy()[0]
    
    # Calculate NSFW score (explicit + partial nudity + full nudity)
    clip_nsfw = float(nsfw_probs[1] + nsfw_probs[2] * 0.7 + nsfw_probs[3])
    
    # Calculate Violence score (violence + weapons + blood)
    clip_violence = float(violence_probs[1] + violence_probs[2] * 0.8 + violence_probs[3] * 0.9)
    
    # Try to call custom model endpoints if available, otherwise use CLIP only
    nsfw_custom = 0.0
    violence_custom = 0.0
    
    if NSFW_ENDPOINT:
        try:
            nsfw_custom = await call_model_endpoint(NSFW_ENDPOINT, img)
        except:
            pass
    
    if VIOLENCE_ENDPOINT:
        try:
            violence_custom = await call_model_endpoint(VIOLENCE_ENDPOINT, img)
        except:
            pass
    
    # If custom models are available, combine with CLIP (weighted)
    # If not available, use CLIP as primary (with improved accuracy)
    if nsfw_custom > 0 or violence_custom > 0:
        # Custom models available - combine with CLIP
        nsfw_score = (nsfw_custom * 0.7 + clip_nsfw * 0.3)
        violence_score = (violence_custom * 0.7 + clip_violence * 0.3)
    else:
        # No custom models - use improved CLIP as primary
        # Apply light calibration (reduce false positives but keep accuracy)
        nsfw_score = clip_nsfw * 0.85  # Light scaling to reduce false positives
        violence_score = clip_violence * 0.85
    
    # Significantly reduce scores for animated/cartoon content to prevent false positives
    # Animated violence (like Tom & Jerry) should not be flagged as real violence
    if is_animated:
        nsfw_score = nsfw_score * 0.2  # Reduce animated NSFW scores by 80%
        violence_score = violence_score * 0.25  # Reduce animated violence scores by 75%
    
    return {
        "frame_num": frame_num,
        "nsfw_score": float(np.clip(nsfw_score, 0.0, 1.0)),
        "violence_score": float(np.clip(violence_score, 0.0, 1.0)),
        "clip_nsfw": float(clip_nsfw),
        "clip_violence": float(clip_violence),
        "custom_nsfw": float(nsfw_custom),
        "custom_violence": float(violence_custom),
        "is_animated": is_animated
    }

async def call_model_endpoint(endpoint, image):
    """Call Azure ML model endpoint"""
    try:
        # Convert image to base64
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ENDPOINT_KEY}"
        }
        data = {"image": img_str}
        
        response = requests.post(endpoint, headers=headers, json=data, timeout=5)
        if response.status_code == 200:
            return response.json().get("score", 0.0)
        return 0.0
    except Exception as e:
        print(f"Model endpoint error: {e}")
        return 0.0

async def generate_explanation_async(video_id: str, frames_data: list, nsfw_avg: float, violence_avg: float):
    """Generate human-readable explanation asynchronously (off critical path)"""
    try:
        prompt = f"""Analyze this video moderation result and provide a clear explanation:

NSFW Score: {nsfw_avg:.2f}/1.0
Violence Score: {violence_avg:.2f}/1.0
Frames Analyzed: {len(frames_data)}

Top concerning frames:
{json.dumps([f for f in frames_data[:3]], indent=2)}

Provide:
1. Risk assessment (Low/Medium/High)
2. Specific concerns found
3. Explanation for human reviewers

Be concise and factual. Do NOT make the final decision - that is done by the policy engine."""
        
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {"role": "system", "content": "You are an AI content moderation assistant. Provide clear, factual analysis. You do NOT make moderation decisions - only explain what was detected."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        explanation = response.choices[0].message.content
        
        # Update decision document with explanation (non-blocking)
        try:
            videos_table.update_item(
                Key={"video_id": video_id},
                UpdateExpression="SET ai_explanation = :explanation, explanation_generated_at = :timestamp",
                ExpressionAttributeValues={
                    ":explanation": explanation,
                    ":timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            print(f"Failed to update explanation in DB: {e}")
            
    except Exception as e:
        print(f"OpenAI explanation generation error (non-critical): {e}")

@app.post("/explain")
async def explain_decision(video_id: str):
    """Generate detailed explanation for a moderation decision (optional LLM endpoint)"""
    if not AZURE_OPENAI_ENABLED or not client:
        raise HTTPException(status_code=503, detail="Azure OpenAI explanation service is disabled")
    
    try:
        decision_response = videos_table.get_item(Key={"video_id": video_id})
        if 'Item' not in decision_response:
            raise HTTPException(404, "Video not found")
        decision = decision_response['Item']
        
        # Check if explanation already exists
        if decision.get("ai_explanation"):
            return {"explanation": decision["ai_explanation"], "cached": True}
        
        prompt = f"""Explain why this video received these scores:

NSFW: {decision.get('nsfw_score', 0):.2f}
Violence: {decision.get('violence_score', 0):.2f}

Provide a clear explanation suitable for content creators."""
        
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {"role": "system", "content": "You are a helpful content moderation assistant explaining decisions to creators."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=300
        )
        
        explanation = response.choices[0].message.content
        
        # Cache explanation
        videos_table.update_item(
            Key={"video_id": video_id},
            UpdateExpression="SET ai_explanation = :explanation, explanation_generated_at = :timestamp",
            ExpressionAttributeValues={
                ":explanation": explanation,
                ":timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return {"explanation": explanation, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "device": str(device),
        "models": ["CLIP", "Custom NSFW", "Custom Violence"],
        "llm_explanation_enabled": AZURE_OPENAI_ENABLED and client is not None
    }

async def poll_gpu_queue():
    """Background worker that continuously polls SQS GPU queue for videos to analyze"""
    print("🚀 Starting SQS GPU queue polling worker for Deep Vision...")
    
    while True:
        try:
            if not SQS_GPU_QUEUE_URL:
                print("⚠️  SQS_GPU_QUEUE_URL not configured, worker sleeping...")
                time.sleep(30)
                continue
            
            # Poll SQS for messages
            response = sqs_client.receive_message(
                QueueUrl=SQS_GPU_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,  # Long polling
                VisibilityTimeout=600  # 10 minutes for deep analysis
            )
            
            messages = response.get('Messages', [])
            
            if not messages:
                continue  # No messages, continue polling
            
            for message in messages:
                try:
                    # Parse message
                    body = json.loads(message['Body'])
                    video_id = body.get('video_id')
                    s3_key = body.get('s3_key', f"videos/{video_id}.mp4")
                    
                    print(f"🎬 Deep analyzing video: {video_id}")
                    
                    # Download video from S3
                    local_path = f"/tmp/{video_id}.mp4"
                    s3_client.download_file(S3_BUCKET, s3_key, local_path)
                    
                    # Process video with CLIP
                    cap = cv2.VideoCapture(local_path)
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    interval = int(fps) if fps > 0 else 30
                    
                    frames_data = []
                    count = 0
                    
                    while cap.isOpened():
                        ret, frame = cap.read()
                        if not ret:
                            break
                        if count % interval == 0:
                            # Use improved analyze_frame_with_ai function
                            frame_analysis = await analyze_frame_with_ai(frame, count // interval)
                            frames_data.append(frame_analysis)
                        
                        count += 1
                    
                    cap.release()
                    os.unlink(local_path)
                    
                    # Calculate aggregate scores using improved method
                    nsfw_scores = [f["nsfw_score"] for f in frames_data]
                    violence_scores = [f["violence_score"] for f in frames_data]
                    
                    # Use 90th percentile to catch more content while reducing false positives
                    nsfw_avg = float(np.percentile(nsfw_scores, 90)) if nsfw_scores else 0.0
                    violence_avg = float(np.percentile(violence_scores, 90)) if violence_scores else 0.0
                    
                    # Light scaling only if custom models are not available
                    has_custom_models = any(f.get("custom_nsfw", 0) > 0 or f.get("custom_violence", 0) > 0 for f in frames_data)
                    if not has_custom_models:
                        # CLIP-only mode - apply light scaling for better accuracy
                        nsfw_avg = nsfw_avg * 0.75
                        violence_avg = violence_avg * 0.75
                    
                    final_score = max(nsfw_avg, violence_avg)
                    
                    # Update DynamoDB
                    videos_table.update_item(
                        Key={"video_id": video_id},
                        UpdateExpression="SET nsfw_score = :nsfw, violence_score = :violence, final_score = :final, #status = :status, analyzed_at = :timestamp, frames_analyzed = :frames, model_version = :version",
                        ExpressionAttributeNames={"#status": "status"},
                        ExpressionAttributeValues={
                            ":nsfw": Decimal(str(nsfw_avg)),
                            ":violence": Decimal(str(violence_avg)),
                            ":final": Decimal(str(final_score)),
                            ":status": "analyzed",
                            ":timestamp": datetime.utcnow().isoformat(),
                            ":frames": len(frames_data),
                            ":version": "clip-vit-base-patch32"
                        }
                    )
                    
                    # Log analysis event
                    events_table.put_item(
                        Item={
                            "event_id": f"{video_id}_{int(datetime.utcnow().timestamp() * 1000)}",
                            "video_id": video_id,
                            "event_type": "analyze",
                            "event_data": {
                                "nsfw_score": str(nsfw_avg),
                                "violence_score": str(violence_avg),
                                "final_score": str(final_score),
                                "frames_analyzed": len(frames_data),
                                "model": "clip-vit-base-patch32",
                                "device": str(device)
                            },
                            "timestamp": datetime.utcnow().isoformat(),
                            "ttl": int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)
                        }
                    )
                    
                    # Get original risk_score from fast-screening (if available)
                    try:
                        video_resp = videos_table.get_item(Key={"video_id": video_id})
                        original_risk_score = 0.0
                        if "Item" in video_resp:
                            r = video_resp["Item"].get("risk_score")
                            if r is not None:
                                original_risk_score = float(r)
                    except Exception as e:
                        print(f"⚠️  Failed to fetch risk_score from DynamoDB: {e}")
                        original_risk_score = 0.0
                    
                    # Send to Policy Engine for decision
                    policy_decision_made = False
                    try:
                        print(f"🔔 Calling policy-engine at {POLICY_ENGINE_URL}/decide for video {video_id}")
                        policy_response = requests.post(
                            f"{POLICY_ENGINE_URL}/decide",
                            json={
                                "video_id": video_id,
                                "nsfw_score": nsfw_avg,
                                "violence_score": violence_avg,
                                "risk_score": original_risk_score,  # Use original risk_score from fast-screening
                                "hate_speech_score": 0.0  # Not implemented yet
                            },
                            timeout=30
                        )
                        if policy_response.status_code == 200:
                            result = policy_response.json()
                            print(f"✅ Policy evaluation completed for {video_id}: decision={result.get('decision')}, final_score={result.get('final_score', 0):.3f}")
                            policy_decision_made = True
                        else:
                            print(f"❌ Policy evaluation returned {policy_response.status_code}: {policy_response.text}")
                            # Try to parse error response
                            try:
                                error_data = policy_response.json()
                                print(f"   Error details: {error_data}")
                            except:
                                print(f"   Error text: {policy_response.text}")
                    except requests.exceptions.ConnectionError as e:
                        print(f"❌ Failed to connect to policy-engine at {POLICY_ENGINE_URL}: {e}")
                        print(f"   This may indicate the service is not available or URL is incorrect")
                    except requests.exceptions.Timeout as e:
                        print(f"❌ Policy-engine request timed out after 30s: {e}")
                    except Exception as e:
                        print(f"❌ Failed to trigger policy evaluation: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # If policy decision failed, log it but don't fail the analysis
                    # The stuck videos worker will pick it up later
                    if not policy_decision_made:
                        print(f"⚠️  Policy decision not made for {video_id}. Status set to 'analyzed', decision='pending'.")
                        print(f"   The stuck videos worker will process this video within 60 seconds.")
                    
                    print(f"✅ Deep analyzed video {video_id}: nsfw={nsfw_avg:.3f}, violence={violence_avg:.3f}, final={final_score:.3f}")
                    
                    # Delete message from queue
                    sqs_client.delete_message(
                        QueueUrl=SQS_GPU_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    
                except Exception as e:
                    print(f"❌ Error processing GPU queue message: {e}")
                    import traceback
                    traceback.print_exc()
        
        except Exception as e:
            print(f"❌ Error polling GPU queue: {e}")
            time.sleep(10)

def run_poll_gpu_queue():
    """Wrapper to run async poll_gpu_queue in a new event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll_gpu_queue())

@app.on_event("startup")
async def startup_event():
    """Start background worker on app startup"""
    worker_thread = threading.Thread(target=run_poll_gpu_queue, daemon=True)
    worker_thread.start()
    print("✅ Deep Vision service started with GPU queue polling worker")
