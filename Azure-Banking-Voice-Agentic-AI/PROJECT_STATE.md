# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/`,
`docs/phase1/`, and `docs/handoffs/`, never here. Check this file's size before every edit — ceiling
is ≤400 lines/~20KB; move the oldest closed material out first if an addition would exceed it.

## Current phase

**Phase 2 — Realtime session, agent core, gate, test harness. 6 of 8 tickets built, none reviewed.**
Spec: GitHub issue #16. Tickets: #17–#24 (sub-issues of #16). Phase 1 closed first — its exit
criteria are met and written up in `docs/phase1/EXIT-AND-PHASE2-ENTRY.md`.

**No `APPROVED: Phase 2` has been typed.** Marco invoking `/implement Phase 2` on 2026-09-07 was
read as go-ahead for the phase's non-billable work; the typed approval still gates anything
billable, so **#24 was deliberately not started**. Nothing built this session touches Azure, costs
money, or has been deployed.

Built and committed (all local, unpushed, **none reviewed by a human yet**):
- **#17 `6261e78`** — restructure into the planned package layout. App out of `docs/echo-app/`;
  `voice-agent/azbank_voice_agent/` is now one installable package with the module boundaries
  `docs/PLAN.md` specifies. Mechanical, no behaviour change, same test count before and after.
- **#18 `703c74d`** — a whole call runs end-to-end against `FakeTransport` + `FakeRealtimeServer`,
  no Azure, no patching. **This is `docs/PLAN.md`'s Phase 2 headline exit criterion, met.**
- **#19 `3e82d69`** — `dispatch/gate.py`, deny-all by default, plus the structural proof that it is
  in front of every declared tool. **B1 surface — needs a human look (see Next actions).**
- **#21 `e79f50c`** — B3 boot guard, keyed on (name, version) together, reading the live deployment
  at boot, failing closed. **Cannot deploy as-is (see Next actions).**
- **#22 `464a4e5`** — `T-B3-SUCCESSOR-BOOT`, skip-by-default.
- **#23 `7dbbdcb`** — `make lint` (ruff + mypy) and the B3 static allowlist check, all passing.

**69 tests green, 0.19s, no cloud dependency** (3 skipped: the successor rehearsal, by design).
`make lint` clean. Not built: **#20** (agent table + handoff — blocked on #19 being reviewed, since
it extends the same permission table) and **#24** (needs the typed approval and a human to dial).

**Phase 1 remains the demonstrable deliverable and still works** — the restructure preserved B4's
per-call caps and B2's tone handling, both still covered by their own tests.

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

1. **Review the two diffs `CLAUDE.md` says never get auto-accepted**, before anything is built on
   top of them:
   - **`3e82d69` (#19, B1 gate).** One judgement call to confirm or reverse: `PERMISSIONS` grants
     `get_balance`/`transfer`/`list_accounts` to an **anonymous** caller. Rationale in the module —
     nothing real is behind those tools (an in-memory dict), and Phase 1's six exit rows depend on
     them. The justification is "there is nothing behind these tools", not "these tools are safe",
     and it expires the moment Phase 3 adds a real network path. Denying them instead is a one-line
     change that breaks the demo call until Phase 4.
   - **`e79f50c` (#21, B3 guard).** Also touches the DTMF-adjacent boot path indirectly.
2. **#20 is deliberately blocked on that review** — it extends the same permission table, and
   stacking a second unreviewed B1 change was avoided on purpose.
3. **Before any Phase 2 deploy, two things are unverified and one will fail:**
   - The container image build is **UNVERIFIED** — Docker was not running when #17 rewrote the
     Dockerfile. `docker build voice-agent/` is the check.
   - B3's ARM reader has **never been run live**. Verify free and read-only, no deploy needed:
     `AZURE_SUBSCRIPTION_ID=… AZURE_RESOURCE_GROUP=… AOAI_ACCOUNT_NAME=… AOAI_DEPLOYMENT=gpt-realtime-mini
     python -m azbank_voice_agent.boot` under `az login`.
   - The Container App has **no managed identity and no ARM permissions**, so the boot guard will
     correctly refuse to start the deployed app until that identity + role assignment + three env
     vars exist. That is B3 working, not a bug — but it is real infrastructure work
     (`docs/PLAN.md` puts managed identity in Phase 7) that nobody has done.
4. **`ADR-003` is Proposed, not Accepted** — stay on the base `openai` SDK rather than adopting
   `openai-agents`. Needs Marco's confirmation. Consequence if accepted: `docs/PLAN.md`'s
   "pin `openai-agents >= 0.3.0`" line and Phase 2's "`RealtimeSession` via `model_config`"
   phrasing are stale and need a separate approved edit.
5. **#24 needs `APPROVED: Phase 2` typed**, plus re-provisioned compute and a human to dial, for
   the provisional B5 latency figure (≥100 real turns).
6. Recompute R-08's demo-runs/month figure against the 2026-09-01 IDLE verdict (currently stale at
   Phase 0's 79.2 figure).
