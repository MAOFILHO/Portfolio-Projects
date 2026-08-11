# Example Mutual Insurance Company — Ontario Automobile Policy Wording

**Form edition:** EM-OAP-2026-08 (synthetic, original wording) | **Effective:** policies issued/renewed on or
after 2026-07-01 | **Governing law:** *Insurance Act* (Ontario) and the Statutory Accident Benefits Schedule
(O. Reg. 34/10, as amended)

This is a synthetic policy wording, originally authored for this project, following the same section
structure and coverage taxonomy as the Standard Ontario Automobile Policy (OAP 1) — not a reproduction of
FSRA's copyrighted form. Grounding facts and sources are in `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md`;
that document also names every place this wording deliberately simplifies real Ontario practice. This
wording is the primary retrieval corpus for the **Coverage Question** intent and half of the **Rental /
Towing Entitlement** intent; deductible/total-loss/injury-mapping computation rules live in the companion
document `coverage-logic.md`; the rental endorsement lives in `endorsements.md`.

---

## Section 1 — Words With Special Meaning

- **"You," "your"** — the policyholder named on the Declarations Page, and any person who ordinarily lives
  with the policyholder and is a listed driver.
- **"Your automobile"** — the vehicle(s) described on the Declarations Page by VIN, year, make, and model.
- **"Accident"** — an incident involving the ownership, use, or operation of an automobile, resulting in loss
  or damage, that arises out of a single continuous event.
- **"Actual Cash Value (ACV)"** — the cost to replace your automobile with one of like kind and quality,
  immediately before the loss, less depreciation.

## Section 2 — Description of Automobile Coverage

The coverages in force for a specific automobile are those shown on that automobile's Declarations Page.
Not every section below applies to every policy — Sections 3, 4, 5, 6, and 8 are mandatory on every Example
Mutual Ontario auto policy; Section 7 (Loss or Damage) and the endorsements in `endorsements.md` apply only
where selected and shown on the Declarations Page.

---

## Section 3 — Third Party Liability Coverage

We will pay all sums you become legally liable to pay as damages because of bodily injury to, or death of,
any person, or loss of or damage to property of others, arising from an accident involving your automobile.

**Limit:** the amount shown on your Declarations Page. **The statutory minimum limit in Ontario is
$200,000.** Example Mutual's standard-issue policies carry **$1,000,000**, reflecting common Ontario
practice of carrying materially more than the statutory floor.

**What is not covered (selected exclusions):** liability arising while the automobile is used to carry
persons or property for compensation (ride-share/commercial use, unless a commercial endorsement is shown on
the Declarations Page); liability for damage to property you own, are transporting, or have care, custody or
control over other than a residence or its contents; liability arising from intentional acts.

---

## Section 4 — Accident Benefits Coverage

If you are injured in an automobile accident, we will pay the benefits described below, regardless of who
was at fault. Benefits are organized into three severity tracks. **The severity track is determined by
medical assessment (using the insurer's standard treatment/assessment forms), never by this policy wording
and never automatically from how a loss is initially reported.** See `coverage-logic.md` §3 for the explicit
boundary between how a loss is initially described (the KABCO scene-severity scale) and how a benefit track
is actually assigned (a clinical/legal determination made after the fact) — this project's voice agent
performs the former only, never the latter.

| Track | Combined cap (Medical, Rehabilitation & Attendant Care) | Who qualifies |
|---|---|---|
| **Minor Injury Guideline (MIG)** | **$3,500** | Whiplash-associated disorders, sprains, strains, contusions, lacerations, and similar injuries with no complicating factors, assessed by a treating practitioner |
| **Non-catastrophic (post-MIG)** | **$65,000** | Injuries that don't meet MIG criteria, or are removed from MIG due to a complicating factor (e.g. a relevant pre-existing condition) |
| **Catastrophic impairment** | **$1,000,000** | Meets one of eight defined categories set out in the Statutory Accident Benefits Schedule (e.g. ≥55% whole-person impairment; specified classes of severe mental/behavioural impairment) — determined through a formal medical assessment process, never at first notice of loss |

**Mandatory, at every track:** Medical, Rehabilitation, and Attendant Care Benefits, as capped above.

**Optional — you elect these individually on your Declarations Page (per FSRA's Ontario-wide reform
effective 2026-07-01, when these ceased being automatically bundled):**

| Optional benefit | What it pays if elected |
|---|---|
| Income Replacement Benefit | 70% of gross weekly employment income, to a maximum of $400/week, for up to 104 weeks |
| Caregiver Benefit | Reasonable expenses for a substitute caregiver, if you provided care to another person before the accident and can no longer do so |
| Housekeeping & Home Maintenance Benefit | Reasonable expenses for services you can no longer perform yourself |
| Dependent Care Benefit | Reasonable child/dependent care expenses you incur to attend treatment |
| Death & Funeral Benefits | A stated lump sum to your estate/dependents, plus funeral expense reimbursement |
| Indexation Benefit | Annual cost-of-living adjustment to your other elected benefit amounts |

If your Declarations Page does not list an optional benefit, it is **not** part of your coverage — this
policy does not assume any optional benefit is in force absent an explicit election.

---

## Section 5 — Uninsured Automobile Coverage

If you are injured or killed, or your automobile is damaged, by an identified uninsured motorist or an
unidentified hit-and-run driver, this coverage responds where Third Party Liability coverage would otherwise
have applied but for the other driver's lack of insurance. Mandatory on every policy; no separate limit shown
on the Declarations Page — it follows the minimum statutory limits set by regulation.

---

## Section 6 — Direct Compensation – Property Damage (DCPD) Coverage

If your automobile is damaged in an accident in Ontario involving at least one other insured automobile, and
you are **not entirely at fault**, we will pay to repair or replace your automobile in proportion to your
degree of non-fault, without regard to the other driver's insurer. Fault is apportioned per the Ontario Fault
Determination Rules (0%, 25%, 50%, 75%, or 100%, by accident-scenario schedule) — this policy pays your
not-at-fault share under this section; any at-fault share, if you also carry Collision coverage (Section 7),
is paid there instead, subject to your Collision deductible.

**Deductible:** ⚠ **corrected 2026-08-11 against FSRA's own consumer guidance** — a DCPD deductible is not
universally absent; Ontario insurers may offer one as an option to lower premium (a policyholder can choose
to add one). **No Example Mutual policyholder in this project's synthetic corpus has added an optional DCPD
deductible** — every synthetic policy's DCPD section is deductible-free, a deliberate simplification stated
here rather than the earlier draft's incorrect blanket "no deductible ever applies" claim. See
`docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` §4 for the citation and the correction note.

**Towing and storage:** reasonable towing and storage charges to transport your damaged automobile from the
accident scene to the nearest qualified repair facility are included in a covered claim under this section
(or under Section 7, if that section responds instead), up to **$150 per incident**, with no separate
deductible. *(This is distinct from — and does not include — roadside assistance for a non-accident
breakdown, such as a dead battery or lockout; that is a separate optional product this policy does not
include, named for completeness in `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` §7.)*

**Opting out:** a policyholder may sign an agreement to waive DCPD coverage (available since 2024-01-01) in
exchange for a premium reduction. **No Example Mutual policyholder in this project's synthetic corpus has
made this election** — DCPD is active on every synthetic policy, a deliberate simplification named in
`docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` §7.

---

## Section 7 — Loss or Damage Coverages (optional)

Shown on your Declarations Page only if purchased.

- **Collision or Upset** — pays to repair or replace your automobile if damaged by collision with another
  object or by upsetting (rolling), regardless of fault. This is the coverage that responds to your
  **at-fault share** of an accident (Section 6 pays the not-at-fault share). Subject to your selected
  deductible.
- **Comprehensive** — pays for loss or damage from causes other than collision or upset: fire, theft,
  vandalism, falling/flying objects, weather, and glass breakage. Subject to your selected deductible.
- **All Perils** — combines Collision/Upset and Comprehensive under a single deductible; adds coverage for
  loss caused by an occupant using the vehicle without your consent.
- **Specified Perils** — a narrower, lower-cost alternative to Comprehensive, covering only the specific
  named perils listed on the Declarations Page (typically fire, theft, lightning, windstorm, hail, and a
  short list of similar events). Not modeled further in this corpus beyond naming it — this project's
  synthetic policyholders carry Collision, Comprehensive, or All Perils, never Specified Perils alone, since
  it adds a narrower peril list without changing any of the six intents' behavior.

**Deductible:** shown on your Declarations Page, either **$500 or $1,000**, chosen at the time the policy was
issued. Applies once per claim under Collision, Comprehensive, or All Perils coverage — never under DCPD
(Section 6) or Third Party Liability (Section 3). Full arithmetic in `coverage-logic.md` §1.

**Total loss:** if the estimated cost to repair exceeds **80% of your automobile's Actual Cash Value**
immediately before the loss, Example Mutual settles the claim as a total loss rather than authorizing
repair. This is Example Mutual's own stated claims-handling rule — Ontario does not set a single legislated
percentage (see `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` §6) — applied consistently and disclosed here
rather than left as adjuster discretion. Settlement is Actual Cash Value, less your deductible (if the claim
is paid under Collision/Comprehensive/All Perils) or Actual Cash Value with no deductible (if paid entirely
under DCPD, i.e., you were not at fault). Full worked formula in `coverage-logic.md` §2.

---

## Section 8 — Statutory Conditions

Conditions the *Insurance Act* (Ontario) requires in every automobile policy issued in the province,
including:

- **Notice of loss:** you must notify Example Mutual of any accident or loss **as soon as reasonably
  possible**. This project's "File a new auto claim" intent exists specifically to make that notice
  low-friction over voice.
- **Proof of loss:** Example Mutual may require a signed statement detailing the circumstances of the loss,
  the amount claimed, and other relevant particulars, generally within 90 days of the loss.
- **Cooperation:** you must cooperate with Example Mutual's investigation, including providing information
  reasonably requested and not admitting fault to a third party.
- **Fraud:** any wilfully false statement in connection with a claim voids that claim.
- **Claim status:** Example Mutual will provide a claim number at first notice of loss and will make claim
  status available on request throughout the life of the claim — the basis for this project's "Check claim
  status" intent.

---

## Cross-references

- Deductible arithmetic, total-loss settlement formula, and the KABCO-vs-SABS injury-severity boundary:
  `coverage-logic.md`
- Rental reimbursement (OPCF 20-style optional endorsement): `endorsements.md`
- Regulatory grounding and every named simplification: `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md`
