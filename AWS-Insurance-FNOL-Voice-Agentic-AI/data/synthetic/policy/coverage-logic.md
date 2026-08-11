# Coverage Logic — deductibles, total loss, injury-severity mapping

Resolves `Q5` ("deductible logic, total-loss threshold, and injury-severity→coverage mapping have no prior
art"). This is the **computable rules spec**, not retrieval prose — Phase 5's `src/fnol_voice_agent/
validation/coverage.py` (per `docs/phase0/TARGET-LAYOUT.md`'s REFACTOR mapping of repo 7's
`check_coverage_limits`) implements exactly these rules; nothing here is decorative. Companion to
`example-mutual-oap-policy-wording.md`, which is the retrieval prose these rules are grounded in.

---

## 1. Deductible arithmetic

```
covered_payout = min(repair_or_replacement_cost, coverage_limit) − deductible_if_applicable
```

- `deductible_if_applicable` = the policyholder's selected deductible (**$500 or $1,000**, from the
  Declarations Page) **only** when the claim is paid under Collision, Comprehensive, or All Perils (Section
  7). It is **always $0** under DCPD (Section 6) or Third Party Liability (Section 3) — those sections never
  carry a deductible, per the policy wording.
- `coverage_limit` — Third Party Liability: $1,000,000 (Section 3). Loss or Damage: uncapped up to the
  vehicle's Actual Cash Value (a damage claim can't exceed what the car is worth; see total-loss rule below).
- Result floors at $0 — a payout is never negative even if `deductible_if_applicable` exceeds the loss amount
  (in which case the claim is simply not economical to file, and the policyholder is told that plainly rather
  than being walked through a claim that nets $0).

**Worked example:** $1,800 windshield/body damage, Comprehensive coverage, $500 deductible → payout =
min($1,800, ACV) − $500 = **$1,300**.

**Worked example, DCPD, no deductible:** $4,200 damage, not-at-fault DCPD claim → payout = min($4,200, ACV)
− $0 = **$4,200**.

## 2. Total-loss determination

```
is_total_loss = (estimated_repair_cost >= 0.80 * actual_cash_value)

if is_total_loss:
    settlement = actual_cash_value − deductible_if_applicable
else:
    settlement = covered_payout   # §1's formula
```

- The **80% of ACV** threshold is Example Mutual's own stated claims-handling rule (Section 7 of the policy
  wording), not a legislated Ontario percentage — Ontario leaves this to insurer discretion, typically in the
  70–80% range (`docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` §6). Chosen at the upper end of that range and
  disclosed in the policy wording rather than left as undisclosed adjuster discretion.
- `deductible_if_applicable` follows the same rule as §1: $0 for a not-at-fault DCPD-settled total loss, the
  policyholder's selected amount for an at-fault or single-vehicle Collision/Comprehensive total loss.
- **Vehicle branding** (Ontario's "salvage"/"irreparable" labels) is a separate, regulatory, post-settlement
  process — this project does not model it; it only computes the settlement decision above, which is the
  FNOL-relevant piece (whether/what a caller can expect to be paid), not the subsequent title-branding
  paperwork.

**Worked example:** $16,000 estimated repair cost, $18,000 ACV → 16,000 / 18,000 = 88.9% ≥ 80% → **total
loss**. If Collision-settled (some at-fault share) with a $1,000 deductible: settlement = $18,000 − $1,000 =
**$17,000**. If fully DCPD-settled (not at fault): settlement = **$18,000**.

## 3. Injury-severity mapping — KABCO vs. SABS, kept as two distinct axes

**This is the boundary this project's architecture depends on getting right, and it is stated explicitly
because conflating the two would be a real design error, not a cosmetic one.**

| | KABCO | SABS severity track |
|---|---|---|
| **What it is** | A scene-reported injury scale (NHTSA MMUCC standard), harvested in Phase 0 | A clinical/legal benefit-eligibility tier (MIG / non-catastrophic / catastrophic), defined in the Statutory Accident Benefits Schedule |
| **Who assigns it** | Whoever reports the loss — a caller, a responding officer — describing what they observe or feel, at first notice | A treating medical practitioner, using formal assessment forms, generally over days-to-weeks, not at first notice |
| **When it's available** | Immediately, at FNOL, from the caller's own words | Never at FNOL — it does not exist yet when a claim is first reported |
| **What this project's agent does with it** | **L1** (the deterministic pre-node, `ADR-010`/`D12`/`D15`) uses injury/fatality *language* to trigger immediate hard escalation — it does not classify severity, it detects presence | **Never computed by this agent.** Referenced only in `CoverageQuestion` RAG answers, to describe *what a caller could expect* if their injury turns out to fall into a given track — always phrased as informational, never as a determination this system is making |

**KABCO → informational SABS-track description** (used only by the `CoverageQuestion` RAG surface, when a
caller asks something like "what does my policy cover if I'm hurt" — never used to route, score, or decide
anything):

| KABCO | Description | Informational SABS-track framing (not a determination) |
|---|---|---|
| **K** — Fatal injury | Confirmed or apparent fatality | Never reaches this table — `L1` hard-escalates immediately and bypasses the RAG/generation path entirely (`ADR-010`'s sequence diagram). Death & Funeral Benefits, if elected, are described only by the human escalation path, never generated here |
| **A** — Suspected serious injury | Severe, incapacitating | "Likely assessed under the non-catastrophic track initially; a catastrophic-impairment assessment may follow depending on clinical findings — that determination is made by a medical assessment, not at the time of your call" |
| **B** — Suspected minor injury | Evident but not incapacitating | "Often assessed initially under the Minor Injury Guideline; may be moved to the non-catastrophic track if there's a complicating factor — your treating provider makes that call, not this system" |
| **C** — Possible injury | Claimed but no visible evidence | "Typically starts under the Minor Injury Guideline pending assessment" |
| **O** — No apparent injury | None reported or visible | "No Accident Benefits claim expected; this would be handled as a property-damage-only claim" |

**Why K never reaches this table in practice:** by construction, any K- or A-level language triggers `L1`'s
immediate escalation before the conversation ever reaches the `CoverageQuestion` intent's RAG path — this
table's K row exists for documentation completeness (so a reader doesn't wonder where fatality went), not
because the generation model will ever actually produce it.

---

## Sources

Dollar figures and the 80%-of-ACV total-loss framing trace to `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md`,
verified live 2026-08-11. The KABCO scale itself traces to `docs/phase0/DOMAIN-ARTIFACTS.md` (repo 5,
NHTSA MMUCC standard). No figure in this document is asserted from memory without that chain.
