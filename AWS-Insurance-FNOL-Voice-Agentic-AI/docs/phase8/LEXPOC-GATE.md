# `ADR-007`'s POC gate — result

**Phase 8, Stage 2. Run 2026-08-12/13. Verdict: `ADR-007` is upheld. It is not superseded.**
**Stack destroyed 2026-08-13, zero residue. Exit criteria 8 and 15 discharged.**

---

## 1. What was being decided

`ADR-007` chose nested CloudFormation `AWS::Lex::Bot` over native `aws_lexv2models_*`, and was unusually
candid about the asymmetry in its own evidence: the rejection of the native option rests on two
**confirmed**, dated, open provider bugs, while the choice of this option rests on the **absence** of a
confirmed one. It refused to call that resolved and wrote a mandatory POC into its consequences section:

> Build the smallest `AWS::Lex::Bot` stack that exercises the FNOL intent with
> `PromptAttemptsSpecification` and `DTMFSpecification`, apply it, change a prompt, apply again, and
> confirm the change actually took. If it does not, `ADR-007` is superseded here — not worked around.

Marco, on approving Stage 2: *"if the second apply silently no-ops, do not work around it. That is
`ADR-007` resolving against native `aws_lexv2models_*`, and the answer is nested CFN or CDK — which is
what the three-way comparison was for. Report the result before choosing."*

It did not silently no-op. The rest of this document is what the throwaway found on the way there, which
turned out to be worth more than the verdict.

## 2. How it was tested

`infra/terraform/stacks/lexpoc` — an eleven-slot `FileAutoClaim` intent with explicit `SlotPriorities`,
a `PromptSpecification` on every slot, and `PromptAttemptsSpecification` +
`AudioAndDTMFInputSpecification` + `DTMFSpecification` on the two digit-only slots. Slot inventory and
prompt wording taken from `docs/phase4/SLOT-DESIGN.md` §1.1–1.2, not invented, so that a defect found
here is a defect that would have been found in the real bot.

**Three instruments, at three depths, because they can disagree and the disagreement is the finding:**

| | Reads | Answers |
|---|---|---|
| **DECLARED** | `terraform output` | what Terraform rendered into the template |
| **DEFINITION** | `DescribeSlot` on the DRAFT bot | the artifact |
| **RUNTIME** | `RecognizeText` against the test alias | what a caller is actually told |

Stopping at DEFINITION would have been `RESULTS.md` §3.5 for a fifth time — a guard that checks the
artifact rather than the outcome. The two are not the same object here: the definition is what the
locale build *reads*, not what it *serves*.

**A negative control ran alongside every assertion.** `police_report_number`'s DTMF `endTimeoutMs` is
hardcoded in the template while `policy_number`'s is templated, so the gate asserts an expected
non-change beside the expected changes. An update mechanism that rewrote the whole locale, and one that
reported success while changing nothing, are indistinguishable from a pass if every observed field moves
together.

**And the gate itself was proven able to fail.** `tests/unit/test_lexpoc_gate.py` — 15 tests, each
mutating the recorded evidence into the failure it claims to catch: #42147's signature, a stale build,
a run compared against itself, a control field that moved, a truncated slot list, a reordered priority
list, a merge-not-replace deletion. A guard only ever seen to pass is not known to work.

## 3. The three applies

| Apply | Change | Template SHA | Result |
|---|---|---|---|
| 1 | create | `bbe0002…` | 3 resources, 38 s. Definition, runtime and declaration agree |
| 2 | **prompt string** `What's your policy number?` → `Okay. What is your policy number? It starts with P Y.` **and** DTMF `endTimeoutMs` 5000 → 3000 | `c2c23e2…` | **Both took**, at definition *and* runtime. Control slot held at 5000. Bot id unchanged — an in-place update, not a replacement |
| 3 | **removed** a message group | `131bd75…` | The deleted message stopped being served. The update replaces, it does not merge |

Evidence: `docs/evidence/phase8/lexpoc-apply-{1,2,3}.json`, recorded by `scripts/lexpoc_gate.py` at the
time each apply landed.

```
lexpoc-gate: lexpoc-apply-1.json -> lexpoc-apply-2.json
  ok   the update reached the deployed bot
  ok   before: declared == definition == runtime
  ok   after:  declared == definition == runtime
```

Apply 3 answers a question the gate as written did not ask, and the more dangerous one. A mechanism that
merges rather than replaces applies every edit correctly and quietly keeps everything you deleted — which
looks like a working pipeline right up until the thing you deleted was deleted for a reason.

## 4. Four findings, none of which was the verdict

### 4.1 The locale build finishes *after* CloudFormation reports success

`CREATE_COMPLETE` at 38 s, with the locale at `ReadyExpressTesting`. `Built` arrived ~16 s later. The
same gap appeared on all three applies.

**Consequence for Stage 3:** a `terraform apply` that has returned successfully does not mean the bot is
built. Anything that depends on a built locale — an `AWS::Lex::BotVersion`, the Connect bot association,
a post-deploy smoke test — can race a green apply. This has to be an explicit wait, not an assumption,
and "it worked when I ran it" will be the usual evidence for the assumption.

### 4.2 A bot created by CloudFormation cannot be spoken to unless you say so

`RecognizeText` failed with `The BotAliasId TSTALIASID does not have Language en_US enabled`.
`TestBotAliasSettings.BotAliasLocaleSettings[].Enabled` must be set explicitly, and **AWS's own
`AWS::Lex::Bot` reference example does not set it**.

The failure mode is the interesting part: every control-plane read reports a healthy bot. It builds, it
lists, `DescribeBotLocale` says `Built`. Only an attempt to actually talk to it fails. A deployment
pipeline that validated the bot by describing it would have shipped this.

### 4.3 `MessageSelectionStrategy: Ordered` does not do what Phase 4 assumed

`SLOT-DESIGN.md` §4 specifies that on the **first** no-match for a digit-only slot the reprompt
proactively offers the keypad — an F7 mitigation feeding the "repair success rate ≥ 0.80" target. That
was authored as two ordered message groups.

Lex plays **one message from every message group on every attempt**, concatenated. `Ordered` selects
among `Variations` *within* a group; it does not walk groups across retries. Recorded in
`lexpoc-apply-2.json`, the opening turn of the conversation:

```
"What is your policy number? …"  +  "Sorry, I didn't catch that. You can also enter it on your keypad…"
```

The caller is apologised to for a mistake they have not yet had the chance to make.

**Per-attempt prompt text is not expressible in `PromptSpecification` at all.** The DTMF-offer repair
belongs in the codehook (Stage 4), as an `ElicitSlot` with its own message. `SLOT-DESIGN.md` §4 carries a
dated correction pointing here. This is the finding that most justifies the POC: it is a live dialogue
defect, it would have shipped, and no amount of reading the schema would have surfaced it.

### 4.4 `ListSlots` pages at 10, and the intent has 11

An unpaginated read returns a complete-looking set of ten slots with `other_party_involved` silently
missing. Same shape as everything else in this project's instrument-defect history: the wrong answer
arrives confidently and correctly formatted. `_paginate_slots` exists for this, and a test asserts the
count.

Related: `slotPriorities` come back keyed by **slot ID**, unordered. Checking that the elicitation order
Phase 4 designed is the order that deployed requires resolving IDs to names first — and safety is
priority 1, so this is not a cosmetic ordering.

## 5. Two things confirmed that were previously assumed

- **The `Project` tag reaches the bot.** CloudFormation propagated all five stack-level tags to the Lex
  resource, verified with `ListTagsForResource`, not inferred from the stack. Stage 0's rule — activation
  is not propagation — applied to a new resource type before relying on it.
- **The intent↔slot cycle (#39948) genuinely does not arise.** Eleven slots with explicit priorities, one
  resource body, no `null_resource`, no out-of-band CLI. This was `ADR-007`'s main structural claim and it
  now has a measurement behind it rather than an argument.

## 6. What this gate does **not** establish

Stated plainly, because the temptation after a pass is to treat it as broader than it is.

1. **Nothing about published versions or aliases.** Everything here ran against `DRAFT` and the built-in
   test alias. Stage 3 associates Connect with a **version**, and a version snapshots a built locale — so
   the staleness question of §4.1 re-opens in a different shape there and is not answered by this pass.
2. **Nothing about DTMF actually working on a phone call.** `DTMFSpecification` was verified as
   *configuration that deploys and updates*. Whether a caller pressing keys is understood is criterion 1's
   job, and only a real call tests it.
3. **Two fields moved, not the schema.** One string and one nested integer. That covers #42147's family
   and #36845's family respectively, which is what the ADR asked for — it is not exhaustive.
4. **`aws_cloudformation_stack` is still an opaque box in `terraform plan`.** Observed directly: the plan
   reports that `template_body` changed, not which prompt changed. `ADR-007` accepted this as the cost of
   avoiding #39948 and the acceptance stands, but Stage 3 loses per-field review on every bot change and
   should not pretend otherwise.

## 7. Cost

Approved as **line C** in `COSTS.md`, separately from the phase, on Marco's condition that a resource
created to test whether we can create resources gets its own accounting and is destroyed when it has
served its purpose.

| Item | Units | Cost |
|---|---|---|
| Lex bot, locale, 11 slots, custom slot type, at rest | 3 applies + 1 destroy | **$0.00** — Lex bills per request only; no charge for storage or for a locale build |
| IAM role + inline policy | 2 resources | $0.00 |
| CloudFormation stack | 1 | $0.00 |
| `lexv2-models` control-plane reads | ~40 | $0.00 |
| `RecognizeText` runtime probes | **11 text requests** | **$0.00825** |
| **Total** | | **≈$0.008** |

**Destroyed 2026-08-13.** `0 added, 0 changed, 3 destroyed`. Verified after the fact rather than
asserted: `list-bots` empty, `list-stacks` empty, `get-role fnol-lexpoc-runtime` returns `NoSuchEntity`.

The stack directory stays in the repository, with its state key and an empty state. `scripts/lexpoc_gate.py`
stays too and fails loudly if run against the torn-down stack, which is the correct behaviour for a gate
whose subject no longer exists. The findings outlive the resource; the resource does not outlive the
question.
