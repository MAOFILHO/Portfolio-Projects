# Runbook — `C14` warm-path latency exceedance

`C14`: end-to-end voice-turn latency, Lex STT completion → Polly audio stream start, budget 1,800ms p95
(`CLAUDE.md`, Voice turn-latency budget). This is criterion 5's first half (`PROJECT_STATE.md`:6264 —
"incident response for `C14`'s measured warm-path exceedance and a guardrail false-positive spike"; the
guardrail-spike half is a separate document, not built here).

**Canonical phrasing — use verbatim, every time this project's own `C14` figure is cited:**

> warm-path p95 1,819ms, measured on a sample excluding cold starts; true p95 over real traffic mix is
> ≥1,819ms, distance to the 1,800ms target unmeasured

(`docs/RESULTS.md`:4493–4494, §12.10 — the section that retired the shorthand this phrasing replaces.)

**What's banned is narrower than it might read.** The retired shorthand — "19ms," used as a stand-in for
`C14`'s own claim, e.g. "`C14` fails by 19ms" — is banned in that role: as a substitute for the phrasing
above. It is not banned as three characters that may never appear in this document; §6 discusses the
retired phrasing by name where the history is being described. It's protected here because that shorthand
is exactly how this got wrong once already: "19ms" is real arithmetic on a sample that structurally excludes
ASR, TTS, and telephony, but stated bare it reads as a specific, known overage rather than a floor on an
unmeasured one — a scoped claim compressed into a wrong one. See §6 for the full account.

---

## 1. What this runbook is for, and what it is not

`C14` is not a hypothetical future incident. It is already on record as **measured-failing**, with a
**decision** on file — accept-and-carry-forward — not an open, undecided problem
(`PROJECT_STATE.md` open item `H`, line 4184; `docs/RESULTS.md` §11.22, ~lines 3935–4000). This runbook is
for an operator who needs to (a) re-confirm or refresh the latency signal, or (b) triage a fresh
observation that latency looks worse than the recorded figure. It is **not** an automated-alert response
guide, because no automated alert exists — see §3, and see §2 for how operators actually arrive here instead.

If you are here because a real caller complained about a slow turn: no real caller has ever reached this
system (zero inbound calls to the live DID, confirmed as of the last figure recorded here — re-check
`CLAUDE.md`'s verified-environment-facts table before assuming that is still true). Treat that report as
the trigger to re-verify the "no real caller yet" premise itself before anything else.

---

## 2. How you get here — there is no automatic trigger, so arrival is the first thing to diagnose

This is the runbook's activation problem, not a footnote: check which of these paths actually brought you
here before starting §4, because the first step differs by path and one of them isn't a `C14` signal at all.

- **A `make verify-lambda-execution` failure.** Checked directly (`scripts/verify_lambda_execution.py`):
  the script contains zero references to `Duration`, timing, or elapsed time — it asserts `FunctionError`
  absence and payload shape only (§5 below). **A failure here is not a `C14` signal** and this document is
  probably the wrong runbook — go to §5 first, which exists precisely to stop "Lambda failed" from being
  read as "Lambda is slow." Only come back to this document if §5's own finding turns out to implicate
  timing, which it is not built to detect.
- **Someone reads the operational dashboard.** The "Codehook Lambda -- Duration" panel (§3) is the one
  mechanism in this project that a human can look at and notice a high p95/Maximum line. This is the path
  this document was actually written for — first step is §4, to take a real reading and see what that panel
  number is (and, per §4's own warning, is not) measuring.
- **A customer report.** Per §1, no real caller has ever reached this system — zero inbound calls to the
  live DID as of the last figure recorded here. A customer report is therefore either about a different
  system, or evidence that the "no real caller yet" premise itself has gone stale; re-verify that premise
  (§1) before treating it as a `C14` observation at all.
- **An internal report** ("that turn felt slow" from someone running the simulator or eval harness).
  Legitimate, but still just a subjective flag until a real reading is taken — first step is §4, the same as
  the dashboard path.
- **Nothing — and for two independent reasons, not one.** First, no CloudWatch alarm exists to page or
  email anyone: zero `aws_cloudwatch_metric_alarm` resources in this project (§3). Second, checked directly
  against the eval-gate CI workflow
  (`/Users/marco/K21/Real-world/.github/workflows/aws-insurance-fnol-voice-agentic-ai-eval-gate.yml`): it
  contains no reference to `Duration`, `latency`, `1800`, or `C14` — a green or red run says nothing about
  this criterion either. An operator who expects "CI would have caught it" or "an alarm would have paged
  someone" is wrong on both counts; arrival here is always manual.

---

## 3. Detection — there is no automated alarm for this

Checked directly against `infra/terraform` before writing this: **zero `aws_cloudwatch_metric_alarm`
resources exist anywhere in this project.** The only alarm that exists at all is the budget alarm
(`aws_budgets_budget.project`, `infra/terraform/stacks/observability/budget.tf:15`, criterion 1) — it
watches spend, not latency, and cannot fire on this condition. **There is no mechanism that pages, emails,
or otherwise notifies anyone when Lambda duration or any latency figure crosses a threshold.** If a
mechanism like that should exist, it doesn't yet — say so, don't describe one as if it does.

The one thing that does exist is a **dashboard panel**, which requires a human to look at it:

- **"Codehook Lambda -- Duration"** panel, `infra/terraform/stacks/observability/dashboard.tf:104-121` —
  native `AWS/Lambda`/`Duration` metric, p50/p95/Maximum series, 5-minute period.
- Dashboard resource `aws_cloudwatch_dashboard.operational`, name `fnol-voice-agent-operational`
  (`infra/terraform/stacks/observability/dashboard.tf:83`, output
  `operational_dashboard_name` at `infra/terraform/stacks/observability/outputs.tf:21-23`). Read the name
  live via `terraform -chdir=infra/terraform/stacks/observability output operational_dashboard_name` rather
  than hardcoding it.

**What does not exist, stated plainly rather than described as if built:**

- **No per-turn sub-component latency breakdown** (router vs. guardrail vs. generation vs. checkpointer).
  The dashboard's own file comments name this directly: "**B2 turn-latency, scoped jointly with Stage D's
  `C14` signal, not built**" (`dashboard.tf:53-59`) and, on the dashboard's own in-page text widget,
  "**Turn-latency sub-components (criterion 3's fourth category) are Stage B2, not built here**"
  (`dashboard.tf:189-191`). `PROJECT_STATE.md`'s own re-open trigger list for item `H` (line 4184) names
  "Tier A instrumentation" as **not yet built** either — the closest thing to a real per-turn breakdown is
  the one-time, non-live analysis in `docs/RESULTS.md` §11.15/§11.16.
- **No structured per-turn timing log.** Checked directly: `src/fnol_voice_agent/api/lex_codehook.py` has
  exactly three logging calls (`logger.info` at lines 507 and 566, `logger.exception` at line 687), none of
  them timing-related. There is nothing to run a CloudWatch Logs Insights query against for this, unlike
  the guardrail-usage widget the operational dashboard does have.

---

## 4. Manual latency read — the one mechanism that exists

Two options, both manual, both point-in-time:

1. **Look at the dashboard panel** (§3) for a rolling view.
2. **A one-off `GetMetricStatistics` read**, the same method and metric criterion 8a used to produce its
   own number (`docs/RESULTS.md` §74, lines 10021-10032):

   ```bash
   FN=$(terraform -chdir=infra/terraform/stacks/main output -raw codehook_function_name)
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda --metric-name Duration \
     --dimensions Name=FunctionName,Value="$FN" \
     --start-time <window-start-ISO8601> --end-time <window-end-ISO8601> \
     --period <seconds-spanning-the-whole-window> \
     --statistics Minimum Average Maximum \
     --extended-statistics p50 p95 p99 \
     --region us-west-2
   ```

   Use a single period spanning the entire window (as `RESULTS.md` §74 did) so CloudWatch computes one
   aggregate percentile across every datapoint, not a per-bucket average of percentiles — a per-bucket
   average is a different, less meaningful number. Read the function name live via `terraform output`
   (pattern in `scripts/verify_lambda_execution.py:200-207`, `terraform_outputs()`) — it derives from
   `local.name_prefix = "fnol"` (`infra/terraform/stacks/main/main.tf:138`) plus a fixed suffix
   (`infra/terraform/stacks/main/lambda.tf:270`), not something to hardcode.

**Read the result carefully — this is NOT a `C14` measurement.** `AWS/Lambda`/`Duration` on the codehook
function is Lambda invocation time only: no Lex STT leg, no Polly TTS leg, no telephony wire or playout
time. Criterion 8a is explicit that its own number "**is not, and must not be read as, a measurement of the
1,800ms voice-turn budget**" (`docs/RESULTS.md`:10007-10009) and reports "no comparison to the 1,800ms
budget attempted or implied" (`docs/RESULTS.md`:10043). **A fresh read from this same query is a different
measurement than `C14`, not an update or supersession of it — report it labeled as what it is** (e.g.
"Lambda-invocation p95," per criterion 8a's own precedent), never folded into or presented as a new `C14`
figure.

For reference, the last recorded read of this metric (criterion 8a, closed 2026-08-16, `docs/RESULTS.md`
§74, 121 samples over the then-current build): p50 841.25ms, **p95 1,651.06ms**, p99 12,279.58ms, Maximum
12,707.69ms. That number is now stale (it is scoped to a specific `CodeSha256` and a specific ~2.5h window)
— treat it as a historical example of the method, not a current reading.

---

## 5. If you suspect the Lambda itself is broken, not merely slow

Distinguish "slow" from "broken" before doing anything else — they call for different responses.
`make verify-lambda-execution` (`Makefile:186`, runs `scripts/verify_lambda_execution.py`) is the existing
permanent gate: 13 real `lambda:Invoke` calls against real events, each checked for a real `FunctionError`
field and a well-formed payload — not a bare `StatusCode: 200`, which the script's own docstring notes is
returned identically for both a normal response and an unhandled exception
(`scripts/verify_lambda_execution.py:12-23`). If this fails, you have a correctness regression (the
`D80`-shaped failure mode that check was built for), which is a different problem from `C14`'s latency
exceedance — do not conflate the two, and do not treat a latency investigation as covering this.

Real cost: small and estimated live by the script itself before it calls anything
(`scripts/verify_lambda_execution.py:690-712`) — a few thousandths of a dollar at this event count,
consistent with how this check has been run throughout Phase 11.

**A high `p99`/`Maximum` next to a materially lower `p95` is expected, not a new finding on its own.**
Criterion 8a's own read (§4 above) found `p99`/`Maximum` roughly 7–8x the `p95`, attributed to real
cold-start `_get_graph()` construction measured independently at ~10.3–11.4s (`D83`,
`docs/RESULTS.md`:10034-10039). If a fresh read shows the same shape — a small number of very slow
invocations pulling the tail up while `p95` stays far below them — that is consistent with the known cold-start
mechanism, not evidence of a new regression by itself.

---

## 6. What is already known, and already decided — read before proposing a fix

**Status: accept-and-carry-forward** (`docs/RESULTS.md` §11.22; `PROJECT_STATE.md` open item `H`, line
4184). This is a decision on record, with named conditions for reopening it — not an absence of a decision,
and not something to re-derive from first principles.

**Why the retired shorthand is never used here, restated so this runbook doesn't reintroduce it:** the
1,819ms warm-path figure is measured over a sample that structurally excludes ASR, TTS, and telephony
wire/playout time — none of
which this project has ever measured. Whatever those add can only add to the true figure, never subtract
from it, so the true overage against the 1,800ms target is unmeasured and at least as large as the sample
shows, not a specific known quantity. Any phrasing that states a fixed number of milliseconds of overage
claims more precision than exists.

**Already tried and closed — do not re-propose without addressing why each was closed:**

| Option | Outcome | Where |
|---|---|---|
| Caching | Closed structurally at $0 — Nova Micro's explicit prompt caching doesn't apply to the `tools` field, the one field in this call large enough to matter | `docs/RESULTS.md`:3506-3525 |
| Schema strip (shrink the router's tool schema) | Tested for real against Bedrock, **rejected on quality**: 32% classification disagreement at n=50, 4 dropped safety-flag verdicts — not shipped, latency direction left unresolved | `docs/RESULTS.md`:3500 |
| Provisioned throughput | Closed on cost policy — every comparable published PT rate found is orders of magnitude over the $25/month ceiling | `docs/RESULTS.md`:3503 |
| Context-enrichment for routing (`D90` part 1, Option 1) | Built and measured for real against Bedrock (`scripts/measure_router_context_latency.py`, 141 golden-corpus turns, 282 calls): Δp95 = +38.7ms, 95% CI [-51.3, +157.9] — not distinguishable from zero. Shipped for an unrelated reason (a misrouting defect), not as a `C14` fix, and did not move `C14` | `PROJECT_STATE.md`:8987 |
| Lexical short-circuit for routing | **The one option left open, deliberately not pursued** — its only latency-positive form risks `C1` (union recall) by skipping the Bedrock call on some turns, and needs its own scoping before it can be tried safely | `docs/RESULTS.md`:3502, 3992-3995 |

**Re-open this only on one of the five named triggers** (verbatim, `PROJECT_STATE.md`:4184): a real inbound
call is placed and measured; Tier A instrumentation (§3) is built; a scoped lexical short-circuit is
designed and its required `C1` re-verification passes; Nova Micro's serving characteristics or the
`tools`-field caching exclusion changes; or the cost ceiling / Bedrock provisioned-throughput pricing
changes materially. A mitigation proposal that doesn't address why the five options above were already
closed repeats prior work rather than advancing past it (`docs/RESULTS.md`:3979-3982).

---

## 7. What to actually do

1. If you took a manual read (§4): report the number labeled for exactly what it measures — "Lambda-invocation
   p95," not "`C14`" — and record it following this project's existing citation discipline. Do not present
   it as a new `C14` figure.
2. Check the result against the five triggers in §6. If none apply, **no action is required** — the
   exceedance is a documented, accepted, carried-forward state, not an open incident to close.
3. If a trigger does apply, or you're not sure whether one does: **stop and take it to Marco before building
   anything** — the same discipline as the STOP CONDITIONS govern billable resources, applied here to
   reopening a closed mitigation decision.

---

## 8. Guardrail false-positive spike

Out of scope for this document — criterion 5's second half, a separate runbook, not written here.
