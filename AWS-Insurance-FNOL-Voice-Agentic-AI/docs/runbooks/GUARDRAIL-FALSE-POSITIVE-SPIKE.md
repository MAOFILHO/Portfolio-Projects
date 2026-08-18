# Runbook — guardrail false-positive spike

This is criterion 5's second half (`PROJECT_STATE.md`:6264 — "incident response for `C14`'s measured
warm-path exceedance and a guardrail false-positive spike"; the `C14` half is
`docs/runbooks/C14-WARM-PATH-EXCEEDANCE.md`).

**Why this wasn't written until now, recorded so a future reader doesn't re-derive the question.** The
deferral was Marco's, not a project decision: he held this document back because `D121`'s fix was expected
to change the guardrail's Terraform config, and writing a runbook against a config about to move would go
stale on arrival. The fix actually adopted — `ADR-017` direction 3-coarse — routes `update_contact_info`
around `guardrails_output_check` in `agents/graph.py`; it touches no Terraform at all. Checked directly:
`git diff --name-only a5441b9^..82dfdb6` (the full `D121`/`ADR-017` fix range) lists `graph.py`,
`graph_structure.py`, `redteam/*`, tests, and docs — zero paths under `infra/terraform`. The premise the
deferral rested on never materialized, so it no longer applies. This document is not blocked on anything
further.

---

## 1. What this runbook is for, and what it is not

This is about a guardrail **false positive** — the guardrail blocking or masking something it shouldn't —
which is the opposite failure direction from what this project's other guardrail-facing checks guard
against. `C1`, `make redteam`, and `scripts/measure_guardrail_safety_interference.py` all exist to catch
the guardrail **under-blocking** (a real attack or injury phrasing getting through, or reaching the caller
unmasked). None of them is built to notice the guardrail catching something benign. A clean run on any of
those three says nothing about this failure class — see §2.

This is **not** a hypothetical. `D89` is on record as a live, reproduced, still-open false positive
(`PROJECT_STATE.md` open item `OI6`, line 872) — a benign `FileAutoClaim` confirmation, blocked by the
`legal_and_medical_advice` denied topic. §3 below is `D89`'s worked example, kept current rather than
described once and left stale. Like `C14`, this runbook must state its own scope caveat up front: no real
caller has ever reached this system (zero inbound calls to the live DID, `CLAUDE.md`'s verified-environment
table) — re-check that table before assuming it still holds. Every trigger and probe below was run against
eval-harness, gate-check, or diagnostic traffic, never a real caller.

---

## 2. Entry conditions — how does an operator get here?

There is no automated alarm for this either — checked directly, same finding as `C14`'s own runbook:
**zero `aws_cloudwatch_metric_alarm` resources exist in this project.** Arrival is always manual, and which
path you came in by changes the first step:

- **`make verify-lambda-execution` fails on event 12.** This is the one mechanism that actually detects
  `D89` today, and it does so deterministically, not statistically. Event 12
  (`scripts/verify_lambda_execution.py:603-622`, transcript `"yes, go ahead and file it"`) asserts
  `_expect_file_auto_claim_filed` (`:429-458`), which in turn asserts `executed_node_intent == "FileAutoClaim"`
  via `_expect_executed_node_intent` (called at `:450`). When `D89` fires, the guardrail short-circuits the
  turn before `route_and_classify` ever runs (§4 below), so `executed_node_intent` is absent and this
  assertion fails — by design, not by accident (the function's own docstring, `:438-444`, states the
  absence is the correct, honestly-reported value on this path). **If this is why you're here, you have
  already found the live worked example** — go straight to §3, this is `D89`, not a new finding, unless
  the failure message doesn't match (see §6 before assuming it's the same defect).
- **Someone reads the operational dashboard's guardrail-usage widget.** `dashboard.tf:156-174` is a raw
  CloudWatch Logs Insights table (`fields @timestamp, @message | filter @message like /guardrail_usage/ |
  sort @timestamp desc | limit 100`) reading the structured line `observability/guardrail_metrics.py`
  emits (`:55-77`) on every `apply_guardrail()` call — `{"metric": "guardrail_usage", "source":
  "INPUT"/"OUTPUT", "blocked": bool, "masked": bool, "units": {...}}`. **This is a table, not a count or a
  threshold** — nothing aggregates `blocked: true` rows or compares them against a baseline rate. A human
  has to notice the pattern by eye.
- **`make redteam` is green (or red) — this is not a signal either way.** Checked directly:
  `redteam/run.py`'s own docstring (`:1-16`) scores two families — injection/PII/fraud attacks (does a
  malicious payload reach caller-facing speech) and escalation jailbreaks (does the system fail to
  escalate an injury). Both are **under-blocking** checks. A false positive on benign content moves neither
  score. Same for `scripts/measure_guardrail_safety_interference.py` (`:1-18`): it measures whether the
  input guardrail blocks **injury/must-escalate phrasings**, a different population from an ordinary
  intent's own confirmation turn. Neither script is a `D89` detector, and neither would have found it.
- **A customer report.** Per §1, no real caller has ever reached this system. Re-verify that premise
  (`CLAUDE.md`'s verified-environment table) before treating the report as evidence about this system at
  all.
- **An internal report** ("the eval harness/simulator hit a refusal on something benign"). Legitimate —
  first step is to reproduce it as a direct `ApplyGuardrail` probe (§3's method) rather than trust the
  transcript alone, since a masked/blocked response and a legitimately-refused one can look similar in a
  log line without checking `action`/`blocked` directly.
- **Nothing, and for the same two reasons `C14`'s runbook names for itself:** no CloudWatch alarm exists to
  page anyone, and the eval-gate CI workflow contains no reference to guardrail blocking rates at all
  (checked the same way as the `C14` runbook did, same file:
  `/Users/marco/K21/Real-world/.github/workflows/aws-insurance-fnol-voice-agentic-ai-eval-gate.yml`). A
  green CI run says nothing about this criterion.

---

## 3. The known, live worked example — `D89`

**Corrected mechanism — the retired "the word 'file'" characterization is banned as a stand-in for this
finding, the same way `C14`'s "19ms" is banned, and for the identical reason: it once compressed a real,
measured finding into a wrong one.** `PROJECT_STATE.md`'s own `OI6` row, written the same day the defect was
found, first stated the trigger as "narrowed to the word 'file', evaluated with no surrounding context." A
33-call live probe the same day (`docs/RESULTS.md` §41, lines 8259–8393) overturned that directly: **every
bare "file" phrasing tested returned `NONE`** — `"file"`, `"file it"`, `"please file it"`, `"file a
claim"`, 8 independent phrasings in total, none blocked. The word alone is not the trigger. It's fine to
say "`D89`" or describe the real mechanism below; what's banned is re-stating "the word 'file' triggers
it," because that specific claim was tested and found false.

**The real mechanism** (`docs/RESULTS.md` §41 §3, confirmed deterministic — repeat calls on the same input
returned identical results every time): the **conjunction** of three elements —

1. an affirmation-or-interrogative frame (`"yes, ..."` / `"should I ...?"`),
2. `"go ahead"`,
3. `"file"` with an object that reads as **"a/the claim"** — including the bare pronoun `"it"` referring to
   one.

Drop any one of the three and the result flips to `NONE`. `"go ahead and file it"` alone (no frame) = NONE.
`"yes, file it"` alone (no "go ahead") = NONE. `"should I go ahead and submit this claim"` (swap the verb) =
NONE. `FileAutoClaim`'s own confirmation prompt — `"...Should I go ahead and file this claim?"` — and its
natural affirmative reply — `"yes, go ahead and file it"` — both independently reproduce the exact shape of
the topic's own listed example, `"Should I sue the other driver?"` (`infra/terraform/stacks/guardrails/main.tf:207`):
same interrogative frame, same permission-seeking shape, `"file"` standing in for `"sue"`.

**Blast radius is confirmed narrow, not assumed.** A later shape-isolation probe (`docs/RESULTS.md` §47 §2)
ran the identical confirmation-seeking shape against `UpdateContactInfo`, `CheckClaimStatus`, and
`RentalTowingEntitlement`'s own natural confirmation phrasings — 0/6 blocked. **Only `FileAutoClaim`'s own
phrasing is implicated.** A control inside that same set — `"should I go ahead and check on your claim
status"`, which contains "claim" but not "file" — also returned `NONE`, narrowing the mechanism further:
neither "file" nor "claim" triggers alone; the collocation of "file" with a claim-referring object, under
the confirmation shape, does.

**Currently live, reconfirmed today (2026-08-18), not trusted from the record alone.** `aws bedrock
list-guardrails --guardrail-identifier zl5ppnyorwd2` shows exactly two versions, `DRAFT` and `5`. `aws
bedrock get-guardrail --guardrail-version 5` reads `legal_and_medical_advice`'s definition and all three
examples byte-identical to `infra/terraform/stacks/guardrails/main.tf:202-211`'s declared text. `aws lambda
get-function-configuration --function-name fnol-codehook` reads `FNOL_GUARDRAIL_VERSION=5` — the deployed
Lambda is pinned to the version that carries this behavior, not a stale one. `git log -- infra/terraform/stacks/guardrails/main.tf`
shows no functional change since `0f50516` (2026-08-12, pre-`D89`); the one later commit,
`f3ebc4b`, is documentation-only by its own message. **The worked example still stands, against today's
actual deployed configuration, not a historical snapshot of it.**

---

## 4. What happens when it fires — a dead end, not a real transfer

Worth knowing before triaging a report, because it shapes what a caller actually experiences. When
`guardrails_input_check` (`agents/nodes/guardrails_nodes.py:35-53`) returns `blocked: True`, the graph
routes straight to `guardrail_blocked_response` (`agents/graph.py:109-114`, edge at `:222`/`:226`), which
returns a fixed line — `_GUARDRAIL_INPUT_BLOCKED_RESPONSE`, `"I'm not able to help with that -- let me
connect you with someone who can."` (`graph.py:96-98`) — and goes straight to `END` (`graph.py:226`).

**That state carries no `escalation` key.** `api/lex_codehook.py:557-559` checks the graph's returned state
for a truthy `escalation` field before calling `_close(..., escalated=True, ...)` at `:573`; the
guardrail-blocked branch never sets that field, so it falls through to the plain `_close(event,
response_text, executed_node_intent=...)` at `:583`, with `escalated` defaulting to `False`. No `escalate="true"` session
attribute, no `EscalationRecord`, no `initiate_escalation()` call. **Confirmed by reading today's code, not
by trusting a prior write-up**: `docs/runbooks/GUARDRAIL-OPERATIONS.md` §4 describes this same gap but was
last touched 2026-08-12 (`git log`), before Phase 8 built the real Connect-level transfer (`$.Attributes.escalate`
→ `TransferContactToQueue`, `PROJECT_STATE.md`:3324) that the general form of this defect (`D43`,
`docs/phase7/NOT-FIXED.md:105-111`) was closed against. That general mechanism now exists and works when
triggered — but this specific path never triggers it, because it never sets the session attribute the
mechanism reads. The caller hears "let me connect you with someone who can" and the call simply ends.

**This is its own filed defect, not merely context — `D140`/`OI58` (`PROJECT_STATE.md`, new Open Items row;
full account `docs/RESULTS.md` §94).** It is not scoped to this one path: the same shape (a transfer-promising
`response_text` with no `escalation` key set) is confirmed at two further sites —
`guardrails_nodes.py:106-107`'s OUTPUT-guardrail-block branch, and `update_contact_info.py:59-63`'s own
`_CONFIRM_CEILING`-exhausted branch. The third one matters beyond this runbook: `ADR-017`'s own accepted
argument leans on that exact ladder "escalating to a human," and `§94` found it doesn't — see that entry for
the full account, not repeated here. Don't re-describe `D140` inline elsewhere; point to the filed item.

Read here, this stays what it was: a spike in `D89` isn't "callers get an inconvenient extra confirmation,"
it's "callers get a promise of a handoff that doesn't happen" — now with a filed defect behind that claim
rather than only this paragraph.

---

## 5. Already tried and reverted — read before proposing a fix

**Two attempts, both on `legal_and_medical_advice`'s Terraform definition, both abandoned. Told in full,
including the correction, because the corrected version is the part worth keeping.**

| Attempt | What happened | Where |
|---|---|---|
| **Attempt 1 (v3→v4): exclusion-clause carve-out**, mirroring `non_auto_insurance_products`'s own `"...is NOT this topic."` pattern | **Failed at `terraform apply`** — `ValidationException`, exceeded Bedrock's documented 200-character cap on denied-topic definitions. The original 188-char definition had 12 characters of headroom, previously unmeasured | `docs/RESULTS.md` §42 (8394–8526) |
| **Attempt 2 (v4): positive re-scoping**, rewording away from an exclusion clause per Bedrock's own guidance | **Applied, then falsified by a live 3-set probe**: 0 of 4 `D89` triggers moved to `NONE` — identical to v3's blocking behavior in every case. **Reverted to v5**, definition restored verbatim to the original v3 text | `docs/RESULTS.md` §43 (8527–8637), §44 (8638–8755) |

**Plainly, before the detail: Attempt 2 was abandoned partly on a premise later found false. It was never
actually disproven on that count — only mis-attributed — so it is reconsiderable, not closed.** Attempt 2
was rejected for two reasons at the time: it fixed none of the 4 `D89` triggers (0/4 — this part is real and
still stands), *and* it appeared to introduce a regression on the topic's own listed example, `"Do I need to
see a doctor for this or will it heal on its own?"`, which stopped blocking. That second reason turned out to
be wrong. Once v5 — the reverted definition, byte-identical to the original v3 wording — was confirmed live
on three independent AWS reads (`docs/RESULTS.md` §47 §0), the identical example produced the identical
`NONE` (§47 §1's v3-equivalence probe). **The gap predates both fix attempts and was never tested before
`D89`'s investigation started** — nobody had run the topic's own canonical example through `ApplyGuardrail`
before that day. It is a real, separate, still-open gap (an under-match on the topic's own example, the
opposite direction from `D89`'s over-match), tracked in the same `OI6` row, but it is not something Attempt 2
caused and not something reverting to v5 fixed. **The operational consequence: Attempt 2's 0/4 result on its
own stated purpose is settled and still disqualifying — but the "it also regresses the medical example"
objection is not a live reason to avoid retrying a similar approach. A future attempt at Attempt 2's general
shape should be evaluated on whether it fixes `D89`'s conjunction, not rejected pre-emptively for a
side-effect that was never real.**

**The standing rule this produced, worth citing rather than re-deriving**: `docs/REVIEW-CRITERIA.md` §10
(lines 297–323) — *"a guardrail (or classifier) `examples` entry is a config input, not a verified
behavior."* Listing a phrase under a topic's `examples` is an instruction to the classifier, not proof the
classifier catches it. Before citing an example as evidence of current behavior — a baseline a rewrite
might have regressed, a control in a comparison set — run it through `ApplyGuardrail` directly.

**Do not re-propose Attempt 2's shape (a positive re-scoping of the definition alone) without addressing
why it failed on its own stated purpose** — 0/4, not a partial success. `docs/RESULTS.md` §47 §3 names two
better-supported candidates, neither built: (a) reword `FileAutoClaim`'s own confirmation prompt off the
collision shape (`"should I go ahead and submit this claim"` already reads `NONE` in the original 33-probe
set), or (b) a more surgical definition edit separating "settling/litigating a claim in a dispute" from
"filing an insurance claim with this agent" — the two turned out to be genuinely close in the definition's
own "settlement negotiations" language, not merely a shape-matching artifact. An `examples` edit is **not**
supported by the shape-isolation data as a next lever (§47 §3) — the retained example does not anchor
confirmation-shaped utterances broadly (the 0/6 six-intents control), so editing it would not be addressing
the actual mechanism.

---

## 6. Separating the two causes of a spike — the response differs

A rise in blocked/masked counts on the guardrail-usage widget (§2) has exactly two possible causes in this
project, and they call for different responses. Check which one before doing anything else.

### Cause A — the guardrail definition itself changed

Something was applied to `infra/terraform/stacks/guardrails` — a deliberate edit, or drift. Check:

```bash
git log -- infra/terraform/stacks/guardrails/main.tf          # was the declared config edited?
terraform -chdir=infra/terraform/stacks/guardrails output guardrail_version   # current published version
aws bedrock get-guardrail --guardrail-identifier zl5ppnyorwd2 \
    --guardrail-version <that number> --region us-west-2      # what's actually live
```

Compare the live read against `main.tf`'s declared text directly — the same method `D89`'s own
investigation used (`docs/RESULTS.md` §41 §1) to rule out drift the first time. If the version number is
higher than the last one recorded in this document, or the live text disagrees with `main.tf`, **this is
Cause A**: a real policy change happened. Response: `docs/runbooks/GUARDRAIL-OPERATIONS.md` §1's
after-any-policy-change checklist (confirm the version incremented, update every pinned caller, and — this
is the one that matters for a false-positive spike specifically — re-run
`scripts/measure_guardrail_safety_interference.py` per §2, because a definition edit can move the
under-blocking risk `C1` cares about at the same time it moves an over-blocking one).

### Cause B — what's arriving at the guardrail changed, definition held fixed

If Cause A's checks come back clean — version unchanged, live text matches `main.tf` — the spike is in the
**population of turns being evaluated**, not the evaluator. In this project that can only mean one of a
small number of things, because nothing rewrites the text the guardrail sees: `agents/graph.py`'s own
pipeline diagram (`:9-23`) shows `l1_safety_check` runs before `guardrails_input_check` and nothing between
Lex's own `turn_input` and the guardrail call modifies that text — `guardrails_input_check`
(`guardrails_nodes.py:36`) calls `apply_guardrail("INPUT", state.get("turn_input", ""))` directly, the raw
value Lex supplied.

- **A new or changed test population** — a new `verify-lambda-execution` event, a new eval/redteam corpus
  entry, a new diagnostic probe — started exercising phrasing that happens to hit `D89`'s known conjunction
  or a shape adjacent to it. Expected, not a regression, if the new phrasing is a variant of `FileAutoClaim`'s
  own confirmation. Check what changed by looking at what's new in the gate/corpus, not at the guardrail.
- **Real caller traffic**, if this project ever has any (currently it does not — §1). A spike from this
  source is the one case that would be genuinely new information, not a rediscovery of `D89`.

**Distinguishing the two in practice**: reproduce the specific blocked utterance as a direct `ApplyGuardrail`
probe (same method as `docs/RESULTS.md` §41/§47 — a handful of real calls, ~$0.0001–0.0005 each at this
guardrail's content+topic-policy pricing). If it matches `D89`'s known three-part conjunction (§3), it's a
recurrence of the known finding, not a new one — go to §7 item 2. If it doesn't match the conjunction but
still blocks, **it's a new trigger shape** — file it as its own defect, the same way `D89` itself was filed,
rather than folding it into `D89`'s already-fully-diagnosed and already-disposed record.

---

## 7. What to actually do

1. Confirm what you're looking at before doing anything else: reproduce the exact blocked utterance as a
   direct `ApplyGuardrail` call and check it against `D89`'s minimized conjunction (§3). Don't assume a
   report is `D89` just because it involves a block on a `FileAutoClaim`-shaped turn — check the actual
   phrase.
2. **If it matches `D89` exactly**: this is a known, open, already-fully-diagnosed defect (`OI6`,
   `PROJECT_STATE.md`:872) — not a new incident. No emergency action is required; confirm it's still `OI6`
   and move on, the same "no action required for a documented, accepted state" posture `C14`'s own runbook
   takes for its exceedance.
3. **If §6 identifies Cause A** (the definition changed): stop before proposing anything — this needs
   `GUARDRAIL-OPERATIONS.md` §1's post-edit checklist and §2's safety-interference re-measurement, and,
   per the STOP CONDITIONS, no Terraform apply against this stack proceeds without the same discipline any
   other change to it gets.
4. **If it's a new trigger shape**, not `D89` and not a definition change: file it as its own defect with
   its own minimized repro (§3's method is the template — isolate which elements of the phrase are
   necessary, don't stop at the first blocking example). Do not extend `D89`'s own fix proposals (§5) to
   cover it without checking whether they actually would — Attempt 2's own history is the reason not to
   assume a definition-level fix generalizes.
5. Any proposed fix — for `D89` or a new finding — must address why the two prior attempts (§5) don't
   already cover it: Attempt 1 never reached runtime (apply-time character-cap failure), Attempt 2 reached
   runtime and measurably failed its own purpose (0/4). A proposal that doesn't engage with why those two
   were abandoned is repeating work already done, not advancing past it.
