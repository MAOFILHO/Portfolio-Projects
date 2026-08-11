# Architecture — Phase 2

Two diagrams: the system end-to-end, and the per-turn safety-ordering sequence that `ADR-010` specifically
requires be visible in the architecture, not buried in code.

---

## System architecture

```mermaid
flowchart TD
    Caller(["Caller<br/>(reviewer / author, invited only — ADR-001, threat model)"])

    subgraph Telephony["Telephony — infra/terraform/stacks/telephony (separate state, never destroyed)"]
        DID["Protected DID<br/>+14169871547 (CA)<br/>inbound-only"]
        ConnectInstance["Connect instance<br/>marcos-ivr-demo<br/>Connect Customer (default tier)<br/>bundled AI unused — ADR-001"]
    end

    subgraph TurnMgmt["Turn management — infra/terraform/stacks/main"]
        Flows["Contact flows<br/>recording OFF — constraint 18<br/>Set Disconnect Flow"]
        LexBot["Lex V2 bot<br/>nested AWS::Lex::Bot via CFN — ADR-007<br/>ASR / TTS voice / barge-in / DTMF<br/>6 intents, 11-slot FileAutoClaim"]
    end

    subgraph AgentCore["Agent core — Lambda, Python 3.12, SnapStart — ADR-009"]
        direction TB
        L1["L1: deterministic injury/fatality<br/>pre-node — D12, no LLM call<br/>runs FIRST, every turn"]
        RouterL2["Router + L2 safety classifier<br/>merged call, forced tool-use<br/>us.amazon.nova-micro-v1:0 — ADR-004"]
        GuardIn["ApplyGuardrail (INPUT)<br/>explicit graph node, not bolted to<br/>the model call — ADR-010"]
        Graph["LangGraph StateGraph<br/>6 intents, conditional edges<br/>checkpointed per turn — ADR-005"]
        Gen["Generation node<br/>feature-flagged: Nova Lite (default)<br/>or Claude Haiku 4.5 — ADR-004,<br/>winner decided by Phase 6 evals"]
        GuardOut["ApplyGuardrail (OUTPUT)<br/>before TTS — ADR-010"]
    end

    subgraph DataTools["Data & tools"]
        DDB[("DynamoDB<br/>checkpoints (langgraph-checkpoint-aws,<br/>DynamoDB+S3 overflow — ADR-005)<br/>claim records<br/>vector store — ADR-002")]
        S3[("S3<br/>redacted transcripts<br/>checkpoint overflow >350KB")]
        MockClaims["Mock claims system<br/>(tool call)"]
        MockCRM["Mock CRM<br/>(tool call, UpdateContactInfo)"]
    end

    subgraph PostCall["Post-call — async, EventBridge-triggered — ADR-006"]
        EB["EventBridge rule<br/>source: aws.connect<br/>detail.eventType: DISCONNECTED"]
        PostLambda["Post-call Lambda<br/>idempotent, keyed on contactId<br/>Layer-2 redaction defense-in-depth — ADR-011<br/>soft-flag computation, eval sampling"]
        DLQ["SQS DLQ<br/>failed post-call runs"]
    end

    subgraph Human["Human escalation — always reachable, from any state"]
        CCP["Simulated FNOL specialist<br/>CCP softphone<br/>$0 settlement authority, cannot deny"]
    end

    subgraph Obs["Observability"]
        CW["CloudWatch<br/>structlog JSON, OTel traces<br/>Bedrock-calls-per-contactId alarm<br/>concurrent-calls alarm"]
        Budget["AWS Budgets<br/>$25/mo non-action alarm, $0 cost"]
    end

    Caller -->|"voice / DTMF"| DID --> ConnectInstance --> Flows --> LexBot
    LexBot -->|"codehook: sessionState,<br/>interpretedValue"| L1
    L1 -->|"no escalation"| RouterL2
    L1 -->|"escalation — immediate,<br/>bypasses everything below"| CCP
    RouterL2 --> GuardIn
    GuardIn -->|"not blocked"| Graph
    GuardIn -.->|"blocked"| LexBot
    Graph --> Gen
    Graph -->|"CheckClaimStatus,<br/>RentalTowingEntitlement"| MockClaims
    Graph -->|"UpdateContactInfo,<br/>read-back + confirm"| MockCRM
    Graph <-->|"checkpoint per turn"| DDB
    Graph -->|"CoverageQuestion,<br/>RentalTowingEntitlement RAG"| DDB
    Gen --> GuardOut
    GuardOut -->|"not blocked"| LexBot
    GuardOut -.->|"blocked"| LexBot
    Graph -->|"capability / confidence<br/>escalation route 3/4"| CCP
    LexBot -->|"TTS via Polly"| Caller

    ConnectInstance -.->|"DISCONNECTED event,<br/>best-effort delivery"| EB --> PostLambda
    PostLambda --> S3
    PostLambda --> DDB
    PostLambda -.->|"failure"| DLQ
    PostLambda --> CW

    AgentCore -.-> CW
    TurnMgmt -.-> CW
    CW -.-> Budget

    classDef safety fill:#7a1f1f,stroke:#f5b7b1,color:#fff
    classDef guardrail fill:#7a5c1f,stroke:#f5d7a1,color:#fff
    classDef async fill:#1f4a7a,stroke:#a1c7f5,color:#fff
    class L1 safety
    class CCP safety
    class GuardIn guardrail
    class GuardOut guardrail
    class EB async
    class PostLambda async
    class DLQ async
```

**Reading the color coding:** red nodes are the safety path (deterministic, union-semantics, cannot be
vetoed downstream — `D12`/`D15`). Amber nodes are Guardrails, explicitly sequenced as their own graph nodes
rather than bolted onto a model call (`ADR-010`). Blue nodes are the async post-call pipeline, fully
decoupled from the per-turn latency budget by construction (`ADR-006`).

---

## Per-turn safety ordering — the sequence `ADR-010` requires be visible

```mermaid
sequenceDiagram
    participant Caller
    participant Lex as Lex V2
    participant L1 as L1 (deterministic pre-node)
    participant RL2 as Router + L2 (Nova Micro)
    participant GI as ApplyGuardrail (INPUT)
    participant Gen as Generation node
    participant GO as ApplyGuardrail (OUTPUT)
    participant Human as CCP (human)

    Caller->>Lex: speech turn (ASR transcript)
    Lex->>L1: raw turn text
    Note over L1: Runs before ANYTHING else.<br/>Not a model call — D12.
    alt Injury/fatality indication (K or A)
        L1->>Human: immediate transfer, 911 guidance first
        Note over L1,Human: Bypasses L2, Guardrails, generation<br/>entirely. Not overridable downstream.
    else No escalation trigger
        L1->>RL2: proceed
        Note over RL2: Merged call: intent routing +<br/>recall-biased safety classification.<br/>Forced tool-use, required safety_flag field.
        RL2->>GI: proceed (L2 flag carried forward)
        Note over GI: Explicit graph node.<br/>NOT attached to the model call —<br/>ADR-010's core architectural choice.
        alt Guardrails blocks input
            GI->>Lex: blocked-message response
        else Not blocked
            GI->>Gen: proceed
            Gen->>GO: candidate response
            alt Guardrails blocks output
                GO->>Lex: blocked-message response<br/>(FM inference already billed)
            else Not blocked
                GO->>Lex: response text
                Lex->>Caller: Polly TTS
            end
        end
    end
```

**Why this specific ordering is load-bearing, restated from `ADR-010`:** a general-purpose content filter has
no concept of this project's escalation requirement — it could legitimately block a graphic injury
description as violent content. L1 must see the caller's actual words before any filter has a chance to
intercept them. This is why L1 sits before the merged router+L2 call, and why Guardrails is driven explicitly
via `ApplyGuardrail` rather than attached to the model invocation, which the current AWS documentation
confirms is the intended, decoupled integration pattern for exactly this kind of ordering requirement.

## Sources

Diagram content reflects decisions already accepted in `docs/adr/ADR-001` through `ADR-011`, plus verified
facts in `PROJECT_STATE.md` (Connect instance/DID identifiers, `OutboundCallsEnabled: false`). No new external
research was required to draw this diagram — it is a synthesis of already-cited sources, not a new claim.
