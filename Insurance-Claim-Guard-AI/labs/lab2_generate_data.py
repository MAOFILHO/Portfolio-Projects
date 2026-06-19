"""
Lab 2: Prepare Production Data
===============================
Generates a 500-record insurance claims CSV and verifies
the policy document is in place.
 
Run: python labs/lab2_generate_data.py
"""
 
import sys
import os
import csv
import random
from datetime import datetime, timedelta
 
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.config import DATA_DIR, CLAIMS_CSV, POLICY_DOC, print_header, print_step
 
# ─── Dataset Configuration ────────────────────────────────
NUM_RECORDS = 500
 
INCIDENT_TYPES = [
    "Auto Collision", "Property Damage", "Medical Claim",
    "Theft", "Natural Disaster", "Liability", "Fire Damage",
]
REGIONS = ["North", "South", "East", "West", "Central"]
POLICY_TYPES = ["Auto", "Property", "Health", "Life", "Liability"]
STATUSES = ["Approved", "Denied", "Under Review", "Settled", "Pending"]
ADJUSTER_NAMES = [
    "Sarah Johnson", "Michael Chen", "Priya Patel",
    "James Wilson", "Maria Garcia", "David Kim",
    "Lisa Anderson", "Robert Taylor", "Aisha Mohammed",
    "Thomas Brown",
]
 
# Realistic claim amount ranges (USD) by incident type
AMOUNT_RANGES = {
    "Auto Collision":   (2_000, 75_000),
    "Property Damage":  (5_000, 250_000),
    "Medical Claim":    (500, 150_000),
    "Theft":            (1_000, 50_000),
    "Natural Disaster": (10_000, 500_000),
    "Liability":        (5_000, 200_000),
    "Fire Damage":      (15_000, 400_000),
}
 
DEDUCTIBLE_OPTIONS = {
    "Auto": [500, 1000, 1500],
    "Property": [1000, 2500, 5000],
    "Health": [250, 500, 1000],
    "Life": [0],
    "Liability": [1000, 2000],
}
 
 
def generate_record(i):
    """Generate one realistic insurance claim record."""
    base = datetime(2024, 7, 1)
    inc_date = base + timedelta(days=random.randint(0, 540))
    clm_date = inc_date + timedelta(days=random.randint(0, 14))
 
    itype = random.choice(INCIDENT_TYPES)
    region = random.choice(REGIONS)
    ptype = random.choice(POLICY_TYPES)
    status = random.choice(STATUSES)
 
    mn, mx = AMOUNT_RANGES[itype]
    amount = round(random.uniform(mn, mx), 2)
 
    if status == "Denied":
        approved = 0.0
    elif status in ("Approved", "Settled"):
        approved = round(amount * random.uniform(0.6, 1.0), 2)
    else:
        approved = 0.0
 
    deductible = random.choice(DEDUCTIBLE_OPTIONS[ptype])
 
    fraud = random.choices([True, False], weights=[8, 92])[0]
    fscore = (round(random.uniform(0.65, 0.99), 2) if fraud
              else round(random.uniform(0.01, 0.40), 2))
 
    if status in ("Approved", "Settled", "Denied"):
        pdays = random.randint(3, 90)
        sdate = (clm_date + timedelta(days=pdays)).strftime("%Y-%m-%d")
    else:
        pdays = random.randint(1, 30)
        sdate = ""
 
    return {
        "claim_id": f"CLM-{i:04d}",
        "policy_number": f"POL-{random.randint(100000, 999999)}",
        "policyholder_name": f"Customer_{i:04d}",
        "claim_date": clm_date.strftime("%Y-%m-%d"),
        "incident_date": inc_date.strftime("%Y-%m-%d"),
        "incident_type": itype,
        "claim_amount": amount,
        "approved_amount": approved,
        "status": status,
        "adjuster_name": random.choice(ADJUSTER_NAMES),
        "fraud_flag": fraud,
        "fraud_score": fscore,
        "region": region,
        "policy_type": ptype,
        "deductible": deductible,
        "settlement_date": sdate,
        "processing_days": pdays,
    }
 
 
def main():
    print_header(2, "Prepare Production Data")
 
    # ── Generate CSV ──
    print_step("Step 1: Generate Claims Dataset")
 
    random.seed(42)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
 
    records = [generate_record(i + 1) for i in range(NUM_RECORDS)]
 
    with open(CLAIMS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
 
    fraud_count = sum(1 for r in records if r["fraud_flag"])
    avg_amt = sum(r["claim_amount"] for r in records) / len(records)
 
    print(f"   ✅ Generated {NUM_RECORDS} records → {CLAIMS_CSV.name}")
    print(f"   Fraud cases: {fraud_count} ({fraud_count/NUM_RECORDS*100:.1f}%)")
    print(f"   Avg claim:   ${avg_amt:,.2f}")
 
    # ── Verify policy doc ──
    print_step("Step 2: Verify Policy Document")
 
    if POLICY_DOC.exists():
        lines = len(POLICY_DOC.read_text().splitlines())
        print(f"   ✅ Found: {POLICY_DOC.name} ({lines} lines)")
    else:
        print(f"   ❌ NOT FOUND: {POLICY_DOC}")
        print(f"   Please create data/contoso_insurance_policy.md")
        print(f"   (see Step 2.2 in the lab guide)")
 
    print(f"\n{'='*65}")
    print("  ✅ Lab 2 Complete!")
    print("  Next → python labs/lab3_file_search.py")
    print(f"{'='*65}\n")
 
 
if __name__ == "__main__":
    main()
