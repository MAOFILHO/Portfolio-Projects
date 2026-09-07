# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/`,
`docs/phase1/`, and `docs/handoffs/`, never here. Check this file's size before every edit — ceiling
is ≤400 lines/~20KB; move the oldest closed material out first if an addition would exceed it.

## Current phase

**Phase 2 — Realtime session, agent core, gate, test harness. 7 of 8 tickets built** (#17-#23,
now #20 too); the six built before this update were reviewed and fixed, **#20 is built but not
yet run through `/code-review`.** Spec: GitHub issue #16. Tickets: #17–#24 (sub-issues of #16).
Phase 1 closed first — its exit criteria are met and written up in
`docs/phase1/EXIT-AND-PHASE2-ENTRY.md`.

**`APPROVED: Phase 2` was typed by Marco 2026-09-07**, gating #24's billable work. **#24 is still
not started** — three prerequisites are unmet first (see Next actions): the container image build
is unverified, B3's ARM reader has never run live, and the Container App has no managed identity.
Nothing built this session touches Azure, costs money, or has been deployed.

Built and committed (all local, unpushed):
- **#17 `6261e78`** — restructure into the planned package layout. App out of `docs/echo-app/`;
  `voice-agent/azbank_voice_agent/` is now one installable package with the module boundaries
  `docs/PLAN.md` specifies. Mechanical, no behaviour change, same test count before and after.
- **#18 `703c74d`** — a whole call runs end-to-end against `FakeTransport` + `FakeRealtimeServer`,
  no Azure, no patching. **This is `docs/PLAN.md`'s Phase 2 headline exit criterion, met.**
- **#19 `3e82d69`, reviewed, gate now denies everyone (`0bf1d03`)** — `dispatch/gate.py`'s
  `PERMISSIONS` table was reviewed per CLAUDE.md's never-auto-accept rule and emptied: no
  agent/state pair is permitted anything until Phase 4 adds a real `AUTHENTICATED` transition.
  Demo call now gets refused rather than answered, as intended.
- **#21 `e79f50c`** — B3 boot guard, keyed on (name, version) together, reading the live deployment
  at boot, failing closed. Guard code itself unchanged this session. **Cannot deploy as-is (see
  Next actions).**
- **#22 `464a4e5`, reviewed and fixed (`0ce99d5`)** — `T-B3-SUCCESSOR-BOOT` now proves a real
  sequence (guard admits the successor, then a full turn completes), not two disconnected facts.
  Still skip-by-default; run deliberately with `AZBANK_RUN_SUCCESSOR_BOOT=1`.
- **#23 `7dbbdcb`, reviewed and fixed (`a1106b4`, `5179c5e`)** — `make lint` (ruff + mypy) and the
  B3 static allowlist check. Checker now covers `docs/*/wizard/*.sh`, `Dockerfile`,
  `pyproject.toml` (not just the package), scans whole-file text (catches a pair literal wrapped
  across lines), and checks `(name, version)` pairs, not just names.
- **#20 `bd005df`, not yet reviewed** — declarative `AgentSpec` table (`agents/specs.py`): identity,
  instructions, tool scope. A call now opens on `gate.TRIAGE_AGENT` (was `BANKING_AGENT`); a
  `handoff_to_banking` function call reconfigures the one existing session onto the banking
  agent's instructions/tools rather than opening a second one, and never touches
  `dispatch_tool_call` or the gate (routing, not a banking action). `dispatch/gate.py` gained the
  `TRIAGE_AGENT` constant only — `PERMISSIONS` is still `{}`, `is_allowed()`'s logic unchanged.
  All 5 of #20's acceptance criteria met; needs `/code-review` before being called reviewed, same
  as the other six.

Two rounds of `/code-review` ran this session (`5288f8a..40a39b5`, then `40a39b5..HEAD`), each
producing Standards + Spec findings; every actionable finding from both is fixed as of `38dec8c`.
Also fixed, not tied to a single ticket: the B2 leak in `realtime/session.py` (tool arguments,
agent transcript, and AOAI error events all now log arrival only, never content — `b9140fb`,
`9197651`), and a CI workflow now exists (`ca53cae`,
`.github/workflows/azure-banking-voice-agentic-ai-ci.yml` at the monorepo root, approved by Marco
by exact absolute path since it falls outside `PROJECT_ROOT`).

Findings raised but deliberately not actioned, with reasoning recorded in the commits/session, not
silently dropped: the B3 static checker still cannot catch a model pin split across unrelated
variables (e.g. bash) — that's the runtime boot guard's job, not this checker's; the successor
rehearsal patches the gate open on purpose (proving the call completes is orthogonal to B1
policy); CI does not auto-run the successor rehearsal (it's designed to be run deliberately, not
routinely).

**93 tests green, ~0.5s, no cloud dependency** (3 skipped: the successor rehearsal, by design).
`make lint` clean. Not built: **#24** (typed approval now in hand, but real infra work — see Next
actions — and a human to dial are still needed first).

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

1. **`/code-review` #20** — the six other Phase 2 tickets each got a Standards+Spec pass before
   being called reviewed; #20 hasn't yet. Do this before treating #20 as done the way #17-#19/21-23
   are.
2. **This whole session's work is unpushed** — 22 commits ahead of `origin/azure-banking-work`.
   `git push origin azure-banking-work` from this session failed (`Permission denied (publickey)`
   — no SSH access to Marco's GitHub key from this sandboxed environment); needs to be pushed from
   a machine that has it. Not a formal gate, but real risk: it all exists in one worktree only.
3. **Before any Phase 2 deploy, one thing is now verified, one still isn't, and one will fail:**
   - **B3's ARM reader is now verified live** (2026-09-07, this session, under `az login`) — read
     against the real `aoai-azure-banking-voice-cc` deployment, confirmed
     `('gpt-realtime-mini', '2025-10-06')`, matching the active pin exactly. Free, read-only, no
     resource created.
   - The container image build is **still UNVERIFIED** — Docker isn't running in this session's
     environment either (checked twice, 2026-09-07). `docker build voice-agent/` is the check,
     needs a machine with Docker running.
   - The Container App has **no managed identity and no ARM permissions**, so the boot guard will
     correctly refuse to start the deployed app until that identity + role assignment + three env
     vars exist. That is B3 working, not a bug — but it is real infrastructure work
     (`docs/PLAN.md` puts managed identity in Phase 7) that nobody has done. This step needs
     Marco's hands (a live provisioning decision) — `/wizard` territory, not something to script
     unattended.
4. **`ADR-003` — Accepted 2026-09-07.** Stay on the base `openai` SDK, do not adopt `openai-agents`.
   `docs/PLAN.md`'s stale `openai-agents >= 0.3.0` pin instruction and `RealtimeSession`/
   `model_config` phrasing are corrected (`05cb998`).
5. **#24: `APPROVED: Phase 2` is typed.** What's left: item 3's remaining two prerequisites (image
   build, managed identity), re-provisioned compute, and a human to dial, before the provisional
   B5 latency figure (≥100 real turns) can be measured. `docs/PLAN.md`'s Exit paragraph makes this
   figure load-bearing for the phase's formal close, not optional. Dialing the call itself is
   `/wizard` territory — Marco's hands/voice, not something Claude can do.
6. Recompute R-08's demo-runs/month figure against the 2026-09-01 IDLE verdict (currently stale at
   Phase 0's 79.2 figure).
