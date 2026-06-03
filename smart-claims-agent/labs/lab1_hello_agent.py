"""
Lab 1: Your First Agent — Hello World
======================================
Run: python labs/lab1_hello_agent.py
"""
 
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
 
from utils.config import get_clients, MODEL, print_header, print_step
from azure.ai.projects.models import PromptAgentDefinition
 
 
def main():
    print_header(1, "Your First Agent — Hello World")
 
    # ── Step 1: Create clients ──────────────────────────
    print_step("Step 1: Initialize Clients")
    project_client, openai_client = get_clients()
    print("   ✅ Clients created")
 
    # ── Step 2: Create an agent version ─────────────────
    # PromptAgentDefinition defines the agent's model and
    # instructions (system prompt). create_version registers
    # the agent in your Foundry project.
    print_step("Step 2: Create Agent Version")
 
    agent = project_client.agents.create_version(
        agent_name="smartclaims-hello",
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions=(
                "You are SmartClaims, a friendly insurance assistant "
                "created by Contoso Insurance. You help customers "
                "with their insurance queries. Always be professional, "
                "clear, and helpful. When greeting someone, introduce "
                "yourself as SmartClaims."
            ),
        ),
    )
    print(f"   Agent: {agent.name} (version: {agent.version})")
 
    # ── Step 3: Send a single request ───────────────────
    # The agent_reference in extra_body routes the request
    # to YOUR agent (with its instructions) rather than
    # using the raw model directly.
    print_step("Step 3: Single Request")
 
    response = openai_client.responses.create(
        extra_body={
            "agent_reference": {
                "name": agent.name,
                "version": agent.version,
                "type": "agent_reference",
            }
        },
        input=(
            "Hi! I just purchased a new auto insurance policy. "
            "What does it typically cover?"
        ),
    )
    print(f"\n   👤 User: What does auto insurance cover?")
    print(f"   🤖 SmartClaims:\n   {response.output_text[:500]}")
 
    # ── Step 4: Multi-turn conversation ─────────────────
    # conversations.create() starts a stateful session.
    # Passing conversation=id in each call maintains context.
    print_step("Step 4: Multi-Turn Conversation")
 
    conversation = openai_client.conversations.create()
    print(f"   Conversation started (id: {conversation.id})")
 
    # Helper to call agent in this conversation
    def ask(user_input):
        return openai_client.responses.create(
            conversation=conversation.id,
            extra_body={
                "agent_reference": {
                    "name": agent.name,
                    "version": agent.version,
                    "type": "agent_reference",
                }
            },
            input=user_input,
        )
 
    # Turn 1
    r1 = ask("I want to file a claim for a car accident that happened yesterday.")
    print(f"\n   👤 Turn 1: File a claim for car accident")
    print(f"   🤖 Response: {r1.output_text[:400]}")
 
    # Turn 2 — agent remembers the car accident context
    r2 = ask("What documents will I need to submit?")
    print(f"\n   👤 Turn 2: What documents do I need?")
    print(f"   🤖 Response: {r2.output_text[:400]}")
 
    # ── Step 5: Clean up ────────────────────────────────
    # Always delete agents when done to keep project clean.
    print_step("Step 5: Clean Up")
 
    project_client.agents.delete(agent.name)
    print(f"   ✅ Agent '{agent.name}' deleted")
 
    print(f"\n{'='*65}")
    print("  ✅ Lab 1 Complete!")
    print("  Next → python labs/lab2_generate_data.py")
    print(f"{'='*65}\n")
 
 
if __name__ == "__main__":
    main()
