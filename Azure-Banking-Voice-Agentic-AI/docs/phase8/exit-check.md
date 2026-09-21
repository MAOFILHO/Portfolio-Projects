# Phase 8 — exit check, against `docs/phase8/exit-criteria.md`

**Status, 2026-09-21: criteria 1-5 and 8-10 met, 6-7 closed with a stated limit (D15). The gate's
`/code-review` has been run four times (fixed points `2dc4961`, `b0110ce`, `854842d`, then `fc4cc52`) and all four sets
of findings are addressed below; the fourth round's own small fixes have not been reviewed. Not yet signed off.**
Nothing in this table is a projection: where a criterion rests on a live call, it says how many. Three more real
calls (`p8c`, `p8d`, `p8e`) confirmed the async credential live: Table, Blob, Language and the text model on `p8c`, and
the realtime connection on `p8d`; `p8e` carries the scrub fix and ran one clean call. The shield, the new phone patterns
(the `p8e` blob held no phone-shaped text, so they were deployed but not triggered) and the pending-first row have no
live proof and rest on tests.

| | |
|---|---|
| `make lint` | clean: ruff, mypy, the B3/D5/D2 checks, `bicep build` on all 8 modules |
| `make test` | 755 voice-agent (3 skipped by design) + 90 mock-core-banking, all pass; B1 corpus 593 cases, 0 breaches |
| `/code-review` | 3 rounds during the build (`build-notes.md`), then **the gate review, 2026-09-21, fixed point `2dc4961`**, then **a second review of its fixes, fixed point `b0110ce`**, then **a third, fixed point `854842d`**, then **a fourth, fixed point `fc4cc52`** (Standards and Spec axes, run separately each time). Disposition of every finding: below. |
| Live | six real calls: two on image `p8a`, one on `p8b`, one on `p8c`, one on `p8d`, one on **`p8e`** (revision `ca-azbank-echo-p0--0000005`, 2026-09-21 21:38 UTC, image digest `sha256:3e71d119…`, the third review's scrub fix: booted clean with the B3 guard passing, one row `transfer`, 10 turns; ledger 3.796 to 4.799 min = 1.003 min against the call's 60,202 ms; blob 7 agent turns, no digit run of four, no phone-shaped or spoken-digit run and no `[REDACTED]`, digits only in `$1,900`, `$1,000` and `$200`). Earlier, **`p8d`** (revision `ca-azbank-echo-p0--0000004`, 2026-09-21 12:56 UTC, the second review's code: booted clean with the B3 guard passing, connected, authenticated, one row `balance_enquiry`, 7 turns; ledger 3.169 to 3.796 min = 0.627 min against the call's 37,607 ms; blob 5 agent turns, digits only in `$1,900` and `$1,000`). Earlier, **`p8c`** (revision `ca-azbank-echo-p0--0000003`, 2026-09-21 10:34 UTC, the gate-review code). Ledger 2.071 to 3.169 min = 1.098 min = 65.9 s, matching the call's 65,856 ms; one row; blob clean (6 turns, no digit run of four, no phone-shaped or spoken-digit run; digits only in `$` amounts). |
| Model pin review (`CLAUDE.md`, at every gate) | read live from the Models API and ARM, 2026-09-20: `gpt-realtime-mini` `2025-10-06` retires **2027-04-06** (6.5 months), `NoAutoUpgrade`; `gpt-5.4-mini` `2026-03-17` retires **2027-09-21** (12 months), `NoAutoUpgrade`. Neither is under 2 months; no stop-and-ask. Successor `gpt-realtime-1.5` is GA, retires 2027-08-24. |

## Criterion by criterion

| # | criterion | evidence |
|---|---|---|
| 1 | Redacted transcript reaches Blob, no raw write first | ✅ Unit tests prove the blob writer only receives redacted text and that a failed redaction writes nothing (ADR-007). **Live on six calls**: each blob read back, no PIN, phone number or digit run. **Limits:** no blob for a closed-line call or one with no agent turns (nothing to store, so `transcript_status=none`); one agent turn over 1,000 characters fails closed and keeps its row. |
| 2 | A summary/intent/outcome row for every completed call | ✅ Live on six calls, each `caller_hangup`, transcript `stored`, summary `done`. A call whose realtime connection cannot be opened also gets a row (tested on the main and closed paths, not live). The row is now written **first** with `pending` fields and overwritten when the steps finish, so a kill mid-pipeline leaves the pending row (tested; the pending state itself was not observed live). |
| 3 | Outcome is exactly the five-value enum | ✅ `postcall/outcome.py`; a drift test on `session.py`; and (gate review) seven endings are driven through `run_call` / `run_closed_call` and their outcome read off the capture, mutation-checked: `caller_hangup`, `escalated`, `closed_path`, and four that land on `error` (turn cap, time cap, the model ending an unauthenticated call, a relay that fails). **`authenticated_served` and `attempts_exhausted` are covered by the outcome unit tests only, not driven through `run_call`.** |
| 4 | The pipeline cannot affect B4 or B5 | ✅ **with a limit.** Background task, never awaited; tests prove the same frames, events and turn cap, and that a capture that raises cannot skip the ledger charge. **The tests measure no latency**; B5's frozen figure (p95 1025 ms, N=13) is not re-measured. Gate review: the Table and Blob clients had a sync credential whose token refresh ran on the event loop; one async credential now serves them and the Language and text-model tokens (**live on `p8c`**: ledger read and write, Blob write, both tokens). Second review: the realtime connection still built a sync credential per call; it now takes a provider from the shared one (**live on `p8d`**: the call connected and ran; `client.py` has no other route to a token. This is one call, not a latency measurement). |
| 5 | B3 covers the second deployment | ✅ `CLAUDE.md` B3 row; the static check scans both deployment classes and (gate review) pins each name to the files that may carry it; `boot.assert_text_model_safety` is the non-fatal runtime guard (ADR-006). Bicep now declares the text deployment, **never deployed**. |
| 6 | `evals/`: 20 scenarios, ≥95% over 20 runs | ⚠️ **Not built, no result. Closed with a stated limit (D15)**: `eval-redteam-limits.md`. |
| 7 | `redteam/` at its L4 cadence | ⚠️ **Live run not done. Closed with a stated limit (D15)**, same document. The deterministic corpus (593 cases, 0 breaches) runs in `make test`. |
| 8 | ADR-006 and ADR-007 | ✅ Both written, each with a 2026-09-21 build note. |
| 9 | `RESULTS.md`, an architecture diagram, a current README badge | ✅ `RESULTS.md` (78 lines, ceiling 120); `docs/architecture.md` (Mermaid, parsed clean by the mermaid parser, not viewed rendered on GitHub); README badge "Phase 8 of 8 (exit gate pending)". |
| 10 | `COSTS.md` prices Language and the second model; R-08 recomputed | ✅ `COSTS.md`, "Phase 8 — every input priced": list-price arithmetic, **not billed figures**; the Language billing unit and the Global meter for `canadacentral` stay unverified. The second row write per call adds about 67 Table transactions a month, under the cent the Table line already rounds to. |

## The gate review's findings, and what became of each

Fixed and tested. The three on B2, B4 and billable IaC were shown to Marco and approved before they were committed (`f30419b`, `bb3faf7`):

| finding | disposition |
|---|---|
| `scrub_numbers` left the area code, or six digits of a dotted number | **Fixed.** A phone-shaped pattern runs first; `$12.50` and `4.25 percent` survive. **B2, approved.** |
| A cancelled ledger write lost that call's minutes (B4) | **Fixed.** The write is its own shielded task; shutdown waits for it. **B4 / `session.py`, approved.** |
| Row written last; a kill loses it | **Fixed.** Row first with `pending`, overwritten at the end. |
| Sync credential on the event loop (B5 exposure, and the ledger client since Phase 5) | **Fixed** for Table, Blob, Language and the text model: one async credential, live on `p8c`. The realtime connection was missed; see the second review below. |
| Static check accepted either pin anywhere | **Fixed.** File-scoped; two new tests fail it on cross-wiring. |
| Criterion 3's tests were tautological | **Fixed.** Seven end-to-end endings, mutation-checked, 0 flakes in 40 runs. |
| No Bicep for Language or the text deployment | **Written, never deployed, not wired into `azbank-deploy`.** A read-only `what-if` found one deploy blocker: a duplicate Language role assignment. **Billable IaC, approved.** |
| Malformed endpoint refuses boot | **Kept, reason recorded** in `boot.py`: single-revision mode means a revision that won't boot never takes traffic. A test pins it. |
| Closed-line calls store no blob | **Documented** (criterion 1). |
| Language keeps results 24 hours; ADR-007 assumed a PIN read-back D14 removed | **Documented** in ADR-007. |
| Doc drift (image, glossary, "one call", outcome wording, dates, module count) | **Fixed.** Live times are UTC. |
| Scope beyond the spec (`scrub_numbers`, correlation-id replacement, the `INTENTS` list, the `client.py` change, the README rewrite) | **Accepted and recorded** in `build-notes.md`. |
| Smells: `capture=None` guards, `StrEnum`, one shared endpoint check, per-call `PostcallServices`, the model literal in Bicep | **Not changed.** Refactors on the live path with no behaviour gained; say so if you want any of them. |

## The second review's findings (fixed point `b0110ce`), and what became of each

Two verified defects in my own fixes, then drift. Committed (`2b4b2e2`) after Marco's look at the B2 diffs.

| finding | disposition |
|---|---|
| **Scrub regression:** the phone pattern took ten digits out of a longer run and left the tail (`4165550199123` gave `[REDACTED]123`); a slash, comma, dash, underscore, middle dot, non-breaking space or newline between groups left two groups | **Fixed (B2, approved and committed).** A chain of 10+ digits with non-word characters between digits is masked whole; four-digit runs allow more separators. Judged by a fuzz that turned out too narrow: see the third review (the gap was capped at three characters). |
| **B2 leak scan failed ~3 runs in 100.** A generated correlation id (`uuid4().hex`, more than half digits) can spell the test PIN `1234` or `9999`; found by repeating the suite, not by the review | **Fixed (B2-adjacent, approved and committed).** `storable_or_generated_id` now translates digits to letters, as `session.py` already does for its frame ids. |
| **Realtime client** built a sync `DefaultAzureCredential` per call and called it on the loop | **Fixed, live on `p8d` and `p8e`.** `connect_realtime(token_provider)` is handed the shared async provider; a real call on each connected and ran on it. |
| Criterion 3 "each ending" overstated | **Reworded** (above). |
| `RoleAssignmentExists` written as observed | **Reworded** as inferred from the `what-if` `Create`. |
| Only `LANGUAGE_ENDPOINT` had a boot-refusal test | **Added** for `TRANSCRIPTS_ACCOUNT_URL`. |
| Deleting `_ledger_writes.add` passed every test | **Test added**, mutation-checked. |
| Flaky `assertNotIn("bad", generated_id)` (a hex id can contain "bad", ~1 in 75) | **Fixed.** |
| Pending row after a failed final write undocumented | **Documented** in `store.py` and `pipeline.py`. |
| Doc drift: review range, "last commit", test-run date, README casing, dangling `item 10 (f)`, `allowed_pairs` docstring, `aoai.bicep` header | **Fixed.** |
| **B2 log scan fails about 1 run in 150** on an `httpcore` debug record whose memory address (`0x10ee77770`) has a digit run that matches a secret; pre-existing, third-party | **Not fixed.** The fix strips `0x...` addresses inside the B2 detector, so it waits for Marco. |
| Not changed, by choice: the smells (record built twice, `_write_row(what)` naming), the B3 per-file check (a per-variable check is not worth it), the credential not closed if startup fails between its creation and the `try` (the process exits either way), the unused `textDeploymentName` output, a hung store adding a fourth 60 s step, the test that writes into the real `summarizer.py` | Say so if you want any of them. |

## The third review's findings (fixed point `854842d`), and what became of each

Neither axis found a hard violation of a documented standard. One defect in my own fix, and doc drift.

| finding | disposition |
|---|---|
| **Scrub regression, again (B2):** the gap between digits was capped at three characters, so `416 .. 555 .. 0199`, `416 ... 555 ... 0199` and `416 - - 555 - - 0199` left the area code and exchange (the first pattern masked them). "0 leaks in 20,000 random shapes" held only for shapes the generator built | **Fixed, committed (`476bead`, B2, approved by Marco) and deployed on `p8e`, not triggered live.** The gap is now up to eight characters, four-digit runs allow two separators, and the fuzz is a committed test (3,000 shapes, gaps of 0-8 characters). `p8d` carried the three-character version; `p8e` (digest `sha256:3e71d119…`) carries this one, checked inside the image on the three leaking shapes and the `$1,900` amount. The 2026-09-21 21:38 call's blob held no phone-shaped text, so the pattern has run only in tests and in the image. |
| Known limit, not new: four-digit runs still leak in `4,1,6,5`, `1, 2, 3, 4`, `4;1;6;5`, zero-width joiners and `1 two 3 four`; commas are excluded on purpose so `$1,900` survives | **Listed, not changed.** |
| Over-masking: `$12,345,678.90` and `$5,000,000,000` now masked (10+ digits) | **Accepted**, within "deliberately blunt". |
| `scripts/b5_probe.py:243` calls `connect_realtime()` with no argument (`TypeError`); no test checks that `app.py` passes `_realtime_token_provider` | **Fixed.** The probe builds its provider from `azure.identity.aio.DefaultAzureCredential`, hands it to `connect_realtime`, no longer demands `AOAI_KEY`, and has a second startup guard, `assert_probe_matches_connect_realtime`, beside the `run_call` one (tests for both, one of them a call rather than a signature). Two tests drive `media_stream` on the normal and the closed path and read what `connect_realtime` was given; mutating either call site to `connect_realtime(None)` fails the matching test. **The probe itself has not been run** (it dials a billable realtime connection). |
| Doc drift: `RESULTS.md` lines 13, 23-24, 26 and 45 (stale "not yet live", a spliced `p8c`/`p8d` sentence, "four calls"), "Azure refuses" stated as fact in `README.md` and `PROJECT_STATE.md`; HEAD hash; "digit-free ids live on `p8d`"; `session.py` "one place" | **Fixed.** The counts moved to 845; "Azure refuses" is now "expected to refuse, inferred from `what-if`" everywhere it was stated; the `session.py` docstring says the table lives in two files. |
| Smells: `_DIGIT_FREE` duplicated, `_LINK` and `_DIGIT_FREE` names, four ordered regex passes | **Not changed.** |

## The fourth review's findings (fixed point `fc4cc52`), and what became of each

Covered `476bead`, `897f833` and the probe, call-site tests and doc fixes. Neither axis found a hard violation.
`scrub.py` (B2) and a docstring in `session.py` were flagged for a human look; the scrub change was approved by
Marco in-session, and `session.py` is docstring-only.

| finding | disposition |
|---|---|
| A doc line said the third round's fixes were "committed" before the probe, tests and doc fixes were | **Fixed.** Reworded to say what has and has not been reviewed. |
| **The scrub cap is still arbitrary:** `416 ........ 555 ........ 0199` (gaps of ten) leaves `416` and `555`, and the fuzz covers gaps of 0-8 only, so "no shape leaks" was wider than the test | **Listed, not widened.** The limit is now written in the `scrub.py` docstring (also `416 abc 555 abc 0199` and `4,1,6,5`). Widening it is a B2 change and Marco's call. |
| A comment and a test docstring said the probe's `TypeError` was missed by "ruff and mypy because `scripts/` is in neither"; ruff does lint `scripts/` (`Makefile`), it just cannot see an arity mismatch | **Fixed.** |
| `_assert_signature_matches` took a `where_to_fix` that was always `"_run_one()"` | **Fixed** (dropped). `name` stays: the tests patch in stand-ins, whose own name is not the one an operator should see. |
| The disposition above named `RESULTS.md` among the "Azure refuses" edits; it never made that claim | **Fixed.** |
| The probe's role claims (`Owner`, `Contributor` carry no data actions; `Foundry User` carries `Microsoft.CognitiveServices/*`) could not be checked by the reviewer | Read live with `az role definition list`, 2026-09-21; unchanged. |
| Not changed, by choice: `_run_one`'s six positional arguments, two weak tests (a source grep for `"AOAI_KEY"`, an `assertNotEqual(..., MASK)`), `_DIGIT_FREE` in two files, the probe's credential created before its `try` (a failure there leaves the core-banking client open), the probe exiting 0 when every call fails (pre-existing), a long line in `PROJECT_STATE.md` | Say so if you want any of them. |

**Seen live, not a criterion:** the agent talks over the caller (barge-in). Other open items:
`PROJECT_STATE.md`.

## Owed before this phase is closed

1. *(done 2026-09-21: the first round's B2, B4 and billable-IaC diffs were approved and committed; `/code-review` of them ran over `b0110ce..854842d`.)*
2. *(done 2026-09-21: the scrub and the other B2 and billable-IaC diffs were approved and committed.)* The third (`854842d`) and fourth (`fc4cc52`) `/code-review`s ran; whether the fourth round's small fixes need a fifth is Marco's call.
3. *(done 2026-09-21: `p8d`, then `p8e`, built, deployed and called; see the Live row.)*
4. **Closure sign-off**, then `/handoff` (copied to `docs/handoffs/` and committed), then `/clear`.

**Closure sign-off**: not yet given.
