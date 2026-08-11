# Ontario Insurance Reference — Phase 3

Per Marco's instruction: the synthetic policy corpus is anchored to **Ontario auto insurance specifically**,
not generic North American boilerplate. This document is the verified regulatory grounding the corpus is
built on — every real-world fact below was checked live on 2026-08-11 (not from memory, per this project's
standing discipline), cited, and separated from where this project **deliberately simplifies**. Where Ontario
specifics would complicate one of the six intents beyond what a portfolio-scale prototype needs, that's
stated here by name, not silently smoothed over.

**Standing caveat:** this project produces a **structurally faithful, originally-worded synthetic policy** —
it follows the same section taxonomy and coverage categories as the real Standard Ontario Automobile Policy
(OAP 1), issued by a fictional carrier ("Example Mutual"). It is **not** a reproduction of FSRA's copyrighted
OAP 1 form text, and none of its dollar figures should be read as Example Mutual's real-world rate filing —
they're chosen within realistic Ontario ranges, cited against real reference points below, for architectural
and eval fidelity, not as a claim of insurer-specific accuracy.

---

## 1. OAP 1 section structure (verified)

The Standard Ontario Automobile Policy (OAP 1), the mandatory policy form under Ontario's *Insurance Act*,
is organized into numbered sections. Cross-verified across FSRA's own consumer guidance and independent
insurance-industry summaries:

| Section | Coverage | Mandatory? |
|---|---|---|
| 3 | Third Party Liability | ✅ Mandatory |
| 4 | Accident Benefits (governed by the Statutory Accident Benefits Schedule, SABS) | ✅ Mandatory core; several sub-benefits became optional 2026-07-01 (§3 below) |
| 5 | Uninsured Automobile Coverage | ✅ Mandatory |
| 6 | Direct Compensation – Property Damage (DCPD) | ✅ Mandatory, unless opted out (§4 below) |
| 7 | Loss or Damage Coverages (Collision/Upset, Comprehensive, Specified Perils, All Perils) | ✗ Optional |
| 8 | Statutory Conditions (conditions the *Insurance Act* requires in every Ontario auto policy) | ✅ Mandatory, procedural |

This is the taxonomy `data/synthetic/policy/example-mutual-oap-policy-wording.md` follows section-for-section.

## 2. Mandatory minimum Third Party Liability

**$200,000** is the statutory minimum (Section 3). Real-world practice, per multiple independent sources, is
that most policyholders carry well above the minimum — commonly **$1,000,000**. Example Mutual's synthetic
policies in this corpus carry **$1,000,000**, with the $200,000 statutory floor cited in the wording as the
regulatory minimum, not the corpus's chosen limit.

## 3. Accident Benefits (Section 4 / SABS) — including a live regulatory change

Verified benefit structure and caps:

| Benefit | Cap | Status |
|---|---|---|
| Medical, Rehabilitation & Attendant Care — **Minor Injury Guideline (MIG)** track | **$3,500** combined | Mandatory |
| Medical, Rehabilitation & Attendant Care — non-catastrophic (post-MIG) track | **$65,000** combined | Mandatory |
| Medical, Rehabilitation & Attendant Care — catastrophic impairment track | **$1,000,000** combined | Mandatory |
| Income Replacement Benefit | 70% of gross weekly income, max **$400/week**, up to 104 weeks (standard) | **Optional as of 2026-07-01** |
| Caregiver Benefit | — | **Optional as of 2026-07-01** |
| Housekeeping & Home Maintenance Benefit | — | **Optional as of 2026-07-01** |
| Dependent Care Benefit | — | **Optional as of 2026-07-01** |
| Death & Funeral Benefits | — | **Optional as of 2026-07-01** |
| Indexation Benefit | — | **Optional as of 2026-07-01** |

**This is a live, current regulatory fact, not a stale assumption:** FSRA's SABS reform took effect
**2026-07-01** — five weeks before this document was written — making Income Replacement, Caregiver,
Housekeeping/Home Maintenance, Dependent Care, Death & Funeral, and Indexation benefits **optional
elections** a policyholder actively selects at renewal, rather than automatically bundled. Medical,
Rehabilitation, and Attendant Care benefits remain mandatory at all three severity tracks. This is exactly
the kind of fact this project's standing rule ("verify against current sources, never memory") exists to
catch — a model trained before mid-2026 would confidently assert the old always-bundled regime. The corpus
reflects the **current, post-reform** state: each synthetic policyholder's declarations page states which
optional benefits they elected (Phase 3, task 5).

**Catastrophic impairment** is a defined 8-category clinical/legal test (e.g., ≥55% whole-person impairment,
or marked/extreme mental-behavioural impairment classes) applied by medical assessment, **never** by this
project's agent. See §6 below for how this bounds the injury-severity mapping.

## 4. Direct Compensation – Property Damage (DCPD), Section 6

Mandatory, no-fault: an Ontario driver claims property-damage repair costs from **their own insurer**, for
the portion of the accident **not** their fault, without waiting on the other driver's insurer or a fault
finding by any third party. Since **2024-01-01**, a policyholder may opt out via a signed agreement
(commonly referenced as OPCF 49) to reduce premium — this project's synthetic policyholders are **not**
modeled as having opted out (see §7, simplification 2).

**No deductible applies to a DCPD claim** — the deductible only attaches to first-party Collision coverage
(Section 7), which responds to the at-fault share.

## 5. Fault apportionment (Ontario Fault Determination Rules, O. Reg. 668)

Legislated rules assign fault in fixed percentage bands — **0%, 25%, 50%, 75%, or 100%** — per a schedule of
accident-scenario descriptions (e.g., rear-end collisions default to 100% against the following driver).
The not-at-fault share is paid via DCPD (own insurer, no deductible); the at-fault share (if any) is paid via
Collision coverage (own insurer, subject to the policyholder's chosen deductible) or pursued against the
other driver's Third Party Liability coverage.

## 6. Total loss — no single legislated percentage

Ontario does **not** set one statutory total-loss percentage. Insurers apply their own internal threshold,
typically **70–80% of Actual Cash Value (ACV)**, comparing estimated repair cost against ACV. Separately,
Ontario's vehicle branding program (administered through the used-vehicle information system) assigns a
**"salvage"** or **"irreparable"** brand once a vehicle is written off — a regulatory labeling regime, distinct
from the insurer's own repair-vs-total-loss trigger. **Example Mutual's stated internal rule, used throughout
this corpus, is 80% of ACV** — chosen at the upper (more repair-favoring) end of the observed real-world
range, and stated as an explicit policy rule rather than left implicit, per Marco's instruction.

## 7. Rental (OPCF 20) and towing/roadside (OPCF 35) — and why intent 4 only uses one of them

Two distinct, verified Ontario endorsement products exist:

- **OPCF 20 (Loss of Use)** — optional endorsement reimbursing a rental vehicle while the insured car is
  undergoing **covered repair**. Real-world daily caps commonly run **$50/day** with total caps around
  **$1,000–$2,000**, varying by insurer.
- **OPCF 35 (Emergency Roadside Assistance)** — optional endorsement covering **non-collision breakdowns**
  (dead battery, lockout, flat tire, out of fuel) — commonly ~**$50/incident**, capped at roughly twice per
  12 months.

**Deliberate simplification, stated plainly:** this project's intent 4 ("Rental / towing entitlement") is
scoped to the **post-accident FNOL context** — a caller who has just filed or is asking about a claim, not a
roadside-breakdown caller. In that context, **towing the damaged vehicle from the accident scene to a repair
shop is realistically an incidental covered expense bundled into the Section 6 (DCPD) or Section 7 (Collision/
Comprehensive) claim settlement itself**, not OPCF 35's separate non-accident roadside product. This project
therefore models "towing" as a **stated per-incident towing allowance inside the Loss-or-Damage/DCPD claim**
(§7's `example-mutual-oap-policy-wording.md`), and does **not** build out OPCF 35 as a separate coverage —
OPCF 35 is named here so the simplification is visible, not silently dropped. Rental (OPCF 20) is modeled in
full as the optional endorsement it actually is, since it's the more consequential half of intent 4's
compound RAG+tool case.

---

## Sources

All facts above verified live 2026-08-11 via web search against FSRA-adjacent and independent Ontario
insurance-industry sources (FSRA's own site returned HTTP 403 to direct fetch — corroborated instead across
`en.wikipedia.org/wiki/Ontario_Automobile_Policy_1`, `en.wikipedia.org/wiki/Ontario_Fault_Determination_Rules`,
and multiple independent Ontario insurance-broker/law-firm publications converging on the same section
structure, dollar figures, and the 2026-07-01 SABS optionality reform). No figure here is asserted from
training-data memory alone — the July 2026 reform in particular is the kind of recent change memory would
miss entirely.

## Summary of deliberate simplifications (per Marco's instruction: name them, don't smooth them)

1. **Fault-percentage apportionment (O. Reg. 668) is not modeled as agent logic.** The FNOL agent's job is
   intake, not adjudication — consistent with the existing architecture (the human FNOL specialist has $0
   settlement authority and cannot deny, per `docs/phase0/DOMAIN-ARTIFACTS.md`'s harvested authority model).
   Coverage-question answers describe *that* fault determines DCPD-vs-Collision routing, never compute a
   percentage.
2. **No synthetic policyholder has opted out of DCPD** (OPCF 49). Keeps DCPD uniformly active across the
   corpus, avoiding a second claim-routing branch this prototype's scope doesn't need.
3. **Intent 4's "towing" is the accident-scene towing allowance bundled into a covered claim, not OPCF 35's
   separate roadside-breakdown product.** OPCF 35 is named, not built.
4. **KABCO (scene-reported injury severity) and SABS's MIG/non-catastrophic/catastrophic tiers are kept as
   two distinct axes, never conflated** — see `data/synthetic/policy/coverage-logic.md` §3 for the explicit
   boundary statement. This project's agent never performs the clinical/legal catastrophic-impairment
   determination; it only ever hard-escalates on injury/fatality language (`ADR-010`, `D12`, `D15`).
