# Handoff — Phase 3 signed off, Phase 4 (auth gate permissions) next

Written 2026-09-09. Branch `azure-banking-work`, worktree
`/Users/marco/K21/Real-world-worktrees/azure-banking/Azure-Banking-Voice-Agentic-AI`.
Working tree clean; last commit `ccba34b`.

## STOP CONDITIONS — absolute, no exceptions

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.** No teardown
  path may include a number-release/delete call. Added 2026-08-20 (R-09, `docs/PLAN.md`): ACS's
  Canadian geographic-number inventory has been observed to lose entire localities within ~20 minutes
  — unlike every other resource in this project, an equivalent replacement may not be purchasable if
  this number is ever lost. Qualitatively different from the general "no billable resource without
  approval" rule above: this isn't about cost, it's about irreplaceability.
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling (below).
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

**Phase 4 is the phase where two of those bind on the first diff**: it adds permissions to
`dispatch/gate.py` and puts the DTMF PIN on the path. Every diff touching either gets a human look.

## Where things stand

**Phase 3 (mock-core-banking) was signed off by Marco on 2026-09-09** — "Phase 3: APPROVED". That is
the exit-criteria sign-off and **not** authorisation to provision anything. Nothing is provisioned:
the Dockerfile and `infra/modules/mock-core-banking.bicep` are written and left unapplied, and the
live container app is untouched.

Do not re-read the phase's history to get oriented. It is written up and should be referenced, not
reconstructed:

| what | where |
|---|---|
| current state, open items, next actions | `PROJECT_STATE.md` (9.0 KB, ceiling 20 KB) |
| Phase 3 closed record — scope, decisions, all three review rounds, the overruled rule | `docs/phase3/archive.md` |
| Phase 3 written exit criteria | `docs/phase3/exit-criteria.md` |
| Phase 2, Phase 1 closed records | `docs/phase2/archive.md`, `docs/phase1/archive.md` |
| spec and tickets | GitHub issues #25, #26-32 on `MAOFILHO/Portfolio-Projects` |
| the phase plan, constraints, risks | `docs/PLAN.md` (Phase 4 is at line 635) |
| domain vocabulary | `CONTEXT.md` |

Last four commits: `ccba34b` (the overruled account-name rule + sign-off), `a2426ba` (archiving),
`762135f` (two rounds of review fixes), `4e77828` (Phase 3's earlier fixes).

**Verify live Azure state against the API before acting on `PROJECT_STATE.md`** — resume discipline,
`CLAUDE.md`. The doc is a snapshot and has been wrong before.

## Phase 4 — what it is

`docs/PLAN.md` line 635, quoted in full:

> **Phase 4 — Auth gate permissions ⛔ *B1/B2 threshold*.** KBA (card last-4 + DOB) + DTMF PIN. Adds
> the `Authenticated` transition and the permissions it unlocks to the Phase-2 gate — does not
> introduce the gate itself. ≥120 adversarial cases in `redteam/` (deterministic, L1, free).
> **Exit:** B1 = 0 breaches, B2 = 0 occurrences, both blocking in CI.

### What already exists, and must not be rebuilt

- **The gate itself.** `voice-agent/azbank_voice_agent/dispatch/gate.py` is a pure function of
  `(agent, auth_state, tool_name)`, deny-all, with `PERMISSIONS = {}`. Phase 4 **adds rows to that
  table**; it does not touch `is_allowed()`. `ANONYMOUS`/`AUTHENTICATED` and
  `TRIAGE_AGENT`/`BANKING_AGENT` are already named there, so the table's shape is the real one.
- **The choke point.** `dispatch/tools.py::dispatch_tool_call` is the only path from "the model asked
  for a tool" to "the tool ran", and `tests/test_gate.py` proves that tool by tool off the declared
  tool list rather than a hand-maintained one.
- **DTMF arrival, already B2-safe.** `transport/acs.py::classify_inbound` returns `(DTMF, None)` —
  the tone value never leaves that function. `realtime/session.py` logs arrival only and ignores the
  frame. Phase 4 is where the tone actually has to be consumed, and that is the diff that most needs
  a human look.
- **The auth state is already threaded through every call**, not ambient: `run_call` holds `agent`
  and `auth_state` as call-scoped locals and passes both to every dispatch. Phase 4 adds the
  transition into `AUTHENTICATED`; it should not need to change how the value travels.

### What does not exist yet

- `redteam/` — the directory does not exist. Neither does `evals/`. `docs/PLAN.md` line 393 has the
  intended layout.
- Any transition into `AUTHENTICATED`. Phase 2 deliberately shipped the state name with no way to
  reach it.
- Any KBA data. `mock-core-banking` holds two accounts and balances only — no card numbers, no dates
  of birth, no PIN. Phase 4 has to decide where those live; the service is the obvious home, and
  extending it means the same status-mapping and no-prose discipline `docs/phase3/archive.md`
  records.
- Phase 4 tickets. The last issue is #32, so Phase 4's spec issue and its sub-issues start at #33.

## Traps this session hit that will recur

These are not general advice; each one cost a round here.

1. **A comment that has drifted is a defect in this repo, not a nitpick.** Two review rounds spent
   findings on rationale that was true when written and false by the time it was read. If you change
   behaviour, change the paragraph arguing for it in the same diff.
2. **The fake and the real client must fail identically.** Issue #25's user story 10. Three separate
   rounds found divergences. `tests/test_core_banking_fake.py`'s `EXPECTED_ERRORS` table is driven
   against a real spawned service by `tests/test_core_banking_live.py`, so it cannot rot into a
   transcribed constant. Phase 4 will need the same arrangement for whatever stands in for KBA.
3. **A test asserting a caller-facing sentence belongs where that sentence can actually be produced.**
   The fake has no URL and no HTTP status; assertions about real-service wording are meaningless
   against it. That mistake was made twice, most recently on 2026-09-09.
4. **`assertIn` on a caller-facing sentence can pass while the caller hears something wrong.** The
   original URL leak survived because the URL contained the account name. Assert exact sentences.
5. **Model arguments are not schema-shaped.** `"amount": "100"`, `true`, `null`, an object, an
   unparseable payload — all reached production paths here. B2 makes this sharper in Phase 4: the
   PIN arrives as DTMF, and whatever consumes it must not be able to raise, log, or echo it.
6. **`dispatch_tool_call` never raises, and that is load-bearing** — `run_call` re-raises whatever
   escapes, which drops the call mid-sentence.
7. **Never speak an exception's own message.** Compose the sentence, log the diagnosis. The generic
   branch was speaking `str(e)` and put a JSON parser message in front of a caller.

## Open items carried into Phase 4

Full list in `PROJECT_STATE.md`; these are the ones with a bearing on this phase:

- **`infra/modules/mock-core-banking.bicep` is unvalidated** — no `bicep` CLI here, and `infra/` has
  no `main.bicep` to be consistent with. Phase 3's one known-partial.
- **Provisioning mock-core-banking is a separate, unapproved step** with R-08 (recomputed against a
  **two**-Container-App fixed cost) as its precondition. It is next action 1 in `PROJECT_STATE.md`,
  and it is not part of Phase 4.
- **No durable ACS-side call-diagnostics path** — Phase 6's real fix, but Phase 4 is the phase whose
  failures most need auditing.
- **Dead air before the agent speaks first (2.5–11 s)** is parked deliberately, and the note exists
  so it is not re-litigated at every boundary.

## Suggested skills

Call these with the Skill tool. **Marco invokes skills; do not reach for one on your own initiative**
— name it and stop (`CLAUDE.md`, Skill discipline).

- **`/research`** — before any factual claim about DTMF delivery semantics in ACS bidirectional
  streaming, or about what Azure charges for anything Phase 4 might add. This project has been burned
  by an unverified regional assumption once already.
- **`/wizard`** — Phase 4 has a human-in-the-loop step Claude cannot perform: dialling the number and
  entering a PIN by keypad. Phase 0 ran this way.
- **`/code-review`** — before the phase gate, no exceptions. Run both axes against the phase's opening
  commit, with the spec issue as the spec argument. Three rounds on Phase 3 each found real defects
  after the previous round had declared itself clean.
- **`/diagnosing-bugs`** — for anything that looks like "sometimes the gate lets it through". Build
  the loop before theorising; that discipline found every defect in the last two rounds.
- **`/prototype`** — only if the KBA-then-PIN state model is genuinely unresolved, not as a substitute
  for `/research`.

## First moves for the next session

1. Verify live Azure state against the API; report any disagreement with `PROJECT_STATE.md` rather
   than trusting either silently.
2. Read `docs/PLAN.md`'s Phase 4 section and the B1/B2 rows of its constraints table. Do not start
   from this document's summary of them.
3. Write Phase 4's exit criteria and get Marco's explicit approval **before any code** — that is a
   stop condition, not a formality. Phase 3's live at `docs/phase3/exit-criteria.md` as the model to
   follow.
4. File the spec issue and its sub-issues (#33 onwards), per `docs/agents/issue-tracker.md`.
