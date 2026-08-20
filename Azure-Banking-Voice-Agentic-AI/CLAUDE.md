# CLAUDE.md — Azure-Banking-Voice-Agentic-AI

**Canonical project path**: `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI`, inside the
`Portfolio-Projects` monorepo (`git@github.com:MAOFILHO/Portfolio-Projects.git`), branch
`azure-banking-voice-agentic-ai`. Recorded here because a session started from an unrelated directory
has no other way to find it — added 2026-08-20 after exactly that happened.

### STOP CONDITIONS — absolute, no exceptions

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling (below).
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

---

## What this project is

A production-grade prototype IVR — a real Canadian phone number that a caller dials to reach a
banking voice agent — built on Azure Communication Services + Azure OpenAI's realtime API, under a
hard **$25/month** ceiling. It is the deliberate Azure counterpart to
`AWS-Insurance-FNOL-Voice-Agentic-AI`: same portfolio, same rigor, different cloud, different domain.

**`docs/PLAN.md` is the source of truth for scope, architecture, budget, region, phase plan, and
tracked risks.** This file does not repeat that content — it exists for the operating rules that
apply *across* every phase. Read `docs/PLAN.md` before starting any phase.

---

## Named constraints — the spine

Every one of these is measurable, adversarially tested where noted, and CI-gating. They do not move
without Marco's explicit sign-off; if a phase's design would violate one, that's a stop-and-ask, not
a judgment call.

| ID | Constraint | Target | Enforced at |
|---|---|---|---|
| **B1** | **Auth Gate Integrity** — zero authenticated-only tool invocations reach the core-banking client while `session.auth_state != Authenticated` | **0 breaches / ≥120 adversarial cases** | L1, blocking CI |
| **B2** | **PIN Confidentiality** — the DTMF PIN never appears in any transcript, log line, OTel span attribute, or persisted record | **0 occurrences**, artifact scan | L0+L1, blocking CI |
| **B3** | **Model Pinning** — no code path can instantiate a realtime deployment outside the allowlist, keyed on **(deployment name, model version) together, not name alone** (an active pin plus one documented successor, not a single frozen constant) | **0 violations** | startup guard (reads the live deployment's actual model version at boot, not config alone) + CI static check + Bicep |
| **B4** | **Cost Ceiling** — no call exceeds 5 min / 20 turns; daily aggregate minute cap trips "we're closed"; **fails closed** | **0 overruns, 0 fail-open events** | L1, blocking CI |
| **B5** | **Turn Latency** — p95 turn round-trip | **PROVISIONAL after Phase 2 (N≥100 real turns); FROZEN after Phase 5 (tool calls in path)** | L3 + production OTel |

`spendingLimit: Off` is confirmed on the subscription — **Azure will not stop spend at any
threshold.** B4 is the only brake that exists. Any p95 latency figure quoted anywhere in this project
**states the turn count behind it**; a percentile with no stated N is not a finding.

Full detail (fail-closed test cases, the B3 startup guard, B5's staged measurement) lives in
`docs/PLAN.md` — this table is the quick-reference, not the definition.

**Model pin review**: B3's active pin (`docs/PLAN.md` decision 14) is checked against the live Models
API at every phase gate — its retirement date is a scheduled decision to revisit on a known clock, not
something that gets discovered as a surprise partway through a later phase. If the active pin's
retirement is under 2 months out at any gate and no better-runway GA option exists yet, that's a
stop-and-ask before the phase proceeds, same as any other named constraint here.

Phase 0 also found (2026-08-20) that the startup guard's original design checked deployment *name*
only, not name+version — promoted to a hard Phase 2 requirement after R-01's own evidence showed one
name can span multiple versions with different retirement dates and rate limits, which a name-only
allowlist would not catch on a silent redeploy. See `docs/PLAN.md`'s B3 code block and
`docs/phase0/findings.md` "B3 end-to-end check".

---

## `PROJECT_STATE.md` — decision 18

`PROJECT_STATE.md` is a **fixed-size current-state document only**: open items, current phase, active
defects, next actions. **Hard ceiling: ≤400 lines / ~20 KB.** Historical narrative, saga write-ups,
and anything past-tense belongs in `docs/phaseN/`, never here.

This rule exists because FNOL's `PROJECT_STATE.md` grew to 557 KB and became that project's single
biggest token cost. Check the file's size before every edit; if an addition would push it over the
ceiling, move the oldest closed material out to `docs/phaseN/` first, in the same commit.

---

## Resume discipline

**On resuming any session, verify live Azure state before acting on `PROJECT_STATE.md`.** At minimum:
resource-provider registration state, resource-group existence, and any resources the doc claims
exist. `PROJECT_STATE.md` is a snapshot and goes stale between sessions (a registration can finish, a
manual action can happen outside any session) — the API is truth, the doc is not. Report any
disagreement between the two rather than silently trusting either one and proceeding. Added 2026-08-20
after a resume found `Microsoft.Communication` already `Registered` while the doc still said
`Registering`, and separately found two real fixes sitting uncommitted in the working tree from a
session that ended without closing them out.

## Hard exclusions

These are not style preferences — each one is a specific, evidenced defect found during scoping.
Reintroducing any of them is a regression, not a fresh judgment call.

- **Never vendor `fixed_openai_agents.py` from `azure-openai-agents`.** It fabricates telemetry:
  when a handoff span's real `to_agent` is missing, it invents a destination by string-matching that
  demo's specific agent names. Any dashboard built on it is partly fiction.
- **Never reproduce the silent-fallback bug** (`azure-openai-agents/main.py:59-65`,
  `check_account_balance` returning `$1,000.00` for any unknown account). An unknown account **must
  raise**; the caller-facing path handles the error gracefully. Covered by `T-UNKNOWN-ACCT`.
- **`AI-Powered-Call-Center-Intelligence`'s post-call ARM template is disqualified as infrastructure
  reference.** It hardcodes App Service Plan `EP1` (Elastic Premium) and Azure SQL — either alone
  blows the $25/month ceiling several times over. Its post-call *topology* (blob → redaction →
  summary) is a fine reference; its ARM template is not.

---

## Model / context policy

- **Opus** for phase kickoff (design, exit-criteria authoring) and phase review (does the exit
  criteria actually hold). **Sonnet** for implementation inside an approved phase.
- **`/clear` at every phase boundary**, and only after `/handoff` has written a handoff doc under
  `docs/handoffs/` and the phase's work is committed. Never `/clear` with uncommitted work or an
  unwritten handoff outstanding.
- **`/handoff` itself always writes to the OS temp directory, never into the repo** — that's the
  skill's own fixed behavior (`~/.claude/skills/handoff/SKILL.md`: "Save to the temporary directory of
  the user's OS"), not a mistake to fix per-invocation. macOS `/tmp` is periodically cleaned and gone on
  reboot, so **every `/handoff` output must be copied to `docs/handoffs/` and committed before the
  session ends** — this is the compensating step that actually makes "unwritten handoff outstanding"
  above mean what it says. Added 2026-08-20 after a handoff nearly got lost this way.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or the DTMF/PIN path (B2).** Repeated from the stop conditions above deliberately — this is
  the one rule most likely to get skipped under time pressure.

---

## Skill discipline

**Marco invokes skills — Claude does not invoke them on its own initiative.** When a phase or situation
calls for `/research`, `/wizard`, `/code-review`, or `/prototype` below, Claude's job is to say so
plainly (name the skill and why it applies) and stop — not to reach for a `Skill` tool call itself. This
is a deliberate override of the general default (elsewhere, calling a skill proactively is normal
practice); here it exists because Phase 0's hard gates depend on a human decision point actually being a
stop, not a pass-through Claude reasons its way around under time pressure.

- **Main flow, per phase:** design → build → test → `/code-review` → exit-criteria check → commit →
  `/handoff` → `/clear`.
- **`/research`** for any factual unknown — pricing, API shape, region/model availability,
  regulatory requirement. Never answer from memory or assumption; this project has already been
  burned once by an unverified regional assumption (see `docs/PLAN.md`, decision 12's history).
- **`/wizard`** for phases with a human-in-the-loop step Claude cannot perform itself — provisioning
  that needs a live decision, dialing a real phone, anything requiring Marco's hands or voice.
  Phase 0 runs this way.
- **`/code-review`** before every phase gate, no exceptions — including phases that feel too small
  to need it.
- **`/prototype`** only for a genuinely unresolved design question (does this state model feel
  right, what should this turn-taking logic actually do) — not as a substitute for `/research` on a
  factual question, and not for routine implementation.
