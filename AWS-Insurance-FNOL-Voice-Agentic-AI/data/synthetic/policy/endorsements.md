# Endorsements — Example Mutual Ontario Automobile Policy

Optional coverages, in force only when shown on a policy's Declarations Page. Resolves the source-corpus gap
`docs/phase0/DOMAIN-ARTIFACTS.md` flagged (`R5`: "rental reimbursement / towing / roadside — zero mentions
across all eight source repos"), authored from scratch and grounded against real Ontario endorsement products
(`docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` §7). This is the retrieval-and-tool-call surface for the
**Rental / Towing Entitlement** intent — the compound RAG+tool case.

---

## Rental Reimbursement Endorsement (Loss of Use)

Modeled on Ontario's real OPCF 20 product. If shown on your Declarations Page, this endorsement pays for a
rental vehicle while your automobile is undergoing **repair for a covered loss** — it does not apply to
routine maintenance, and it does not apply if your automobile is settled as a total loss (a total-loss
settlement compensates you for the vehicle itself, not a rental in the interim).

**Terms, stated explicitly as this project's policy rule (not left to be inferred by a caller or the agent):**

| Term | Value |
|---|---|
| Daily reimbursement cap | **$50/day** |
| Maximum duration | **20 days per claim** |
| Total cap per claim | **$1,000** (= $50 × 20 days — the two limits are consistent, not independent) |
| When it starts | The day your automobile is delivered to the repair facility for a covered repair |
| When it ends | The earlier of: the day repairs are complete, day 20, or the day the $1,000 cap is reached |
| Deductible | None — this endorsement has its own dollar/day caps instead of a deductible |
| Requires | An active, covered claim under Section 6 (DCPD) or Section 7 (Collision/Comprehensive/All
Perils) for the same automobile. Not available on its own. |

**Worked example (the compound RAG+tool case):** a policyholder's automobile has been in the shop 12 days
for a covered collision repair. Entitlement remaining = min(20 − 12, ($1,000 − 12×$50) / $50) = min(8 days,
8 days) = **8 days / $400 remaining**. The tool call this intent makes (Phase 5) looks up `days_in_repair`
from the mock claims system and returns this arithmetic — the RAG half of the intent is *"is rental covered
at all, and under what terms"* (this document); the tool-call half is *"how much is left on this specific
claim"* (mock claims system state, not static text).

## Towing — bundled into the underlying claim, not a separate endorsement here

Deliberate scope decision, named in `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` §7: this project's "towing"
half of intent 4 is the **accident-scene towing allowance already stated in Section 6 of the policy wording**
(`example-mutual-oap-policy-wording.md`) — up to **$150 per incident**, bundled into a covered DCPD or
Loss-or-Damage claim, no separate deductible, no separate endorsement to elect. A caller asking "is towing
covered" is answered from that section directly; there's no separate towing entitlement lookup the way
there's a rental-days-remaining lookup, because towing isn't metered against a running balance the way
rental days are — it's a flat per-incident allowance either included in the claim or not.

Real Ontario roadside-assistance products (OPCF 35: battery boosts, lockouts, non-accident breakdowns) exist
but are out of scope for this intent, since intent 4 is scoped to the post-accident FNOL context, not
roadside breakdowns unrelated to a claim. Named here rather than silently omitted.

---

## Sources

Rental endorsement terms grounded against real OPCF 20 reference ranges ($50/day and $1,000–$2,000 total caps
being common in the Ontario market) verified live 2026-08-11 — see `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md`
§7 for the underlying citations. Exact dollar figures are Example Mutual's own stated terms, not a claim to
match any specific real insurer's actual filed rates.
