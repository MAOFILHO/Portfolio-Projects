# Cost attribution audit — can the `Project` tag actually reach the money?

**Phase 8, Stage 0. 2026-08-12.** Written because Marco made it a condition of `APPROVED: Phase 8`:

> On the tag-filtered alarm: activate the cost allocation tag in Stage 0 as you've scoped it, and verify
> the tag actually propagates to the Connect and Lex resources before relying on the filter. A
> tag-filtered alarm that silently matches nothing is the same failure shape as the fingerprint that
> hashed three files.

That framing is exact, and the audit found the failure it predicted. The plan's Stage 5 wording —
*"Filter on `Project=AWS-Insurance-FNOL-Voice-Agentic-AI`, which requires activating that cost allocation
tag first"* — treats activation as the work. **Activation is not the work.** A tag key can be Active while
no billing line item in the account carries it, and the resulting alarm reads $0.00 forever. It does not
error, it does not warn, and it is indistinguishable from a project comfortably under budget.

This is `RESULTS.md` §3.5 in a new costume: *a guard that checks the artifact rather than the outcome is
not a guard.* Checking that the tag is Active checks the artifact. Checking that a dollar of Connect spend
lands under the filter checks the outcome.

---

## 1. What was done

| | |
|---|---|
| `Project` cost allocation tag | **Activated** 2026-08-12 via `ce update-cost-allocation-tags-status`. No portal click |
| Status verified | `ce list-cost-allocation-tags --status Active` returns exactly `Project`, `Type: UserDefined` |
| Data availability | Up to 24h before it appears in billing data, and it is **not retroactive** — everything before activation stays untagged forever |

Activation is necessary and it is done. The rest of this document is about whether it is sufficient, per
line item. It is not.

---

## 2. The audit, per cost line item

The test applied to each row is not "can this resource hold a tag" — nearly everything can. It is **"does
the billing record for this charge carry the tag."** Those are different questions and the gap between
them is where the silent failure lives.

| Cost line item | Aug gross | Does `Project=` reach the billing record? | What it actually needs |
|---|---|---|---|
| **Canada DID daily** `USW2-CA-did-numbers` | $0.06/day | **Unverified — testable 2026-08-13.** The phone-number resource carries the tag, but the charge is sold by a third party (see §3) | Empirical check once tag data accrues |
| **Connect voice service minutes** | $0 so far | ❌ **NO.** Bills are *"summarized at the AWS account level by usage type"* by default | **Contact tags**, set per contact — see §4 |
| **Lex V2 speech requests** | $0 so far | ✅ **Yes, at the alias.** *"you can allocate costs for each alias using tags specific to the alias"* | Tag the bot **alias**, not just the bot |
| **Bedrock on-demand inference** | $0.00124 (ours) | ❌ **NO.** System-defined `us.*` cross-region profiles are not taggable | An **application inference profile** — see §5 |
| **Bedrock guardrail evaluations** | included above | ❌ Same as above — no taggable resource on the invocation path | Same as §5, if it applies to `ApplyGuardrail` at all (unconfirmed) |
| Lambda, DynamoDB, S3, CloudWatch | $0.00 | ✅ Yes. Ordinary resource tags via provider `default_tags` | Already handled |
| S3 state bucket | $0.00 | ✅ Yes | Done in Stage 0 |

**Two of the three largest cost sources in this project — Connect voice and Bedrock inference — do not
carry the tag by default, and neither fails loudly.** Had the alarm been built as the plan described it,
it would have been filtering on a tag that matched the state bucket and nothing that costs money.

---

## 3. The DID charge is sold by a third party, which is why it was never found

Standing open question since Phase 0, closed here.

`CLAUDE.md` recorded the Canada DID rate as **STILL UNCONFIRMED**, with the note that *"Cost Explorer
showed no Amazon Connect line at all."* That observation was true and the inference drawn from it was
wrong. There is no Amazon Connect line because **the charge is not filed under Amazon Connect.** It is
filed under:

```
Contact Center Telecommunications (service sold by AMCS, LLC)
```

A separate seller, sorting elsewhere in every service-grouped view. Looking for "Amazon Connect" would
never have found it no matter how long we waited, and "wait for a full billing period" would have
produced the same empty result in September.

With the right service name, the rate falls out of two independent days:

| Day | Usage qty (days) | Cost | Implied rate |
|---|---|---|---|
| 2026-08-11 | 0.8388 | $0.05033 | **$0.06000 / day** |
| 2026-08-12 | 0.1667 | $0.01000 | **$0.06000 / day** |

**`USW2-CA-did-numbers` = $0.06/day = $1.83/month.** Twice the US rate ($0.03/day) and at the top of Phase
0's $0.90–$3.00 guess. 7.3% of the $25 ceiling, permanently, for a number that must not be released.

The generalisable lesson is small and sharp: **a $0.00 reading and an absent line item look identical in a
grouped cost report, and only one of them means "no spend."** The second day's row is what makes this a
measurement rather than a division — one day alone could have been a proration artifact.

---

## 4. Connect voice: instance tags are the wrong tags, and they look right

This is the specific trap. The obvious move is to tag the Connect instance — it is the resource, it is
untagged today (`list-tags-for-resource` returns `{}`), tagging it is one API call, and afterwards every
`ListTagsForResource` check passes.

**It would not attribute a single cent.** AWS documents instance tags as serving *tag-based access control*
— *"build tailored authorization through tag-based access control (TBAC)"* — and documents cost attribution
for Connect usage as a separate mechanism entirely:

> By default bills for Connect Customer channels (voice calls, chat, tasks, and emails) are summarized at
> the AWS account level by usage type. […] To obtain a more detailed view of your bill and usage, you can
> add cost allocation tags (key:value pairs) **to contacts**.

And, flatly: *"Contact tags only function as cost allocation tags."*

So the tag has to be on the **contact**, set per call, by a **`Contact tags` block in the contact flow** or
the `TagContact` API. That makes it **a Stage 3 contact-flow requirement**, not a Stage 5 billing
configuration — a dependency that did not exist in the plan and that would have been discovered, if at all,
by noticing months later that the Connect line was missing from a tagged report.

Constraints found while reading, all load-bearing:

- **Maximum 6 user-defined tags per contact.**
- **A tag edited more than 3 hours after disconnect never reaches billing** — the contact record updates,
  the bill does not. Tagging is a call-time act, not a reconciliation one.
- **No PII in tags.** AWS states this explicitly, and for an FNOL system whose contacts carry claim
  numbers and policy numbers this is a real rule, not boilerplate. The tag value is the project name.

### The more robust filter, and why it cannot be turned on yet

Connect emits **system-defined** contact tags on every contact without any flow configuration:

- `aws:connect:instanceId`
- `aws:connect:systemEndpoint` — the phone number the caller reached

Either would attribute **all** Connect spend correctly with no dependence on our flow being written
correctly, which makes them strictly better than a user tag we have to remember to set. This account has
exactly one Connect instance and one DID, both ours, so either key is a complete and unambiguous filter.

**But neither is activatable today.** `ce list-cost-allocation-tags --type AWSGenerated` lists five keys
and no `aws:connect:*` among them: the keys only come into existence once contacts do, and no call has ever
been placed. Sequence consequence, which belongs in the plan:

> **Activate `aws:connect:instanceId` immediately after the first real call (criterion 1), then wait up to
> 24h.** Connect coverage in the budget alarm is necessarily *behind* the first call. Criterion 9 cannot be
> fully discharged before criterion 1, and any ordering that assumes otherwise is wrong.

Belt and braces is the right posture here: set the `Project` contact tag in the flow **and** activate the
system-defined key when it appears. The first is under our control and testable in the simulator; the
second cannot be broken by a flow edit.

---

## 5. Bedrock: the `us.*` profile cannot be tagged, and there is exactly one way around it

Constraint 17 requires invocation through US cross-region inference profiles (`us.*`), never a hardcoded
regional model ID. Those profiles are **system-defined**, and system-defined profiles carry no tags. So
today every Bedrock dollar this project spends is unattributable.

The account makes this concrete. August Bedrock gross, by usage type:

| Usage type | Aug gross | Whose |
|---|---|---|
| `USW2-Llama3-3-70B-Customization-Training` | **$0.84935** | sibling fine-tuning project |
| Llama 3.3 70B inference (4 usage types) | $0.03264 | sibling |
| `USW2-NovaMicro-*`, `USW2-NovaLite-*`, `USW2-TitanEmbeddingV2-*` | **$0.00124** | **ours** |

**The sibling project is 99.86% of this account's Bedrock spend.** This is the tag filter's entire
justification, restated as a measurement rather than the plan's forecast — and it is precisely the service
where the tag currently cannot reach.

AWS's answer is **application inference profiles**: a user-created profile that wraps a model *or a
system-defined cross-region profile*, carries tags, and is passed as `modelId` in place of the model
string.

> To create an application inference profile for multiple Regions, specify a cross Region (system-defined)
> inference profile. […] Usage and costs for requests made to the Regions in the inference profile will be
> tracked.

That wrapping is what makes this compatible with constraint 17 rather than a violation of it: the
`modelSource` remains `us.amazon.nova-micro-v1:0`, routing stays cross-region US, and only the identifier
passed at call time changes from a profile ID to a profile ARN. **The constraint's substance is preserved
and its literal wording is not** — which is an ADR, not a silent config change. Recorded as an open
decision below rather than actioned inside Stage 0.

Documented limit, worth knowing before anyone expects too much of it:

> Application inference profiles deliver aggregated billed dollars to AWS Cost Explorer and CUR. The finest
> grain is **per usage type per day**; they do not produce per-request cost.

Per-run cost in `COSTS.md` therefore stays a computed estimate. The profile makes the *daily total*
attributable and auditable — which is what a budget alarm needs — and does not make per-run figures
measured. §6 is why that distinction currently matters a great deal.

---

## 6. Two findings that fall out of the same data

### 6.1 The account is on credits, and `CLAUDE.md` says the opposite

`CLAUDE.md` states: **"Assume no promotional credits on this account."** That is wrong, and it is wrong in
the direction that disables the budget alarm.

Grouping by `RECORD_TYPE` shows usage and credit cancelling to approximately zero every month:

| Month | Usage | Credit | Net |
|---|---|---|---|
| 2026-06 | $12.4417 | −$12.4417 | ~$0 |
| 2026-07 | $0.4315 | −$0.4315 | ~$0 |
| 2026-08 (to 08-12) | $2.5955 | −$2.5955 | ~$0 |

Net cost for August month-to-date is **−$0.0000005646**. Every default cost view on this account reads
zero while $2.60 of real usage accrues.

**Consequence for the alarm, and it is the whole ballgame:** AWS Budgets defaults to a cost type that nets
out credits. A $25 budget on this account with default settings **cannot ever fire** — not because spending
is controlled, but because the number it watches is pinned near zero by credits that will one day run out,
at which point the same $25 becomes reachable with no warning at all.

The budget **must** be configured `IncludeCredit: false` (and `IncludeRefund: false`), so it tracks gross
usage. This is the identical failure shape to the tag filter, one layer down, and it was found only because
the tag question forced a look at how the account actually bills. Neither would have announced itself.

There is no public API for remaining credit balance; it is Billing-console only. So the honest statement is:
**gross usage is the number this project manages against, and the credit balance is an unknown buffer, not
a budget.**

### 6.2 `COSTS.md` and Cost Explorer disagree about our own Bedrock spend by ~300×

`COSTS.md` reports **≈$0.411** across Phases 3–7 against the $5 standing cap. Cost Explorer's gross for our
Nova Micro, Nova Lite and Titan usage types is **$0.00124** for all of August.

Not reconciled, and deliberately not resolved by picking the convenient number. Candidates:

1. **Cost Explorer lag.** Real, but 08-11 — the day Stage 8 ran — shows *no* Bedrock line at all, and
   08-12 shows $0.00120. Lag explains a delay, not a two-order-of-magnitude gap.
2. **`COSTS.md` over-estimates.** Plausible on arithmetic: $0.40 of Nova Micro input at $0.035/1M is 11.4M
   tokens, which this project's measured volumes do not support.
3. **Guardrail evaluations billed elsewhere or mostly free.** No `Guardrails` usage type appears at all,
   despite hundreds of `ApplyGuardrail` calls in Phase 7. The `…FreeUnits` counters in `GuardrailResult.usage`
   may account for it — that is checkable against the captured `usage` blocks.

It matters in both directions. If $0.411 is a large over-estimate, then every "spend so far" figure this
project has published is wrong, and future phases have been reasoning under a false constraint. Phase 8's
criterion 13 is about logging spend *accurately*, and an unreconciled 300× discrepancy is a failure of that
criterion whichever way it resolves.

**Owner: Stage 5, after Cost Explorer has settled for 2026-08-11/12.** Recorded as open rather than closed.

---

## 7. Open decisions this audit creates

| # | Decision | Owner |
|---|---|---|
| A | Application inference profile for Bedrock cost attribution — needs an ADR against constraint 17's literal wording. Marco's call, not a config change | Stage 5, **ask first** |
| B | `Contact tags` block in the contact flow, value `Project=…`, ≤6 tags, no PII | Stage 3 |
| C | Activate `aws:connect:instanceId` after the first real call, then wait 24h | Stage 5, gated on criterion 1 |
| D | Budget configured `IncludeCredit: false` / `IncludeRefund: false` | Stage 5 |
| E | Tag the Lex bot **alias**, not only the bot | Stage 2 |
| F | Reconcile `COSTS.md` ≈$0.411 against Cost Explorer's $0.00124 | Stage 5 |
| G | Verify the AMCS-sold DID line item carries the tag once data accrues | 2026-08-13 |

---

## 8. Criterion 9, restated so it cannot be passed by activating a tag

The original wording — *"Budget alarm is tag-filtered and demonstrated to ignore the sibling project's
spend"* — is satisfiable by an alarm that ignores **everyone's** spend, including ours. Ignoring the
sibling is the easy half; a filter matching nothing does it perfectly.

The criterion is discharged when **both** hold:

1. A tagged report attributes a **known, non-zero** quantity of *our* spend — the DID's $0.06/day is the
   natural probe, since it accrues without us doing anything.
2. The same report **excludes** a known non-zero quantity of the sibling's spend — the $0.84935 Llama
   training run of 2026-08-10 is the natural probe, since it has already happened.

Two probes, opposite directions, both with a number known in advance. One probe alone cannot tell a working
filter from a broken one.
