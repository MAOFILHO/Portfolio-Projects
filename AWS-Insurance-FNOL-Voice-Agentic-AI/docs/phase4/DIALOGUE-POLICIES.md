# Dialogue Policies — Phase 4

Covers three roadmap components together (dialogue policies, barge-in/repair, escalation triggers) because
they interact directly — the barge-in design in §6 only makes sense against the per-turn pipeline in §1, and
the retry ceiling in §7 is what keeps §6's repair behavior from becoming its own unbounded loop.

---

## 1. Per-turn pipeline — reference

Every turn, whether it followed a completed bot prompt or interrupted one (barge-in — see §6), runs the same
five-step sequence. Nothing in this document adds a second pipeline for a special case; every policy below
is a decision about *what happens at* one of these five steps, never a bypass of them.

1. **L1** — deterministic injury/fatality pre-node, on the raw ASR transcript, before anything else touches
   it (`D12`, `ADR-010`).
2. **Merged Nova Micro routing + L2 safety call** — forced tool-use, intent/slot classification and
   recall-biased safety classification in one call (`ADR-004`). Runs only if L1 did not already escalate.
3. **`ApplyGuardrail`, input** — explicit graph node, not bolted onto a model call (`ADR-010`).
4. **Generation** (feature-flagged tier) or a tool call, depending on intent — only if steps 1–3 did not
   already terminate the turn.
5. **`ApplyGuardrail`, output**, then Polly synthesis.

L3 (the hard "agent" barge-in intent) is not a pipeline step — it is a caller-triggered override reachable at
any point in this sequence, covered in §6 and §8.

---

## 2. `CoverageQuestion` compound dialogue policy

Resolves `coverage-logic.md` §4's finding: **the split is by question type, not benefit type**, and this
changes intent 3's dialogue design directly — it is not a pure-RAG intent for every sub-question.

**Decision path, run after slot-filling (`policy_number`, `coverage_topic`) and before generation:**

1. Classify the filled `coverage_topic` into one of two question types. This classification is itself part
   of the merged router+L2 call's output (step 2 above) — not a separate model round-trip, consistent with
   `ADR-004`'s latency reasoning.
   - **Election-fact** ("is X part of my coverage") — is it in force at all?
   - **Eligibility/amount** ("will I get paid, and how much") — a determination, not a fact.
2. **Election-fact, mandatory coverage** (TPL, DCPD, Uninsured Auto, Medical/Rehab/Attendant Care at any
   severity track) → **pure RAG**. Same answer for every policyholder; the retrieved policy-wording passage
   is sufficient. No tool call.
3. **Election-fact, optional benefit or endorsement** (the six 2026-07-01 SABS elections, Section 7
   Loss-or-Damage selection, rental endorsement) → **RAG + tool**. Retrieve the general "what this benefit
   is" passage from the wording (RAG), then call the mock policy system for this caller's `elected_benefits`
   map (tool) before answering yes/no. **This is the tool Phase 5 must build — named here as a forward
   requirement, not built in this phase**: a `GetPolicyholderElections`-shaped call, keyed on `policy_number`,
   returning the same election fields `data/synthetic/policyholders/policyholders.json` already models.
4. **Eligibility/amount, any benefit type** → **always deflect**, regardless of steps 2/3's classification.
   Scripted deflection: *"That depends on a few things I can't determine from here — let me get you to
   someone who can walk through your specific claim."* No RAG synthesis is attempted for this branch; the
   generation node is never invoked with an eligibility/amount question, precisely because the failure mode
   being avoided is a **confident-sounding but ungrounded amount**, not a poorly-grounded one — the policy
   is escalate-before-generate, not generate-then-check.
5. **Abstention is success, not failure**, per `PROBLEM-FRAMING.md`'s existing groundedness framing —
   unchanged by this split. If step 2's RAG retrieval returns nothing relevant, the answer is "I don't have
   that in your policy — let me get you to someone who does," same as any other `CoverageQuestion` miss.

**Why this can't be resolved at slot-filling time:** `coverage_topic` is free text captured before the
question-type classification happens — a caller says "am I covered for X," and the mandatory-vs-optional
determination requires knowing which of the six 2026-07-01 elections (if any) `X` maps to, which itself
requires the RAG retrieval to have already run once to identify the benefit. The practical order is: retrieve
first (to identify what benefit is being asked about and whether it's mandatory or optional), *then* decide
whether a tool call is also required — not decide up front from the raw utterance alone.

---

## 3. `RentalTowingEntitlement` compound dialogue policy

Consistent with `endorsements.md`'s existing shape — restated here as dialogue policy rather than corpus
content.

1. RAG retrieval answers *"is this covered at all, and under what terms"* — the daily cap, day limit, and
   total cap for rental (`endorsements.md`), or the flat per-incident towing allowance.
2. A tool call to the mock claims system answers *"what's the state of this specific claim"* — for rental,
   `days_in_repair` (feeding the `min(20 − days, ($1,000 − days×$50)/$50)` arithmetic `endorsements.md`
   already specifies); for towing, whether an active covered claim exists at all (towing has no running
   balance to check, per `endorsements.md`'s scope note — it's in-or-out, not metered).
3. **Both must run before the response is generated.** Answering from RAG alone while ignoring claim state is
   named a failure in `PROBLEM-FRAMING.md` even when the coverage statement is true on its own — this
   document does not relax that; the generation node's prompt (`PROMPT-REGISTRY.md`) requires both retrieval
   and tool results present in context before it is invoked for this intent.
4. If `claim_number` was not supplied and cannot be resolved to exactly one open claim on the policy
   (`SLOT-DESIGN.md` §3's fallback), the tool-call half cannot run — the response states the policy terms
   from RAG and explicitly says claim-specific status can't be checked without a claim number, rather than
   silently answering the RAG half alone and presenting it as complete.

---

## 4. Write-path confirmation policy

Full elicitation-level mechanics live in `SLOT-DESIGN.md` §2; stated here as policy because it is a dialogue
decision, not a slot-format one. **`UpdateContactInfo` writes only on unambiguous affirmative confirmation of
a character-grouped read-back, with exactly one retry on a failed/ambiguous confirmation before escalation —
tighter than the general two-attempt ceiling (§7), because a silent partial write is a critical defect, not a
missed target** (`PROBLEM-FRAMING.md`). No other intent in this taxonomy performs a write, so no other intent
carries this policy.

---

## 5. `InjuryEscalation` — hard escalation dialogue behavior

**Mechanically not a dialogue policy in the normal sense** — it is the one intent with no negotiation, no
slot filling, and no LLM discretion (`PROBLEM-FRAMING.md`). What this section specifies is the *scripted
behavior* once L1, L2, or L3 fires, since "no LLM discretion" means the words themselves must be fixed, not
generated per-turn.

**Sequence, fixed and identical regardless of which detection layer fired (`D15`'s union semantics — no
layer differs in what happens next):**

1. **Safety guidance first, verbatim**: *"If anyone needs medical help, please hang up and call 911."*
   Spoken before anything else, including before the transfer itself begins — a caller mid-emergency should
   not wait through a transfer announcement to hear this.
2. **Transfer initiated within the same turn** (`PROBLEM-FRAMING.md`'s success criterion) — no additional
   question asked, including no re-confirmation of what was just said. Asking "are you saying someone is
   hurt?" would be exactly the "negotiation" this intent is defined to never do.
3. **Full captured context handed to the human** — whatever slots were already filled on any in-progress
   intent (per `AI-USE-CASE-CARD.md` F8's durable checkpoint state), plus which detection layer fired and the
   triggering utterance verbatim, so the human does not re-ask what the caller already said.
4. **Preemption from any state**: this sequence can begin from inside any other intent's slot-filling, from
   the initial greeting, from a hold state — there is no graph node this pre-node cannot interrupt. This is
   what "immediate... from any state" means concretely: the pre-node is checked at step 1 of *every* turn's
   pipeline (§1), never conditionally skipped because some other flow is "in the middle of something."

**A completed escalation is a successful call outcome**, not a containment failure — restated here because
it is the one place in this document where the natural instinct (measure success as "resolved the call") is
backwards.

---

## 6. Barge-in and the L1 safety ordering — designed, not discovered

**Marco's addition, given R4 (zero prior art for barge-in anywhere in the source corpus) makes this a
genuinely greenfield design, not an adaptation.**

### 6.1 The ordering constraint on the interruption path

`ADR-010` fixes L1's position on the *normal* turn path: raw input reaches L1 before the model, before
Guardrails, before anything else touches it. Barge-in raises the same question on a different path: **when a
caller interrupts the bot's own prompt audio mid-sentence, does that interrupting utterance reach L1 before
anything else consumes it?**

**Design decision: barge-in does not create a second code path. It only changes when a turn starts, not what
happens once one does.**

Lex V2's `AllowInterrupt` (set `true` on every prompt, per `SLOT-DESIGN.md`'s elicitation prompts and
`PERSONA.md`'s scripted lines alike) lets caller speech interrupt Polly audio mid-playback. When barge-in
fires, Lex finalizes whatever ASR captured up to that point as this turn's `transcriptions[]` and invokes the
DialogCodeHook with the **same event shape** as any other turn — there is no `is_barge_in` branch anywhere in
the pipeline. Concretely, this means:

- L1 still runs first, unconditionally, on that turn's raw `transcriptions[].transcription` — before Lex's
  own slot-interpretation (`interpretations[]`), before the merged router+L2 call, before anything. Barge-in
  does not introduce a new consumer that could reach the text ahead of L1; it only ever changes *which of the
  bot's own prompts was mid-playback* when the caller started talking.
- What barge-in *does* change is the bot's own in-flight state: the prompt audio stops immediately, and
  whatever slot was being elicited is abandoned **for this turn only** — not lost. Dialog state is
  DynamoDB-checkpointed (`ADR-005`), so if the barge-in utterance turns out not to be a safety trigger and
  not a fulfilling answer to the abandoned slot, that slot is simply re-elicited on the next turn. This is the
  concrete closure of `AI-USE-CASE-CARD.md` F8's named "barge-in mid-write is an untested edge" gap **at the
  design level** — Phase 9 still has to verify it holds under real latency and concurrency, which is why F8's
  wording is not changed to "solved" anywhere in this document.

### 6.2 A barge-in cut off mid-word

The harder case: the caller starts talking, but Lex's own end-of-utterance detection (voice activity
detection, silence timeout, or the call itself degrading) finalizes a transcript before a complete thought —
including before an injury word is spoken. This is an ASR-layer limitation. Nothing downstream of the
microphone, including L1, can recover a word that was never captured. This document does not claim otherwise
— it specifies what the system does with an *incomplete* capture, which is a different and answerable
question.

**Two rules, both unconditional:**

1. **L1 still runs on whatever partial transcript was captured — never skipped because a transcript looks
   fragmentary.** A partial match is exactly as actionable as a full one; discarding a truncated capture
   without checking it would be strictly worse than checking a lexicon that might miss it anyway.
2. **Any barge-in event where L1/L2 do *not* detect a safety trigger from the (possibly partial) captured
   transcript is followed by an explicit open re-prompt, not a silent resumption of the original script.**
   The next system utterance is *"Sorry — go ahead, what were you saying?"*, never an immediate re-ask of the
   original slot question as though the interruption hadn't happened. This gives a caller whose utterance was
   physically cut off one guaranteed chance to complete the thought before the system reasserts its own
   agenda — treating the *fact of interruption itself* as a signal worth one turn of attention, independent
   of whether the captured fragment happened to match anything.

**What this does not claim:** this is not a 100% recall mechanism against mid-word cutoff — an ASR engine
that finalizes before the injury word is spoken cannot be fixed by anything running after it. This is a named
instance of `AI-USE-CASE-CARD.md` F1's existing residual risk (novel/incomplete phrasing evading L1 and L2),
not a new one and not one this document claims to close. What *is* guaranteed: the system never treats an
interruption as noise to discard, and never proceeds past an unexplained barge-in on its own agenda without
giving the caller one explicit, structured chance to say it again.

**The open re-prompt is not a separate, uncounted loop.** It consumes one attempt on the same shared retry
ladder defined in §7 — if the caller doesn't respond to *"go ahead, what were you saying?"* either, that
counts toward the same two-attempt ceiling as any other no-input event on that turn. There is exactly one
retry mechanism in this system, not a barge-in-specific one layered on top.

---

## 7. No-input / no-match retry ceiling

**Marco's addition: name the ceiling and what happens at it, since an IVR that loops on no-match is the most
common way these systems become unusable, and `D13` means the fallback must be escalation, not a hang-up.**

**Ceiling: two consecutive no-input/no-match events on the same slot or clarifying question.** This number is
not new — `PROBLEM-FRAMING.md`'s escalation route 3 already fixed it ("two consecutive no-match/no-input").
What was missing, and what this section adds, is the concrete ladder shape and the exact behavior at the
ceiling.

**Ladder:**

1. **Attempt 1** — the slot's canonical elicitation prompt (`SLOT-DESIGN.md`'s per-slot table).
2. No-input or no-match → **Attempt 2** — a *rephrased or simplified* reprompt, never a verbatim repeat. A
   verbatim repeat of a prompt the caller already failed to answer is a known bad IVR pattern and is
   explicitly excluded here. For the three DTMF-eligible slots (`SLOT-DESIGN.md` §4), attempt 2 proactively
   offers the keypad alternative rather than repeating the same speech prompt differently worded.
3. No-input or no-match again → **ceiling reached** → escalation route 3 ("Capability"), not a third attempt
   and not a hang-up. Scripted: *"I'm having trouble catching that — let me connect you with someone who
   can help."* Full context captured so far transfers with the call, same pattern as §5's injury handoff.

**Scope: per slot or per clarifying question, not a whole-call global counter.** A caller who struggles twice
reading out a police report number but then completes the remaining eight slots cleanly has not demonstrated
a systemic problem — escalating the whole call on that basis would be a false-escalation-rate failure
(`PROBLEM-FRAMING.md`'s containment design, `D13`). Total no-match count across a call is still tracked as a
soft, non-gating observability signal — it is what `SUCCESS-METRICS.md`'s existing "Repair success rate ≥
0.80" target measures — but it is a reported metric, not a second hidden ceiling.

**Barge-in-originated turns are not exempt and not penalized.** Per §6.2, a barge-in that yields an
unintelligible or unclassifiable transcript counts as a no-match on this same ladder, using the same two-step
shape — there is no separate barge-in retry budget, by design, so the barge-in repair flow in §6.2 cannot
become its own unbounded loop layered on top of this one.

**Hang-up is never a fallback state anywhere in this design.** Every ladder in this system terminates in
exactly one of two outcomes: successful capture/resolution, or escalation with context handed over. This is
restated as an explicit negative rule because it is the property an IVR most easily loses by accident — a
missing `else` branch that falls through to silence is a design defect under this policy, not an edge case.

---

## 8. Escalation-trigger enumeration

Every trigger that can end a turn in a human handoff, mapped to `PROBLEM-FRAMING.md`'s four escalation
routes, so nothing here adds a route or a trigger silently.

| Trigger | Route | Source |
|---|---|---|
| L1 deterministic injury/fatality match | 1 — Safety | `D12`, §5 |
| L2 recall-biased safety classification (merged router call) | 1 — Safety | `ADR-004`, §5 |
| L3 — hard "agent"/"human" barge-in, any state | 2 — Caller request | `PROBLEM-FRAMING.md`, always reachable including mid-barge-in-repair (§6) |
| Out-of-corpus `CoverageQuestion` (RAG returns nothing relevant) | 3 — Capability | §2 step 5 |
| Out-of-scope intent (§`INTENT-TAXONOMY.md` §2.2) | 3 — Capability | Declined, not attempted |
| Ambiguity unresolved after one repair attempt | 3 — Capability | `INTENT-TAXONOMY.md` §3 |
| Two consecutive no-input/no-match on the same slot/question | 3 — Capability | §7 |
| `CoverageQuestion` eligibility/amount sub-question | 3 — Capability (immediate, no attempt at generation) | §2 step 4 |
| `UpdateContactInfo` confirmation failed twice | 3 — Capability (tighter ladder, one retry not two) | §4, `SLOT-DESIGN.md` §2 |
| Sustained low ASR/intent confidence across turns | 4 — Confidence | `PROBLEM-FRAMING.md` |
| Groundedness self-check failure on a coverage answer | 4 — Confidence | `PROBLEM-FRAMING.md`, `AI-USE-CASE-CARD.md` F3 |

**No trigger in this table may be tuned to improve containment optics at the cost of recall (`D13`).**
Routes 1 and 2 are non-negotiable by construction (deterministic pre-node, always-on barge-in intent); routes
3 and 4 are the only ones with any judgment involved, and `PROBLEM-FRAMING.md`'s false-escalation-rate metric
is what keeps them from drifting toward over-escalation, not under-escalation — the asymmetry is deliberate.
