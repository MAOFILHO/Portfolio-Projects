# ADR-003 — Realtime SDK: base `openai` client, not `openai-agents`

Status: **Accepted** — confirmed by Marco 2026-09-07. Recorded now because issue #18's acceptance
criteria require the choice to be written down with a reason before the relay is built on either
path.
Date: 2026-09-07

## Context

`docs/PLAN.md` says two things that this phase has to reconcile.

Its Architecture section states, as a verified finding, that the OpenAI Agents SDK can target
Azure — `api.openai.com` is only a default, and supplying `headers` via `model_config` bypasses the
`OPENAI_API_KEY` requirement — and instructs: **"Pin `openai-agents >= 0.3.0` as a floor in
`pyproject.toml`, not a comment."** Its Phase 2 definition then describes the deliverable as
"`RealtimeSession` against Azure via `model_config` override", which is that SDK's API shape.

Phase 1 did not do that. It shipped directly on the base `openai` SDK's realtime client
(`client.realtime.connect(model=…)`), and that path is confirmed working against the live
deployment — a documented probe for tool calling
(`docs/phase1/evidence/tool-calling-probe-2026-08-29.json`), a correction to the outbound audio
event name, and two real answered calls on 2026-09-01 with all six exit-test rows passing.

So Phase 2 either adopts the SDK the plan names, or deviates deliberately and says why.

## Decision

**Stay on the base `openai` SDK. Do not add `openai-agents`.** No floor pin is added to
`pyproject.toml`.

Reasons, in the order they actually weigh:

1. **The base path is proven live; the SDK path is not.** Switching would mean re-verifying the
   Azure realtime wire path against a live deployment — billable calls, on a project whose entire
   remaining call budget is measured in hours per month — to replace something already demonstrated
   working on two real calls. That is spending the scarcest resource this project has to move
   sideways.
2. **The SDK's main draw does not survive contact with this project's own constraints.**
   `openai-agents` earns its keep on agent orchestration and handoffs. `docs/PLAN.md` already
   records that realtime handoffs do not support `input_filter`, which is why the reference repo's
   handoff message filter "cannot be ported" — and decision 6 specifies agent swap via
   `session.update`, a raw protocol operation the base client issues directly. Issue #20 implements
   the agent table as a declarative structure this project owns.
3. **A dependency that mediates the protocol makes the fakes weaker.** Issue #18's fakes stand in
   for the realtime connection at the wire-event level, which is the level Phase 1's live probes
   actually verified. Testing against an SDK's abstraction of those events would move the fakes one
   layer away from the thing that was measured.
4. **It is one fewer dependency on the B3 path.** Every layer between this code and the deployment
   name is a layer that could resolve a model differently than the boot guard checked.

## Consequences

- `docs/PLAN.md`'s Architecture section described a path this project is not taking (the
  `openai-agents >= 0.3.0` floor-pin instruction, and Phase 2's "`RealtimeSession` … via
  `model_config` override" phrasing) — corrected in place alongside this ADR's acceptance
  (2026-09-07), not left stale now that the decision is confirmed rather than proposed.
- The relay owns the protocol directly: `realtime/client.py` builds the connection,
  `realtime/session.py` speaks events. Both are small, and both are covered by fakes that replay
  the event names confirmed live.
- If a later phase needs genuine multi-agent orchestration beyond `session.update` swapping, this
  decision is worth revisiting — at that point the SDK would be replacing something real rather
  than something already working.
- The `RealtimeConnection` protocol in `realtime/client.py` is the seam that would make such a
  swap contained: anything satisfying `send` plus async iteration can be dropped in, including an
  SDK-backed implementation.
