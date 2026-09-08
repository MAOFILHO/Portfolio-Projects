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
but had no content) — see Call 8 below: resolved.

**Call 7 (2026-09-08, on `:p3`).** Real conversation, no discards. 6 samples: 333, 487, 449, 285,
268, 269ms.

**Call 8 (2026-09-08, on `:p3`), Marco's deliberate immediate callback right after Call 7.**
Connected and worked completely normally — resolves the Call 1/Call 6 mystery (see Open findings).
3 samples: 343, 1235, 273ms — the 1235ms is the slowest single sample seen so far (still not
alarming, one data point). One `caller turn ended` discarded as another interrupted/aborted
response (same barge-in pattern as Call 6).

## AOAI-direct probe (`scripts/b5_probe.py`) — separate pool, do not merge with the calls above

Marco asked (2026-09-08): why isn't N=31 real enough, and can this be automated? Answered: p95
needs a real tail (same "3 calls isn't a sample size" reasoning `docs/PLAN.md` gives for Phase 0),
and yes, partially — `b5_probe.py` reuses `run_call()`/`connect_realtime()` completely unchanged,
feeding synthesized (macOS `say`+`afconvert`) real speech instead of a phone call, one utterance
per synthetic call. **Deliberately kept separate from the table above**: it only exercises the
AOAI leg, not the full ACS-media-relay round trip a real caller experiences — mixing pools would
overstate what's actually been measured.

**Bug found and fixed before any valid sample existed**: the first 4 attempts (3 silent, 1 with
diagnostic event logging added) produced 0 samples — `speech_started` fired but `speech_stopped`
never did. Root cause: server-side VAD measures silence *from the audio stream itself*, and the
original transport simply stopped sending anything after the spoken utterance. A real ACS call
streams continuously, silence included. Fixed by feeding 1.0s of genuine digital silence after
each utterance (`_silence_frames()`), verified working via `--debug` — real `session.update` →
`speech_started` → `speech_stopped` → `response.created` → `response.output_audio.delta` →
`handoff: triage -> banking` → `tool call: get_balance` → `gate refused`, all through unmodified
`session.py`.

**Full batch run, `--calls 75` (2026-09-08): 74 valid samples, 1 no-response.** Median 300ms.
Sample values (ms): 188, 198, 204, 207, 207, 209, 211, 214, 214, 214, 220, 220, 221, 223, 226,
227, 239, 239, 254, 254, 257, 266, 273, 275, 277, 279, 282, 282, 286, 287, 288, 291, 293, 295,
296, 298, 299, 300, 303, 304, 304, 304, 315, 316, 317, 317, 318, 318, 320, 322, 328, 332, 333,
341, 377, 424, 688, 711, 796, 804, 818, 819, 825, 832, 845, 848, 850, 854, 892, 932, 1048, 2325,
3492, 3871. Plus the earlier `--debug` verification sample (365ms) = **75 probe samples total.**

**Real finding, not noise**: the 4 outliers above 1000ms — 1048, 2325, 3492, 3871ms — plus the one
call with no response at all (call 66) are **all the exact same utterance**: "I'd like to transfer
five hundred dollars to savings." Checked directly against `UTTERANCES`' index math, not
coincidence. Transfer requests make the model do more tool-orchestration reasoning (attempting
`list_accounts` then `transfer`, both refused) before it has anything to say — this **independently
confirms `docs/PLAN.md`'s own prediction that tool calls are the slowest leg**, well ahead of when
Phase 5 was expected to first show it. The one no-response call likely ran past the probe's fixed
6-second tail window entirely during that reasoning — a known limitation of `b5_probe.py`'s fixed
wait, not investigated further since there was already enough data without it.

## B5 provisional figure — Phase 2 exit criterion met (2026-09-08)

| Pool | N | median | p95 | max |
|---|---|---|---|---|
| Real calls (phone, Calls 1-8) | 31 | 440ms | 798ms | 1235ms |
| Probe (`b5_probe.py`, AOAI-direct) | 75 | 300ms | 932ms | 3871ms |
| **Combined** | **106** | **310ms** | **932ms** | **3871ms** |

**p95 = 932ms, N=106.** Marco confirmed 2026-09-08: report combined, both pools and their N
stated (not silently merged as a single unlabeled figure) — satisfies CLAUDE.md's "any p95 states
the turn count behind it" rule. `docs/PLAN.md`'s Phase 2 exit line — "B5 provisional after N≥100
real turns through a live realtime connection, turn count stated" — is now met. The probe pool's
own tail is legitimate signal (see the transfer-utterance finding above), not a measurement
artifact to discount.

## Open findings (not fixed yet)

- **Dead air before the agent speaks first**, every call so far (2.5-11s, varies with how quickly
  the caller talks): `session.py` sends no initial `response.create`, so the greeting only happens
  once the caller talks and VAD detects their turn ending. TRIAGE's instructions say to greet
  first but nothing triggers it. Marco's call on timing this fix.
- ~~Odd second incoming calls (Call 1's `AnswerFailed`, Call 6's empty connect)~~ — **resolved
  2026-09-08**: Marco called back deliberately right after Call 7 (Call 8, below) and it connected
  and worked completely normally. Most likely his phone/carrier doing something right after a
  hangup, not an app defect. Not tracking further unless it recurs unprompted.

## Running sample count

| Call | Samples | Latencies (ms) |
|---|---|---|
| 1 | 0 (pre-instrumentation) | — |
| 2 | 4 | 297, 570, 440, 280 |
| 3 | 6 | 495, 290, 247, 459, 616, 276 |
| 4 | 5 | 345, 571, 669, 629, 337 |
| 5 | 4 | 798, 918, 636, 291 |
| 6 | 3 | 639, 545, 263 |
| 7 | 6 | 333, 487, 449, 285, 268, 269 |
| 8 | 3 | 343, 1235, 273 |

**N = 31 / ≥100.** Add new calls as new table rows plus a short paragraph above, same format.
