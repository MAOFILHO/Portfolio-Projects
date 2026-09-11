# Phase 5 — the `/code-review` findings, and what was done about them

Past-tense record, kept out of `PROJECT_STATE.md` per decision 18. Commits `581b8f4` (seven
findings) and `59a3d93` (the eighth, landed separately). The review itself ran 2026-09-11 against
the merge-base with `main`, `07faf3b` — 114 commits, 84 code files.

**The review's own verdict is not restated here.** It lives in the session that produced it; this
file records only what changed and what the fixes are pinned by.

## The eight

Each row names the test that fails if the fix is reverted. Every one of those tests was written
first and observed red.

> **Corrected 2026-09-11, by the `/code-review` of these very commits.** That claim was **false for
> row 5**. The B1 fix carried two tests and only one of them pinned it: the second compared the
> default row's grants to the smallest row's *by value*, and `(banking, anonymous)` and
> `(triage, anonymous)` both grant exactly `{escalate_to_human}` — so it passed with the defect
> restored. It tested the pair that was already innocent and never looked at the authenticated row,
> which is the only place the two agents differ. Replaced by
> `test_the_default_agent_is_least_privileged_in_every_auth_state`, which quantifies over every
> auth state and was confirmed red against a reverted fix before this note was written. Recorded
> here because a document claiming its fixes are pinned, while one of them is not, is the same
> defect class this whole file is about.

| # | Finding | Fixed by | Pinned by |
|---|---|---|---|
| 1 | **B3: the successor allowlist entry could never match a live deployment.** The guard compares `properties.model.name`, a *model* name. The entry spelled it `gpt-realtime-1-5`, a *deployment*-name form traced to `docs/phase0/findings.md:361`. The live Models API says `gpt-realtime-1.5`. Booting the pre-vetted successor would have been refused at startup by the allowlist that exists to permit it | the dot, in `boot.py` | `test_boot.py::test_the_guard_admits_the_successor_spelled_the_way_the_catalog_spells_it` |
| 2 | **B4: criterion 11's "times out" branch was asserted, not implemented.** No deadline on either side of the seam, so a Storage endpoint that accepted the connection and went silent stalled the media socket with a caller on it. The only evidence was a fake pre-raising the exception the code was meant to produce | `session.LEDGER_DEADLINE_SECONDS`, wrapping the budget read and the teardown write | `test_whole_call.py::test_a_store_that_never_answers_at_all_refuses` |
| 3 | **B4: the daily ledger lost concurrent updates.** Read-then-write across two awaits: two calls ending together in one process both read the same figure and the second write erased the first. The comment defended this with a `maxReplicas: 1` belonging to mock-core-banking — the voice agent has no Bicep module at all | an in-process `asyncio.Lock` (Marco's choice, 2026-09-11) | `test_call_records.py::test_two_calls_ending_together_both_count_against_the_day` |
| 4 | **B4: minutes and `end_call` were skipped when a pre-`try` send raised.** Both relays took the start time, sent their opening frames, and only then opened the block whose `finally` charges the day — against a docstring promising "every path out" | the `try` moved above the preamble sends, in both relays | `test_whole_call.py::test_a_send_that_fails_before_the_relay_starts_is_still_charged` and its two siblings |
| 5 | **B1: the dispatcher's default agent was the most privileged, not the least.** `BANKING_AGENT` under a docstring calling both defaults least-privileged. True of the *pair* only, because `ANONYMOUS` grants nothing to anybody. Latent: `session.py` is the sole production caller and passes both explicitly | `TRIAGE_AGENT` | `test_tools.py::TheDefaultsAreTheLeastPrivilegedOnes` |
| 6 | **`MAX_CLOSED_CALL_TURNS` enforced nothing.** Referenced nowhere; the one-turn bound held structurally because the relay returned at the first `response.done`. Editing the constant changed no behaviour | `speak_once` counts completed responses against it | `test_whole_call.py::test_the_turn_bound_is_the_named_constant_and_not_a_coincidence` |
| 7 | **The entry point read configuration and built a live ACS client at import time** — the one file in that role not following a rule three sibling modules state as a rule | configuration read at call time; the client built in `lifespan()` beside the other two, and closed there | `test_app.py::ImportingThisModuleHasNoSideEffects`, which imports from a scrubbed subprocess |
| 8 | **Three tidy-ups**: the unrecognised-outcome check and its eight-line comment duplicated across two call sites; `CallScope`'s two collaborator fields typed `object` in a package defining Protocols for exactly that; the probe's frame-size expression written twice | `client._recognised`; the Protocols; `_BYTES_PER_FRAME` | the existing suites |

## Two decisions inside the fixes

**The shared money helpers were made public, not duplicated.** The review read
`fake.py` importing `_cents`/`_dollars` from `.client` as a private cross-module reach, by analogy
with `DEFAULT_PIN`, which is respelled. The analogy does not hold: `DEFAULT_PIN` belongs to the
*other deployable* and shared-nothing (decision 9) forbids reaching for it, whereas these two are
siblings in one package and a **prior** review (2026-09-08) deliberately made the fake share them,
because a fake with its own rounding rule drifts from the real one silently. Respelling would have
reintroduced that defect. They are now `to_cents` / `to_dollars`.

**No SDK-level timeout on the table client.** See `PROJECT_STATE.md` open item 19. The short form:
azure-core clients accept unknown keyword arguments and ignore them, so a misremembered option name
would read as configured and do nothing — the same failure shape as a role assignment returning
200 OK and granting nothing. The deadline sits at the seam instead, where it is tested.

## Two defects found while fixing B3, not in the review

Both were hidden by skip-by-default, and both meant `T-B3-SUCCESSOR-BOOT` had not executed since
Phase 3 — the rehearsal read green by never running.

1. Phase 3 (issue #29) made `CORE_BANKING_URL` a boot requirement; the rehearsal's env fixture was
   never updated, so setting the run flag produced a `SystemExit` about a missing core-banking
   address rather than a rehearsal.
2. Phase 5 (issue #48) gave `run_call` a fourth collaborator; the rehearsal never grew one.

The module's own docstring had warned about exactly this: *"a rehearsal that silently declines to
run is worse than no rehearsal, because it reads green."* It had been true there for two phases.

The rehearsal also no longer feeds `boot.SUCCESSOR_REALTIME_MODEL` back as the reader's own answer.
It compared the string to itself, which is why it could not have caught finding 1. It now feeds a
literal catalog pair, so a drifted pin fails there.

## Closed, moved here from `PROJECT_STATE.md`

**The dead-air gap before the agent's first words** (open item 10, closed by #51). The relay sends
an initial `response.create`, so the greeting — which is what asks for the PIN — no longer waits for
the caller to speak. Parked at two prior phase boundaries; unparked in the phase whose exit depends
on a caller keying a PIN they were never asked for.

## What this does not do

- **It does not re-run `/code-review`.** The fixes are unreviewed. Marco invokes that skill.
- **It does not close Phase 5.** Four tickets remain (`#57`–`#60`), nothing is provisioned, no call
  has been made, and B5 is not frozen.
- **The eight findings were never filed as issues.** Both commits reference only the spec `#43`.
