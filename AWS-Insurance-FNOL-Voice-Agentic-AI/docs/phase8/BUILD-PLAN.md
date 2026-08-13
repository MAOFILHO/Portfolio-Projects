# Phase 8 — Telephony and infrastructure as code

**Status: APPROVED 2026-08-12.** Marco typed `APPROVED: Phase 8`. Three separate authorisations were
granted, and they are separate on purpose — see §3.

1. **Provisioned resources**, under **$2**.
2. **A real-call allowance: 20 calls, ≈$4**, as a line distinct from the Bedrock standing cap. Marco's
   words: *"different resource class, different authorization."* The simulator stays the default path and
   every real call is logged in `COSTS.md`.
3. **The Stage 2 `AWS::Lex::Bot` POC**, with two conditions attached: it gets **its own line in
   `COSTS.md`**, and it is **destroyed when the gate passes or fails** — *"it has no purpose after
   `ADR-007` resolves."*

## STOP CONDITIONS — restated verbatim

- No phase begins without written exit criteria from the prior phase and my explicit approval.
- No billable AWS resource is created without me typing `APPROVED: <phase name>`.
- The Amazon Connect instance and DID already exist. Never create either.
- `PROJECT_STATE.md` is updated before any session ends.
- Restate these four conditions verbatim at the top of every session summary and after every `/compact`.

---

## 1. What this phase is

Everything the agent needs to answer a real phone call, expressed as Terraform. Today the repo has one
provisioned resource — the Bedrock guardrail, on **local state** — and a graph that has never been reached
by a telephone.

The roadmap's line for this phase:

> Consume pre-provisioned instance via data source; flows/queues/Lex/Lambda as IaC; telephony stack import
> guard asserting `Protected=true`; uniquely-named flows so a known-good fallback always exists.

**Constraint 16 governs everything here and is not negotiable in either direction.** The Connect instance
`eba56246-0368-4f1c-8b97-e2ab3b0e8246` and the DID `+14169871547` exist. Terraform consumes the instance
via a data source; it never runs create-instance and never creates a second one. The number lives in
`stacks/telephony` with `prevent_destroy`, in **separate state that `make destroy` does not touch**.
Releasing and re-claiming risks a **180-day claim block** — that is the failure this rule exists to prevent,
and it is not recoverable by re-running anything.

### What Phase 7 hands over

| | |
|---|---|
| Shipped and verified | The graph, L1/L2, the guardrail at **v3**, the eval harness, 377 tests |
| `C1` | **Composed escalation recall 1.000 (26/26)** on the shipped `L1 → guardrail v3 → L2` path |
| Known-open | `NOT-FIXED.md` — 12 entries, of which **#2 (`D43`) and #12 are Phase 8's** |
| Spend | ≈$0.397 of Phase 7's $1.25; standing Bedrock cap ≈$0.411 of $5.00 |

---

## 2. Stages

### Stage 0 — `make bootstrap`, the state backend, and the cost allocation tag ✅ **DONE 2026-08-12**

Delivered: `Project` tag activated · `infra/terraform/bootstrap` applied (6 resources, $0.00) · guardrail
stack migrated to the remote backend and verified by a **no-change plan** · `make bootstrap` and
`make verify-backend` · `.terraform.lock.hcl` un-ignored · **`docs/phase8/COST-ATTRIBUTION-AUDIT.md`**.

The audit changed four things downstream, listed here because they are dependencies, not observations:

| Finding | Lands in |
|---|---|
| Connect voice needs **contact tags** set in the flow — instance tags are TBAC and attribute nothing | **Stage 3** |
| Bedrock on-demand is **unattributable** through a system-defined `us.*` profile; needs an application inference profile, which needs an ADR against constraint 17's literal wording | **Stage 5, ask first** |
| `aws:connect:instanceId` is the robust filter and **cannot be activated until contacts exist** — so criterion 9 is gated behind criterion 1, then 24h | **Stage 5** |
| The account is on credits offsetting 100% of usage; the budget must set `IncludeCredit: false` or it can never fire | **Stage 5** |


**First action of the phase, before any bucket: activate the `Project` cost allocation tag.** It takes up
to 24h to appear in billing data, so everything downstream of it is blocked on starting it early. And per
Marco's condition on criterion 9, activation is not the deliverable — **propagation is**. A tag key can be
activated while no resource in the account actually carries it, in which case the filtered alarm matches
nothing, reports $0 forever, and is indistinguishable from a project that is under budget.

S3 bucket (versioned, SSE-S3, public access blocked) plus native S3 state locking. **No DynamoDB lock
table** — Terraform ≥1.10 supports `use_lockfile`, and a lock table is a billable resource this project
does not need for a single operator.

Then **migrate the guardrail stack off local state**, which is the debt Phase 7 knowingly took on. Its
residual risk was stated at the time as *"lose the local state and the guardrail is orphaned — a $0/mo
orphan, findable by name."* Migration is the routine `terraform init -migrate-state`.

### Stage 1 — `stacks/telephony`, the protected stack

The DID, imported and never created. **The import guard asserts `Protected=true` on the number's tags
before proceeding** — that assertion is why the tag exists (`PROJECT_STATE.md`, Phase 0), and it must fail
the run rather than warn.

Three properties, each tested rather than asserted:

1. `prevent_destroy = true` on the phone-number resource.
2. **Separate state file**, and `make destroy` does not name this directory. A CI check greps the destroy
   target for it, because "we know not to" is not a control.
3. A `terraform plan` in this stack after a `make destroy` shows **no changes** — the proof that teardown
   left it alone.

### Stage 2 — the Lex bot, and `ADR-007`'s mandatory POC gate

`ADR-007` chose nested CloudFormation `AWS::Lex::Bot` inside `aws_cloudformation_stack` because three open
provider bugs sit exactly on this project's needs: `prompt_specification` updates silently not applied
(#42147), "inconsistent result after apply" on `prompt_attempts_specification` (#36845), and a **circular
dependency between `aws_lexv2models_intent` and `aws_lexv2models_slot` via `slot_priority`** (#39948).

The ADR did not declare that resolved. It recorded a **mandatory Phase 8 proof-of-concept**, because the
cycle is confirmed avoided by the nested shape while the multi-slot/prompt-attempts risk is *unconfirmed
rather than clean*. So Stage 2 is a gate, not a task:

> **Build the smallest `AWS::Lex::Bot` stack that exercises the 9-slot FNOL intent with
> `PromptAttemptsSpecification` and `DTMFSpecification`, apply it, change a prompt, apply again, and
> confirm the change actually took.** If it does not, `ADR-007` is superseded here — not worked around.

The "change it and apply again" half is the whole point. #42147 is a *silent* failure: the first apply
looks fine.

### Stage 3 — `stacks/main`

Contact flows, queue, hours of operation, the Lex association, the Lambda association, the Lambda itself,
the DynamoDB tables (checkpointer + vector store), the S3 bucket. All destroyable.

**Two things that are not routine:**

- **Uniquely-named flows.** Every flow carries a content hash or timestamp suffix, so a bad flow never
  overwrites a known-good one and the DID can be pointed back within one console-free apply. This is the
  rollback story for the one resource that cannot be recreated.
- **`recording stays off` becomes CI, not a convention.** Constraint 18's check: fail the build if any flow
  contains an `UpdateContactRecordingBehavior` whose `RecordedParticipants` is non-empty, or any occurrence
  of `AnalyticsBehavior`, `ContactLens`, `RealTimeContactAnalysis`. **Flow files are globbed by content**
  (presence of an `Actions` or `modules` key), not by `.json` extension — some upstream exports have no
  extension, and extension-globbing would silently skip them.

### Stage 4 — the Lambda codehook

`src/fnol_voice_agent/api/` does not exist yet. This is the first code Phase 8 writes: the Lex V2 codehook
entry point, the sessionState contract (`Delegate`/`Close`/`ElicitSlot`, `slots.X.value.interpretedValue`),
and the graph invocation keyed on the Connect `contactId` per `ADR-005`.

`ADR-009` binds: no client at module load, SnapStart-compatible, lazily created and cached per instance.

### Stage 5 — cost controls, on the day the resources appear

`CLAUDE.md`: *"Budget alarm + cost dashboard ship day one, not at the end."* Phase 8 is day one.

⚠ **The budget alarm must be tag-filtered, and this is a finding, not a preference.** Cost Explorer for
this account on 2026-08-10 shows `USW2-Llama3-3-70B-Customization-Training` — **the sibling project's
fine-tuning run, in the same account.** An account-wide $25 alarm would fire on a neighbour's spend and be
disabled within a week. Filter on `Project=AWS-Insurance-FNOL-Voice-Agentic-AI`, which requires activating
that cost allocation tag first (it takes up to 24h to appear, so it is a Stage 0 task, not a Stage 5 one).

Also `make verify-billable` — read-only, asserts no unexpected billable resource exists — and the
teardown-and-rebuild proof below.

### Stage 6 — the two `NOT-FIXED` items this phase owns

- **#2 / `D43`:** the blocked-turn branch promises a human and delivers nothing. Phase 7 declined to write
  a fake `EscalationRecord` behind a stub transfer on the grounds that *"a record with no transfer behind
  it is a different lie, not a smaller one."* Phase 8 wires the real transfer, so the reason for declining
  expires here.
- **#12:** publishing a guardrail version deletes the version the previous verification was measured
  against. Either a retention approach, or an accepted trade recorded as one.

---

## 3. Cost gate

**No resource is created until `APPROVED: Phase 8`.** Pricing below re-verified 2026-08-12 against current
AWS sources, not from memory. Two figures moved and are corrected in `CLAUDE.md`'s table in this commit.

| Resource | SKU / tier | Free tier | Est. monthly at demo volume | If teardown is forgotten |
|---|---|---|---|---|
| S3 state bucket + native locking | Standard, versioned | 5 GB (account-age-independent) | **$0.00** | ~$0.00 — kilobytes |
| Connect instance | pre-existing, **Customer Basic** | n/a | **$0.00 at rest** | $0.00 — no idle charge |
| **Canada DID** `+14169871547` | `USW2-CA-did-numbers` | none | **$1.83/mo — MEASURED 2026-08-12**, $0.06/day on two independent days | **survives `make destroy` by design** |
| Connect voice service | **Customer Basic, $0.015/min** first 5M min/mo | none | ~$0.06 at 20 demo calls × 4 min | $0.00 — usage only |
| Canada inbound telephony | per-minute, on top of the above | none | ⚠ unconfirmed, ~$0.01/call order | $0.00 |
| Lex V2 speech | $0.004 / speech request | **none — no perpetual free tier** | ~$0.64 at 20 calls × 8 turns | $0.00 |
| Lambda | 128–512 MB, on-demand | **1M req + 400k GB-s/mo, perpetual** (re-verified) | **$0.00** | $0.00 |
| DynamoDB (checkpointer, vectors) | on-demand | 25 GB storage only — **not** free RCU/WCU on-demand | <$0.01 | ~$0.00 at this size |
| S3 (artifacts) | Standard | 5 GB | **$0.00** | ~$0.00 |
| CloudWatch logs + alarms | basic | 5 GB logs, 10 metrics | **$0.00** | ~$0.00 |
| Bedrock guardrail resource | — | free at rest | **$0.00** | **$0.00** |
| **Provisioned concurrency** | — | **explicitly excluded** — the Lambda free tier does not apply to it (re-verified) | — | — |

**Estimated Phase 8 total: under $2**, dominated by Lex speech requests on real calls, which is why the
simulator stays the default path.

✅ **The Canada DID rate is resolved, and the reason it took eight phases is instructive.** It is
**$0.06/day = $1.83/month** — twice the US rate, 7.3% of the ceiling, permanent, and the project's only
always-on cost.

Every previous attempt failed for the same reason, and the reason was not lag. The charge is filed under
**`Contact Center Telecommunications (service sold by AMCS, LLC)`** — a separate seller — and not under
Amazon Connect. The observation *"Cost Explorer shows no Amazon Connect line at all"* was true; the
inference that nothing had posted was wrong. Waiting for a full billing period would have produced exactly
the same empty result in September. **A $0.00 reading and an absent line item are indistinguishable in a
grouped cost report, and only one of them means "no spend."**

The **per-minute inbound** rate is still unmeasured and needs a real call — it resolves with criterion 1.

**Two spend requests, both needing an explicit word:**

1. **`APPROVED: Phase 8`** for the provisioned resources above.
2. **A real-call allowance.** Real calls are the only way to verify a phone system, and they are the
   dominant marginal cost (~$0.15–0.20/call all-in). Requesting **20 calls, ≈$4**, with the simulator as the
   default path and every real call logged in `COSTS.md`. The Phases 3–7 Bedrock standing cap does not
   cover telephony and is not stretched to.

---

## 4. Exit criteria

Phase 8 is complete when every row is discharged or explicitly recorded as violated — `PROJECT_STATE.md`'s
Phase 7 criterion 16 is the precedent for the second option, and it is a real option.

| # | Criterion |
|---|---|
| 1 | **A real inbound call to `+14169871547` reaches the agent and completes a turn**, with the transcript in `docs/evidence/`. Nothing else in this list substitutes for it |
| 2 | **The Connect instance was never created and never re-created.** `terraform state list` shows it only as a data source; the instance's `CreatedTime` is unchanged from `2026-08-11` |
| 3 | **The DID's `Protected=true` import guard fails the run when the tag is absent** — demonstrated by removing it in a scratch copy, not asserted |
| 4 | `make destroy` runs to completion, then `make verify-billable` reports **$0 of unexpected billable resources**, and a `terraform plan` in `stacks/telephony` shows **no changes** |
| 5 | `make deploy` rebuilds everything destroyed, from clean, in one command, and criterion 1 passes again afterwards |
| 6 | **Zero portal clicks beyond the four already recorded** in `MANUAL-STEPS.md`. Any fifth is added there with its justification, or the phase does not close |
| 7 | **The recording CI check is red on a deliberately bad flow** and green on the shipped ones. Globbing is **by content**, proven against an extensionless file |
| 8 | **`ADR-007`'s POC gate discharged**: a prompt change applied twice, verified to have actually taken effect. If it did not, an ADR supersedes `ADR-007` and says what replaced it |
| 9 | **Budget alarm is tag-filtered and proven with two probes in opposite directions**, each with a value known in advance: it must **include** a known non-zero quantity of *our* spend (the DID's $0.06/day, which accrues on its own) and **exclude** a known non-zero quantity of the sibling's (the $0.84935 Llama training run of 2026-08-10). One probe cannot distinguish a working filter from one that matches nothing — "ignores the sibling" is satisfied perfectly by a filter that ignores everybody. Also: **`IncludeCredit: false`**, per §6.1 of the audit. Marco, granting the approval: *"A tag-filtered alarm that silently matches nothing is the same failure shape as the fingerprint that hashed three files."* See `COST-ATTRIBUTION-AUDIT.md` |
| 15 | **The Stage 2 Lex POC is destroyed once `ADR-007` resolves, pass or fail**, and its own `COSTS.md` line shows the teardown. Marco's condition on approving it separately: *"it has no purpose after `ADR-007` resolves"* |
| 10 | The guardrail stack is on the **remote backend**, and `RESULTS.md`/`PROJECT_STATE.md` record the migration |
| 11 | **`D43` is fixed** — a blocked turn either performs a real transfer or stops promising one |
| 12 | **`C1` re-verified on the deployed system** if anything in `_FINGERPRINT_SOURCES` moved. Phase 7's finding is that a defensible per-component change can move the composition; a Lambda wrapper around the graph is exactly such a change. **The reasoning for skipping this will be "the graph is unchanged, only its wrapper is new." That sentence is verbatim the argument Stage 8 rejected and §3.9 documented. If discharging this criterion feels unnecessary when you reach it, that feeling is the finding — proceed anyway.** (Marco, on granting `APPROVED: Phase 8`) |
| 13 | Spend inside the approved gate, **every run logged in `COSTS.md` at the time it runs.** Phase 7 failed this one and recorded it as failed; Phase 8 does not get to fail it the same way twice |
| 14 | `PROJECT_STATE.md` updated, `/compact` after sign-off |

### Two criteria I want to flag as harder than they look

**Criterion 1** is the first time this project touches a telephone. Everything before it is text. Expect
ASR-shaped surprises the transcript-level bias check in §5.2 of `RESULTS.md` explicitly could not see —
that section says in as many words that it *"is not an ASR or accent audit"*, and Phase 8 is where that
limitation stops being theoretical.

**Criterion 12** is the one most likely to be skipped, because it will feel unnecessary — the graph is
unchanged, only its wrapper is new. That is verbatim the reasoning Phase 7 rejected at Stage 8, one section
after documenting why it was wrong. On Marco's instruction that reasoning now lives **inside the criterion
text**, not only here, so it cannot be lost by reading the table alone.

---

## 5. Open questions — resolved 2026-08-12

1. **Real-call allowance** — ✅ **20 calls / ≈$4, approved as a separate line** from the Bedrock cap.
2. **`/Users/marco/K21/Real-world/.github/workflows/`** — still a Phase 10 write outside `PROJECT_ROOT`,
   still **not** pre-approved, not needed in Phase 8. Flagged so it is not stumbled into.
3. **The `AWS::Lex::Bot` POC** — ✅ **approved, and separately.** Marco: *"A resource created to test
   whether we can create resources is exactly the thing that gets folded in silently and then never
   accounted for."* Conditions: its own `COSTS.md` line, and destroyed once the gate resolves either way.
