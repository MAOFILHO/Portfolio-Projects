# ADR-003: LangGraph orchestrates the agent — Bedrock Agents Classic is closed to new customers, AgentCore rejected on regional fragmentation and framework fit

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

`CLAUDE.md`'s stack description already names LangGraph, but two AWS-native alternatives needed to be
assessed on the merits rather than dismissed by the stack description alone: **Amazon Bedrock Agents
("Classic")** and **Amazon Bedrock AgentCore**. Both were checked against current documentation today,
2026-08-11.

## Decision

**LangGraph orchestrates the agent, deployed on Lambda.** Neither Bedrock Agents Classic nor AgentCore is
adopted, for two different, independently sufficient reasons.

### Bedrock Agents Classic — not a live option

AWS's own current documentation carries a banner: *"Amazon Bedrock Agents (now Amazon Bedrock Agents
Classic) is no longer open to new customers. For capabilities similar to Bedrock Agents Classic, explore
Amazon Bedrock AgentCore. Existing customers can continue to use the service as normal."*
(<https://docs.aws.amazon.com/bedrock/latest/userguide/agents-how.html>) This project's Bedrock/Connect
account activity began 2026-08-11, so it is a new customer for this service — **Bedrock Agents Classic is
not available to adopt, independent of any technical assessment.**

Recorded for completeness, since it is informative about *why* AWS is steering everyone toward AgentCore
instead: Agents Classic's default orchestration is a single-agent ReAct-style loop (reason → pick
action/knowledge-base query → observe → repeat), and even its "pre-processing" step — nominally where a
safety gate might sit — **itself invokes the foundation model** by default, which is the opposite of the
deterministic, non-LLM L1 pre-node this project's safety design requires (`D12`). Custom orchestration via a
Lambda-driven callback state machine *can* achieve a deterministic pre-model gate (the Lambda receives a
`START` state before any model is invoked and can short-circuit straight to `FINISH`), but that is a single
callback FSM with named states, not a declarative multi-node graph with typed conditional edges — a materially
different and less expressive programming model than LangGraph's `StateGraph`, and moot anyway given the
service is closed to this project.

### AgentCore — rejected on two grounds, one already established

**Regional fragmentation, established in `ADR-008`:** full-feature AgentCore parity (Runtime, Evaluations,
Policy) exists in exactly 4 regions; `us-west-2` has full parity, but the fragmentation itself — a real
capability wall other projects have hit — is corroborating evidence against building on a framework whose
capability set varies by region, when this project's actual orchestration needs (a state graph with
conditional edges, a custom checkpointer, a deterministic safety pre-node) have no such constraint under
LangGraph on Lambda.

**Framework fit, checked today:** current AWS guidance explicitly documents *"LangGraph... on AgentCore"* as
a supported pattern (<https://aws.amazon.com/blogs/machine-learning/build-highly-scalable-serverless-langgraph-multi-agent-systems-in-aws-with-amazon-bedrock-agentcore/>)
— meaning AgentCore is, in current AWS practice, a **hosting/runtime layer that people run LangGraph on top
of**, not a competing orchestration framework with its own graph model. Adopting AgentCore now would mean
either (a) using it purely as a Lambda alternative for hosting the same LangGraph graph this project already
needs, which is a Phase 9 deployment-target question, not an orchestration-framework question, or (b) using
its own agent-runtime abstractions instead of LangGraph, which would mean giving up the explicit
`StateGraph`/conditional-edge model this project's safety-ordering (`ADR-010`) and slot-filling (Phase 1)
design already depend on, for a framework with a narrower region footprint and no demonstrated advantage for
this project's specific requirements.

**This project runs LangGraph on Lambda, not on AgentCore**, because Lambda is already the compute layer
constraint 17 fixes for this region, and nothing about AgentCore's value proposition — primarily aimed at
larger, more complex multi-agent systems with built-in memory/identity/gateway services this project's
six-intent, single-agent-graph scope does not need — outweighs the added region-fragmentation and
architectural-lock-in risk of adopting it now.

## Consequences

**Positive:**
- Confirms the existing stack description in `CLAUDE.md` was the right call, now for verified reasons rather
  than by assumption — Bedrock Agents Classic turned out to be foreclosed entirely, which this project would
  not have known without checking.
- LangGraph's explicit graph model is exactly what `ADR-010`'s safety-ordering decision and the Phase 1
  slot-filling design already assume; no rework required.

**Negative / accepted residual risk:**
- LangGraph on Lambda means this project owns more of the orchestration/persistence plumbing itself
  (`ADR-005`'s checkpointer decision is a direct consequence) rather than getting memory/identity/gateway
  services bundled the way AgentCore would provide them. Accepted as the correct trade for a six-intent,
  single-agent-scope prototype — those bundled services solve problems this project does not have at its
  current scale.
- If a future phase's scope grew substantially (multi-agent orchestration, cross-session memory beyond a
  single call), this ADR's conclusion should be revisited — recorded as a scope-triggered revisit condition,
  not treated as a decision that could never change.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| Bedrock Agents Classic | Not available | Confirmed closed to new customers as of 2026-08-11; also would have required custom-orchestration workarounds even if available |
| Bedrock AgentCore (as orchestration framework) | Rejected | Regional feature fragmentation (`ADR-008`); current AWS guidance treats it as a hosting layer for LangGraph, not a competing graph model — no capability gained by adopting it as the orchestrator |
| Bedrock AgentCore (as Lambda replacement, running LangGraph on top) | Deferred, not rejected | A legitimate Phase 9 deployment-target question, independent of the orchestration-framework decision this ADR makes |
| **LangGraph on Lambda** | **Chosen** | Matches this project's actual scope (single agent, explicit graph, deterministic safety ordering); avoids region fragmentation and a foreclosed service |

## Sources

- <https://docs.aws.amazon.com/bedrock/latest/userguide/agents-how.html>
- <https://docs.aws.amazon.com/bedrock/latest/userguide/agents-custom-orchestration.html>
- <https://aws.amazon.com/blogs/machine-learning/build-highly-scalable-serverless-langgraph-multi-agent-systems-in-aws-with-amazon-bedrock-agentcore/>
- `docs/adr/ADR-008-region-selection.md` (AgentCore region-tier findings, cited rather than re-derived)

All facts fetched live on 2026-08-11 via a background research agent, per the project's standing rule to
verify against current sources rather than memory.
