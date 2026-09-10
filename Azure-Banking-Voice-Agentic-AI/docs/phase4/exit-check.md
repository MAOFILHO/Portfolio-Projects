# Phase 4 — exit criteria, checked one by one

Every criterion in `docs/phase4/exit-criteria.md` against what was actually built, with its evidence
named. **Anything unmet is stated as unmet rather than reworded.**

Built 2026-09-10, tickets **#34–#42** under spec **#33**, on branch `azure-banking-work`.

## The headline numbers

| | |
|---|---|
| voice-agent tests | 315 pass, 3 skipped by design |
| mock-core-banking tests | 47 pass |
| B1 red-team | **13 distinct attack ideas → 211 concrete cases**, 194 reaching an attempt |
| B1 breaches | **0** |
| B2 occurrences | **0** |
| `make lint` | clean |
| B3 static allowlist check | passing |
| Azure resources created | **none** |
| real calls made | **none** |

Both red-team numbers appear together everywhere the suite is described: here, in
`redteam/README.md`, in the suite's own printed output, and in the commit that added it. A case count
with no idea count behind it is the same empty claim as a percentile with no N.

---

## Criterion by criterion

**1. Four explicit rows, one grant, `is_allowed()` untouched.** ✅ Met.
`dispatch/gate.py`. All four pairs written out; `is_allowed()` is byte-identical to its pre-Phase-4
form, which the diff shows directly. `tests/test_gate.py` pins the exact literal.

**2. No tool is reachable while a call is anonymous.** ✅ Met.
`TheExhaustiveCrossProduct` in `tests/test_gate.py` drives the full cross-product off
`dispatch/tools.py`'s declared list, not a hand-maintained one, and asserts refusal for all three
non-granting pairs.

**3. Handoff stays ungated.** ✅ Met.
No handoff name appears anywhere in the table, asserted. `test_an_anonymous_caller_routed_to_banking_is_refused_everything_there`
routes an anonymous call to banking and shows it reaches the core-banking client not at all.

**4. The auth state stays binary.** ✅ Met.
The gate's key space is unchanged at two agents by two states. How many digits have arrived never
leaves the authenticator; no test asserts on it, and none can.

**5. One factor, decided by the system of record, 200 with an outcome field.** ✅ Met.
`POST /credential-checks` answers 200 for both accepted and rejected. A rejected credential is not a
4xx, for the same reason a declined transfer is not.

**6. The keypad protocol in full.** ✅ Met.
Four digits, auto-submit on the fourth, star clears, pound ignored, no inter-digit timeout, three
rejections end the call, buffer zeroed on submit, on clear and on call end. `tests/test_authenticator.py`.
The absence of a timer is asserted by parsing the module rather than grepping it.

**7. The PIN never reaches the model.** ✅ Met; the shape is confirmed, acceptance is not.
No tool call, no argument, no transcript carries a digit. The outcome is injected as a conversation
item plus a response request, stating the outcome only.

**Updated 2026-09-10 after `/research`** (`docs/phase4/research-carried-findings.md` §1). The item's
shape is **confirmed correct against the specification**: `role: "system"` with `type: "message"` is
one of exactly three message items accepted, and `input_text` is the only content type permitted on
a system message. What no primary source states is whether Azure's endpoint and this model version
accept it, and none documents this event per model version at all — the case B3 exists for. That is
a one-frame live probe at Phase 5's real-call exit, the same move Phase 1 used on the same wall.

**The injected outcome is now addressable, both frames of it.** The item and the response request
each carry a client `event_id`, and an `error` naming either is logged as that injection being
refused rather than as an unattributed error. That is the only documented way to tell the two apart.
The ids contain no decimal digit, so they cannot spell a credential into B2's run-wide scan.

**It makes a rejection legible; it does not make silence legible.** No source states a response
deadline and the relay imposes none, so an injection that is simply never answered is still
indistinguishable from an accepted one. Recorded as `PROJECT_STATE.md` open item 18 rather than
built, because a timer on the relay's PIN path is a Phase 5 design question and the authenticator
carries "no timer of any kind" as a deliberate decision.

**8. No plaintext PIN is persisted.** ✅ Met.
`db.py` seeds a SHA-256 digest beside `SEED_ACCOUNTS`. The database is dumped and scanned in
`mock-core-banking/tests/test_db.py`, and the real file a spawned service wrote is scanned in
`tests/test_core_banking_live.py`.

**9. B1 = 0 breaches, blocking, in three tiers.** ✅ Met.
The exhaustive cross-product, the `redteam/` YAML corpus expanded by a loader, and the spy on the
core-banking client keyed on method name. Verified against a real injected breach: a single
permissive row fails the suite and the failure names the case.
**The idea count is 13 against a target of 20–30.** Reported, not padded. `redteam/README.md`
explains why the honest number is that low.

**It was 11 until 2026-09-10.** Two ideas that were real, tested, and deliberately uncounted —
inheriting a previous caller's authentication, and completing an entry with characters that are
digits to Unicode and to no keypad — are now generated by the loader rather than sitting beside it,
so they count. The matrix grew a `prior_call` field and an `after_homoglyph_digits` point; no
near-duplicate was added, and the narrow assertions those two ideas used to carry stayed in
`tests/test_redteam.py` as assertions about them. **The gap to 20 is still reported rather than
closed**, for the reason it always was: the surface is three operations, two agents and two auth
states, and reaching 20 would take a wider system.

That change carried a correctness fix with it, and it points the dangerous way rather than the safe
one. The detector reads the spy from a mark taken **after** the prior call, so an earlier caller's
accepted verdict cannot be counted as this call's. Verified against a real injected breach, the way
this suite's claims are: with one permissive gate row, two cross-call cases reach a banking
operation and the detector catches both — read across the whole process instead, it catches **none**
of them. Unlike the `/code-review` defect it resembles, this one would have under-reported.

**The sharpened definition now reads the same in all four places** (corrected 2026-09-10). It was
approved in `exit-criteria.md` and recorded as a decision in `docs/PLAN.md`, but the named-constraint
tables in `CLAUDE.md` and `docs/PLAN.md` both still carried the pre-sharpening wording — the row a
fresh session reads first, and the one `tests/redteam_harness.py` explicitly notes would have scored
the PIN check itself as a breach. Both tables now carry the approved sentence verbatim. No constraint
moved: this propagated wording Marco had already signed off, and the target is untouched.

**10. B2 = 0 occurrences, blocking.** ✅ Met — **against three of the four surfaces B2 names.**
A run-wide capture checks both rendered messages and raw arguments; the database file is scanned; one
test leaks deliberately and asserts the detector fires. The run-wide scan looks for whole values and
therefore cannot see a digit-by-digit leak, so that one is caught precisely at the relay instead. Both
rules were verified against real injected leaks. Implemented with `unittest`, not pytest — flagged in
`docs/phase4/findings.md` §3.

**Which surfaces, stated rather than left to the reader** (corrected 2026-09-10 after `/code-review`
read this entry as claiming all four):

| B2 surface | Covered | Where |
|---|---|---|
| Log lines | Run-wide, every record the run emits | `tests/test_zz_b2_leak_scan.py` |
| Persisted records | Yes, the real file a spawned service wrote | `tests/test_core_banking_live.py` |
| Transcripts / injected items | Run-wide across every red-team call, **including the prior call of each cross-call case**, and the whole-call test | `redteam_harness.credentials_in_what_the_call_sent`, `tests/test_whole_call.py` |
| OTel span attributes | **Vacuously — this project emits no spans yet**, and the switches that would fill them are asserted off | `tests/test_b2_content_recording.py`; Phase 6 owns the rest |

The OTel row is the honest one: `grep -riE "opentelemetry|otel|tracer|span"` returns nothing outside
a comment, so there is no span for a PIN to reach. That is not coverage and is not counted as any;
the row becomes real work in Phase 6 and is recorded in `docs/phase4/findings.md` §4 as an
outstanding surface rather than a met one.

**Made precise 2026-09-10 after `/research`.** The surface is empty for three independent reasons,
not one: nothing emits spans; the realtime path is uninstrumented by both the OpenTelemetry OpenAI
instrumentation and the Azure Monitor distro, so adding either yields no `gen_ai.*` attribute at
all; and both content-recording switches default off. The third is now asserted rather than
described, and the assertion is negative by design — it costs no spans and no deployment, and it
goes red the day someone enables content recording. Two things Phase 6 inherits: B2's four named
surfaces are narrower than the real ones, since content can also travel on span events, on log
records, or out of the process entirely via the completion hook; and the Azure OpenAI
`RequestResponse` diagnostic category, whose content coverage no Microsoft page describes, must not
be enabled here until its destination table has been queried and read.

The transcript row was widened on 2026-09-10: it previously rested on one call, in
`tests/test_whole_call.py`, while every call that actually keys wrong credentials went unscanned on
that surface. Each red-team case now scans what it sent to the model and back to the caller.

**And widened again the same day, after that first widening overstated itself.** The row was
rewritten to claim every red-team call while the harness still discarded the prior call of each
cross-call case — twelve calls, and the **only** calls in the whole corpus that key the *accepted*
credential into a model context. Every other call keys a rejected one. So the sentence claimed
coverage of exactly the calls most worth watching, one file away from the paragraph forbidding that
move. The harness now keeps every call's surfaces and scans all of them. **Verified by planting a
real leak in the relay**: with the injection rewritten to append the submitted credential, all
twelve cross-call cases report it.

**The pre-fix figure first published here was wrong and is corrected**: measured rather than
assumed, six of the twelve caught the plant on their own call, not none. What was true of all
twelve is that the *accepted* credential's surface went unread. `docs/phase4/findings.md` carries
the full correction.

**11. Every attempt logged, carrying no digit.** ✅ Met.
Info on success, warning on each rejection with the attempt number only.

**12. The fake and the real client fail identically on verification.** ✅ Met.
`EXPECTED_VERIFICATIONS` is driven against the fake in `tests/test_core_banking_fake.py` and against
a really spawned service over a real socket in `tests/test_core_banking_live.py`. Neither claim rests
on the other.

**13. The agent instructions rewritten in the same diff as the transition.** ✅ Met.
Both landed in the #37 commit. `TriageAsksForTheKeyedPin` asserts the instructions ask for the keyed
PIN, forbid asking aloud, forbid reading a digit back, and forbid counting attempts out loud.

**14. A new `auth/` package holding a pure state machine.** ✅ Met.
Constructed per call inside the relay, taking the injected core-banking client. Verification goes on
the existing `HttpCoreBankingClient`, so it inherits the circuit breaker and fails closed for free.

**15. `make test` green across both suites, `make lint` clean, B3 check passing.** ✅ Met.
Zero cloud dependency. See the table above.

**16. Nothing provisioned, no real call made.** ✅ Met.

---

## B3 model pin review at the gate — checked live 2026-09-10, passes

`CLAUDE.md` requires the active pin to be checked against the **live Models API** at every phase
gate, not read out of this repo's own notes. Run against `canadacentral` and against the deployment
itself, both read-only and free:

| | pin | retires | runway from 2026-09-10 |
|---|---|---|---|
| active | `gpt-realtime-mini` 2025-10-06 | 2027-04-06 | **~6.9 months** |
| documented successor | `gpt-realtime-1.5` 2026-02-23 | 2027-08-24 | ~11.5 months |
| *not* pinned, for contrast | `gpt-realtime-mini` 2025-12-15 | 2026-12-15 | ~3.1 months |

**No stop-and-ask triggered.** The threshold is a retirement under two months out at a gate; the
active pin has nearly seven, and the successor is still GA and still listed.

**The live deployment matches the pin exactly**: `aoai-azure-banking-voice-cc` runs deployment
`gpt-realtime-mini` on model version `2025-10-06`, `GlobalStandard`, `NoAutoUpgrade`. Name *and*
version together, which is the pairing R-01's evidence forced B3 to key on.

**No drift** between the live API and `docs/PLAN.md` decision 14. All three retirement dates match
what was recorded in Phase 0.

---

## The carried assumptions, resolved

Both were stated up front as overrulable.

1. **"The third rejected attempt ends the call through the same path `CallLimitExceeded` uses."**
   Held, with the refinement issue #37 already anticipated: **same branch, distinct type.**
   `auth.AttemptsExhausted` travels the relay's "expected, not a relay failure" list alongside
   `CallLimitExceeded` rather than reusing it, so a security event and a cost event stay
   distinguishable in every log that reads them.
2. **"The buffer is zeroed at all three points, not only on submit."** Held, unchanged.

## Deviations, all flagged

Four, each in `docs/phase4/findings.md` rather than folded in silently: a seventh outcome the
tickets' list omits but their protocol requires, the unverified injected-item wire shape, the
`unittest`-for-pytest substitution the criteria themselves anticipated, and B2's coverage being two
rules rather than one.

## Open, carried out of this phase

- **No real DTMF tone has ever been consumed.** Closes at Phase 5's real-call exit.
- **The injected conversation item's acceptance is unverified.** `/research` ran 2026-09-10 and
  settled the shape against the specification; what no source documents is whether Azure's endpoint
  and this model version accept it. A one-frame live probe closes it.
- **The DTMF tone vocabulary is unverified and the documentation cannot settle it.** Raised by that
  same research. The classifier now accepts both candidate vocabularies so the question cannot break
  the call, but **Phase 5's real call must press `*` and `#`** — a digits-only call would leave it as
  open as it is now while looking closed. `docs/phase4/findings.md` carries the full account.
- **Nothing guarantees DTMF and audio frames arrive in order** on this socket. The four-digit
  accumulator assumes they do. Newly named, not yet observed.
- **One test failure seen once and not reproduced in 98 runs.** `docs/phase4/findings.md`. Still
  unexplained, but no longer able to hide the same way: `make test` keeps each suite's whole output
  in its own file whatever the caller pipes stdout through, and the live test now retries a start on
  a fresh port and reports the spawned service's own words instead of an exit code alone.
