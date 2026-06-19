"""
Lab 5: Function Tool Agent - Custom Business Logic
====================================================
v2.x Responses API - Manual function call handling
Run: python labs/lab5_function_tools.py
"""
 
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
 
from utils.config import (
    get_clients, MODEL, print_header, print_step, ask_with_functions,
)
from utils.business_functions import get_claim_status, calculate_fraud_risk
from azure.ai.projects.models import PromptAgentDefinition
 
 
# --------------------------------------------------
# Function registry and schemas
# --------------------------------------------------
FUNCTION_MAP = {
    "get_claim_status": get_claim_status,
    "calculate_fraud_risk": calculate_fraud_risk,
}
 
FUNCTION_TOOLS = [
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
                    "description": "Claim ID in CLM-XXXX format (e.g., CLM-0042)"
                }
            },
            "required": ["claim_id"]
        }
    },
    {
        "type": "function",
        "name": "calculate_fraud_risk",
        "description": (
            "Calculate fraud risk score for a new insurance claim. "
            "Returns risk score (0-1), risk level, and recommendation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "incident_type": {
                    "type": "string",
                    "description": "Type of incident",
                    "enum": [
                        "Auto Collision", "Property Damage",
                        "Medical Claim", "Theft",
                        "Natural Disaster", "Liability",
                        "Fire Damage"
                    ]
                },
                "claim_amount": {
                    "type": "number",
                    "description": "Dollar amount of the claim"
                },
                "region": {
                    "type": "string",
                    "description": "Geographic region",
                    "enum": ["North", "South", "East", "West", "Central"]
                },
                "days_since_policy_start": {
                    "type": "integer",
                    "description": "Days since policy was activated"
                }
            },
            "required": [
                "incident_type", "claim_amount",
                "region", "days_since_policy_start"
            ]
        }
    },
]
 
 
def main():
    print_header(5, "Function Tool Agent - Custom Business Logic")
    project_client, openai_client = get_clients()
 
    # -- Step 1: Define function schemas -----------------
    print_step("Step 1: Register Function Schemas")
    for tool in FUNCTION_TOOLS:
        params = list(tool["parameters"]["properties"].keys())
        print(f"   [OK] {tool['name']}({', '.join(params)})")
 
    # -- Step 2: Create agent with function tools --------
    print_step("Step 2: Create Agent")
 
    agent = project_client.agents.create_version(
        agent_name="smartclaims-functions",
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions=(
                "You are SmartClaims Operations Agent. Tools available: "
                "(1) get_claim_status - look up any claim by ID (CLM-XXXX). "
                "(2) calculate_fraud_risk - assess fraud risk for new claims. "
                "Always use tools when relevant. Present results clearly "
                "with key details highlighted."
            ),
            tools=FUNCTION_TOOLS,
        ),
    )
    print(f"   Agent: {agent.name} v{agent.version}")
 
    # -- Step 3: Test function calls ---------------------
 
    print_step("Step 3: Test Function Calls")

    tests = [
        ("Claim Lookup",
         "What is the status of claim CLM-0042?"),
        ("Fraud Risk Assessment",
         "Calculate fraud risk for a $85,000 Theft claim from the "
         "West region. Policy started 45 days ago."),
        ("High-Risk Scenario",
         "New Fire Damage claim: $350,000, Central region, policy "
         "only 20 days old. What is the fraud risk?"),
        ("Combined Query",
         "Look up CLM-0100. Based on the details, does the existing "
         "fraud score seem appropriate?"),
    ]

    for title, question in tests:
        print(f"\n   --- {title} ---")
        print(f"   User: {question[:80]}")

        # Fresh conversation per question avoids call_id conflicts
        conversation = openai_client.conversations.create()

        answer = ask_with_functions(
            openai_client, agent, conversation.id,
            question, FUNCTION_TOOLS, FUNCTION_MAP,
        )

        if len(answer) > 500:
            answer = answer[:500] + "..."
        print(f"   Agent: {answer}")
 
    # -- Step 4: Clean up --------------------------------
    print_step("Step 4: Clean Up")
    project_client.agents.delete(agent.name)
    print("   [OK] Agent deleted")
 
    print(f"\n{'='*65}")
    print("  [OK] Lab 5 Complete!")
    print("  Next: python labs/lab6_multi_tool.py")
    print(f"{'='*65}\n")
 
 
if __name__ == "__main__":
    main()
