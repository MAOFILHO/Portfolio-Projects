# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`): what is true now, what is open, what happens next.
**Nothing past-tense belongs here.** Closed phases are archived per phase and the archives are the
account of what happened:

| phase | closed record |
|---|---|
| 0 | `docs/phase0/findings.md`, `docs/phase0/EXIT-AND-PHASE1-ENTRY.md` |
| 1 | `docs/phase1/archive.md`, `docs/phase1/EXIT-AND-PHASE2-ENTRY.md` |
| 2 | `docs/phase2/archive.md` |
| 3 | `docs/phase3/archive.md` (exit criteria: `docs/phase3/exit-criteria.md`) |
| 4 | `docs/phase4/exit-check.md`, `docs/phase4/findings.md`, `docs/phase4/research-carried-findings.md` (exit criteria: `docs/phase4/exit-criteria.md`) |
| 5 | `docs/phase5/exit-check.md`, `docs/phase5/review-fixes.md`, `docs/phase5/commit-review-digest.md` (exit criteria: `docs/phase5/exit-criteria.md`) — **closed 2026-09-12** |
| 6 | `docs/phase6/exit-check.md` (exit criteria: `docs/phase6/exit-criteria.md`) — **closed 2026-09-15** |
| 7 | `docs/phase7/exit-check.md` (exit criteria: `docs/phase7/exit-criteria.md`) — **closed 2026-09-18** |

**Phase 8 is not yet started** — see "Current phase" below.

Check this file's size before every edit — ceiling is **≤400 lines / ~20KB**; move the oldest closed
material into the archive above if an addition would exceed it.

## Stop conditions in force

`CLAUDE.md`'s stop-conditions list is canonical and is not restated here. These are the ones with a
live bearing on the current moment:

1. **The phone number `+17059100383` is never released**, by any script, at any phase, for any
   reason (R-09). Irreplaceable, not merely billable.
2. **No billable Azure resource without Marco typing `APPROVED: <phase name>`.** `APPROVED: Phase 5`,
   `APPROVED: Phase 6`, and `APPROVED: Phase 7` are all on record and all spent. Phase 8 has not been
   designed or approved yet — nothing may be provisioned under its name until it is.
3. **`dispatch/` changes are never auto-accepted**, even when `gate.py` itself is untouched.
4. **B1's sharpened definition stands**: no *banking* operation — balance, transfer, list,
   transactions, card block — reaches the core-banking client while the call is unauthenticated. The
   set reachable while anonymous is **exactly the PIN check and asking for a person**. Held across
   every live call in Phase 5, including the ones that failed to complete their script — 0 breaches.
5. **This file is updated before any session ends**, and never exceeds the ceiling above.

## Current phase

**Phase 7 (IaC completion & CI/CD) closed 2026-09-18** — all 9 exit criteria met, 2 with a stated
limit (both accepted by Marco, both tracked as Phase 7 debt). Full account: `docs/phase7/exit-
check.md`. Real Azure findings from closing it out: a live RBAC gap (research claimed "already
granted," wasn't), two `agents/specs.py` conversational bugs found on real calls, and a stale ACS
webhook after a from-empty redeploy (Container Apps environments get a new random domain suffix on
recreation; the CLI doesn't yet detect a dependency's *value* drifting under an already-deployed
resource) — fixed live, not yet fixed in the CLI itself.

**Phase 8 is not yet started.** No design doc, no exit criteria, no `APPROVED: Phase 8` — per the stop
conditions above, nothing is provisioned under its name until all three exist.

Phase 6 (Observability) **closed 2026-09-15** — all 14 exit criteria met, none with a stated limit.
Full account: `docs/phase6/exit-check.md`.

## Live Azure state

Verify this against the API before acting on it (`CLAUDE.md`, Resume discipline) — it is a snapshot
and goes stale between sessions.

- Resource group `rg-azure-banking-voice-agentic-ai`.
- AOAI `aoai-azure-banking-voice-cc` — `gpt-realtime-mini` 2025-10-06, GlobalStandard, NoAutoUpgrade.
  Re-verified live 2026-09-11: pin retires **2027-04-06**, ~6.8 months out, no stop-and-ask.
  Successor `gpt-realtime-1.5` still GA (retires 2027-08-24).
- ACS `acs-azure-banking-voice`; phone number **`+17059100383`** (owned, $1.00/mo, never released).
- Container Apps environment `cae-azure-banking-voice-p0`, Consumption plan, **amd64-only** — every
  image build for this project must pin `--platform linux/amd64` (memory: `azure-banking-docker-
  platform-pin`, an arm64 image cost real debugging time to diagnose on 2026-09-12).
- **Default domain suffix is `yellowmoss-81870d2d`** as of 2026-09-18's teardown/redeploy — this is
  random per environment and changes on recreation. Confirm live (`az containerapp show`) before
  trusting a webhook URL or FQDN recorded in any doc, this one included.
- Storage account `stazbankcallrecords`, table `callrecords`. Write-then-read proven live through the
  voice agent's managed identity.
- Container App `ca-azbank-core-banking`, internal-only ingress (deliberate, criterion 22 — also why
  Phase 5's B5 probe pool could not be gathered from outside the environment), `Healthy`, one replica.
- **Container App `ca-azbank-echo-p0`**, min-replicas=1 (**billing now**), running
  `docker.io/maofilho/azbank-echo-p0:p7c`, rebuilt from empty 2026-09-18 by the new deploy CLI. Its
  system-assigned identity is **`bb712203-9e00-42a5-a0b5-0f38b376c79e`** — a fresh GUID, since
  recreating the app regenerates the identity. Holds `Cognitive Services OpenAI User` on the AOAI
  resource (granted automatically by the CLI's `aoai` deploy step, no manual `az role assignment
  create` needed this time) and `Storage Table Data Contributor` scoped to `stazbankcallrecords`. Any
  principal ID recorded before 2026-09-18 (including `5e09fe34...` below) is stale.
- **Data-plane auth to AOAI is now the identity token** (`DefaultAzureCredential`, no key fallback in
  code), proven live 2026-09-17 (`docs/phase7/d2-live-call-result.md`). The `AOAI_KEY` env var is
  still present on the container app but unused by code — pending removal alongside the
  `disableLocalAuth: true` flip. Storage auth is managed identity only, unchanged.
- **Logs: query `workspace-rgazurebankingvoiceagenticai1D`** (`bf520f2c-e2bc-4488-8965-9317a7922c74`),
  never `...aiCS`, which has been stale since 2026-08-25. `...aixC` is an orphan. Three workspaces
  exist, not two.
- **Application Insights `appi-azure-banking-voice`** (issue #62), workspace-based on `...1D`,
  `provisioningState: Succeeded`, created 2026-09-14 (Marco, `infra/provision-app-insights.sh`).
- **`ca-azbank-echo-p0` carries `p7c`** — D2's identity-auth code plus both `agents/specs.py` fixes
  from `docs/phase7/d2-live-call-result.md`, live-verified 2026-09-17 and again 2026-09-18 after the
  from-empty rebuild. Revision number is stale after that rebuild — re-check live, don't trust a
  recorded number. Carries `APPLICATIONINSIGHTS_CONNECTION_STRING` (secretref) and
  `AZURE_MONITOR_AUTH=connection_string` (the named fallback, not identity — D10's IAM role is still
  an open `/research` question).
- **D16 smoke call redone and delivery confirmed, 2026-09-15** (`docs/phase6/d16-smoke-call-result.md`,
  correlation id `aa509ec4`). 17 spans landed in `...1D`, `call` span attributes match D15 exactly, B2
  scan zero matches, both cost/latency metrics landed. The first attempt (2026-09-14, `393815d8`) had
  hit the pre-#61 image and produced no spans; not repeated.

## Open items

Full triage of which of these block what: `docs/phase1/EXIT-AND-PHASE2-ENTRY.md` Part 1. Listed here
because they are genuinely unresolved, not because any of them is currently blocking.

1. **No durable ACS-side call-diagnostics path.** App-side container logs deliver correctly. ACS-side
   call diagnostics were never configured. **Phase 6 is NOT its fix** (corrected 2026-09-11) — Phase 6
   produces app-side traces via the OTel Distro's own endpoint, independent of the failed
   `Microsoft.Insights/diagnosticSettings` mechanism. Needs its own decision and a queried table.
2. **`02-test-calls.sh` must not be re-run carelessly.** No skip-if-already-confirmed guard on
   Stages 1-3 — prompts for 3 fresh billable calls before Stage 4's free evidence extraction runs.
3. **R-03's Call-1 zero-DTMF anomaly is permanently unresolved** — dropped as an entry criterion
   2026-08-28, evidence no longer exists.
4. **Docker Hub vs ACR — still on Docker Hub.** Due a decision at Phase 1 kickoff, didn't happen.
5. **Rate-limit meaning unconfirmed** — per-deployment `rateLimits` doesn't reconcile against the
   Quota Tier table. Cheap Foundry-portal check, still not done.
6. **`gpt-realtime-1.5` successor boot untested** against a real successor — the rehearsal
   (`T-B3-SUCCESSOR-BOOT`) exists and is skipped by design.
7. **Stale `az` CLI `defaults.location=eastus`** (this machine). Fix identified (`--location ""`),
   pending sign-off.
8. *(closed 2026-09-13, applied 2026-09-14: `COSTS.md` "R-08, recomputed for Application Insights
   sharing the shared 5 GB grant"; `infra/modules/app-insights.bicep`)* — the Log Analytics
   auto-provision choice is settled as "bind explicitly to the existing `...1D` workspace," not
   "let a fourth workspace auto-provision." Applied live, see "Live Azure state" above.
9. **`silence_duration_ms` 200→600 (`0ed61e0`) has now been exercised by real calls and did not
   recur as mid-PIN interruption.** A different, unrelated silence mode surfaced instead (post-refusal
   silence, `docs/phase5/exit-criteria.md` known-partial 9) — recorded there, not chased further.
10. *(closed, `docs/phase5/review-fixes.md`; number held so 11+ keep their references)*
11. **The DTMF tone vocabulary: `*` confirmed, `#` still unconfirmed.** `*` produces its own log
    outcome (`cleared`) and was observed four times live 2026-09-12. `#` is classified under the same
    catch-all `ignored` outcome as any post-authentication digit, so its exact media-path spelling
    remains unconfirmed — accepted as a known gap (Marco, 2026-09-12). `docs/phase4/research-carried-
    findings.md` §2b.
12. **Nothing guarantees DTMF and audio frames arrive in order on the media socket.** The payload's
    `timestamp` is still unread; not instrumented in Phase 5. Still open.
13. **`RequestResponse` is an Azure OpenAI diagnostic-log category with no documented content
    coverage** (`/research` confirmed 2026-09-13, `docs/phase6/research-content-capture.md` — no
    Microsoft primary source describes it, for Azure OpenAI or the realtime API). Not enabled, must
    not be until its destination table is queried and read; whether it even fires for a realtime
    deployment is unanswered and doesn't need to be, since staying disabled already satisfies Phase
    6's criterion 4.
14. *(closed 2026-09-13, `docs/phase6/research-content-capture.md`: none of the FastAPI/httpx/requests
    instrumentations capture bodies by default or via any opt-in flag at the pinned release. D8/issue
    #61 unblocked. One residual note carried into #61: the ASGI layer's `http.url` attribute includes
    the full query string by default, redacted only for four cloud-signature params — not a live gap
    on this project's query-string-free webhook route, but worth a guard if a future route changes
    that.)*
15. **`transport/acs.py`'s audio branch is not total, unlike its DTMF branch.** Pinned by
    `tests/test_acs.py::test_a_malformed_audio_frame_still_raises`. Not changed — a never-auto-accept
    path nobody asked to alter.
16. **The relay imposes no deadline on the injected PIN-outcome frames.** Deliberately sequenced
    behind live evidence: the injected system message was confirmed accepted 2026-09-12
    (`docs/phase5/exit-check.md`, wire-format question 1), so this deadline is now insurance against a
    case never observed, not urgent.
17. **The call-record store sets no SDK-level timeout, deliberately** — the deadline is at the seam
    (`session.LEDGER_DEADLINE_SECONDS`), tested. `/research` owes the azure-core option names.
18. **The daily ledger's lock is in-process only.** Fine for one replica; ETag optimistic concurrency
    is the fix, deliberately not-yet (Marco, 2026-09-11).
19. **A genuine dropped connection during a pending escalation can still misreport `end_reason`.**
    Fixed 2026-09-14 (`fe1bb82`): the escalation's closing-remark audio now always reaches the caller,
    and the two known races against classification (B4's turn cap; a clean end-of-stream) are closed
    and tested. Left open (Marco's call, same day, round 2 of that fix's own `/code-review`): a real
    abnormal socket close (caller hangs up mid-apology, or the connection errors rather than closing
    cleanly) can still bypass both fixes and log as `"caller_hangup"` or a bare `"error"` instead of
    `"escalated"`. `FakeRealtimeServer` has no fixture for an abnormal close, so this isn't testable
    as the fake stands today — needs one before it can be fixed.

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

**R-01–R-06 resolved** (R-03 partial, see item 3). **R-08 recomputed 2026-09-11, passes**: fixed
$14.60/mo, 45–67 demo runs/month against a gate of 5 (`COSTS.md`). No input is unpriced. **R-09**
(number irreplaceability) and **R-07** (`spendingLimit: Off`) are standing facts, not open items.
**R-08 recomputed again for Phase 6, 2026-09-13** (`COSTS.md`) — Application Insights shares the
container logs' free grant rather than adding one; worst-case bound **$0.00/mo added**, fixed total
unchanged at $14.60/mo. Priced before provisioning, per `docs/phase6/exit-criteria.md` D4; the
resource is now live (created 2026-09-14, see "Live Azure state" above), and no cost delta has
been observed to contradict the pre-provisioning estimate.

## Next actions (in order)

1. *(closed 2026-09-15: B2 widening signed off and implemented — issue #65, `2458da3`. CLAUDE.md's
   B2 row and `docs/phase6/exit-criteria.md` both carry the approved wording and met status.)*
2. *(closed 2026-09-15: `git log e42c063..HEAD` human-reviewed in full — 58 commits, `/code-review`.)*
3. *(closed 2026-09-15: `ADR-005-shared-core-banking-client-and-anonymous-reach.md` written — the
   shared client (issue #35) and the `escalate_to_human`-while-anonymous corollary of B1.)*
4. *(closed 2026-09-15: D16 smoke call redone, delivery confirmed — `docs/phase6/d16-smoke-call-
   result.md`. Issue #62's criteria are now met by live evidence.)*
5. **`/research`**: the IAM role Application Insights ingestion needs for D10's Entra-authenticated
   identity path — undocumented anywhere in this repo. Until settled, #62's script wires the named
   connection-string fallback instead (Phase 7 debt).
6. *(Phase 7 closed 2026-09-18 — all 9 exit criteria met, 2 with a stated limit. Full account,
   including the RBAC-gap and `agents/specs.py` findings, the deploy/teardown CLI build, and the
   live ACS-webhook-staleness bug found and fixed on the closing redeploy:
   `docs/phase7/exit-check.md`.)*
7. **`DOCKERHUB_PASSWORD` still needs adding as a GitHub repository secret** before the `deploy`/
   `teardown` *workflows* can run (the local CLI already works without it being a GitHub secret —
   Marco supplied it as a local env var for today's live runs).
8. **Phase 8 not yet designed.** Needs a design doc + exit criteria + `APPROVED: Phase 8` before any
   work starts, same as every prior phase.

**Still not written, needs Marco:** the root `CONTEXT-MAP.md` that `docs/agents/domain.md` calls for.
It sits outside `PROJECT_ROOT` and needs approval by absolute path. `CONTEXT.md` (this project's own
glossary) is written and committed.
