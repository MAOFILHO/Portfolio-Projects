# Phase 4 — Auth gate permissions: exit criteria

**Written at phase kickoff, 2026-09-10**, from a design session that worked the decision tree to
exhaustion before any code. `CLAUDE.md`'s first stop condition makes the phase's start conditional on
these existing and on Marco's explicit approval, so they are written before the work, not
reconstructed after it.

Spec: GitHub issue **#33**. Tickets: **#34-42**, sub-issues of #33, filed 2026-09-10 with GitHub
blocking edges.

**Approved by Marco 2026-09-10**, including the B1 sharpening below.

**Entry conditions, both satisfied:** Phase 3's exit criteria are written and met
(`docs/phase3/exit-criteria.md`), and Marco signed off 2026-09-09 — "Phase 3: APPROVED",
`docs/handoffs/2026-09-09-phase3-signoff-phase4-entry.md`.

**No `APPROVED: Phase 4` is required for this scope** — this phase creates no billable Azure
resource and deploys nothing. Provisioning mock-core-banking remains a separate, unapproved step
with the R-08 recompute as its precondition, and it is not part of this phase.

**Two never-auto-accept rules bind every diff here.** This is the phase that adds permissions to
`dispatch/gate.py` and the phase that first consumes a DTMF tone. Both get a human look, however
mechanical the change appears.

---

## Scope change from `docs/PLAN.md`, approved 2026-09-10

**Authentication is the PIN alone. The spoken knowledge check is dropped.** `docs/PLAN.md` decision 7
and its Phase 4 line both specify card last four plus date of birth, spoken, followed by the PIN by
keypad. Marco cut the spoken factor on 2026-09-10 on prototype-simplicity grounds, and `docs/PLAN.md`
is amended in the same commit as this file rather than left to drift.

What the cut removes: the `authenticate_caller` tool, its argument schema, ISO-date normalisation of
a spoken date of birth, a second verification endpoint, and the malformed-versus-rejected distinction
that only existed because a tool call could arrive misshapen.

What survives intact is the property the phase exists to demonstrate: **a secret that never reaches
the model, and a gate that opens only on a fact the system of record verified.** A second factor
nobody dials would not have strengthened that.

One consequence is worth stating in its own right, because it makes the gate's story stronger rather
than weaker: **with no authentication tool, no tool at all is reachable while a call is anonymous.**

---

## Required Marco's explicit sign-off before the phase began — given 2026-09-10

**B1's breach definition is sharpened, and B1 is a named constraint.** `CLAUDE.md` says named
constraints do not move without explicit sign-off, so this is called out rather than folded into the
criteria below. The cut above shrinks the problem but does not remove it: the PIN is verified by the
system of record, so one operation still reaches the core-banking client while the call is anonymous.

> **B1 (sharpened).** No *banking* operation — balance, transfer, or list — reaches the core-banking
> client while the call's auth state is not authenticated. PIN verification is the only operation
> reachable while anonymous, and a test asserts that set is exactly that one.

Nothing about the target changes: still 0 breaches across ≥120 adversarial cases, still L1, still
blocking. Only the phrase "authenticated-only tool invocations" is replaced by the named banking
operations, so the detector cannot mistake a PIN check for a breach.

---

## The criteria

1. **The gate gains four explicit rows, one of which grants anything.** `is_allowed()` is untouched.
   All four `(agent, auth_state)` pairs are written out, including the three that grant nothing, so
   the table states its own completeness rather than relying on absent keys:

   | agent | auth state | tools |
   |---|---|---|
   | triage | anonymous | *(none)* |
   | triage | authenticated | *(none)* |
   | banking | anonymous | *(none)* |
   | banking | authenticated | `get_balance`, `transfer`, `list_accounts` |

2. **No tool is reachable while a call is anonymous.** A test drives the full cross-product off the
   declared tool list and asserts that every tool is refused for all three non-granting pairs.

3. **Handoff stays ungated.** An anonymous call may still be routed to the banking agent and be
   refused everything there. Gating the handoff would put a routing decision inside the control and
   give the gate a second job.

4. **The auth state stays binary.** Anonymous or authenticated, with nothing in between. How many
   digits have arrived is private to the authenticator and invisible to the gate, so the gate's key
   space is unchanged at two agents by two states.

5. **Authentication is one factor, decided by the system of record.** Four digits arrive as DTMF
   tones and are verified by `mock-core-banking` at a single endpoint, which answers **200 with an
   outcome field** — the same shape a decline already uses. A rejected PIN is a working system saying
   no, not a broken request, and mapping it to a 4xx would put it in the same bucket as
   unknown-account.

6. **The keypad protocol, in full.** Four digits, submitted automatically on the fourth. Star clears
   the buffer. Pound is ignored, since a fixed length needs no terminator. **No inter-digit timeout**
   — deliberately cut on 2026-09-10 as the only piece of this phase that would put a timer on the
   audio event loop. Three rejected submissions end the call after a composed sentence. The buffer is
   zeroed on submit, on clear, and on call end whatever the outcome.

7. **The PIN never reaches the model.** The triage instruction asks the caller to key it; no tool
   call, no argument, no transcript carries a digit. The outcome is injected as a conversation item
   followed by a response request — the same mechanism the handoff already uses — stating the outcome
   only, never a digit and never an attempt count.

8. **No plaintext PIN is persisted.** The demo PIN is **1234**, seeded into `db.py` as a SHA-256
   digest beside `SEED_ACCOUNTS`. One stdlib line, no salt ceremony, no dependency added to a module
   that deliberately hand-writes its SQL. The digest is what the database holds, so the artifact scan
   in criterion 10 can cover the database file without a carve-out.

9. **B1 = 0 breaches, blocking in CI**, against the sharpened definition above, in three tiers:
   - the exhaustive gate cross-product, generated from the declared tool list, not hand-maintained;
   - `redteam/` YAML, one file per attack idea carrying a matrix, with concrete cases as the
     cross-product of the idea with tool, agent, and point in the call;
   - a spy on the core-banking client keying on method name, so a breach is detected where the call
     actually lands rather than by reading the gate's own return value.

   **Both numbers are reported everywhere the suite is described** — distinct attack ideas as well as
   concrete cases. The constraint fixes the case count at ≥120; the idea count is whatever it honestly
   is. If fewer genuinely distinct ideas exist than the 20–30 aimed for, the real number is reported
   and the shortfall explained, never padded with near-duplicates to make a total look larger. A case
   count with no idea count behind it is the same empty claim as a percentile with no N, which this
   project already forbids for B5.

10. **B2 = 0 occurrences, blocking in CI.** An autouse fixture captures every record from every logger
    for the whole run and checks **both the rendered message and the raw arguments** — a PIN passed as
    a lazy formatting argument never appears in a rendered message. The SQLite file is scanned after a
    run. One test deliberately emits the PIN and asserts the scanner catches it, so a scanner that
    silently stopped working cannot pass forever. It all lives inside pytest, so it is blocking by
    construction rather than a CI step someone can drop.

11. **Every attempt is logged, and carries no digit.** Info on a successful authentication, warning on
    each rejected one, carrying the attempt number only. Same reasoning the gate already uses for
    refusals: a failure is either an attack or a bug, and both are worth seeing.

12. **The fake and the real client fail identically on PIN verification.** The fake holds a real
    credential store, and `tests/test_core_banking_live.py` is extended to drive the new method against
    a spawned service, so the parity table cannot rot into a transcribed constant. Trap 2 from Phase 3,
    which found divergences in three separate review rounds.

13. **The agent instructions are rewritten in the same diff that adds the transition.** Triage
    currently says "You have no banking tools of your own" and says nothing about authentication. It
    asks for the PIN right after the greeting. Trap 1 — drifted prose is a defect here, and this is
    prose the model acts on.

14. **A new `auth/` package holds a pure state machine**, constructed per call inside the relay where
    the auth state already lives, taking the injected core-banking client. Verification goes on the
    existing `HttpCoreBankingClient` rather than a client of its own, which reuses the circuit
    breaker — so if the service is unreachable, authentication fails closed for free rather than
    needing its own fail-closed path.

15. **`make test` green across both suites with zero cloud dependency**, `make lint` clean, the B3
    static allowlist check still passing.

16. **Nothing is provisioned and no real call is made.** `docs/PLAN.md`'s Phase 4 exit is stated purely
    as B1 and B2 blocking in CI, and it is met without deploying anything.

---

## Known-partial, recorded up front

**No real DTMF tone has ever been consumed by this system.** Phase 0 confirmed live, on calls 2 and 3,
that tones *arrive* during active bidirectional streaming; every line of code that acts on one is new
here and is exercised only against fakes. This is the direct consequence of criterion 16 and of the
decision that Phase 4 is CI-only.

It closes in Phase 5, whose exit already requires all four intents working over a real call — which by
then also needs mock-core-banking provisioned. Recorded here so the gap is a decision rather than
something a later session discovers.

## Deliberately parked, carried forward

- **The dead-air gap** before the agent's first words (2.5–11 s). Parked at Phase 3 kickoff and still
  parked. It has a sharper edge now that the greeting is what asks for the PIN, so a caller who says
  nothing is waiting on a prompt that has not been triggered. Still the greeting path's defect, not
  this phase's, and this phase's diff already touches the relay's DTMF handling — changing both at once
  means a review that cannot attribute a regression to either.
- **R-08's stale figure**, still a precondition of *provisioning* rather than of code.
- **No durable ACS-side call-diagnostics path.** Phase 6 is its real fix, but this is the phase whose
  failures most need auditing.

## Assumptions carried, not confirmed

Stated so they are visible rather than silent:

1. The third rejected attempt ends the call through the same path `CallLimitExceeded` uses, rather than
   a new mechanism (criterion 6).
2. The buffer is zeroed at all three points listed, not only on submit (criterion 6).

Either can be overruled without disturbing another criterion.
