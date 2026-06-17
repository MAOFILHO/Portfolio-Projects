"""
Local agent script for AgentCore Observability demo.

Runs the Step 1 Strands agent under opentelemetry-instrument so traces
are sent to CloudWatch GenAI Observability. Not the Runtime container
entrypoint — this is a standalone local script.

Usage (called by step5_observability.py):
  opentelemetry-instrument python runtime/observability_agent.py --session-id "session-1234"
"""
import argparse
import os
import sys

from boto3.session import Session
from opentelemetry import baggage, context

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentcore.step1_agent import MODEL_ID, SYSTEM_PROMPT, build_agent


def parse_arguments():
    parser = argparse.ArgumentParser(description="Customer Support Agent — OTEL demo")
    parser.add_argument("--session-id", type=str, required=True, help="Session ID for trace correlation")
    return parser.parse_args()


def set_session_context(session_id: str):
    """Attach session ID to OpenTelemetry baggage for trace correlation."""
    ctx = baggage.set_baggage("session.id", session_id)
    token = context.attach(ctx)
    print(f"  Session ID '{session_id}' attached to telemetry context")
    return token


def main():
    args = parse_arguments()
    context_token = set_session_context(args.session_id)

    try:
        agent = build_agent()
        query = "What is the return policy for laptops, and do you have any ThinkPad recommendations?"
        print(f"\n  Query: {query}\n")
        result = agent(query)
        print("\n  Agent trace sent to CloudWatch GenAI Observability.")
    finally:
        context.detach(context_token)


if __name__ == "__main__":
    main()
