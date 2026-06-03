"""
Lab 3: File Search Agent — Policy Q&A (RAG)
============================================
Run: python labs/lab3_file_search.py
"""
 
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
 
from utils.config import get_clients, MODEL, POLICY_DOC, print_header, print_step
from azure.ai.projects.models import PromptAgentDefinition, FileSearchTool
 
 
def main():
    print_header(3, "File Search Agent — Policy Q&A (RAG)")
    project_client, openai_client = get_clients()
 
    # ── Step 1: Create Vector Store ─────────────────────
    # A Vector Store is a managed document index. The service
    # automatically chunks, embeds, and indexes your documents.
    print_step("Step 1: Create Vector Store")
 
    vector_store = openai_client.vector_stores.create(
        name="ContosoPolicyStore"
    )
    print(f"   ID: {vector_store.id}")
 
    # ── Step 2: Upload and index the policy document ────
    # upload_and_poll does: upload → chunk → embed → index.
    # It waits until indexing is complete before returning.
    print_step("Step 2: Upload & Index Document")
 
    file = openai_client.vector_stores.files.upload_and_poll(
        vector_store_id=vector_store.id,
        file=open(str(POLICY_DOC), "rb"),
    )
    print(f"   File indexed: {file.id}")
 
    # ── Step 3: Create the File Search agent ────────────
    # FileSearchTool connects the agent to the Vector Store.
    print_step("Step 3: Create Agent with FileSearchTool")
 
    file_search_tool = FileSearchTool(
        vector_store_ids=[vector_store.id]
    )
 
    agent = project_client.agents.create_version(
        agent_name="smartclaims-policy-qa",
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions=(
                "You are SmartClaims Policy Assistant for Contoso Insurance. "
                "Answer questions using ONLY the uploaded policy documents. "
                "Rules: (1) Cite the specific section. (2) If not in the "
                "document, say so. (3) Be precise with numbers and limits. "
                "(4) For exclusions, suggest alternatives if available."
            ),
            tools=[file_search_tool],
        ),
    )
    print(f"   Agent: {agent.name} v{agent.version}")
 
    # ── Step 4: Run policy Q&A ──────────────────────────
    print_step("Step 4: Policy Q&A")
 
    conversation = openai_client.conversations.create()
 
    def ask(q):
        return openai_client.responses.create(
            conversation=conversation.id,
            extra_body={"agent_reference": {
                "name": agent.name, "version": agent.version,
                "type": "agent_reference"}},
            input=q,
        )
 
    questions = [
        "What is the maximum auto liability coverage?",
        "Are flood damages covered under property insurance?",
        "How do I file a claim after an auto accident? What docs do I need?",
        "What happens if someone commits insurance fraud?",
        "What are the health insurance deductible options for HDHP?",
    ]
 
    for i, q in enumerate(questions, 1):
        print(f"\n   ┌─ Question {i}: {q}")
        r = ask(q)
        answer = r.output_text
        if len(answer) > 500:
            answer = answer[:500] + "..."
        print(f"   └─ 🤖 {answer}")
 
    # ── Step 5: Clean up ────────────────────────────────
    print_step("Step 5: Clean Up")
    project_client.agents.delete(agent.name)
    openai_client.vector_stores.delete(vector_store.id)
    print("   ✅ Agent and Vector Store deleted")
 
    print(f"\n{'='*65}")
    print("  ✅ Lab 3 Complete!")
    print("  Next → python labs/lab4_code_interpreter.py")
    print(f"{'='*65}\n")
 
 
if __name__ == "__main__":
    main()
