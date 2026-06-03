"""
SmartClaims — Custom Business Logic Functions
==============================================
Used as Function Tools by the agent in Labs 5 and 6.
Simulates real business operations (database lookups,
ML model calls) that would run in production.
"""
 
import json
import csv
from pathlib import Path
 
CLAIMS_CSV = Path(__file__).resolve().parent.parent / "data" / "contoso_claims_data.csv"
 
 
def get_claim_status(claim_id: str) -> str:
    """
    Look up the current status of an insurance claim by ID.
 
    Simulates a database query to the claims management system.
    In production, this would call your CRM or claims API.
 
    Args:
        claim_id: Claim identifier in CLM-XXXX format
                  (e.g., CLM-0042, CLM-0100)
 
    Returns:
        JSON string with claim details or error message
    """
    claims = {}
    with open(CLAIMS_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            claims[row["claim_id"]] = row
 
    if claim_id in claims:
        c = claims[claim_id]
        return json.dumps({
            "claim_id": c["claim_id"],
            "policy_number": c["policy_number"],
            "policyholder": c["policyholder_name"],
            "status": c["status"],
            "incident_type": c["incident_type"],
            "incident_date": c["incident_date"],
            "claim_amount": float(c["claim_amount"]),
            "approved_amount": float(c["approved_amount"]),
            "adjuster": c["adjuster_name"],
            "fraud_score": float(c["fraud_score"]),
            "region": c["region"],
            "processing_days": int(c["processing_days"]),
        }, indent=2)
    else:
        return json.dumps({
            "error": f"Claim '{claim_id}' not found.",
            "hint": "Use format CLM-XXXX (e.g., CLM-0042)",
        })
 
 
def calculate_fraud_risk(
    incident_type: str,
    claim_amount: float,
    region: str,
    days_since_policy_start: int,
) -> str:
    """
    Calculate fraud risk score for a new insurance claim.
 
    Simulates an ML fraud detection model. In production,
    this would call your fraud detection microservice.
 
    Args:
        incident_type: One of Auto Collision, Property Damage,
            Medical Claim, Theft, Natural Disaster, Liability,
            Fire Damage
        claim_amount: Dollar amount of the claim (e.g., 45000.00)
        region: One of North, South, East, West, Central
        days_since_policy_start: Days since policy activation
 
    Returns:
        JSON string with risk score, level, and recommendation
    """
    type_risk = {
        "Auto Collision": 0.15, "Property Damage": 0.10,
        "Medical Claim": 0.12, "Theft": 0.25,
        "Natural Disaster": 0.05, "Liability": 0.18,
        "Fire Damage": 0.20,
    }
    score = type_risk.get(incident_type, 0.15)
 
    if claim_amount > 200000:
        score += 0.20
    elif claim_amount > 100000:
        score += 0.15
    elif claim_amount > 50000:
        score += 0.08
 
    region_mod = {
        "North": 0.00, "South": 0.03, "East": -0.02,
        "West": 0.05, "Central": 0.01,
    }
    score += region_mod.get(region, 0)
 
    if days_since_policy_start < 30:
        score += 0.15
    elif days_since_policy_start < 90:
        score += 0.10
 
    score = max(0.0, min(1.0, round(score, 2)))
 
    if score >= 0.50:
        level, rec = "HIGH", "Manual review by senior adjuster + SIU referral"
    elif score >= 0.30:
        level, rec = "MEDIUM", "Enhanced documentation + additional evidence"
    else:
        level, rec = "LOW", "Fast-track processing eligible"
 
    return json.dumps({
        "fraud_risk_score": score,
        "risk_level": level,
        "recommendation": rec,
        "factors": {
            "base_risk": type_risk.get(incident_type, 0.15),
            "amount_risk": "high" if claim_amount > 100000 else "normal",
            "region": region,
            "new_policy": days_since_policy_start < 90,
        },
    }, indent=2)
