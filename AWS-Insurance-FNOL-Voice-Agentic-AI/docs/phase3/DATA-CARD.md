# Data Card — Phase 3 synthetic corpus

> ⚠ **AS OF DATE: 2026-08-11.** This corpus reflects Ontario's SABS reform effective **2026-07-01** — five
> weeks before this card was written. It **will go stale** on Ontario's own regulatory schedule, independent
> of this project. **Before relying on this corpus, or reusing its dollar figures, past roughly Q1 2027,
> re-verify against FSRA's current guidance** (`docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` §8 has the
> citation trail to start from). This warning is carried here verbatim from
> `ONTARIO-INSURANCE-REFERENCE.md`, per Marco's instruction that it needs to be visible wherever the corpus
> itself is described, not just in the reference document upstream of it.

Covers everything produced in Phase 3: the policy wording corpus, coverage logic, endorsements, and the
policyholder/vehicle/claim records. Purpose: state plainly what's synthetic, what's grounded in real
regulatory/domain sources (and how strongly), and what's authored with no external grounding at all — the
same "label what's asserted vs. synthesized" discipline this project already applies to metrics and cost
figures (`CLAUDE.md` constraint: "no invented metrics or capabilities anywhere in docs").

---

## 1. Provenance, by document

| Document | What it is | Provenance |
|---|---|---|
| `data/synthetic/policy/example-mutual-oap-policy-wording.md` | Policy wording (Sections 3–8), the `CoverageQuestion` RAG corpus | **Structural fidelity to a real regulatory framework** (Ontario OAP 1's section taxonomy), **originally worded** — not a reproduction of FSRA's copyrighted form. Section numbering itself is a *corpus construction choice*, not a verified citation (`ONTARIO-INSURANCE-REFERENCE.md` §1) |
| `data/synthetic/policy/coverage-logic.md` | Deductible arithmetic, total-loss formula, KABCO↔SABS boundary, optional-benefit entitlement policy | Mix: the *mechanism* (deductible math, 80%-of-ACV rule) is Example Mutual's own stated construction; the KABCO scale itself is **real** (NHTSA MMUCC standard, harvested Phase 0 from repo 5); the SABS severity-tier *dollar figures* it references are corpus construction choices (see below) |
| `data/synthetic/policy/endorsements.md` | Rental (OPCF-20-modeled) and towing (bundled allowance) | Modeled on **real** Ontario endorsement product categories (OPCF 20, OPCF 35 named-but-not-built); specific dollar terms ($50/day, $1,000 cap, $150 towing) are Example Mutual's own construction, grounded against real-world reference *ranges*, not claimed to match any filed rate |
| `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` | Regulatory grounding + full citation audit | Mixed-strength, graded claim-by-claim in its own §8 — this data card doesn't restate that grading, it points to it |
| `data/synthetic/policyholders/policyholders.json`, `vehicles.json`, `claims.json` | Structured seed records for the mock claims/CRM tool layer | **100% fabricated** — names, contact info, addresses, VINs, plates, claim narratives. Numeric fields (deductibles, ACVs, repair costs, settlements) are internally consistent by construction, machine-validated (`scripts/validate_synthetic_records.py`), not derived from any real claims data |

## 2. What's real (verified, cited, with a grade in `ONTARIO-INSURANCE-REFERENCE.md` §8)

- The existence and general shape of Ontario's OAP 1 policy structure, DCPD, and the SABS.
- The **2026-07-01 SABS reform** making several accident benefits optional — 🟢 directly quoted from FSRA's
  own page, the strongest-grade claim in the whole corpus.
- The $200,000 statutory minimum Third Party Liability limit — 🟢 directly quoted from FSRA.
- DCPD's no-fault mechanics, the 2024-01-01 opt-out date, and — caught during citation verification, not
  assumed — that a DCPD deductible is *optional*, not universally absent — 🟢 directly quoted from FSRA.
- The Ontario Fault Determination Rules' fixed percentage-band structure (0/25/50/75/100%) — 🟡/🔴, primary
  regulation URL confirmed to resolve but not machine-readable; percentage bands confirmed via secondary
  sources only.
- That Ontario sets **no single legislated total-loss percentage** — confirmed 🔴 across multiple independent
  secondary sources agreeing on this specific point (the absence of a number is itself the corroborated fact).
- The KABCO injury-severity scale (K/A/B/C/O) — real NHTSA MMUCC standard, harvested in Phase 0 from source
  repo 5, not re-verified in Phase 3 (no new claim was made about it here).

## 3. What's a corpus construction choice, not a verified regulatory fact

**Restated here per Marco's instruction, after being reframed in `ONTARIO-INSURANCE-REFERENCE.md` §§1 and 3:**

> Example Mutual's synthetic corpus uses $3,500 / $65,000 / $1,000,000 as its SABS tier caps, matching
> values widely reported for post-2026-07-01 Ontario SABS. Primary sources were inaccessible at time of
> writing (see `ONTARIO-INSURANCE-REFERENCE.md` §8). These are corpus parameters, not verified regulatory
> citations.

The same disposition applies to:
- OAP 1's specific section numbering (3 Liability, 4 Accident Benefits, 5 Uninsured Auto, 6 DCPD, 7 Loss or
  Damage, 8 Statutory Conditions) — a widely-reported structure the corpus adopts for fidelity, not a number
  confirmed against directly-read primary text.
- The Income Replacement Benefit formula (70% of gross weekly income, $400/week max, 104 weeks) — same
  secondary-source-only grade as the other SABS dollar figures.

**Why this is still worth having built:** ground truth for this project's Phase 6 evals is the **corpus's own
internal consistency** — every dollar figure traces through `coverage-logic.md`'s formulas exactly, machine-
verified (`scripts/validate_synthetic_records.py`), regardless of whether each figure has been independently
confirmed against currently-inaccessible primary Ontario legislative text. The structural fidelity (real
coverage categories, real mechanism shapes, a real and current regulatory reform reflected accurately) is
what makes this corpus more useful than generic North American boilerplate for eval purposes — that value
doesn't depend on every dollar amount being provably exact.

## 4. What has no external grounding at all — authored from scratch

- **Rental and towing dollar terms** ($50/day, 20-day/$1,000 cap, $150/incident towing allowance) — grounded
  against real-world *reference ranges* (§8, sources C1–C2) but the specific numbers are Example Mutual's own
  invention, same as any insurer's actual filed rates would be.
- **Example Mutual's 80%-of-ACV total-loss rule** — a specific number chosen within the real, corroborated
  70–80% insurer-discretion range (§8, source C3), not itself sourced from anywhere.
- **Every policyholder, vehicle, and claim record** — entirely fabricated, including names, contact
  information, addresses, VINs (with deliberately invalid check digits, per `docs/phase3/DATA-CONTRACTS.md`
  §3), plates, loss narratives, and dates. No real claims data of any kind was used, referenced, or
  approximated.
- **The claim-number format** (`CLM-YYMM-NNNNN-C`, Luhn mod-10) — an original design (`docs/phase3/
  DATA-CONTRACTS.md`), not modeled on any real insurer's numbering scheme.

## 5. PII and image gates (continuation of Phase 0's cleared gates)

No real customer or policy data anywhere in this corpus. All names are placeholder-style; phones use the
`555` reserved exchange; emails are `@example.com`; addresses are generic Ontario street + city, not real
locations tied to any real incident. No images anywhere in Phase 3 output, continuing the blanket no-images
rule from Phase 0. VINs deliberately fail NHTSA check-digit validation by one position, machine-verified —
never the structurally-valid VIN flagged in Phase 0 archaeology, and never a real WMI (fictional `9SY` used
throughout).

## Sources

Provenance grading in §§2–4 above is a summary view; the authoritative, per-claim citation grades with tested
URLs live in `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` §8. This card does not re-verify anything — it
organizes what that document and `scripts/validate_synthetic_records.py` already established, for a reader
who wants the provenance answer without reading the full citation audit.
