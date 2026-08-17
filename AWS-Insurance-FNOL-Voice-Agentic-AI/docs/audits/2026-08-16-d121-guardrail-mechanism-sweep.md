# `D121` mechanism sweep — every mechanism in the guardrail capable of masking a caller's own data back to them

`REVIEW-CRITERIA.md` §8 (extended 2026-08-16, after `D121`): "when a fix removes one mechanism that
produces an unwanted outcome, enumerate every other mechanism capable of producing the *same outcome*, not
only every other call site of the *same mechanism*." This sweep is that enumeration, run **before** Block
2's design decision closes, per Marco's explicit instruction that a sweep informing a choice without being
written down is unfalsifiable six weeks out — the exact shape of the original `D16`→`D121` gap.

**Scope of the outcome being swept for**: a mechanism in `infra/terraform/stacks/guardrails/main.tf`
producing `action: ANONYMIZED` (or equivalent — replacing real caller-supplied content with an
unconfirmable placeholder) against text that is the caller's own data, spoken back to them by this system.
Not "any guardrail intervention" — a `BLOCK` is a different outcome shape (`D89`'s class, refusal, not
substitution) and is noted below only to confirm it was checked and excluded, not folded in.

Every top-level policy block in the live `main.tf` (298 lines, read in full 2026-08-16 for this sweep) is
covered. Config citations are file:line against the file as committed at `f3ebc4b` (the last commit that
touched this file), re-verified by reading the file directly at write time, not from memory of an earlier
read.

## Mechanism inventory

| # | Mechanism | Config file:line | Action(s) it can take | Produces "masked back" outcome? | Structurally reachable from any of the six in-scope intents' spoken output? |
|---|---|---|---|---|---|
| 1 | Content filters (`VIOLENCE`, `SEXUAL`, `HATE`, `INSULTS`, `MISCONDUCT`, `PROMPT_ATTACK`) | `main.tf:94-130` | `BLOCK` only — content filters have no `ANONYMIZE` action in Bedrock's API at all | **No, not in kind.** A content-filter intervention is a refusal, not a substitution; there is no partial-mask outcome this policy type can produce | N/A — excluded by action type, not by reachability |
| 2 | Denied topics (`non_auto_insurance_products`, `legal_and_medical_advice`) | `main.tf:137-211` | `BLOCK` only — topic policy has no `ANONYMIZE` action either | **No, not in kind**, same reason as #1. This is `D89`'s mechanism and outcome class (refusal on a misclassified turn), a different defect from `D121`'s | N/A — excluded by action type |
| 3 | Word filters (`word_policy_config` — custom words/managed word lists) | **Absent from this file entirely.** Grepped the full 298 lines: no `word_policy_config` block exists in `aws_bedrock_guardrail.fnol` | N/A — not configured | **No** — the mechanism does not exist in this guardrail at all, zero exposure by construction | N/A |
| 4a | PII entity `EMAIL` | `main.tf:236` (`sensitive_information_policy_config` → `pii_entities_config` `for_each` set, `action = "ANONYMIZE"` at `main.tf:246`) | `ANONYMIZE` | **Yes** | **Yes — `D121`, confirmed live.** `update_contact_info.py:54,69` speaks `filled['new_value']` verbatim when `field="email"` |
| 4b | PII entity `PHONE` | `main.tf:237` | `ANONYMIZE` | **Yes** | **Yes — `D121`, confirmed live.** Same two lines, `field="phone"` |
| 4c | PII entity `CREDIT_DEBIT_CARD_NUMBER` | `main.tf:238` | `ANONYMIZE` | Yes, in principle | **No.** No node in `src/fnol_voice_agent/agents/nodes/` collects a card number as a slot at all — grepped `card`/`credit` across `src/`: only hits are `guardrails/pii.py` (transcript-side redaction, a different boundary — `ADR-011`), `models/policy.py`, and `validation/identifiers.py`, none of which feed a `response_text` construction. No structural path exists for this entity to fire |
| 4d | PII entity `US_SOCIAL_SECURITY_NUMBER` | `main.tf:239` | `ANONYMIZE` | Yes, in principle | **No.** No SSN slot exists in any of the six intents; same grep as 4c, no hit tying an SSN-shaped value to any `response_text` |
| 4e | PII entity `CA_SOCIAL_INSURANCE_NUMBER` | `main.tf:240` | `ANONYMIZE` | Yes, in principle | **No.** Same as 4d — no SIN slot anywhere in the graph |
| 4f | PII entity `DRIVER_ID` | `main.tf:241` | `ANONYMIZE` | Yes, in principle | **No.** `file_auto_claim.py` collects `driver_name` (a name, not a licence/ID number) and `insured_vehicle_vin` (a VIN, a different identifier) — neither is `DRIVER_ID`-shaped, and `_summarize()` (`file_auto_claim.py:76-79`) only ever echoes `loss_type`/`loss_datetime`/`loss_location` back to the caller, not `driver_name` or the VIN. No confirmation turn in this codebase speaks a driver-licence-shaped value |
| 4g | PII entity `PASSWORD` | `main.tf:242` | `ANONYMIZE` | Yes, in principle | **No.** No password concept exists anywhere in this domain |
| 5 | Custom identifier regexes (`policy_number`, `claim_number`, `licence_plate`, `vin`) | **Absent** — removed at v2→v3, documented in place at `main.tf:250-267` as a comment explaining the removal, not as live config | N/A — not configured | N/A — mechanism does not exist | N/A. This is `D16`'s mechanism; its closure is what `D121` showed was incomplete (a different mechanism, same outcome). Re-confirmed absent by reading the block directly, not assumed from the comment alone: no `regexes_config` block appears anywhere in `sensitive_information_policy_config` |

## Verdict

**Exactly one mechanism, with two configured entities, is both live and structurally reachable: `EMAIL`
(4a) and `PHONE` (4b) via `UpdateContactInfo`'s own confirmation readback.** This is `D121` in full — the
sweep does not surface a second, undiscovered instance of the same outcome anywhere else in the six
in-scope intents' designed conversational paths.

Every other candidate was checked and excluded on one of three independent bases, not assumed clean:

- **Wrong action type** (#1, #2) — the mechanism exists and is reachable, but cannot produce a mask/
  substitution outcome at all, only a block. Different defect class (`D89`), not a missed instance of this
  one.
- **Not configured** (#3, #5) — the mechanism does not exist in the live guardrail, confirmed by reading
  the full resource block rather than trusting a comment or a prior summary.
- **Configured but not structurally reachable** (4c–4g) — the entity type exists in
  `sensitive_information_policy_config` and could mask if it ever saw matching text, but no node in this
  codebase ever constructs a `response_text` containing a card number, SSN, SIN, driver-licence ID, or
  password. Checked by grepping the relevant field names across `src/` and by reading every
  `response_text` call site in `agents/nodes/*.py` directly (all 27 sites enumerated, listed below) rather
  than by assuming a slot that exists must be echoed.

## Every `response_text` call site, for the reachability claim above

Grepped directly (`grep -n "response_text" src/fnol_voice_agent/agents/nodes/*.py`), 27 sites across 8
files, re-checked at write time:

- `check_claim_status.py:48` — echoes `claim.claim_number`, `claim.status`. Neither is a configured PII
  entity (claim number was `D16`'s regex, removed; status is an enum).
- `file_auto_claim.py:77-78,102,112,139` — echoes `loss_type`, `loss_datetime`, `loss_location`,
  `claim.claim_number`. None are configured PII entity types.
- `coverage_question.py:92` — LLM-generated `answer`. Context traced: retrieved static policy corpus text,
  `AccidentBenefitsElections` (six booleans, `models/policy.py:14-25`, no PII-shaped fields), and the
  caller's own `coverage_topic` string. No structural PII entity in the fixed parts of the context.
- `rental_towing.py:69-74,86` — echoes `claim.claim_number`, `days_used`, `days_remaining`,
  `amount_remaining_cad` (all non-PII-entity-shaped), plus an LLM-generated `answer` over the same kind of
  context as `coverage_question.py`.
- `update_contact_info.py:54,69,84` — echoes `filled['new_value']` verbatim (`D121`'s site) and
  `result.field` (an enum label, not a value).
- `injury_escalation.py:39`, `repair.py:67,71-72`, `guardrails_nodes.py:94,107,118` — all fixed strings or
  the guardrail's own already-processed `output_text`, no caller-supplied slot value involved.

## One residual gap, named rather than swept as closed

`coverage_question.py`'s `coverage_topic` and `rental_towing.py`'s `entitlement_type` are **free-text
slots sourced from the caller's own words**, fed into an LLM generation context and then, via `answer`,
potentially into `response_text`. If a caller volunteered PII-shaped text inside one of these free-text
slots (e.g. "my coverage question is about the policy on my email marcos@gmail.com" — an unlikely but not
impossible utterance) and the model's answer happened to reproduce it, that would be a *third* mechanism
shape entirely — the guardrail firing on caller-volunteered PII inside a generated answer, not on a
structured slot echo. **This is not audited here and is not the same defect as `D121`**: `D121` is a
designed confirmation step that *always* speaks a PII-entity-shaped value for two of three field choices;
this hypothetical is an *edge case* dependent on what a caller chooses to say inside an open-ended slot.
Named as a residual gap, not scoped, not probed — a live multi-turn check through this specific path has
never been run.
