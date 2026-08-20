# ADR-002 — Geography knobs

Status: Accepted
Date: 2026-08-20

## Context

The question this ADR originally set out to answer: does ACS's `dataLocation` property constrain which
countries or localities a phone number can be purchased from, forcing this project's ACS resource and
Azure OpenAI resource into a coordinated regional split? **Answer, confirmed empirically: no.** Number
purchase is gated only by the Azure subscription's billing address (Canada), never by the ACS resource's
`dataLocation` — there was never a technical coupling to design around. `location` (ACS's ARM
control-plane field) is always `'global'` — ACS is not a regional resource — and is independent of
`dataLocation` (data-at-rest geography, governing only call artifacts and resource metadata).

That question turned out not to be the interesting one. Investigating it surfaced a real, undocumented
platform constraint instead:

**ACS's Canadian geographic phone number inventory is thin and volatile, not merely uncoupled from
`dataLocation`.** Measured, not assumed — full queries and evidence in `docs/phase0/findings.md`
("R-05", "R-05 supplemental", "ACS Canadian phone number inventory is genuinely volatile"):

- An unfiltered List Available Localities query (no `locality`/`administrativeDivision` filter — the
  only way to see the whole inventory rather than test one guess at a time) returned **10 localities in
  the entire country** at first check: Brockville, Guelph, North Bay, Sault Sainte Marie, Thunder Bay
  (all ON); Chicoutimi, Montreal, Thetford Mines (QC); Biggar, Lanigan (SK).
- **Toronto is absent. No GTA-adjacent locality is present at all** — none of 416/647/437/905/289 are
  reachable through this API, at any point this project queried it. Confirmed against the country-wide,
  unfiltered list, not inferred from a single Toronto-filtered query returning `404` — a control query
  against a locality that *is* listed (Guelph) returned a clean `200` with a real area code in the same
  window, ruling out a broken endpoint, a bad token, or a malformed request as the explanation.
- **The inventory changed within the same session, ~20 minutes apart.** Guelph returned `200` /
  `areaCode: 226` on first check. A re-check roughly 20 minutes later returned `404 NotFound`,
  reproduced three times, two seconds apart, to rule out a transient blip. A re-run of the unfiltered
  nationwide dump confirmed the drop was real inventory change, not a query fluke: 8 localities
  remained — Guelph and Biggar both gone, the other 8 unchanged.
- No documented explanation from Microsoft rules this in or out — not a rate limit, not a permissions
  scope, not an API version issue (all independently ruled out; see `findings.md`). The most plausible
  explanation is real-time contention for a small shared number pool across every ACS customer
  purchasing in the same localities, but that is stated there as inference, not as a confirmed fact.

## Decision

Two decisions follow directly from this finding, not from the original `dataLocation` question:

1. **Decision 13 (`docs/PLAN.md`) revised.** "Canada local geographic, Toronto area
   (416/647/437/905/289)" is unfulfillable against ACS's actual Canadian inventory — not "available but
   taken," genuinely absent. Revised to **705 (North Bay / Sault Ste Marie, ON)**, live-confirmed
   purchasable via Search Available Phone Numbers immediately before purchase, not carried over from an
   earlier List Area Codes check in the same session.
2. **R-09 added** to `docs/PLAN.md`'s tracked risks and to `CLAUDE.md`'s stop conditions: the
   purchased number is never released, by any script, at any phase, for any reason. Given observed
   volatility, there is no guarantee an equivalent replacement — or any number in the same numbering
   plan area — would still be purchasable if this one were ever lost, unlike almost every other resource
   in this project, which Bicep/the deploy CLI can recreate identically. Every purchase-adjacent script
   must re-verify actual inventory via Search Available Phone Numbers (not List Area Codes / List
   Localities, which only prove a locality is server-side recognized, not that a number is currently
   reservable) immediately before acting — never from an earlier-in-session check, however recent.

Number actually purchased under this revised decision: `+17059100383` (`COSTS.md`,
"First billable resource purchased").

## Consequences

- The `dataLocation`/number-purchase coupling question is fully closed: no cross-region hop, no design
  constraint to build around. ACS (`location: global`, `dataLocation: Canada`) and Azure OpenAI
  (Canada Central) share a single jurisdiction by choice, not by technical requirement — the residual
  gap in that jurisdiction claim is ADR-001's, not this one's.
- The real constraint this project designed around here is inventory scarcity and volatility, not
  geography-pairing. There is no further number-purchase code path planned past Phase 0, but if one is
  ever added, it must treat a `200` from the locality/area-code list endpoints as a point-in-time
  snapshot with no stated TTL, never a purchase guarantee.
- This is a genuinely undocumented characteristic of ACS's Canadian geographic-number product — not
  inferable from Microsoft's public pricing or availability pages, not something a plan written from
  documentation alone would have caught. Recorded here as a platform finding for the Phase 8 portfolio
  write-up: the kind of thing that distinguishes having built on ACS from having read about it, not a
  note explaining away a changed plan.
