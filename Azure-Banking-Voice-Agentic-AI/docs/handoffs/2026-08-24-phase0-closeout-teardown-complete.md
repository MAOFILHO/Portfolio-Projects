# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 0 closeout, 2026-08-24

**Canonical path**: `/Users/marco/K21/Real-world-worktrees/azure-banking/Azure-Banking-Voice-Agentic-AI`,
branch `azure-banking-work`. Verify with `git branch --show-current` / `git worktree list` before
doing anything — don't trust this line to have stayed current (`CLAUDE.md`'s own instruction).

## STOP CONDITIONS — restated verbatim from CLAUDE.md, per its own requirement

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.** No teardown
  path may include a number-release/delete call. Added 2026-08-20 (R-09, `docs/PLAN.md`): ACS's
  Canadian geographic-number inventory has been observed to lose entire localities within ~20 minutes
  — unlike every other resource in this project, an equivalent replacement may not be purchasable if
  this number is ever lost. Qualitatively different from the general "no billable resource without
  approval" rule above: this isn't about cost, it's about irreplaceability.
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling (below).
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

## Where things stand: Phase 0 is COMPLETE

`PROJECT_STATE.md` is the authoritative current-state snapshot — read it first. Full derivation for
everything below: `docs/phase0/findings.md`; the closeout commit itself, `07faf3b`.

- **R-04: IDLE** — 299 Azure Monitor `Replicas` datapoints, 0 scale-to-zero gaps.
- **R-08: PASSES — 79.2 demo runs/month**, computed at **$0.031/min**, deliberately the *pessimistic*
  end of `docs/PLAN.md`'s $0.0215–$0.031/min range, so the gate result holds unconditionally regardless
  of which end turns out to be closer to reality. Fixed monthly cost: **$6.72**.
- **Teardown succeeded**: Container App, Event Grid subscription, and Container Apps environment all
  independently confirmed deleted. The script's final "TEARDOWN INCOMPLETE" banner was a **false
  negative** — a timeout waiting on the slow environment delete, not an actual failure. **Fix this
  before `04-teardown-and-r08.sh` runs again** (it won't run again this phase, but the bug is real and
  unfixed in the script as committed).
- **Stage 6 (dedup + commit evidence files) never ran** — the script exited before reaching it (the
  false-negative above). R-09 was verified **manually afterward**, via the same `/phoneNumbers` GET
  the script itself uses: `+17059100383` confirmed still owned. Evidence files and everything else
  Stage 6 would have done were committed by hand instead — see `07faf3b`.
- All of the above, plus the R-09 script fixes (transport-failure vs. genuine-absence distinction) and
  the R-03 cold-start-ruled-out / Phase-1-entry-criterion write-up from earlier this session, are
  **already committed as `07faf3b`**. `git status` at session end: clean except `docs/PLAN.md` (below)
  and an untracked `.serena/` directory (unrelated tooling artifact, not part of this project).

### Cost Management: two failed queries — read this before trusting any dollar figure

Cost Management queries (the `az rest` calls against the Cost Management Query REST API) **failed in
both Stage 1 and Stage 2** of the teardown run. Stage 2's failure specifically means **`COSTS.md` has
no measured dollar figure from this run** — its numbers are *modeled*: Canada Central Retail Prices API
rates applied to measured usage quantities (Replicas continuity, RxBytes/TxBytes), not dollars observed
in actual billing. **Do not describe `COSTS.md`'s Container Apps figures as "measured in dollars"** —
say "modeled from measured usage + published rates" instead.

The **variable $/min figure (the $0.031 R-08 used)** carries the same caveat one level further back: it
comes from `docs/PLAN.md`'s own estimate, which is itself US-rate-suspect (the same US-East-vs-Canada-
Central mismatch settled for the *fixed* Container Apps figures on 2026-08-22 — `docs/phase0/
findings.md`, "US-East-vs-Canada-Central") and has never been independently verified against Canada
Central rates for the *variable* per-minute meters (PSTN, ACS streaming, model tokens). R-08 used the
pessimistic end specifically to route around this uncertainty, not to resolve it — the underlying
number is still unverified for this region.

### Correction to the previous handoff

`docs/handoffs/2026-08-22-phase0-r04-r08-answered-pending-monday-teardown.md` stated that script 04
commits the evidence files as part of its own run (Stage 6). **That was wrong** — the script contains
no `git add`/`git commit` anywhere; committing evidence files has always been a manual step. Recorded
here so the error doesn't propagate further; not worth editing the 08-22 doc itself (historical, not
current-state).

### `docs/PLAN.md` — one uncommitted section, deliberately held back

`docs/PLAN.md` has an uncommitted 48-line addition from 2026-08-21: a new "Observability tooling"
section (Phase 6) pinning the **Azure Monitor OpenTelemetry Distro → Application Insights** as the
recommended tool over LangFuse (residency conflict — LangFuse Cloud has no Canada region; self-host
would be an unbudgeted new resource). **Left out of the teardown commit deliberately, still pending
Marco's explicit confirmation** — same as any other architecture decision in this file. Do not fold it
into a future commit without that confirmation, and do not treat its Phase 6 recommendation as settled
— see the Phase 1 priority section below for why it specifically needs revisiting, not just rubber-
stamping.

## Phase 1 priority: one gap blocks four things

The Log Analytics zero-rows gap (`PROJECT_STATE.md` open item 1, `docs/phase0/findings.md` "Log
delivery — still zero rows...") is no longer just an observability nuisance. It now blocks:

1. **DTMF disambiguation** (`PROJECT_STATE.md` open item 10 / `docs/phase0/findings.md` "R-03
   residual — promoted to a Phase 1 entry criterion") — distinguishing "DTMF not sent" from "sent but
   unrecognized upstream by ACS" needs real ACS-side call diagnostics, which this gap blocks entirely.
2. **Any real log path** for Phase 1 onward — a production voice agent cannot run with no durable
   logging (open item 1's own closing line).
3. **The Phase 6 observability decision** — the uncommitted PLAN.md section above recommends
   Application Insights on **the same underlying pipeline** (Log Analytics ingestion) that currently
   returns zero rows for two independently-configured delivery paths. **That recommendation must be
   conditioned on this gap closing, not asserted over it** — confirming it as-is without first
   resolving why the existing pipeline is silent would be recommending a fix built on the same broken
   foundation.
4. **Possibly the Cost Management failures** (Stage 1 and Stage 2, above) — a second broken Azure
   telemetry *read* path in the same subscription. Might share a root cause with the Log Analytics gap
   (e.g. a subscription-level telemetry/RBAC issue), might not. Not investigated; flagged as a
   possibility worth keeping in view while investigating #1–3, not a confirmed link.

### Check this first: the two-workspace hypothesis (UNTESTED)

Two Log Analytics workspaces exist in the resource group:
`workspace-rgazurebankingvoiceagenticaiCS` and `workspace-rgazurebankingvoiceagenticaixC`
(`docs/phase0/findings.md` line ~1221, `PROJECT_STATE.md` line 42 — the `...aiCS` one is documented as
"the real one, linked"; `...aixC` as "an orphan, left in place"). **Untested hypothesis**: the
diagnostic setting may be configured to deliver to one workspace while every query this project has run
so far queried the other — which would fully explain why **two separately, correctly-configured**
delivery paths (native `appLogsConfiguration` and an explicit `az monitor diagnostic-settings`
resource) both came back empty. This is the cheapest possible explanation and hasn't been ruled out.
**Check it before any deeper platform-level investigation.**

**Do not delete either workspace** — even the one currently believed orphaned. If the hypothesis above
is right, `...aixC` may turn out to be the one actually receiving data.

### Also for Phase 1: evidence file size

`containerapp-logs-snapshot-2026-08-21.jsonl` went into git at **51,948 lines** (~6.4 MB across the
`docs/phase0/evidence/` directory as a whole). Decide deliberately whether raw `launchd` `--tail 300`
snapshots belong in the repo at that volume going forward, or whether the committed artifact for future
phases should be a reduced/summarized form instead (e.g. dedup'd + trimmed to the windows that actually
matter, rather than every 15-minute pull verbatim). Not decided this session — flagging so it's a
deliberate Phase 1 choice, not a repeat of the same pattern by default.

## Suggested skills for the next session

- **`/research`** — first action of the next session, for the two-workspace hypothesis: check the
  diagnostic setting's actual target workspace ID against which workspace ID recent queries used. This
  is a factual/API-shape question (this project's standing rule: verify, don't assume from memory), not
  a design question — `/research`, not `/prototype`.
- **`/wizard`** — once the workspace question is settled, if fixing the delivery path needs a live
  Azure Console/CLI decision that Marco must make by hand.
- **`/code-review`** — before Phase 1's exit-criteria gate, once whatever fixes the Log Analytics gap
  lands; also owed to `04-teardown-and-r08.sh`'s false-negative teardown-check bug before that script
  is ever run again (not yet reviewed formally).

Marco invokes skills himself, per this project's `CLAUDE.md` — the above is informational for the next
session, not a queue of actions to run unprompted.

## Redactions

None needed — no API keys, tokens, or credentials appear anywhere in this session's changes or in this
document. The phone number (`+17059100383`) and resource names are project infrastructure identifiers,
not personal data.
