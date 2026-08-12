"""Phase 5 Stage 5: Guardrails (`ADR-010`) + PII redaction (`ADR-011`).

Two independent modules, kept separate because they answer different questions:
  - `client.py` -- *is this text safe to send to the model / return to the caller* (Bedrock Guardrails,
    called explicitly via `ApplyGuardrail`, never bolted onto a model invocation -- `ADR-010`).
  - `pii.py` -- *what does this text look like once it's been scrubbed for durable storage* (transcript/log
    redaction -- `ADR-011`'s boundary table).

Neither module talks to the other. A LangGraph node (Stage 6) is expected to call both, in the ADR-010
sequence, independently of whichever store/log write eventually uses `pii.py`'s redaction.
"""

from __future__ import annotations
