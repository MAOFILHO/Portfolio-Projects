# CLAUDE.md — AWS-Insurance-FNOL-Voice-Agentic-AI

### STOP CONDITIONS — absolute, no exceptions

- No phase begins without written exit criteria from the prior phase and my explicit approval.
- No billable AWS resource is created without me typing `APPROVED: <phase name>`.
- The Amazon Connect instance and DID already exist. Never create either.
- `PROJECT_STATE.md` is updated before any session ends.
- Restate these four conditions verbatim at the top of every session summary and after every `/compact`.

---

## What this project is

An agentic, voice-first **First Notice of Loss (FNOL)** intake system for **P&C auto** insurance, built on
Amazon Connect + Lex V2 + Bedrock + LangGraph. Portfolio-grade prototype: small scale, minimal cost,
architecturally honest. Everything a production system would have is present and *functional* — IaC, CI/CD,
evals, guardrails, observability, tests, runbooks — just sized down.

**Nothing may be stubbed out and labelled "production would do X here." If it's in the README, it runs.**

Health and life claims are explicitly out of scope. Scope is P&C auto only.

### The six in-scope intents — exactly six, no additions

1. **File a new auto claim** — multi-slot: policy number, date/time, location, vehicles, injuries. The slot-filling showcase.
2. **Check claim status** — tool call into the mock claims system.
3. **Coverage question** — RAG against synthetic policy wordings. Primary groundedness eval target.
4. **Rental / towing entitlement** — RAG plus tool call. The compound case.
5. **Update contact info** — write path; requires an explicit confirmation policy.
6. **Injury or fatality mentioned** — immediate hard-coded escalation from any state. No negotiation, no slot filling, no LLM discretion.

---

## Non-negotiable constraints

### Cost
- **COST GATE.** No provisioning, `terraform apply`, or billable resource creation until Marco types `APPROVED: <phase name>`. Before every provisioning step, print a table: resource → SKU/tier → free-tier coverage → estimated monthly cost at demo volume → cost if teardown is forgotten. **Verify pricing against current AWS sources; never from memory.**
- **Standing approval (granted):** Bedrock on-demand inference for Phases 3–7, **capped at $5 total**, logged per-run in `COSTS.md`. Provisioned resources are still gated individually.
- Default to always-free SKUs; where none exists, cheapest viable, stated out loud.
- **Banned by default** (require written justification + approval): OpenSearch Serverless, Kendra, provisioned-throughput Bedrock, Aurora (any flavor), NAT Gateway, always-on ECS/EKS/Fargate, Contact Lens real-time analytics, SageMaker endpoints, MSK, Connect Voice ID, Connect Cases, multi-AZ anything.
- Destroyable in one command, rebuildable in one command. `make destroy` must leave a $0 footprint (excluding the protected DID). Budget alarm + cost dashboard ship day one, not at the end.
- **Hard ceiling: $25/month.** Not a target.

### Engineering
- **Zero portal clicks.** 100% IaC. Only permitted manual steps: the pre-provisioned Connect instance, admin user, and DID, plus (added 2026-08-11, Marco-approved) the one-time Connect Customer → Connect Customer Basic instance-tier switch — no IaC path exists for it. All four documented in `docs/runbooks/MANUAL-STEPS.md`.
- Python 3.12 backend (`>=3.12,<3.13`), React + TypeScript + Vite frontend. **Terraform ≥1.9** (ADR in Phase 2). Mixing Terraform and CDK is forbidden.
- No secrets in code, ever. SSM standard parameters preferred (free) or Secrets Manager. `.env.example` only.
- Everything runs locally without AWS: LocalStack/moto, plus a call simulator that replays audio/text turns through the agent.
- Conventional commits, semantic versioning, pre-commit hooks (ruff, black, mypy, terraform fmt, tflint, detect-secrets, gitleaks).

### Responsible AI
- PII redaction on every transcript before it is persisted or logged. Recordings off by default, opt-in flag.
- Bedrock Guardrails on input **and** output. Prompt-injection defence on anything retrieved from the KB or returned by a tool.
- Explicit AI disclosure in the greeting. Human escalation always reachable, including a hard "agent" barge-in intent that works from any state.
- **No invented metrics or capabilities anywhere in docs.** If something is projected or simulated, label it as such.

### Voice turn-latency budget
End-to-end turn latency from Lex STT completion to Polly audio stream start must stay **under 1,800 ms (p95)**.
If a tool call is projected to exceed 1,000 ms, the graph must support interim audio fillers ("Let me check
that for you…") or stream response tokens immediately. Cold-start impact is measured in Phase 9 and addressed
in an ADR. Provisioned concurrency requires cost-gate approval — prefer a scheduled warmer, smaller
deployment package, or SnapStart first.

### Telephony (constraint 16) — read before touching `infra/terraform`
The Connect instance and DID **already exist**. Terraform consumes the instance via a **data source or
import**; it must never run create-instance and never create a second instance. The phone number lives in
`infra/terraform/stacks/telephony` with `prevent_destroy = true`, in **separate state that `make destroy`
does not touch**. Releasing and re-claiming numbers risks a **180-day claim block**.

The number carries `Protected=true` as a tag — **the telephony stack's import guard asserts this tag** before
proceeding. Contact flows, queues, hours of operation, Lex association and Lambda association are all
Terraform-managed and destroyable; the instance and number are not.

### Single-region rule (constraint 17)
Connect, Lex V2, Lambda, DynamoDB, S3 and Step Functions all live in **us-west-2**. Bedrock is invoked via
**US cross-region inference profiles (`us.*`)**, never a hardcoded regional model ID — this is *mandatory*,
not stylistic: `amazon.nova-micro-v1:0` supports only `INFERENCE_PROFILE`. Region is a Terraform variable
and must never appear as a literal in application code; a region migration must be a tfvars change, not a refactor.

### Recording stays off (constraint 18)
No contact flow may enable call or screen recording. In the modern (2019-10-30) flow schema there is **no
`RecordingBehaviorOption`** — recording state is purely the participants array:

```json
{ "Type": "UpdateContactRecordingBehavior",
  "Parameters": { "RecordingBehavior": { "RecordedParticipants": [] } } }
```

Empty array = off. **CI check** fails the build if any flow contains an `UpdateContactRecordingBehavior`
action whose `RecordedParticipants` is non-empty, or if any flow file contains `AnalyticsBehavior`,
`ContactLens`, or `RealTimeContactAnalysis`. Flow files are globbed **by content** (presence of an `Actions`
or `modules` key), **not by `.json` extension** — some upstream exports have no extension.

---

## Verified environment facts

Checked against live AWS and current pricing pages. Re-verify rather than trusting this table if a decision
turns on it — several of these change monthly.

| Fact | Value |
|---|---|
| Account / identity | `759316130780` — `arn:aws:iam::759316130780:user/marcos-mlops` |
| Region | `us-west-2` |
| Connect instance | `eba56246-0368-4f1c-8b97-e2ab3b0e8246` alias `marcos-ivr-demo`, ACTIVE, `CONNECT_MANAGED`, inbound-only |
| Connect access URL | `https://marcos-ivr-demo.my.connect.aws` |
| **DID (Canada, not US)** | `+14169871547`, id `55cba0a6-3f67-4982-b3d8-6943d3b07054`, `PhoneNumberCountryCode: CA`, CLAIMED |
| DID tags | `Project=AWS-Insurance-FNOL-Voice-Agentic-AI`, `Owner=marcos`, `Protected=true` |
| Bedrock profiles ACTIVE | `us.amazon.nova-micro-v1:0`, `us.amazon.nova-lite-v1:0`, `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `us.anthropic.claude-3-haiku-20240307-v1:0` |
| Embeddings | `amazon.titan-embed-text-v2:0` (ON_DEMAND), **$0.02 / 1M tokens** |
| Nova Micro pricing | **$0.035 / 1M input · $0.14 / 1M output** — re-verified 2026-08-11, corrects an earlier $0.075/$0.30 figure |
| Nova Lite pricing | **$0.06 / 1M input · $0.24 / 1M output** — re-verified 2026-08-11, corrects an earlier $0.13/$0.52 figure |
| Claude Haiku 4.5 pricing | **$1.00 / 1M input · $5.00 / 1M output** — from Anthropic's own docs by exact Bedrock model ID; not independently re-confirmed against the AWS Price List API, which omitted all modern Anthropic models from its live us-west-2 dump on 2026-08-11 |
| Claude 3 Haiku pricing | $0.25 / 1M input (confirmed via AWS Price List API) · $1.25 / 1M output (widely cross-referenced, not independently re-confirmed against a primary AWS source on 2026-08-11) |
| Cross-region inference profile surcharge | **None** — confirmed via AWS docs: "no additional cost associated with cross-region inference" for `us.*` profiles |
| Lex V2 pricing | $0.004 / speech request · $0.00075 / text request · **no perpetual free tier** (re-confirmed 2026-08-11) |
| Connect voice — **tier switch DONE 2026-08-11** | Instance is on **Amazon Connect Customer Basic**. Voice service **$0.015/min for the first 5M min/month** (tier 2: $0.0125/min) — re-verified 2026-08-12 against the Connect Customer pricing appendix, and this **corrects the earlier $0.018/min figure**. Telephony is billed separately on top. The AI-bundled **Amazon Connect Customer** tier ($0.038/min) was the default on our instance and was switched away from, because `ADR-001` deliberately does not use its bundled AI. Manual console step, Marco-approved, recorded in `docs/runbooks/MANUAL-STEPS.md` §4 |
| **Canada DID daily rate — CONFIRMED 2026-08-12** | **`USW2-CA-did-numbers` = $0.06/day = $1.83/month**, twice the US rate, 7.3% of the ceiling, permanent. Measured on two independent days (0.8388 days → $0.05033; 0.1667 days → $0.01000), not divided from one. **The charge is filed under `Contact Center Telecommunications (service sold by AMCS, LLC)`, not under Amazon Connect** — which is why every earlier search found nothing and would have kept finding nothing in September. A $0.00 reading and an absent line item look identical in a grouped cost report. The **per-minute inbound** rate is still unmeasured; it needs a real call. `docs/phase8/COST-ATTRIBUTION-AUDIT.md` §3 |
| Cost Explorer API is **not free** | `ce:GetCostAndUsage` and friends bill **$0.01 per request**. Cheap, but the tool used to control cost is itself a cost line, and a polling loop over it would be a genuinely stupid way to breach a $25 budget. Batch queries; do not poll |
| Guardrails | $0.15 / 1k text units (content filters, denied topics) · $0.10 / 1k (PII, contextual grounding) · **regex-based sensitive-information filters are FREE** (AWS pricing page, verbatim: *"Sensitive information filters (regular expression) - Free"*, re-verified 2026-08-12) · Automated Reasoning checks ~$0.17/unit, **exact unit unconfirmed** — re-verify before relying on this line |
| Guardrail usage is **measurable, not estimable** | Every `ApplyGuardrail` response carries a `usage` block (`topicPolicyUnits`, `contentPolicyUnits`, `sensitiveInformationPolicyUnits`, `…FreeUnits`, …). `GuardrailResult.usage` captures it as of Phase 7 Stage 8, so guardrail rows in `COSTS.md` are exact from that point on. **Bedrock does not evaluate the sensitive-information policy on `source="INPUT"`** — verified live, that counter is always 0 on input |
| Guardrails call model | `ApplyGuardrail` (and the newer, 2026 `InvokeGuardrailChecks`) run **decoupled from any model invocation** — callable anywhere in application control flow, not only bolted onto `Converse`/`InvokeModel`. Load-bearing fact for `ADR-010` |
| Call recording | **disabled** |

⚠ **The "12-month free tier" is largely gone.** AWS's current framing (checked 2026-08-11): new accounts get
"$100 in credits immediately... up to $200 over 6 months"; a separate, account-age-independent "30+ services
always free within monthly usage limits" layer persists (Lambda 1M req + 400k GB-s, DynamoDB 25 GB storage
only — **not** free RCU/WCU in on-demand mode, Step Functions 4,000 transitions, CloudWatch/SNS basics).
S3 Vectors has no free tier.

🔴 **"Assume no promotional credits on this account" was WRONG — corrected 2026-08-12.** This account is on
credits, and they currently offset **100%** of usage: grouping by `RECORD_TYPE` gives usage $12.44 / credit
−$12.44 (June), $0.43 / −$0.43 (July), $2.60 / −$2.60 (August MTD). Net August cost is
**−$0.0000005646**. Every default cost view on this account reads ~$0 while real money accrues.

Two consequences, both binding:

1. **Any AWS Budget must be configured `IncludeCredit: false` and `IncludeRefund: false`.** A $25 budget
   with default settings on this account can never fire — not because spending is controlled, but because
   the number it watches is pinned near zero by credits. When those credits run out, the same $25 becomes
   reachable with no warning at all. This is the same silent-nothing failure as a tag filter that matches
   nothing, one layer down.
2. **Manage against gross usage** (`RECORD_TYPE = Usage`), never net. The remaining credit balance has **no
   public API** — Billing console only — so it is an unknown buffer, not a budget.

⚠ **Telephony is the dominant marginal cost per conversation, ~$0.15–0.20 depending on which Connect tier
applies (see above) — Bedrock is noise by comparison even before the Nova pricing correction, and more so
after it.** The call simulator is therefore the **primary cost control**, not a convenience — ~100 real
calls would still consume a meaningful share of the monthly budget even at the lower Customer Basic rate.

---

## Commands

```bash
make bootstrap    # one-time local + state backend setup
make deploy       # provision everything destroyable      (alias: provision)
make destroy      # return to $0; never touches stacks/telephony  (alias: teardown)
make eval         # eval report with real numbers
make redteam      # guardrail effectiveness report
make test         # unit + lifecycle-phased suites
make lint         # ruff + black + terraform fmt + tflint
make typecheck    # mypy strict
make simulate     # call simulator, no AWS spend
make verify-billable   # read-only: assert no unexpected billable resource exists
```

`bootstrap`/`deploy`/`destroy`/`eval`/`redteam` are the canonical names (per the Definition of Done);
`provision`/`teardown` are aliases kept for consistency with sibling projects in the monorepo.

---

## Monorepo conventions (this is a folder inside `MAOFILHO/Portfolio-Projects`)

Git root is `/Users/marco/K21/Real-world`, remote `git@github.com:MAOFILHO/Portfolio-Projects.git`.
Naming convention is `<Cloud>-<Domain-Descriptor>-<AI|ML>`, Title-Case-Hyphenated.

**GitHub Actions reads workflows only from the repository root.** A `.github/workflows/` directory inside a
project folder is silently ignored — no error, no warning. Workflows are therefore authored in
`.github/workflows-for-monorepo-root/` with a project-name prefix, `paths:`-scoped to this folder, each job
setting `working-directory`, and copied to the monorepo root on install. Repo variables are prefixed
(`FNOL_*`) so they cannot collide with a sibling project's settings.

Layout follows the sibling project `AWS-Bedrock-Agentic-FineTuning-Platform`:
`src/<pkg>/`, `infra/terraform/`, lifecycle-phased `tests/{unit,pre_provision,post_provision,post_run,post_teardown}`,
`docs/{COST-ACTUALS,RESULTS,LESSONS-LEARNED,INCIDENT-LOG}.md`.

### Scope rule — writes outside PROJECT_ROOT

> Writes outside PROJECT_ROOT require explicit approval, requested by ABSOLUTE
> PATH, before the change. Monorepo convention is not pre-authorisation. Three
> known future instances: the root .gitignore (done), /Users/marco/K21/Real-world/
> .github/workflows/ (Phase 10), and the root README project index (Phase 12).
> Each gets its own approval.

`PROJECT_ROOT` is `/Users/marco/K21/Real-world/AWS-Insurance-FNOL-Voice-Agentic-AI`. The git root is its
parent, so **being in the same git repository does not make a file in scope** — that includes the monorepo
root `.gitignore` and `README.md`, `.github/workflows/`, and every sibling project.

**None of the three instances above is pre-approved. Ask when you reach it.**

Two corollaries, from how this rule was actually earned:

1. Name the **absolute path** when requesting approval — not "the root config", not a bare filename.
2. If a change crosses a boundary that a plan or verification criterion asserted, **say so plainly and record
   the criterion as violated**. Do not let it lapse silently. Approval of a change's *intent* is not licence
   to go quiet about its *scope*. See `PROJECT_STATE.md` → D9/D10 and the Phase 0 verification table, where
   item 1 is recorded as knowingly violated rather than marked passed.

---

## How to work here

- **Plan first.** No application code or provisioning before approval.
- **TDD on the agent core and tool layer**: test first, watch it fail, implement, refactor.
- **Plan mode for anything touching Terraform.** Always show `terraform plan` output and the cost delta before apply.
- Use a subagent per phase where it isolates context; keep the main thread as the integrator.
- Update `PROJECT_STATE.md` at the end of every working session. Run `/compact` after each phase sign-off.
- Commit at every meaningful checkpoint, conventional commits. Never commit generated artifacts, `.tfstate`, or anything matching a secret pattern.
- Ambiguity that materially changes the design → **stop and ask**. Cosmetic → decide and note it in `PROJECT_STATE.md`.
- Prefer boring, well-supported libraries. Pin versions. Justify every new dependency in one line.
- **Search for current AWS capabilities, quotas, model availability by region and pricing** rather than relying on memory.
- ADRs are immutable once accepted — supersede, never edit.

### Do-not-propagate list (from Phase 0 archaeology)

The eight source repos under `/Users/marco/K21/Temp/CallCenter/AWS` are **read-only**; never modify them and
never write into them. Three artifacts must never enter this project:

1. AWS account ID `482186147085` (inside repo 5's Lex export zip) — hand-author the bot instead of importing.
2. VIN `1HGCF86461A130849` — a structurally valid Honda VIN that may map to a real vehicle. Generate our own with a deliberately invalid check digit.
3. `dl_AZ.jpg` / `dl_MA.jpg` / `dl_OH.jpg` — DMV specimen licences containing real human face photographs.

**Blanket rule: vendor no images from any source repo.** Also never carry forward the leaked account IDs
`117026838272` / `123255318457`, the plaintext password `insurance_db_password123`, the `999999` OTP bypass,
`cert_reqs='CERT_NONE'`, or the live `webhook.site` URLs.

See `docs/phase0/` for the merge matrix, dependency conflicts, domain artifacts and security findings.
