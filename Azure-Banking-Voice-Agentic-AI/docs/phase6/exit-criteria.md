# Phase 6 — Observability: design and exit criteria

> **NOT APPROVED. Phase 6 has not begun and does not begin on this document.**
>
> This file is the written output of a `/grill-with-docs` design session on 2026-09-11. Marco
> settled 19 design questions across three rounds. The last message of that session was
> "Enough questions! Let's run Phase 6!", and the answer to it is the same answer
> `PROJECT_STATE.md` next-action 0 already carried: **Phase 5's exit is not met**, so no phase
> begins. `CLAUDE.md`: "No phase begins without written exit criteria from the prior phase and
> Marco's explicit approval."
>
> **Marco's own Q1 answer in this same session was "Design-only."** This document is that.
>
> | approval | state |
> |---|---|
> | The 19 design decisions below | **Given 2026-09-11**, question by question |
> | Begin Phase 6 | **NOT given** |
> | `APPROVED: Phase 6` for billable resources | **NOT given** |
> | **B2 widening** (a named-constraint change) | **NOT given** — see "Constraint changes" below |
> | Phase 5 sign-off | **NOT given** — Phase 5's exit is not met |

**Written before the work, not reconstructed after it.** No spec issue exists yet; `#43` is Phase 5's
and this is not a sub-issue of it.

---

## Entry conditions — updated 2026-09-12, four of eight still unmet

| condition | state |
|---|---|
| Phase 5's exit criteria written | **Satisfied** — `docs/phase5/exit-criteria.md`, approved 2026-09-11 |
| **Phase 5's exit criteria met** | **Satisfied, 2026-09-12** — all 18 tickets closed; two met with a stated limit (B5 frozen on the real-call pool only; the acceptance call's evidence is scattered across the day, not one continuous run — both Marco's explicit call). `docs/phase5/exit-check.md` |
| **Marco's sign-off on Phase 5** | **Still owed** — distinct from the exit being met |
| **Marco's approval to begin Phase 6** | **Still owed** — `APPROVED: Phase 6` (typed 2026-09-12) covers only the billable-resource gate, not this |
| **Open item 16 settled** (`/research`) | **NOT settled** — hard blocker on one ticket, see criterion 3 |
| **Open item 15 settled** (`/research`) | **NOT settled** |
| **B2 widening signed off** | **NOT given** — a named constraint does not move without it |
| Phases 4 and 5 reviewed (`git log e42c063..HEAD`) | **Still NOT done** — the 2026-09-12 `/code-review` covered only `a7e06d1..HEAD` (17 of the 42 commits since `e42c063`); the other 25 remain unreviewed |

**Four of eight entry conditions are unmet.** This is recorded as a list of blockers, not as a
checklist to be worked around.

---

## What Phase 6 is, in one paragraph

The relay records what happens inside a call and sends it to Application Insights, so that one call
can be read end to end afterwards. It records nothing the caller said, nothing that identifies the
caller, and never the PIN. Nothing it records governs anything: every named constraint holds with
telemetry entirely absent.

---

## The 19 settled decisions

Numbered as they were asked, so the reasoning behind each is findable in the session that produced
it. Every one carries Marco's answer, given 2026-09-11.

### Scope and sequencing

**D1 — Phase 6 is designed now and begins later.** The Phase 5 acceptance call is a one-shot,
human-in-the-loop event answering four wire-format questions no document can answer. Instrumenting
the image under acceptance test confounds that test. The four open questions are about frame
*contents*, and a log line captures a frame's contents as well as a span does. If the acceptance
call needs more evidence, the fix is more log lines on the DTMF and injection paths, not a telemetry
backend.

**D6 — Phase 6 does not fix `PROJECT_STATE.md` open item 1.** That item claims Phase 6
(Observability) is "its real fix" for the absent durable ACS-side call-diagnostics path. The claim is
wrong and is corrected in the same commit as this file. The OpenTelemetry Distro ingests via its own
endpoint authenticated by the resource's connection string, a mechanism entirely independent of
`Microsoft.Insights/diagnosticSettings` — which is exactly what failed in Phase 0
(`docs/handoffs/2026-08-27-phase1-logpath-resolved.md`). Phase 6 produces app-side traces from the
relay process. ACS-side call diagnostics are different data, from a different producer, over the
mechanism that already failed here once. Out of scope, and the open item keeps an accurate
description instead of a promised fix.

**D16 — Phase 6 makes its own call, and it is a smoke call nobody is grading.** Not a second
acceptance run. Riding Phase 5's acceptance call is what D1 rejected. A synthetic span proves
delivery and proves nothing about whether a real call produces the tree in D15. Roughly 2 minutes,
one authenticated intent, one refusal.

**The `CLAUDE.md` rule that an ARM 200 OK proves creation and not delivery binds this phase
twice over**: once for the Application Insights resource, once for every exporter that returns
success. Nothing here is described as verified until the destination table has been queried for rows
after a known emission.

### What must never appear

**D2 — "zero PII" is replaced by a named list of forbidden values.** The `PLAN.md` exit for this
phase reads "a full call traceable end-to-end with zero PII in any span". In a project whose
glossary says the Profile "never identifies anyone, because there is only one and no caller is ever
distinguished from another", that criterion is either vacuous or secretly means something specific.
It is made specific:

| value | status | why |
|---|---|---|
| The DTMF PIN | **Forbidden** | B2, unchanged |
| The caller's phone number | **Forbidden** | Genuinely identifying, and it arrives from ACS |
| Transcript text (caller or agent) | **Forbidden** | Everything the caller said |
| Balances and amounts | Permitted, **and not used** — see D15 | The profile is synthetic and the money is not real |
| Correlation and connection ids | **Permitted** | They are what makes a trace useful at all |

An unnamed "PII" criterion is the same empty claim as a percentile with no N.

**D7 — B2 widens in channels and in values, to the two scannable literals only.** The PIN and the
caller's phone number are both known literals and can be scanned for by value, which is how B2
already works. Transcript text cannot: you cannot scan for "anything the caller said", because you
do not know it in advance. Folding all three under one constraint id would give B2 an assertion that
cannot fail honestly. **Transcript text is protected by the D15 allowlist instead**, which is
falsifiable where a value scan is not.

**D8 — the caller's phone number is protected by never acquiring it. The scan is the net.** Verified
in the code 2026-09-11: `voice-agent/azbank_voice_agent/app.py` reads exactly two fields off the
`IncomingCall` event, `incomingCallContext` and `correlationId`, and logs only the second. The
number is never read.

> **The ACS webhook request body is the single highest-risk surface this phase has.** It carries the
> caller's number, and `incomingCallContext` is an opaque token that plausibly encodes it. If
> `opentelemetry-instrumentation-fastapi` captures request bodies by default, enabling it puts the
> caller's phone number into telemetry on the first call, with no code in this project ever having
> read it. This is `PROJECT_STATE.md` open item 16, and it stops being "settle it before Phase 6
> enables anything" and becomes a hard blocker on criterion 3.

**D9 — not emitting is the control; the redaction filter is the net.** The same shape the glossary
already settled for authorization: the auth gate is the only thing that decides, everything else is
defence in depth. The filter is a **deny-by-default attribute filter**, not a scrubber: it drops any
attribute whose key is not on the allowlist, without inspecting values. "Scrubbing" implies pattern
matching, and a regex scrubber has to be right about every attribute every future instrumentation
adds — the unbounded-list problem D7 refused. A regex can silently half-work; a key allowlist cannot.

**D11 — telemetry fails open, stated explicitly rather than left to the library's defaults.** B4
fails closed and is adversarially tested for it. Telemetry is a different kind of thing: an exporter
that blocks when the ingestion endpoint is slow sits on the turn path, damages B5, and in the worst
case drops a call in order to record that a call happened.

> **The corollary matters more than the decision: because telemetry fails open, no named constraint
> may be enforced by it.** B1, B2 and B4 all hold with telemetry entirely absent, and a test proves
> the relay runs correctly with the exporter unreachable.

### Shape

**D5 — one trace per call.** The root span opens when the media WebSocket opens and closes when it
closes, carrying the correlation id already threaded through the relay. Children per turn, per tool
call, per gate decision, per core-banking request. That mirrors the domain exactly: a call contains
turns, a turn contains tool calls, and a tool call is an attempt whose outcome is the gate's alone.

**D13 — the closed path is traced, and its two causes are distinguished in the span.** The glossary
is deliberate that budget-spent and ledger-unreadable are indistinguishable *to the caller*, because
telling them apart is a probing oracle for the condition that costs money. In telemetry they are
opposites: one is the brake working as designed, the other is a failure that needs waking someone
up. A span is not caller-visible, so the oracle argument does not reach it. **Recorded with its
reasoning because the inconsistency with the glossary is exactly what a later session tidies away
without knowing why it was there.**

**D14 — traces and metrics. Not log records, in this phase.** Traces are the deliverable. Metrics
cost almost nothing in volume and give B4's daily minute ledger and B5's turn latency a proper home,
rather than reconstructing them from spans every time. Log records are excluded: the relay has 48 log
lines, **only 6 of which carry the correlation id**, so exporting them would double the surface to
carry lines that mostly cannot be attributed to a call. The 6-of-48 gap is a later phase's decision,
not this one's. Note that B2's widened channel list still *covers* log records for scanning purposes
whether or not this phase exports them.

**D15 — the attribute allowlist.** This is D9's control and D7's criterion, so it is the phase's
central artifact and is written before any code. A deny-by-default filter with no list drops
everything.

| span | permitted attribute keys |
|---|---|
| **Call** | correlation id, connection id, auth state at end, end reason, turn count, duration, closed-path taken, closed-path cause |
| **Turn** | turn index, duration, agent spoke |
| **Tool call** | tool name, calling agent, gate decision, outcome class (one of the glossary's four: unknown account, declined, unavailable, malformed) |
| **Core banking** | HTTP method, route template, status code, duration |

Nothing carrying text the caller or the agent said. **Balances and amounts stay off the list despite
D2 permitting them** — permitted is not the same as useful, and every value not on the list is one
less thing to defend. Anything a future ticket wants added goes on by an explicit edit to this table,
which is the entire point of deny-by-default.

### Auth, testing, vocabulary, record

**D4 — workspace-based Application Insights in Canada Central.** Bound to
`workspace-rgazurebankingvoiceagenticai1D`, the only one of the three workspaces proven to deliver
rows; never `...aiCS`, stale since 2026-08-25, and never the `...aixC` orphan. Stays inside the
single-jurisdiction residency posture of ADR-001 and ADR-002.

> **The 5 GB free grant is shared, not additional.** It is per billing account per tier, and
> container logs already consume it through the same Log Analytics ingestion meter. Beyond it,
> `$2.76/GB` in `canadacentral`. App Insights data gets 90 days of free retention against 31 for a
> generic workspace. **R-08 is recomputed before provisioning, not after**, counting container-log
> volume and telemetry volume against one grant. `PROJECT_STATE.md` open item 8 (the Log Analytics
> auto-provision choice) is settled in the same decision rather than carried past a third phase.

**D10 — target Entra-authenticated ingestion using the existing system-assigned identity**
(`5e09fe34-8913-4aa2-80ac-618af308a88f`), which already holds Reader on the Azure OpenAI resource.
Consistent with Phase 7's no-keys direction. The connection-string path is the **named fallback**,
and taking it is a recorded decision carrying a Phase 7 debt, not a default that quietly becomes
permanent. Which of the two is viable, and what role the identity needs, is a `/research` question.

**D17 — enforced in CI with no Azure, blocking.** Run the existing fake-call test paths with an
in-memory exporter attached, which collects spans in the test process instead of sending them. Then
assert two things:

1. The set of attribute keys across all spans is **exactly** the D15 table, no more.
2. No attribute value anywhere contains the test PIN or the test phone number. This is B2's scan on
   its new channel.

Both are free, deterministic and blocking. **This requires adding OpenTelemetry as a real
dependency**, so `tests/test_b2_content_recording.py::test_nothing_in_the_deployables_imports_opentelemetry`
and the corresponding rule in `tests/test_zz_b2_leak_scan.py` must be rewritten rather than deleted:
the rule they encode (nothing emits spans, so the surface is empty) stops being true on the day this
phase starts, and what replaces it is the allowlist assertion above.

**D18 — six glossary terms**, written into `CONTEXT.md` as they settle rather than batched: trace,
span, attribute, allowlist, telemetry, redaction filter. They respect the existing rule that **call**
is the unit and **session** is reserved for the realtime session.

**D19 — one ADR covering two decisions, not two ADRs.** D11 (telemetry fails open, and no constraint
is enforced by it) and D9 (not emitting is the control, the filter is only a net) are the same
decision seen twice: **telemetry observes this system, it never governs it.** Both are hard to
reverse, surprising without context, and the result of a real trade-off, which is the bar. It joins
the two ADRs already offered and outstanding rather than jumping the queue.

**D3 and D12** are recorded under "Constraint changes" and "B5" below, since they move named
constraints.

---

## Constraint changes — NOT signed off

**A named constraint does not move without Marco's explicit sign-off**, the same way B1's sharpening
got it before Phase 4 began. Two changes are proposed here and **neither is approved**.

### B2, proposed new wording

Current (`CLAUDE.md`): *"the DTMF PIN never appears in any transcript, log line, OTel span attribute,
or persisted record."*

Proposed: *"neither the DTMF PIN nor the caller's phone number appears in any transcript, log line,
persisted record, or OpenTelemetry content channel — span attribute, span-event attribute, log
record, or completion-hook upload."*

Two widenings, both from D3 and D7:

- **Channels, 1 → 4.** Phase 4's research (`docs/phase4/research-carried-findings.md` §3c, §3e)
  established that content can travel as a span attribute, as an attribute on a span event, as a log
  record, or out of the process entirely via `OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK=upload`.
  B2's wording names one of the four. A scanner reading span attributes only would satisfy B2 as
  written while missing three ways the same content leaves. Scanned **by namespace and by value**,
  not against a fixed attribute list: the older `gen_ai.prompt`/`gen_ai.completion` names are already
  gone, `gen_ai.prompt.variable.<name>` is a caller-named prefix, and Azure's own realtime SDK uses
  `gen_ai.event.content` again.
- **Values, 1 → 2.** The caller's phone number joins the PIN. Both are known literals.

Target does not move: **0 occurrences, artifact scan, L0+L1, blocking CI.**

### B2's fourth surface becomes met rather than uncovered

`docs/phase4/exit-check.md` criterion 10 and `docs/phase5/exit-check.md` both report the span-attribute
surface as **uncovered rather than met**, because this project emits no spans. Phase 6 is the day
that stops being true, and D17 is what replaces the negative assertion with a positive one.

### B5 — D12

The constraints table enforces B5 at "L3 + production OTel", and B5 freezes after Phase 5. **Phase 5
did not freeze it**, so Phase 6 would inherit an unfrozen constraint while building the production
half of its measurement.

**Phase 6 builds the measurement path and does not set the number.** B5 freezes in Phase 5, from the
probe, as planned. If production traces later disagree with the frozen figure, that is a reported
finding that goes to Marco, never an automatic re-freeze. A trace-derived percentile states its turn
count like every other percentile in this project.

---

## Proposed exit criteria

Written as criteria, not as tickets. **None of these is in force**; they take effect if and when
Phase 6 is approved.

| # | criterion | how it is proved |
|---|---|---|
| 1 | Application Insights exists in Canada Central, workspace-based, bound to `...1D` | ARM read **and** a queried row, per the 200-OK rule |
| 2 | R-08 recomputed against one shared 5 GB grant, before provisioning | `COSTS.md`, with open item 8 settled in the same decision |
| 3 | **Open item 16 answered from the packages' source** before FastAPI instrumentation is enabled | `/research` output, cited to source, not memory |
| 4 | Open item 15 answered, or `RequestResponse` left disabled with that recorded | `/research` output |
| 5 | Exporter authenticates via the system-assigned identity, or the fallback is recorded with its Phase 7 debt | Deployed config + a delivered span |
| 6 | One trace per call, root spanning the media socket, children per D5 | The D16 smoke call, read out of `...1D` |
| 7 | **Attribute keys across all spans are exactly the D15 table** | Blocking CI test, in-memory exporter |
| 8 | **B2: 0 occurrences of the PIN or the phone number across all four channels** | Blocking CI test + artifact scan |
| 9 | The relay runs correctly with the exporter unreachable | Blocking CI test |
| 10 | No named constraint is enforced by telemetry | B1, B2, B4 suites pass with telemetry absent |
| 11 | The closed path is traced and its two causes are distinguished | Blocking CI test |
| 12 | B4's daily ledger and B5's turn latency exist as metrics | The D16 smoke call, read out of `...1D` |
| 13 | Six glossary terms in `CONTEXT.md` | The file |
| 14 | One ADR: telemetry observes, never governs | `docs/adr/` |

**Criteria 3 and 4 are `/research` items and Claude does not invoke skills here** (`CLAUDE.md`, Skill
discipline). They are named.

---

## What this phase must not do

- Provision anything before `APPROVED: Phase 6` is typed verbatim.
- Enable FastAPI instrumentation before criterion 3 is answered.
- Enable the Azure OpenAI `RequestResponse` diagnostic category on `aoai-azure-banking-voice-cc`
  before its destination table has been queried and read. It is a candidate fifth B2 surface and its
  name is the only thing anyone knows about it.
- Set `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` or
  `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED`, in the environment or programmatically. Both
  default off and both stay unset. A shipped Azure realtime SDK has already emitted transcripts and
  function-call arguments unconditionally once, ignoring this very opt-in.
- Release the phone number. Never, by any script, at any phase, for any reason.
