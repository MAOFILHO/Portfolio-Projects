# Phase 4 — findings and recorded deviations

Written as the phase was built, ticket by ticket, rather than reconstructed at the end. Everything
here is something a later session would otherwise discover rather than read.

---

## Deviations from the written tickets

Each of these is flagged rather than folded in silently, which is the rule the exit criteria set
for the one deviation they anticipated (the `unittest`-for-pytest substitution, criterion 10).

### 1. The authenticator has seven outcomes, not the six #36 lists

`docs/phase4/exit-criteria.md` and issue #36 both name six: accumulating, cleared, authenticated,
rejected credential, attempts exhausted, unavailable. The implementation has a seventh,
**`IGNORED`**.

It is required by the protocol the same tickets specify. Pound is ignored, and a key arriving after
the call's authentication question is already settled — passed, or exhausted — is ignored too.
Neither is *accumulating* (nothing was accumulated) and neither is *cleared* (nothing was cleared),
so reporting either would be untrue. The relay acts on the same four outcomes it always did; the
addition is entirely on the silent side.

### 2. The injected conversation item's shape is not verified against the live deployment

Criterion 7 and issue #37 call for the outcome to be injected "as a conversation item plus a
response request — the same mechanism the handoff already uses". The handoff's mechanism is a
`conversation.item.create` carrying a **`function_call_output`**, and that shape *is* verified live
(`docs/phase1/research-aoai-realtime-wire-format.md`, confirmed on a real Phase 1 call).

A PIN outcome answers no tool call, so it has no `call_id` and cannot use that item type. What
`realtime/session.py:_spoken_note` sends instead is a `message` item with a `system` role and
`input_text` content. **That shape is the documented one and nothing more — this project has never
seen the deployment accept it.**

This sits in the same known-partial as the keyed tone itself and closes at the same point: Phase 5's
real-call exit. It is recorded here because Phase 4 deploys nothing, so nothing in this phase can
close it, and `CLAUDE.md`'s rule against answering a factual API question from memory means it must
not be left reading as verified.

**Wanted before Phase 5's real call:** `/research` on the Azure OpenAI realtime API's
`conversation.item.create` item types, specifically whether a `system`-role `input_text` message is
accepted mid-session on a `gpt-realtime-mini` deployment, and what a rejection looks like.

### 3. B2's leak detector is `unittest`, not a pytest autouse fixture

Anticipated by the exit criteria's own criterion 10 and by issue #39, and repeated here so the
record is in one place. This project runs stdlib `unittest discover` from its `Makefile`; the
criterion's intent — blocking by construction rather than a CI step someone can drop — is met by
installing the capture from the suite itself.

---

## Recorded up front, unchanged

**No real DTMF tone has ever been consumed by this system.** Phase 0 confirmed live, on calls 2 and
3, that tones *arrive* during active bidirectional streaming. Every line of code that acts on one is
new in this phase and is exercised only against fakes. This is the direct consequence of the phase
deploying nothing, and it closes at Phase 5's real-call exit.
