# ADR-017: `D121`'s fix — `EMAIL`/`PHONE` PII masking on `UpdateContactInfo`'s readback

**Status: PROPOSED, NOT DECIDED.** Every other ADR in this project is written once accepted
(`docs/adr/*.md`, grepped: all five existing ADRs read `Status: Accepted`). This one is committed in
draft form, deliberately deviating from that convention, because Marco's own instruction reserved the
decision step (`/grill-with-docs`) for his explicit invocation and it has not run this session — writing
this as "Accepted" would mean adopting a decision nobody has actually made. Flagged here rather than left
silent, per this project's own standing practice of surfacing convention deviations rather than letting
them pass. **Do not treat this document as settled until its Status line changes.**
**Date:** 2026-08-16 (Phase 12, Block 2)
**Supersedes:** nothing yet — no prior ADR addressed `D121`'s outcome.

---

## Context

`D121`/`OI39` (`RESULTS.md` §76, `PROJECT_STATE.md` `OI39`): `UpdateContactInfo`'s confirmation readback
(`update_contact_info.py:54,69`, `f"That's {filled['new_value']} -- is that right?"`) speaks the caller's
new value verbatim. For `field=email`/`field=phone`, the guardrail's `EMAIL`/`PHONE` PII entities
(`ANONYMIZE`, `infra/terraform/stacks/guardrails/main.tf:236-237,246`) mask it on OUTPUT to a literal,
unconfirmable placeholder — `"That's {EMAIL} -- is that right?"` — confirmed live (`§76`). The one
allowed retry (`_CONFIRM_CEILING = 1`) re-asks the identical masked string and escalates every time.
`UpdateContactInfo` cannot reach fulfillment by voice for two of its three field values. `field=mailing_
address` is unaffected — `ADDRESS` is not a configured entity.

`§77` triaged this **FIX NOW**, explicitly not scoped that session: "it needs a design decision, a
guardrail version bump, a redeploy, and a `C1` cycle — that is a fresh session's work." This document is
that fresh session's design output, not its execution — **no Terraform edit, no version bump, no redeploy,
no `C1` cycle has run.**

### Input side is clean — ruled out as a contributing cause

`§78`: Bedrock never evaluates the sensitive-information policy on `source="INPUT"` at all
(`guardrails_nodes.py:35-53`, live-verified Stage 8), and `filled['new_value']` traces directly from Lex's
own `interpretedValue` (`lex_codehook.py:454-469`) with nothing guardrail-shaped upstream. The masking
happens only at the OUTPUT call, only because the confirmation string speaks the value back. This rules
out "the caller's input is somehow corrupted or mis-captured" as a contributing cause and confirms the
defect is entirely in *how the confirmation is worded*, not in what data reaches the node.

### `§8` mechanism sweep — is this the only instance of the outcome?

`REVIEW-CRITERIA.md` §8 (extended after `D121`): a fix must enumerate every mechanism capable of the same
outcome, not just every other call site of the same mechanism — the `D16`→`D121` gap was exactly a
call-site sweep that missed a different mechanism producing the identical outcome. Full sweep:
`docs/audits/2026-08-16-d121-guardrail-mechanism-sweep.md`.

**Verdict: `EMAIL`/`PHONE` via `UpdateContactInfo`'s readback is the only live, structurally reachable
instance of "caller's own data masked back to them" among the six in-scope intents.** Content filters and
denied topics can only `BLOCK`, never mask (different outcome, `D89`'s class). Word filters and custom
regexes are absent from the live config entirely. The other five configured PII entities
(`CREDIT_DEBIT_CARD_NUMBER`, `US_SOCIAL_SECURITY_NUMBER`, `CA_SOCIAL_INSURANCE_NUMBER`, `DRIVER_ID`,
`PASSWORD`) are configured but never reachable — no node in this codebase ever echoes a card, SSN, SIN,
driver-ID, or password value back to a caller, confirmed by reading all 27 `response_text` call sites
directly. One residual gap named, not audited: a caller volunteering PII-shaped text inside a free-text
slot (`coverage_topic`, `entitlement_type`) could in principle surface in a generated answer — a different
mechanism shape, not measured.

**Consequence for scope**: whichever direction is chosen, it needs to fix exactly one readback
construction (`update_contact_info.py:54,69`) against exactly two entity types. It does not need to touch
content filters, denied topics, or the other five PII entities — the sweep found no second instance for
those to have to account for.

---

## The candidates

### Direction 1 — remove `EMAIL`/`PHONE` from the OUTPUT PII entity list

`infra/terraform/stacks/guardrails/main.tf:236-237`, drop the two entries from the `for_each` set. Mirrors
the v2→v3 precedent exactly: the four `D16` regexes were removed for the identical stated reason ("masking
a caller's own identifier back to them is a defect with no upside," `docs/phase7/NOT-FIXED.md` #8) — this
would be the same tradeoff, applied to a different mechanism reaching the same outcome the sweep above
confirms is otherwise unique to these two entities.

**What this does not touch**: the other five PII entities, all content filters, both denied topics — the
sweep found nothing else depending on `EMAIL`/`PHONE` remaining configured. **What it gives up**: any
guardrail-layer backstop against the agent *generating* an email or phone number somewhere unintended
(e.g., a future LLM-generated free-text path, per the sweep's own residual gap) — today that backstop is
inert everywhere except the one intended path it breaks, so the loss is theoretical, not measured against
any live-caught case.

### Direction 2, as Marco originally specified — spelled/phonetic or grouped-digit readback of the full value

**Empirically falsified this session, not merely untested** (`RESULTS.md` §79, 6 probes against live
`zl5ppnyorwd2` v5). Spelling an email letter-by-letter or NATO-phonetic still classifies as `EMAIL` and
masks identically to the raw address. Reading phone digits individually or grouped still classifies as
`PHONE` and masks — one variant (`phone_grouped_digits`) produced a *malformed partial mask*, replacing one
mid-sequence token and leaving digit fragments on both sides, a strictly worse shape than the clean
single-token replacement `D121` already documented. **Filed as its own defect, `D122`/`OI44`
(`PROJECT_STATE.md`), not folded into this ADR's evidence for direction 2's falsification** — a
confidentiality failure (most of the real digits leak in plain text while the guardrail reports a
successful intervention), distinct in kind from `D121`'s clean-but-unconfirmable over-masking. **A spelled
or grouped full-value readback trades one unconfirmable placeholder for another, sometimes a more broken
one. This variant of direction 2 should not be built.**

### Direction 2′ — partial-disclosure readback (new candidate, surfaced by this session's probes, not proposed by Marco, not evaluated for viability)

Two follow-up probes (`§79`): a short email prefix (`"the address starting with m, a, r, c, o, s"`) passed
with **no intervention** — `masked: False`, `action: NONE`, the original text would reach the caller
unchanged. The phone equivalent (`"the number ending in one, five, four, seven"`) **still masked**. The two
entities do not behave symmetrically under partial disclosure, and only one partial shape per entity was
tested — this is a signal that a partial form *can* survive, not a measured boundary for either detector.

Open questions this document originally did not resolve, named for the grilling session:

- Where does `EMAIL`'s detector actually start firing as more of the address is spoken? One 6-character
  prefix passed; a longer prefix, or one containing `@`, might not.
- Where does `PHONE`'s detector stop firing? Four bare digits already triggered it — is any digit sequence
  above some short length unsafe, regardless of framing?
- Does a partial value give a caller enough signal to actually confirm identity, or does it just move the
  "confirmation is unconfirmable" problem from a placeholder token to an ambiguous fragment ("ending in
  1547" could match many numbers a caller might mis-hear as their own)?
- A partial-disclosure design also does not fully address Marco's original stated motivation — voice
  transcription failure on the *full* value — since it deliberately never speaks the full value to catch a
  transcription error in it.

**Closed on requirements, 2026-08-17 — explicitly NOT falsified.** `/grill-with-docs` Round 1 (below):
the readback's governing purpose is STT-accuracy confirmation (catching a voice-transcription error in
the value itself), stated by Marco as the requirement independent of any code reading, not inferred from
`update_contact_info.py`'s current wording. A partial value cannot reveal a transcription error in the
part it never speaks, so direction 2′ cannot satisfy that requirement regardless of where its detector
boundaries eventually turn out to sit — the four bullets above are answered "moot," not "resolved." No
probe was run against direction 2′ to establish this; it was disqualified before reaching the empirical
question `§79`'s two partial probes only began to sketch. **A future reader must not read this as "tested
and failed"** — it is "ruled out on what it would have needed to do," a different and weaker kind of
closure than direction 2's (which *was* tested to failure, `§79`).

### Direction 3 — leave the guardrail config untouched; skip the OUTPUT `ApplyGuardrail` call for
`update_contact_info_node`'s output specifically (new candidate, Marco, Round 2)

Narrower in one specific sense than direction 1: `EMAIL`/`PHONE` masking stays configured and available to
every *other* node, rather than being removed from the guardrail globally. Needs no `main.tf` edit, no
guardrail version bump, no `stacks/main` redeploy — a code change to this project's own routing, plus its
eval cycle.

**Structural reachability, checked before any merits argument (`/grill-with-docs` Round 2), full account
below in the grilling log.** Direction 3 exactly as first scoped — "skip it for the confirmation turn
specifically" — is **not reachable at today's graph routing granularity**: `guardrails_output_check` is one
shared node, reached from all five intent nodes through a single conditional-edge function
(`graph.py:104-107`, `_after_intent_node`) that branches only on `bool(state.get("response_text"))`, with
no notion of which node — let alone which of `update_contact_info_node`'s five internal branches — produced
it. Hitting only the two `D121` readback sites would need a new state flag plus a new conditional-edge
branch; a **coarser** version — skip OUTPUT for the whole `update_contact_info` node, all five branches —
*is* directly reachable today (one destination change in an existing routing map) and is what "coarse, if
Direction 3 is chosen at all" (Round 2 Q1, below) resolved to build, on the strength of one supporting fact:
`update_contact_info_node` never calls an LLM — every branch is a fixed string or an f-string over a slot
value/enum/exception string, never model-generated prose — so the coarse version's added exposure over the
precise one is bounded by that same shape, not by anything open-ended.

**What this gives up, priced, not waved past (Marco's own framing):** skipping the call for this node drops
content-filter and denied-topic coverage for it too, not only `EMAIL`/`PHONE`. Its content being
template-plus-slot-value rather than generated prose bounds that risk but does not remove it, and no test
in this codebase today asserts `guardrails_output_check` dominates the graph the way `assert_dominates`
does for `l1_safety_check` — direction 3 would be the first deliberate, permanent bypass of a node with no
such invariant guarding it, and the invariant it would need to add ("dominates, except these named
exceptions") is structurally weaker than the one it replaces.

---

## `/grill-with-docs` session log, 2026-08-17 — Round 1 (direction 1 vs. 2 vs. 2′)

**Q1 — what is the readback for: STT-accuracy confirmation, or write-consent confirmation?** Marco: (a),
STT-accuracy confirmation — stated as the requirement independent of `update_contact_info.py`'s current
wording, not inferred from it. (The recommendation offered during grilling had inferred the same answer
from the code; Marco's correction: that is inferring a requirement from an implementation, which tells you
what the previous author did, not what the system must do. The conclusion holds — on the stated-requirement
grounds, not the code-reading ones. Recorded that way here, not the other.) This is what closes direction 2′
on requirements above.

**Q2 — is giving up the guardrail-layer PII backstop (direction 1) acceptable, given the sweep found it
inert everywhere else?** Marco: acceptable, but not to be recorded as "inert" — "never fired on a real case"
is an argument from absence, bounded by what the sweep actually searched (`REVIEW-CRITERIA.md` §6).
Correct framing: **acceptable for the paths the sweep enumerated**, with the free-text-slot gap
(`coverage_topic`; see the erratum above — `entitlement_type` was wrongly named alongside it and does not
carry this risk) explicitly still open, untouched by either direction, and now gating direction 1 itself
(Round 2, below).

**Q3 — close direction 2′ (full-value spelled/grouped readback) now, or spend a session characterizing its
detector boundaries first?** Marco: close now, on requirements (Q1), not on the falsification direction 2
already received. Do not spend a session probing boundaries for a candidate disqualified before reaching
them. Record precisely: **closed on requirements, not falsified** — see the closure note above, inline
where direction 2′ is defined, not only here.

## Round 2 (direction 1 vs. direction 3)

Structural reachability established first, per Marco's instruction, before any merits argument — full
account inline under direction 3, above. Summary: `guardrails_output_check` is one shared node with no
`assert_dominates`-style invariant guarding it; `update_contact_info_node` has five `response_text`
branches, not one "confirmation turn"; the node never calls an LLM, which bounds a coarse whole-node skip's
added exposure to the same template-plus-slot-value shape the precise, two-branch version would have had
anyway.

**Q1 — coarse whole-node skip, or a new flag gated to just the two readback branches, if direction 3 is
chosen at all?** Marco: coarse, agreed — the no-LLM fact is the right basis for that.

**Q2 — does direction 3 need a dominance test as a companion, regardless of scope?** Marco: agreed, and
this is the strongest structural argument against direction 3 on its own terms — it would be the first
deliberate bypass of a node with no dominance test today, and the test it would need to add ("dominates,
except these named exceptions") is a weaker invariant than the one it replaces.

**Q3 — does skipping the Terraform version-bump/redeploy/`C1`-cycle machinery materially favor direction
3?** Marco: agreed it isn't load-bearing, but **do not record it as ordinary friction** — a guardrail
version bump plus redeploy is the exact operation class that produced `D97`/`OI14`'s outage in this
project (`RESULTS.md` §45–§47). Recorded here as **the operation with a prior outage precedent in this
project**, not as "recoverable in one session."

**Q4 — is keeping `EMAIL`/`PHONE` configured for hypothetical future nodes speculative generality, given the
sweep found no live node reaching them today?** **Marco's pushback, not accepted as offered.** The
"currently zero benefit" framing was itself an argument from absence over a path the sweep explicitly
marked unaudited: `coverage_question.py`'s free-text `coverage_topic` slot, fed into the only
LLM-generated `response_text` path in the system. That is the one place `EMAIL`/`PHONE` could be doing real
work today, not hypothetical future work — §6 applied to the side of the argument that favored direction 1,
not only the side that favored keeping the entities. **Consequence: direction 1 is Marco's lean, but
conditional on auditing that path first.** If it is real (a caller-volunteered PII string in `coverage_topic`
can reach the model's generated `answer` unmasked), direction 1 removes the only live PII backstop in the
system to fix an unrelated node, and the choice reopens.

## Free-text PII audit — scoped 2026-08-17, **rate probe run 2026-08-17 (Round 3)**

**Question, corrected 2026-08-17 (Marco):** this was never one question — it was an existence question
("can this path happen at all") bundled with a rate question ("how often"). **The existence question is
answered by the code trace alone and was never actually gated on a probe.** The magnitude the probe measures
changes how often the backstop matters, not whether the path exists — so this section's original framing
("audit — NOT run," implying the whole question was open) was a gate left standing by inertia after its
own evidence had already closed half of it. Recorded here as a correction to this document's own prior
framing, not a quiet edit.

**Existence — settled by code trace, not by the probe below.** Exactly one slot qualifies, not two — see
the sweep erratum above: `entitlement_type` is a closed two-value Lex slot (`EntitlementTypeValues`,
`bot.yaml.tftpl:161-176`) and cannot carry caller free text into `rental_towing.py` at all.
`coverage_topic`, by contrast, is `AMAZON.FreeFormInput` (`bot.yaml.tftpl:627`), genuinely unconstrained,
and reaches the model directly: `coverage_question.py:88` quotes it verbatim into the LLM's `user_message`
(`f'Caller\'s question: "{coverage_topic}"'`), `generate_response()` runs against the default generation
model (`us.amazon.nova-lite-v1:0`, flaggable to `us.anthropic.claude-haiku-4-5-20251001-v1:0`,
`config/settings.py`), and the returned `answer` becomes `response_text` with **no post-filtering** before
reaching the same shared `guardrails_output_check` node every other intent uses. `_COVERAGE_SYSTEM_PROMPT`
instructs the model "Do not restate the caller's question" — a soft, instruction-following constraint, not
a code-level guarantee. **The path is real. Direction 1-global's "the entities are dormant" premise was
false before any probe ran**, and Round 2 Q4's conclusion (direction 1 conditional on this audit) rested on
existence, which needed no probe to confirm.

**Rate — run 2026-08-17, real, small-n.** Seven real calls: one control (`coverage_topic` with no PII) plus
six probes crossing PII shape (email/phone, the same synthetic fixtures `§76`/`§79` already established:
`marcos@gmail.com`, `416-987-1547`) × position in the utterance (start/middle/end) — same order of magnitude
as `§79`'s 8-probe design, cost pre-approved by Marco at that order. Each probe: one real
`generate_response()` call against the live default model (`_COVERAGE_SYSTEM_PROMPT` verbatim, a static
synthetic policy-text stand-in for `search()`'s retrieved text — the KB retrieval mechanism itself is not
what this probe tests), then one real `ApplyGuardrail` OUTPUT call (`BedrockGuardrailClient`, live
`zl5ppnyorwd2` v5) against the real `answer`. Script: `coverage_topic_pii_probe.py`, session scratchpad,
one-off, not the permanent gate. Cost: $0.0002 (Converse) + $0.0028 (guardrail) ≈ **$0.0030**, logged in
`COSTS.md`.

**Result: 0/6 PII-embedded probes had the caller's email or phone echoed verbatim in the model's generated
answer.** Nova Lite obeyed `_COVERAGE_SYSTEM_PROMPT`'s "do not restate the caller's question" instruction
across all six positions/shapes tested; the OUTPUT guardrail read `action: NONE` on all seven calls
(nothing to catch, because nothing was echoed). **Stated at the same epistemic level `§79` used for its own
small-sample findings, not stronger:** this is a real, measured 0% rate on n=6, one model
(`us.amazon.nova-lite-v1:0`), one system prompt, one synthetic policy-text context, one caller persona style
— a signal about this specific configuration, not a proof that no `coverage_topic` phrasing, model, or
future prompt edit could ever produce an echo. The path stays real (existence, above); its observed
*frequency* under current conditions is low, not zero-by-construction.

**Round 3 Q1 — confirmatory run against the flagged alternate model, Marco's instruction.** The generation
model is flag-flippable (`us.amazon.nova-lite-v1:0` ↔ `us.anthropic.claude-haiku-4-5-20251001-v1:0`,
`config/flags.py`); a 0/6 rate on only the default model says nothing about the alternate one, and either
could be live in production. Same 6 PII-embedded probes, re-run against `ALTERNATE_GENERATION_MODEL_ID`
directly (`generate_response()` takes no model override by design, so `coverage_topic_pii_probe_alt_model.py`
replicates its exact call construction against the alternate constant rather than flipping the live flag).
**Result: 0/6 again. Combined: 0/12 across both flaggable generation models.** Cost: $0.0056 (Claude Haiku
4.5 is priced far above Nova Lite — $1.00/$5.00 vs. $0.06/$0.24 per 1M — so this half of the combined run
cost nearly twice the first half despite fewer calls), logged in `COSTS.md`. Same epistemic ceiling as
before: 0/12 is a stronger signal than 0/6, still not a proof, still one system prompt and one synthetic
context across both runs.

**Round 3 Q2 — the existing transcript-redaction regex (`redact_for_transcript()`, `EMAIL_RE`/`PHONE_RE`,
`ADR-011`) as a second-layer mitigation on `coverage_question.py`'s answer specifically, applied before
speech rather than before persistence.** Marco's instruction: this bears directly on the Round 2/3
tradeoff, not a bolt-on to whichever direction wins — but only after two checks, run this entry, not
assumed.

**Check 1 — coverage, not existence, of the regex pair itself (`coverage_check.py`, $0, pure regex, no
AWS calls).** Two parts:

- *Against the actual 12 probe outputs* (all 13 real strings from both live runs, transcribed verbatim,
  no new calls): none contained the caller's email or phone — matching the 0/12 echo result already
  measured. **There was nothing for the regex to catch in this sample; that is a limit on what this check
  can show, not evidence the regex works.** Recorded as such, not glossed as a passing test.
- *Against the two PII fixtures directly* (`marcos@gmail.com`, `416-987-1547`), independent of what the
  12-sample run happened to produce — this is the part that actually answers "would it catch it if it
  were there": `EMAIL_RE.search("marcos@gmail.com")` **matches**. `PHONE_RE.search("416-987-1547")`
  **does not.** Read `PHONE_RE`'s own definition (`guardrails/pii.py:112`) and its docstring comment:
  the pattern requires a literal `555` exchange segment — it is scoped to this project's *synthetic test
  data convention* (`docs/phase0`, e.g. `"555-0142"`), not to phone numbers generally. **A real caller's
  real phone number, in production, would never contain a `555` exchange and this regex would not match
  it, ever, by construction — not a sampling gap, a design scope gap.** `EMAIL_RE` is a general-purpose
  pattern and generalizes to a real caller's real email; `PHONE_RE` does not generalize to a real caller's
  real phone number at all. **The two entities this mitigation would need to cover are not symmetrically
  covered by it.**

**This finding is bigger than this ADR's own scope, and is filed separately, deliberately not folded in
here: `D124`/`OI46` (`PROJECT_STATE.md`).** `redact_for_transcript()` is not only relevant to this Round 3
mitigation candidate — it is the mechanism the live, deployed `PIIRedactionLogFilter`
(`observability/log_redaction.py`, installed at every Lambda cold start) already depends on for
`CLAUDE.md`'s own non-negotiable transcript/log redaction constraint. The same `PHONE_RE` gap found here
means that mechanism has had essentially zero real phone-number coverage since it shipped — a live
production defect independent of `D121`'s fix direction, not this ADR's to carry. See `D124`'s own row for
the full account, including the generalization check (`OI47`) on whether the other `ADR-011` patterns share
this problem (they don't, for different reasons per pattern).

**Check 2 — new failure mode from this specific placement, not inherited from `ADR-011`.** `ADR-011`'s
`redact_for_transcript()` runs against text already decided and already about to be persisted — a false
positive there degrades a stored log line silently, after the fact, with no caller-facing consequence at
all. Placed at `coverage_question.py`'s call site, before the answer is spoken, the same regex runs on
the *live turn* with no equivalent of `update_contact_info_node`'s retry-and-escalate ladder: a false
positive here ships a redacted-mid-sentence answer straight to the caller, once, with nothing downstream
to catch or recover it. It is also not obviously safe even in the literal sense: the function's output
format, `[REDACTED:<TYPE>]`, was designed to be *read* in a log, not *spoken* by Polly — a false-positive
hit would have the agent's voice say bracket-redacted-colon-email-bracket, or similar, mid-answer, which
is a new and different kind of broken output than either a silent log edit or a Bedrock `{EMAIL}` token
already documented for `D121`. **This is a genuinely different risk shape than the mechanism it reuses,
not the same mechanism at a new address**, and any adoption of this mitigation would need its own
placeholder wording (not the transcript format verbatim) and its own answer to what happens on a match —
neither designed nor scoped here.

**Consequence for direction 1-global's residual cost, restated per Marco's instruction — accurately, not
as a clean win:** direction 1-global loses the Bedrock-layer backstop on the `coverage_topic` path; a
regex-layer backstop already exists at that same call site **for `EMAIL` only** — `PHONE_RE`'s
555-exchange scoping means it provides **no real coverage for a caller's actual phone number** as
currently written, and adopting it for the live-speech path (not just persistence) introduces a new,
un-scoped failure mode of its own (Check 2). This is not "loses the only backstop" (Round 2 Q4's original
framing) and it is also not "a complete backstop already exists" — it is **loses the Bedrock-layer
backstop on `coverage_topic`; a partial, EMAIL-only regex backstop already exists at that call site,
covers real email addresses, does not cover real phone numbers, and would need new design work (coverage
fix for `PHONE_RE`, a speakable placeholder, a decided consequence on a match) before it could be trusted
to carry the weight Q2 asked whether it could carry.**

## Direction 1-narrowed — reachability check (Marco, Round 3): remove `EMAIL`/`PHONE` from OUTPUT for
`update_contact_info`'s readback only, keep them in force where the LLM generates a response

**Question: does Bedrock's guardrail model support per-invocation entity scoping, or is the entity list
fixed per guardrail version?** Checked against the current `ApplyGuardrail` API reference
(`docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ApplyGuardrail.html`) and the SDK request
shapes for the same operation (Java, Go, PHP SDKs, cross-checked, not read from memory): the request takes
exactly `guardrailIdentifier`, `guardrailVersion`, `source`, `content`, and (newer) `outputScope` — **no
field anywhere in the request accepts a per-call policy or entity override.** `CreateGuardrail`/
`UpdateGuardrail`'s `sensitiveInformationPolicyConfig` (which entities, which action) is resource-level
configuration, bound to a `guardrailIdentifier` + `guardrailVersion` pair, not a parameter of the call that
applies it. **Fixed per guardrail version, confirmed from the current API reference, not assumed.**

**Consequence, per Marco's own instruction: the only form direction 1-narrowed could take is a second
guardrail resource, its own version lifecycle, invoked selectively.** Priced honestly, not waved past:

- A new `aws_bedrock_guardrail` (e.g. a "narrow" guardrail, `EMAIL`/`PHONE` excluded, content
  filters/denied topics mirrored for parity) plus its own `aws_bedrock_guardrail_version`, in
  `infra/terraform/stacks/guardrails/main.tf` — the same version-bump/redeploy/`C1`-cycle machinery
  direction 1-global already needs, **not avoided, duplicated.**
- **This doubles `D97`/`OI14`'s coupling-defect surface rather than avoiding it.** `D97`'s root cause was
  one guardrail-version reference (`FNOL_GUARDRAIL_VERSION`) going stale after one guardrail's version was
  replaced without a coordinated `stacks/main` redeploy. Two independently-versioned guardrails need two
  independently-tracked version references, each with its own staleness window — editing either guardrail
  without redeploying `stacks/main` now reproduces `D97`'s exact failure mode, and the two windows are not
  correlated: fixing one guardrail's drift does nothing for the other's.
- **It does not avoid direction 3's routing-granularity problem — it adds to it.** Round 2 established that
  `guardrails_output_check` is one shared node with no node/branch-level distinction in the graph today.
  Direction 1-narrowed needs that same missing distinction (which node/branch produced this `response_text`)
  *plus* a second dimension on top of it — which `guardrailIdentifier`/`guardrailVersion` pair to call with
  — so it inherits Round 2 Q2's structural objection in full, without direction 3's compensating benefit (no
  version-bump machinery).
- Bedrock's own per-call dollar cost delta is negligible (one `ApplyGuardrail` call against a different
  guardrail ID costs the same policy units as against the current one) — **the real cost is entirely
  operational: more moving parts, doubled staleness surface, and the same routing gap direction 3 has,
  paid for on top of direction 1's own deploy machinery, not instead of it.**

**Verdict: direction 1-narrowed is reachable in principle (a second guardrail is an ordinary AWS pattern),
but it is not lighter than either direction it was meant to sit between — it is heavier than direction
1-global and inherits direction 3's own structural cost besides. Too heavy, said plainly, per Marco's own
fallback instruction.** The decision collapses back to **direction 1 (global) versus direction 3 (coarse)**,
with `coverage_topic`'s path now priced as a **known, measured cost of direction 1-global** — a real path
with a real, currently-low, small-sample-measured rate, not a hypothetical one.

## Decision

**Not made. Still PROPOSED, nothing accepted.** Direction 2 (empirically falsified), direction 2′ (closed
on requirements), and direction 1-narrowed (reachable but too heavy, collapses to the two below) are all
off the table, each on its own distinct ground, none to be conflated with the others. The live question is
**direction 1-global versus direction 3-coarse**, now with the free-text-PII cost measured on both
flaggable models (0/12) rather than merely named, and with the regex-reuse mitigation (Round 3 Q2)
established as **real but partial** — it narrows direction 1-global's residual cost for `EMAIL`, leaves it
essentially unchanged for `PHONE`, and carries its own new, un-scoped failure mode if adopted. It changes
what direction 1-global's cost *is*, not whether that cost is acceptable — that judgment is still open.

## Consequences (of whichever direction is eventually chosen)

**Directions 1 and 2′ both require**, at minimum: a guardrail-stack edit (`main.tf`), a version bump
(`aws_bedrock_guardrail_version`'s `replace_triggered_by` — editing the guardrail alone updates `DRAFT`
only, `main.tf:280-297`'s own documented hazard), a `stacks/main` redeploy to pick up the new
`FNOL_GUARDRAIL_VERSION`, and a full `C1` recall cycle to confirm no regression — the same sequence `D89`
and `D97`/`OI14` both required and, in `D97`'s case, broke availability when the two stacks were applied
out of order. **Whichever of the two is chosen, apply both stacks together, batched, not sequentially** —
`D97`'s own closure is the standing precedent for why, and per Round 2 Q3, that precedent is a prior real
outage in this project, not a theoretical caution.

**Direction 3 needs none of that** — no `main.tf` edit, no version bump, no guardrail-stack redeploy; a
`stacks/main`-only code change (the graph routing edit named above) plus its own eval cycle, and, per Round
2 Q2, a new `assert_dominates`-style test as part of the same change, not a follow-up.

If direction 2′ is chosen (currently closed on requirements, not expected to be revived without a change to
Round 1 Q1's answer), `D121`'s fix verification additionally needs the missing "before" artifact `OI43`
names — a captured pre-guardrail readback string — since a partial-disclosure fix's success criterion ("the
new readback is not masked, and a caller can actually confirm from it") cannot be checked against `§76`'s
post-mask-only record alone.

Whichever of direction 1 or direction 3 is eventually chosen, `D123`/`OI45`
(`update_contact_info.py:79`'s missed site, filed this session) needs its own scope decision as part of
that fix, not silent inclusion — direction 1 closes it for free (same as `:54,69`); direction 3 chosen at
coarse scope (Round 2 Q1) also covers it, since `:79` is inside the same node a whole-node skip already
bypasses, but this was never part of what "the confirmation turn" originally named and should be said
explicitly when the fix is written up, not discovered again later.
