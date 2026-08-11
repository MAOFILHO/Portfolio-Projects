# Ontario Insurance Reference — Phase 3

> ⚠ **AS OF DATE: 2026-08-11. This document will go stale.** It reflects Ontario's SABS reform that took
> effect **2026-07-01** — five weeks before this was written. Ontario auto insurance regulation changes on
> its own schedule, independent of this project. **Before relying on this document, or the corpus built on
> it, past roughly Q1 2027, re-verify against FSRA's current guidance** rather than trusting the dates below
> to still be current. This warning is carried forward into `docs/phase3/DATA-CARD.md`.

Per Marco's instruction: the synthetic policy corpus is anchored to **Ontario auto insurance specifically**,
not generic North American boilerplate. This document is the regulatory grounding the corpus is built on —
every claim below was checked live on 2026-08-11 (not from memory, per this project's standing discipline),
and every citation was tested, not just cited (§8). **Not everything checked out as a directly-verified
primary-source fact — where it didn't, that's stated as plainly as where it did**, per Marco's instruction
that a broken or unconfirmed regulatory citation is worse than none: §1 (OAP 1 section numbering) and §3
(the specific SABS dollar caps) are marked explicitly as **corpus construction choices**, not verified
regulatory citations, because their primary sources tested as inaccessible (§8). Ground truth for this
project's evals is the corpus itself, which is internally consistent regardless of whether every figure in
it has been independently confirmed against currently-inaccessible primary legislative text. Where Ontario
specifics would complicate one of the six intents beyond what a portfolio-scale prototype needs, that's
stated here by name too, not silently smoothed over.

**Standing caveat:** this project produces a **structurally faithful, originally-worded synthetic policy** —
it follows the same section taxonomy and coverage categories as the real Standard Ontario Automobile Policy
(OAP 1), issued by a fictional carrier ("Example Mutual"). It is **not** a reproduction of FSRA's copyrighted
OAP 1 form text, and none of its dollar figures should be read as Example Mutual's real-world rate filing —
they're chosen within realistic Ontario ranges, cited against real reference points below, for architectural
and eval fidelity, not as a claim of insurer-specific accuracy.

---

## 1. OAP 1 section structure — a corpus construction choice, not a verified citation

**Restated 2026-08-11, per Marco's instruction**: §8 (source B1) graded this numbering 🔴 — the FSRA OAP 1
PDF, the one primary source that would confirm it, returned an "Access denied" page despite an HTTP 200
status, and was never successfully read. Rather than present unread-primary-source numbering as a verified
regulatory fact, here is the honest framing:

**Example Mutual's synthetic corpus organizes its policy wording into the six-section structure below —
Third Party Liability, Accident Benefits, Uninsured Automobile, DCPD, Loss or Damage, Statutory Conditions —
matching a structure widely reported, by secondary aggregation, as the real OAP 1's section layout. The
primary source (FSRA's own OAP 1 form) was inaccessible at time of writing (§8, source B1). This numbering
is a corpus construction choice made for structural fidelity, not a verified regulatory citation.** FSRA's
own consumer guidance (§8, source A1) does independently confirm the *coverage content* of each row below —
what's mandatory, what's optional, what each coverage does — without itself using "Section N" numbering; only
the specific numbering is unverified, not the underlying coverage taxonomy:

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

**Mandatory-vs-optional status: 🟢, directly confirmed** (§8, source A3 — FSRA's own dedicated reform page,
quoted verbatim). **The specific dollar caps below are a corpus construction choice, restated 2026-08-11 per
Marco's instruction, not a verified regulatory citation:**

> Example Mutual's synthetic corpus uses $3,500 / $65,000 / $1,000,000 as its SABS tier caps, matching
> values widely reported for post-2026-07-01 Ontario SABS. Primary sources were inaccessible at time of
> writing (see §8, sources B2–B3). These are corpus parameters, not verified regulatory citations.

The mandatory-vs-optional *status* of each benefit (row 4 below onward) rests on the directly-quoted FSRA
reform page and is solid; the *dollar amounts* are the corpus's own chosen parameters, corroborated across
multiple independent secondary sources but never confirmed against O. Reg. 34/10's own clause text, which
this document's automated verification could not read (§8, source B2).

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
finding by any third party. Since **2024-01-01**, a policyholder may opt out via a signed agreement to reduce
premium — **directly confirmed, verbatim, from FSRA's own consumer page** (§8, source A2): *"Effective
January 2024, you may elect not to claim Direct Compensation-Property Damage coverage."* This project's
synthetic policyholders are **not** modeled as having opted out (see §7, simplification 2).

**Deductible — ⚠ corrected 2026-08-11.** An earlier draft of this document and the policy wording stated
"no deductible applies to a DCPD claim" as an absolute rule. That was wrong, caught during citation
verification: FSRA's own page states, verbatim (§8, source A2), *"Some policies don't have a direct
compensation property damage deductible, but you can add one to lower your premium."* A DCPD deductible is
therefore **optional, not universally absent**. Corrected wording: **no Example Mutual policyholder in this
project's synthetic corpus has added an optional DCPD deductible** — every synthetic policy's DCPD section is
deductible-free by corpus construction, not by regulatory default. `example-mutual-oap-policy-wording.md`
and `coverage-logic.md` §1 both carry this correction.

## 5. Fault apportionment (Ontario Fault Determination Rules, O. Reg. 668)

**Citation grade: 🟡 primary URL confirmed / 🔴 percentage-band detail from secondary sources** — §8, source B4.

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

## 8. Citation audit — every URL tested, every claim graded by source strength

Marco's instruction, verbatim: "confirm the cited URL resolves and state which claims rest only on secondary
sources." Done properly, not by re-asserting the earlier vague "Sources" paragraph: every URL below was
tested with `curl` (not just re-trusted from a search engine's summary) on 2026-08-11, and its actual
returned content — not just its HTTP status — was inspected. **A 200 status is not treated as proof of a
working citation** — one source below returned HTTP 200 with an "Access denied" body, which would have been
a false-positive citation if status code alone had been trusted.

**Grading key:** 🟢 **Primary, quoted** — the regulator's own text, fetched and directly quoted here. 🟡
**Primary, resolves but unreadable** — the correct primary legislative URL, confirmed live (200, correct
page), but client-side-rendered so the actual clause text could not be machine-extracted; the citation exists
and is checkable by a human, but this document did not itself verify the clause text against it. 🔴 **Secondary
only** — no primary source was successfully read; the claim rests on independent industry/legal-practice
publications, corroborated across more than one, but not on the regulator's or legislature's own text. ⚫
**Broken — do not rely on this URL** — tested and found not to resolve to real content despite a misleading
status code; removed from active citation.

| # | Claim | Grade | URL(s) tested | What was found |
|---|---|---|---|---|
| A1 | $200,000 minimum Third Party Liability | 🟢 | `fsrao.ca/consumers/auto-insurance/purchasing-your-policy/what-standard-auto-insurance-policy` | HTTP 200, real content. Verbatim: *"By law, you must carry a minimum of $200,000 in third-party liability coverage, but you can choose to purchase a higher amount."* |
| A2 | DCPD mechanics: no-fault, Jan 2024 opt-out, deductible is optional-not-absent | 🟢 | same URL as A1 | HTTP 200, real content. Verbatim quotes given inline in §4 above |
| A3 | 2026-07-01 SABS reform: only Medical/Rehab/Attendant Care remain mandatory, rest optional | 🟢 | `fsrao.ca/industry/auto-insurance/changes-statutory-accident-benefits-coverage-ontario-july-1-2026` | HTTP 200, real content. Verbatim: *"As of July 2026, medical, rehabilitation and attendant care benefits will remain mandatory, while all other accident benefits coverage will be optional..."* Page title itself confirms this is FSRA's own dedicated page for this exact reform |
| A4 | Uninsured Automobile Coverage is mandatory | 🟢 | same URL as A1 | HTTP 200, real content, confirms this section exists and its purpose |
| B1 | OAP 1's six numbered sections (3 Liability … 8 Statutory Conditions) | 🔴 | `fsrao.ca/media/5156/download` (the actual OAP 1 PDF) | **Tested and found broken**: HTTP 200 but body is an "Access denied" page, not the document — see ⚫ note below. Section numbering rests on a web-search engine's own summary of this same inaccessible PDF, not independently re-read here. **This is the single most load-bearing unresolved citation in this document** — the entire section-by-section structure of `example-mutual-oap-policy-wording.md` follows this numbering, and it has not been confirmed against readable primary text. Cross-checked only against Wikipedia's coverage-type list, which explicitly does not give official section numbers either |
| B2 | O. Reg. 34/10 (SABS) exists at this citation and governs Accident Benefits | 🟡 | `ontario.ca/laws/regulation/100034` | HTTP 200, confirmed correct e-Laws page **by URL**, but the page is a client-rendered SPA — `curl` retrieved 54KB of scaffolding and zero regulation text. A human clicking the link gets the real text; this document's automated verification could not read it |
| B3 | SABS dollar figures: MIG $3,500, non-catastrophic $65,000, catastrophic $1,000,000, IRB 70%/$400/104 weeks | 🔴 | `injured.ca/what-are-medical-and-rehabilitation-benefits-under-the-accident-benefits-schedule/`, `ahinjurylaw.com/income-replacement-benefits-guide/`, and other personal-injury-law-firm publications, converging independently on the same figures | Primary text (O. Reg. 34/10 itself, B2) not machine-readable — see B2. **These are the most consequential dollar figures in the entire corpus and they rest on secondary legal-industry sources only**, not a directly-read regulation clause. Multiple independent firms agree, which is real corroboration, but it is not the same as reading O. Reg. 34/10 §45/§18 (the actual clause numbers) directly |
| B4 | Fault Determination Rules: fixed 0/25/50/75/100% bands, O. Reg. 668 | 🟡 primary URL / 🔴 dollar-band detail | `ontario.ca/laws/regulation/900668` (200, unreadable SPA, same as B2); `en.wikipedia.org/wiki/Ontario_Fault_Determination_Rules` (200, readable, but itself a secondary tertiary summary) | Same pattern as B2/B3 — primary regulation confirmed to exist and resolve, percentage-band detail sourced from Wikipedia + one insurance-broker blog, not the regulation's own scenario schedule |
| B5 | CanLII mirror of O. Reg. 34/10 and O. Reg. 777/93 | ⚫ | `canlii.org/en/on/laws/regu/o-reg-34-10/...`, `canlii.org/en/on/laws/regu/o-reg-777-93/...` | **Tested and found broken to automated access**: HTTP 403, and a retry with full browser headers returned a bot-detection challenge page ("Please enable JS and disable any ad blocker"), not legal text. Not usable as a citation from this document; a human following the link directly in a browser will likely succeed where this automated check did not |
| C1 | OPCF 20 (rental) real-world reference terms (~$50/day, $1,000–$2,000 total caps) | 🔴 | `thinkinsure.ca/insurance-help-centre/loss-of-use-coverage.html` and similar insurance-broker publications | Industry practice, not a regulatory figure — appropriately secondary-sourced; already framed in §7 as "real-world reference points," not an authoritative figure Example Mutual is claimed to match |
| C2 | OPCF 35 (roadside) real-world reference terms (~$50/incident) | 🔴 | `insurancehotline.com/resources/your-guide-opcf-35-and-sef-35-emergency-roadside-assistance` (this specific URL returned HTTP 403 on retest — broken); corroborated instead via other broker sources found in the original search | Same disposition as C1 — industry practice, appropriately secondary, and this project explicitly declined to build OPCF 35 as a coverage (§7), so this figure is flavor/context only, not load-bearing |
| C3 | Total-loss threshold: no single legislated %, insurer discretion typically 70–80% ACV | 🔴 | `idcollision.com/total-loss-thresholds-vehicle-written-off-ontario/`, `quotefinder.ca/how-much-will-my-insurance-give-me-for-my-totaled-car/` and similar | Confirmed as **not** a regulatory figure by multiple independent sources agreeing it's insurer-discretionary — the "no single percentage" claim itself is the load-bearing fact here, and it is corroborated, even though no primary source states a number (because no primary source sets one) |

**Net assessment:** the claims that actually drive caller-facing dollar amounts in the corpus — the SABS
benefit caps (B3) and the OAP 1 section structure itself (B1) — are the two claims resting on the weakest
citation grade. Both are corroborated across multiple independent secondary sources (which is why they were
used at all), but **neither has been confirmed by this document against directly-read primary legislative
text**, because the two most authoritative primary sources for them (the FSRA OAP 1 PDF, and CanLII's mirror
of O. Reg. 34/10) were both tested and found inaccessible to automated verification. This is stated plainly
rather than papered over with a confident-sounding "Sources" paragraph, per Marco's instruction that a
broken or unverified citation on a regulatory claim is worse than no citation. A reader who needs B1/B3 to be
authoritative (e.g., before using this corpus for anything beyond this portfolio project) should follow the
🟡/🔴 URLs above directly in a browser, where FSRA's and CanLII's client-side rendering will likely succeed
where this document's automated `curl`-based check did not. **§1 and §3 above have been restated accordingly
as corpus construction choices rather than verified citations — this table is the reason why, and it is left
exactly as first written, since it's the artifact that surfaced the distinction in the first place.**

## Summary of deliberate simplifications (per Marco's instruction: name them, don't smooth them)

1. **Fault-percentage apportionment (O. Reg. 668) is not modeled as agent logic.** The FNOL agent's job is
   intake, not adjudication — consistent with the existing architecture (the human FNOL specialist has $0
   settlement authority and cannot deny, per `docs/phase0/DOMAIN-ARTIFACTS.md`'s harvested authority model).
   Coverage-question answers describe *that* fault determines DCPD-vs-Collision routing, never compute a
   percentage.
2. **No synthetic policyholder has opted out of DCPD** (signed waiver, available since 2024-01-01). Keeps
   DCPD uniformly active across the corpus, avoiding a second claim-routing branch this prototype's scope
   doesn't need.
3. **No synthetic policyholder has added the optional DCPD deductible** FSRA confirms insurers may offer.
   Corpus-wide, DCPD stays deductible-free by construction, not by universal regulatory default — this is a
   correction applied 2026-08-11 after the earlier draft overstated it as an absolute rule (§4 above).
4. **Intent 4's "towing" is the accident-scene towing allowance bundled into a covered claim, not OPCF 35's
   separate roadside-breakdown product.** OPCF 35 is named, not built.
5. **KABCO (scene-reported injury severity) and SABS's MIG/non-catastrophic/catastrophic tiers are kept as
   two distinct axes, never conflated** — see `data/synthetic/policy/coverage-logic.md` §3 for the explicit
   boundary statement. This project's agent never performs the clinical/legal catastrophic-impairment
   determination; it only ever hard-escalates on injury/fatality language (`ADR-010`, `D12`, `D15`).
6. **"Am I entitled to X?" is answered by question type, not benefit type** — an election-fact lookup (do I
   have this coverage) is answered from the structured policyholder record; an eligibility/amount
   determination (will I actually get paid, and how much) is always deflected to a human, regardless of
   whether the underlying benefit is mandatory or optional. Full reasoning in
   `data/synthetic/policy/coverage-logic.md` §4.
