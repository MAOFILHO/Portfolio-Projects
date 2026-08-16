# FNOL Phase 11 handoff — 2026-08-16

Project: `/Users/marco/K21/Real-world/AWS-Insurance-FNOL-Voice-Agentic-AI` (monorepo root:
`/Users/marco/K21/Real-world`, do not write outside the project path without absolute-path approval —
`CLAUDE.md` "Scope rule").

This file is a map, not a source of truth. Everything it points at can drift; this file itself will not be
updated again — re-read the pointed-to files, don't trust this doc's prose over them.

## Read first, in this order

1. `CLAUDE.md` — stop conditions (top of file), cost gate, PROJECT_ROOT scope rule. Restate the four STOP
   CONDITIONS verbatim at the top of your first response and after every `/compact`, per its own instruction.
2. `PROJECT_STATE.md` line 13 (`**Last updated:**`) — the single most current narrative line in the project.
3. `PROJECT_STATE.md` lines 5952–5992 — Phase 11's 8 exit criteria, table + stage mapping + current status
   paragraph. This is the authoritative criteria table; nothing below duplicates its text, only its shape.
4. `docs/RESULTS.md` §34, §36, §37 — the `D90` saga end to end (root cause → fix → live verification →
   process defect found while writing it up). Long, but it's the freshest and most load-bearing work.
5. `docs/REVIEW-CRITERIA.md` — the whole file is short; §6/§7/§8 are new this project-arc, see below.

## Phase 11 — eight criteria, current state (full text: `PROJECT_STATE.md` lines 5952–5992)

Stage letters, per the table's own mapping: **0** preflight, **A** criteria 1+2, **B** criterion 3,
**C** criterion 4, **D** criterion 8(a/b), **E** criterion 5, **F** criterion 6.

| # | What | Stage | State |
|---|---|---|---|
| 1 | Budget alarm, firing-proof required | A | Cost table presented (`RESULTS.md` §17), **not applied** — awaiting Marco's go. `PROJECT_STATE.md` line 44, "Firing-proof clock" |
| 2 | Cost dashboard, checked against a known real number | A | Same as #1 — not started |
| 3 | Operational CloudWatch dashboard, split B1/B2 | B | **B1 built + applied**, emitter confirmed live in real CloudWatch. **B2 not built** (needs Stage D's latency instrumentation). Panel-liveness proof (**claim (b)**, see Open items) still not obtained, **blocked on `D88`** |
| 4 | PII redaction at the CloudWatch Logs sink | C | **Built** (`observability/log_redaction.py`). Positive-control run 1 (local) PASSED. **Run 2 (deployed-runtime proof) CLOSED 2026-08-16** — real self-report line captured live (`OI2`, now closed) |
| 5 | Ops runbooks | E | Not started — explicitly gated on Stages A–D's *actual* built mechanisms existing first |
| 6 | Branch protection required-status-check | F | **Pending, not blocked.** Workflow ran green on `origin/main` once (run `31887876709`). Manual console click still undone — `docs/runbooks/MANUAL-STEPS.md` item 5. Negative-control push (Marco's amendment 3) not yet run |
| 7 | Record hygiene | 0 | **Closed**, confirmed Stage 0 |
| 8a | `C14` regression signal (Lambda p95 over eval-harness calls, not real traffic) | D | Not started this phase-arc — `C14`'s existing measured value is from Phase 9 (see canonical phrasing below), Stage D itself hasn't re-run it |
| 8b | `C1` scheduled-eval tripwire | D | Not started as a *scheduled* mechanism — `C1` itself has been re-verified live multiple times ad hoc this arc, most recently 2026-08-16 (see C1 section below), but no EventBridge-scheduled tripwire exists yet |

**Not yet touched this arc:** Stage A apply, Stage D (both halves), Stage E, Stage F's manual click +
negative control.

## `C1` — status, three tiers (do not compress this to "C1 verified")

**Corrected 2026-08-16** (this handoff's first draft flattened these into one list and, in doing so, dropped
the topology qualifier and added a non-canonical item — see `RESULTS.md` §38 for the finding). Restructured
per Marco's direct instruction into the shape the record itself uses: exactly three canonical scope
qualifiers, kept separate from build-identity tracking, kept separate from other live caveats.

**Tier 1 — the canonical scope qualifiers. Exactly three, quoted, not merged** (`PROJECT_STATE.md:5087` and
`:5746`, both state it identically):

> "VERIFIED, WARM PATH, build `u9iIy...`. 1.000 (26/26)... **Scope, restated:** this figure describes today's
> topology — every turn reaches the merged `classify_turn` call. A lexical short-circuit... would change
> that topology and would require re-verifying `C1` against it... Cold-start coverage remains an existence
> proof (1/19), not a measurement."

(a) **Warm path only.**
(b) **Scoped to today's topology** — every turn reaches the merged `classify_turn` call. A lexical
    short-circuit (or any other routing change) would change that topology and would require re-verifying
    `C1` against it — **even on an identical build hash.** Do not collapse this into build identity below;
    the record treats them as orthogonal (`PROJECT_STATE.md:5041-5042`, `:6638`, `:7174`): build identity
    tracks the artifact, topology tracks the structural claim.
(c) **Cold-start coverage is a 1-of-19 existence proof, not a measurement** — same epistemic category this
    project also applies to `CF3`'s n=5 result.

**Tier 2 — artifact identity, tracked separately, not itself a scope qualifier:**

`CodeSha256` `51JN903edLEVaSjP5zoEWQir4VLC+lQEVHA56b/5CUc=` (re-verified 2026-08-16, `RESULTS.md` §36 §4;
`PROJECT_STATE.md` `OI7` row). This is the re-verification trigger — `C1` reads `VERIFIED` against this
specific deployed build or `PENDING RE-VERIFICATION` otherwise (`PROJECT_STATE.md:6638`). It answers "is
this still the build that earned the 1.000," a different question from tier 1(b)'s "is the structure that
produced the 1.000 still in place."

**Tier 3 — other live caveats, explicitly NOT part of the canonical three:**

- **k=1 sampling.** The `1.000` is n=26 at one sample per item. "The k-sample reading of `C1`" is a
  **separate, older (Phase 7), still-open interpretive question** — never resolved to k=5 as recommended,
  still live (`PROJECT_STATE.md:563`) — not one of the three canonical qualifiers above.
- **Immune only to the mechanisms actually checked.** This session's `D90`-narrowing finding
  (`RESULTS.md` §34 §3, Marco's own correction): `C1` is confirmed structurally immune to `D90`'s
  wire-contract mechanism specifically (reads `sessionAttributes.escalation_reason`, never `intent.name`) —
  that is not a general clean bill against every other open defect.

Any future session citing `C1` should quote tier 1's three qualifiers in full, state tier 2's build hash
separately, and only add tier 3's items when the caveat they name is actually relevant — never fold any of
the three tiers into another.

## `C14` — canonical phrasing, verbatim (do not use "19ms" shorthand anywhere)

> "warm-path p95 1,819ms, measured on a sample excluding cold starts; true p95 over real traffic mix is
> ≥1,819ms, distance to the 1,800ms target unmeasured"

Source of the correction: `docs/RESULTS.md` §12.10. This is a Phase 9 measurement, not yet re-run inside
Phase 11 Stage D — 8a above is the criterion that will next touch this number.

## Open items — one line each, full text at the cited row

All rows live in `PROJECT_STATE.md`'s "Open items — current phase" table (~lines 651–661) unless noted.
Do not restate their full paragraphs here; read the row.

| Item | One-line state | Row / section |
|---|---|---|
| `OI1` | Stage A's $2.00 synthetic-breach notification still live on the real budget — permanent hair-trigger, not yet removed | `PROJECT_STATE.md` `OI1` row |
| `OI3` | `codehook_deps_layer`'s `etag` phantom diff — **corrected 2026-08-16**: confirmed it DOES cause a real (harmless) re-upload every plan/apply, not a no-op. Still not fixed; fix is a Terraform-mechanics swap to `source_hash` | `PROJECT_STATE.md` `OI3` row; `RESULTS.md` §36 §1 |
| `OI5` (`D88`) | OUTPUT guardrail v3 has zero PII entities left that would ever fire on this domain's own data spoken back to its owner (deliberate, Marco-approved removal, predates this session's test). Test's own assertion was stale, not the guardrail. **3 options given to Marco, none chosen** | `PROJECT_STATE.md` `OI5` row |
| `OI6` (`D89`) | INPUT guardrail false-blocks the word "file" in an ordinary `FileAutoClaim` confirmation ("yes, go ahead and file it"), zero conversational context. **Open, unscoped, Marco's to take up** | `PROJECT_STATE.md` `OI6` row |
| `OI7` (`D90`) | **Part 2 (wire contract) CLOSED 2026-08-16** — `executed_node_intent` shipped, deployed, live-verified. **Part 1 (zero-context routing) remains OPEN and unscoped** — `route_and_classify` still classifies every turn from raw text alone. `D90` overall stays open until part 1 does too | `PROJECT_STATE.md` `OI7` row; `RESULTS.md` §34, §36 |
| `OI8` (`D91`) | Staged-but-uncommitted work can silently ride into an unrelated commit (`git commit` acts on the whole index). This instance's impact was null (pure renames). **Guard proposed** (session-start `git status --porcelain` read), **not built** | `PROJECT_STATE.md` `OI8` row |
| `OI9` (`D92`, new 2026-08-16) | The eval harness overwrites its own baseline JSON with no existing-file check and no build-identifying field to compare against — same defect class as `D91` (a convention held up only by operator memory). **Guard proposed** (add a build-hash field, then compare-and-refuse or compare-and-auto-archive — block vs. auto-archive is Marco's undecided call), **not built** | `PROJECT_STATE.md` `OI9` row; `RESULTS.md` §37 §1 |
| `CF8` | Standing `make verify-*` gate exercising every ordinary intent's real, deployed, slot-filled happy path. Built, currently **10/13 green** (correct state — 3 known failures are `D88`/`D89`/`D90` part 1). Proposed as a **Phase 12 entry condition**, not a Phase 11 exit criterion | `PROJECT_STATE.md` `CF8` row (~line 642) |
| Claim (b) | Stage B1's forced-guardrail-intervention panel-liveness proof (criterion 3's liveness requirement). `D87` no longer blocks it; **now blocked on `D88` specifically** — v3's guardrail config may have removed every ordinary-flow trigger that would ever fire | `PROJECT_STATE.md` criterion-3 row text (line 5969) |

## `REVIEW-CRITERIA.md` — new standing rules this arc (full text at the cited section, not reproduced here)

- **§6 — sweep recall is bounded by the search terms, not the corpus.** Any grep/sweep "found"/"not found"
  claim must state the term list, the raw hit count, and whether the remainder was individually inspected or
  pattern-classified.
- **§7 — activity signals are not effect signals.** Added after `D88`: a log line firing, a code path
  executing, or a config existing is not the same claim as the effect it's supposed to produce actually
  happening.
- **§8 — a defect fixed at one call site is not fixed until every site of that class is enumerated.**
  Added after `D90` part 2 / `D84`'s asymmetry: `D84` fixed `_elicit_slot()`'s echo-Lex's-intent defect two
  phases before `_close()`'s identical, unfixed sibling site was found — absence of a loud failure (Lex's
  `ValidationException` forced `D84`'s discovery; `Close` has no equivalent) is not evidence of correctness.

## `RESULTS.md` §34's three tiers — current state (full detail: §34 §2 as updated 2026-08-16, plus §37 §2)

Post-tightening (`RESULTS.md` §36 §6, §37), the tiers from the original sweep have moved:

- **Structurally immune** (unchanged): `C1` (reads `escalation_reason`, never `intent.name`), `D84`'s own
  regression tests, `D47`'s bias-routing finding (`measure_bias_pairs.py` never touches the codehook).
- **Moved from "inferred" to structurally verified**: `verify_lambda_execution.py` events 10–12 now assert
  `executed_node_intent` directly, not template-substring content. Event 11 (`UpdateContactInfo`) is the
  clean case — same PASS before and after, entirely different footing (`RESULTS.md` §37 §2).
- **Still true-by-accident, untouched by this tightening**:
  `test_file_auto_claim_reaches_fulfilment_and_closes` (`tests/unit/test_lex_codehook.py`) — still pins its
  fake router to one constant intent every turn, never exercises a genuine disagreement. Out of this arc's
  tightening scope.
- **Still actually exposed on the live path, narrower than before**: event 13
  (`RentalTowingEntitlement`) — the code-level check now exists and is unit-proven correct
  (`test_close_carries_executed_node_intent_on_an_ordinary_fulfillment`), but is unexercised live because
  `D90` part 1's misroute fails the prior `Close` check first, every run.

## Immediate next steps (not decided here, listed for orientation only)

- `D90` part 1 (zero-context routing) — unscoped, explicitly "Marco's to take up next."
- Option A (mirror `D84` inside `_close()` itself) — blocked on a live verification question: does Lex
  accept a `Close` whose intent name disagrees with the turn's own NLU intent? Unconfirmed, unlike
  `ElicitSlot`'s known `ValidationException`. Needs the same live-check discipline `D84` itself used.
- `D88`/`D89` — dispositions pending Marco (3 options given for `D88`, none chosen; `D89` unscoped).
- `D91`/`D92` guards — both proposed, neither built; both need Marco's block-vs-report call before scoping.
- Phase 11 Stage A apply — cost table already presented, needs `APPROVED: Phase 11` (already have phase
  approval) plus explicit go on the apply step itself, per the redeploy-is-always-FULL-REVIEW rule.

## Suggested skills for the next session

- **`diagnosing-bugs`** — if the next session picks up `D90` part 1 or option A's live-Lex-acceptance
  question; both are genuine open bugs needing a tight repro loop before any fix.
- No other skill is obviously load-bearing from here — the rest of Phase 11 (Stage A apply, runbooks,
  branch protection) is direct execution against an already-approved plan, not diagnosis or design work.
