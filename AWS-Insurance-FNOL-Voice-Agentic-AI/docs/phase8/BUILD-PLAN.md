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
| `C1` | **Composed escalation recall 1.000 (26/26)** on the shipped `L1 → guardrail v3 → L2` path — accurate as Phase 7's handover, local graph only. **Stage 4 update, not a Phase 7 correction:** the Lambda wrapper this phase adds broke that path entirely (`D80`/`D81`, `PROJECT_STATE.md`); as of Stage 4, `C1` is unverified on any deployed build, see `RESULTS.md` §0.2/§11 |
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

### Stage 1 — `stacks/telephony`, the protected stack ✅ **DONE 2026-08-12**

`terraform apply`: **1 imported, 0 added, 0 changed, 0 destroyed.** The number is under Terraform
management with zero modification to it — no `default_tags` block in this stack, deliberately, so the
tags in config are exactly the three the number already carried and a correct apply is a no-op.

| Property | How it was established |
|---|---|
| Import guard fails without the tag | **Demonstrated, criterion 3.** Two scratch runs: a wrong number ID fails on import; a valid import whose tag condition cannot be satisfied fails at **plan** time with the guard's own message, before anything is imported. The first run alone would have been a false pass — it failed on `Cannot import non-existent remote object`, not on the guard |
| `prevent_destroy` | `terraform plan -destroy` → `Error: Instance cannot be destroyed`. Run, not asserted |
| Separate state | `stacks/telephony/terraform.tfstate`, and `make verify-destroy-scope` fails if any other stack shares the key |
| `make destroy` cannot reach it | `make verify-destroy-scope` + 8 unit tests, each with a negative control. There is no `destroy` target yet, so that check currently passes with nothing to find — which is exactly when it has to be written |

The guard reads `Protected` from the Resource Groups Tagging API rather than from a variable, and is
fail-closed: an absent tag, an absent resource, or an unrecognised response shape all evaluate to
something that is not `"true"` and all stop the run. Same asymmetry as Phase 7's mask-vs-block parser.

The DID, imported and never created. **The import guard asserts `Protected=true` on the number's tags
before proceeding** — that assertion is why the tag exists (`PROJECT_STATE.md`, Phase 0), and it must fail
the run rather than warn.

Three properties, each tested rather than asserted:

1. `prevent_destroy = true` on the phone-number resource.
2. **Separate state file**, and `make destroy` does not name this directory. A CI check greps the destroy
   target for it, because "we know not to" is not a control.
3. A `terraform plan` in this stack after a `make destroy` shows **no changes** — the proof that teardown
   left it alone.

### Stage 2 — the Lex bot, and `ADR-007`'s mandatory POC gate ✅ **DONE 2026-08-13 — `ADR-007` UPHELD**

**The second apply took, at definition and at runtime.** `ADR-007` stands; nothing supersedes it. A third
apply also confirmed that a **deletion** propagates rather than merging — the question the gate as written
did not ask, and the more dangerous one. Stack **destroyed**, residue verified, line C closed at $0.00825.

Four findings that matter more than the verdict, all in **`docs/phase8/LEXPOC-GATE.md`**:

| | Finding | Lands in |
|---|---|---|
| 1 | The **locale build finishes after CloudFormation reports success** (`CREATE_COMPLETE` at 38 s, `Built` ~16 s later). A green apply does not mean a built bot | **Stage 3** — explicit wait, not an assumption |
| 2 | **`TestBotAliasSettings` must be set explicitly** or the bot cannot be spoken to — and AWS's own reference example omits it. Every control-plane read reports a healthy bot | **Stage 3** |
| 3 | **`MessageSelectionStrategy: Ordered` does not walk message groups per attempt.** Phase 4 §4's keypad-offer-on-first-no-match is **not declaratively expressible**; it belongs in the codehook. Recorded consequence: the opening turn apologised to the caller before they had spoken | **Stage 4**; `SLOT-DESIGN.md` §4 carries a dated correction |
| 4 | **`ListSlots` pages at 10 and the intent has 11** — an unpaginated read silently drops `other_party_involved` | the gate script; a test asserts the count |

Also confirmed rather than assumed: the `Project` tag **propagates from the CFN stack to the Lex bot**
(Stage 0's rule applied to a new resource type), and #39948's intent↔slot cycle genuinely does not arise
in the nested shape.

Discharged by `scripts/lexpoc_gate.py` — three instruments (declared / definition / runtime), a negative
control field held still, and **15 tests in `tests/unit/test_lexpoc_gate.py` that mutate the recorded
evidence into each failure the gate claims to catch**. Evidence: `docs/evidence/phase8/lexpoc-apply-{1,2,3}.json`.

Original scope below.

---

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

### Stage 3 — `stacks/main` ⏸ **BUILT AND PLANNED 2026-08-13 — apply pending**

**23 resources, `terraform plan` clean, `terraform validate` clean, 488 tests green.** The apply has not
run: the harness's permission layer declined it, so the plan and its cost delta are below and the apply
needs a word. Nothing in this stage is outside the `APPROVED: Phase 8` under-$2 authorisation.

**Cost delta: $0.00/month at rest.** Lambda, DynamoDB on-demand, S3 and CloudWatch are free at this
volume; Connect flows, queues and hours of operation are not billed at all; Lex bills per runtime
**request** and not for storing a bot — measured in Stage 2, not assumed. Nothing in this stage places a
call, and a call is the only thing here that costs money.

| Resource | Count | At rest |
|---|---|---|
| Lex bot + published version + `live` alias (2 CFN stacks) | 2 | $0.00 |
| Connect contact flow, queue, hours of operation | 3 | $0.00 — not billed |
| Connect↔Lex integration association, Connect↔Lambda association | 2 | $0.00 |
| Lambda + log group + 2 permissions | 4 | $0.00 (1M req / 400k GB-s free) |
| IAM: 2 roles + 2 inline policies | 4 | $0.00 |
| DynamoDB checkpointer + vector table, on-demand | 2 | $0.00 idle; 25 GB storage free |
| S3 artifacts bucket + 4 configuration resources | 5 | $0.00 |
| `terraform_data` build wait, `terraform_data` flow version | 2 | $0.00 |

#### Four things in this stage that are not routine

**1. The provider cannot express two of these resources at all — an independent vindication of `ADR-007`.**
`ADR-007` chose nested CloudFormation on the strength of three provider *bugs*, and Stage 2 discharged its
POC gate against them. Stage 3 found two provider **gaps** that would have forced the same decision from
scratch:

- **There is no `aws_lexv2models_bot_alias` resource.** Provider 6.59.0 ships `_bot`, `_bot_locale`,
  `_bot_version`, `_intent`, `_slot`, `_slot_type`. No alias — and Connect associates with an *alias*.
- **`aws_connect_bot_association` is Lex V1 only.** Its schema carries one `lex_bot` block with `name` and
  `lex_region`, the classic-Lex shape. The V2 association needs `LexV2Bot.AliasArn`, which the resource
  cannot express, while `AWS::Connect::IntegrationAssociation` documents "Lex bot (both v1 and v2)".

Neither was known when `ADR-007` was written. **A decision holding up for reasons its author did not have
is worth more than the reasons they did have**, and it is recorded in `release.yaml.tftpl`'s header rather
than as an ADR amendment, because nothing about the decision changed.

**2. The version-staleness trap was read out of the documentation before the resource was written.**
`AWS::Lex::BotVersion`, verbatim: *"If the DRAFT version of this resource hasn't changed since you created
the last version, Amazon Lex doesn't create a new version, it returns the last created version."* Every
property except `BotId` is "Update requires: No interruption". **That is the Bedrock Guardrails DRAFT trap
in a second service** — `RESULTS.md` §3.5.1, instance 1 — and this time it was predicted rather than
measured after the fact. The fix is the CloudFormation analogue of `replace_triggered_by`: the version's
**logical ID carries the bot definition's hash**. Plus `make verify-lex`, because §3.5.1 rule 1 says a
mechanism is not a verification.

**3. Constraint 18's CI check, as `CLAUDE.md` words it, has a hole. Widened, and reported rather than
widened silently.** `CLAUDE.md` specifies *"`RecordedParticipants` is non-empty"*. The
`UpdateContactRecordingBehavior` parameter reference shows **three independent switches**:

```
RecordedParticipants        — Agent / Customer call audio
ScreenRecordedParticipants  — Agent screen recording
IVRRecordingBehavior        — "Enabled" | "Disabled"
```

A flow with `{"RecordedParticipants": [], "IVRRecordingBehavior": "Enabled"}` **passes the check exactly
as worded while recording the caller's entire self-service conversation** — and the IVR leg is the only
leg this system has, because there are no agents. `scripts/check_flows.py` fails on all three.
`tests/unit/test_check_flows.py::test_ivr_recording_fails_even_with_an_empty_participant_list` is the
negative control. **Amendment accepted by Marco 2026-08-13; `CLAUDE.md`'s constraint 18 now names all
three switches plus a missing behaviour object, and checker and constraint agree.** See `D73` — the
reason the gap could not be left open is that it had a direction: the constraint is what people read, the
checker is what people edit to get green.

**4. The DID is deliberately not pointed at the flow, and the flow's greeting deliberately promises
nothing.** The Stage 3 codehook implements the Lex wire contract and does not yet run L1/L2. A number
pointed at a flow is a number a stranger can dial, and an FNOL bot that collects claim details with no
injury-detection path is the one thing `CLAUDE.md` marks as admitting no negotiation. An unrouted number
rings out: a worse demo, a better system. Same reasoning keeps *"say agent to reach a person"* out of the
greeting — `NOT-FIXED.md` #2's *"a record with no transfer behind it is a different lie, not a smaller
one"*, committed in the first sentence of the call. Both land in Stage 4, one resource and one default.

#### One design decision worth flagging

**L3 — the hard "agent"/"human" override — is NOT a seventh Lex intent, and that is about correctness
rather than about counting to six.** Mid-slot-elicitation an utterance is matched against the active slot
type, so a caller saying "agent" while `policy_number` is being elicited produces a **no-match, not an
intent switch**. A Lex intent for L3 would be reachable from most states and would *look* reachable from
all of them. L3 therefore lives in the codehook as a deterministic per-turn check, exactly where L1 lives
and for `ADR-010`'s reason — and `DialogCodeHook` is enabled on `FallbackIntent` so a no-match turn
reaches it. Stage 4 implements it.

#### Original scope below

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

### Stage 4 — the Lambda codehook, the real transfer, and the DID — **PROPOSED 2026-08-13, awaiting `APPROVED: Stage 4`**

`src/fnol_voice_agent/api/lex_codehook.py` exists from Stage 3 but implements the Lex V2 wire contract and
nothing above it — its own docstring names what is missing and defers each item here by name. This stage
closes those items, wires the real Connect transfer `D43`/`NOT-FIXED.md` #2 has been waiting on since
Phase 7, and — **only if the last thing it does passes** — routes the DID. Nothing before the final
criterion touches `stacks/telephony`'s state.

**Re-scoped from the original plan, named rather than left to drift:** `NOT-FIXED.md` #2 (`D43`, the real
transfer) was filed under Stage 6 when this plan was written. It moves to Stage 4 because it is now
coupled to the same flow content this stage already has to touch for the greeting change (`D75`) — proving
a real transfer needs an actual `Transfer to Queue` action in the flow, wired from an escalation signal
this stage introduces. Building that twice, once here and once in Stage 6, is the kind of split that lets
half of it ship silently incomplete. Stage 6 keeps `NOT-FIXED.md` #12 (guardrail version retention), which
is unrelated.

#### What Stage 3 already named as missing, and this stage owns

1. **`_dispatch()` replaced with the real LangGraph invocation**, `thread_id` = Connect `contactId`, per
   `ADR-005`. The DynamoDB checkpointer Stage 3 provisioned starts being read and written for the first
   time.
2. **L1 and L3 wired in as the deterministic per-turn checks `D74` requires**, reachable from `FallbackIntent`'s
   `DialogCodeHook` (already enabled in `bot.yaml.tftpl` — that line was load-bearing before this stage
   existed to use it). L2 is already inside the graph (`ADR-010`'s ordering); this stage does not rebuild
   it, only reaches it.
3. **The sessionState contract completed**: `ElicitSlot` alongside the `Delegate`/`Close` Stage 3 shipped,
   because the graph — not Lex's own slot machine — now decides what happens next on some turns.
4. **The fail-open/fail-closed split** `lex_codehook.py`'s own docstring flags as unexamined: today every
   error path returns `Delegate`, chosen deliberately for a handler that did nothing safety-relevant. Once
   L1/L2 run behind it, an exception swallowed on a turn carrying an injury disclosure is a `C1` breach
   wearing a resilience argument, not a resilience win. This stage splits the two cases: fails open
   (`Delegate`) where no safety signal has fired on the turn, fails closed (escalate) once one has.
5. **`ADR-009` extended to the new client set.** The checkpointer client and any Bedrock client the graph
   needs are lazily created and cached, never at module load — same two-level test (source-level and
   observed) Stage 3 already applied to the codehook's own boto3 usage.

#### The real transfer (`D43`, `NOT-FIXED.md` #2)

The escalation path performs an actual transfer to the queue Stage 3 provisioned — `EscalationRecord`'s
`real_connect_transfer_executed` stops being a hardcoded `False`. This needs a `Transfer to Queue` action
in the contact flow, reached from an escalation signal the graph hands back (session attribute or an
equivalent the flow can branch on) — not a second, parallel path that bypasses the flow the caller is
already in.

#### The greeting flow (`D75`)

*"Say agent to reach a person"* enters the greeting only now that saying it is true. Per `D75`'s own
mechanism: the flow's content hash makes this a **new** flow, not an edit to the one currently serving —
so a bad version never overwrites a known-good one and rollback is "point the association back," not
"redeploy."

#### `_FINGERPRINT_SOURCES`, widened a third time

`D53` widened the tuple from three files to seven because the guardrail joined the composition and nobody
told the fingerprint. The same mistake is available again here: `lex_codehook.py` and whatever graph-
invocation glue this stage adds are now load-bearing components of what gets measured, and the fingerprint
must move when they do. Widen it as part of this stage, not discovered after the fact the way `D53` was.

#### Stage 4 exit criteria

| # | Criterion |
|---|---|
| 1 | `_dispatch()` invokes the real graph, keyed on `contactId`. A two-turn conversation against the live alias (`RecognizeText`, not a real call) shows a slot value collected on turn 1 still present on turn 2 — proof the checkpointer round-trips, not just that it was provisioned |
| 2 | An "agent" utterance mid-slot-elicitation (a Lex no-match, per `D74`'s own finding) reaches L3 through `FallbackIntent`'s codehook and escalates — demonstrated live, not asserted from the graph's existing unit coverage alone |
| 3 | The fail-open/fail-closed split is real, proven by a test that forces an exception **after** a safety flag is set and asserts the response is not `Delegate` |
| 4 | A forced escalation performs a **real** Connect transfer to the Stage 3 queue. `EscalationRecord.real_connect_transfer_executed` is `True` on that path, verified against a live contact record, not against the field the code sets |
| 5 | sessionState contract covers `Delegate`/`Close`/`ElicitSlot`, each exercised by at least one live turn |
| 6 | The new greeting flow (with the agent-override line) exists as a distinct, content-hash-suffixed resource. `terraform plan` confirms it is a new flow, not a diff to the currently-serving one |
| 7 | `_FINGERPRINT_SOURCES` includes every file this stage adds to the composition. A test fails if a file under `src/fnol_voice_agent/api/` is not in the tuple, mirroring `D53`'s fix rather than re-deriving it |
| 8 | `ADR-009`'s discipline (no client at module load, lazy + cached) holds for every client this stage adds, checked at both the source level and the observed level |
| 9 | **`C1` re-verified against the DEPLOYED system.** Not the local graph call `D52` measured — a real invocation through the deployed Lambda and the live Lex bot alias (`RecognizeText`/direct Lambda invoke), on the independent injury set, k-sampled per Stage 8's protocol. Composed recall must not fall below the 1.000 (26/26) baseline `D52` established, or the candidate is rejected regardless of what it buys, exactly as `C1` has read everywhere else it has applied. **This is Phase 8 exit criterion 12, discharged here because this stage is the first point at which `_FINGERPRINT_SOURCES` moves on a deployed resource** — and it is a precondition of criterion 10, not a parallel item |
| 10 | **The DID is routed — last, and only if criterion 9 passed.** `aws_connect_phone_number_contact_flow_association` is created against the flow from criterion 6, in `stacks/main`, still not touching `stacks/telephony`'s state per `D75`'s second-order finding. **This criterion's own text carries its precondition, matching how Phase 8's criterion 12 was written:** routing the number before criterion 9 passes repeats the exact mistake `D75` was filed to prevent — a number a stranger can dial with no *verified-on-the-deployed-system* safety path behind it. "The graph already passed `C1` once, locally, in Phase 7" is not evidence about this Lambda; that reasoning is `D75` restated, not a new argument, and it is exactly the shape of the reasoning `_FINGERPRINT_SOURCES` existed to stop from going unmeasured |

Phase 8's own exit criterion 1 — the real inbound call — follows Stage 4's close, not inside it. Stage 4
ends when the number can be dialed safely; dialing it is the phase's own headline criterion and is reported
separately, with its own transcript in `docs/evidence/`.

**Cost, named rather than assumed covered.** Criterion 9's deployed re-verification is real `lexv2-runtime`
requests plus the Bedrock calls inside the graph they trigger — cheap (`D52`'s local run was $0.0212 for a
larger, k=5 sweep across all 43 items; this is a subset of that shape) but not telephony, and not covered
by the Bedrock standing cap, which `CLAUDE.md` scopes to **Phases 3–7** by its literal wording, not Phase 8.
Same pattern as the Stage 2 POC and the 20-call allowance: **its own line in `COSTS.md`, its own word before
it runs.** Criterion 10's real inbound call is separately covered by the existing 20-call/≈$4 telephony
allowance and is not this stage's to spend from.

`ADR-009` binds throughout: no client at module load, SnapStart-compatible, lazily created and cached per
instance.

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
| 8 | ✅ **DONE 2026-08-13. `ADR-007`'s POC gate discharged**: a prompt change applied twice, verified to have actually taken effect at both definition and runtime. `ADR-007` is **upheld** — no supersession needed. `docs/phase8/LEXPOC-GATE.md` |
| 9 | **Budget alarm is tag-filtered and proven with two probes in opposite directions**, each with a value known in advance: it must **include** a known non-zero quantity of *our* spend (the DID's $0.06/day, which accrues on its own) and **exclude** a known non-zero quantity of the sibling's (the $0.84935 Llama training run of 2026-08-10). One probe cannot distinguish a working filter from one that matches nothing — "ignores the sibling" is satisfied perfectly by a filter that ignores everybody. Also: **`IncludeCredit: false`**, per §6.1 of the audit. Marco, granting the approval: *"A tag-filtered alarm that silently matches nothing is the same failure shape as the fingerprint that hashed three files."* See `COST-ATTRIBUTION-AUDIT.md` |
| 15 | ✅ **DONE 2026-08-13. The Stage 2 Lex POC is destroyed once `ADR-007` resolves, pass or fail**, and its own `COSTS.md` line shows the teardown. Marco's condition on approving it separately: *"it has no purpose after `ADR-007` resolves"*. Line C closed at **$0.00825**; residue verified by three independent reads, not asserted |
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
