from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import os
import json
import boto3
import httpx
from botocore.exceptions import ClientError
from decimal import Decimal
from openai import AzureOpenAI

app = FastAPI()

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
DYNAMODB_VIDEOS_TABLE = os.getenv("DYNAMODB_VIDEOS_TABLE", "guardian-videos")
DYNAMODB_EVENTS_TABLE = os.getenv("DYNAMODB_EVENTS_TABLE", "guardian-events")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification:8005")

# AWS Clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
videos_table = dynamodb.Table(DYNAMODB_VIDEOS_TABLE)
events_table = dynamodb.Table(DYNAMODB_EVENTS_TABLE)

# Azure OpenAI client for reviewer copilot features (optional - disabled by default)
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

class ReviewItem(BaseModel):
    video_id: str
    risk_score: float
    flagged_frames: List[str]
    submitted_at: datetime = None

@app.post("/queue")
async def add_to_queue(item: ReviewItem):
    """Add video to human review queue (simplified - uses videos table)"""
    if item.submitted_at is None:
        item.submitted_at = datetime.utcnow()
    
    # Update video record to mark for review
    try:
        videos_table.update_item(
            Key={"video_id": item.video_id},
            UpdateExpression="SET #status = :status, review_submitted_at = :submitted_at, flagged_frames = :frames",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "review",
                ":submitted_at": item.submitted_at.isoformat(),
                ":frames": item.flagged_frames
            }
        )
    except ClientError as e:
        raise HTTPException(500, f"Failed to add to queue: {str(e)}")
    
    # Log review event
    try:
        events_table.put_item(
            Item={
                "event_id": f"{item.video_id}_{int(datetime.utcnow().timestamp() * 1000)}",
                "video_id": item.video_id,
                "event_type": "review_queued",
                "event_data": {
                    "risk_score": str(item.risk_score),
                    "flagged_frames_count": len(item.flagged_frames)
                },
                "timestamp": item.submitted_at.isoformat(),
                "ttl": int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)
            }
        )
    except ClientError as e:
        print(f"Failed to log event (non-critical): {e}")
    
    # Get queue position (count videos with status="review")
    try:
        response = videos_table.scan(
            FilterExpression="#status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "review"},
            Select="COUNT"
        )
        position = response.get('Count', 0)
    except ClientError as e:
        position = 0
    
    return {"status": "queued", "position": position}

@app.get("/queue")
async def get_queue():
    """Get all videos pending human review (query status=review OR decision=review)"""
    try:
        # Scan for videos with status="review" OR decision="review" so queue shows all borderline cases
        response = videos_table.scan(
            FilterExpression="(#status = :s) OR (#decision = :d)",
            ExpressionAttributeNames={"#status": "status", "#decision": "decision"},
            ExpressionAttributeValues={":s": "review", ":d": "review"}
        )
        items = response.get('Items', [])
        
        # Sort by review_submitted_at (or decided_at if not available)
        items.sort(key=lambda x: x.get('review_submitted_at', x.get('decided_at', '')))
        
        # Enhance items with AI summaries if available (optional feature)
        if AZURE_OPENAI_ENABLED and openai_client:
            for item in items:
                video_id = item.get("video_id")
                if video_id and not item.get("ai_summary"):
                    # Note: AI summary generation is available via /review/{video_id}/summary endpoint
                    item["ai_summary_available"] = True
        
        return {"items": items, "count": len(items)}
    except ClientError as e:
        raise HTTPException(500, f"Failed to get queue: {str(e)}")

@app.post("/review/{video_id}")
async def submit_review(video_id: str, approved: bool, notes: str = ""):
    """Submit human review decision (simplified - updates videos table)"""
    decision = "approved" if approved else "rejected"
    reviewed_at = datetime.utcnow()
    
    try:
        # Update video record with review decision
        videos_table.update_item(
            Key={"video_id": video_id},
            UpdateExpression="SET #status = :status, #decision = :decision, human_reviewed = :human_reviewed, reviewer_notes = :notes, reviewed_at = :reviewed_at",
            ExpressionAttributeNames={
                "#status": "status",
                "#decision": "decision"
            },
            ExpressionAttributeValues={
                ":status": decision,
                ":decision": decision,
                ":human_reviewed": True,
                ":notes": notes,
                ":reviewed_at": reviewed_at.isoformat()
            }
        )
    except ClientError as e:
        raise HTTPException(500, f"Failed to submit review: {str(e)}")
    
    # Log review event
    try:
        events_table.put_item(
            Item={
                "event_id": f"{video_id}_{int(datetime.utcnow().timestamp() * 1000)}",
                "video_id": video_id,
                "event_type": "review_completed",
                "event_data": {
                    "decision": decision,
                    "notes": notes,
                    "human_reviewed": True
                },
                "timestamp": reviewed_at.isoformat(),
                "ttl": int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)
            }
        )
    except ClientError as e:
        print(f"Failed to log event (non-critical): {e}")
    
    # Send notification via direct HTTP call
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{NOTIFICATION_SERVICE_URL}/notify",
                json={
                    "video_id": video_id,
                    "decision": decision,
                    "webhook_url": "https://webhook.site/unique-id"  # TODO: Get from video metadata
                },
                timeout=5.0
            )
    except Exception as e:
        print(f"Failed to send notification (non-critical): {e}")
    
    return {
        "video_id": video_id,
        "decision": decision,
        "reviewed_at": reviewed_at,
        "notes": notes
    }

@app.get("/review/{video_id}/summary")
async def get_review_summary(video_id: str, language: str = "en"):
    """Generate AI summary for reviewer (copilot feature - optional)"""
    if not AZURE_OPENAI_ENABLED or not openai_client:
        raise HTTPException(status_code=503, detail="AI copilot features are disabled. Set AZURE_OPENAI_ENABLED=true to enable.")
    
    try:
        # Get video data
        video_response = videos_table.get_item(Key={"video_id": video_id})
        if 'Item' not in video_response:
            raise HTTPException(404, "Video not found")
        video = video_response['Item']
        
        # Check if summary already exists
        if video.get("reviewer_summary"):
            return {"summary": video["reviewer_summary"], "cached": True}
        
        prompt = f"""Summarize this video moderation case for a human reviewer:

Video ID: {video_id}
Risk Score: {float(video.get('risk_score', 0)):.2f}
NSFW Score: {float(video.get('nsfw_score', 0)):.2f}
Violence Score: {float(video.get('violence_score', 0)):.2f}
Final Score: {float(video.get('final_score', 0)):.2f}
Frames Analyzed: {video.get('frames_analyzed', 0)}

Provide:
1. Brief summary of what was detected
2. Key timestamps/frames of concern (if available)
3. Context for the reviewer
4. Suggested focus areas

Be concise and actionable. Do NOT make the final decision - that is the reviewer's responsibility."""
        
        response = openai_client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {"role": "system", "content": f"You are a content moderation copilot assisting human reviewers. Provide clear, factual summaries. You do NOT make decisions - only assist reviewers. Respond in {language}."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400
        )
        
        summary = response.choices[0].message.content
        
        # Cache summary
        videos_table.update_item(
            Key={"video_id": video_id},
            UpdateExpression="SET reviewer_summary = :summary, summary_generated_at = :timestamp",
            ExpressionAttributeValues={
                ":summary": summary,
                ":timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return {"summary": summary, "cached": False, "language": language}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/review/{video_id}/suggest")
async def suggest_review_action(video_id: str):
    """AI suggestion for review action (copilot - does NOT make final decision)"""
    if not AZURE_OPENAI_ENABLED or not openai_client:
        raise HTTPException(status_code=503, detail="AI copilot features are disabled. Set AZURE_OPENAI_ENABLED=true to enable.")
    
    try:
        video_response = videos_table.get_item(Key={"video_id": video_id})
        if 'Item' not in video_response:
            raise HTTPException(404, "Video not found")
        video = video_response['Item']
        
        prompt = f"""Based on these moderation scores, suggest a review action:

Risk Score: {float(video.get('risk_score', 0)):.2f}
NSFW Score: {float(video.get('nsfw_score', 0)):.2f}
Violence Score: {float(video.get('violence_score', 0)):.2f}
Final Score: {float(video.get('final_score', 0)):.2f}

Provide:
1. Suggested action (Approve/Reject) with confidence level
2. Reasoning for the suggestion
3. Key factors to consider
4. Potential edge cases

IMPORTANT: This is a SUGGESTION only. The human reviewer makes the final decision."""
        
        response = openai_client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {"role": "system", "content": "You are a content moderation copilot. You provide suggestions to assist reviewers, but the final decision is always made by the human reviewer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=300
        )
        
        suggestion = response.choices[0].message.content
        
        return {
            "suggestion": suggestion,
            "disclaimer": "This is an AI suggestion only. The human reviewer makes the final decision.",
            "video_id": video_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/review/{video_id}/explain")
async def explain_decision_to_creator(video_id: str, language: str = "en"):
    """Generate explanation for content creator (multilingual support - optional)"""
    if not AZURE_OPENAI_ENABLED or not openai_client:
        raise HTTPException(status_code=503, detail="AI explanation features are disabled. Set AZURE_OPENAI_ENABLED=true to enable.")
    
    try:
        video_response = videos_table.get_item(Key={"video_id": video_id})
        if 'Item' not in video_response:
            raise HTTPException(404, "Video not found")
        video = video_response['Item']
        
        # Check if explanation exists
        explanation_key = f"creator_explanation_{language}"
        if video.get(explanation_key):
            return {"explanation": video[explanation_key], "cached": True, "language": language}
        
        prompt = f"""Explain this moderation decision to a content creator in a clear, professional manner:

Video ID: {video_id}
Decision: {video.get('decision', 'pending')}
NSFW Score: {float(video.get('nsfw_score', 0)):.2f}
Violence Score: {float(video.get('violence_score', 0)):.2f}

Provide:
1. Clear explanation of what was detected
2. Why the decision was made
3. What the creator can do (if applicable)
4. How to appeal (if applicable)

Be professional, clear, and helpful. Respond in {language}."""
        
        response = openai_client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {"role": "system", "content": f"You are a helpful content moderation assistant explaining decisions to creators. Be professional and clear. Respond in {language}."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=400
        )
        
        explanation = response.choices[0].message.content
        
        # Cache explanation
        videos_table.update_item(
            Key={"video_id": video_id},
            UpdateExpression=f"SET {explanation_key} = :explanation, {explanation_key}_generated_at = :timestamp",
            ExpressionAttributeValues={
                ":explanation": explanation,
                ":timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return {"explanation": explanation, "cached": False, "language": language}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        response = videos_table.scan(
            FilterExpression="#status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "review"},
            Select="COUNT"
        )
        queue_size = response.get('Count', 0)
    except:
        queue_size = 0
    
    return {
        "status": "healthy",
        "queue_size": queue_size,
        "ai_copilot_enabled": AZURE_OPENAI_ENABLED and openai_client is not None
    }
