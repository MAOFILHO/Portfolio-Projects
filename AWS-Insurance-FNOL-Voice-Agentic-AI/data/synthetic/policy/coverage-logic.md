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
  7), or if the policyholder has added an optional DCPD deductible. It is **$0 under Third Party Liability**
  (Section 3, never carries a deductible) **and $0 under DCPD (Section 6) for every policyholder in this
  corpus** — ⚠ this is a stated corpus simplification, not a universal rule: FSRA's own guidance confirms an
  Ontario insurer may offer an optional DCPD deductible to lower premium, and this project's synthetic
  policyholders are modeled as uniformly not having added one (`docs/phase3/ONTARIO-INSURANCE-REFERENCE.md`
  §4), the same simplification pattern as the DCPD-opt-out decision.
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

## 4. Answering "am I entitled to X?" for optional SABS benefits

Because the 2026-07-01 SABS reform made Income Replacement, Caregiver, Housekeeping & Home Maintenance,
Dependent Care, Death & Funeral, and Indexation benefits individual elections (`docs/phase3/
ONTARIO-INSURANCE-REFERENCE.md` §3), two policyholders holding otherwise-identical policies can have
different answers to "am I covered for X" — the shared policy wording alone can't answer that; it has to come
from the specific policyholder's record. This section decides how the agent handles that, and reframes the
question Marco posed (structured record vs. deflect vs. "depends on benefit type") because the real answer
doesn't split on benefit type — **it splits on question type.**

**Two distinct question types, answered two different ways:**

1. **"Is X part of my coverage?" — an election-fact lookup.** Answerable directly, **from the structured
   policyholder record** (not the RAG corpus, which is generic across every policyholder and structurally
   cannot know one caller's elections):
   - For a **mandatory** coverage (Third Party Liability, DCPD, Uninsured Automobile, Medical/Rehabilitation/
     Attendant Care at any severity track) — the answer is "yes" for every policyholder, and is answerable
     from the **RAG corpus alone**, no tool call needed, since it's a fact about the policy form, not about
     any individual.
   - For an **optional** benefit or endorsement (the six 2026-07-01 elections above, the Section 7 Loss-or-
     Damage selection, and the rental endorsement) — the answer varies by policyholder, so `CoverageQuestion`
     becomes a **RAG+tool compound case here too**, not only in intent 4: the agent retrieves the general
     "what this benefit is" text from the wording (RAG), then calls the mock policy system for this specific
     caller's `elected_benefits` map (tool) before answering yes/no. **This is a real scope note for Phase 4/5
     conversation design, flagged here rather than discovered mid-implementation**: `CoverageQuestion` is not
     a pure-RAG intent for every sub-question the way it might look from the wording document alone.
2. **"Will I actually receive X, and how much?" — an eligibility/adjudication question.** **Always deflected
   to a human**, regardless of whether the underlying benefit is mandatory or optional. This follows directly
   from decisions already made elsewhere in this document and in the broader architecture: payout on Medical/
   Rehabilitation/Attendant Care depends on a clinical severity-track assessment this agent never performs
   (§3 above); DCPD-vs-Collision payout depends on a fault percentage this agent never computes (§2, `ADR`
   framing); total-loss settlement depends on a repair estimate the agent doesn't have until an adjuster
   inspects the vehicle. The FNOL specialist's own authority is $0 settlement, cannot deny
   (`docs/phase0/DOMAIN-ARTIFACTS.md`'s harvested authority model) — an agent with less standing than the
   human it escalates to should not attempt an amount or eligibility determination either.

**Why not "deflect everything" or "answer everything from the record":** deflecting a plain yes/no coverage
fact ("do I have rental coverage") would violate this project's own harvested design principle — "don't make
a distressed caller repeat known data" / don't be needlessly unhelpful when the answer is a simple lookup.
Answering an eligibility/amount question directly would mean the agent adjudicating a claim, which nothing
in this architecture authorizes it to do. The boundary is the question, not the benefit.

**Baked into the synthetic records (task 5, next):** policyholders are generated with **deliberate variation**
in their optional-benefit elections — some with Income Replacement Benefit elected and some without, some
with Collision, some with Comprehensive, some with All Perils, some with the rental endorsement and some
without — specifically so `CoverageQuestion`'s election-fact-lookup path has real, differing ground truth to
be evaluated against in Phase 6, not a corpus where every policyholder looks the same.

---

## Sources

Dollar figures and the 80%-of-ACV total-loss framing trace to `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md`,
verified live 2026-08-11. The KABCO scale itself traces to `docs/phase0/DOMAIN-ARTIFACTS.md` (repo 5,
NHTSA MMUCC standard). No figure in this document is asserted from memory without that chain.
