"""
SmartClaims Agent — Centralized Configuration
==============================================
Shared configuration and client setup used across all lab
exercises. Import this instead of repeating setup code.
 
Usage:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from utils.config import get_clients, MODEL, print_header
"""
 
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
 
 
# ─── Load Environment ─────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
 
# ─── Validate Required Variables ──────────────────────────
ENDPOINT = os.environ.get("PROJECT_ENDPOINT")
MODEL = os.environ.get("MODEL_DEPLOYMENT_NAME")
 
if not ENDPOINT:
    print("❌ ERROR: PROJECT_ENDPOINT not set in .env")
    print("   Copy .env.example to .env and fill in your values.")
    sys.exit(1)
 
if not MODEL:
    print("❌ ERROR: MODEL_DEPLOYMENT_NAME not set in .env")
    sys.exit(1)
 
# ─── File Paths ───────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CLAIMS_CSV = DATA_DIR / "contoso_claims_data.csv"
POLICY_DOC = DATA_DIR / "contoso_insurance_policy.md"
 
 
# ─── Client Factory ──────────────────────────────────────
def get_clients():
    """
    Create and return (project_client, openai_client).
    
    Uses DefaultAzureCredential which picks up:
    - Azure CLI login (az login)
    - Environment variables
    - Managed Identity (production)
    """
    project_client = AIProjectClient(
        endpoint=ENDPOINT,
        credential=DefaultAzureCredential(),
    )
    openai_client = project_client.get_openai_client()
    return project_client, openai_client
 
 
# ─── Display Helpers ──────────────────────────────────────
def print_header(lab_number, lab_name):
    """Print a formatted lab header."""
    print(f"\n{'='*65}")
    print(f"  Lab {lab_number}: {lab_name}")
    print(f"  SmartClaims AI Agent — Microsoft Foundry SDK v2.x")
    print(f"{'='*65}\n")
 
 
def print_step(step_text):
    """Print a formatted step divider."""
    print(f"\n{'─'*50}")
    print(f"  {step_text}")
    print(f"{'─'*50}")

# ─────────────────────────────────────────────────────────────
# 6. Function call loop (v2.x pattern)
# ─────────────────────────────────────────────────────────────
import json

def ask_with_functions(openai_client, agent, conversation_id,
                       user_input, tools, function_map):
    """
    Send a message and handle the v2.x function call loop.
    NOTE: Do NOT pass tools= to responses.create() when using
    agent_reference — tools are already on the agent definition.
    """

    response = openai_client.responses.create(
        conversation=conversation_id,
        extra_body={
            "agent_reference": {
                "name": agent.name,
                "version": agent.version,
                "type": "agent_reference",
            }
        },
        input=user_input,
        # ← tools= removed here (causes 400 when agent_reference is set)
    )

    # Loop until agent returns text (not function calls)
    max_rounds = 10  # safety limit
    for _ in range(max_rounds):
        function_calls = [
            item for item in response.output
            if item.type == "function_call"
        ]

        if not function_calls:
            return response.output_text

        # Execute each function call locally
        tool_outputs = []
        for fc in function_calls:
            print(f"    [TOOL CALL] {fc.name}({fc.arguments})")
            func = function_map.get(fc.name)
            if func:
                try:
                    args = json.loads(fc.arguments)
                    result = func(**args)
                except Exception as e:
                    result = json.dumps({"error": str(e)})
            else:
                result = json.dumps({"error": f"Unknown function: {fc.name}"})

            tool_outputs.append({
                "type": "function_call_output",
                "call_id": fc.call_id,
                "output": result if isinstance(result, str) else json.dumps(result),
            })

        # Send results back — again NO tools= here
         # Send results back — use previous_response_id, NOT conversation
        response = openai_client.responses.create(
            extra_body={
                "agent_reference": {
                    "name": agent.name,
                    "version": agent.version,
                    "type": "agent_reference",
                }
            },
            input=tool_outputs,
            previous_response_id=response.id,
        )
        
    return response.output_text