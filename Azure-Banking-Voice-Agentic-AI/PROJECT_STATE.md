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

**Phase 7 is open** — see "Current phase" below.

Check this file's size before every edit — ceiling is **≤400 lines / ~20KB**; move the oldest closed
material into the archive above if an addition would exceed it.

## Stop conditions in force

`CLAUDE.md`'s stop-conditions list is canonical and is not restated here. These are the ones with a
live bearing on the current moment:

1. **The phone number `+17059100383` is never released**, by any script, at any phase, for any
   reason (R-09). Irreplaceable, not merely billable.
2. **No billable Azure resource without Marco typing `APPROVED: <phase name>`.** `APPROVED: Phase 5`
   and `APPROVED: Phase 6` are both on record and both spent — issue #62's Application Insights ran
   (2026-09-14) and is live. `APPROVED: Phase 7` is on record (2026-09-16, typed twice) but **not yet
   spent** — every Phase 7 Bicep module written so far (`acs.bicep`, `aoai.bicep`,
   `container-apps-env.bicep`, `voice-agent.bicep`) is WRITTEN, NOT APPLIED; no new resource has
   actually been provisioned under this phase.
3. **`dispatch/` changes are never auto-accepted**, even when `gate.py` itself is untouched.
4. **B1's sharpened definition stands**: no *banking* operation — balance, transfer, list,
   transactions, card block — reaches the core-banking client while the call is unauthenticated. The
   set reachable while anonymous is **exactly the PIN check and asking for a person**. Held across
   every live call in Phase 5, including the ones that failed to complete their script — 0 breaches.
5. **This file is updated before any session ends**, and never exceeds the ceiling above.

## Current phase

**Phase 7 (IaC completion & CI/CD) is open** — design doc approved and `APPROVED: Phase 7` given,
both 2026-09-16 (`docs/phase7/exit-criteria.md`). Goal: every Azure resource this project owns gets a
Bicep module, a CLI can stand the system up or tear it down to zero billable spend, and 3 GitHub
Actions workflows (`ci`/`deploy`/`teardown`) run on OIDC with no long-lived Azure secret.

Done so far: `infra/modules/acs.bicep`, `aoai.bicep`, `container-apps-env.bicep`, `voice-agent.bicep`
— all 7 live Azure resources this project owns now have a Bicep module (the phone number needs none,
verified — ACS manages it exclusively via data-plane REST, outside ARM). All WRITTEN, NOT APPLIED.
D5 (phone-number safety) and D2 (AOAI key retirement)'s Bicep-side guard rails are real, blocking CI
checks (`scripts/check_no_phone_number_release.py`, `scripts/check_aoai_key_migration_consistency.py`).

**Deploy/teardown CLI and workflows written 2026-09-18, not yet run against Azure** — `src/
azbank_deploy/` (Typer, `make deploy`/`make teardown`), `.github/workflows/azure-banking-voice-
agentic-ai-{deploy,teardown}.yml`. Full account, including a real bug the tests caught
(`container_apps_env` could never tear down because `acs` depended on it and `acs` never goes
absent) and the one documented Bicep workaround (Option B, Marco 2026-09-18): `docs/phase7/
deploy-teardown-cli.md`. D5's static check now scans `src/azbank_deploy/` too. **Still needed before
this phase can close**: `/code-review`, then a real `make deploy` run against the live resource
group (already `APPROVED: Phase 7`, but genuinely untested code touching billable resources gets a
look first) and a real `make teardown` run with Marco watching (exit-criteria's own rule).

**D2's live-call verification closed 2026-09-17** —
`docs/phase7/d2-live-call-result.md`, correlation id `c30c38ee-5428-4724-853a-05134b51b261`: balance
spoken after PIN, proving the identity-token auth path works with no `AOAI_KEY` fallback in code.
`disableLocalAuth: true` can now be reviewed as its own diff (`infra/modules/aoai.bicep`'s two-part
gate is satisfied). See "Next actions" below.

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
- Storage account `stazbankcallrecords`, table `callrecords`. Write-then-read proven live through the
  voice agent's managed identity.
- Container App `ca-azbank-core-banking`, internal-only ingress (deliberate, criterion 22 — also why
  Phase 5's B5 probe pool could not be gathered from outside the environment), `Healthy`, one replica.
- **Container App `ca-azbank-echo-p0`**, min-replicas=1 (**billing now**), running
  `docker.io/maofilho/azbank-echo-p0:p5i`, revision `--0000011`, `Healthy`, 100% traffic, 0 restarts —
  the routing/transfer-word fix, confirmed live 2026-09-12. Its system-assigned identity
  (`5e09fe34-8913-4aa2-80ac-618af308a88f`) holds `Reader` on the AOAI resource and `Storage Table Data
  Contributor` scoped to `stazbankcallrecords`.
- **Data-plane auth to AOAI is now the identity token** (`DefaultAzureCredential`, no key fallback in
  code), proven live 2026-09-17 (`docs/phase7/d2-live-call-result.md`). The `AOAI_KEY` env var is
  still present on the container app but unused by code — pending removal alongside the
  `disableLocalAuth: true` flip. Storage auth is managed identity only, unchanged.
- **Logs: query `workspace-rgazurebankingvoiceagenticai1D`** (`bf520f2c-e2bc-4488-8965-9317a7922c74`),
  never `...aiCS`, which has been stale since 2026-08-25. `...aixC` is an orphan. Three workspaces
  exist, not two.
- **Application Insights `appi-azure-banking-voice`** (issue #62), workspace-based on `...1D`,
  `provisioningState: Succeeded`, created 2026-09-14 (Marco, `infra/provision-app-insights.sh`).
- **`ca-azbank-echo-p0` is now running `p7c`**, image `docker.io/maofilho/azbank-echo-p0:p7c`,
  revision `--0000013`, Healthy/100% traffic — D2's identity-auth code plus both `agents/specs.py`
  fixes from `docs/phase7/d2-live-call-result.md`, all three live-verified 2026-09-17. Carries
  `APPLICATIONINSIGHTS_CONNECTION_STRING` (secretref) and `AZURE_MONITOR_AUTH=connection_string` (the
  named fallback, not identity — D10's IAM role is still an open `/research` question).
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
6. *(closed 2026-09-16: `infra/modules/container-apps-env.bicep` and `infra/modules/voice-agent.bicep`
   written — `9eb300f`, `2d839e3`. All 7 live Azure resources this project owns now have a Bicep
   module.)*
7. *(written 2026-09-18: `src/azbank_deploy/` (Typer CLI) — design settled via `/prototype`
   (`infra/PROTOTYPE-deploy-teardown-ordering.html`, throwaway branch), Marco confirmed
   auto-computed legal order is correct. 14 unit tests, `make lint`/`make test` clean. **Not yet
   run against Azure.**)*
8. *(written 2026-09-18: `.github/workflows/azure-banking-voice-agentic-ai-{deploy,teardown}.yml`,
   `workflow_dispatch` only (D3), OIDC via the 3 secrets from D4. `DOCKERHUB_PASSWORD` is a NEW
   required secret this needs that D4's setup didn't create — not yet added by Marco.)*
9. *(closed 2026-09-17: `/research` found the exact RBAC role — `Cognitive Services OpenAI User` —
   `docs/phase7/research-aoai-rbac-realtime.md`. `realtime/client.py` migrated to a
   `DefaultAzureCredential` bearer token (commit `fd1da9b`), source no longer references the static
   key at all. Both research findings verified live via a real call — `docs/phase7/d2-live-call-
   result.md`.)*
10. *(closed 2026-09-17: the research's "already granted" claim for the RBAC role was wrong — Bicep
    had it written, not applied, same as every other Phase 7 module. Live check
    (`az role assignment list`) found it genuinely absent, meaning the already-deployed `p7a` image
    — identity-auth-only, no key fallback — had **no working path to AOAI at all** until this was
    caught. Fixed by granting the role directly, scoped to the additive half of `aoai.bicep`'s own
    documented rule ("safe to apply any time"); confirmed readable back before the verification call.
    Resume-discipline lesson: a commit message's "already granted" is not live state — check the API.)*
11. *(closed 2026-09-17: `agents/specs.py`'s pre-PIN escalation wording, its own follow-on
    handoff-skipping regression, and both fixes — full account in `docs/phase7/d2-live-call-
    result.md`. Third live-verified fix to that file this week; a fourth would be worth pausing to
    build a scripted conversation replay before iterating on more real calls.)*
12. *(closed 2026-09-18: `/code-review` ran on `53f868b` (Standards + Spec axes) — 0 hard
    violations, one real finding fixed (`d7c6b14`, dead `location` param on
    `list_soft_deleted_cognitive_services_accounts`; `az cognitiveservices account list-deleted` has
    no location filter, confirmed via its own `-h`). Marco then ran `make deploy` live (no-op, every
    resource already matched) and `make teardown` live (all 7 teardown-eligible resources removed,
    soft-deleted AOAI purged, ACS + phone number untouched, Marco watching throughout, per
    exit-criteria's rule). **Live system is currently torn down — the phone line will not answer
    until redeployed.**)*
13. **Redeploy now** (same images, `p7c`/`p5`) to restore the live system and to be the real
    from-empty test of exit criterion 4 (the first `make deploy` above was a no-op resume, not a
    true bring-up). Then one smoke call to close criterion 4. `DOCKERHUB_PASSWORD` still needs
    adding as a GitHub secret before the `deploy`/`teardown` *workflows* (not the local CLI) can run
    (items 7/8).
14. **Phase 7 debt, accepted 2026-09-18 (Option A):** `make teardown` doesn't remove 3
    auto-created Log Analytics workspaces or 2 Application Insights alert artifacts — resources
    Container Apps/App Insights create as side effects, outside this CLI's 8-node graph. Checked
    live: `PerGB2018`, no active ingestion, 30-day retention within Azure's free window — $0 ongoing
    cost. Accepted as out of scope rather than extending the CLI today.

**Still not written, needs Marco:** the root `CONTEXT-MAP.md` that `docs/agents/domain.md` calls for.
It sits outside `PROJECT_ROOT` and needs approval by absolute path. `CONTEXT.md` (this project's own
glossary) is written and committed.
