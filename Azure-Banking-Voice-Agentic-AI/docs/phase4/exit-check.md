# Phase 4 — exit criteria, checked one by one

Every criterion in `docs/phase4/exit-criteria.md` against what was actually built, with its evidence
named. **Anything unmet is stated as unmet rather than reworded.**

Built 2026-09-10, tickets **#34–#42** under spec **#33**, on branch `azure-banking-work`.

## The headline numbers

| | |
|---|---|
| voice-agent tests | 263 pass, 3 skipped by design |
| mock-core-banking tests | 47 pass |
| B1 red-team | **11 distinct attack ideas → 193 concrete cases**, 176 reaching an attempt |
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

**7. The PIN never reaches the model.** ✅ Met, with one shape unverified.
No tool call, no argument, no transcript carries a digit. The outcome is injected as a conversation
item plus a response request, stating the outcome only.
**The injected item's wire shape is not verified against the live deployment** — see
`docs/phase4/findings.md` §2. Phase 4 deploys nothing, so nothing in this phase could verify it.

**8. No plaintext PIN is persisted.** ✅ Met.
`db.py` seeds a SHA-256 digest beside `SEED_ACCOUNTS`. The database is dumped and scanned in
`mock-core-banking/tests/test_db.py`, and the real file a spawned service wrote is scanned in
`tests/test_core_banking_live.py`.

**9. B1 = 0 breaches, blocking, in three tiers.** ✅ Met.
The exhaustive cross-product, the `redteam/` YAML corpus expanded by a loader, and the spy on the
core-banking client keyed on method name. Verified against a real injected breach: a single
permissive row fails the suite and the failure names the case.
**The idea count is 11 against a target of 20–30.** Reported, not padded. `redteam/README.md`
explains why the honest number is that low.

**10. B2 = 0 occurrences, blocking.** ✅ Met, by two rules rather than one.
A run-wide capture checks both rendered messages and raw arguments; the database file is scanned; one
test leaks deliberately and asserts the detector fires. The run-wide scan looks for whole values and
therefore cannot see a digit-by-digit leak, so that one is caught precisely at the relay instead. Both
rules were verified against real injected leaks. Implemented with `unittest`, not pytest — flagged in
`docs/phase4/findings.md` §3.

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
- **The injected conversation item's shape is unverified.** Wants `/research` before Phase 5's real
  call. `docs/phase4/findings.md` §2 names the exact question.
- **One test failure seen once and not reproduced in 98 runs.** `docs/phase4/findings.md`.
