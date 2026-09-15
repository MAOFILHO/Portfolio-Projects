# D16 smoke call — result

Run 2026-09-15. Runbook: `docs/phase6/smoke-call-runbook.md`. Prior attempt (2026-09-14, correlation
id `393815d8`) hit the pre-#61 image and produced no spans — not repeated here.

## Call

- Correlation id: `aa509ec4-0c99-4dae-a339-39bf4957fe55`
- Connection id: `1c005e80-0d28-4e81-b4b8-03be3c4846af`
- Time: 2026-09-15T13:13:06Z–13:13:50Z UTC, 8 turns, `duration_ms=42257`
- Live container revision at call time: `ca-azbank-echo-p0--p6a20260914114410` (verified via `az
  containerapp show` before the call, matches issue #61's code)
- Deviation from script: the caller asked for accounts + made a transfer, not a plain balance
  check. Both are valid authenticated intents; this doesn't affect what D16 is checking.

## Delivery — confirmed

17 spans landed in `AppDependencies` under one trace (`OperationId
0fbed5fc19c793d970e889a2758792ee`), workspace `workspace-rgazurebankingvoiceagenticai1D`:

- 1 `call` span, 8 `turn` spans, 2 `tool_call` spans (`list_accounts`, `transfer`, both
  `gate_decision=allowed`), 3 `core_banking` spans (the PIN check at
  `/credential-checks` plus one per tool call) with their auto-instrumented HTTP children.

## `call` span attributes — match D15 exactly

`correlation_id, connection_id, auth_state=authenticated, end_reason=caller_hangup, turn_count=8,
duration_ms=42257, closed_path_taken=False`. No `closed_path_cause` — correct by design
(`session.py:300-302`: only set when `closed_path_taken=True`). No extra attributes. Nothing else
present on the span.

## B2 scan — clean

Searched every column of every row on this trace for the literal PIN (`1234`): **zero matches.**

## Metrics — landed

`b5.turn_latency_seconds` (×2) and `b4.daily_minutes_used` (×1) present in the window.

## Verdict

Delivery proven. Issue #62's criteria (Phase 6 exit criteria 6/7/8/12) are met by live evidence, not
just code review.
