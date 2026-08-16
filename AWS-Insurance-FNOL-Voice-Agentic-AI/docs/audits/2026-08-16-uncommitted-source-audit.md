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
