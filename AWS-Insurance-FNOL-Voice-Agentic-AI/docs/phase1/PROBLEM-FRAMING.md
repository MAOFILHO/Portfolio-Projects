# Problem Framing — Phase 1

## The scenario

**Example Mutual** — an explicitly fictional US personal-auto carrier — runs a voice line for policyholders
reporting and asking about auto claims. Today every call reaches a human FNOL specialist, including the large
share that are short status checks and coverage questions. The specialists' scarce skill is judgement on
messy, distressed, ambiguous calls; it is being spent on lookups.

> **"Example Mutual" is a deliberately synthetic carrier name**, chosen so this project cannot be mistaken for
> or confused with a real insurer. All policy wordings, policyholders, vehicles and claims are synthetic. No
> real carrier's branding, terminology, rates or documents are used.

The prototype puts an AI agent in front of that line. It answers the routine calls end-to-end, captures a
complete and validated First Notice of Loss when there is one, and hands the rest to a human **quickly and
with context already gathered**.

### Why FNOL, and why voice

FNOL is chosen because it is genuinely hard in ways that exercise the whole stack rather than a happy path:

- **Callers narrate, they do not fill forms.** They give the date twice in different words, mention the other driver's insurer before their own policy number, and volunteer things nobody asked for. Slot filling must track what is still missing in graph state rather than interrogating linearly.
- **The branch structure is real.** A comprehensive claim asks different questions than a collision; a disabling-damage claim opens a towing path; any injury changes everything immediately.
- **Grounding matters and is checkable.** Coverage and entitlement questions have unambiguous answers in the policy document, so groundedness can be measured rather than asserted.
- **The caller may be distressed.** Someone standing on a roadside is the worst possible audience for a chatty, interrogating, or slow agent. This is what makes the 1,800 ms p95 latency budget — measured **Lex STT completion → Polly audio stream start** (constraint 14; excludes telephony wire delay and audio playout, both of which sit outside this window and add to what the caller actually feels) — and barge-in a correctness requirement, not polish.

Scope is **P&C personal auto only**. Health and life claims are out of scope.

---

## The six intents

Exactly six. Additions are out-of-scope future work (see Non-goals), because more intents dilute eval quality
and threaten the cost ceiling.

### 1 · `FileAutoClaim` — file a new auto claim

The slot-filling showcase, and the only intent that writes a claim record.

**Safety precedes data.** The graph enters `safety_check` before any collection, and a mandatory-escalation
trigger (intent 6) fires from there or from any later state.

| Slot | Type | Required | Notes |
|---|---|---|---|
| `policy_number` | `^PY\d{4}$` | ✅ | Verified against the mock policy store |
| `loss_datetime` | datetime | ✅ | Fuzzy parsing — "yesterday about 5:30", "last Tuesday evening" |
| `loss_location` | free text | ✅ | City / ZIP / intersection / address; precision not demanded |
| `insured_vehicle` | enum from policy | ✅ | Disambiguated if the policy lists more than one |
| `loss_type` | enum | ✅ | Collision · Comprehensive · Theft · Vandalism · Weather · Liability |
| `damage_description` | free text | ✅ | Also drives the damage-extent classification |
| `injuries_present` | bool | ✅ | **Any affirmative routes to intent 6 immediately** |
| `driver_name` | free text | ✅ | Plus `relationship_to_insured`, default "Self" |
| `police_report_filed` | bool | ✅ | |
| `police_report_number` | `^\d{4}-\d{4}-\d{3}$` | conditional | Required only if `police_report_filed` |
| `other_party_involved` | bool | ✅ | Name and insurer captured if present |

**Success:** a claim record written with all required slots populated and validated, a speakable claim number
read back and confirmed, and a caller who was asked one question at a time.

**Soft flags recorded for humans, never spoken to the caller and never acted on during the call:** late
reporting, absent police report on a multi-party loss, vague description, damage inconsistent with stated
loss type.

### 2 · `CheckClaimStatus` — check an existing claim

Tool call into the mock claims system. Slots: `claim_number` **or** `policy_number` (either suffices;
policy number resolves to the most recent open claim, disambiguating if several).

**Success:** current status and next expected step stated accurately from the tool result, with no invented
detail about timing or outcome.

### 3 · `CoverageQuestion` — coverage question

RAG against synthetic policy wordings. **The primary groundedness eval target.** Slots: `policy_number`,
plus a free-text `coverage_topic`.

**Success:** an answer traceable to a retrieved passage, correct per the ground-truth annotation, that
declines rather than guesses when the corpus does not cover the question. **An honest "I don't have that in
your policy — let me get you to someone who does" is a success, not a failure.**

### 4 · `RentalTowingEntitlement` — rental / towing entitlement

The compound case: RAG **plus** a tool call. Slots: `entitlement_type` (rental | towing), `policy_number`,
optional `claim_number`.

Requires reading the entitlement from the policy *and* checking claim state, because the answer depends on
both ("your policy includes rental at $40/day for 30 days, and your claim is approved, so it's available
now" versus "…but your claim is still under review, so it isn't active yet").

**Success:** both sources consulted, the conjunction reasoned correctly, and the limit and duration stated
accurately. Answering from the policy alone while ignoring claim state is a **failure even if the coverage
statement is true**.

The towing branch also consumes the damage-extent classification: **Disabling damage ⇒ towing applies.**

### 5 · `UpdateContactInfo` — update contact information

The only other write path. Slots: `policy_number`, `field` (phone | email | mailing address), `new_value`.

**Confirmation policy is explicit and mandatory:** the agent reads the new value back, character-grouped for
phone and email, and writes only on unambiguous affirmative confirmation. No write on an ambiguous, partial,
or inferred yes. A failed confirmation loops once, then offers a human.

**Success:** the record changed exactly as confirmed, or no change at all. A silent partial write is the
worst outcome in the entire system and is treated as a **critical defect**, not a missed target.

### 6 · `InjuryEscalation` — injury or fatality mentioned

**Immediate, hard-coded, from any state. No negotiation, no continued slot filling, no LLM discretion.**

Fires on any indication of injury or death to any party, on the KABCO scale at **K** (fatal) or **A**
(suspected serious). B/C (minor/possible) are captured and flagged but do not force escalation — that
distinction is deliberate and is itself an eval target.

Mechanically this is **not a classifier decision**. Detection runs as a deterministic pre-node on every turn,
before the model sees the input, and its outcome is not overridable by anything downstream. It is also
reachable by the caller directly at any time via the hard "agent" barge-in intent.

**Success:** transfer initiated within one turn of the trigger, safety guidance given first ("if anyone needs
medical help, please hang up and call 911"), and full captured context handed to the human. **A completed
escalation is a successful call, not a containment failure.**

---

## Escalation policy

Four routes to a human, in priority order:

| # | Trigger | Behaviour |
|---|---|---|
| 1 | **Safety** — injury/fatality (K or A), or caller in an unsafe location | Immediate. Deterministic. Not overridable. 911 guidance first |
| 2 | **Caller request** — the hard "agent" barge-in intent, from any state, any time | Immediate, no gatekeeping, no "let me try first" |
| 3 | **Capability** — out-of-corpus question, out-of-scope intent, ambiguity unresolved after one repair attempt, or two consecutive no-match/no-input | Graceful, with context handed over |
| 4 | **Confidence** — low ASR or intent confidence sustained across turns, or a groundedness self-check failure on a coverage answer | Graceful; prefer transferring over answering unsupported |

Non-negotiable properties: a human is reachable **from every state**, escalation is **never gated behind
completing slot filling**, and the agent **never argues with a caller who asks for a person**. Everything
captured so far transfers with the call — a caller who repeats themselves to the human has been failed even
if the transfer itself was correct.

Outside business hours, routes 1 and 2 take a callback commitment with the captured context, and say so
plainly rather than implying someone is about to pick up.

---

## Containment — defined so it cannot be gamed

Naive containment (calls not transferred ÷ total calls) rewards refusing to escalate. That is a safety
hazard, so the metric is decomposed. See `SUCCESS-METRICS.md` for measurement detail.

- **Mandatory escalations (routes 1 and 2) are excluded from the containment denominator entirely.** A correctly escalated injury call is a *success*, and counting it against containment would create pressure to suppress the behaviour the system exists to guarantee.
- **Appropriate containment** = resolved without transfer ÷ calls where transfer was *not* warranted.
- **Safety-critical escalation recall must be 100%.** It is a hard gate. No containment number, however good, compensates for a single missed injury escalation.
- **False-escalation rate is tracked in the opposite direction**, so the system cannot buy safety by transferring everything.

**Containment target: ≥65% of non-mandatory calls** — a target for this prototype, not a measured result and
not an industry benchmark.

---

## Non-goals

Stated so scope creep is visible, and so the demo is not judged against things it deliberately does not do.

**The agent does not adjudicate.** Repo 7's authority matrix puts an FNOL specialist at **$0 settlement
authority, a $5,000 reserve ceiling, and no ability to deny a claim**. The agent inherits exactly that. It
never approves, denies, values, or commits to paying anything. It captures, validates, informs from the
policy document, and routes. **AI advises; a licensed human decides.**

Also out of scope:

| Not doing | Why |
|---|---|
| Coverage *decisions* (as opposed to reading coverage terms aloud) | Requires licensed authority the agent does not have |
| Settlement amounts, reserves, total-loss determinations | Same |
| Fraud decisions | Intake-time signals are soft flags for humans. The agent never accuses, never mentions fraud to a caller, and never changes its behaviour based on a flag |
| Identity verification beyond policy-number match | Real KBA/OTP is a security design problem of its own. The prototype states this limitation openly rather than shipping a demo-grade OTP with a bypass |
| Health, life, commercial auto, property | P&C personal auto only |
| Outbound calling, SMS, chat, email | Inbound voice only; the DID is inbound-only |
| Languages other than en-US | Adding locales multiplies eval surface with no architectural gain |
| Payments, premium quotes, policy changes beyond contact info | Different risk class, different authority |
| Call recording | Banned by constraint 18 and enforced in CI |
| Document/photo intake | No MMS path; damage assessment from images is out of scope |

**Explicitly deferred future work** (not built, not implied, not in the README as if present): additional
intents such as roadside dispatch, glass-only claims, adding a vehicle or driver; multilingual support;
agent-assist for the human receiving the transfer; and proactive status callbacks.

---

## What "working" means

Restated as one sentence, because the metrics in `SUCCESS-METRICS.md` exist to measure this and nothing else:

> A distressed caller reaches an agent that discloses it is AI, checks their safety first, asks one question
> at a time, tracks what they have already said, answers coverage questions only from their actual policy,
> completes a validated claim or hands them to a person **within 1,800 ms per turn and under $25 a month** —
> and never, under any circumstances, fails to escalate an injury.
