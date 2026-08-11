# ADR-011: PII redaction boundary and mechanism — formalizes D16; two-layer redaction (in-call deterministic + Guardrails, then async defense-in-depth); reverses one specific piece of Phase 0 guidance

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

`AI-USE-CASE-CARD.md` already contains the substantive analysis this ADR formalizes: **D16**, which
corrected the Phase 1 draft's utility-only exemption of loss date/time from redaction. The card's
re-identification argument — date + time + location together are a quasi-identifier close to uniquely
identifying, because a vehicle collision at a given place and time is frequently externally recorded — is
not repeated here in full; this ADR exists to (a) fix the store/field boundary as an architecture decision,
not just a design note, (b) specify the **mechanism**, which D16 did not, and (c) record explicitly that
this reverses a specific, named piece of earlier Phase 0 guidance rather than let the reversal go unstated.

### The reversal that needs to be on record

`docs/phase0/DOMAIN-ARTIFACTS.md` recorded, as a Phase 0 taxonomy correction: **"`DATE_TIME` must NOT be
blanket-redacted — loss date/time is the single most important captured field."** D16 (Phase 1, corrected
same day) supersedes that specific guidance for transcripts and logs: date/time **is** now blanket-redacted
from those two stores, precisely because the quasi-identifier risk was analyzed properly. Phase 0's artifact
is not edited — per this project's convention, phase artifacts are historical record, not living documents —
but this ADR states the supersession by name so a future reader of `DOMAIN-ARTIFACTS.md` alone is not misled
by now-outdated guidance with no pointer forward.

## Decision

### The boundary (formalizing D16)

| Store | `loss_datetime` | `loss_location` | VIN / plate / policy # / claim # | Standard PII (name, phone, email, address, SSN-shaped strings) |
|---|---|---|---|---|
| **Structured claim record** (DynamoDB) | Retained | Retained | Retained | Retained |
| **Persisted transcript** | Redacted | Redacted | Redacted | Redacted |
| **Application logs / traces / metrics** | Redacted | Redacted | Redacted | Redacted |
| **Eval / red-team fixtures** | Synthetic only | Synthetic only | Synthetic only | Synthetic only |

The structured record is authoritative and unredacted because the fields *are* the payload — this is what
"the utility need is met by the structured record" (D16) means concretely. Every other store gets uniform,
maximal redaction, because a quasi-identifier's risk does not diminish by only partially removing it.

### The mechanism (new in this ADR — D16 fixed the boundary, not how redaction is executed)

**Two layers, not one, with different jobs:**

**Layer 1 — in-call, per-turn, before any transcript line is durably persisted.** This is the layer that
makes `AI-USE-CASE-CARD.md`'s "the unredacted transcript is never written anywhere, not even transiently"
claim actually true, rather than aspirational. It runs on each turn's raw ASR text, before that turn is
appended to the durable per-call transcript store, and combines:
- **Bedrock Guardrails PII filters** (input and output), covering the standard entity taxonomy — name,
  phone, email, address, and similar — per the existing "Guardrails on input and output" requirement in
  `CLAUDE.md`.
- **A deterministic regex/format redactor for the four domain-specific identifiers this project's own
  formats define** — VIN, license plate, policy number, claim number — none of which are in Comprehend's or
  Guardrails' default PII entity taxonomy (a gap Phase 0 archaeology already identified: *"repo 3's PII list
  has no VIN / LICENSE\_PLATE / POLICY\_NUMBER / CLAIM\_NUMBER"*). Because each of these formats is fixed and
  machine-checkable (`^PY\d{4}$` for policy number, the project's own claim-number format from Phase 3, a
  standard 17-character VIN pattern, a plate format), a deterministic redactor is both more reliable and
  cheaper than a generic entity classifier for exactly these four fields — the same "deterministic where
  possible" preference already applied to injury detection (`D12`) and safety ordering (`ADR-010`).
- **Blanket redaction of `DATE_TIME`- and `LOCATION`-tagged spans**, reversing the Phase 0 guidance named
  above. This is applied to the free-text narrative, not to the structured slot capture — the structured
  `loss_datetime`/`loss_location` slot values are captured once, directly into the DynamoDB record, by the
  dialogue graph itself; the transcript redactor's job is only to scrub the caller's spoken narrative, where
  the same information often reappears in prose ("it happened around 5:30 yesterday near the school on
  Maple") with no operational purpose once it has already been captured structurally.

**A caveat inherited from `AI-USE-CASE-CARD.md`, restated because it is load-bearing for Layer 1's design,
not just a footnote:** free-text location redaction is genuinely hard. A location-entity tagger may miss
"right outside my kids' school on Maple." This is why Layer 2 exists — not to fix Layer 1's precision, which
is a modeling problem no second pass eliminates, but to catch a **different class of gap**: cross-turn
leakage, where a fact spans two turns and neither turn's redactor sees the full pattern in isolation.

**"Not even transiently" is scoped to persistent storage, not to in-process memory.** A single Lambda
invocation holding a turn's raw ASR text in a Python variable for the duration of that invocation is not a
"write" in the sense the use-case card means — the claim is about durable storage (DynamoDB, S3, CloudWatch
Logs), not about the impossible bar of a running process never holding a string in memory. This ADR states
that scoping explicitly so a future reader does not over-read the original phrasing into an unbuildable
requirement.

**Layer 2 — async, post-call, defense-in-depth (runs inside `ADR-006`'s existing post-call pipeline).** Once
the full call's already-redacted transcript is assembled, Layer 2 re-scans the **assembled, already-redacted
artifact** — not a second copy of raw text — for anything Layer 1's per-turn, per-line redaction missed
because the leaking pattern spanned a turn boundary (e.g., the caller says a street name on one turn and a
school name that narrows it to a specific block on the next). Layer 2 does not introduce a new place where
raw text exists; it operates on exactly the transcript Layer 1 already produced, and re-applies the same
entity/format redaction rules across the reassembled document instead of per-line. **This is why `ADR-006`'s
description of the post-call pipeline says "full-transcript PII redaction (beyond what already happened
turn-by-turn)"** — the two ADRs describe the same two-layer design from different sides.

## Consequences

**Positive:**
- Closes the concrete taxonomy gap Phase 0 identified (VIN/plate/policy#/claim# absent from default PII
  entity lists) with a deterministic mechanism rather than leaving it as an open question into Phase 5.
- Makes the "never written anywhere, not even transiently" claim in `AI-USE-CASE-CARD.md` architecturally
  true rather than aspirational, by fixing exactly where Layer 1 sits in the write path.
- The two-layer design gives defense-in-depth against cross-turn leakage without duplicating raw-text
  storage anywhere — Layer 2 reprocesses Layer 1's output, not a second unredacted copy.

**Negative / accepted residual risk:**
- Free-text location/date redaction remains imperfect by nature, as already disclosed in
  `AI-USE-CASE-CARD.md`. Layer 2 mitigates *cross-turn* leakage specifically; it does not make single-turn
  entity tagging perfect, and this ADR does not claim otherwise.
- The regex-based redactor for VIN/plate/policy#/claim# is only as good as this project's own format
  definitions (Phase 3). If a caller states an identifier in a format the regex doesn't anticipate — a
  policy number read with extra pauses or a homophone substitution — it may not be caught by Layer 1's
  deterministic pass and would rely on Layer 2 or Guardrails' generic PII catch-all, neither of which is
  designed for domain-specific ID formats. Recorded as a residual gap for Phase 7 red-teaming to probe.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| Single-layer redaction, only at post-call/async time | Rejected | Would require writing the raw transcript somewhere durable before the async pipeline could redact it, directly violating the "never written anywhere, not even transiently" requirement |
| Rely solely on Bedrock Guardrails' generic PII entity list | Rejected | Does not cover VIN/plate/policy#/claim# — the exact gap Phase 0 identified in the default taxonomy |
| Leave `DATE_TIME` unredacted per the original Phase 0 guidance | Rejected — superseded by D16 | The quasi-identifier analysis in `AI-USE-CASE-CARD.md` shows this is a real re-identification risk when combined with location, not a stylistic preference |
| **Two-layer: in-call deterministic+Guardrails, then async cross-turn defense-in-depth** | **Chosen** | Satisfies the "never transiently unredacted" requirement architecturally; adds cross-turn coverage Layer 1 alone cannot provide |

## Sources

This ADR formalizes an existing project decision (D16, `AI-USE-CASE-CARD.md`) and Phase 0 findings
(`docs/phase0/DOMAIN-ARTIFACTS.md`, `docs/phase0/SECURITY-FINDINGS.md`) rather than new external research;
no live AWS-capability claim in this ADR required fresh verification beyond what `ADR-006` and the existing
Guardrails requirement in `CLAUDE.md` already establish.
