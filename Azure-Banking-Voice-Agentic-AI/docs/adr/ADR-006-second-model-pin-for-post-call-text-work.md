# ADR-006 — A second, non-realtime model pin for post-call summary/intent and L3 eval judging

Status: **Accepted** — decided during Phase 8 design (`/grill-with-docs`, issue #66, Q11/Q12/Q13),
2026-09-18.
Date: 2026-09-18

## Context

Through Phase 7, B3 (Model Pinning) named exactly one allowlisted deployment: the realtime speech-to-
speech model (`gpt-realtime-mini`) a live call actually talks to. Phase 8 adds two new jobs that are
not part of any live call: summarizing a redacted transcript into a summary/intent/**call outcome**
record after hangup, and judging L3 eval transcripts against a rubric. Both are one-shot text
completions over a short, already-redacted input — nothing about them needs a speech-to-speech model,
and the realtime deployment's per-minute pricing is the wrong shape for a job with no audio and no
open connection.

The alternative considered was routing both jobs through the existing realtime deployment anyway, to
avoid a second pin. Rejected: it would mean holding a realtime session open (or reopening one) purely
to get text in and text out, paying for capability neither job uses, and it would blur B3's own
guarantee — "the realtime deployment" stops meaning one thing if the same deployment is also the
thing that summarizes and judges.

## Decision

1. **A second Azure OpenAI deployment, a `gpt-4o-mini`-class text model**, is provisioned for both
   jobs. Exact deployment name is chosen at build time; this ADR fixes the class and the reasoning,
   not the string.
2. **One deployment serves both jobs** — post-call summary/intent and the L3 eval judge — rather than
   two separate pins. Same reasoning ADR-005 already used for one core-banking client: two pins for
   the same kind of job (one-shot text completion, no tools, no audio) is a second thing that can
   drift out of agreement with the first, for no capability gained.
3. **B3 extends to cover both deployments together.** B3's `CLAUDE.md` row currently reads "no code
   path can instantiate a **realtime** deployment outside the allowlist" — that wording is scoped to
   one deployment class and needs editing when this deployment is built, not left to imply the second
   one is unpinned. The allowlist mechanism (keyed on deployment name + model version, per B3's
   existing shape) extends unchanged; only the `CLAUDE.md` prose and the CI static check's scope grow.
4. **This deployment is never reachable from the live-call path.** It is invoked only after a call's
   WebSocket has closed (post-call summary/intent) or entirely outside any call (eval judging) — never
   from `dispatch/gate.py`, never from an agent's tool table. A code path that could reach it from a
   live call would be a B4/B5 regression, not a B3 one, and is out of scope for what this ADR permits.

## Consequences

- **`CLAUDE.md`'s B3 row is edited when this deployment is actually built**, not by this ADR alone —
  same sequencing Phase 6 used for B2's widening (issue #65): the decision is recorded first, the
  constraint's canonical wording changes alongside the code that makes it true.
- **A future third model pin request is a change to this decision**, not a quiet third deployment —
  it needs its own sign-off, the same way ADR-005 treats a second core-banking client or a third
  anonymous-row grant as needing one.
- **The eval judge and the post-call summarizer share a failure mode**: if this deployment's model
  version is retired, both jobs stop working at once, not independently. Accepted — the alternative
  (separate pins) trades that coupling for a second thing to keep in sync, judged the worse trade in
  Decision 2 above.

## Build note — 2026-09-18

Decision 1's class is filled in: the deployment is **`gpt-5.4-mini`** (2026-03-17, GlobalStandard),
live on `aoai-azure-banking-voice-cc`. Chosen live over the ADR's own `gpt-4o-mini` example — status
`Deprecating` on the Models API, wrong choice for a brand-new pin — and over `gpt-5-mini` (GA, but
~4.7 months of runway from today vs. `gpt-5.4-mini`'s ~12, retiring 2027-09-21). This does not change
the decision above; it fixes the string this ADR deliberately left open.

**Decision 3 is now done** (2026-09-18, same session as this note): `CLAUDE.md`'s B3 row and
"Model pin review" paragraph, and `scripts/check_b3_allowlist.py`'s scan scope and allowlist union,
now cover both deployment classes. `boot.py` gained `ACTIVE_TEXT_MODEL` and `ALLOWED_TEXT_MODELS`.
A runtime guard for the text pin (non-fatal, per Decision 4) was drafted and removed the same day:
with no caller until the post-call pipeline exists, it enforced nothing. It is built with that
pipeline instead. **Not done**: `infra/modules/aoai.bicep` still declares only the
realtime pin. This deployment was hand-provisioned (`PROJECT_STATE.md`), not via Bicep, so the text
pin has no Bicep-side enforcement yet — that gap is real follow-up work, not something this note
should let `CLAUDE.md` claim as already covered (`CLAUDE.md`'s B3 row now says so explicitly).

## Build note — 2026-09-20

**Decision 4 is now done.** `boot.assert_text_model_safety` (built 2026-09-19 with the post-call
pipeline) reads the live deployment's `(name, version)` and raises `TextModelUnsafe` on a mismatch or
an unreadable deployment. `postcall/summarizer.py` calls it before every summary, off the event loop;
the pipeline records `summary_status=failed` and carries on. It never blocks boot or a call. Verified
live on 2026-09-19 (a real summary came back) and on a real call on 2026-09-20. **Still not done**:
Bicep-side enforcement (above), unchanged.
