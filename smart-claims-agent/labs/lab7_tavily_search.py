"""
Lab 7: Tavily Web Search - Regulatory Intelligence
====================================================
v2.x - Tavily as custom function tool with manual call handling
Requires: TAVILY_API_KEY in .env
Run: python labs/lab7_tavily_search.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.config import (
    get_clients, MODEL, print_header, print_step, ask_with_functions,
)
from azure.ai.projects.models import PromptAgentDefinition
from tavily import TavilyClient


# --------------------------------------------------
# Tavily search function
# --------------------------------------------------
tavily_client = None


def web_search(query: str) -> str:
    """
    Search the web for current information using Tavily API.

    Args:
        query: The search query

    Returns:
        JSON string with search results
    """
    global tavily_client
    if tavily_client is None:
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return json.dumps({"error": "TAVILY_API_KEY not set"})
        tavily_client = TavilyClient(api_key=api_key)

    try:
        response = tavily_client.search(
            query=query,
            max_results=5,
            include_answer=True,
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:300],
            })
        return json.dumps({
            "answer": response.get("answer", ""),
            "results": results,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# --------------------------------------------------
# Function schema and registry
# --------------------------------------------------
FUNCTION_MAP = {
    "web_search": web_search,
}

FUNCTION_TOOLS = [
    {
        "type": "function",
        "name": "web_search",
        "description": (
            "Search the web for current information about insurance "
            "regulations, industry news, compliance updates, or any "
            "current events not in the uploaded documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    },
]


def main():
    print_header(7, "Tavily Web Search - Regulatory Intelligence")

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        print("   [ERROR] TAVILY_API_KEY not set in .env")
        print("   Get a free key at https://tavily.com")
        return

    project_client, openai_client = get_clients()

    # -- Step 1: Register web_search ---------------------
    print_step("Step 1: Register Tavily as Function Tool")
    print("   [OK] web_search(query) - JSON schema registered")

    # -- Step 2: Create regulatory agent -----------------
    print_step("Step 2: Create Regulatory Intelligence Agent")

    agent = project_client.agents.create_version(
        agent_name="smartclaims-regulatory",
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions=(
                "You are SmartClaims Regulatory Intelligence Agent. "
                "Use the web_search tool to find current insurance "
                "regulations, compliance requirements, and industry "
                "news. Always cite sources with URLs. Present "
                "information in a clear, actionable format."
            ),
            tools=FUNCTION_TOOLS,
        ),
    )
    print(f"   Agent: {agent.name} v{agent.version}")

    # -- Step 3: Query for regulatory updates ------------
    print_step("Step 3: Query Regulatory Updates")

    queries = [
        "What are the latest insurance regulatory changes in the US?",
        "Are there new requirements for AI-powered fraud detection "
        "in insurance?",
        "What are the current NAIC model laws regarding data "
        "privacy in insurance?",
    ]

    for i, q in enumerate(queries, 1):
        print(f"\n   --- Query {i} ---")
        print(f"   Q: {q}")

        # Fresh conversation per query — prevents call_id conflicts
        conv = openai_client.conversations.create()

        answer = ask_with_functions(
            openai_client, agent, conv.id,
            q, FUNCTION_TOOLS, FUNCTION_MAP,
        )

        if len(answer) > 500:
            answer = answer[:500] + "..."
        print(f"   A: {answer}")

    # -- Step 4: Clean up --------------------------------
    print_step("Step 4: Clean Up")
    project_client.agents.delete(agent.name)
    print("   [OK] Agent deleted")

    print(f"\n{'='*65}")
    print("  [OK] Lab 7 Complete!")
    print("  Next: python labs/lab8_production.py")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()