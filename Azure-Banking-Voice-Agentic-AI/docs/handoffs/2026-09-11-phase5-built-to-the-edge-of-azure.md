# Handoff — 2026-09-11: Phase 5 built to the edge of Azure

**Restated verbatim, per `CLAUDE.md`:**

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).
- **The phone number is never released, by any script, at any phase, for any reason.**
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling.
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

---

## Where this stopped, and why

**13 of 18 tickets are done. Everything that can be built and proved without Azure is committed.
Nothing has been provisioned, nothing redeployed, no call made.** A caller dialling the number today
still reaches Phase 1's agent on the Phase 2 image — the gap between what is committed and what
answers the phone is now four phases wide.

The remaining five tickets are not "not got to". They are blocked, and two of the three blockers are
not Marco's time:

1. **`/research` owes two facts.** The role definition GUID in
   `infra/modules/call-records-store.bicep` is written from documentation rather than from a live
   `az role definition list`. Getting it wrong produces a role assignment that returns **200 OK and
   grants nothing** — the exact "creation is not delivery" trap `CLAUDE.md` names. Table Storage's
   rate is the second, and it is R-08's one unpriced input.
2. **A human review of both Bicep modules.** There is no `bicep` CLI here and still no `main.bicep`,
   so human review is the only check that exists.
3. **A phone.** Nothing else can press `*`.

Read the exit check before anything else: `docs/phase5/exit-check.md`. It is criterion by criterion
and it says which ones are not met rather than rounding them.

## What Phase 5 inherits to the next session

**Four phases of code will land on one image.** Phase 3's network client, Phase 4's whole auth path,
and everything here. **Phase 4's diff was never reviewed** — that was Phase 5's one unmet entry
condition, and it was *waived* on 2026-09-11 rather than satisfied. `git log e42c063..HEAD` now
covers both phases, and most of Phase 5's commits touch `dispatch/gate.py`, the DTMF/PIN path, or
both. The smoke call before the acceptance run exists for exactly this.

**The four wire-format questions are all still open**, and no real DTMF tone has ever been consumed
by this system. They close on the acceptance call or not at all.

## Traps this phase hit, which the exit check does not carry

**Two exit criteria predicted the wrong thing.** Both were corrected in place, inline next to the
criterion that made them, rather than being quietly satisfied against a different reading:

- Criterion 17 said the red-team harness's reachable-while-anonymous assertion would widen to
  "verification and escalation". It did not need to — the harness's detector watches the
  core-banking client, which escalation never touches, so its assertion is unchanged and is
  *stronger* than the one predicted. The gate-level half lives in `tests/test_gate.py` instead.
  **Reporting the criterion met against the harness would have been a claim outrunning its
  evidence**, which is this project's named recurring defect.
- Criterion 11 placed B4's budget read in the incoming-call webhook. It is on the media socket.
  The decisive reason: a decision made in the webhook has to reach the media socket somehow, and a
  marker in the WebSocket URL is client-controllable on a public, unauthenticated endpoint — which
  is fail-open, on the one constraint whose point is failing closed.

**B2's scanner caught two real things, both the same defect through new doors.** A relay log line
passed a raw duration as a lazy formatting argument, and `1.7117999959737062e-06` contains "9999", so
a run that leaked nothing went red. Fixed at the source: whole seconds, bounded by the wall-clock
caps to three digits. Then the ledger's accumulated minutes did the same thing — and there the source
fix is not available, because a measurement is not an identifier anybody gets to choose. **The
matcher was wrong, not the data**: numeric fields are now compared as numbers and text fields are
still substring-matched, which is strictly more precise rather than weaker.

**Three tests had their premise generalised rather than their assertion weakened**, each annotated
with why. "Banking declares every tool" became "every declared tool has a home on some agent" —
`block_card` belongs to Cards, so the old question was the wrong one. "The granting row" became "any
granting row". And the account-enum guard now names the one `(tool, parameter)` pair that is
enumerated on purpose, with a second test that fails if the exemption outlives the parameter.

**`agents/specs.py`'s scaling claim was finally tested.** It said since Phase 2 that adding an agent
is a table row. Three phases later there was a third agent to try it with and it held: one row there,
two in `PERMISSIONS`, nothing else. The one line that did change is in the red-team harness, and that
it was a one-line generalisation rather than a second branch is the evidence rather than an exception.

## What is owed and is not in any ticket

- **`git log e42c063..HEAD` is still owed a human read.**
- **One ADR is offered and not written** (`docs/adr/`): the shared core-banking client that made B1's
  restatement necessary, and now a second candidate — **the corollary change**, which is exactly the
  kind of decision that reads as arbitrary later without the reasoning beside it.
- **The root `CONTEXT-MAP.md`**, still outside `PROJECT_ROOT` and still needing approval by absolute
  path.
- **`/code-review` has not run on this phase.** `CLAUDE.md` requires it before the gate, no
  exceptions, and Marco invokes it.

## The recurring defect, and where it nearly landed this time

**A claim that outruns its evidence.** It happened three times in Phase 4. This phase had more
opportunities than any before it, and the two it caught are recorded above rather than fixed
silently. The ones still ahead are the dangerous ones: a provisioned resource whose ARM 200 proves
creation and not delivery, a role assignment that grants nothing while reporting success, a cap that
must be observed tripping rather than reasoned about, and a real call that will be tempting to
describe as having closed questions it only touched.

**Before writing "verified", run the thing and read the result.**
