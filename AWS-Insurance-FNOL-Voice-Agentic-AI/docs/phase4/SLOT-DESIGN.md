# Slot Design — Phase 4

Full elicitation spec for every slot-bearing intent: `FileAutoClaim` (the showcase, ~11 slots) and
`UpdateContactInfo`. `CheckClaimStatus`, `CoverageQuestion` and `RentalTowingEntitlement` carry 1–3 slots
each and are covered more briefly in §3. `InjuryEscalation` has no slots — it is a pre-node trigger, not a
form (`DIALOGUE-POLICIES.md` §5).

Every slot here follows the **shared no-input/no-match retry ceiling** defined in `DIALOGUE-POLICIES.md` §7:
two attempts, then escalate. This document does not repeat that mechanism — it states which slots get the
proactive DTMF offer that ceiling design makes available, and what validates as a successful capture.

All identifier formats are `docs/phase3/DATA-CONTRACTS.md`, unchanged — this document elicits them, it does
not redefine them.

---

## 1. `FileAutoClaim` — 11 slots

### 1.1 Elicitation priority order

Stated as the order slots are **asked when nothing has been volunteered yet** — not a rigid linear script.
Per `PROBLEM-FRAMING.md`, the graph tracks what remains missing and skips anything the caller already
volunteered unprompted (a caller who opens with "someone hit me at Main and 5th around 3" has just filled
`loss_location` and part of `loss_datetime` before being asked). This priority list is also the source
Phase 8's CFN `AWS::Lex::Bot` `slot_priority` field is authored from — a conversation-design decision, not an
infra one, per `ADR-007`'s residual gap (R1).

| # | Slot | Why here |
|---|---|---|
| 1 | `injuries_present` | Asked first among slots, even though a separate `safety_check` graph state already ran before collection began (`PROBLEM-FRAMING.md`). This is the *formal* capture into the record, and doubles as another checkpoint for L1/L2 against fresh language the caller hasn't used yet |
| 2 | `policy_number` | Needed to resolve `insured_vehicle`'s enum — everything after this can be policy-scoped |
| 3 | `insured_vehicle` | Depends on #2; disambiguated only if the policy lists more than one vehicle |
| 4 | `loss_datetime` | Narrative slots next, in the order a caller naturally narrates: when → where → what |
| 5 | `loss_location` | |
| 6 | `loss_type` | |
| 7 | `damage_description` | Also drives the damage-extent classification consumed by intent 4's towing branch (`endorsements.md`) |
| 8 | `other_party_involved` (+ name, insurer if present) | |
| 9 | `police_report_filed` | |
| 10 | `police_report_number` | Conditional — only elicited if #9 is affirmative |
| 11 | `driver_name` (+ `relationship_to_insured`, default "Self") | Last: most calls don't need dialogue here at all, since "Self" is the default and only needs confirming, not eliciting |

### 1.2 Per-slot specification

| Slot | Elicitation prompt (canonical form) | Validation | Confirmation | DTMF fallback |
|---|---|---|---|---|
| `injuries_present` | "Is anyone hurt, including you?" | bool | **None** — any affirmative escalates immediately per intent 6; adding a confirm step here would violate the "no negotiation" hard rule | N/A |
| `policy_number` | "What's your policy number?" | `^PY\d{4}$`, resolved against the mock policy store | **Always confirm** — read back digit-grouped ("P-Y, four eight two one — is that right?"). Critical identifier, F7 mitigation | ✅ 4 digits, offered proactively after the **first** no-match (see §4) |
| `insured_vehicle` | "Is this about your [vehicle 1] or your [vehicle 2]?" (only asked if >1 on policy; otherwise auto-filled and confirmed, not elicited) | Enum match against the policy's vehicle list, or ordinal ("the first one") | Confirm-if-low-confidence only | Digit-keyed ordinal (1/2) when multiple vehicles |
| `loss_datetime` | "When did this happen?" | Fuzzy-parsed (`dateutil`-class parsing, "yesterday about 5:30") | Confirm-if-low-confidence — read back the parsed value ("that's Tuesday the 11th, around 5:30 PM?") since fuzzy parsing is exactly where a silent misparse is most likely | N/A |
| `loss_location` | "Where did it happen?" | Free text, no format constraint | Confirm-if-low-confidence | N/A |
| `loss_type` | "Was this a collision, comprehensive-type loss like theft or weather, or something else?" | Enum: Collision · Comprehensive · Theft · Vandalism · Weather · Liability | None — constrained response space, low ASR risk | N/A |
| `damage_description` | "Can you describe the damage?" | Free text | Confirm-if-low-confidence | N/A |
| `other_party_involved` | "Was another vehicle or driver involved?" | bool (+ name/insurer sub-fields if affirmative) | None on the bool; confirm-if-low-confidence on sub-fields | N/A |
| `police_report_filed` | "Was a police report filed?" | bool | None | N/A |
| `police_report_number` | "What's the report number?" (conditional) | `^\d{4}-\d{4}-\d{3}$` | Always confirm — digit-grouped read-back | ✅ digits + implicit dash placement, offered after first no-match |
| `driver_name` | "Were you driving, or someone else?" | Free text + `relationship_to_insured` (default "Self") | Confirm-if-low-confidence | N/A |

### 1.3 Close-out

Per `PROBLEM-FRAMING.md`'s success criterion: a full summary read-back of the captured claim, then the
speakable claim number (`docs/phase3/DATA-CONTRACTS.md`'s `CLM-YYMM-NNNNN-C`, read digit-grouped with the
Luhn check digit stated separately — "your claim number is C-L-M, two-six-zero-eight, dash, zero-zero-zero-
four-two, check digit four") — confirmed once, not re-litigated slot-by-slot a second time.

---

## 2. `UpdateContactInfo` — 3 slots, mandatory confirmation write path

| Slot | Elicitation prompt | Validation | Confirmation |
|---|---|---|---|
| `policy_number` | "What's your policy number?" | Same as §1.1 | Always confirm |
| `field` | "Is this your phone number, email, or mailing address?" | Enum: phone \| email \| mailing address | None — constrained response space |
| `new_value` | "What should I update it to?" | Format-checked per `field` (E.164-ish for phone, RFC-shape for email, free text for address) | **Mandatory, character-grouped read-back** per the existing constraint ("requires an explicit confirmation policy") — phone read back digit-grouped, email read back token-by-token ("j... at... example... dot... com") |

**Write gate, restated from `PROBLEM-FRAMING.md` because it is the single highest-consequence rule in this
document:** write only on unambiguous affirmative confirmation. A failed or ambiguous confirmation loops
**once** (not the shared 2-attempt ceiling — this write path gets exactly one retry before falling straight
to escalation, tighter than the general ceiling, because a silent partial write is named a critical defect,
not a missed target). No write on partial, inferred, or ambiguous "yes."

---

## 3. Remaining intents — 1–3 slots each

### `CheckClaimStatus`
`claim_number` **or** `policy_number` — either suffices. Elicitation: "What's your claim number, or if you
don't have it handy, your policy number?" — offers the fallback path up front rather than after a failure,
since both are always valid (unlike the DTMF-after-first-miss pattern in §4, which is specifically for
recovering from a *failed* capture of one required field). `claim_number` follows §4's DTMF pattern if the
caller does supply one and it fails to capture. `policy_number` resolves to the most recent open claim,
disambiguating by date if more than one.

### `CoverageQuestion`
`policy_number` (always confirmed, same as §1.1) + free-text `coverage_topic`. No DTMF fallback on
`coverage_topic` — it's free text, not a digit-bearing identifier. See `DIALOGUE-POLICIES.md` §3 for how the
sub-question type (election-fact vs. eligibility/amount) is resolved *after* this slot is filled, not during
elicitation.

### `RentalTowingEntitlement`
`entitlement_type` (enum: rental | towing), `policy_number` (confirmed), optional `claim_number` (DTMF-
eligible per §4 if supplied and it fails capture). If `claim_number` is not volunteered, it is resolved the
same way as `CheckClaimStatus`'s fallback — most recent open claim on the policy.

---

## 4. DTMF fallback — which slots get it, and why

Per `DATA-CONTRACTS.md`'s reasoning: DTMF is a first-class input path for **digit-only** identifiers, not a
universal fallback. Only three slots across the whole taxonomy qualify: `policy_number`, `claim_number`,
`police_report_number` — all digits-only by construction (`DATA-CONTRACTS.md` §1–2, §6).

**Policy:** on the **first** no-match on any of these three slots specifically (not the general two-attempt
ceiling — this is a targeted repair that fires earlier), the reprompt proactively offers the keypad
alternative: *"You can also enter that on your keypad, followed by the pound key."* This is a targeted
mitigation for F7 (ASR error on critical identifiers) and directly serves the Phase 1 "Repair success rate ≥
0.80" target — it does not replace the shared retry ceiling in `DIALOGUE-POLICIES.md` §7, it is a better
second attempt within it, not an additional attempt beyond it.

Free-text and enum slots (`loss_location`, `damage_description`, `loss_type`, …) have no DTMF equivalent —
offering a keypad for a free-text description is meaningless — and simply use the shared retry ceiling
unmodified.
