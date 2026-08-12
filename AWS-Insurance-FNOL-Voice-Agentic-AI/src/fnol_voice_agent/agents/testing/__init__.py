"""Test-only doubles for the agent core. `fake_llm.py`'s `FakeBedrockConverseClient` is
the deterministic stand-in `aws/bedrock_router.py`'s functions accept in place of a real
Bedrock client -- see docs/phase5/BUILD-PLAN.md Stage 4. Nothing here ever makes a
network call.
"""
