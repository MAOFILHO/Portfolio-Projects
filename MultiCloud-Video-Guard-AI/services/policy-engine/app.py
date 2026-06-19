from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from enum import Enum
from typing import Optional, Dict, Any
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import json
from decimal import Decimal
import httpx
from openai import AzureOpenAI
import threading
import time

app = FastAPI()

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
DYNAMODB_VIDEOS_TABLE = os.getenv("DYNAMODB_VIDEOS_TABLE", "guardian-videos")
DYNAMODB_EVENTS_TABLE = os.getenv("DYNAMODB_EVENTS_TABLE", "guardian-events")

# Service URLs (for direct HTTP calls - simpler than SQS)
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification:8005")

# AWS Clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
videos_table = dynamodb.Table(DYNAMODB_VIDEOS_TABLE)
events_table = dynamodb.Table(DYNAMODB_EVENTS_TABLE)

# Azure OpenAI client for policy interpretation (optional - disabled by default)
AZURE_OPENAI_ENABLED = os.getenv("AZURE_OPENAI_ENABLED", "false").lower() == "true"
openai_client = None
if AZURE_OPENAI_ENABLED:
    try:
        openai_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
    except Exception as e:
        print(f"Azure OpenAI initialization failed (non-critical): {e}")
        openai_client = None

class Decision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REVIEW = "review"

class ModerationResult(BaseModel):
    video_id: str
    risk_score: float
    nsfw_score: float = 0.0
    violence_score: float = 0.0
    hate_speech_score: float = 0.0

AUTO_APPROVE_THRESHOLD = float(os.getenv("AUTO_APPROVE_THRESHOLD", "0.2"))
AUTO_REJECT_THRESHOLD = float(os.getenv("AUTO_REJECT_THRESHOLD", "0.8"))

@app.post("/decide")
async def make_decision(result: ModerationResult):
    # Recalculate risk_score as max of content scores (more accurate than fast-screening heuristic)
    # This ensures risk_score reflects actual content risk, not just motion/color features
    effective_risk_score = max(result.nsfw_score, result.violence_score, result.risk_score)
    
    # Use effective risk_score in final calculation
    final_score = (
        effective_risk_score * 0.4 +
        result.nsfw_score * 0.3 +
        result.violence_score * 0.2 +
        result.hate_speech_score * 0.1
    )
    
    if final_score < AUTO_APPROVE_THRESHOLD:
        decision = Decision.APPROVE
    elif final_score > AUTO_REJECT_THRESHOLD:
        decision = Decision.REJECT
    else:
        decision = Decision.REVIEW

    # Use display values for status/decision so dashboard and frontend show correctly (approved/rejected/review)
    status_value = "approved" if decision == Decision.APPROVE else ("rejected" if decision == Decision.REJECT else "review")
    decision_value = status_value

    # Update video record in DynamoDB (single source of truth)
    try:
        videos_table.update_item(
            Key={"video_id": result.video_id},
            UpdateExpression="SET #status = :status, #decision = :decision, final_score = :final_score, risk_score = :risk_score, nsfw_score = :nsfw_score, violence_score = :violence_score, decided_at = :decided_at",
            ExpressionAttributeNames={
                "#status": "status",
                "#decision": "decision"
            },
            ExpressionAttributeValues={
                ":status": status_value,
                ":decision": decision_value,
                ":final_score": Decimal(str(final_score)),
                ":risk_score": Decimal(str(effective_risk_score)),  # Update risk_score to effective value
                ":nsfw_score": Decimal(str(result.nsfw_score)),
                ":violence_score": Decimal(str(result.violence_score)),
                ":decided_at": datetime.utcnow().isoformat()
            }
        )
    except ClientError as e:
        print(f"Failed to update video in DynamoDB: {e}")
    
    # Log decision event to events table
    try:
        events_table.put_item(
            Item={
                "event_id": f"{result.video_id}_{int(datetime.utcnow().timestamp() * 1000)}",
                "video_id": result.video_id,
                "event_type": "decide",
                "event_data": {
                    "decision": decision_value,
                    "final_score": str(final_score),
                    "risk_score": str(effective_risk_score),
                    "original_risk_score": str(result.risk_score),
                    "nsfw_score": str(result.nsfw_score),
                    "violence_score": str(result.violence_score)
                },
                "timestamp": datetime.utcnow().isoformat(),
                "ttl": int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)  # 90 days TTL
            }
        )
    except ClientError as e:
        print(f"Failed to log event (non-critical): {e}")
    
    # Send notification via direct HTTP call (simpler than SQS)
    # Human review cases don't need immediate notification
    if decision != Decision.REVIEW:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{NOTIFICATION_SERVICE_URL}/notify",
                    json={
                        "video_id": result.video_id,
                        "decision": decision_value,
                        "webhook_url": "https://webhook.site/unique-id"  # TODO: Get from video metadata
                    },
                    timeout=5.0
                )
        except Exception as e:
            print(f"Failed to send notification (non-critical): {e}")
    
    return {
        "video_id": result.video_id,
        "decision": decision_value,
        "final_score": final_score,
        "requires_review": decision == Decision.REVIEW
    }

class PolicyRule(BaseModel):
    """Policy rule configuration"""
    name: str
    condition: str
    action: str
    threshold: Optional[float] = None
    region: Optional[str] = None
    age_group: Optional[str] = None

class NaturalLanguagePolicy(BaseModel):
    """Natural language policy input"""
    policy_text: str
    region: Optional[str] = None
    context: Optional[str] = None

@app.post("/policy/interpret")
async def interpret_policy(policy: NaturalLanguagePolicy):
    """Convert natural language policy to executable rules (LLM-assisted)"""
    if not AZURE_OPENAI_ENABLED or not openai_client:
        raise HTTPException(status_code=503, detail="Policy interpretation features are disabled")
    
    try:
        prompt = f"""Convert this content moderation policy into executable rules:

Policy: {policy.policy_text}
Region: {policy.region or 'Global'}
Context: {policy.context or 'General content moderation'}

Return a JSON object with:
{{
    "rules": [
        {{
            "name": "rule_name",
            "condition": "specific condition (e.g., nsfw_score > 0.7)",
            "action": "approve|reject|review",
            "threshold": 0.0-1.0,
            "region": "region_code or null",
            "age_group": "minor|adult|all or null"
        }}
    ],
    "explanation": "brief explanation of the policy"
}}

Be specific and actionable. Use clear thresholds and conditions."""
        
        response = openai_client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {"role": "system", "content": "You are a policy engine assistant. Convert natural language policies into executable, structured rules. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        
        return {
            "interpreted_rules": result.get("rules", []),
            "explanation": result.get("explanation", ""),
            "original_policy": policy.policy_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy interpretation failed: {str(e)}")

@app.post("/policy/validate")
async def validate_policy_rule(rule: PolicyRule):
    """Validate a policy rule for correctness"""
    errors = []
    
    # Validate action
    if rule.action not in ["approve", "reject", "review"]:
        errors.append(f"Invalid action: {rule.action}. Must be 'approve', 'reject', or 'review'")
    
    # Validate threshold if provided
    if rule.threshold is not None:
        if not 0.0 <= rule.threshold <= 1.0:
            errors.append(f"Threshold must be between 0.0 and 1.0, got {rule.threshold}")
    
    # Validate age group if provided
    if rule.age_group is not None:
        if rule.age_group not in ["minor", "adult", "all"]:
            errors.append(f"Invalid age_group: {rule.age_group}")
    
    if errors:
        return {"valid": False, "errors": errors}
    
    return {"valid": True, "rule": rule.dict()}

def fix_stuck_videos_worker():
    """Background worker that periodically checks for and fixes videos stuck in processing"""
    import sys
    print("🔧 Starting stuck videos fixer worker...", flush=True)
    sys.stdout.flush()
    
    while True:
        try:
            # Scan for stuck videos:
            # 1. status='analyzed' but no decision made (should trigger policy decision)
            # 2. status='screened' with decision='pending' (old stuck state)
            # 3. status='processing' for more than 1 hour (likely stuck)
            stuck_videos = []
            
            # Get all videos and filter for stuck ones
            response = videos_table.scan()
            all_videos = response.get('Items', [])
            
            current_time = datetime.utcnow()
            for video in all_videos:
                status = video.get('status', '')
                decision = video.get('decision', '')
                analyzed_at = video.get('analyzed_at', '')
                uploaded_at = video.get('uploaded_at', '')
                
                # Case 1: Analyzed but no decision
                if status == 'analyzed' and not decision:
                    stuck_videos.append(video)
                # Case 2: Screened with pending decision
                elif status == 'screened' and decision == 'pending':
                    stuck_videos.append(video)
                # Case 3: Processing for more than 1 hour
                elif status in ['processing', 'uploaded', 'screened']:
                    try:
                        if uploaded_at:
                            upload_time = datetime.fromisoformat(uploaded_at.replace('Z', '+00:00'))
                            if (current_time - upload_time.replace(tzinfo=None)).total_seconds() > 3600:  # 1 hour
                                stuck_videos.append(video)
                    except:
                        pass
            
            if stuck_videos:
                print(f"🔍 Found {len(stuck_videos)} stuck video(s), fixing them...")
                
                for video in stuck_videos:
                    video_id = video.get('video_id')
                    status = video.get('status', '')
                    risk_score = float(video.get('risk_score', 0.0))
                    nsfw_score = float(video.get('nsfw_score', 0.0))
                    violence_score = float(video.get('violence_score', 0.0))
                    
                    try:
                        # If video is analyzed but no decision, make decision
                        if status == 'analyzed' and not video.get('decision'):
                            # Create ModerationResult and call make_decision internally
                            result = ModerationResult(
                                video_id=video_id,
                                risk_score=risk_score,
                                nsfw_score=nsfw_score,
                                violence_score=violence_score,
                                hate_speech_score=0.0
                            )
                            
                            # Call make_decision synchronously (we're in a thread)
                            import asyncio
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            decision_result = loop.run_until_complete(make_decision(result))
                            loop.close()
                            
                            print(f"✅ Fixed stuck video {video_id}: decision={decision_result.get('decision')}, final_score={decision_result.get('final_score', 0):.3f}")
                        # If video is stuck in processing, mark as needing review
                        elif status in ['processing', 'uploaded', 'screened']:
                            # Update status to reviewed if scores are available, otherwise keep processing
                            if nsfw_score > 0 or violence_score > 0:
                                result = ModerationResult(
                                    video_id=video_id,
                                    risk_score=risk_score,
                                    nsfw_score=nsfw_score,
                                    violence_score=violence_score,
                                    hate_speech_score=0.0
                                )
                                import asyncio
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                decision_result = loop.run_until_complete(make_decision(result))
                                loop.close()
                                print(f"✅ Fixed stuck video {video_id}: decision={decision_result.get('decision')}, final_score={decision_result.get('final_score', 0):.3f}")
                            else:
                                print(f"⚠️  Video {video_id} still processing, scores not available yet")
                    except Exception as e:
                        print(f"❌ Failed to fix stuck video {video_id}: {e}")
                        import traceback
                        traceback.print_exc()
            
            # Sleep for 60 seconds before checking again
            time.sleep(60)
            
        except Exception as e:
            print(f"❌ Error in stuck videos fixer worker: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)  # Wait before retrying

@app.on_event("startup")
async def startup_event():
    """Start background worker on app startup to fix stuck videos"""
    import sys
    worker_thread = threading.Thread(target=fix_stuck_videos_worker, daemon=True)
    worker_thread.start()
    print("✅ Policy Engine service started with stuck videos fixer worker", flush=True)
    sys.stdout.flush()

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "policy_interpretation_enabled": AZURE_OPENAI_ENABLED and openai_client is not None
    }
