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
single-token replacement `D121` already documented. **A spelled or grouped full-value readback trades one
unconfirmable placeholder for another, sometimes a more broken one. This variant of direction 2 should not
be built.**

### Direction 2′ — partial-disclosure readback (new candidate, surfaced by this session's probes, not proposed by Marco, not evaluated for viability)

Two follow-up probes (`§79`): a short email prefix (`"the address starting with m, a, r, c, o, s"`) passed
with **no intervention** — `masked: False`, `action: NONE`, the original text would reach the caller
unchanged. The phone equivalent (`"the number ending in one, five, four, seven"`) **still masked**. The two
entities do not behave symmetrically under partial disclosure, and only one partial shape per entity was
tested — this is a signal that a partial form *can* survive, not a measured boundary for either detector.

Open questions this document does not resolve, named for the grilling session:

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

---

## Decision

**Not made.** Reserved for Marco's own `/grill-with-docs` session against this document and the sweep
artifact, per his explicit instruction that the grilling step is his to invoke, not mine to replicate.

## Consequences (of whichever direction is eventually chosen)

Both directions require, at minimum: a guardrail-stack edit (`main.tf`), a version bump
(`aws_bedrock_guardrail_version`'s `replace_triggered_by` — editing the guardrail alone updates `DRAFT`
only, `main.tf:280-297`'s own documented hazard), a `stacks/main` redeploy to pick up the new
`FNOL_GUARDRAIL_VERSION`, and a full `C1` recall cycle to confirm no regression — the same sequence `D89`
and `D97`/`OI14` both required and, in `D97`'s case, broke availability on when the two stacks were applied
out of order. **Whichever direction is chosen, apply both stacks together, batched, not sequentially** —
`D97`'s own closure is the standing precedent for why.

If direction 2′ is chosen, `D121`'s fix verification additionally needs the missing "before" artifact
`OI43` names — a captured pre-guardrail readback string — since a partial-disclosure fix's success
criterion ("the new readback is not masked, and a caller can actually confirm from it") cannot be checked
against `§76`'s post-mask-only record alone.
