# FNOL Phase 11 reviewer briefing — 2026-08-16 (closing entry)

Project: `/Users/marco/K21/Real-world/AWS-Insurance-FNOL-Voice-Agentic-AI` (monorepo root:
`/Users/marco/K21/Real-world`, do not write outside the project path without absolute-path approval —
`CLAUDE.md` "Scope rule").

This file is a map, not a source of truth. Everything it points at can drift; this file itself will not be
updated again — re-read the pointed-to files, don't trust this doc's prose over them. Supersedes
`docs/handoffs/2026-08-16-phase11-midflight.md` for current state, not for its own prior content — that file
is a snapshot of an earlier point the same day and is left as-is, per this project's "supersede, never edit"
convention for artifacts like this.

## Read first, in this order

1. `CLAUDE.md` — stop conditions (top of file), cost gate, PROJECT_ROOT scope rule. Restate the four STOP
   CONDITIONS verbatim at the top of your first response and after every `/compact`, per its own instruction.
2. **This section's own top item — `D121`/`OI39`.** Read it before anything else in this file.
3. `PROJECT_STATE.md` line 13 (`**Last updated:**`) — the single most current narrative line in the project.
4. `PROJECT_STATE.md`'s Phase 11 criteria table (search `## Phase 11 exit criteria` or grep `| 8a |`) — the
   authoritative criteria table; nothing below duplicates its text, only its shape.
5. `docs/REVIEW-CRITERIA.md` §8 — extended this session with `D121` as a worked example; read the extension,
   not just the original rule.

## Top open item — read this first

### `D121` / `OI39` — `UpdateContactInfo` cannot be completed by voice for `field=email` or `field=phone`

**Severity, Marco's own framing, verbatim in substance: higher than anything else currently open in this
ledger.** Two of three field values on one of the six in-scope intents are structurally dead by voice — not
degraded, not occasionally wrong, **uncompletable** — and this has been true silently since the guardrail's
`EMAIL`/`PHONE` PII entities were configured, well before this session found it.

**Mechanism** (`docs/RESULTS.md` §76, live-confirmed, not inferred): `update_contact_info_node`'s own
confirmation readback (`agents/nodes/update_contact_info.py:54,69`) speaks the caller's new value verbatim —
`f"That's {new_value} -- is that right?"`. For `field=email`/`field=phone`, that string contains a real
email or phone number, which the OUTPUT guardrail's `sensitive_information_policy_config` (`infra/terraform/
stacks/guardrails/main.tf:236-237`) masks: `EMAIL`/`PHONE` are both configured `ANONYMIZE`. The caller
receives `"That's {EMAIL} -- is that right?"` verbatim — Bedrock's own placeholder token, not their data.
Nothing they can truthfully say confirms a literal `{EMAIL}`; the node's one allowed retry
(`_CONFIRM_CEILING = 1`) re-asks the identical masked string, then escalates to a human. Only
`field=mailing_address` (not a configured PII entity type) works.

**Confirmed live**, real `guardrail_usage` log line, same `requestId`: `masked=true`, `blocked=false`,
`sensitiveInformationPolicyUnits=1`. Full transcript and the live-check script's own reasoning (why
pre-filling `confirm=Yes` would have missed the vulnerable line) are in `RESULTS.md` §76.

**Status: FIX NOW bucket, deliberately NOT scoped or fixed this session.** Marco's instruction verbatim:
"it needs a design decision, a guardrail version bump, a redeploy, and a `C1` cycle — that is a fresh
session's work, not the end of a long one." `PROJECT_STATE.md`'s `OI39` row carries this as both FIX NOW
(not accepted risk) and NOT DONE (nothing touched this entry) at once, deliberately.

**Candidate fix directions, not evaluated, not chosen** (`OI39`'s own row has the full text):

1. Remove `EMAIL`/`PHONE` from the OUTPUT PII entity list — mirrors the `D16` v2->v3 reasoning exactly,
   the same tradeoff Marco already made once for the identifier regexes.
2. Keep the entities; have `update_contact_info_node` read back a de-guardrailed confirmation (e.g. "your
   new email", not the value itself, or a spelled/partial form).

Either direction needs a guardrail version bump + `stacks/main` redeploy + `C1` re-verification — there is
no in-place fix.

**The corrected lesson, worth carrying into the fix design, not just the ledger**: the `D16` v2->v3 fix
enumerated every call site of the custom-regex mechanism it removed, correctly, and closed all of them — it
never checked whether the *outcome* it was fixing (a caller's own data masked back to them) was reachable
through a *different* mechanism. It was. `REVIEW-CRITERIA.md` §8 was extended this session with this as a
worked example: **enumerate mechanisms capable of producing the same outcome, not only call sites of the
same mechanism.** Whichever direction is chosen for `D121`, re-check the guardrail's full config (content
filters, word filters, topic denials — not just the PII entity list) against the same question before
calling it closed.

## Phase 11 — eight criteria, current state

Stage letters, per `PROJECT_STATE.md`'s own mapping: **0** preflight, **A** criteria 1+2, **B** criterion 3,
**C** criterion 4, **D** criterion 8(a/b), **E** criterion 5, **F** criterion 6.

**7 of 8 closed or satisfied. Criterion 5 is the only remaining gap.**

| # | What | State |
|---|---|---|
| 1 | Budget alarm, firing-proof required | **CLOSED.** Full chain: `$0.25` threshold applied → `NotificationState: ALARM` confirmed live → SNS published → breach email received and confirmed by Marco (`ACTUAL $0.71`, 6:45 PM local). First alarm in this project demonstrated to actually fire, not merely exist as correct config. Temporary test notification's removal plan is ready (`/tmp/oi1_removal.tfplan`, `0 add/1 change/0 destroy`, $0) — **awaiting Marco's apply**, `OI1`'s row |
| 2 | Cost dashboard, checked against a known real number | **CLOSED.** Independent live CE read ($4.3355138372) vs. the dashboard's one datapoint ($3.7828941608) — correctly directioned, mechanism confirmed correct. **Named gap, not folded in**: `aws_scheduler_schedule.ce_pull_weekly` has never fired on its own schedule (created 2026-08-15T18:40:12, next ~2026-08-22); the one existing datapoint is a pre-schedule manual test invocation |
| 3 | Operational CloudWatch dashboard, split B1/B2 | **B1 fully closed**, including the panel-liveness proof (claim (b)) — a real OUTPUT intervention now on record, dashboard-widget-visible. That same check surfaced `D121` (above). **B2 (turn-latency) still not built** — deferred, named home: **Phase 12 entry condition** |
| 4 | PII redaction at the CloudWatch Logs sink | **CLOSED** (both runs, `OI2`) |
| 5 | Ops runbooks | **OPEN — deliberately not written this session.** Marco's explicit instruction: two runbooks needed (`C14` warm-path exceedance, guardrail false-positive spike), canonical `C14` phrasing verbatim (below), guardrail runbook to use `D89`'s real live false-positive as its worked example. Not started |
| 6 | Branch protection required-status-check | **CLOSED**, both halves, independently verified via `gh run view 31971816508` / `gh pr view 4`, not taken on any prior record's word alone |
| 7 | Record hygiene | **CLOSED**, Stage 0 |
| 8a | `C14`-adjacent regression signal (Lambda p95 over eval-harness calls) | **CLOSED.** p95 = 1,651.06ms, 121 real eval-harness/probe invocations, current deployed build only. **Explicitly not a `C14` measurement** — no Lex/Polly leg in this number, no comparison to the 1,800ms voice-turn budget attempted |
| 8b | `C1` scheduled-eval tripwire | **Satisfied**, not by a synthetic injection but by `D97`'s real outage-and-recovery cycle (guardrail-version coupling defect, window `18:21:13Z`→`21:07:08Z`) — a genuine before/during/after exercise of the signal |

## `C1` — status, three tiers (do not compress this to "C1 verified")

Unchanged from the midflight handoff's own careful accounting — quoted here again because `REVIEW-CRITERIA.md`
§9 exists specifically because this compressed once already. **Tier 1 (three canonical scope qualifiers:
warm-path only; scoped to today's topology, not just build identity; cold-start is a 1-of-19 existence proof,
not a measurement), Tier 2 (build identity, tracked separately), Tier 3 (other live caveats — k=1 sampling;
immune only to mechanisms actually checked)** — full text, quoted from source, is
`docs/handoffs/2026-08-16-phase11-midflight.md`'s own "`C1` — status, three tiers" section. Re-read it there,
don't restate it from memory here.

**Current build, this session's own live-verified value**: `CodeSha256 /4FFnR9Q7cbkbuWmCR1Yth2baW/cxp7F+r/fPP+JCOo=`,
`1.000 (26/26)`, reproducible from `main` as of commit `8f140bc`. This is a dated claim, not a permanent
property — any uncommitted `src/` edit breaks the reproducibility half again silently.

## `C14` — canonical phrasing, verbatim (do not use "19ms" shorthand anywhere)

> "warm-path p95 1,819ms, measured on a sample excluding cold starts; true p95 over real traffic mix is
> ≥1,819ms, distance to the 1,800ms target unmeasured"

Source: `docs/RESULTS.md` §12.10. This is still the live figure — criterion 8a (closed this session) measured
Lambda-invocation p95, a **different, non-comparable number** (turn-processing only, no Lex/Polly leg); it
does not update or supersede this one. The runbook for criterion 5 must use this exact phrasing.

## Open items — one line each, full text at the cited row

All rows live in `PROJECT_STATE.md`'s "Open items — current phase" table unless noted. Read the row before
acting on any of these; this table exists to help you find the row, not to replace it.

| Item | One-line state |
|---|---|
| **`OI39`/`D121`** | **Top item — see above.** `UpdateContactInfo` dead by voice for `field=email`/`field=phone`. FIX NOW, unscoped |
| `OI1` | Removal plan for the temporary $0.25 test notification is ready (`/tmp/oi1_removal.tfplan`), awaiting Marco's apply |
| `OI3` | `codehook_deps_layer`'s `etag` phantom diff — confirmed real (harmless re-upload every plan/apply), fix is a Terraform-mechanics swap to `source_hash`, not applied |
| `OI5`/`D88` | Re-closed. Narrow finding (claim-number masking) stays not-a-defect; the "no ordinary path exists" scope claim was corrected and the correction is what led to `D121` |
| `OI6`/`D89` | INPUT guardrail false-blocks the word "file" in an ordinary `FileAutoClaim` confirmation. Open, unscoped |
| `OI7`/`D90` part 1 | Zero-context turn classification misroutes at least one event live. Option 1 shipped and **confirmed insufficient** (live repro: context reaches the classifier, misroute persists). Open, unscoped, explicitly not pre-scoped for the next build |
| `OI8`/`D91` | Staged-but-uncommitted work can silently ride into an unrelated commit. **Accepted-risk convention**, not a pending control — no verified session-start hook point exists |
| `OI9`/`D92` | Eval harness overwrites its own baseline JSON with no existing-file check. Assessed convertible, not built — `D98`'s lint was the cheaper case, built first |
| `OI15`/`D98` | `D89`/`D90` both expose FileAutoClaim/UpdateContactInfo confirmation turns identically — recorded, tracks with those two's own status, no separate fix |
| `OI17`/`D99` | `non_auto_insurance_products` topic under-triggers on its own canonical life-insurance example. Probe run, inconclusive — a life-insurance sentence is inconsistently classified at the individual verb/object level, root cause not isolated |
| `OI18`/`D100` | Event 13 (`RentalTowingEntitlement` misroute) has been standing in for a risk it doesn't represent — the real, unmeasured risk is a continuation-turn exposure deep in a real multi-turn conversation. Triage question: MEASURE (one live checkpointer probe) or ACCEPT unmeasured — not decided |
| `OI19`/`D101` | Cross-session coordination (`SendMessage`/`ListAgents`) happened and worked this arc but exists in no record — needs a bucket, not resolved |
| `OI38`/`D120` | `git checkout <ref> -- <path>` run against an assumption, not a check, silently overwrote uncommitted work twice in one session. Recovery worked both times by luck (diffs happened to be on hand), not process. Guard proposed (pre-checkout diff check, or stash-wrap), not built |
| `CF8` | Standing `make verify-*` gate exercising every ordinary intent's real, deployed, slot-filled happy path. Built, 10/13 green (3 known failures: `D88`-shaped assertions since fixed, `D89`, `D90` part 1). Proposed as a **Phase 12 entry condition** |

## `REVIEW-CRITERIA.md` — standing rules touched this arc

- **§6** — sweep recall is bounded by the search terms, not the corpus.
- **§7** — activity signals are not effect signals (a log line firing is not the same claim as the effect
  happening).
- **§8** — a defect fixed at one call site is not fixed until every site of that class is enumerated.
  **Extended this session** with `D121`/`D16` as a worked example: enumerate every *mechanism* capable of
  producing the same outcome, not only every other call site of the same mechanism. Read the extension in
  full — it's short, and it's the lens `D121`'s eventual fix should be designed through.
- **§9** — a summary carrying a scoped claim must cite its source line and re-verify scope at write time, not
  from memory. This file follows that rule for `C1`'s tiers above (pointer to source, not restated from
  memory) and for `C14`'s phrasing (quoted verbatim, sourced).

## Immediate next steps (not decided here, listed for orientation only)

- `D121`/`OI39` — the design decision named above, then guardrail version bump, redeploy, `C1` cycle. Top
  priority by Marco's own stated severity ranking.
- Criterion 5 — write the two runbooks (`C14` warm-path exceedance, guardrail false-positive spike using
  `D89`'s real live false-positive as the worked example) once Stage A–D's actual mechanisms are stable
  enough that a runbook written against them won't immediately drift — `D121`'s fix will touch the guardrail,
  so writing the guardrail runbook before that fix lands risks describing a config that's about to change.
- `OI1` — apply the removal plan already generated (`/tmp/oi1_removal.tfplan`).
- `D90` part 1, `D89`, `D99`, `D100`'s MEASURE/ACCEPT question — all open, unscoped, Marco's to take up.

## Suggested skills for the next session

- **`diagnosing-bugs`** — if the next session designs `D121`'s fix (a genuine design decision with a live
  repro already in hand, `RESULTS.md` §76) or picks up `D90` part 1 (confirmed-insufficient fix, needs a
  fresh hypothesis).
- No other skill is obviously load-bearing from here — criterion 5's runbooks are direct writing against
  already-built mechanisms (once `D121` settles), not diagnosis or design work.
