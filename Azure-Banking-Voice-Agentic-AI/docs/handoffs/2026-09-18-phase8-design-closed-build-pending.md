# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 8 design closed, build pending

**Date**: 2026-09-18
**Canonical path**: `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI`, branch `main`, no
worktree split (confirmed at session start against `CLAUDE.md`'s canonical-path warning).

## Stop conditions — restated verbatim, per `CLAUDE.md`

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.**
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling
  (≤400 lines / ~20 KB — currently 215 lines / 16.6 KB).
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

## What this session did

Ran `/grill-with-docs Phase 8` (grilling + domain-modeling skills together) to take Phase 8 from a
one-paragraph sketch (`docs/PLAN.md`) to an approved design. 13 questions across 3 rounds, all
answered and confirmed as shared understanding. Then wrote the design doc and both ADRs it named,
ran `/research` on the one fact-dependent decision, corrected a wrong assumption it found, and got
Marco's sign-off on the corrected cost.

**Full content lives in these artifacts — do not re-derive it here, read them:**

- `docs/phase8/exit-criteria.md` — the design itself: 13 settled decisions (D1-D13), entry conditions,
  current-state gap table, 10 proposed exit criteria, what the phase must not do.
- `docs/adr/ADR-006-second-model-pin-for-post-call-text-work.md` — the second, non-realtime AOAI
  deployment for post-call summary/intent + L3 eval judging, and how B3 (Model Pinning) needs to
  extend to cover it (extension itself not yet written into `CLAUDE.md` — deferred to when that
  deployment is actually built, same sequencing Phase 6 used for B2's widening).
- `docs/adr/ADR-007-redact-before-first-write.md` — why transcript redaction happens in memory before
  the first Blob write, never on a stored raw copy — this is what keeps the new transcript pipeline
  from becoming a new B2 surface.
- `docs/phase8/research-language-pii-quota.md` — primary-sourced findings on Azure AI Language
  Conversation PII detection: no free tier exists for this specific feature (Standard-tier only,
  $1.00/1,000 text records in Canada Central); region is confirmed fine.
- `CONTEXT.md` — **Call outcome** added as its own glossary term (`end_reason` in code), kept distinct
  from the renamed **Tool-call outcomes** section (the four tool-call failure types).
- `COSTS.md` — new section pricing the Language resource at this project's volume: bounded
  $0.07-$1.34/mo (exact billing unit — per turn vs. per call — unconfirmed by any source found). No
  R-08 recompute needed; trivial against the $25/mo ceiling.
- GitHub issue [#66](https://github.com/MAOFILHO/Portfolio-Projects/issues/66) — tracking issue, with
  a closure-summary comment.
- Commits: `49c10cc` (design + both ADRs), `cd83471` (research correction + cost line + approval
  record).

## Approvals on record

- `APPROVED: Phase 8` — given 2026-09-18, covers the phase generally.
- `APPROVED: Phase 8 Language resource` — given 2026-09-18, **separately**, after `/research` found
  the original "free tier" assumption was wrong and the real cost was bounded and shown to Marco
  first. This distinction matters: don't treat a blanket phase approval as covering a cost premise
  that changed after the approval was given — that pattern (surface the correction, re-confirm at the
  corrected number, only then treat it as approved) is what happened here and is worth repeating if a
  similar correction surfaces during build.

## Where this stands — nothing built yet

Design is fully closed and approved. **No code has been written for Phase 8; no Azure resource for it
has been provisioned.** The session stopped deliberately at the design-to-build boundary (Marco chose
to `/handoff` rather than continue into build in the same session) — this matches `CLAUDE.md`'s
"`/clear` at every phase boundary" guidance. Recommend `/clear` after this handoff is read and
committed, before build work starts, per that same rule.

## Open questions for the next session

1. **Where to start the build** — not decided. Two reasonable entry points were on the table when
   this session ended: (a) the redact-before-first-write pipeline (ADR-007) first, since it's the
   lower-risk piece and doesn't touch a new Azure resource; (b) the Language resource provisioning
   first, since its approval is now in hand and later steps depend on it existing. Ask Marco, don't
   assume.
2. **The exact deployment name for the second, non-realtime AOAI model** (ADR-006) — the ADR fixes the
   model class (`gpt-4o-mini`-class) and the reasoning, not the string. Pick this at build time.
3. **The per-call billing unit for Conversation PII detection** (per turn vs. per conversation) is
   still unconfirmed by any primary source `/research` found — `docs/phase8/research-language-pii-
   quota.md` §1d flags this as an open question. Doesn't block starting the build (the cost bound
   either way is trivial), but worth resolving once the resource is live and a real invoice line
   exists to check against.

## Suggested skills for the next session

- **Skill discipline override is in force** (`CLAUDE.md`, "Skill discipline" section) — for this
  project specifically, do not invoke `/research`, `/wizard`, `/code-review`, or `/prototype`
  proactively. Name the applicable one and why, then stop and let Marco call it. This is a deliberate
  override of the general default elsewhere in this session's environment.
- **`/code-review`** — required before the Phase 8 gate closes, no exceptions, same as every prior
  phase. Marco invokes it when build work is far enough along.
- **`/wizard`** — only if the Language resource's provisioning turns out to need a manual, one-time
  human-in-the-loop portal step (RBAC grant, resource registration) the CLI/Bicep can't do alone —
  same shape as Phase 7's D4 (GitHub OIDC setup). Not confirmed needed yet; check when build reaches
  that step.
- **`/research`** is not expected to be needed again for Phase 8 — the one fact-dependent decision
  (D2) is resolved. Only reach for it if a new factual unknown surfaces during build (a different
  quota, an API shape question, etc.).
- **`mattpocock-skills:tdd`** — worth considering for the redact-before-first-write pipeline and the
  post-call analytics code, given this project's existing L0-L4 test-layer discipline
  (`docs/PLAN.md`, "Testing strategy") and that ADR-007's guarantee (no raw transcript write, ever) is
  exactly the kind of property a test-first pass is good at pinning down before the implementation
  exists to accidentally violate it.
