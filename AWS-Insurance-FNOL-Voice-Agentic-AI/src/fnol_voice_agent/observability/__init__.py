"""Observability: the mechanisms Phase 11 wires so the running system can be watched, not just built.

`log_redaction`: the sink-level PII filter, `ADR-011` applied at the CloudWatch Logs boundary.
`guardrail_metrics`: Stage B1's guardrail-usage emitter, criterion 3's live source. Stage D (latency
signals) and Stage B2 (turn-latency sub-components -- deliberately scoped jointly with Stage D, not built
separately, per Marco's instruction) land in this package too, as they're built.
"""

from __future__ import annotations
