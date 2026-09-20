# Phase 8 build notes

Past-tense record of the build, moved out of `PROJECT_STATE.md` (which holds current state only).
Criteria: `docs/phase8/exit-criteria.md`. Decisions: D14-D18, ADR-006, ADR-007.

## What was built (all on `main`)

Agent-side transcript capture (D14), D17 outcome mapping, the redact-before-write pipeline (ADR-007),
the Blob transcript store, the summary row, the Language PII redactor plus a deterministic number
scrub, the `gpt-5.4-mini` summariser, and the non-fatal B3 text-pin guard
(`boot.assert_text_model_safety`, ADR-006 Decision 4).

Applied with Marco's approval: the private `transcripts` container and its scoped Blob role;
`gpt-5.4-mini` at capacity 10 with `NoAutoUpgrade`. `APPROVED: Phase 8 Language resource` was given
2026-09-18.

## Live proof, 2026-09-20 (image `p8a`, revision `ca-azbank-echo-p0--0000001`)

One real call proved criteria 1-2: a Table row (`caller_hangup`, transcript `stored`, summary `done`,
intent `balance_enquiry`) and a redacted blob with no PIN and no phone number. One call, so "every
completed call" rests on the unit tests plus that one. Marco's user holds Storage Table Data Reader
and Blob Data Reader on `stazbankcallrecords` (granted by Marco, 2026-09-20; shared-key access is off).

## `/code-review` round 1 (against `47eb921`)

Its 12 Standards findings were fixed in `4b857a2`. Spec-axis findings left open, recorded in
`PROJECT_STATE.md`.

## `/code-review` round 2 (against `34db864`, i.e. `4b857a2` only)

Fixed:
- **B4 ordering.** Round 1's fix put `capture.finish` ahead of the ledger write, so anything that
  raised there would have skipped the day's charge (fails open). The ledger write is first again;
  the capture is finished in an inner `finally` so a cancelled write still finishes it. Both call
  paths, with a test each. `session.py` `finally` blocks, not the `end_call()` line.
- **Correlation id.** It is a Blob name and a Table RowKey, but only the Blob writer checked it, so an
  id with `#` or `?` lost the whole row. The check (`call_records.is_storable_id`) now runs where the
  id enters the pipeline; an unsafe id is replaced by a generated one and the row is written. The Blob
  store keeps its own refusal.
- `_step` returns `(result, problem)` with the record's own status strings; the `_OK`/`_FAILED`
  verdict constants (one collided in value with `SUMMARY_FAILED`) and the `_problem`/`_status` pair
  are gone. `PostcallServices.call_records` is typed `CallRecordStore`.
- `boot.py`'s orphaned doc comment; `CLAUDE.md`'s B3 row no longer contradicts itself about the text pin.
- Tests: the duration test no longer relies on a 50 ms margin; `test_app.py` no longer asserts on
  dataclass internals; the model-written `intent` scrub has a test.

Declined:
- `_optional_service_url` takes six string parameters. Round 1 asked for the two near-identical
  validators to be merged; this is the cost of that, and there are two callers.
- `scrub_numbers` leaves the area code of a formatted number (`(416) 555-0199` becomes
  `(416) [REDACTED]`). `scrub.py` is B2 territory; widening it is a design choice for Marco.

## `/code-review` round 3 (against `4b857a2`, working tree included)

Both axes found the same worst issue: an escalation row is keyed on the raw `x-ms-call-correlation-id`
header, unchecked. Fixed by checking the id once where it enters (`app.media_stream`), so the relay, the
escalation row, the capture, the logs and the span share one storable id; `dispatch/tools.py` is untouched.
`is_storable_id` gained a 128-character cap; `storable_or_generated_id` is shared by `app.py` and the
pipeline. A missing header still yields `None` (an existing test pins that).

Marco accepted the `session.py` ledger-first reorder and the `CLAUDE.md` B3 wording. The two comments the
review found overstating ("First, ahead of anything else", "on every path out") were corrected.

Not done, Marco's call: shielding the ledger write from cancellation (`asyncio.shield`, changes B4
behaviour). Low-priority judgement calls left as they are: `problem` naming in `pipeline.py`,
duplicated test helper classes, `is_storable_id` living in the Table store module.
