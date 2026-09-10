# Handoff — 2026-09-10: Phase 4 built and reviewed three times, awaiting Marco's sign-off

Next session's focus: **Phase 5**. Read this, then `PROJECT_STATE.md`, then stop and check the two
things under "Before you touch anything".

---

## Stop conditions — restate these verbatim at the top of your first summary

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.** No teardown
  path may include a number-release/delete call. Added 2026-08-20 (R-09, `docs/PLAN.md`): ACS's
  Canadian geographic-number inventory has been observed to lose entire localities within ~20
  minutes — unlike every other resource in this project, an equivalent replacement may not be
  purchasable if this number is ever lost. Qualitatively different from the general "no billable
  resource without approval" rule above: this isn't about cost, it's about irreplaceability.
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling.
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

---

## Before you touch anything

1. **Confirm where you are.** `git branch --show-current` must be `azure-banking-work`, and the
   working directory must be the worktree at
   `/Users/marco/K21/Real-world-worktrees/azure-banking/Azure-Banking-Voice-Agentic-AI`. If either
   is wrong, stop and tell Marco where you landed. Do not relocate silently, and never write into
   the old checkout at `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI`.
2. **Verify live Azure state against the API before acting on `PROJECT_STATE.md`.** It is a snapshot
   and has gone stale before. Report disagreements rather than trusting either side.

---

## Where the project actually is

**Phase 4 is built, reviewed three times, and not signed off.** Nothing was provisioned, nothing
redeployed, and no real call was made this whole phase. A caller dialling the number today still
reaches Phase 1's agent on the Phase 2 image.

Criterion-by-criterion evidence is `docs/phase4/exit-check.md`. Recorded deviations and every review
pass are `docs/phase4/findings.md`. Sourced API research is
`docs/phase4/research-carried-findings.md`. **Do not re-derive any of it here — read those.**

| | |
|---|---|
| voice-agent tests | 315 pass, 3 skipped by design |
| mock-core-banking tests | 47 pass |
| B1 red-team | 13 ideas → 211 cases, 194 reaching an attempt, 0 breaches |
| B2 | 0 occurrences, three of four named surfaces |
| `make lint`, B3 static check | clean, passing |

**The one thing blocking the gate**: everything in `git log e42c063..HEAD` is committed and
unreviewed by Marco. Four of those five commits touch the DTMF or PIN path, so the never-auto-accept
rule binds them. Read the range from git, never from a count written in a document — a count was
written into `PROJECT_STATE.md` twice and was wrong both times, because the commit that updates the
number is itself uncounted at the moment it is written.

---

## What Phase 5 inherits, and what will bite

These are the items from this phase that bear on Phase 5 specifically. Full detail is in the
documents above; this is the short list of what changes your plan.

1. **The real call must press `*` and `#`, not only digits.** The DTMF media-stream frame has no
   schema in any Azure specification, and neither control key has a documented spelling on that
   path. The classifier accepts both candidate vocabularies so the ambiguity cannot break a call,
   but that is a mitigation, not an answer. **A digits-only test call closes nothing while looking
   like it closed this.** `docs/phase4/research-carried-findings.md` §2b.
2. **The injected conversation item's acceptance is a one-frame live probe.** Its shape is confirmed
   against the specification; what no source documents is whether Azure's endpoint and
   `gpt-realtime-mini` `2025-10-06` accept it. Both frames now carry a client `event_id`, so a
   rejection can be attributed rather than guessed at. Phase 1 settled the same class of question
   the same way — see `docs/phase1/research-aoai-realtime-wire-format.md`.
3. **Silence is still indistinguishable from acceptance.** The relay imposes no deadline on an
   injected frame. Deliberately not built: the authenticator carries "no timer of any kind" as a
   design decision, so a timer on that path is a Phase 5 design question. Open item 18.
4. **Nothing guarantees DTMF and audio frames arrive in order.** The webhook path ships a
   `sequenceId` for exactly that problem; the media-stream path ships nothing equivalent. The
   four-digit accumulator assumes arrival order equals press order. Observe it; do not inherit it.
5. **mock-core-banking provisioning is a Phase 5 precondition with its own approval.** R-08 must be
   recomputed against a **two**-Container-App fixed cost first, and the Bicep module
   (`infra/modules/mock-core-banking.bicep`) has never been validated — no `bicep` CLI here.
6. **B5 freezes at Phase 5**, and every percentile quoted anywhere states the turn count behind it.

---

## Traps this session actually hit

Worth reading before you write anything, because each cost a review round.

- **A claim that outruns its evidence is this project's recurring defect.** It happened three times
  in this phase, each time inside the fix for the previous one: a B2 surface reported as covered
  while unscanned, then a counterfactual published without being run, then a completeness claim on a
  buffer bound that cannot be complete. Before writing "verified", run the thing.
- **`CONTEXT.md` is load-bearing.** Its Avoid lists caught four terms in this phase, in log lines,
  caller-facing sentences and comments. Check new prose against it.
- **Random hex identifiers can spell a four-digit credential by chance** and turn B2's run-wide scan
  red on a coincidence. Identifiers on that path are built to be unable to contain a digit.
- **`make test` keeps each suite's whole output** in `.test-output-*.log`, so a failure's name
  survives a piped run. One unreproduced failure is still open; if it recurs, keep the output whole.

---

## Suggested skills for the next session

Marco invokes skills; **you name them and stop**. Do not reach for the `Skill` tool yourself. That is
a deliberate override of the usual default and exists so a hard gate stays a human decision point.

- **`/wizard`** — Phase 5 has a human-in-the-loop core: dialling a real phone, pressing real keys,
  hearing the result. That is the phase shape `/wizard` exists for, same as Phase 0.
- **`/research`** — for any remaining factual unknown before the real call. Never answer a pricing,
  API-shape, or region question from memory; this project has been burned by an unverified regional
  assumption already.
- **`/code-review`** — before the Phase 5 gate, no exceptions.
- **`/prototype`** — only if the response-deadline design in item 3 above turns out to be a genuinely
  unresolved design question rather than a small fix.

---

## Verification commands

```
git branch --show-current          # must be azure-banking-work
git worktree list
git log e42c063..HEAD --oneline    # the unreviewed range
make test                          # 315 + 47, whole output kept in .test-output-*.log
make lint                          # ruff + mypy + B3 static allowlist check
```

No cloud dependency in either target. No credentials needed, no spend possible.

---

## Housekeeping

- `.serena/` at the worktree root stays **untracked** — Marco's call, 2026-09-10. It is tool state,
  not project work.
- The branch is **5 commits ahead of `origin/azure-banking-work` and unpushed**. Pushing was not
  asked for and was not done.
- This handoff was written to the OS temp directory by the skill's own fixed behaviour, then copied
  into `docs/handoffs/` and committed. macOS clears `/tmp` on reboot, so that copy is what makes it
  survive.
