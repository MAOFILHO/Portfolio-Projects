# Phase 8 — Post-call analytics, evals & docs: design and exit criteria

> **APPROVED. Phase 8 is open.**
>
> This design came from a `/grill-with-docs` round with Marco (2026-09-18) — 13 questions across two
> rounds, all answered, tracked in issue #66. Contrast with Phase 7, whose doc started as a first-pass
> draft with no grilling round.
>
> | approval | state |
> |---|---|
> | The 13 design questions below (Q1-Q13) | **Given 2026-09-18**, question by question |
> | The doc as a whole, as shared understanding | **Confirmed 2026-09-18**, Marco |
> | `APPROVED: Phase 8` for billable resources | **Given 2026-09-18**, Marco (typed verbatim) |
> | The Azure AI Language resource specifically | **Facts resolved 2026-09-18** (`docs/phase8/research-language-pii-quota.md`) — no free tier exists for Conversation PII detection; Standard-tier only, ~$0.07-$1.34/mo bounded at this project's volume (`COSTS.md`). **`APPROVED: Phase 8 Language resource` given 2026-09-18, Marco (typed verbatim), at the corrected non-free price.** |

---

## Entry conditions

| condition | state |
|---|---|
| Phase 7's exit criteria written | Satisfied — `docs/phase7/exit-criteria.md` |
| Phase 7's exit criteria met | Satisfied — all 9 criteria, 2 with a stated limit, `docs/phase7/exit-check.md`, 2026-09-18 |
| Marco's sign-off on Phase 7 | Satisfied — `docs/phase7/exit-check.md` records the closure sign-off |
| Marco's approval to begin Phase 8 | **Given 2026-09-18** |

---

## What Phase 8 is, in one paragraph

Once a call ends today, nothing durable remains of it beyond the Phase 6 trace — no transcript a
reviewer can read afterward, no evidence the agent's behaviour holds up across repeated runs, and no
top-level docs telling a reader what this project is or how it fared. Phase 8 closes all three: a
per-call record (redacted transcript to Blob, a summary/intent/**call outcome** row to Table Storage)
written asynchronously after hangup; an `evals/` suite (20 scenarios, LLM-judged, weekly + on-demand)
proving the agent behaves the same way across repeated runs, not just once on a good day; and the
docs — `RESULTS.md`, an architecture diagram, an updated `README.md` — that let this repo read as a
matched pair with `AWS-Insurance-FNOL-Voice-Agentic-AI`.

---

## Current state — what already exists vs. what Phase 8 adds

| item | today | gap |
|---|---|---|
| Post-call transcript/metadata pipeline | Does not exist | this phase's main deliverable |
| **Call outcome** field (`end_reason`) | Exists in code per `PROJECT_STATE.md` open item 19, three values in use | needs the full 5-value enum (D10) and a durable home in Table Storage |
| PII redaction for transcript text | Only the span **Redaction filter** (attribute-name allowlist) exists — never applied to conversational text | new mechanism (D2/D8): Azure AI Language Conversation PII detection |
| Second, non-realtime AOAI deployment | Does not exist — only the realtime pin (`gpt-realtime-mini`) is deployed | this phase provisions it (D11/D12), and B3 needs to extend to cover it |
| `evals/` | Directory does not exist (`docs/PLAN.md` names it as a target, not yet built) | this phase's main deliverable — 20 scenarios, LLM-judge, ≥95% over 20 runs |
| `redteam/` | 18 of the "20-30" target (Phase 4, issue #41) | none — accepted as final (D5) |
| `RESULTS.md` | Does not exist | this phase's main deliverable, own size ceiling (D6) |
| Architecture diagram | Does not exist | this phase's main deliverable |
| `README.md` | Exists (39.7 KB), phase badge reads "Phase 6 of 8" | needs updating to reflect Phase 8 |
| `COSTS.md` | No line for a Language resource or a second AOAI deployment | this phase adds both once priced |
| ADRs | 5 exist (`docs/adr/`) | 2 more this phase (D13): B3's extension, redact-before-first-write |

---

## Settled decisions — given 2026-09-18

**D1 (Q1) — Call outcome is its own glossary term, distinct from tool-call outcomes.** `CONTEXT.md`
updated same session: **Call outcome** (`end_reason` in code) covers how a call ended; the renamed
**Tool-call outcomes** section stays reserved for the four per-tool-call failure types (Unknown
account, Declined, Unavailable, Malformed). No code rename — `end_reason` stays as spelled.

**D2 (Q2, Q8) — PII redaction uses Azure AI Language's Conversation PII detection, deployed in Canada
Central.** Chosen over a rule-based/regex redactor because transcript text needs real PII detection
(names, addresses), not just pattern matching, and over generic-text PII detection because Conversation
PII detection is purpose-built for multi-turn dialogue with speaker turns — closer to what a call
transcript actually is. Canada Central is non-negotiable per `ADR-001`. **A new billable resource —
provisioning is gated on the `/research` pass below, not on `APPROVED: Phase 8` alone.**

**D3 (Q3) — the post-call pipeline runs in-process, inside the existing `ca-azbank-echo-p0` container
app.** No new compute resource. Triggered at call end (WebSocket close), not by a separate scheduled
job reading the call-record store.

**D4 (Q4) — redaction happens in-memory before the first write to Blob.** No raw-transcript write
ever exists at any point, in any storage. This is what keeps the transcript pipeline from becoming a
new B2 surface — B2's guarantee (no PIN, no phone number, in any channel) holds because the
unredacted state that could violate it is never persisted, not because a scan catches it after the
fact. Proven by a dedicated test (D-test-1 below), same shape as B2's existing artifact scan.

**D5 (Q5) — the redteam corpus (`redteam/`, 18 ideas) is accepted as final.** Not topped up to the
"20-30" target from Phase 4 — an honest count, consistent with Phase 5's precedent of reporting rather
than padding.

**D6 (Q6) — "matched pair with FNOL" means the same top-level file set, not the same size.**
`RESULTS.md`, `README.md`, and an architecture diagram get written. `RESULTS.md` gets its own line-
count ceiling, the same discipline `PROJECT_STATE.md` already carries (decision 18) — FNOL's own
`RESULTS.md` grew to 941 KB, the exact pattern that ceiling exists to avoid. Ceiling number is set
when the doc is drafted, sized to what a reviewer would actually read in one sitting.

**D7 (Q7) — tracking issue opened.** [#66](https://github.com/MAOFILHO/Portfolio-Projects/issues/66),
`needs-triage` (the label didn't exist in this repo yet — created it to match
`docs/agents/triage-labels.md`'s documented vocabulary).

**D8 — same as D2.** (Q8 confirmed the Conversation-specific, Canada-Central-only shape of D2; folded
in rather than kept as a separate decision.)

**D9 — same as D11/D12 below.** (Q9 established *that* summary/intent generation is a new async call;
D11 and D12 settle *which* model and *when* it runs, which subsumes Q9's placement decision.)

**D10 (Q10) — Call outcome's fixed enum: five values.** `authenticated_served`, `escalated`,
`caller_hangup`, `closed_path`, `error`. Matches the existing **Closed path** and **Escalation**
glossary terms exactly — no category exists that the glossary doesn't already name. A call that
doesn't cleanly fit one of the first four values is `error`, never left unclassified.

**D11 (Q11) — summary/intent generation runs on a second, non-realtime Azure OpenAI deployment**
(a `gpt-4o-mini`-class text model, exact deployment name TBD at build time), not the realtime pin.
Runs fully async, after the WebSocket closes — never in the live-call path, so it cannot affect B4
(cost ceiling) or B5 (turn latency). **B3 (Model Pinning) needs to extend to cover this second
deployment** — B3's current wording in `CLAUDE.md` scopes the allowlist to "a realtime deployment"
only. The extension itself (exact wording, allowlist mechanism) is written when this deployment is
actually built, same pattern Phase 6 used for B2's widening (issue #65) — recorded as a committed
decision here, not yet as a `CLAUDE.md` edit.

**D12 (Q12) — the L3 eval judge reuses D11's text model.** One new model pin to review at phase gates
instead of two. Consistent with `docs/PLAN.md`'s existing $6/mo eval budget, which already assumes a
cheap judge model rather than the realtime one.

**D13 (Q13) — two ADRs this phase**, written once D11's model choice is final (it now is):
1. The second, non-realtime model pin and how B3 extends to cover it.
2. Redact-before-first-write as the design that keeps B2 from needing a new channel.

Both meet the three-part bar for an ADR: hard to reverse, surprising without context, and the result
of a genuine trade-off.

**D14 (added 2026-09-19, Marco) — the stored transcript is agent-side only.** Caller speech is never
transcribed: `session.py` leaves `input_audio_transcription` off, and turning it on needs a named
transcription deployment (a new billable resource and a third B3 pin). The Blob record holds what the
agent said, not a two-sided conversation. This corrects `docs/PLAN.md`'s "transcript already in hand,
no STT needed", which held for agent speech only. Open consequence: D2 chose Conversation PII
detection for its speaker-turn design, and there is now one speaker. Whether it is still the right
feature (plain Text PII detection has a free allotment, per `research-language-pii-quota.md`) is
undecided and must be settled before the pipeline calls the Language resource. **Settled same day
(D18 below): keep Conversation PII detection.**

**D15 (2026-09-19, Marco) — Phase 8 closes with a stated limit on criteria 6 and 7.** Criteria 1-5 and
8-10 are built and proved; the eval runner (needs TTS caller audio, no TTS resource is provisioned) and
the redteam live run are recorded as debt with exactly what is missing, the precedent Phase 7 set for
its 2 limited criteria. Marco's closure sign-off is still required.

**D16 (2026-09-19, Marco) — "≥95% over 20 runs" means 20 scenario runs, once each.** Not 20 full-suite
runs (~800 call-minutes, roughly $7-14 by `docs/PLAN.md`'s table, over the $6/mo ceiling).

**D17 (2026-09-19, Marco) — Call outcome mapping, literal D10.** Code's 8 `end_reason` values resolve
to the 5-value enum: `closed`→`closed_path`, `escalated`→`escalated`, `caller_hangup`→`caller_hangup`,
`model_ended` while authenticated→`authenticated_served`. Everything else (`cost_cap`, `timeout`,
`attempts_exhausted`, `model_ended` while anonymous, `error`, any unknown value)→`error`. The raw
`end_reason` is stored beside it, so nothing is lost. `docs/phase8/exit-criteria.md`'s gap table
originally said 3 values were in use; the code has 8.

**D18 (2026-09-19, Marco) — keep Conversation PII detection (D2 stands).** Already provisioned, priced
($0.07-$1.34/mo) and approved; one speaker does not invalidate it.

---

## `/research` — resolved 2026-09-18

Full findings: `docs/phase8/research-language-pii-quota.md`, both primary-sourced from Microsoft's own
pricing and Learn pages.

- **No free tier for Conversation PII detection.** Only plain Text PII detection gets a free
  allotment; Conversation PII redaction is Standard-tier only, billed from the first record —
  **$1.00/1,000 text records** for the first 0.5M records/month in Canada Central, $0.75/1,000 after.
  This corrects `docs/PLAN.md`'s original one-paragraph sketch, which assumed "Language free tier."
- **Canada Central confirmed** — two independent primary sources, neither inferred from the base
  Language resource's general availability (see the research doc §2).
- **Cost bound at this project's call volume** (~45–67 demo calls/month, `COSTS.md`): the exact
  billing unit per call is unconfirmed by any source found (per-turn vs. per-conversation is an open
  question the research doc flags), so this bounds rather than pins a figure. Worst case — one record
  per turn, capped at B4's 20 turns/call, 67 calls: **1,340 records/mo ≈ $1.34/mo.** Best case — one
  record per call: **67 records/mo ≈ $0.07/mo.** Either bound is small against the $25/mo ceiling and
  the ~$10.40/mo of headroom above the $14.60/mo fixed cost (`COSTS.md`).
- **Still needs Marco's explicit go-ahead at this corrected, non-free price** before D2 provisions —
  the blanket `APPROVED: Phase 8` was given on the "free tier" premise; that premise is now known
  false, so it doesn't stand in for a decision Marco hasn't actually made yet.

---

## Exit criteria (in force)

In force since the whole doc was approved 2026-09-18. **Criteria 6 and 7 close with a stated limit, not a
result (D15):** `docs/phase8/eval-redteam-limits.md`. Status against each: `docs/phase8/exit-check.md`.

| # | criterion | how it is proved |
|---|---|---|
| 1 | A redacted agent-side transcript (D14) reaches Blob for every completed call, with no raw-transcript write ever occurring first | D4's dedicated test — assert no unredacted transcript content appears in any Blob write, across a fake-call run |
| 2 | A summary/intent/**call outcome** record reaches Table Storage for every completed call | Live call + a queried row, same "200 OK proves creation, not delivery" discipline as Phase 6/7 |
| 3 | **Call outcome** uses exactly the 5-value enum (D10), never an unclassified state | Test asserting every fake-call scenario resolves to one of the 5 values |
| 4 | The redaction and summary/intent calls never affect B4 or B5 | Test proving fake-call latency and turn-cap behaviour are unchanged with the post-call pipeline attached vs. detached |
| 5 | B3 extends to cover the second, non-realtime deployment (D11) | `CLAUDE.md` B3 row updated + CI static check covers both deployments |
| 6 | `evals/` runs 20 scenarios through the LLM judge, ≥95% pass over 20 runs | A real weekly/on-demand run, reported |
| 7 | `redteam/` (18 ideas) runs at its L4 cadence, sampled, $-capped, non-blocking | A real run, reported |
| 8 | Both D13 ADRs are written and accepted | `docs/adr/ADR-006-*.md`, `docs/adr/ADR-007-*.md` |
| 9 | `RESULTS.md` and an architecture diagram exist; `README.md`'s phase badge is current | Files present, `README.md` diff |
| 10 | `COSTS.md` prices the Language resource and the second model deployment; R-08 recomputed if either changes the fixed monthly total | `COSTS.md` diff, same recompute discipline as every prior phase |

---

## What this phase must not do

- Provision the Azure AI Language resource before its `/research` pass clears the quota/region
  question — `APPROVED: Phase 8` covers the phase, not a fact that hasn't been checked yet.
- Write a raw (unredacted) transcript to any persistent storage, even transiently.
- Route summary/intent generation through the realtime deployment, or leave it uncovered by an
  extended B3 allowlist.
- Let the post-call pipeline add latency or cost to the live call — it runs after hangup, full stop.
- Pad the redteam corpus to hit "20-30" — 18 stays 18.
- Let `RESULTS.md` grow without the ceiling D6 commits to.
