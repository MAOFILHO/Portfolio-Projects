# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/`,
`docs/phase1/`, and `docs/handoffs/`, never here. Check this file's size before every edit — ceiling
is ≤400 lines/~20KB; move the oldest closed material out first if an addition would exceed it.

## Current phase

**Phase 1 — Agentic conversation prototype. Exit criteria met 2026-09-01; Phase 2 not yet entered.**
`docs/PLAN.md`'s 6-row exit test table: all 6 PASS on a real call to `+17059100383`. Full exit-criteria
retrospective, open-item triage, and Phase 2 entry options (not decisions): **`docs/phase1/
EXIT-AND-PHASE2-ENTRY.md`**, written 2026-09-07. No `APPROVED: Phase 2` has been typed — Phase 2 has
not begun, and per `CLAUDE.md`'s model/context policy, authoring its exit criteria is Opus's job
(phase kickoff), not Sonnet's.

**This session (2026-09-07): `/code-review`'d Phase 1 (fixed point `46a1b11`..`HEAD`), found
`bridge.py`'s call loop had no upper bound at all, added a bare per-call guard** —
`MAX_CALL_TURNS=20`, `MAX_CALL_SECONDS=300` in `voice-agent/bridge.py`, committed `5113544`. **Not
full B4** — no daily cap, no cost store, no fail-closed-on-unreachable-store (`T-B4-FAILCLOSED`);
that's Phase 5 scope (`docs/PLAN.md:621-624`), named explicitly as such in the code and tests. Also
corrected two stale lines this file previously carried (see "Closed this session" below).

**Mock accounts module, tool-calling bridge, and the `app.py:86` fix are all done, tested, and
verified live** — `voice-agent/accounts.py`, `voice-agent/bridge.py`, `docs/echo-app/app.py`.
24/24 tests pass (`make test`). Two real calls (2026-09-01) exercised balance query, transfer,
mutated-balance re-check, overdraft refusal, unknown-account refusal, clean call end — all correct.

**Step 5 operating-mode verdict: IDLE.** Container settles back to its ~189 KB in/~118 KB out per-
15min baseline within one bucket after a call, across both real calls. R-08's demo-runs/month figure
(79.2, from Phase 0) is stale against this measurement and needs recomputing — not done yet.

## Phase 0 — closed

All 12 stages of `01-provision.sh` ran, first real answered call 2026-08-21, teardown complete
(commit `07faf3b`). Compute was re-provisioned for Phase 1's own work (below) — Phase 0's own
teardown is not the current resource state. Full narrative: `docs/phase0/findings.md`,
`docs/phase0/EXIT-AND-PHASE1-ENTRY.md`, `docs/handoffs/2026-08-24-phase0-closeout-teardown-complete.md`.

**Resources live now**: resource group `rg-azure-banking-voice-agentic-ai`; AOAI
`aoai-azure-banking-voice-cc` (`gpt-realtime-mini` 2025-10-06 GlobalStandard, NoAutoUpgrade); ACS
`acs-azure-banking-voice`; phone number `+17059100383` (owned, $1.00/mo, R-09 — never released);
Container Apps environment `cae-azure-banking-voice-p0`; Container App running Phase 1's
`voice-agent` bridge (min-replicas=1, billing now, IDLE per the measurement above); two Log
Analytics workspaces (`...aiCS` real/linked, `...aixC` orphan, left in place).

## Open items

Full triage of which of these block what, and why none block Phase 1's own exit criteria (already
met): `docs/phase1/EXIT-AND-PHASE2-ENTRY.md` Part 1. Listed here because they're still genuinely
unresolved, not because anything below is currently blocking.

1. **No durable ACS-side call-diagnostics path.** App-side container logs deliver correctly
   (`docs/handoffs/2026-08-27-phase1-logpath-resolved.md`); ACS-side call diagnostics were never
   configured, and per item 3 below, won't be for the R-03 question specifically. Matters more once
   Phase 2 adds a gate whose failures need auditing — Phase 6 (Observability) is its real fix.
2. **`02-test-calls.sh` must not be re-run carelessly.** Stages 1-3 have no skip-if-already-confirmed
   guard — unconditionally prompts for 3 fresh billable calls before Stage 4's free, read-only
   evidence extraction can run. Candidate fix: an `--extract-only` flag.
3. **R-03's Call-1 zero-DTMF anomaly is permanently unresolved for Call 1** — dropped as a Phase 1
   entry criterion 2026-08-28 (Call 1's evidence no longer exists to settle it). Calls 2/3 already
   confirm DTMF works in the common case.
4. **Docker Hub vs ACR — still on Docker Hub.** Was due a deliberate decision at Phase 1 kickoff;
   didn't happen. ACR with managed-identity pull matches Phase 7's "no keys" direction but costs a
   real ~$5/mo.
5. **Rate-limit meaning unconfirmed** — the Models API's per-deployment `rateLimits` field doesn't
   reconcile against the documented subscription-level Quota Tier table. Cheap Foundry-portal check
   (~30s), still not done.
6. **`gpt-realtime-1.5` successor boot untested** — by design, Phase 2's own deliverable
   (`T-B3-SUCCESSOR-BOOT`, needs `FakeRealtimeServer`, which Phase 2 builds).
7. **Stale `az` CLI `defaults.location=eastus`** (this machine only, `~/.azure/config`). Fix
   identified (`--location ""`), shown as a diff, not yet applied — pending sign-off.
8. **Log Analytics workspace auto-provision choice** (`az containerapp env create`'s default, no
   `--logs-destination` flag passed) — tied to item 1; needs a deliberate choice regardless of cost,
   since the auto-provisioned path doesn't even deliver logs.
9. **Intermittent interrupt-the-caller defect.** Agent talks over the caller, cutting in before a
   sentence finishes. Reproduced on the first real call, not the second, same image and VAD config
   both times — nothing explains the absence on the second call. **Explicitly not gating Phase 1's
   exit table** (`docs/PLAN.md`'s own words). Scoped as `server_vad` config tuning, not new code,
   once/if it reproduces again.

**Closed this session (were stale lines in this file, now corrected):** the old "Budget section
stale" item — already fixed by commit `6390cac`, which predates Phase 1's start; and the old
"`app.py:86` has no try/except" item — the fix landed in Phase 1's own work, confirmed by 4 passing
tests and independently by this session's `/code-review`.

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

**R-01, R-02, R-03 (partial, see item 3), R-04, R-05, R-06 resolved.** **R-04 reconfirmed
2026-09-01 for Phase 1's stateful agent loop** (IDLE, see Current phase above). **R-08 answered in
Phase 0 (~79–114 demo runs/month, gate passes) but stale as of the 2026-09-01 IDLE verdict — needs
recomputing, not done.** **R-09** (number irreplaceability) is a standing hard rule, not something
to resolve. **R-07** is a standing fact (`spendingLimit: Off`), not something to resolve.

## Next actions (in order)

1. **Marco decides Phase 2 entry** per `docs/phase1/EXIT-AND-PHASE2-ENTRY.md` Part 3 — proceed to
   Phase 2 at all, who authors its exit criteria (Opus session vs. Marco directly), and whether any
   open item above (1 and 4 are the two flagged) should actually block Phase 2 entry even though
   neither blocked Phase 1's.
2. Recompute R-08's demo-runs/month figure against the 2026-09-01 IDLE verdict (currently stale at
   Phase 0's 79.2 figure).
