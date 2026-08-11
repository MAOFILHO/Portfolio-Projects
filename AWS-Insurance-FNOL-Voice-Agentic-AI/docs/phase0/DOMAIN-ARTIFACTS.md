# Domain Artifact Inventory — Phase 0

Insurance domain knowledge harvested from the eight source repos, **separately from the code merge matrix** —
several of these are valuable even where the surrounding code is discarded.

## Synthetic-data attestation

**All data in this project is synthetic.** No real customer, policyholder, policy, vehicle or claim data from
any source enters it. The PII gate found no real customer data in the eight repos (see
`SECURITY-FINDINGS.md`), but three artifacts are nonetheless excluded by name — a real AWS account ID inside
repo 5's Lex export, a structurally valid Honda VIN in repo 6, and DMV specimen licence images containing
real human face photographs. **No images are vendored from any source repo.**

Where a figure below came from a source repo it is a *synthetic* figure from that repo, not an industry
benchmark. Nothing here is a validated actuarial or performance number, and none of it may be presented as
one (constraint 13).

---

## 1. Identifier formats

| Entity | Formats found | Source |
|---|---|---|
| Policy number | `PY####` (`PY1234`); `POL-AUTO-12345`; `POL-#####` (`POL-12345`); bare UUID v4 | 5 / 7 / 8 / 6 |
| Claim number | `PY1234-123450` (policy + OTP); `CLM-YYYY-NNN`; `CLM-###`; bare UUID v4 | 5 / 7 / 8 / 6 |
| Driver's licence | `^[A-Z]\d{8}$` (`D08954142` AZ, `S99988801` MA) | 6 |
| Licence plate | `^[A-Z]{3}-\d{4}$` (`KJH-4523`) | 8 |
| **Police report number** | `^\d{4}-\d{4}-\d{3}$` — year-MMDD-sequence (`2024-0116-425`) | 8 |
| VIN | 17-char (`1HGCM82633A123456`) — see exclusion note | 5 / 6 |
| Fraud pattern | `FP-###` | 7 |
| External core-system id | UUID v4 (Socotra `locator`) | 5 |
| Other-party insurance id | 12 digits (`111111111111`) | 6 |

### ⚠ Gap 1 — no usable claim number exists in the corpus

- Repo 5's `PY1234-123450` is the policy number concatenated with the **six-digit OTP** — it leaks a secret into an identifier read aloud on a recorded-adjacent channel. A design flaw, not a pattern.
- Repo 6 uses a bare UUID v4 — **unspeakable over voice**.
- Repo 8's `CLM-001` is three digits and does not scale.

**Proposal for Phase 3:** `CLM-YYMM-XXXXX` with a check character, using a voice-safe alphabet (no
`0/O`, `1/I/L`, `5/S`, `2/Z`) so ASR confusions are caught rather than accepted. Decided with the Phase 3
data contracts.

---

## 2. FNOL intake sequence

**Repo 5's Lex slot priorities** — the only real FNOL elicitation order in the corpus, with verbatim prompts:

| # | Slot | Lex slot type | Prompt (verbatim) |
|---|---|---|---|
| 1 | `Policy_VIN` | `AMAZON.AlphaNumeric` | "We need to verify your identity with few questions. What is your Policy # or Vin # ?" |
| 2 | `CommPref` | `AMAZON.AlphaNumeric` | "Do you prefer email and Mobile number to get a one time password?" |
| 3 | `OTP` | `AMAZON.Number` | "We sent an OTP to you mobile number. Please type in the code to proceed further" |
| 4 | `CarMake_Model` | `AMAZON.AlphaNumeric` | "Which car are you filing for?" |
| 5 | `LossDate` | `AMAZON.AlphaNumeric` | "What is the Date and time of the Incident" |
| 6 | `LossLocation` | `AMAZON.AlphaNumeric` | "As close as you can recall, Where did it happen? (City , Zip, or address)" |
| 7 | `Details` | `AMAZON.FreeFormInput` | "Describe the incident as best as you can" |
| 8 | `DriverName` | `AMAZON.AlphaNumeric` | "Can you provide full name of the person who was driving the car?" |
| 9 | `IncidentReport` | `AMAZON.FreeFormInput` | "If you have a Police Incident report number, please enter that. If not say I dont know or Not applicable." |

Bot config: `nluConfidenceThreshold: 0.4`, `idleSessionTTLInSeconds: 300`, neural voice `Danielle`.
Multi-vehicle disambiguation: *"I see more than one car in your Auto policy — {Vehicle_List}. Which car are
you filing the claim for?"* Confirmation readback: *"Please confirm that these details are correct:-
CustomerName:{…}, CarMake_Model:{…}, LossDate:{…}, LossLocation:{…}"*

**Critical divergence from our design:** this sequence puts **identity verification and OTP first**, before
any safety question. Repo 6 does the opposite and is right — see §3. Our sequence leads with safety.

**Repo 6's required-field set**, with the human-readable labels it uses for TTS readback — the better
starting point for our slot definitions:

| Field | Voice phrasing |
|---|---|
| `occurrence_date_time` | "date and time of accident" |
| `location_description` | "accident location" |
| `damage_description` | "damage description" |
| `policy_id` | "policy number" |
| `drivers_license` | "driver's license number" |
| `number_of_passengers` | "number of passengers" |
| `was_driving` | "whether you were driving" |
| `police_filed` | "whether police report was filed" |
| `police_receipt` *(conditional on `police_filed == True`)* | "whether you have the police report receipt" |

Repo 6's workflow phase enum — adopt as our graph's high-level state:
**`safety_check → collection → validation → confirmation`**

Repo 5's incident-context fields worth capturing: `weather_conditions`, `police_report` (bool),
`witnesses` (count), `traffic_violation` (bool), `photos_available`, `emergency_services`,
`relationship_to_primary_insured` (default `"Self"`).

Date tolerance: repo 5's parser accepts **nine** date formats and defaults a missing time to `01:01:01`;
repo 6 uses `dateutil.parser.parse(fuzzy=True)` for "yesterday at 3pm". Both are relevant — callers state
dates loosely and out of order.

---

## 3. Safety-first triage — the most important behavioural artifact

Repo 6's priority-ordered ladder, with verbatim guidance strings. Inputs: `is_safe`, `needs_medical`,
`police_contacted`, `in_safe_location`.

```
if needs_medical:          safety_confirmed = False
  "Please call 911 or your local emergency number immediately if you need medical assistance.
   Your safety is the priority. We can help with your claim once you've received medical attention."

elif not in_safe_location: safety_confirmed = False
  "Please move to a safe location away from traffic before we continue. Your safety is most important."

elif not police_contacted: safety_confirmed = True     ← recommends, does NOT block
  "I recommend contacting the police to file an accident report. This will help with your claim.
   Would you like to do that now, or shall we proceed with collecting your claim information?"

else:                      safety_confirmed = True
  "I'm glad you're safe. Let's proceed with collecting your claim information."
```

Note the design judgement: a missing police report **recommends and continues**; only medical need and an
unsafe location halt collection.

Governing principles from repo 6's system prompt, to carry into our prompt library:

- Safety and well-being before any claim information.
- **"DO NOT ask the customer for information that is already available in our system. The customer is in distress and should not have to repeat information they've already provided during signup."**
- One question at a time; do not overwhelm the caller with all questions at once.
- Summarise **only the incident information** and confirm before submission; do **not** read back the insurer's account or policy information.
- Submit only after explicit confirmation; if the caller corrects something, update it.
- If emergency help is needed: provide 911, strongly encourage calling, offer to continue afterwards — but if the caller insists on filing now, proceed.

Empathy phrase bank: *"I'm sorry to hear about your accident."* · *"Take your time."* · *"I understand this
is stressful."* · *"That's okay, we can come back to that."* · *"Just to make sure I have this right…"* ·
*"I'm glad you're safe."* · *"Your safety is what matters most."*

Repo 5's human-escalation intent supplies **12 verbatim escalation utterances** — a ready training set for
our hard "agent" barge-in intent (intent 6).

---

## 4. Injury severity — KABCO (NHTSA MMUCC)

From repo 5's `SampleRepairCost.docx`, verbatim. This is a **real regulatory standard**, which is why it is a
KEEP rather than something we invent.

| Code | Level | Definition |
|---|---|---|
| **K** | Fatal Injury | Any injury that results in death within 30 days after the crash |
| **A** | Suspected Serious Injury | Severe laceration, broken or distorted extremity, crush injuries, suspected skull/chest/abdominal injury, significant burns, unconsciousness, or paralysis |
| **B** | Suspected Minor Injury | Any injury evident at the scene — a lump on the head, abrasions, bruises, minor lacerations |
| **C** | Possible Injury | Reported or claimed injury — momentary loss of consciousness, claim of injury, limping, complaint of pain or nausea |
| **O** | No Apparent Injury | No reason to believe the person received any bodily harm |

**Vehicle extent of damage:**

| Level | Definition |
|---|---|
| None | No visible damage |
| Minor | Does not affect operation or disable the vehicle |
| Functional | Not severe but affects operation of the vehicle or its parts |
| **Disabling** | **Prevents the vehicle from being driven from the scene — typically severe damage requiring towing** |

Two rules this gives us directly:
- **Intent 6 (hard escalation)** triggers on any mention mapping to **K or A**, from any state, with no LLM discretion. B/C are captured and flagged, not escalated.
- **Intent 4 (towing entitlement)**: `Disabling Damage ⇒ towing applies` is our only prior-art hook for the towing branch.

---

## 5. Coverage taxonomy, deductibles and repair costs

**Coverage list** (repo 5, verbatim): Bodily Injury Liability, Property Damage Liability,
Uninsured/Underinsured Motorist, Comprehensive, Collision, Medical Payments, Personal Injury Protection.
Deductible `$500`; premium `$750 / 6 months`.

**Covered perils** (repo 7): `collision`, `comprehensive`, `liability`, `medical`, `uninsured_motorist`.
**Exclusions** (repo 7): `racing`, `commercial_use`, `intentional_damage`.

**Claim type enum** (repo 7) — close to our Lex loss-type slot as-is: Collision, Comprehensive, Liability,
Property Damage, Bodily Injury, Theft, Vandalism, Fire, Weather Damage.
**Claim subtypes** (repo 8): Wind/Hail Damage, Collision, Fire Damage, Theft, Water Damage, Flood, Storm Damage.

**Coverage arithmetic** (repo 7): `covered_amount = min(claim_amount − deductible, policy_limit)`;
`within_limits = claim_amount <= policy_limit + deductible`.

**Repair cost bands** (repo 5, verbatim): Windshield $250–900 · Dented bumper $400–1,500 · Paint chips/
scratches $250–1,500 · Door or fender dings $250–500 · Suspension $100–5,000+ · Front-end $200–2,000 ·
Rear-end $200–2,000 · Frame $600–10,000 · Side impact $200–2,000 · Door $50–1,500 · Body panel $50–2,000.

**Labour formula** (repo 5): `total_labour = hourly_rate × repair_hours × multiplier`, four worked tiers —
Simple `$80 × 2 × 1.0 = $160`; Moderate `$100 × 6 × 1.1 = $660`; Complex `$120 × 10 × 1.3 = $1,560`;
Extensive `$150 × 15 × 1.5 = $3,375`.

**Parts price table** (repo 5, per vehicle): Brakes, Bumper, Door, Engine, Fender, Headlight, Suspension,
Tires, Transmission, Windshield. E.g. *Toyota Camry 2021*: 300/400/700/3500/900/800/3000/1500/4000/1250.

### ⚠ Gaps 2–4 — three coverage areas no repo provides

| # | Gap | Evidence |
|---|---|---|
| 2 | **Deductible logic** | Repo 6 returns a hardcoded `$100.00` string; repo 5 displays `$500` statically. **Nothing computes anything.** |
| 3 | **Rental reimbursement / towing / roadside** | **Zero mentions across all eight repos** — yet these are two of our six intents. Phase 3 authors both coverage sections from scratch, internally consistent with the rest of the corpus, or intent 4 has no ground truth |
| 4 | **Total-loss determination** | No threshold, no ACV calculation, no salvage rule anywhere. Repo 5's parts table + labour formula is raw material only |

### ⚠ Gap 5 — injury severity is never connected to coverage

Repo 6 stops at emergency triage ("call 911"); repo 5's KABCO scale is documentation only, **never coded**.
Nothing in any repo maps injury severity to BI / PIP / MedPay coverage or to adjuster escalation. Phase 3
authors this mapping, and it is what intent 6 is tested against.

---

## 6. Data schemas

**Repo 6 `FNOLPayload`** — the canonical shape (Pydantic v2, a KEEP):

```json
{
  "incident": {
    "occurrenceDateTime": "ISO8601", "fnolDateTime": "ISO8601",
    "location": {"country":"US","state":"AZ","city":"Phoenix","zip":"85007","road":"124 Main St"},
    "description": "Rear-End Collision"
  },
  "policy": {"id": "<uuid>"},
  "personalInformation": {"customerId":"","driversLicenseNumber":"","isInsurerDriver":true,
                          "licensePlateNumber":"","numberOfPassengers":1},
  "policeReport": {"isFiled": true, "reportOrReceiptAvailable": true},
  "otherParty": {"insuranceId":"","insuranceCompany":"","firstName":"","lastName":""}
}
```

⚠ **Two inconsistencies in repo 6 to fix, not inherit:** its event schema requires all four `otherParty`
fields while its Pydantic model marks them all `Optional`; and `numberOfPassengers` is `"type":"string"` in
the event schema but `int` in the model. Our schema is the single source of truth and validates both ways.

**Repo 5 claim record fields:** `CaseNumber, PolicyNumber, CustomerName, CustomerEmail, CustomerPhone,
CarMake_Model, Vehicles, LossDate, LossLocation, Details, IncidentReport, DriverName, Submission,
case_status, GenAI_Summary, comments, claim_amount, CreatedAt, UpdatedAt, CreatedBy`.
(Its `VehiclceAnalysis` typo is propagated throughout that repo — do not reproduce it.)

**Policy / vehicle record** (repo 6): `make, model, color, type, year, mileage, vin, startDate, endDate`
(6-month terms).

**Status lifecycles:**
- Repo 5 `case_status`: `New → Pending for user documents → Review → Approved | Rejected | Closed`
- Repo 7 `ClaimStatus`: Received, In Progress, Under Investigation, Adjudicated, Approved, Denied, Paid, Closed
- Repo 8: `New | Needs Review | Resolved`

---

## 7. Business rules

**Claim acceptance** (repo 6), with verbatim rejection messages:
1. Policy-period rule: `policyStartDate < incidentDate < policyEndDate` — *"The incident happened on {date} which is outside policy active period. Policy active from {start} till {end}."*
2. Driver's-licence match: stored `DOCUMENT_NUMBER` must equal the supplied `driversLicenseNumber` — *"Personal information (Driver's License) does not match"*

**Regulatory clocks** (repo 7): **FNOL 24 hours**, coverage decision 30 days, fraud reporting 10 days,
claim resolution 90 days.

**Authority-limit matrix** (repo 7) — governs what our agent may and may not do:

| Role | Max settlement | Max reserve | Can deny? | Supervisor approval? |
|---|---|---|---|---|
| **FNOL specialist** | **$0** | **$5,000** | **No** | **Always** |
| Adjuster | $10,000 | $25,000 | — | — |
| Senior adjuster | $50,000 | $100,000 | — | — |
| Supervisor | $100,000 | $250,000 | — | — |
| Manager | $500,000 | $1,000,000 | — | — |

**This is the governing constraint on our agent's scope**: an FNOL specialist captures and validates, and
**never adjudicates coverage or denies a claim on the call**. Repo 7's principle is explicit —
`create_ai_recommendation` returns `{ai_recommendation_only: True, human_decision_required: True}`.
**AI advises; a licensed human decides.**

**Escalation thresholds** (repo 7): claims > $100k trigger large-loss reporting; > $50k enhanced fraud
screening and routing to a senior adjuster; jurisdictions CA/NY/FL add enhanced consumer protection.
Repo 7 also models `bad_faith_prevention_notes` — a real insurance-compliance concept.

**Triage rubric** (repo 8) — thresholds and a weighted evidence score:

```
damage amount:    > $30,000 → high ;  > $15,000 → medium ;  else low
evidence volume:  > 10 items → high ;  > 5 items → medium ;  else low
claim subtype:    Fire Damage | Theft | Flood | Storm Damage → high ; Property → medium ; else low

evidence score:  severe +4 · moderate +2 · fire/water/weather/theft damage +3 · structural area +2
                 poor-quality/blurry video +2 · staged/suspicious video +4
                 major inconsistencies +5 · minor inconsistencies +2
                 likely/potential fraud +6 · low credibility +3
                 no fraud indicators / consistent / credible −2   (floored at 0)
     score >= 6 → high ; >= 3 → medium ; >= 1 → low ; else minimal

routing:  Complex → "Needs Review" (human adjuster)  ;  Simple → "Resolved" (auto-close)
bias:     "Be conservative — when in doubt, mark as COMPLEX."
fallback (no LLM):  estimated_damage > $20,000 OR total evidence items > 8 → Complex
```

The **deterministic fallback** is the part worth most to us: a non-LLM path that still routes correctly when
inference fails or is switched off, which suits both the latency budget and the cost ceiling.

**Fraud signals** (repo 6, three concrete rules): claimant first name ≠ name on driver's licence; detected
vehicle colour ≠ colour on policy; "no damage detected" on a damage claim.
Repo 5 adds a genuinely useful vision rule: **reported vehicle ≠ vehicle in the image → hard stop**
("CRITICAL MISMATCH").
Repo 7's named patterns: amount near policy limit (`> limit × 0.9`), delayed reporting (`> 7 days`),
frequent claimant (`> 2 claims in 12 months`), weather-event opportunist.

⚠ **All fraud signals are intake-time soft flags recorded for human review — never on-call fraud decisions,
and never spoken to the caller.**

---

## 8. Post-call analysis taxonomy

Repo 8's **transcript** tags map 1:1 onto our post-call pipeline:

| Dimension | Values |
|---|---|
| Emotional state | calm · distressed · angry · suspicious |
| Story consistency | consistent · minor_inconsistencies · major_inconsistencies |
| Fraud risk | none · potential · likely |
| Information quality | complete · partial · vague |
| Credibility | high · medium · low |

Secondary reference — image tags (damage type / severity / affected area / characteristics) and video tags
(quality, consistency, temporal analysis).

---

## 9. Test fixtures and synthetic-data recipes

**Six synthetic FNOL transcripts** (repo 8) — KEEP. Natural monologues that state fields out of order,
volunteer unasked-for information, and mention injury status, police report numbers and photos. The two
auto-relevant ones are `CLM_002` (rear-end collision) and `CLM_004` (vehicle theft); the other four are
property claims and of lower value. All phone numbers are `555-` reserved; all emails `@email.com`.

`CLM_002` is a good stress case for slot filling: it supplies date/time, location, damage description,
other-party name and insurer, injury status, police-report existence and photo availability — but in
narrative order, not slot order, and with the date given twice ("yesterday evening" then "January 15th").

**Synthetic-caller audio recipe** (repo 8) — REFACTOR, and the only budget-compatible test-data approach in
the corpus: generate a transcript, then Polly `Engine='neural'` → `OutputFormat='pcm'` → WAV **16 kHz mono
16-bit**, which matches Lex/Connect input format exactly. Polly neural is ~$16/1M characters, so a full
fixture set costs cents. **The Nova Canvas image and Nova Reel video paths in the same file are discarded —
Nova Reel at ~$0.08/s would breach the budget outright.**

**Seed records** (repo 7): `sample_claims.json` and `fraud_patterns.json` — useful shapes; keep the auto
records, drop the home/water-damage ones.

---

## 10. Core-system integration contracts (mock CRM/OMS reference)

Repo 5 documents a real **Guidewire ClaimCenter Cloud API** FNOL sequence, useful for making our mock
claims system behave like something real rather than a toy:

```
POST  /claim/v1/unverified-policies   {policyNumber, policyType: {code: "PersonalAuto"}}
POST  /claim/v1/claims                {lossDate, policyNumber}            → claimId
POST  /claim/v1/claims/{claimId}/contacts  {contactSubtype: "Person", firstName, lastName} → contactId
PATCH /claim/v1/claims/{claimId}      {reporter: {id: contactId}}
POST  /claim/v1/claims/{claimId}/submit
   (wrapped in POST /composite/v1/composite)
lossDate format: "%Y-%m-%dT%H:%M:%S.00Z"
```

**Socotra** alternative: authenticate → list policyholder policies (pick latest by `startTimestamp`) →
create claim from `policyLocator` → update with `{incident_type, fraud_check, incident_summary,
incidentTimestamp, notificationTimestamp, status: "open"}`.

**Repo 6's event vocabulary** (14 events, a KEEP) — our EventBridge contract even though we run far fewer
services: `Claim.Requested` (`fnol.service`), `Claim.Accepted`, `Claim.Rejected` (`claims.service`),
`Customer.Submitted/Accepted/Rejected/Document.Updated`, `Document.Processed/Rejected`,
`Fraud.Detected/Not.Detected`, `Settlement.Finalized`, `Vendor.Finalized`.
Notably, repo 6's voice agent integrates at the **REST boundary (`POST /fnol`), not the event bus** — the
right seam for us too.

**Repo 4's transcript envelope**, recorded for reference only (repo 4 is otherwise discarded): a
Lex/Contact-Lens-compatible transcript shape of `ContentMetadata` (including `RedactionTypes`),
`CustomerMetadata.ContactId`, `Participants[{ParticipantId, ParticipantRole}]`, `Version: '1.1.0'`,
`Transcript[{Id, Content, ParticipantId}]`. Relevant only if we later persist transcripts in a
Lex-analysable shape.

---

## 11. PII taxonomy for redaction

Repo 3's 22 Comprehend entity types, verbatim, with masking strategy `REPLACE_WITH_PII_ENTITY_TYPE`
(so "My name is John Doe" → "My name is [NAME]"):

```
BANK_ACCOUNT_NUMBER, BANK_ROUTING, CREDIT_DEBIT_NUMBER, CREDIT_DEBIT_CVV, CREDIT_DEBIT_EXPIRY,
PIN, EMAIL, ADDRESS, NAME, PHONE, SSN, DATE_TIME, PASSPORT_NUMBER, DRIVER_ID, URL, AGE,
USERNAME, PASSWORD, AWS_ACCESS_KEY, AWS_SECRET_KEY, IP_ADDRESS, MAC_ADDRESS, ALL
```

**Three corrections for FNOL:**

1. **Remove `DATE_TIME`.** Blanket-redacting it is actively harmful — loss date and time is the single most important field we collect. Redacting it would destroy the record we exist to create.
2. **Remove `ALL`** — it subsumes the other 22 and makes the list meaningless.
3. **Add** `VIN`, `LICENSE_PLATE`, `POLICY_NUMBER`, `CLAIM_NUMBER`. None exists in Comprehend's taxonomy; `DRIVER_ID` is the closest to a driver's licence. These become custom regex detectors.

Implementation note: repo 3 contains **zero regexes** — detection is entirely delegated to Comprehend, and
it uses `Mode='ONLY_REDACTION'`, so **no entity offsets or confidence scores are ever available**. For
selective masking we want offsets and per-entity confidence, which means the synchronous
`detect_pii_entities` API or our own regexes. Neither is demonstrated in the corpus.

---

## 12. Voice-channel prior art — what does not exist

Recorded here so Phase 4 is scoped honestly. Across all eight repos combined:

- **Barge-in, DTMF, no-input/no-match and timeout configuration: only `MaxRetries: 2` exists.** Nothing else. No `AllowInterrupt`, `MessageSelectionStrategy`, `PromptAttemptsSpecification` (with `AllowedInputTypes`, `AudioAndDTMFInputSpecification.StartTimeoutMs`, `AudioSpecification.{EndTimeoutMs,MaxLengthMs}`, `DTMFSpecification.{MaxLength,EndTimeoutMs,DeletionCharacter,EndCharacter}`), `WaitAndContinueSpecification`, `SlotCaptureSetting`, or `FailureResponse`/`TimeoutResponse`. Repo 2's only DTMF handling is a hack — adding the literal utterance "1" to an intent so a keypad tone is treated as speech.
- **Streaming, partial responses and interim audio fillers: none.** Repo 1 makes a single blocking LLM call inside a 300 s-timeout Lambda, so the caller hears dead air for the entire model latency. This is the clearest thing the corpus does *wrong* for a voice UX, and constraint 14's 1,800 ms p95 has no prior art to lean on.
- **Lex event fields we need are absent**: `interpretations[]` (ranked NLU candidates with `nluConfidence`), `transcriptions[]` (ASR n-best), `requestAttributes`, `proposedNextState`, and V2 `ConfirmIntent`/`ElicitIntent`. Source these from AWS docs.
- **No repo uses MCP at all.**

One transferable warning, from repo 6's engineering guide: **speech models need an explicit `inputSchema`;
docstring-inferred tool schemas are insufficient.** Its `submit_fnol` tool carries a 90-line explicit nested
schema for exactly this reason. Worth heeding when we define MCP tool schemas.
