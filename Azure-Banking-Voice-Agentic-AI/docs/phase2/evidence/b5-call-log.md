# #24 — B5 call log

Detailed per-call record for the ≥100-real-turn B5 provisional figure (`docs/PLAN.md`'s Phase 2
Exit paragraph). `PROJECT_STATE.md` keeps only the running tally per decision 18 (current-state
only, size-ceilinged) — this file is the history, moved out here 2026-09-08 once the call log grew
past a few entries.

All timelines pulled from Log Analytics (`workspace-rgazurebankingvoiceagenticai1D`,
`bf520f2c-e2bc-4488-8965-9317a7922c74` — see `PROJECT_STATE.md`'s "Resources live now" for why this
one, not the documented-but-stale `...aiCS`). `az containerapp logs show --follow`/`--tail` (the
live log-stream endpoint) is unreachable from Marco's network entirely — TCP connect to
`canadacentral.azurecontainerapps.dev:443` times out, confirmed from both a Claude Code session and
Marco's own terminal directly; cause unknown, not a sandbox issue. Log Analytics is the working
fallback, with its normal few-minute ingestion delay.

Each latency sample = time from a `caller turn ended` line (server VAD's `speech_stopped`) to the
*next* `agent audio started` line (first `response.output_audio.delta` of the following response
cycle) — see `session.py`'s `model_to_transport()` and `42e02c5`'s commit message for why this
pairing is correct even across a tool-call round-trip with no audio of its own.

## Calls

**Call 1 (2026-09-08, on `:p2`, before B5 logging existed — 0 samples).** `handoff: triage ->
banking` fired correctly; the model attempted `handoff_to_banking` *again* while already on
`banking` and was refused (`BANKING.handoff_to` is empty — this is 2026-09-07's `/code-review` fix
firing live for the first time); `get_balance`, `list_accounts`, `transfer` all refused with a
spoken reply; clean hangup at 82s, no B4 cap hit. Found: no B5 timestamp pair existed at all
(fixed, `42e02c5`) and a second incoming call ~43s later got
`Microsoft.Communication.AnswerFailed` (unexplained, never recurred on any later call).

**Call 2 (2026-09-08, on `:p3`, B5 logging live).** Same shape as Call 1 — handoff fired,
`get_balance`/`list_accounts` refused, clean hangup, no `AnswerFailed`. First real B5 numbers: 297,
570, 440, 280ms (all sub-second). `speech_stopped` confirmed live — marked so in code (`e12a86f`).

**Call 3 (2026-09-08, on `:p3`).** Same shape — handoff fired, `list_accounts`/`get_balance`
refused, clean hangup, no `AnswerFailed`. 6 samples: 495, 290, 247, 459, 616, 276ms.

**Call 4 (2026-09-08, on `:p3`).** Same shape, 5 samples: 345, 571, 669, 629, 337ms. Dead air only
~2.5s this time — Marco confirmed he spoke immediately rather than waiting; not code variability,
just when the caller happened to talk (confirms the gap's real cause: it's exactly how long the
caller waits before speaking, since nothing ever prompts the agent to speak first).

**Call 5 (2026-09-08, on `:p3`).** Same shape, 4 samples: 798, 918, 636, 291ms — the first two are
the slowest seen so far, still sub-second.

**Call 6 (2026-09-08, on `:p3`).** Handoff fired, `get_balance` refused twice (model retried it
within the same reply, model's spoken refusal recommended the banking app or a branch instead — a
natural paraphrase, not a code change), clean hangup. 3 samples: 639, 545, 263ms. **New pairing
rule found**: Marco's first utterance produced a `caller turn ended` with no reply before he spoke
again — the model started responding, got interrupted (barge-in) when he kept talking, and that
response never completed (no audio, no second `caller turn ended` paired to it). Correctly
excluded from the sample count: whenever two `caller turn ended` lines appear back-to-back with no
`agent audio started` between them, the earlier one is an aborted/interrupted response, not a real
round-trip — discard it, only pair the later one. **New, unexplained**: ~55s after Call 6 ended, a
second `IncomingCall` connected and disconnected in ~2.3s with zero conversation (no `caller turn
ended`, no `agent audio started` at all) — cause unknown, didn't recur before this. Second
unexplained near-empty/failed call now on record (Call 1 had `AnswerFailed`, this one connected
but had no content) — watch for a third before treating this as a real pattern.

## Open findings (not fixed yet)

- **Dead air before the agent speaks first**, every call so far (2.5-11s, varies with how quickly
  the caller talks): `session.py` sends no initial `response.create`, so the greeting only happens
  once the caller talks and VAD detects their turn ending. TRIAGE's instructions say to greet
  first but nothing triggers it. Marco's call on timing this fix.
- **Odd second incoming calls, twice now, different shapes**: Call 1's follow-up got
  `AnswerFailed`; Call 6's follow-up connected but had zero conversation (~2.3s, no turn-ended, no
  audio). Neither recurred immediately after. Not yet a confirmed pattern — watch for a third.

## Running sample count

| Call | Samples | Latencies (ms) |
|---|---|---|
| 1 | 0 (pre-instrumentation) | — |
| 2 | 4 | 297, 570, 440, 280 |
| 3 | 6 | 495, 290, 247, 459, 616, 276 |
| 4 | 5 | 345, 571, 669, 629, 337 |
| 5 | 4 | 798, 918, 636, 291 |
| 6 | 3 | 639, 545, 263 |

**N = 22 / ≥100.** Add new calls as new table rows plus a short paragraph above, same format.
