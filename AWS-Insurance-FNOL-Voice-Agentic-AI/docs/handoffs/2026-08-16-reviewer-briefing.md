# FNOL reviewer briefing — 2026-08-16

Project: `/Users/marco/K21/Real-world/AWS-Insurance-FNOL-Voice-Agentic-AI` (monorepo root:
`/Users/marco/K21/Real-world`). This is a briefing for the reviewer, not a session handoff for a
continuing agent — see `docs/handoffs/2026-08-16-phase11-reviewer-briefing.md` for that. This file is a
map, not a source of truth: everything it points at can drift; it will not be updated again. Re-read the
cited files, don't trust this doc's prose over them — that discipline is exactly your job description below.

## Your role

You review phase/stage reports before Marco approves them. Specifically:

- **Push back on protocols that don't support their claims.** If a check's own design can't distinguish the
  outcome it claims from a different, weaker one, say so before the claim is accepted — don't wait to be
  asked.
- **Flag where a measurement is weaker than the conclusion drawn from it.** A sample size, a scope
  qualifier, an "activity happened" reading standing in for an "effect happened" claim — these are your
  primary targets. `docs/REVIEW-CRITERIA.md` (below) is the accumulated, dated record of exactly this kind
  of gap being found, each one after it had already slipped past a report once.
- **Say when a finding belongs in `RESULTS.md` rather than a footnote.** A finding's home tells the reader
  how seriously to take it; misplacing one (a real defect buried in prose, a caveat inline where it reads as
  settled) is itself a defect this project has a name for (`REVIEW-CRITERIA.md` §7/§9).
- **Direct over agreeable.** State the gap plainly, with the file:line it's checkable against. Do not soften
  a real finding into a question, and do not manufacture a finding to seem thorough — both failure modes are
  on record in this project's own history (`docs/REVIEW-CRITERIA.md`'s §1 checklist exists because both
  happened).

## The recurring defect class — read this before reviewing any closure

**A finding closes correctly on its own narrow, actually-checked scope — but carries a broader claim riding
along that was never itself checked, and the broader claim, not the narrow one, is what later turns out
wrong.** This has recurred today with three independent, load-bearing instances. When you review a closure,
separate what was actually verified from any broader statement attached to it, and ask whether the broader
statement got the same scrutiny.

1. **`D93`/`OI10`** (`PROJECT_STATE.md` `OI10` row) — the original `$2.00` synthetic-breach threshold was
   measured correctly against account-wide untagged MTD spend. The narrow measurement was right. Nobody
   checked whether that was the number the budget's own `cost_filter` actually evaluates — it isn't
   (tagged spend only, confirmed never past `$0.48`) — so the threshold could never have fired. Correct
   measurement, wrong scope match, unchecked.
2. **`D88`/`OI5` → `D121`** (`docs/RESULTS.md` §33 §2, §76) — "not a defect" (the claim-number-masking
   finding, narrow) closed correctly and stays closed. A second, broader claim was attached to that same
   closure — "no ordinary in-scope conversational path exists that would ever fire a real OUTPUT
   intervention" — and was never itself tested. It was false: `UpdateContactInfo`'s own confirmation
   readback is exactly such a path, found by reading the code, then confirmed live (`D121`).
3. **`D16` (2026-08-12) → `D121`** (`docs/REVIEW-CRITERIA.md` §8's extension, today) — removing the four
   custom identifier regexes correctly closed every call site of *that* mechanism for "masking a caller's
   own data back to them." Nobody checked whether the same *outcome* was reachable through a *different*
   mechanism. It was — the PII entity `ANONYMIZE` policy, untouched by that change, reaches the identical
   outcome on a different node. The fix was incomplete, not wrong in kind.

When a report tells you something is closed, ask what was actually checked versus what was merely stated
alongside it — and treat the second category as unverified until it has its own citation.

## `C1` — the three-tier discipline (do not let a report compress this to "C1 verified")

**Tier 1 — the three canonical scope qualifiers, verbatim from `PROJECT_STATE.md:5371`:**

> "VERIFIED, WARM PATH, build `u9iIy...` [historical hash as originally written — see build hash below for
> the current value]. 1.000 (26/26), provenance-gated, `fail-closed: 0`, independently corroborated...
> **Scope, restated:** this figure describes *today's topology* — every turn reaches the merged
> `classify_turn` call. A lexical short-circuit's `C1`-threatening form would change that topology and would
> require re-verifying `C1` against it before the 1.000 figure could be trusted again for the modified
> system; it is not automatically inherited. Cold-start coverage remains an existence proof (1/19), not a
> measurement."

That is: **(a)** warm path only, **(b)** scoped to today's topology — not automatically inherited across a
routing change, even on an identical build hash, **(c)** cold-start coverage is a 1-of-19 existence proof,
not a measurement.

**Tier 2 — build/artifact identity, tracked separately, not itself a scope qualifier:** current live build
`CodeSha256 /4FFnR9Q7cbkbuWmCR1Yth2baW/cxp7F+r/fPP+JCOo=`, `1.000 (26/26)`, confirmed live (not from apply
output alone) 2026-08-16, reproducible from `main` as of commit `8f140bc` (`PROJECT_STATE.md`, Phase status
table row 8). This answers "is this still the build that earned the 1.000" — a different question from
tier 1(b)'s "is the structure that produced the 1.000 still in place."

**Tier 3 — other live caveats, explicitly not part of the canonical three:** k=1 sampling (the `1.000` is
n=26 at one sample per item, a separate, still-open Phase 7 question); "immune only to mechanisms actually
checked" (`C1` is confirmed structurally immune to specific named mechanisms, e.g. `D90`'s wire-contract
shape — not a general clean bill against every other open defect).

**A report citing `C1` should quote tier 1 in full, state tier 2's hash separately, and only add tier 3
items when the specific caveat named is actually relevant.** Never let one tier stand in for another —
`REVIEW-CRITERIA.md` §9 exists because this collapsed once already, silently, inside a corrected handoff.

## `C14` — canonical phrasing, verbatim

> "warm-path p95 1,819ms, measured on a sample excluding cold starts; true p95 over real traffic mix is
> ≥1,819ms, distance to the 1,800ms target unmeasured"

Source: `docs/RESULTS.md` §12.10. Reject "19ms" or "failing by 19ms" anywhere it appears — that phrasing
implies a known, specific gap rather than a floor on an unmeasured one, and this project retired it
everywhere on the record for exactly that reason. **Phase 11's criterion 8a measured a different, related
but non-comparable number** — Lambda-invocation p95 (1,651.06ms, turn-processing only, no Lex/Polly leg) —
and does not update or supersede this figure. If a report conflates the two, that is itself a finding.

## `REVIEW-CRITERIA.md` §§6–10 — one line each (full text at the section cited)

- **§6** — a grep/sweep "N found" claim is a claim about the search terms run, not the corpus, until a
  differently-worded recall check still agrees.
- **§7** — a non-zero usage counter, a clean `StatusCode`, or a legal response shape proves the control ran,
  never that it did what it exists to do; check the effect field, not the activity field.
- **§8** — a defect "fixed" at one call site isn't fixed until every site of that class is enumerated;
  **extended today** to mechanisms, not just call sites (see "the recurring defect class," above).
- **§9** — a summary carrying a scoped claim must cite its source file:line and re-verify against the
  *current* state at write time, not quote from memory — and a verbatim quote of a stale figure is not
  itself sufficient; bracket it or state the current value alongside it.
- **§10** — a guardrail or classifier's `examples` entry is a config input, not a verified behavior, until a
  direct probe checks it; something can sit in an `examples` list, cited as settled fact through two fix
  attempts, and turn out never to have been tested.

## Phase 11 — eight criteria, exact closure state as of tonight

Full text: `PROJECT_STATE.md`'s Phase 11 criteria table (`| 1 |` through `| 8b |`, search for `| 8a |` to
locate it) and the Phase status table row 11. **7 of 8 closed or satisfied; criterion 5 is the sole
remainder, left open deliberately.**

| # | State |
|---|---|
| 1 — Budget alarm | **CLOSED.** Full chain confirmed: `$0.25` threshold applied → `NotificationState: ALARM` live → SNS published → breach email received and confirmed by Marco (`ACTUAL $0.71`). Temporary test notification's removal plan is generated (`/tmp/oi1_removal.tfplan`) and awaiting apply — `OI1`'s row |
| 2 — Cost dashboard | **CLOSED**, `RESULTS.md` §75. Independent live CE read vs. the dashboard's own datapoint, correctly directioned. Named, not worked around: `aws_scheduler_schedule.ce_pull_weekly` has never fired on its own schedule |
| 3 — Operational dashboard | **B1 CLOSED including the panel-liveness proof**, `RESULTS.md` §76 — a real OUTPUT intervention now on record, which is what surfaced `D121` (see below). **B2 (turn-latency) not built** — deferred, Phase 12 entry condition |
| 4 — PII redaction, Logs sink | **CLOSED**, both runs, `OI2` |
| 5 — Ops runbooks | **OPEN, deliberately not written tonight.** Two runbooks needed: `C14` warm-path exceedance (canonical phrasing above), guardrail false-positive spike (`D89`'s real live false-positive as worked example). Marco's instruction: hold until `D121`'s guardrail fix lands, so the runbook doesn't describe a config about to change |
| 6 — Branch protection | **CLOSED**, both halves, independently verified via `gh run view 31971816508` / `gh pr view 4` |
| 7 — Record hygiene | **CLOSED**, Stage 0 |
| 8a — Lambda p95 signal | **CLOSED**, `RESULTS.md` §74. p95 = 1,651.06ms, 121 samples, current build only. Explicitly not a `C14` measurement |
| 8b — `C1` scheduled-eval tripwire | **Satisfied**, not by synthetic injection but by `D97`'s real outage-and-recovery cycle (guardrail-version coupling defect, window `18:21:13Z`→`21:07:08Z`) |

## Every open item — bucket and named home

`D121`/`OI39` first, per Marco's instruction. All others: full text at the cited `PROJECT_STATE.md` row;
this list gives bucket + home only.

| Item | Bucket | Named home |
|---|---|---|
| **`D121`/`OI39`** — `UpdateContactInfo` cannot complete by voice for `field=email`/`field=phone`, live, highest severity currently open (`RESULTS.md` §76, `OI39` row) | **FIX NOW** | **Next session, explicitly not scoped tonight** — needs a design decision, guardrail version bump, redeploy, `C1` cycle |
| `OI1` — temporary `$0.25` test notification | Fix, generated | Removal plan ready (`/tmp/oi1_removal.tfplan`), awaiting Marco's apply |
| `OI3` — S3 `etag` phantom diff on `codehook_deps_layer` | **ACCEPT** | Confirmed harmless (bucket versioning off, byte-identical re-upload); not worth a `source_hash` fix ahead of a change that touches this stack anyway |
| `OI5`/`D88` | Closed, re-closed | Narrow finding stays not-a-defect; the corrected scope claim is what produced `D121`, above |
| `OI4` — claim (b) | Closed | `RESULTS.md` §76 |
| `OI6`/`D89` — INPUT guardrail false-blocks "file" in an ordinary confirmation | **DEFER** | Phase 12 entry condition — guardrail-definition review pass, alongside `D99` and §10's `examples`-verification rule |
| `OI7`/`D90` part 1 — zero-context turn routing, Option 1 shipped and confirmed insufficient | **DEFER** | Phase 12 entry condition — triage decision itself is Marco's to make there, not pre-scoped |
| `OI8`/`D91` — staged-but-uncommitted work can ride into an unrelated commit | **ACCEPT** | No verified session-start hook point exists in `.claude/settings.json`; impact to date null, both instances |
| `OI9`/`D92` — eval harness overwrites its own baseline with no identity check | **DEFER** | Phase 13 scope item — costlier guard than `D98`'s lint, explicitly not proposed for immediate build |
| `OI10`/`D93` | Closed | Threshold re-derived and applied |
| `OI11`/`D94` — untracked `observability/` package deployed via 3 live builds | **Partially fixed** | Python package committed (`65c9e8d`). Residuals still untracked and **not yet bucketed**: `scripts/verify_{d87_scope,log_redaction,stage_b1_live_invoke}.py`, `tests/unit/test_{guardrail_metrics,log_redaction}.py`, `evals/baselines/...u9iIy.json` — flag this gap if it isn't picked up soon |
| `OI14`/`D97` — guardrail-version cross-stack coupling outage | Closed | Window `18:21:13Z`→`21:07:08Z`. Recurrence guard **still proposed, not built** — unscheduled |
| `OI15`/`D98` — `D89`×`D90` shared exposure tracker | **DEFER (auto)** | Closes automatically when both `D89` and `D90` part 1 close, no standalone home needed |
| `OI17`/`D99` — life-insurance scope-containment gap, inconclusive probe | **DEFER** | Phase 12 entry condition — same guardrail-review pass as `D89` |
| `OI18`/`D100` — continuation-turn exposure, MEASURE vs. ACCEPT undecided | **DEFER** | Phase 12 entry condition — decided there because deciding requires the probe itself |
| `OI19`/`D101` — cross-session coordination is an unrecorded trust surface | **DEFER** | Phase 12 entry condition — three named sub-questions, Marco's to decide together |
| `OI38`/`D120` — `git checkout <ref> -- <path>` overwrote uncommitted work twice, same mechanism | **DEFER** | Phase 12 entry condition — next candidate after `D98`'s lint |
| `CF8` — standing `make verify-*` gate over every ordinary intent's real fulfillment path | **DEFER** | Phase 12 entry condition, unchanged — currently 10/13 green, correctly not-green (3 known real failures) |

## Operating constraints

- **COST GATE** (`CLAUDE.md`) — no provisioning or billable resource without Marco typing
  `APPROVED: <phase name>`; standing approval for Bedrock on-demand inference, Phases 3–7, capped at `$5`
  total, logged per-run in `COSTS.md`. Provisioned resources are still gated individually regardless of that
  cap.
- **Deny-listed commands** (`.claude/settings.json`'s `permissions.deny`, exact list) — the agent cannot run
  these; Marco runs them himself and reports the output back: `terraform apply`/`destroy`/`import`/`state`/
  `force-unlock`/`taint`/`untaint`, `git push`, `aws connect associate-phone-number-contact-flow`/
  `disassociate-phone-number-contact-flow`/`release-phone-number`/`delete-instance`/`claim-phone-number`,
  `aws lexv2-runtime recognize-text`/`recognize-utterance`, `aws bedrock-runtime invoke-model`/`converse`.
  This session's own `terraform apply` attempt was blocked by this list, not by Marco or a stop condition —
  recorded in `PROJECT_STATE.md`'s `OI1`/`OI10` rows as it happened.
- **`PROJECT_ROOT` boundary** (`CLAUDE.md` "Scope rule") — `PROJECT_ROOT` is this project's own directory;
  the git root is its parent (`/Users/marco/K21/Real-world`). Being in the same git repository does not put
  a file in scope. Three known future instances (root `.gitignore`, done; root `.github/workflows/`, Phase
  10; root `README.md` project index, Phase 12) are each their own approval, not covered by monorepo
  convention.
- **A `stacks/main` redeploy means a `C1` re-verification cycle.** Standing rule, `PROJECT_STATE.md:6533`:
  any `src/` content change with a new `source_code_hash` requires a full `C1` harness re-run before
  "VERIFIED" can be claimed again — **measured, not estimated, this session: ~$0.10 (`$0.0977`), ~1m41s**
  (`RESULTS.md` line 7596). This is why `D121`'s fix is explicitly a fresh session's work, not tonight's: the
  guardrail change alone isn't the cost — the redeploy-triggered `C1` cycle is part of the same unit of work.

## Phase 12 and `CF8`

Phase 12 ("Documentation and demo," Phase status table row 12) has not started — `⬜ Not started`,
`PROJECT_STATE.md`. **`CF8`** (`PROJECT_STATE.md` `CF8` row) is its proposed **entry condition**, not an
exit criterion of Phase 12 itself: a permanent, named `make verify-*` gate exercising every ordinary
intent's real, deployed, slot-filled happy path, at minimum on every `stacks/main` deploy. Built, currently
**10/13 green** — the 3 failures are known, real, unrelated-to-`D87` defects (`D88`-shaped assertions since
fixed, `D89`, `D90` part 1), which is the correct state to enter Phase 12 scoping with, not a reason to
loosen the condition. Marco's own framing for why this is an entry condition and not softer: "filing
findably is not the same as filing effectively" — `CF7` sitting unscheduled since Phase 10 close is the
evidence that a proposed-but-unenforced check doesn't survive contact with the next phase.

## Seven working-tree-vs-repo instances today

Marco's own count, stated directly when the seventh (the untracked `infra/terraform/stacks/observability/`
stack, `PROJECT_STATE.md:63`) was found: "Seventh working-tree-vs-repo instance today and the largest." This
briefing can independently cite five distinct mechanisms behind that count, each already cross-referenced in
the ledger as part of the same family ("the working tree and the repository disagree, and something acted
on the repository's version without checking" — `OI38`'s own row):

1. **`D91`/`OI8`** — `git commit` acts on the whole staged index; unrelated staged content can ride into a
   commit alongside what was intended.
2. **`D94`/`OI11`** — `data.archive_file`'s `source_dir` zips the working tree, not `git` — untracked-but-
   present files silently entered three live Lambda deploys before detection.
3. **`D120`/`OI38`** — `git checkout <ref> -- <path>` run against an assumption about what a branch
   contains, not a check, silently overwrote uncommitted work twice (same mechanism both times).
4. **`D92`/`OI9`** — the eval harness unconditionally overwrites its own baseline JSON with no existing-file
   or build-identity check; not a `git` mismatch specifically, but the same "convention protected only by
   operator memory, no fail-loud mechanism" shape (`D92`'s own row: "same defect class as `D91`").
5. **The `infra/terraform/stacks/observability/` stack itself** — an entire 10-file, 795-line Terraform
   stack, deployed and live, simply never `git add`ed. No single command caused it; it was never staged,
   discovered only when the directory was checked as a whole.

**This briefing does not have first-hand citations for two more instances to reach seven** — Marco's count
may include occurrences from parallel terminal sessions this document's own sources don't cover. Treat "five
cited, seven counted" as the honest state of this section rather than stretching the cited list to seven by
under-verified inference — consistent with the discipline this whole document asks you to hold reports to.

## Suggested skills

- **`diagnosing-bugs`** — if the next session designs `D121`'s fix (a live repro already in hand, `RESULTS.md`
  §76) or reopens `D90` part 1 (a shipped fix already confirmed insufficient, needs a fresh hypothesis).
- No other skill is load-bearing for reviewing the current report set — this is a review task, not a build
  or diagnosis task.
