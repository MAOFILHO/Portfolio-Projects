# What is AWS already measuring that we have been measuring ourselves?

**Asked once, deliberately, before Stage 3 — on Marco's instruction, 2026-08-13.**

> "This project's instrument defects have mostly been discovered by building a better instrument. This
> one was discovered by noticing an independent instrument already existed, free, and had been running
> the whole time. Ask once, explicitly, before Stage 3: what else is AWS already measuring that we have
> been measuring ourselves? Connect contact records, Lex conversation logs, and Lambda metrics are all
> candidates, and all of them are about to matter."

The prompting case: `COSTS.md`'s Bedrock figures were written by the code that makes the calls, and
CloudWatch `AWS/Bedrock` had been counting the same calls independently, for free, since Phase 3. Nothing
ever looked. The log turned out to under-report by 22%.

## The counterweight, stated first

**"AWS already measures it" does not mean "AWS's instrument is the better one."** Two counterexamples
from this same phase, so this is not a hypothetical hedge:

- **Cost Explorer is the AWS instrument for cost, and it was the wrong one.** It reported $0.00124 against
  an actual $0.52540 — 0.24% — because of settlement lag. Our self-reported log, defective as it was, was
  three orders of magnitude closer.
- **Lex conversation logs would measure exactly what Phase 6 measures by hand, at the price of persisting
  raw caller transcripts** — which collides head-on with `ADR-011`'s redaction boundary. Adopting it
  without reading the fine print would trade an instrument gap for a privacy breach.

So the rule this survey produces is not *prefer AWS's instrument*. It is: **know it exists, and choose
deliberately.** An instrument you didn't know about isn't a decision you made.

---

## The inventory

| # | AWS already measures | Cost | We measure it by | Verdict |
|---|---|---|---|---|
| 1 | **CloudWatch `AWS/Bedrock`** — `Invocations`, `InputTokenCount`, `OutputTokenCount` per `ModelId` | free | `COSTS.md`, computed from our own logs | ✅ **Adopted** at Stage 0.5. Found the 22% under-report |
| 2 | **Lambda `InitDuration`** — cold-start time, on every cold start, in the `REPORT` line and as a metric | free | Phase 9 plans to *measure cold-start impact against the 1,800 ms budget* | ✅ **Adopt.** `ADR-009`'s central number is already being recorded by AWS. Phase 9's job shrinks to interpreting it |
| 3 | **Lex analytics — `ListUtteranceMetrics` / `ListAggregatedUtterances`** — `Count`, **`Missed`**, `Detected` per utterance, grouped and binned | free | Phase 6's no-match and containment counting, by hand over the eval set | ✅ **Adopt as a second instrument.** `Missed` is production no-match; the eval harness measures the same construct on a fixed set. They answer different questions and disagreeing is informative |
| 4 | **Connect contact records** — per-contact transactional record, **24-month retention natively**, queryable via `SearchContacts`/`DescribeContact`/`GetMetricDataV2` | free | nothing yet | ✅ **Adopt — and note the trap.** Kinesis streaming is for *extended* retention and analytics; the records exist and are queryable without it. Enabling data streaming is an instance-level **console** setting (a fifth portal click, criterion 6) *and* a billable Kinesis stream. Both avoidable, and only avoidable if you know the records exist anyway |
| 5 | **Lex slot `ObfuscationSetting`** — Lex replaces a slot value with `{slot_name}` in conversation logs | free | `ADR-011` + our own redaction pipeline | ✅ **DECIDED `D70`** — enabled as defence in depth, never as the boundary; **and no conversation logs in Stage 3** without an `ADR-011`-compatible redaction pass in front of them. See below — its exclusions land squarely on our design |
| 6 | **Bedrock model invocation logging** — full request/response + token breakdown **per invocation**, to CloudWatch or S3 | free feature, storage billed | `COSTS.md`'s per-run figures are computed estimates; #1 gives daily aggregates only | ❌ **DECLINED `D70`, reason recorded rather than re-discovered.** It is the only thing that makes per-run cost *exact*. It also persists complete prompts — i.e. redacted-or-not caller utterances — for the whole account, not per-project. Revisit only with an `ADR-011`-compatible retention and redaction story |
| 7 | **DynamoDB `ConsumedRead/WriteCapacityUnits`** | free | estimated in the cost model | ✅ **Adopt** at Stage 5. Exact beats estimated when exact is free |
| 8 | **`AWS/Lex` runtime metrics** — request count, latency, invalid-Lambda-response count | free | the latency budget is currently measured only in the simulator | ✅ **Adopt.** `RuntimeSuccessfulRequestLatency` is measured on the real path; constraint 14's 1,800 ms p95 has never been observed on anything but our own harness |
| 9 | **CloudTrail** — every control-plane call, incl. who changed a bot or flow | free (management events) | nothing | ➖ **Note only.** Single operator; no drift-attribution problem to solve yet |
| 10 | **AWS X-Ray** | 100k traces/mo free | OTel node tracing, planned | ➖ **Defer to Phase 11** on its merits, not because it was overlooked |

## Two of these change Stage 3's design, not just its dashboards

### Slot obfuscation has three exclusions, and our design walks into all three

From AWS's own documentation, verbatim in substance:

1. *"Any slot values in missed utterances won't be obfuscated."* A caller misreading their policy number
   produces a **no-match**, and the raw utterance is logged unobfuscated. Digit-only identifiers are the
   slots most likely to no-match — `SLOT-DESIGN.md` §4 exists because of exactly that — so the values
   most worth protecting are the ones most likely to escape.
2. *"If you are using slot values in your prompts or responses, those slot values are not obfuscated."*
   Our confirmation policy **reads the policy number back digit-grouped**. The read-back is a response.
3. *"Amazon Lex doesn't obfuscate slot values that you store in request or session attributes."*

**Consequence:** obfuscation is worth enabling and cannot be the boundary. `ADR-011`'s redaction stays
where it is. If conversation logs are enabled at all in Stage 3, they need selective capture plus the
same redaction pass as every other sink — the feature name promises a guarantee the footnotes withdraw.

**Decided `D70`, 2026-08-13.** Obfuscation on; conversation logs off in Stage 3; invocation logging
declined. Marco's reasoning is the durable part, and it generalises past Lex:

> *"No-match data is recoverable later at no privacy cost while identifiers in logs are not removable."*

**The two sides of a telemetry-versus-privacy trade are not symmetric in time.** A deferred measurement can
be taken later; a logged identifier cannot be un-logged. Where the trade is close, the reversible side wins
by default — with the corollary that the deferral has to be *recorded*, or "we can get it later" becomes
"we never got it." Instrument #3 is what makes the deferred side cheap here: `ListUtteranceMetrics` reports
production no-match **counts** without persisting utterance text, so most of what conversation logs were
wanted for costs nothing in privacy terms.

### Contact records make the tag schema question sharper, not softer

`CONTACT-TAG-SCHEMA.md` rejected `Intent` and `Outcome` as contact tags because a contact tagged
`Intent=InjuryEscalation`, joined to a contact record carrying the caller's number, is a health-adjacent
inference in the billing system. Contact records are the other half of that join, they retain for **24
months**, and they are free and already on. That does not change the decision — it confirms the join is
real and cheap for anyone with read access, which was the reason.

## Where this leaves the generalisation

Three of this project's instrument findings came from **building** a better instrument: `fixture_is_stale()`,
the composed-pipeline fingerprint, the mask-vs-block parser. One came from **noticing** one already
existed. The second kind is cheaper and this survey is the attempt to have it on purpose rather than by
luck — but the survey's own output is that the free instrument is sometimes worse (Cost Explorer) and
sometimes a liability (invocation logging). The reusable move is not "adopt AWS's"; it is **"count the
instruments before trusting the one you wrote."** A single instrument cannot be wrong, because there is
nothing for it to disagree with.
