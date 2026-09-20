# Phase 8 — exit check, against `docs/phase8/exit-criteria.md`

**Status, 2026-09-20: criteria 1-5 and 8-10 met, 6-7 closed with a stated limit (D15). Not yet signed off.**
A `/code-review` before the gate and Marco's closure sign-off are both still owed, and one live step
(below) should happen before the sign-off is given. Nothing in this table is a projection: where a
criterion rests on a live call, it says how many.

| | |
|---|---|
| `make lint` | clean: ruff, mypy, the B3/D5/D2 checks, `bicep build` on all 7 modules |
| `make test` | 698 voice-agent (3 skipped by design) + 90 mock-core-banking, all pass; B1 corpus 593 cases, 0 breaches |
| `/code-review` | 3 rounds during the build (`docs/phase8/build-notes.md`). **The gate's own review has not been run.** |
| Live | one real call on image `p8a`, 2026-09-20 |
| Model pin review (`CLAUDE.md`, at every gate) | read live from the Models API and ARM, 2026-09-20: `gpt-realtime-mini` `2025-10-06` retires **2027-04-06** (6.5 months), `NoAutoUpgrade`; `gpt-5.4-mini` `2026-03-17` retires **2027-09-21** (12 months), `NoAutoUpgrade`. Neither is under 2 months; no stop-and-ask. Successor `gpt-realtime-1.5` is GA, retires 2027-08-24. |

## Criterion by criterion

| # | criterion | evidence |
|---|---|---|
| 1 | Redacted transcript reaches Blob, no raw write first | ✅ Unit tests (`tests/test_postcall_pipeline.py`) prove the blob writer only ever receives redacted text and that a failed redaction writes nothing (ADR-007). **Live on one call:** the stored blob was read back, no PIN and no phone number. **Limit:** one agent turn over 1,000 characters fails closed, so that call keeps its row and loses its transcript. |
| 2 | A summary/intent/outcome row for every completed call | ✅ **with limits.** Live on one call: `caller_hangup`, transcript `stored`, summary `done`, intent `balance_enquiry`. A call whose realtime connection cannot be opened now also gets a row (`33adab6`, tested through the real pipeline on both the main and closed paths). **Limits:** the row is written last, after up to three 60-second steps, so a container killed mid-pipeline loses it; and "every completed call" is proven live once. |
| 3 | Outcome is exactly the five-value enum | ✅ `postcall/outcome.py`, a drift test that fails when `session.py` emits an `end_reason` nobody classified (D17). |
| 4 | The pipeline cannot affect B4 or B5 | ✅ **with a limit.** The pipeline is a background task, never awaited; tests prove that attaching a capture leaves the same frames, the same events consumed and the same turn cap, that none of the capture's methods is a coroutine, and (round 2) that a capture that raises cannot skip the day's ledger charge. **The tests measure no latency.** B5's frozen figure (p95 1025 ms, N=13) is not re-measured. |
| 5 | B3 covers the second deployment | ✅ `CLAUDE.md` B3 row; `scripts/check_b3_allowlist.py` scans both deployment classes; `boot.assert_text_model_safety` is a non-fatal runtime guard (ADR-006). **No Bicep enforces it**: the deployment was hand-provisioned. |
| 6 | `evals/`: 20 scenarios, ≥95% over 20 runs | ⚠️ **Not built, no result. Closed with a stated limit (D15).** `docs/phase8/eval-redteam-limits.md`: no caller audio (no TTS resource; a new one needs `APPROVED:`), no scenarios, no judge, no budget-enforcing runner. |
| 7 | `redteam/` at its L4 cadence | ⚠️ **Live run not done. Closed with a stated limit (D15).** The 18-idea corpus and its deterministic runner exist (593 cases, 0 breaches, in `make test`); the live L4 runner was never built. Same document. |
| 8 | ADR-006 and ADR-007 | ✅ `docs/adr/ADR-006-second-model-pin-for-post-call-text-work.md`, `docs/adr/ADR-007-redact-before-first-write.md`. |
| 9 | `RESULTS.md`, an architecture diagram, a current README badge | ✅ `RESULTS.md` (69 lines, ceiling 120); `docs/architecture.md` (Mermaid, parsed clean by the mermaid parser, not viewed rendered on GitHub); README badge now "Phase 8 of 8 (exit gate pending)". The README was also refreshed beyond the badge: it still described Phases 6-7 as unbuilt (tech-stack rows, build status, known gaps, test count, `make` targets). |
| 10 | `COSTS.md` prices Language and the second model; R-08 recomputed if the fixed total moves | ✅ `COSTS.md`, "Phase 8 — every input priced". `gpt-5.4-mini` $0.75 / $4.50 per 1M tokens (Global meter, Retail Prices API); Blob Hot LRS $0.02/GB-month, read live 2026-09-20. The fixed total does not move ($14.60), so no recompute was required; it was done anyway because the per-run cost rose, and runs/month falls from 67 to 57 (45 to 38), gate 5. **These are list-price arithmetic, not billed figures**; the Language billing unit and the Global meter's applicability to `canadacentral` remain unverified. |

## What this check found that the criteria do not show

- **The live image predates the review fixes.** The running revision (`ca-azbank-echo-p0--0000001`, image
  `p8a`) was created 2026-09-19 20:19 -0400, before `4b857a2`. Five later code commits are tested but not
  deployed: the round-1 Standards fixes, the correlation-id check, the ledger-first `finally` (B4), the
  failed-connect row, and their tests. Criteria 1-2's live evidence is for the older code.
- **Open Spec-axis items, none blocking, all in `PROJECT_STATE.md`:** the row is written last; criterion 4's
  test measures no latency; `$` amounts are unredacted in the transcript; `scrub_numbers` leaves the area code
  of a formatted number (`scrub.py` is B2); a cancelled ledger write loses that call's minutes (B4 undercount,
  older than this phase); a call with no correlation-id header keeps `None`.
- **Seen live, not a criterion:** the agent talks over the caller (turn detection and barge-in).

## Owed before this phase is closed

1. **Marco's decision on the live image.** Rebuild (`--platform linux/amd64`), push and update
   `ca-azbank-echo-p0`, then take one call and read the row back. It creates no billable resource, but it
   changes production code on the PIN path, so it needs a human look.
2. **`/code-review`** before the gate (Marco invokes it).
3. **Marco's call on** the two findings left open: `scrub_numbers`, and `asyncio.shield` on the ledger write.
4. **Closure sign-off**, then `/handoff` (copied to `docs/handoffs/` and committed), then `/clear`.

**Closure sign-off**: not yet given.
