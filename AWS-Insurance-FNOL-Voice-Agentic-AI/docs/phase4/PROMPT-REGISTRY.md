# Prompt Registry — Phase 4

Every model-calling node's prompt, plus a structural decision this document makes explicit: **most spoken
lines in this system are never generated at all.** Slot elicitation (`SLOT-DESIGN.md`), retry reprompts,
confirmation read-backs, the injury escalation script (`DIALOGUE-POLICIES.md` §5), and the barge-in open
re-prompt (`DIALOGUE-POLICIES.md` §6.2) are fixed strings or deterministic template substitutions — not LLM
output. This isn't stated as a limitation; it's the load-bearing design decision behind §2's length
discipline, because a line that was never generative in the first place cannot pad itself.

**Two model-calling nodes exist. This registry covers both, and nothing else calls a model.**

---

## 1. Nodes

### 1.1 Merged router + L2 safety classification (`ADR-004`)

Fixed to `us.amazon.nova-micro-v1:0`, forced tool-use, never flag-controlled. Runs every turn that L1 didn't
already terminate (`DIALOGUE-POLICIES.md` §1, step 2).

**Tool schema (`classify_turn`, all fields required — forced tool-use means the call fails validation, not
silently omits, if any required field is missing):**

```json
{
  "name": "classify_turn",
  "description": "Classify this caller turn for routing and safety.",
  "input_schema": {
    "type": "object",
    "required": ["safety_flag", "intent", "intent_confidence", "coverage_question_type"],
    "properties": {
      "safety_flag": {
        "type": "boolean",
        "description": "true if this turn contains any indication of injury, medical distress, or fatality to any party — err toward true on ambiguity, per L2's recall-biased design (D15)."
      },
      "intent": {
        "type": "string",
        "enum": ["FileAutoClaim", "CheckClaimStatus", "CoverageQuestion", "RentalTowingEntitlement", "UpdateContactInfo", "OutOfScope", "Ambiguous"]
      },
      "intent_confidence": { "type": "number", "minimum": 0, "maximum": 1 },
      "coverage_question_type": {
        "type": "string",
        "enum": ["election_fact_mandatory", "election_fact_optional", "eligibility_amount", "not_applicable"],
        "description": "Required only when intent is CoverageQuestion and coverage_topic is already filled; otherwise 'not_applicable'. See DIALOGUE-POLICIES.md §2."
      }
    }
  }
}
```

**System prompt:**

> You classify one caller turn in a P&C auto insurance FNOL call. You do not generate any response the
> caller will hear — you only call `classify_turn`. Set `safety_flag` to true on any hint of injury, pain,
> unconsciousness, or medical distress to anyone, including indirect or self-negating phrasing ("I'm fine but
> he's not moving") — when in doubt, true. Classify `intent` from the caller's turn and prior context. If the
> turn mixes two intents, set `intent` to the one requiring immediate attention and note the confidence
> accordingly — the calling graph handles the deferred second intent, not you. If `coverage_topic` has been
> filled this call, classify whether the question is about *whether coverage exists* (election-fact) for a
> *mandatory* coverage (same for every policyholder) or an *optional* one (varies by policyholder), or
> whether it asks *how much or whether payment will occur* (eligibility_amount). Call the tool. Do not
> produce any other output.

**Why no length discipline applies here:** this node never produces caller-facing text — its only output is
a structured tool call, so §2's discipline is moot for this node by construction, not by omission.

### 1.2 Generation — feature-flagged tier (`ADR-004`)

Behind the generation-tier flag, defaulting to `us.amazon.nova-lite-v1:0`. **Invoked for exactly two cases —
nothing else in this system calls this node.** Both are documented in `DIALOGUE-POLICIES.md` (§2, §3) as the
two places a single retrieved-or-tooled fact isn't enough on its own and genuine synthesis is required.

1. `CoverageQuestion` — election-fact answer synthesis (mandatory: RAG only in context; optional: RAG + tool
   result in context).
2. `RentalTowingEntitlement` — compound synthesis (RAG + tool result, both required in context per
   `DIALOGUE-POLICIES.md` §3 step 3).

See §3 for both prompts, each carrying its length constraint inline rather than as a separate policy applied
after the fact.

---

## 2. Response-length discipline

**Motivating case, stated plainly rather than left as an implicit prompting habit:** during pre-flight
testing, Nova Micro padded a one-word answer into a full sentence unprompted. Every unnecessary clause in a
spoken response costs real Polly synthesis time, which is real time inside the 1,800 ms p95 turn-latency
budget (`CLAUDE.md`'s voice turn-latency constraint) — a generation call that returns fast but produces a
long response has not actually protected the budget, because synthesis time is downstream of response length,
not independent of it. The exact words-per-millisecond relationship is **not asserted here as a verified
number** — that's a Phase 9 measurement — but the qualitative relationship (shorter response ⇒ less synthesis
time ⇒ more headroom) is not in question and is enough to design against now.

### 2.1 Tolerance by turn type

Covers every spoken line in the system, not only the two generative cases, because a verbose *template* is
just as much a latency and cognitive-load cost as a verbose generation — the enforcement mechanism differs,
the discipline does not.

| Turn type | Tolerance | Generated or fixed/templated | Length target | Why |
|---|---|---|---|---|
| Slot elicitation (initial ask) | **Tight** | Fixed string (`SLOT-DESIGN.md`) | ≤1 short sentence | No discretion needed |
| Slot confirmation / value read-back | **Tight** | Templated substitution | Value + "is that right?", ≤1 sentence | Longer makes it *harder*, not easier, to catch a misparse by ear |
| Retry reprompt (ladder attempt 2) | **Tight** | Fixed string (`DIALOGUE-POLICIES.md` §7) | ≤1 short sentence | Caller already failed once — brevity reduces cognitive load, not just latency |
| Barge-in open re-prompt | **Tight** | Fixed string (`DIALOGUE-POLICIES.md` §6.2) | ≤1 short sentence | Same ladder as reprompts |
| Injury escalation script | **Tight** (fixed, not generated) | Fixed string (`DIALOGUE-POLICIES.md` §5) | 2 short sentences total | No LLM discretion by design — length is fixed because content is fixed |
| `UpdateContactInfo` confirmation read-back | **Tight** | Templated, character-grouped | ≤1 sentence | Same reasoning as slot confirmation, higher stakes (write gate) |
| Ambiguity clarifying question | **Tight** | Generated, constrained | 1 sentence, 1 question | One targeted question, not an essay restating the ambiguity |
| `CoverageQuestion` eligibility/amount deflection | **Tight** | Fixed string (`DIALOGUE-POLICIES.md` §2 step 4) | 1 sentence | Scripted; no variation intended |
| `CoverageQuestion` election-fact answer | **Relaxed** | Generated | 1–2 sentences | Caller asked a real question; the answer plus one supporting clause from the retrieved passage is the substance they called for |
| `CoverageQuestion` abstention ("not in your policy") | **Tight** | Fixed template | 1 sentence | Fixed decline-and-transfer line |
| `RentalTowingEntitlement` compound answer | **Relaxed** | Generated | 2–3 sentences | Two facts (policy terms + claim state) must be conjoined coherently — collapsing this to one clipped sentence risks exactly the "answered from one source only" failure `PROBLEM-FRAMING.md` names |
| `FileAutoClaim` close-out summary | **Relaxed** | Templated structured recap | 3–5 short sentences (one per major field group) | Caller must be able to catch an error in an 11-slot record before it's written — brevity here trades accuracy for speed, the wrong trade on a write path |

### 2.2 Enforcement mechanism

- **Templated turns** (the majority): reviewed once at authoring time — this document and `SLOT-DESIGN.md`
  are the enforcement. No runtime discretion exists to drift, so no runtime check is needed.
- **Generated turns** (only the two §1.2 cases plus the constrained ambiguity clarifier): three layers, not
  one, because a single "please be brief" instruction is exactly what failed in the motivating pre-flight
  case —
  1. An explicit length instruction inline in the system prompt (§3), stating the sentence-count target and
     naming the failure to avoid ("do not restate the question, do not add an unsolicited caveat").
  2. A conservative `max_tokens` cap set per prompt (§3) as a hard ceiling, not a suggestion — engineering
     targets stated as such, not verified numbers, pending real-token validation.
  3. A length dimension added to the Phase 6 eval harness (word count and estimated synthesis duration per
     response, checked against budget headroom) — so length discipline is a **measured** eval dimension going
     forward, not a one-time prompting choice trusted to hold.

---

## 3. Generation-node prompts

### 3.1 `CoverageQuestion` election-fact synthesis

**Context provided:** retrieved policy-wording passage(s); if `coverage_question_type == election_fact_optional`,
also the policyholder's `elected_benefits` tool result (`DIALOGUE-POLICIES.md` §2 step 3).

**System prompt:**

> Answer the caller's coverage question using only the policy text and, if provided, their specific election
> record below. State the answer first, in one sentence. You may add one short supporting clause from the
> retrieved text if it adds real information (a limit, a condition) — otherwise stop after the first
> sentence. Never exceed two sentences. Do not restate the caller's question. Do not add a disclaimer,
> caveat, or "please note" unless the policy text itself states a condition the caller needs to know. If the
> retrieved text does not clearly answer the question, say exactly: "I don't have that in your policy — let
> me get you to someone who does." Never guess.

**Suggested cap:** `max_tokens` ≈ 120 (engineering target, not yet validated against real token counts for a
two-sentence spoken answer — validation is criterion 12's optional closing step).

### 3.2 `RentalTowingEntitlement` compound synthesis

**Context provided:** retrieved endorsement terms (`endorsements.md`); the tool result for this claim
(`days_in_repair` for rental, active-claim status for towing).

**System prompt:**

> Answer using both the policy terms and the claim status below — both are required, and an answer that uses
> only one of them is wrong even if it sounds correct. State whether the entitlement applies, then state the
> concrete number that matters to the caller right now (days/dollars remaining for rental; covered or not for
> towing). Two to three sentences. Do not explain the endorsement's general mechanics beyond what answers this
> caller's situation — they asked about their claim, not the product in the abstract. If the claim status
> tool call did not return a resolvable claim, say so plainly and state the policy terms only, without
> implying the entitlement is currently active.

**Suggested cap:** `max_tokens` ≈ 200 (engineering target, same validation status as §3.1).

### 3.3 Ambiguity clarifying question (constrained generation)

**Context provided:** the two (or more) candidate intents/slot interpretations from the merged router call.

**System prompt:**

> The caller's last turn is ambiguous between the intents listed below. Ask exactly one short question that
> would resolve the ambiguity. One sentence. Do not list the possibilities to the caller verbatim — ask
> naturally, the way a person would.

**Suggested cap:** `max_tokens` ≈ 60.

---

## 4. What this registry deliberately does not contain

No prompt for Guardrails — `ApplyGuardrail` is a classification API call, not a prompted generation
(`ADR-010`); it has no prompt to register. No prompt for the injury escalation script, the barge-in
re-prompt, or any slot elicitation/confirmation line — all fixed strings or templates, specified in
`DIALOGUE-POLICIES.md` and `SLOT-DESIGN.md`, not here. Keeping the boundary explicit (generated vs.
templated) is itself the length-discipline mechanism §2 describes — this document would be the wrong place
to also hold every fixed string, since fixed strings need authoring review, not a prompt spec.
