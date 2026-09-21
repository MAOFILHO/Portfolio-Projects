# Architecture

Every box is deployed in `rg-azure-banking-voice-agentic-ai`, Canada Central. The solid path is the live
call; the dashed path is Phase 8's post-call pipeline, which starts only after the call has ended and is
never awaited by it (ADR-006 Decision 4). Written 2026-09-20 and revised 2026-09-21 for the Phase 8 gate review, against the
code in the repo, not a particular image. Confirm the live resources against the Azure API before relying
on it (`CLAUDE.md`, Resume discipline).

```mermaid
flowchart TD
    caller(["Caller<br/>Canadian number"]) -->|dials| acs["Azure Communication Services"]
    acs -->|"Event Grid: incoming call"| app

    subgraph app_box ["Container App ca-azbank-echo-p0, min-replicas 1"]
        app["POST /api/incoming-call<br/>WS /ws media relay"]
        auth["auth: DTMF PIN check<br/>B2: the PIN never leaves here"]
        gate["dispatch/gate.py<br/>B1: deny by default"]
        caps["cost/caps: 5 min, 20 turns,<br/>daily minutes, fails closed<br/>B4"]
        capture["CallCapture<br/>agent words only, in memory"]
        post[["post-call pipeline<br/>background task"]]
    end

    acs <-->|"bidirectional media WSS<br/>audio + DtmfData"| app
    app -->|"DTMF digits"| auth
    app <-->|"audio and tool calls<br/>Entra ID, wss"| rt["Azure OpenAI realtime<br/>gpt-realtime-mini<br/>B3 pinned"]
    rt -->|"tool call"| gate
    gate -->|"only when authenticated<br/>PIN check and escalate are<br/>the only anonymous tools"| bank["ca-azbank-core-banking<br/>FastAPI + SQLite<br/>internal-only ingress"]
    app --> caps
    caps <--> table[("Table Storage stazbankcallrecords<br/>daily minutes, escalations,<br/>call summaries")]
    gate -->|"escalate_to_human"| table
    app --> capture

    capture -.->|"call ends"| post
    post -.->|"1. redact in memory"| lang["Azure AI Language<br/>Conversation PII<br/>canadacentral"]
    post -.->|"2. redacted text only"| blob[("Blob container transcripts<br/>same storage account")]
    post -.->|"3. redacted text only"| txt["Azure OpenAI gpt-5.4-mini<br/>summary + intent<br/>B3 pinned, guard non-fatal"]
    post -.->|"4. call row: pending first, final last"| table

    app -.->|"OpenTelemetry"| ai["Application Insights<br/>appi-azure-banking-voice"]
```

## Reading it

- **B1** is one function of (agent, auth state, tool). No banking operation reaches `ca-azbank-core-banking`
  while the caller is anonymous. **B2**: a PIN arrives as DTMF and is checked in `auth`; it never reaches
  the model, a log line, a span or a stored record. **B4** is the only spend brake, because the subscription
  has `spendingLimit: Off`.
- **The post-call path redacts before it writes** (ADR-007). A transcript that cannot be redacted is never
  written raw: the call gets a row saying so, and no transcript and no summary. Both the blob and the
  summary take only the redacted text.
- **Every post-call step can fail on its own** and costs its own fields of the row (a redaction failure
  takes the transcript and the summary with it). The row is written twice: first, the moment the call ends,
  with the transcript and summary `pending`; then overwritten when the steps finish. A container killed
  mid-pipeline leaves the pending row. A closed-line call, or one with no agent turns, has nothing to redact,
  so it stores no transcript and its row is written once.
- **Auth to every Azure service is a managed identity token**, with no keys in code: one async credential,
  shared by the Table client, the Blob client and the token providers behind the realtime connection,
  Language and the text model. Two things build their own credential, off the call path: the B3 guards'
  ARM read (at boot, and in a thread before each summary) and the telemetry exporter.
  The storage account has shared-key access off.
- Not drawn: the phone number `+17059100383` (an ACS resource, never released by any script), the Event Grid
  subscription, and the deploy CLI (`make deploy`, `make teardown`).

Related: `docs/PLAN.md` (source of truth for scope and budget), `docs/adr/`, `CONTEXT.md` (glossary).
