# AI Use-Case Card — Voice FNOL Intake Agent

**System:** AWS-Insurance-FNOL-Voice-Agentic-AI
**Version:** pre-release (Phase 1 of 13)
**Owner:** Marcos Oliveira
**Date:** 2026-08-11
**Status:** Prototype. **Not deployed. Never to be used with real policyholders or real claims data.**

---

## Intended use

An inbound-voice agent that takes First Notice of Loss for **fictional** P&C personal-auto claims, answers
coverage and entitlement questions from a synthetic policy corpus, checks claim status, updates contact
information, and escalates to a human when appropriate.

**Its actual purpose is to be a portfolio demonstration** of an end-to-end agentic voice system on AWS —
telephony, turn management, grounded retrieval, tool use, guardrails, evaluation, observability and IaC — at
minimal cost. It is architecturally honest at small scale, not production-hardened at any scale.

### Intended users

| User | Interaction |
|---|---|
| Reviewers, interviewers, engineers evaluating this work | Call the DID or drive the simulator |
| The author | Development and demonstration |
| A simulated "human FNOL specialist" | Receives escalated calls at the CCP softphone during demos |

**There are no real policyholders.** All callers are the author or invited reviewers, calling about synthetic
policies belonging to synthetic people.

---

## Out-of-scope uses

Using this system in any of the following ways is a misuse, and it is not built to withstand them:

- **With real policyholders, real claims, or real PII.** No production authentication, no licensed oversight, no regulatory compliance review, no carrier integration.
- **As a system of record.** The mock claims store is synthetic and destroyed by `make destroy`.
- **To make or communicate any coverage, liability, settlement, valuation, denial or fraud decision.** The agent has no authority to decide anything (see Non-goals in `PROBLEM-FRAMING.md`).
- **As legal, insurance, medical or financial advice.** Coverage passages are read from a *synthetic* document that resembles a real policy but governs nothing.
- **As an emergency service.** The agent tells callers to hang up and call 911; it cannot dispatch help, and no part of it is reliable enough to sit between a person and emergency services.
- **Health, life, commercial auto or property claims**, or any locale other than en-US.
- **Any adjudication, triage or routing of real people's claims**, including as a "human-in-the-loop assistant" — the human oversight modelled here is simulated.
- Repurposing the components to build the above without redoing the responsible-AI work from Phase 7 onward.

---

## Data

**All data is synthetic.** Policy wordings, declarations pages, policyholders, vehicles, claims and call
transcripts are authored or generated for this project. No real customer, policy or vehicle data enters it.
See `docs/phase0/DOMAIN-ARTIFACTS.md` for the attestation and `docs/phase0/SECURITY-FINDINGS.md` for three
artifacts excluded by name from the upstream sources.

Caller audio is transcribed by Lex. **Call recording is disabled** and enforced by a CI check. Transcripts
are PII-redacted **before** persistence or logging — the unredacted transcript is never written anywhere,
not even transiently.

One deliberate deviation from the inherited PII taxonomy: **loss date and time are not redacted.** They are
the single most important field the system captures, and blanket-redacting them would destroy the record the
system exists to create. VIN, licence plate, policy number and claim number are *added* as redaction targets.

---

## Failure modes

Known and expected. Ordered by severity, with the mitigation and the residual risk stated honestly.

| # | Failure mode | Severity | Mitigation | Residual risk |
|---|---|---|---|---|
| F1 | **Missed injury escalation** — injury mentioned, escalation does not fire | **Critical** | Deterministic pre-node on every turn, before the model sees input; not overridable downstream; 100% recall is a hard CI gate | Novel phrasings ("my neck feels funny") may evade lexical detection. **This is the system's most serious residual risk and is stated as such rather than resolved.** Phase 7 red-teams it directly |
| F2 | **Silent partial write** on contact update — record half-changed | **Critical** | Mandatory read-back, write only on unambiguous confirmation, single atomic write | Treated as a defect class, not a tuning target |
| F3 | **Hallucinated coverage** — a limit, deductible or entitlement not in the policy | High | RAG with groundedness check; Guardrails contextual grounding; decline-and-transfer preferred over answering | Judge-based groundedness scoring is a **proxy, not ground truth**. Some ungrounded answers will pass |
| F4 | **Confident wrong answer on an out-of-corpus question** | High | Explicit "not in your policy" path; abstention is scored as success | Over-abstention degrades usefulness; the trade-off is tuned against evals, not assumed |
| F5 | **Prompt injection via retrieved documents or tool responses** | High | Injection screening on both; structured output via tool use rather than string parsing | Screening is heuristic. Upstream repos parsed decisions with `if "high priority" in response` — precisely what is avoided here |
| F6 | **Latency breach** — turn exceeds 1,800 ms p95, caller hears dead air | High | Interim audio fillers, streaming, small deployment package; cold-start measured in Phase 9 | Cold starts on a low-traffic demo line are the hard case; provisioned concurrency is cost-gated |
| F7 | **ASR error on critical identifiers** — policy number, claim number, phone digits | Medium | Voice-safe alphabet excluding confusable characters, check character, read-back, DTMF fallback | Accent and noise variation is under-tested; Phase 7 includes a bias check across name/accent/dialect variation |
| F8 | **Slot loss across turns** — caller must repeat themselves | Medium | Durable state checkpointed to DynamoDB keyed on the Connect contact ID | Barge-in mid-write is an untested edge |
| F9 | **Escalating too eagerly** — usable calls dumped on a human | Medium | False-escalation rate tracked opposite containment | Deliberately biased toward over-escalation: a wasted transfer is far cheaper than a missed injury |
| F10 | **Denial of wallet** — runaway spend | Medium | Banned-service list, cost gate, hard $25 budget alarm from the first provisioning phase, simulator-first testing | A single misconfigured always-on resource can breach a $25 ceiling in hours |
| F11 | **Guardrail false positive** blocking a legitimate distressed caller | Medium | Tuned against real utterances; interventions logged and dashboarded | An accident description can legitimately contain violent language. Tuning is imperfect |
| F12 | **Fraud flag leaking into caller-facing speech** | Medium | Flags are write-only to the audit record, never in the response path | Enforced by design and test, not by model behaviour |

---

## Human oversight model

**Simulated, and labelled as such.** Real oversight would require licensed adjusters, a QA function and a
regulatory framework, none of which exists here.

- **In-call:** every path to a human is always available; mandatory escalations are deterministic. The agent captures and validates but **decides nothing** — the authority matrix gives it $0 settlement authority and no ability to deny.
- **Post-call:** every conversation persists a redacted transcript, a turn-by-turn reasoning trace, every tool call with arguments and results, guardrail interventions, and cost — reviewable in the dashboard. Traceability is a first-class output, not a debugging afterthought.
- **Development-time:** an eval harness with ≥60 labelled golden conversations gates every change in CI; a human-review sample accompanies LLM-as-judge scoring, because **judge scores are proxies and never ground truth**.
- **Kill switches:** OpenFeature flags gate model tier, RAG, agentic tools and prompt versions, each taking effect on the next turn. The number can be pointed at a known-good fallback flow mid-demo if a deploy breaks.

### What oversight this prototype does *not* have

No licensed adjuster reviews anything. No QA sampling by trained staff. No complaint or appeal channel. No
regulatory filing, state DOI review, or bad-faith-exposure analysis — even though repo 7's model showed
`bad_faith_prevention_notes` as a real concept, so the *shape* of the gap is understood. No accessibility
audit for callers with speech differences or hearing loss, which is a genuine equity gap in a voice-only
system. No red-team review by anyone other than the author.

---

## Transparency

- **Explicit AI disclosure in the greeting**, before anything is collected. No implication of a human, no human name, no "let me check that for you" framing that suggests a person.
- On request, the agent states plainly that it is an automated system and offers a human immediately.
- Sensitive-information warning in the greeting, as the upstream samples do: callers are told not to give SSNs, card numbers or medical details.
- **No invented metrics or capabilities in any documentation.** Every number in `SUCCESS-METRICS.md` is labelled as a target, a gate, or an observed measurement, and unmeasured targets are marked as such.

---

## Review triggers

This card is revisited when any of the following occurs: an intent is added or removed; the escalation policy
changes; the model tier or router strategy changes; a new data source enters the corpus; Phase 7 red-teaming
finds a failure mode not listed above; or any real (non-synthetic) data is ever proposed for use — which would
require redoing this card from scratch rather than amending it.
