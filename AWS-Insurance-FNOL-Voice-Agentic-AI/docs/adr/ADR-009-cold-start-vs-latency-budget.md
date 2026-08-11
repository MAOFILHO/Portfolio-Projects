# ADR-009: Cold-start mitigation order — smaller package, then Python SnapStart, then a scheduled warmer; provisioned concurrency last and cost-gated

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

The voice turn-latency budget (Lex STT completion → Polly audio stream start, ≤1,800 ms p95) is a
correctness requirement, not polish, per `PROBLEM-FRAMING.md`. `CLAUDE.md` already states a preference
order for cold-start mitigation — "prefer a scheduled warmer, smaller deployment package, or SnapStart
first. Provisioned concurrency requires cost-gate approval" — but does not fix the order among the first
three, and R4/Q-items flagged that this project has zero prior art for measuring or engineering around Lambda
cold starts against a hard sub-2-second budget. This ADR fixes the order and records what was verified today,
2026-08-11, rather than assumed.

### What was verified

- **Python 3.12 Lambda functions can use SnapStart today.** GA'd for Python and .NET on **2024-11-18**,
  expanded to 23 additional regions in **June 2025**.
  (<https://aws.amazon.com/about-aws/whats-new/2024/11/aws-lambda-snapstart-python-net-functions/>,
  <https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html>) This project's prior assumption — inherited
  from SnapStart's Java-only origins — that it wasn't available for a Python 3.12 function is **out of
  date**, and this ADR corrects it rather than repeating it.
- **Three hard constraints on SnapStart, all directly relevant to this architecture, verified from AWS's own
  docs:**
  1. **SnapStart and provisioned concurrency are mutually exclusive** on the same function — this is not a
     "prefer one, fall back to the other" choice at runtime, it is an either/or configuration.
  2. SnapStart does not support ephemeral storage over 512 MB — not expected to bind here, but recorded.
  3. **Network connections established at module-load time (a boto3 client, a Bedrock runtime client) are
     not guaranteed to survive the snapshot/resume cycle** — AWS's own guidance is to "validate the state of
     your network connections and re-establish them as necessary." This is a real code-shape requirement:
     any Bedrock/DynamoDB client instantiated as a module-level singleton must be defensively
     re-validated (or lazily re-created) on each invocation, not assumed live from snapshot. The same
     applies to anything generating IDs, nonces, or randomness at module-load time — it must be regenerated
     per-invocation, not baked into the snapshot.
- **Lambda cold-start init duration is now billed**, as of a **2025-08-01** billing standardization for
  on-demand ZIP-packaged functions — previously the init phase was unbilled. (Cited via search snippet from
  an AWS Compute Blog title; **not independently fetched as a full page in this pass — treat the exact
  mechanics as needing direct verification before it drives a specific cost-table number**, though the
  directional fact — cold starts now cost money proportional to duration where they didn't before — is
  corroborating evidence for minimizing cold-start frequency and duration regardless.)
- **No AWS-published cold-start millisecond figure exists for this project's specific dependency stack**
  (boto3 + a Bedrock runtime client + LangGraph + its transitive dependencies). AWS's own general guidance
  states cold starts "vary from under 100 ms to over 1 second." A Java SnapStart benchmark (AWS Compute
  Blog, 2025-04-29) showed p99.9 cold start dropping from ~6,196 ms to ~1,426 ms with SnapStart and to ~782
  ms with invoke priming — **Java-specific, cited only as a directional illustration of SnapStart's typical
  improvement magnitude, not quoted as a Python number.** Any specific millisecond figure for this project's
  actual Python function must come from an in-repo load test (Phase 9), not from this ADR or from memory —
  consistent with constraint 13's "no invented metrics" discipline extended to engineering claims, not just
  documentation.
- **Provisioned concurrency pricing, current:** $0.0000041667/GB-second standby (billed continuously while
  enabled) + $0.0000097222/GB-second for actual invocation execution while enabled + $0.20/million requests
  (standard, applies regardless). (<https://aws.amazon.com/lambda/pricing/>) The standby charge accrues
  **whether or not the function is ever invoked** — this is the material difference from SnapStart, whose
  charges (caching, minimum 3-hour billing window, and per-restore) are usage-proportional, not
  idle-proportional.

## Decision

**Fixed mitigation order, cheapest/least-invasive first:**

1. **Smaller deployment package.** Lazy-import anything not needed on every turn — RAG/retrieval
   dependencies for `CoverageQuestion`/`RentalTowingEntitlement` only imported when those intents are
   actually reached, not at module load for every invocation regardless of intent. Trim unused boto3
   service clients to only what's invoked. This is free, has no downside, and directly reduces the
   init-phase duration that is now billed regardless of which further mitigation is layered on top.
2. **Python SnapStart** on the turn-processing Lambda(s), enabled on published versions/aliases (SnapStart
   requires this; `$LATEST` is not eligible). Chosen over a scheduled warmer as the primary mitigation
   because it addresses the actual cold-start mechanism rather than reducing its *frequency* — a warmer only
   helps if the warmed environment is the one that answers the next call, which is not guaranteed under
   concurrent invocations. Its two hard constraints are treated as mandatory code-shape requirements, not
   optional hardening: (a) no module-level boto3/Bedrock client is treated as guaranteed-live post-resume —
   every invocation validates or lazily re-establishes it; (b) nothing that generates an ID, nonce, or
   session token at module load is reused across resumes — generated per-invocation instead.
3. **Scheduled warmer** (a low-frequency EventBridge Scheduler rule invoking the function on an idle
   schedule) is kept as a **documented fallback, not built in Phase 2**, for the specific case where Phase 9
   benchmarking shows SnapStart's restore latency still breaches the 1,800 ms budget on the very first call
   after an idle period. A warmer is cheap (a handful of scheduled invocations/day) but only guarantees one
   warm environment, which does not solve a burst of concurrent calls — recorded as a partial mitigation, not
   oversold as sufficient on its own.
4. **Provisioned concurrency — last resort, individually cost-gated per `CLAUDE.md`.** Not adopted in
   Phase 2. If Phase 9's measured p95 (with SnapStart and a trimmed package already in place) still breaches
   1,800 ms, provisioned concurrency is the next step — but it is a resource that accrues cost continuously
   whether or not a call ever arrives, which is exactly the "denial of wallet" failure mode (F10 in
   `AI-USE-CASE-CARD.md`) this project already tracks. It requires its own cost table (idle GB-hours ×
   $0.0000041667, at whatever concurrency level is chosen, run continuously for a month) presented for
   explicit `APPROVED: <phase name>` sign-off before being enabled — not bundled into a general Phase 8/9
   approval.

**Measurement, not assertion:** Phase 9 benchmarks p95 turn latency separately for (a) the first call after
an idle period (cold-start-affected) and (b) calls following shortly after (warm path), using the Lambda
`INIT_REPORT` duration plus the actual graph/tool/Bedrock invocation time, reported against the 1,800 ms
budget as an **OBSERVED** measure — not claimed to meet the budget here, in Phase 2, before it has been
measured even once.

## Consequences

**Positive:**
- The mitigation order matches `CLAUDE.md`'s stated preference (warmer/smaller-package/SnapStart before
  provisioned concurrency) while resolving the previously-unfixed ordering *among* those three, with a
  concrete reason for each position.
- SnapStart's usage-proportional billing (vs. provisioned concurrency's idle-proportional billing) keeps
  this mitigation cheap at demo-scale call volume, consistent with the $25/month ceiling.
- The code-shape requirements SnapStart imposes (defensive client re-validation, no module-load nonce
  generation) are recorded now, before Phase 5 implementation, rather than discovered as a production bug
  after a snapshot/resume silently reused a stale connection.

**Negative / accepted residual risk:**
- No verified Python-specific cold-start millisecond number exists yet for this project's actual dependency
  stack — Phase 9 could discover the budget is not met even with SnapStart, in which case provisioned
  concurrency becomes necessary and must go through its own cost-gate approval at that point, not be
  pre-approved here.
- The 2025-08-01 init-duration billing change was verified only via a search snippet, not a full fetch;
  exact billing mechanics should be re-confirmed directly before that specific figure drives a cost-table
  line in Phase 9/11.
- A scheduled warmer, if ultimately needed, only covers single-concurrency traffic — this project's expected
  demo-scale call volume makes that an acceptable limitation, but it is recorded as a limitation, not solved.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| Provisioned concurrency as the first-line mitigation | Rejected as first choice | Idle-proportional billing accrues cost with zero calls — the exact denial-of-wallet shape (F10) this project already guards against; reserved as a cost-gated last resort |
| Scheduled warmer as the first-line mitigation | Rejected as first choice | Only guarantees one warm environment; does not address concurrent-call bursts the way SnapStart addresses the mechanism itself |
| Do nothing, accept whatever cold-start latency occurs | Rejected | Directly risks breaching the 1,800 ms p95 correctness requirement on exactly the calls (first-of-session, low-traffic demo line) this project is most likely to see |
| **Smaller package → Python SnapStart → warmer (documented fallback) → provisioned concurrency (cost-gated)** | **Chosen** | Matches `CLAUDE.md`'s stated preference order; verified SnapStart is available and usage-proportional-billed for Python 3.12 today |

## Sources

- <https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html>
- <https://aws.amazon.com/about-aws/whats-new/2024/11/aws-lambda-snapstart-python-net-functions/>
- <https://aws.amazon.com/about-aws/whats-new/2025/06/aws-lambda-snapstart-python-net-functions-23-regions>
- <https://aws.amazon.com/lambda/pricing/>
- <https://aws.amazon.com/blogs/compute/optimizing-cold-start-performance-of-aws-lambda-using-advanced-priming-strategies-with-snapstart/>
- <https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html>
- AWS Compute Blog, "AWS Lambda standardizes billing for INIT phase" (2025-08-01 change) — cited via search snippet; flagged above as needing direct re-verification before precise billing figures are used

All facts fetched live on 2026-08-11 via a background research agent, per the project's standing rule to
verify against current sources rather than memory. No specific cold-start millisecond figure for this
project's own function is asserted here — that is Phase 9's job, measured, not projected.
