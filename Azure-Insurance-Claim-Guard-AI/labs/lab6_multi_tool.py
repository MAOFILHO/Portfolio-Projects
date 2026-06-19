"""
Lab 6: Multi-Tool Agent - Complete SmartClaims
===============================================
v2.x - Native tools + manual function call handling
Run: python labs/lab6_multi_tool.py
"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.config import (
    get_clients, MODEL, CLAIMS_CSV, POLICY_DOC,
    print_header, print_step, ask_with_functions,
)
from utils.business_functions import get_claim_status, calculate_fraud_risk
from azure.ai.projects.models import PromptAgentDefinition


# Function schemas (same as Lab 5)
FUNCTION_MAP = {
    "get_claim_status": get_claim_status,
    "calculate_fraud_risk": calculate_fraud_risk,
}

FUNCTION_SCHEMAS = [
    {
        "type": "function",
        "name": "get_claim_status",
        "description": (
            "Look up the current status of an insurance claim by ID. "
            "Returns claim details including status, amount, adjuster, "
            "and fraud score."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "string",
                    "description": "Claim ID in CLM-XXXX format"
                }
            },
            "required": ["claim_id"]
        }
    },
    {
        "type": "function",
        "name": "calculate_fraud_risk",
        "description": (
            "Calculate fraud risk score for a new insurance claim."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "incident_type": {
                    "type": "string",
                    "enum": [
                        "Auto Collision", "Property Damage",
                        "Medical Claim", "Theft",
                        "Natural Disaster", "Liability", "Fire Damage"
                    ]
                },
                "claim_amount": {"type": "number"},
                "region": {
                    "type": "string",
                    "enum": ["North", "South", "East", "West", "Central"]
                },
                "days_since_policy_start": {"type": "integer"}
            },
            "required": [
                "incident_type", "claim_amount",
                "region", "days_since_policy_start"
            ]
        }
    },
]


def main():
    print_header(6, "Multi-Tool Agent - Complete SmartClaims")
    project_client, openai_client = get_clients()

    # -- Step 1: Prepare Resources -----------------------
    print_step("Step 1: Prepare All Resources")

    # CSV for Code Interpreter
    csv_file = openai_client.files.create(
        purpose="assistants",
        file=open(str(CLAIMS_CSV), "rb"),
    )
    print(f"   [OK] CSV uploaded: {csv_file.id}")

    # Vector Store for File Search
    vs = openai_client.vector_stores.create(name="SmartClaimsPolicies")
    openai_client.vector_stores.files.upload_and_poll(
        vector_store_id=vs.id,
        file=open(str(POLICY_DOC), "rb"),
    )
    print(f"   [OK] Policy indexed in Vector Store: {vs.id}")

    # -- Step 2: Configure All Tools ---------------------
    print_step("Step 2: Configure All Tools")

    # In v2.x, native tools are passed as plain dicts — no .definitions
    code_interp_def = {
        "type": "code_interpreter",
        "container": {
            "type": "auto",
            "file_ids": [csv_file.id]
        }
    }

    file_search_def = {
        "type": "file_search",
        "vector_store_ids": [vs.id]
    }

    # Combine native tool dicts + custom function schemas
    all_tools = [code_interp_def, file_search_def] + FUNCTION_SCHEMAS
    print(f"   [OK] {len(all_tools)} tool definitions combined")
    print("   - CodeInterpreter (native, server-side)")
    print("   - FileSearch (native, server-side)")
    print("   - get_claim_status (custom, client-side)")
    print("   - calculate_fraud_risk (custom, client-side)")

    # -- Step 3: Create Unified Agent --------------------
    print_step("Step 3: Create Unified SmartClaims Agent")

    agent = project_client.agents.create_version(
        agent_name="smartclaims-unified",
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions=(
                "You are SmartClaims - an AI insurance claims agent. "
                "Three tool categories: "
                "(1) FILE SEARCH - policy docs for coverage, exclusions, procedures. "
                "(2) CODE INTERPRETER - claims CSV analysis with Python. "
                "Columns: claim_id, incident_type, claim_amount, approved_amount, "
                "status, fraud_flag, fraud_score, region, policy_type, processing_days. "
                "(3) FUNCTIONS - get_claim_status(claim_id), "
                "calculate_fraud_risk(incident_type, claim_amount, region, "
                "days_since_policy_start). "
                "Pick the right tool(s). You may chain multiple tools."
            ),
            tools=all_tools,
        ),
    )
    print(f"   Agent: {agent.name} v{agent.version}")

    # -- Step 4: Test Multi-Tool Scenarios ---------------
    print_step("Step 4: Test Multi-Tool Scenarios")

    scenarios = [
        ("Function - Claim Lookup",
         "What is the status of claim CLM-0042?"),
        ("File Search - Policy",
         "Does our policy cover ride-sharing incidents?"),
        ("Code Interpreter - Analytics",
         "How many claims are Under Review? Show status breakdown."),
        ("Function - Fraud Assessment",
         "New Fire Damage claim: $350K, West region, 60-day-old policy. Fraud risk?"),
        ("Multi-Tool - Analysis + Policy",
         "Which incident type has the highest avg claim amount? "
         "What does our policy say about exclusions for that type?"),
    ]

    for title, q in scenarios:
        print(f"\n   --- {title} ---")
        print(f"   Q: {q[:80]}")

        # Fresh conversation per scenario — prevents call_id conflicts
        conv = openai_client.conversations.create()

        answer = ask_with_functions(
            openai_client, agent, conv.id,
            q, all_tools, FUNCTION_MAP,
        )

        if len(answer) > 500:
            answer = answer[:500] + "..."
        print(f"   A: {answer}")

    # -- Step 5: Clean Up --------------------------------
    print_step("Step 5: Clean Up")
    project_client.agents.delete(agent.name)
    openai_client.vector_stores.delete(vs.id)
    print("   [OK] All resources cleaned up")

    print(f"\n{'='*65}")
    print("  [OK] Lab 6 Complete!")
    print("  Next: python labs/lab7_tavily_search.py")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()