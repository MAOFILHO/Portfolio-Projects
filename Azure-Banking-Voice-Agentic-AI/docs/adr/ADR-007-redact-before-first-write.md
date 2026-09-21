# ADR-007 — Transcript redaction happens before the first persistent write, not after

Status: **Accepted** — decided during Phase 8 design (`/grill-with-docs`, issue #66, Q4), 2026-09-18.
Date: 2026-09-18

## Context

Phase 8 introduces the first persistent, readable-after-the-fact record of what a caller actually
said: a transcript written to Blob storage. Nothing like this existed before — Phase 6's spans record
*that* a turn happened and how long it took, never its content, and the call-record store (`CONTEXT.md`)
holds facts about calls, never transcripts. A transcript is a new kind of artifact for this project,
and it is exactly the kind of place B2 (PIN/phone-number confidentiality) could be violated by a
caller who reads their PIN back to confirm it, or states their own phone number during a call.

Two designs were considered. **Write raw, redact after**: the realtime session's transcript is
written to Blob as-is, then a redaction pass (Azure AI Language Conversation PII detection, ADR-006's
sibling decision D2) runs against the stored blob and overwrites it. **Redact before the first write
(chosen)**: the transcript is held in memory, passed through Conversation PII detection, and only the
redacted result ever touches Blob.

The first design is simpler to implement — a redaction job can run on a schedule, retried
independently of the call path — but it means a raw transcript exists in persistent storage for some
window, however short, between the write and the redaction pass completing. That window is a real B2
surface: a storage-account misconfiguration, a crashed redaction job, or simply reading the blob in
that window would expose exactly what B2 exists to prevent. B2's existing guarantee (0 occurrences,
artifact scan) is proven by scanning what was written after the fact — it has never had to reason
about a window where the wrong thing was written and not yet fixed.

## Decision

1. **The transcript is redacted in memory before it is written anywhere.** Azure AI Language
   Conversation PII detection runs against the in-memory transcript object; only its output is ever
   passed to the Blob write call. No code path writes the pre-redaction transcript to Blob, to Table
   Storage, to a log, or to any other persistent sink, even transiently or for retry purposes.
2. **A raw transcript that cannot be redacted (the redaction call fails or times out) is never written
   unredacted as a fallback.** The call-record store records that redaction failed for this call
   (an operational fact, not the transcript itself); the transcript write is simply skipped for that
   call, same fail-closed posture as B4's cost brake.
3. **This is proven by a dedicated test**, not folded into B2's existing artifact scan: assert that
   across a fake-call run, no Blob write call ever receives content containing an unredacted marker
   the test transcript carries, at any point in the call — not just checking the final state.

## Consequences

- **B2 does not need widening to a fifth channel for this.** The channel (Blob) never carries
  unredacted content at any point, so there is nothing for a post-hoc scan to have caught — the
  control is architectural, the same relationship the **auth gate** has to defence-in-depth checks
  elsewhere in this project: the gate decides, everything else is a net.
- **Redaction failure means a missing transcript for that call, not a delayed one.** A future feature
  that wants "eventually consistent, always arrives" transcripts is a change to this decision, not an
  extension of it — it would need to reopen the write-raw-then-redact design this ADR rejected, with
  its own sign-off.
- **The redaction call is now on the critical path of whether a transcript exists at all**, though
  never on the live call's critical path (ADR-006, Decision 4) — a slow or degraded Language service
  reduces transcript coverage, not call quality. Acceptable: a missing transcript is a worse analytics
  month, not a worse call for the caller.

## Build note — 2026-09-21 (Phase 8 gate review)

**Decisions 1-3 are built and unchanged.** Two facts the Context and Decision 1 did not carry:

- **D14 shrank the premise, not the decision.** The Context imagines a caller reading their PIN back
  to confirm it. D14 (`docs/phase8/exit-criteria.md`, 2026-09-19) made the stored transcript
  agent-side only, so a caller's own words, including a PIN they speak, never enter it. What remains
  at risk is anything the *agent* says: an account number it reads out, a name, a figure. Redaction
  before the first write is still right, for that smaller surface.
- **"No other persistent sink" governs this project's storage. Azure AI Language is a processor, and it
  keeps job results for 24 hours** (`docs/phase8/research-postcall-adapters.md`, results shape). Those
  results carry the redacted text and the detected entities, and an entity records the text it
  matched, so for that window the service holds the PII it found. The adapter does not delete a job
  after reading it, and the voice agent's role (`Cognitive Services Language Reader`) grants
  `jobscancel` and no delete action, so it could not. This is the service's own retention, disclosed
  here rather than designed out; closing it would take a role with delete rights and a `DELETE` after
  each read, a change to be weighed against widening a data-plane grant.
