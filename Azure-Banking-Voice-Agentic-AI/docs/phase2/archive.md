# Phase 2 archive — realtime session, agent core, auth gate, test harness

Phase 2's closed record, moved out of `PROJECT_STATE.md` on 2026-09-09 under decision 18
(`CLAUDE.md`): the state file holds current state, and everything here is past-tense. Nothing in
this file is a live item.

Spec was issue **#16**, tickets **#17-24**.

## Closed and signed off

**Signed off by Marco 2026-09-08 ("Phase 2 approved").** All three exit criteria met:

- fakes-only CI with the gate provably deny-all,
- `T-B3-SUCCESSOR-BOOT` exists,
- B5's provisional figure landed at **p95=932ms, N=106** — 31 real calls plus 75
  `scripts/b5_probe.py` samples, both pools stated.

At close: **98 tests green, ~0.5s, no cloud dependency** (3 skipped: the successor rehearsal, by
design), `make lint` clean, and Phase 1 still working as the demonstrable deliverable.

**Operating-mode verdict: IDLE, reconfirmed 2026-09-08** against R-04's original method, over the
window covering all 8 real B5 calls plus the probe batch — settles to idle within one 15-minute
bucket every time, same ~189KB/118KB baseline as Phase 0 and Phase 1.

Full narrative — what was built per ticket, the two `/code-review` rounds, the B2 leak fix, and the
review findings deliberately not actioned:
`docs/handoffs/2026-09-08-phase2-signoff-phase3-entry.md`. Per-call B5 detail:
`docs/phase2/evidence/b5-call-log.md`.

## What Phase 2 changed on the live deployment

These three actions changed running Azure state during Phase 2. The **end state** they left behind
is current, and lives in `PROJECT_STATE.md` under "Live Azure state"; the history is here.

**System-assigned managed identity added to `ca-azbank-echo-p0`, 2026-09-07** (Marco confirmed the
plan first): principal `5e09fe34-8913-4aa2-80ac-618af308a88f`, granted `Reader` — scoped only to the
`aoai-azure-banking-voice-cc` resource, nothing broader — which is what `boot.read_live_model()`'s
one ARM `GET .../deployments/{name}` call needs. Free, no new billable resource.

**Phase 2 image deployed 2026-09-07** (Marco built and pushed on his laptop, confirmed
`linux/amd64`; Claude confirmed the `az containerapp update` command before running it):
`ca-azbank-echo-p0` moved to `docker.io/maofilho/azbank-echo-p0:p2`, plus the three env vars
`boot.read_live_model()` needs (`AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`,
`AOAI_ACCOUNT_NAME` — added via `--set-env-vars`, additive, with the 5 pre-existing vars confirmed
untouched). New revision `ca-azbank-echo-p0--0000001`, `Healthy`/`RunningAtMaxScale`.

**B3's boot guard ran live for the first time and passed** — confirmed from actual container logs,
not inferred from health state: the managed identity acquired a token,
`GET .../deployments/gpt-realtime-mini` returned `200 OK`, and the app logged
`B3: deployed model ('gpt-realtime-mini', '2025-10-06') matches the active pin.` before
`Application startup complete.` Single-revision mode, so this replaced the running Phase 1
container — flagged to Marco as a real risk (no automatic fallback on a bad boot) before running.

**Redeployed to `:p3` 2026-09-08** (same process, Marco confirmed the command first): adds the B5
latency-anchor logging from `42e02c5` that `:p2` did not have. Revision `--0000002`, `Healthy`, 100%
traffic, B3 verified live again from real logs.

## The third Log Analytics workspace, found 2026-09-08

Two workspaces were on record: `...aiCS` (`2a41795f-...`, Phase 0's documented "real/linked" one)
and `...aixC` (`e42c142b-...`, documented orphan). The container app's diagnostic setting
(`azbank-p0-console-logs`) actually targets a **third, undocumented one**:
`workspace-rgazurebankingvoiceagenticai1D` (`bf520f2c-e2bc-4488-8965-9317a7922c74`). `...aiCS` had
been stale since 2026-08-25 without anyone noticing; `...ai1D` is the live one, confirmed by
querying it and finding real rows from that day's calls.

The operational consequence — query `...ai1D`, never `...aiCS` — is current state and stays in
`PROJECT_STATE.md`.
