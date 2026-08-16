# Uncommitted-source audit — 2026-08-16

Written standalone rather than appended into `PROJECT_STATE.md`/`docs/RESULTS.md`, both of which were under
live, concurrent edit in a parallel session at the time this was produced (Marco working `D89` directly).
Fold a pointer into those files whenever convenient; this file is self-contained until then.

## Origin

Phase 11 criterion 6's negative control (`docs/handoffs`-adjacent work, `PROJECT_STATE.md` `OI11`/`D94`)
found that `main`'s committed `src/fnol_voice_agent/api/lex_codehook.py` imports a package
(`fnol_voice_agent.observability`) that was never committed. Fixed (`65c9e8d`). Marco's instruction on
receiving that finding: don't assume it's isolated — audit the full divergence between the working tree
(which has been the actual source of every `stacks/main` apply this session, via `lambda.tf`'s
`source_dir = "${local.repo_root}/src"`) and `main`'s committed tree, and report every file where they
disagree, with a severity call on each.

## Method

`git diff main --stat -- src tests scripts evals` (monorepo root), read alongside `git status
--porcelain --untracked-files=all`, scoped to this project's own directories. Excludes this session's own
deliberate, disclosed edits (the negative-control `lexicon.py` regression, this project's own doc commits).

## Findings, one row per file, ranked by severity

| File | Divergence | Shipped to deployed Lambda? | Severity | Status |
|---|---|---|---|---|
| `src/fnol_voice_agent/mcp/_paths.py` | Main had the **pre-`D87`-fix** version (`REPO_ROOT = parents[3]`, climbs to an assumed repo root). Working tree had the real fix (`PACKAGE_ROOT = parent.parent`, anchored on the file's own package-relative position) | **Yes — every apply this session** (`otOV3s1E...`, `8Ch4kDuL...`, `51JN903e...`) | **Severe.** `D87` was recorded CLOSED on deployed-runtime verification; that verification was never checked against the repository. Explains all 57 test failures + the `Delegate`≠`Close` failure on a clean-clone CI run | **Fixed, commit `0e72d86`, scoped alone.** Verified locally first: 58 previously-CI-failing tests now pass against this file |
| `tests/unit/test_coverage.py` | Own hardcoded `DATA_DIR` still pointed at the pre-move `data/synthetic/` path | No (tests aren't packaged) | Moderate — blocks any clean-clone CI run entirely, though the deployed artifact is unaffected | **Still stale on `main`.** Not fixed this pass — Marco scoped the commit to `_paths.py` alone |
| `tests/unit/test_identifiers.py` | Same as above | No | Moderate | Still stale |
| `tests/unit/test_models.py` | Same as above | No | Moderate | Still stale |
| `tests/unit/test_pii_redaction.py` | Same as above | No | Moderate | Still stale |
| `scripts/validate_synthetic_records.py` | Same `DATA_DIR` staleness, plus a docstring update naming `D87` | No (`scripts/` isn't under `source_dir = src/`) | Moderate — affects `make lint`'s corpus-consistency check locally/in CI, not the deployment | Still stale |
| `src/fnol_voice_agent/agents/nodes/guardrails_nodes.py` | Working tree wires `emit_guardrail_usage` (Stage B1's guardrail-usage-units emitter) into both the INPUT and OUTPUT guardrail node functions. Main's committed version has neither the import nor the two call sites | **Yes — the `51JN903e...` build** (Stage B1's own apply) | **Severe, same shape as the observability finding, different feature.** The deployed Lambda's guardrail-usage emission was confirmed live this session (a real `INPUT`-side `guardrail_usage` log line captured). `observability/guardrail_metrics.py` itself is now committed (`65c9e8d`) but is currently **orphaned on `main`** — nothing there calls it, so `main`'s own behavior does not match the verified deployed behavior | **Not fixed this pass.** Flagged, not committed — outside the `_paths.py`-alone scope given |
| `tests/unit/test_guardrails_nodes.py` | 56 new lines — the "7 new tests" for the emitter wiring above, referenced earlier this session as already built and passing | No | Moderate — these tests don't exist on `main` at all, so they've never run in any CI context | Still stale |
| `infra/terraform/stacks/observability/*` (9 files) | Entire Stage A Terraform stack (budget, SNS, CE-pull Lambda, dashboard), never committed | N/A — Terraform, not part of the codehook zip | Lower — confirmed via grep that no `stacks/main` `.tf` file references `stacks/observability`, so this is not a same-class "committed code depends on missing code" defect, just separately unshipped IaC | Untracked, unrelated to this defect class |
| `scripts/verify_{d87_scope,log_redaction,stage_b1_live_invoke}.py` (3 files) | Standalone diagnostic scripts used ad hoc this session | N/A | Lower — referenced only in code comments (`grep` confirmed), not imported, not wired into any `make verify-*` target | Untracked, no functional coupling found |
| `evals/baselines/composed_pipeline_deployed_k3_lineE.u9iIy.json` | The `D92`-related archived baseline | N/A (JSON data, not imported) | Lower — a record-keeping gap (the archive itself isn't in git), not a code defect | Untracked |
| `src/fnol_voice_agent/observability/{__init__,guardrail_metrics,log_redaction}.py` | Was untracked; shipped in all three applies | Yes | Was severe | **Fixed, commit `65c9e8d`** |

**Method's own limit, stated plainly**: this audit is a `git diff`/`git status` sweep against the two trees
that exist right now. It would not catch a divergence that existed earlier in the session and was already
resolved (overwritten by a later local edit) before this sweep ran, nor would it catch drift in files outside
`src`/`tests`/`scripts`/`evals` (e.g. `infra/terraform/stacks/main/*.tf` was not swept the same way — a
separate check, not run here, would be needed to rule out Terraform-side drift of the same shape).

## `D87`'s closure — amended, not reopened

**The defect is genuinely fixed where it runs.** `_paths.py`'s corrected arithmetic has been live in the
deployed Lambda since the `8Ch4kDuL...` apply, confirmed from the deployed runtime at the time (`RESULTS.md`
§31/§32) and again structurally consistent with every later build. That verification is not invalidated by
anything in this audit.

**What the closure record did not previously say, and should**: the fix was **never present in version
control until 2026-08-16** (commit `0e72d86`, this entry). Between the `8Ch4kDuL...` apply and this commit,
`main`'s own tree — what a fresh clone would build from — still had the broken pre-fix arithmetic. `D87`'s
CLOSED status should read: **fixed and verified in the deployed Lambda; the fix entered version control
separately and later, 2026-08-16, not at the time of the original fix/verify cycle.** `PROJECT_STATE.md`'s
`OI4`/`D87` row and the Phase 11 criteria table's row 4 both need this qualifier folded in — not done in this
file, since both live in `PROJECT_STATE.md`, currently under concurrent edit.

## The deploy implication, stated plainly

`lambda.tf`'s `data.archive_file.codehook` has `source_dir = "${local.repo_root}/src"` — it zips whatever is
on disk, not whatever is in git. Every `stacks/main` apply this session packaged `src/` from disk:

- **`otOV3s1EXv/sK7XCW+85SrWvqmSYJE/FkUC6+Gikk68=`** (Stage C redeploy) — carried the not-yet-committed
  `observability/log_redaction.py` (fixed 2026-08-16, `65c9e8d`).
- **`8Ch4kDuL7pjJ4YWeunXSZRJP/Wc+ZuxZ5ubfC8w/Th4=`** (the `D87` fix apply) — carried `observability/
  log_redaction.py` (as above) **and** the not-yet-committed `_paths.py` fix (fixed 2026-08-16, `0e72d86`).
- **`51JN903edLEVaSjP5zoEWQir4VLC+lQEVHA56b/5CUc=`** (Stage B1 + `D90` option B, current live) — carries
  both of the above **plus** `guardrails_nodes.py`'s emitter wiring, **still not committed** as of this
  entry (see table above).

**`C1` was re-verified against all three of these builds this session** (§25, §32-adjacent, §36 §7). Each of
those re-verifications remains valid as a statement about the deployed artifact's actual behavior — that is
what `C1` measures, and measuring real behavior against real deployed code is sound regardless of what git
has recorded. But **"build `X`" was not reproducible from the repository at any of the three points it was
verified this session** — a `git clone` + `terraform apply` at any of those moments would not have produced
the build that was actually tested. This is a gap in the *traceability* of `C1`'s verifications, not in
their *validity*, and the two should not be conflated: what `C1` measured happened; what a future person
starting from `main` alone could reproduce, at each of those three points, was something else.

## Finding B, resolved — a negative-control target only "Evaluation gate" catches

Both of `evals/report.py`'s Tier A GATEs (L1 escalation recall == 1.000, retrieval recall@5 >= 0.90) are
independently pinned by dedicated unit tests with hardcoded expected values
(`tests/unit/test_eval_harness.py::test_the_l1_gate_passes_after_the_stage_5_lexicon_fix`,
`::test_the_retrieval_gate_now_passes_at_exactly_its_threshold_and_why_that_is_not_a_clean_pass`) — any live
regression in either metric fails "Unit tests" first, structurally, regardless of what `_paths.py` or
anything else does. Confirmed by reading both tests, not assumed.

**Proposed instead: trip the "Baseline freshness" step** (`fnol-eval-gate.yml`'s step 7,
`evals.regression.baseline_is_stale`). `lexicon.py` is itself one of `BASELINE_SENSITIVE_PATHS`
(`evals/regression.py:146`) — a **comment-only** edit to `lexicon.py` (touching no keyword, no pattern, no
behavior) would leave every live-computed metric untouched (Unit tests pass, "Evaluation gate"'s live-vs-
committed-baseline comparison passes, since nothing measured moved) while still appearing in the PR's
changed-file list under a baseline-sensitive prefix, with no accompanying `evals/baselines/` update. This is
the one candidate step that **cannot** be replicated by a local unit test in principle, not just in this
suite's current state — `baseline_is_stale()` needs `github.event.pull_request.base.sha`, a value that only
exists inside a real `pull_request` CI event, unavailable to any offline `pytest` invocation. It is also a
real, deliberate mechanism this project built (`CF6`(a), baseline provenance/staleness), not an artificial
trip-wire.

**What it demonstrates and what it doesn't**: it demonstrates the "Baseline freshness" step blocking a merge
for a real reason (an undisclosed baseline-relevant change) on the remote — a different mechanism than
`evals.report --check-regression`'s live-metric comparison, but one of the four steps Marco named as an
acceptable target, and the only one of the four not already covered by this session's committed-source
fixes or by existing unit-test duplication.

**Marco's ruling, 2026-08-16, on this substitution**: accepted, and it is the correct choice, not a
concession — "it is a real gate step, past Unit tests, and it is what branch protection now guards. Forcing
the literal 'Evaluation gate' step means manufacturing a regression to satisfy a step name." Recorded
explicitly at criterion 6's closure (`PROJECT_STATE.md`, once that file is safe to edit) rather than left
implicit: the criterion's own written text says "Evaluation gate"; the demonstration used "Baseline
freshness" because Finding B showed the criterion's named class of regression is structurally caught by
`test_eval_harness.py` inside "Unit tests" first, on this repository, as it exists today. **What was
demonstrated and what was not, stated separately**: the branch-protection mechanism blocking a real CI
failure on the remote — demonstrated. The literal "Evaluation gate" step's own failure behavior, the step
that gives the workflow its name — **still never observed failing on GitHub.** Filed as its own open item
below (`OI13`), not folded into criterion 6's closure as if it were satisfied by the substitution.

## `D95`/`OI12` — the double `git checkout <branch> -- <path>` overwrite, filed same family as `D91`/`D94`

Two accidental overwrites this entry, same mechanism both times: `git checkout ci-negative-control-2026-08-16-v3
-- <paths>` was run against an **assumption** about what that branch contained (that it carried the `_paths.py`
fix, then later that it carried the five test-file fixes), not a **check** — in both cases the branch had
never actually had that content committed to it, so the command silently overwrote genuinely uncommitted
local work (the same fixes this whole audit is about) with the branch's own stale, committed content.

**Recovery worked both times, and that is luck, not process**: the full diffs happened to already be
captured earlier in the same conversation (from `git diff main -- <path>` calls run for unrelated reasons),
so reconstruction was possible and was verified afterward (58 tests, then 643 tests, passing). Had those
diffs not already been on hand, both fixes would have been silently lost a second time, in the same session
that exists to document the first time this class of loss happened (`D87`'s fix, originally).

**Same family as `D91`/`D94`, one level closer to the tool itself**: `D91` is uncommitted work getting swept
into an unrelated commit; `D94` is a tracked file importing an untracked one; this is a targeted git
operation overwriting uncommitted content because its source ref was assumed rather than verified to have
that content. All three are "the working tree and the repository disagree, and something acted on the
repository's version without checking."

**Guard proposed, not built** (per this project's own standing convention for this class of finding —
record and propose, don't fix silently mid-task): before any `git checkout <ref> -- <path>`, either (1)
check `git status --porcelain -- <path>` is non-empty and diff it against `<ref>:<path>` first, refusing
(or requiring explicit confirmation) if the working copy has uncommitted changes the ref doesn't already
contain, or (2) `git stash push -- <path>` before the checkout and `git stash pop` after, so an incorrect
assumption about the ref's content becomes a stash conflict to resolve rather than a silent loss. Which of
the two — or a session-level habit rather than a scripted guard — is Marco's call, not decided here.

## Phase 11 criterion 6 — CLOSED, both halves recorded

**Configuration** (§1 above): classic branch-protection rule on `main`, "Require status checks to pass
before merging" enabled, `eval-gate` selected as the required check; "Require a pull request before
merging" and "Require branches to be up to date" both deliberately left off. `MANUAL-STEPS.md` item 5 marked
Done.

**Negative control, demonstrated 2026-08-16, run `31971816508`** (`ci-negative-control-2026-08-16-v4`, PR
#4, closed and branch deleted after capture): a comment-only addition to `lexicon.py` — a
`BASELINE_SENSITIVE_PATHS` entry, no accompanying `evals/baselines/` update — pushed to a branch and opened
as a PR against `main`. Result:

- `Unit tests`: **success** (664/664, on the now-fixed base).
- `Evaluation gate (Tier A + regression vs committed baseline)`: **success** — no live metric moved.
- `Baseline freshness`: **failure** — `BASELINE STALE: These changed without any update to
  evals/baselines/: ['src/fnol_voice_agent/agents/lexicon.py']. They can move every model-dependent number
  in the report, so the committed baseline no longer describes the system it claims to. Re-run make eval
  and commit the new baseline, or say in the PR why the numbers cannot have moved.`
- Everything downstream of the failing step: skipped, as designed.
- PR #4: `mergeStateStatus: BLOCKED`, required check `eval-gate`: `FAILURE`.

**The substitution, stated explicitly, per Marco's ruling** (recorded in full above, at the point Finding B
was resolved): criterion 6's own written text names "Evaluation gate" as the step under test. What was
demonstrated on the remote is "Baseline freshness" failing for a real reason and correctly blocking a merge
— accepted as the correct substitute, not a shortfall, because Finding B showed the criterion's implied
regression class (a live Tier A metric moving) is structurally caught by `test_eval_harness.py` inside
"Unit tests" first, on this repository as it exists today, before "Evaluation gate" is ever reached. That
is real information about this CI pipeline's actual failure-detection order, not a workaround chosen to
dodge a harder case.

**What remains genuinely undemonstrated, filed as `OI13`**: the literal `Evaluation gate` step — the one
that gives the eval-gate workflow its name — has **never been observed failing on GitHub**, this session or
before it. Every real regression this project has caught in CI so far (this entry's `Baseline freshness`
demonstration, and structurally, any future live-metric regression) has been shown to be caught by "Unit
tests" instead, given the current test suite's duplication of both Tier A GATEs as pinned unit-test
assertions. Whether "Evaluation gate" can ever be the first-observed failing step for *any* real regression
under this repository's current test composition — or whether that duplication should be loosened so the
named step can do the job its name implies — is an open question, not decided or attempted here.

**Criterion 6: CLOSED.** Both the configuration and a real, correctly-targeted negative control are done and
recorded, with the one honest gap (referred to below as `OI13[this file]`, pending renumbering — see next
section) named rather than folded into the closure silently.

## Numbering collision — `D95`/`OI12`/`OI13` assigned twice, by two parallel sessions

Neither this file's numbers nor the other session's numbers have been committed to `PROJECT_STATE.md`'s
ledger as of this entry — confirmed via `git status --short PROJECT_STATE.md docs/RESULTS.md`, both still
show `M` (working-tree modifications, not commits). This is a live collision on a shared, uncommitted
draft, not a merge conflict between two already-recorded histories.

### 1. Every identifier this file (this session) assigned

| ID as written in this file | Subject |
|---|---|
| `D94`/`OI11` | `main`'s committed `lex_codehook.py` imports `fnol_voice_agent.observability`, never committed — the untracked-package gap that broke the negative control's first run |
| `D95`/`OI12` | The double `git checkout <branch> -- <path>` overwrite hazard — two accidental losses of uncommitted local fixes this session, both recovered from diffs captured earlier in this same conversation |
| `OI13` (no paired `D` number) | The literal "Evaluation gate" CI step has never been observed failing on GitHub, this session or before — criterion 6's demonstration used "Baseline freshness" instead, per Finding B |

`D94`/`OI11` is not in collision — cross-referenced correctly and consistently by the other session's own
`RESULTS.md` entries (e.g. "carrying Terminal 1's `D87`/`D94` commits"). The collision is confined to
`D95`/`OI12` and `OI13`.

### 2. Highest identifier actually committed to `PROJECT_STATE.md`'s ledger

Read via `git show HEAD:PROJECT_STATE.md` (this session's own last commit, `288ed92`) — the true committed
state, not the shared working tree's live draft: **`OI11`/`D94`** is the highest row actually in a commit.
Rows `OI12` and `OI13` currently visible in the working tree (both sessions' versions) are uncommitted.

### 3. What the other session assigned to the same numbers (read from the shared working tree, not acted on)

| ID as the other session wrote it | Subject | Where it lives |
|---|---|---|
| `D95`/`OI12` | A live production outage: `stacks/main`'s deployed Lambda requests guardrail version `"3"`, which the guardrails stack's own `D89`-driven `v4` replace destroyed — `aws_bedrock_guardrail_version.fnol` is a single replace-on-change resource with no coupling back to `stacks/main`'s pinned version. 10/13 gate events failing, window `2026-08-16T18:21:13Z` onward. Marked **URGENT**, exposure assessed as real-world-zero (no real caller has ever used this DID) but the coupling defect itself is real and will recur | `docs/RESULTS.md` §45 §4, §46; `PROJECT_STATE.md` `OI12` row |
| `D96`/`OI13` | `D89`/`D90` part 1 compounding on single-word confirmation turns (`FileAutoClaim`'s `confirm_file_claim`, `UpdateContactInfo`'s `confirm_update_contact_info`) — both defects share the same low-context exposure surface, cross-referenced into both original entries, not a new independent mechanism | `PROJECT_STATE.md` `OI13` row |

### 4. Proposed reconciliation — this file's items renumber, not the other session's

**Rationale, not a coin flip.** The other session's `D95`/`OI12` is a live, urgent, currently-unfixed
production-outage finding, already written across two `RESULTS.md` sections (§45, §46) with self-checks,
Report blocks, and cross-references into `OI6`/`OI7` — renumbering it now would mean editing a
substantially larger, higher-stakes, already-cross-referenced body of text, for a finding whose urgency
argues for stability, not disruption. This file's own `D95`/`OI12`/`OI13` are confined to one document
(this one), self-contained, and were never committed to `PROJECT_STATE.md` at all — the cheaper and safer
side to move.

**Proposed new numbers, this file's items only:**

| Old (this file) | New (proposed) | Subject |
|---|---|---|
| `D95`/`OI12` | **`D97`/`OI14`** | The double `git checkout <branch> -- <path>` overwrite hazard |
| `OI13` (unpaired) | **`OI15`** | The literal "Evaluation gate" step never observed failing on GitHub |

`D96` is the other session's highest committed-in-prose `D` number; `D97` is the next free one. `OI13` is
the other session's highest `OI`; `OI14`/`OI15` are the next two free ones. Neither collides with anything
either session has written, as of this entry.

**Records needing the update, once Marco confirms:**
- This file: every internal reference to `D95`/`OI12` (the checkout hazard) → `D97`/`OI14`; every reference
  to the unpaired `OI13` (Evaluation gate) → `OI15`.
- This file's own git history (commits `60a65a5`, `288ed92`) used the old numbers in their commit
  messages — commit messages are immutable without a history rewrite, which is a worse trade than a stale
  number in a message (same precedent as `D91`'s own resolution: "a history rewrite to fix a
  message-accuracy issue is a worse trade than the accuracy issue itself"). Not proposed here.
- `PROJECT_STATE.md`'s eventual `OI14`/`OI15` rows (once this file is folded in) carry the new numbers from
  the start — no renumbering needed there, since this file's content has never been committed to that
  ledger yet.

### 5. The underlying hazard, filed as its own item — proposed `D98`/`OI16`, pending confirmation

**Parallel sessions appending to a shared, uncommitted ledger will collide on sequential identifiers, and
nothing today prevents it.** Both this session and the other picked "the next number after the last one I
saw" independently, at different times, against the same shared working-tree file, with no coordination
mechanism between them. The collision was caught only because Marco was reading both threads and noticed
the reused numbers — not because any check in the repository, workflow, or convention would have caught it
otherwise. Same shape as `D91`/`D94`/`D95`(this file's)/`D97`(proposed): the working state and the recorded
state can disagree, and nothing structural stops it.

**Stated plainly, per Marco's instruction**: `PROJECT_STATE.md` and `docs/RESULTS.md` were themselves
uncommitted working-tree drafts — `git status --short` shows both `M`, not clean — at the exact moment
**three sessions** were appending rows to them. That is not a separate hazard from `D94`/`D95`(this
file's own, pre-renumber)/`D97`(proposed renumber) — it is the *same* working-tree-vs-repo disagreement
those entries describe, showing up one layer up: `D94` was a tracked file importing an untracked one;
`D95`/`D97` was a git operation acting on an assumption about a ref's committed content instead of a
check; here, the artifact multiple sessions are reading and appending to *as if it were the shared source
of truth* was never actually committed at any point during the collision, so "read the ledger, take the
next number" was reading a draft, not a record. The record-keeping layer inherited the same disease as the
source layer: uncommitted state was treated as if it were authoritative, by everyone, independently.

**Guard proposed, not built** (per this project's own standing convention — record and propose, don't fix
silently mid-task), two shapes, Marco's call which:

1. **A session claims a block of numbers up front.** Before starting substantive filing work, a session
   reads the ledger, announces (in its own first record of the session, or verbally to Marco if working
   live) "claiming `D95`–`D99`/`OI12`–`OI16`," and uses only that block. Cheap, no tooling, but relies on
   every session actually doing it — the same "protected only by remembering" shape `D91`/`D92`'s own
   guards were proposed against, one level up.
2. **Read the ledger immediately before assigning, every time, not once per session.** Rather than
   claiming a block up front, re-read `PROJECT_STATE.md`'s current highest `D`/`OI` number right before
   writing a new row, not from memory of an earlier read in the same session. Cheaper to describe, harder
   to enforce without tooling (still relies on remembering to re-read), and does not fully prevent a race
   if two sessions read-then-write in close succession — only shrinks the window `D91`'s own guard was
   about, doesn't close it.

Neither is a mechanism that fails loud when skipped, which is the same gap `D91`'s and `D92`'s own proposed
guards were named for. A structural fix (e.g. a numbering scheme that doesn't require sequential
coordination at all — UUIDs, or a per-session prefix like `D-T1-1`/`D-T2-1`) would close the race entirely
but breaks this project's existing convention of a single flat sequence read at a glance — a larger change
than this entry proposes unilaterally deciding. Marco's call.

## Fail-loud controls vs. conventions dressed as controls

Four guards are on the table right now, across three entries: `D91`'s session-start status check, `D92`'s
baseline-archive step, `D97`'s (formerly `D95`) check-before-checkout, `D98`'s number-block claim. All four
share a property worth naming directly: **none of them fails loud when skipped.** Each is a step a session
is supposed to remember to take, with no mechanism that notices the step was skipped and stops anything.
Skipping any of the four produces silence, not an error — which is exactly the failure mode `D91`, `D95`
(original), and this entry's own record-keeping-layer note all independently ran into today.

**Compare against the two guards this project already built that do fail loud:**

- **The pre-commit `PROJECT_ROOT` scope hook** (`scripts/git-hooks/pre-commit` → `scripts/
  check_project_root_scope.py`, installed via `make install-hooks`). Every `git commit` invocation in this
  workspace runs it unconditionally — not "a step a session should remember," a step `git` itself executes
  before the commit is allowed to complete. A staged path outside `PROJECT_ROOT` (absent an `ALLOWLIST`
  entry with a recorded, absolute-path approval) makes the hook exit non-zero, and the commit does not
  happen. Demonstrated red at `e0452cb`'s own investigation (`.serena/` swept in outside `PROJECT_ROOT`),
  per that script's own module docstring.
- **`.claude/settings.json`'s `permissions.deny` list**, this project's own copy (`AWS-Insurance-FNOL-
  Voice-Agentic-AI/.claude/settings.json`), which denies `Bash(git push:*)`, every destructive/mutating
  `terraform` subcommand, and several billable/high-risk `aws` calls outright. This is enforced by the
  harness itself, before the shell ever sees the command — not a check the agent runs and might skip, a
  gate the agent's own tool call cannot get past. It is *why* every `git push` this session ran as `!
  <command>` from Marco directly, not as a tool call from me.

**What actually distinguishes these two from the four pending proposals** is not rigor of design — `D97`'s
check-before-checkout proposal is just as precisely specified as the `PROJECT_ROOT` hook's check — it's
*where the check is wired in*. The two built guards are invoked by something other than the actor's own
discipline: `git commit` calls the hook automatically; the harness's permission layer intercepts the tool
call automatically. Every one of the four pending proposals, as currently written, is invoked by the same
discipline that already failed once today — "remember to run the check before you act" is exactly the
sentence that was true of the checkout hazard's own missing check, and writing a *new* step that also
depends on remembering does not change the failure mode, only its label.

**Which of the four can actually be converted, and which can't, honestly assessed:**

1. **`D97` (checkout hazard) — convertible.** A `git checkout <ref> -- <path>` cannot be intercepted by a
   native git hook (git has no pre-checkout hook for path-scoped checkouts), but it *can* be routed through
   a wrapper — a `bin/`-installed script or shell function that requires path-scoped checkouts to go through
   it, and that runs the diff-and-refuse check from this entry's original proposal before ever invoking real
   `git checkout`. That wrapper is bypassable by calling the real `git` binary directly, exactly as the
   `PROJECT_ROOT` hook is bypassable with `--no-verify` — but this project already accepted that exact
   bypass shape as good enough to call a control, once, for the scope hook. Same standard applied here says
   this one clears the bar. Not built this pass; proposed as the next candidate.
2. **`D98` (numbering collision) — convertible, and cheap.** A duplicate-identifier lint — scan
   `PROJECT_STATE.md` and `docs/RESULTS.md` for every `D\d+`/`OI\d+` token and fail if any appears as more
   than one row header — is mechanical, requires no judgment call, and can be wired into the *same*
   pre-commit hook that already runs `check_project_root_scope.py`, or as its own `make verify-*` target.
   It would have caught today's exact collision, at the moment either session tried to commit the colliding
   row, not after the fact via Marco reading two threads. This is the strongest candidate of the four —
   recommend building it before the next multi-session week, not just recording it as accepted risk.
3. **`D92` (baseline archive) — convertible, more expensive.** The check would need to detect that
   `evals/baselines/composed_pipeline_deployed_k3_lineE.json` changed in a commit and require the
   previous blob's content to also exist under an archive filename in the same commit — buildable (it is
   the same shape as the already-real `baseline_is_stale` mechanism, one step earlier in the lifecycle), but
   more machinery than 1 or 2. Worth it eventually, not proposed for immediate build.
4. **`D91` (session-start status check) — not obviously convertible.** This step happens before any single
   tool call the harness can gate — it is about what a session reads or does at its own start, not a `git`
   or `terraform` invocation with a natural interception point. Claude Code's hook system is understood to
   expose a session-start-shaped event in general, but whether it can carry a check strong enough to block
   a session's first substantive write has not been verified in this project's own `.claude/settings.json`
   (only a `PreToolUse` hook is configured here, for `rtk`). Recording this honestly rather than assuming a
   mechanism exists: **`D91`'s guard should be filed as an accepted-risk convention, not implied to be a
   pending control**, unless and until a real session-start hook point is confirmed and wired up.

**Recommendation, not a decision**: build `D98`'s duplicate-identifier lint and `D97`'s checkout wrapper —
both fit the project's existing hook pattern exactly. Record `D91`'s session-start check as an
accepted-risk convention explicitly, in whatever record eventually carries it into `PROJECT_STATE.md`,
rather than letting it sit next to `D97`/`D98`/`D92` looking like the same kind of thing — `D92` is
convertible too (item 3 above), just costlier, so it is not in the same bucket as `D91`. Marco's call on
sequencing and on whether `D91` gets a real hook point investigated before being downgraded to convention.

## `D98`'s duplicate-identifier lint — built, per Marco's instruction 2026-08-16

**Files**: `scripts/check_duplicate_identifiers.py` (new), `tests/unit/test_check_duplicate_identifiers.py`
(new, 9 tests), `scripts/git-hooks/pre-commit` (extended, second check appended — `set -e` still exits on
the first failure, only the last check keeps the `exec`), `Makefile` (`verify-duplicate-identifiers`
target + `.PHONY` entry, same "STAGED not tree, manual escape hatch for the hook" scope comment as
`verify-project-root-scope`). `make install-hooks` re-run — the installed `.git/hooks/pre-commit` now
runs both checks.

**Design question 1 — section numbers included, not just `D`/`OI`.** Same regex-scan mechanism, no real
added cost, per the framing this was asked under. Scope: `docs/RESULTS.md`'s top-level `## <n>.`/
`## <n>.<n>...` headings only — `PROJECT_STATE.md` doesn't use numbered section headings for its own
structure, only the `D`/`OI` row scheme, so there was nothing parallel to check there.

**Design question 2 — a pre-existing duplicate does not block every future commit.** `GRANDFATHERED_OI`/
`GRANDFATHERED_D`/`GRANDFATHERED_SECTIONS`, three empty `frozenset`s today, same shape and same discipline
as `check_project_root_scope.py`'s own `ALLOWLIST` — add an entry only alongside the specific, recorded
reason a collision was left unresolved, never in advance. A sweep at build time found **no actual
pre-existing duplicate** in either file (confirmed both by the regex directly and by the two "shipped
ledger is clean" pytest baselines below), so the list ships empty rather than seeded speculatively. Stated
plainly in the docstring: an entry silences one specific identifier, not a permanent exemption — a THIRD
row later claiming an already-grandfathered number still fails, because duplicate-ness is recomputed from
content every run, not cached as a count.

**Definition site, not every mention** — the actual design problem this check exists to solve. A raw
`grep -oE 'D[0-9]+'` sweep run earlier in this session's own investigation returned dozens of hits per
identifier (prose cross-references: "`D91`'s hazard realized", "cross-referenced into `OI6`") against
exactly one row that legitimately owns each. The checker only counts a `D` number when it headlines an
`OI` row (`| OI<n> | **\`D<n>\`` immediately after) and only counts an `OI` number at the row it starts —
never a bare mention. `test_cross_reference_mentions_do_not_count_as_duplicate_definitions` encodes this
directly: a fixture where `D87` is mentioned 6 times but legitimately headlines only once passes clean.

**Red before green, demonstrated without touching `PROJECT_STATE.md`/`RESULTS.md`**, per the explicit
instruction not to touch either file this pass. Same discipline `tests/unit/test_check_flows.py` already
uses for the shipped contact flow — "the shipped ledger is the fixture, and every test mutates **a copy**
of it into one specific collision," never the file on disk:

- 9 pytest cases, all against real file content read once and mutated in memory:
  `test_the_shipped_project_state_ledger_has_no_duplicate_oi_or_d_identifiers` and
  `test_the_shipped_results_doc_has_no_duplicate_section_numbers` (green, against the real, current,
  unmodified files — proves the check doesn't just pass on synthetic fixtures);
  `test_duplicate_oi_row_number_is_caught`, `test_duplicate_d_headline_across_two_different_oi_rows_is_caught`,
  `test_duplicate_results_section_number_is_caught` (red, each constructs a real collision by duplicating
  an actual row/heading from the real content, in memory only); `test_project_state_with_zero_oi_rows...`
  and `test_results_with_zero_section_headings...` (red, "found nothing" case); the two definition-vs-mention
  tests above. `.venv/bin/python -m pytest tests/unit/test_check_duplicate_identifiers.py -v` — 9/9 passed.
  Full suite re-run after: 673/673 passed (664 before this entry + 9 new).
- A second, CLI-shaped demonstration, run directly against the real `PROJECT_STATE.md` content
  (read, mutated in memory, never written back), exercising the same `check_project_state` the installed
  hook calls:
  ```
  --- RED: real content + one injected D87 duplicate (never written to disk) ---
   - DUPLICATE D87: headlines more than one Open Items row, on PROJECT_STATE.md line(s) [750, 7689].
  exit code would be: 1

  --- GREEN: real, untouched content ---
  violations: []
  exit code would be: 0
  ```
- `make verify-duplicate-identifiers` run for real against the actual git index (no mutation at all):
  `check-duplicate-identifiers: ok — no duplicate OI/D identifiers, no duplicate RESULTS.md section
  numbers` — exit 0, real git plumbing, real current content.

**Why the demonstration took this shape rather than a live commit against the tracked files**: Marco's
instruction this turn was explicit — do not touch `PROJECT_STATE.md`/`RESULTS.md`, still under live edit
by two other sessions. Injecting a real duplicate into either file, even temporarily, to stage-then-revert
it would itself be a write to a file under someone else's live edit, the exact category the instruction
excludes. The pytest-plus-direct-CLI demonstration above is the same logical proof (a real collision built
from real content, shown red; real content, shown green) without ever landing a byte on either tracked
file — this is a substitution of *mechanism*, not of *rigor*, stated so a later reader doesn't have to
guess whether the standard was actually met.

**`D91`, `D97`, `D92` — status recorded explicitly, per Marco's instruction, so none of the three is left
looking like a pending control it isn't:**

| Guard | Status | Why |
|---|---|---|
| `D98` (this entry) | **BUILT** | Fits the existing pre-commit-hook pattern directly; demonstrated red/green above |
| `D97` (checkout hazard) | **Assessed convertible, not built** | Needs a `git checkout` wrapper (no native git hook exists for path-scoped checkouts) — same bypass profile as the `PROJECT_ROOT` hook, which this project already accepted as good enough once. Not built this pass; next candidate |
| `D92` (baseline archive) | **Assessed convertible, not built** | Needs a same-commit check that a superseded baseline blob is archived before being overwritten — same shape as the already-real `baseline_is_stale` mechanism, one lifecycle step earlier, more machinery than `D97`/`D98`. Not proposed for immediate build |
| `D91` (session-start check) | **ACCEPTED-RISK CONVENTION, not a pending control** | No verified interception point exists in this project's own `.claude/settings.json` — only a `PreToolUse` hook (for `rtk`) is configured; no session-start-shaped hook has been confirmed wired here. Recorded as convention explicitly rather than left implying a control is coming. Reclassify to convertible only once a real hook point is confirmed |

**A fresh collision, found while confirming the "no pre-existing duplicate" premise above — not
resolved, surfaced instead.** `PROJECT_STATE.md`'s live working tree now shows `OI14`/`D97` and
`OI15`/`D98` already claimed by the *other* session, for entirely different content than this file's own
use of those numbers:

- `OI14`/`D97` (other session) = the guardrail-version production outage — the same finding this audit's
  earlier "Numbering collision" section recorded as their `D95`/`OI12`.
- `OI15`/`D98` (other session) = the `D89`/`D90` confirmation-turn compounding — recorded earlier in this
  audit as their `D96`/`OI13`.

**This directly collides with the renumbering Marco approved for this session at the start of this
turn** ("Renumber yours: `D95`/`OI12` -> `D97`/`OI14`, unpaired `OI13` -> `OI15`. File the parallel-session
collision hazard as `D98`/`OI16`.") — the other session moved to claim `D97`, `D98`, and `D99` (plus
`OI14`/`OI15`/`OI17`) independently, in the time between that approval and this entry. No duplicate exists
yet — each number still appears exactly once in the live table — but this file's own internal labels
(`D97` for the checkout hazard, `D98` for this numbering-collision hazard, used throughout the two
sections above) are no longer safe to fold into `PROJECT_STATE.md` under those numbers without a fresh
reconciliation. Not renumbered here, per the standing instruction not to renumber unilaterally — flagged
instead, and it is itself a live instance of exactly the hazard `D98`'s own write-up describes: a number
claimed against a reading of the ledger that was already stale by the time it was used. This needs a new,
short reconciliation pass, against the ledger's state *at the time of that pass*, not against this
entry's own now-stale approval.
