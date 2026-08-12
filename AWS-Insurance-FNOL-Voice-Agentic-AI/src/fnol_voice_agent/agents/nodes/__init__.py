"""LangGraph nodes (Stage 6, `docs/phase5/BUILD-PLAN.md`). Every node is built by a `make_*` factory
taking its external dependencies (a Bedrock caller, a guardrail client) as keyword arguments defaulting to
`None` -- production wiring (`agents/graph.py`) leaves them `None` (real clients constructed lazily
downstream, per `ADR-009`); tests inject `FakeBedrockConverseClient`/`MockGuardrailClient` explicitly. No
node imports boto3 or the `mcp` transport package directly -- only the plain, transport-agnostic handler
functions from `mcp/*_server.py`, per `ADR-012`.
"""
