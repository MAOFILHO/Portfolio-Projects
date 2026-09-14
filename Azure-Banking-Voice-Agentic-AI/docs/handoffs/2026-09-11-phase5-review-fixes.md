# Handoff — 2026-09-11 — Phase 5's review fixes landed; Phase 6 does not start yet

## Stop conditions (restated verbatim, per `CLAUDE.md`)

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.** No teardown
  path may include a number-release/delete call.
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling.
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

---

## Read the request honestly: Phase 6 cannot begin

Marco's words closing this session were *"Phase 5 and let's go Phase 6"*. **Phase 6 does not start,
and this handoff is the reason written down rather than a refusal to act.**

Phase 5's exit is not met. Four tickets are open (`#57`–`#60`), nothing has been provisioned,
no call has been made, and B5 is not frozen. The first stop condition above is unambiguous. What a
caller dialling `+1 705 910 0383` reaches today is still Phase 1's agent on the Phase 2 image — the
gap between what is committed and what answers the phone is **four phases wide**, and Phase 6 would
make it five.

**None of the four remaining tickets is agent-executable.** `#57` provisions billable Azure
resources and needs Marco's typed approval; `#58` needs his hands on a keypad and his voice on a
phone; `#59` freezes B5 from the turns that call produces; `#60` closes out and depends on all
three. An agent picking this up cannot clear the path alone.

A live `APPROVED: Phase 5` was typed this session and **was not used**. Nothing here spent anything
or touched Azure. Treat it as still available for `#57`, but note that Marco typed it in answer to a
question about which tickets to implement, not in answer to a provisioning request — and the project
already has precedent (`PROJECT_STATE.md`, stop condition 2) for an approval signing off exit
criteria without authorising provisioning. **Confirm before spending.**

---

## What this session actually did

Implemented all eight findings of the Phase 5 `/code-review`. Detail is in
**`docs/phase5/review-fixes.md`** — the eight findings, what fixed each, the test that fails if it
is reverted, and two decisions taken inside the fixes. Not repeated here.

Two commits:

| commit | what |
|---|---|
| `581b8f4` | seven findings |
| `59a3d93` | the eighth, alone, because it sits in front of the auth gate |

The eighth was held out of the first commit deliberately, shown to Marco as a standalone diff, and
committed only after he read it and asked for one docstring paragraph to move. That is the
never-auto-accept rule being honoured rather than reasoned around, and the next session should
honour it the same way: **most of what remains touches `dispatch/` or the DTMF/PIN path.**

### Where the eight tickets came from

They were **never filed as issues**. A prior session (transcript `557add17`) ran `/to-tickets` on the
review, drafted eight, asked Marco two questions, and ended before publishing. This session
recovered them from that transcript. Both commits therefore reference only the spec `#43`.

Marco answered both open questions this session:

- **The ledger race** → an in-process lock only, not ETag optimistic concurrency. Recorded as
  `PROJECT_STATE.md` open item 20, with what it does not cover stated rather than implied.
- **The gate-adjacent fix** → implement it, show the diff, do not auto-land it.

### Two defects found that the review did not name

Both hidden by skip-by-default, and together they meant `T-B3-SUCCESSOR-BOOT` **had not executed
since Phase 3** — it read green by never running. Detail in `docs/phase5/review-fixes.md`. Worth
carrying forward as a pattern: this repo has three skip-by-default or ops-only code paths
(`test_successor_boot.py`, `scripts/b5_probe.py`, `docs/phase0/wizard/*.sh`) and two of the three
have now been found broken by drift while reading green. **The probe was repaired in `#54` for
exactly this reason and has still never been run.**

---

## State at handoff

| | |
|---|---|
| branch | `azure-banking-work`, worktree `Real-world-worktrees/azure-banking` |
| working tree | clean, except untracked `.serena/` which predates this session |
| voice-agent tests | 491 pass, 3 skipped by design |
| mock-core-banking tests | 90 pass |
| `make lint`, mypy, B3 static check | clean |
| B1 red-team | 593 cases from 18 ideas, 0 breaches — unchanged by these fixes |
| Azure | nothing provisioned, nothing redeployed, no call made |

`PROJECT_STATE.md` was updated and re-trimmed to stay under its ceiling (20,417 bytes / 276 lines);
open item 10 moved out to `docs/phase5/review-fixes.md` and two items were compressed.

---

## Next actions, in order

The authoritative list is `PROJECT_STATE.md` "Next actions", which now opens with three items this
session added. In short:

1. **`/code-review` the two commits above.** Eight findings were actioned and the fixes are
   themselves unreviewed. This is the cheapest point to catch a bad fix.
2. **File the eight findings as issues**, so the commits stop pointing only at the phase spec.
3. **`/research`** the role definition GUID and Table Storage's rate — both written from
   documentation, both named as unverified in the module that uses them, and the first one failing
   produces a role assignment returning 200 OK that grants nothing. A third question joined them
   this session: the exact `azure-data-tables` transport timeout option names (open item 19).
4. **Human review of the two Bicep modules.** No `bicep` CLI here, no `main.bicep`; human review is
   the only check that exists.
5. **Read `git log e42c063..HEAD`** — Phase 5's one unmet entry condition, waived rather than
   satisfied.
6. **Then `#57`, `#58`, `#59`, `#60`**, in that order, all needing Marco.

---

## Suggested skills

Call these with the `Skill` tool **only when Marco asks for them**. `CLAUDE.md`'s skill discipline
is a deliberate override of the usual default: *"Marco invokes skills — Claude does not invoke them
on its own initiative."* Name the skill and why it applies, then stop. This session followed that
rule and should be copied.

| skill | why, here |
|---|---|
| `/code-review` | Owed on `581b8f4` and `59a3d93`. Also required before every phase gate, no exceptions. |
| `/research` | The three unverified facts in next action 3. Never answer them from memory — this project has been burned once already by an unverified regional assumption (`docs/PLAN.md`, decision 12). |
| `/wizard` | `#57` and `#58` are the textbook case: provisioning that needs a live decision, and dialling a real phone. Phase 0 ran this way. |
| `/handoff` | At the end of the next session. Note that it writes to the OS temp directory by its own fixed design — **copy the output into `docs/handoffs/` and commit it before the session ends**, or it is lost to `/tmp` cleanup. |

`/prototype` is **not** indicated. Nothing outstanding is an unresolved design question; the
remaining work is provisioning, one phone call, and paperwork.

---

## Traps for the next session

1. **Verify live Azure state before trusting `PROJECT_STATE.md`.** Resume discipline, and it has
   already caught one disagreement (a provider registration that had finished while the doc still
   said `Registering`).
2. **A 200 OK proves creation, not access.** `#57`'s role assignment must be proved with a write
   that is read back. This is criterion 21 and it exists because ARM will cheerfully return 200 for
   a role assignment that grants nothing.
3. **The acceptance call must press `*` and `#`.** A digits-only call closes nothing while looking
   like it closed the DTMF vocabulary question. The two keys the keypad acts on have no documented
   spelling on this path at all.
4. **Do not re-run `docs/phase0/wizard/02-test-calls.sh` carelessly** — stages 1-3 unconditionally
   prompt for three fresh billable calls before the free read-only evidence extraction.
5. **Query `workspace-rgazurebankingvoiceagenticai1D`** for logs, never `...aiCS`, which has been
   stale since 2026-08-25. Three workspaces exist, not two.
6. **The phone number is irreplaceable, not merely billable.** ACS's Canadian geographic inventory
   has been observed losing entire localities within ~20 minutes.
