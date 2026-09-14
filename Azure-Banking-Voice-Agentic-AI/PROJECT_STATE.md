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

Phase 6 is in progress (`docs/phase6/exit-criteria.md`, 19 decisions settled 2026-09-11) — issue #61's
code is committed, #62's provisioning is prepared but not applied — see "Current phase" below.

Check this file's size before every edit — ceiling is **≤400 lines / ~20KB**; move the oldest closed
material into the archive above if an addition would exceed it.

## Stop conditions in force

`CLAUDE.md`'s stop-conditions list is canonical and is not restated here. These are the ones with a
live bearing on the current moment:

1. **The phone number `+17059100383` is never released**, by any script, at any phase, for any
   reason (R-09). Irreplaceable, not merely billable.
2. **No billable Azure resource without Marco typing `APPROVED: <phase name>`.** `APPROVED: Phase 5`
   (used) and `APPROVED: Phase 6` (typed 2026-09-12) are both on record. Phase 6's gate covers issue
   #62's Application Insights, prepared (`infra/provision-app-insights.sh`) but **not yet run** — that
   script still needs your own look before it applies, per the next rule down.
3. **`dispatch/` changes are never auto-accepted**, even when `gate.py` itself is untouched.
4. **B1's sharpened definition stands**: no *banking* operation — balance, transfer, list,
   transactions, card block — reaches the core-banking client while the call is unauthenticated. The
   set reachable while anonymous is **exactly the PIN check and asking for a person**. Held across
   every live call in Phase 5, including the ones that failed to complete their script — 0 breaches.
5. **This file is updated before any session ends**, and never exceeds the ceiling above.

## Current phase — Phase 6 (Observability), started 2026-09-12

**Phase 5 closed 2026-09-12.** Exit met; two criteria met with a stated limit (B5 frozen on the
real-call pool only; the acceptance call's evidence is scattered across the day rather than one
continuous call, Marco's explicit choice). Full account: `docs/phase5/exit-check.md`.

**Phase 6's design is done** (`docs/phase6/exit-criteria.md`) but its entry conditions are only
partly met. From that file's own table, re-checked 2026-09-12:

| condition | state |
|---|---|
| Phase 5's exit criteria written | ✅ Satisfied |
| Phase 5's exit criteria met | ✅ **Now satisfied** — closed today, see above |
| Marco's sign-off on Phase 5 | ✅ **Given 2026-09-12** |
| Marco's approval to begin Phase 6 | ✅ **Given 2026-09-12** — explicit choice to start now, research items 15/16 in parallel |
| Open item 16 settled (`/research`) | ✅ **Settled 2026-09-13** — no default/opt-in body capture in any of the three instrumentations; D8's blocker lifted |
| Open item 15 settled (`/research`) | ✅ **Settled as "undocumented" 2026-09-13** — resolves via criterion 4's own fallback (`RequestResponse` stays disabled) |
| B2 widening signed off | **NOT given** |
| Phases 4+5 reviewed (`git log e42c063..HEAD`) | **Still NOT done** — today's `/code-review` covered only `a7e06d1..HEAD` (17 of the 42 commits since `e42c063`); the other 25 remain unreviewed |

**Six of eight conditions are now met.** Only the B2 widening sign-off and the 25-commit review
remain, and neither blocks the code already in flight below.

**Phase 6 specced and split into two tickets** (`/to-spec`, 2026-09-12/13):
- **#61** — the code: spans, metrics, D15 allowlist, fail-open exporter, ADR, and (as of the
  2026-09-13 research) FastAPI/httpx instrumentation. Ships and passes CI against an in-memory
  exporter only; touches no live Azure resource.
- **#62** — provisioning Application Insights and wiring the real exporter, blocked by #61 (Marco's
  call, 2026-09-13: keep provisioning separate, land after the code).
Both carry `ready-for-agent`. `RequestResponse` and the widened B2 wording stay off by decision, not
by open blocker — see the entry-conditions table above.

### Needs Marco

1. **The B2 widening** (`docs/phase6/exit-criteria.md`, "B2, proposed new wording") needs sign-off
   before Phase 6 can touch it — a named constraint does not move without one.
2. **`git log e42c063..HEAD` (25 commits) is still owed a human read** — waived once already at
   Phase 5 entry, not resolved by today's narrower review.

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
- Storage account `stazbankcallrecords`, table `callrecords`. Write-then-read proven live through the
  voice agent's managed identity.
- Container App `ca-azbank-core-banking`, internal-only ingress (deliberate, criterion 22 — also why
  Phase 5's B5 probe pool could not be gathered from outside the environment), `Healthy`, one replica.
- **Container App `ca-azbank-echo-p0`**, min-replicas=1 (**billing now**), running
  `docker.io/maofilho/azbank-echo-p0:p5i`, revision `--0000011`, `Healthy`, 100% traffic, 0 restarts —
  the routing/transfer-word fix, confirmed live 2026-09-12. Its system-assigned identity
  (`5e09fe34-8913-4aa2-80ac-618af308a88f`) holds `Reader` on the AOAI resource and `Storage Table Data
  Contributor` scoped to `stazbankcallrecords`.
- **Data-plane auth to AOAI is still the `AOAI_KEY` secret**; Storage auth is managed identity only.
- **Logs: query `workspace-rgazurebankingvoiceagenticai1D`** (`bf520f2c-e2bc-4488-8965-9317a7922c74`),
  never `...aiCS`, which has been stale since 2026-08-25. `...aixC` is an orphan. Three workspaces
  exist, not two.
- **Application Insights `appi-azure-banking-voice`** (issue #62), workspace-based on `...1D`,
  `provisioningState: Succeeded`, created and wired 2026-09-14 (Marco, `infra/provision-app-
  insights.sh`). `ca-azbank-echo-p0` revision `--obs20260914111702` is Active/Healthy/100% traffic,
  carrying `APPLICATIONINSIGHTS_CONNECTION_STRING` (secretref `appinsights-conn`) and
  `AZURE_MONITOR_AUTH=connection_string` — the named fallback, not the identity path (D10's IAM role
  is still an open `/research` question). **Delivery not yet confirmed**: the D16 smoke call and a
  queried row in `...1D` are still owed (`docs/phase6/smoke-call-runbook.md`) — an ARM 200 OK and a
  `Healthy` revision prove wiring, not that a span actually arrived.

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

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

**R-01–R-06 resolved** (R-03 partial, see item 3). **R-08 recomputed 2026-09-11, passes**: fixed
$14.60/mo, 45–67 demo runs/month against a gate of 5 (`COSTS.md`). No input is unpriced. **R-09**
(number irreplaceability) and **R-07** (`spendingLimit: Off`) are standing facts, not open items.
**R-08 recomputed again for Phase 6, 2026-09-13** (`COSTS.md`) — Application Insights shares the
container logs' free grant rather than adding one; worst-case bound **$0.00/mo added**, fixed total
unchanged at $14.60/mo. Priced before provisioning, per `docs/phase6/exit-criteria.md` D4; the
resource itself does not exist yet.

## Next actions (in order)

1. **B2 widening sign-off**, then the code changes it authorizes.
2. **`git log e42c063..HEAD`, human-reviewed** (25 commits, still owed).
3. **One ADR still offered and not written** (`docs/adr/`): the shared core-banking client that made
   B1's restatement necessary, plus Phase 5's `escalate_to_human`-while-anonymous corollary.
4. **Issue #62**: Application Insights is live and wired (2026-09-14) — make the D16 smoke call
   (`docs/phase6/smoke-call-runbook.md`) and query `...1D` for its rows to confirm delivery, the one
   step left before the ticket's criteria are actually met rather than just deployed.
5. **`/research`**: the IAM role Application Insights ingestion needs for D10's Entra-authenticated
   identity path — undocumented anywhere in this repo. Until settled, #62's script wires the named
   connection-string fallback instead (Phase 7 debt).

**Still not written, needs Marco:** the root `CONTEXT-MAP.md` that `docs/agents/domain.md` calls for.
It sits outside `PROJECT_ROOT` and needs approval by absolute path. `CONTEXT.md` (this project's own
glossary) is written and committed.
