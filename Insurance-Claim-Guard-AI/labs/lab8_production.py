"""
Lab 8: Production Readiness - Tracing, Security, Versioning
=============================================================
v2.x - Standard OpenTelemetry (no AIProjectInstrumentor)
Run: python labs/lab8_production.py
"""
 
import sys
import os
 
# MUST be set BEFORE importing SDK
os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"
 
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
 
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor, ConsoleSpanExporter,
)
from azure.ai.projects.models import PromptAgentDefinition
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError
from utils.config import get_clients, MODEL, print_header, print_step
 
 
def main():
    print_header(8, "Production Readiness")
 
    # -- Step 1: Enable OpenTelemetry Tracing ------------
    print_step("Step 1: Enable OpenTelemetry Tracing")
 
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
 
    # v2.x: Use standard OpenTelemetry instrumentation
    # The SDK auto-emits spans when AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true
    # For Azure Monitor in production:
    #   from azure.monitor.opentelemetry import configure_azure_monitor
    #   configure_azure_monitor(connection_string="InstrumentationKey=...")
    print("   [OK] Tracing enabled (console exporter)")
    print("   For production: use azure-monitor-opentelemetry")
 
    project_client, openai_client = get_clients()
 
    # -- Step 2: Error Handling Pattern ------------------
    print_step("Step 2: Error Handling Pattern")
 
    def safe_call(openai_client, agent, user_input, conv_id=None):
        """Production-grade agent call with error handling."""
        try:
            kwargs = {
                "extra_body": {"agent_reference": {
                    "name": agent.name, "version": agent.version,
                    "type": "agent_reference"}},
                "input": user_input,
            }
            if conv_id:
                kwargs["conversation"] = conv_id
            r = openai_client.responses.create(**kwargs)
            return {"ok": True, "text": r.output_text}
        except ClientAuthenticationError:
            return {"ok": False, "error": "Auth failed. Run: az login"}
        except HttpResponseError as e:
            if e.status_code == 429:
                return {"ok": False, "error": "Rate limited. Wait and retry."}
            return {"ok": False, "error": f"HTTP {e.status_code}: {e.message}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
 
    print("   [OK] safe_call() wrapper defined")
 
    # -- Step 3: Agent Versioning ------------------------
    print_step("Step 3: Agent Versioning")
 
    v1 = project_client.agents.create_version(
        agent_name="smartclaims-prod",
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions="You are SmartClaims v1. Basic assistant.",
        ),
    )
    print(f"   v1: {v1.name} version={v1.version}")
 
    v2 = project_client.agents.create_version(
        agent_name="smartclaims-prod",
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions="You are SmartClaims v2. Enhanced with citations.",
        ),
    )
    print(f"   v2: {v2.name} version={v2.version}")
    print("   Both versions coexist - route traffic by version number")
 
    # Test with error handler
    result = safe_call(openai_client, v2, "Hello from v2!")
    if result["ok"]:
        print(f"   v2 says: {result['text'][:200]}")
    else:
        print(f"   Error: {result['error']}")
 
    # -- Step 4: Security Checklist ----------------------
    print_step("Step 4: Security Best Practices")
    print()
    print("   | Practice            | Details                        |")
    print("   |---------------------|--------------------------------|")
    print("   | Auth in production  | ManagedIdentityCredential      |")
    print("   | Least-privilege     | Azure AI User for developers   |")
    print("   | Secrets             | Azure Key Vault (not .env)     |")
    print("   | Input validation    | Limit length, strip control    |")
    print("   | Audit logging       | Enable in Foundry settings     |")
 
    # -- Step 5: Cost Management -------------------------
    print_step("Step 5: Cost Management")
    print()
    print("   | Component            | Pricing Basis                 |")
    print("   |----------------------|-------------------------------|")
    print("   | GPT-4o-mini model    | Per input/output token        |")
    print("   | Code Interpreter     | Per session (1-hour active)   |")
    print("   | File Storage         | Per GB stored                 |")
    print("   | Tavily Search        | Per API call (1K free/month)  |")
    print("   | Vector Store         | Per GB indexed                |")
    print("   Tip: gpt-4o-mini is ~10x cheaper than gpt-4o.")
 
    # -- Step 6: Clean Up All Lab Agents -----------------
    print_step("Step 6: Clean Up All Lab Agents")
    for name in [
        "smartclaims-hello", "smartclaims-policy-qa",
        "smartclaims-analytics", "smartclaims-functions",
        "smartclaims-unified", "smartclaims-regulatory",
        "smartclaims-prod",
    ]:
        try:
            project_client.agents.delete_agent(name)
            print(f"   [OK] Deleted: {name}")
        except Exception:
            print(f"   [SKIP] {name}")
 
    print(f"\n{'='*65}")
    print("  [OK] Lab 8 Complete!")
    print("  Next: Lab 9 - FastAPI Web App Deployment")
    print(f"{'='*65}\n")
 
 
if __name__ == "__main__":
    main()

