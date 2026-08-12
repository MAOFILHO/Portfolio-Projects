# ADR-012: MCP transport — in-process Python calls on the runtime hot path; the MCP wire protocol is proven servable, not assumed honest, via a falsifiable test in Stage 2

**Status:** Accepted (Phase 5). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

`TARGET-LAYOUT.md` names `src/fnol_voice_agent/mcp/` — "one MCP server per backend domain (policy, claims,
contact, escalation)" — and `docs/phase0/DOMAIN-ARTIFACTS.md`/the Phase 0 roadmap both call for MCP servers as
a first-class Phase 5 deliverable. What was never decided: does the LangGraph agent, running inside a Lambda
function on the call path, actually speak the MCP wire protocol (stdio/SSE, a client-server round trip per
tool call) to reach these servers at runtime — or does "MCP server" describe the *shape* of the tool
interface (typed, schema-validated, one module per domain) while the hot-path caller imports and calls it as
a plain Python function?

This is not a cosmetic question. Two hard constraints already accepted elsewhere in this project bear on it
directly:

1. **The 1,800 ms p95 turn-latency budget** (`CLAUDE.md`, voice turn-latency constraint). A wire-protocol
   round trip — even to a local process — adds serialization, a process boundary, and (for a fresh subprocess
   per invocation) startup cost on top of whatever the tool call itself does. `DIALOGUE-POLICIES.md` §1
   already counts five sequential steps against this budget; adding transport overhead to steps that call
   MCP tools (the per-intent nodes in Stage 6) is a direct latency cost, not a free abstraction.
2. **`ADR-009`'s SnapStart constraint**: "network connections established at module-load time... are not
   guaranteed to survive the snapshot/resume cycle... must be defensively re-validated (or lazily
   re-created)." A persistent MCP server process — or a client connection to one — is exactly this kind of
   state. Running an MCP server as a second long-lived process *inside* a single Lambda invocation is also
   architecturally awkward: Lambda is request/response, not a process host, and standing up a second
   always-on compute resource to host it would collide with the banned-by-default list (`CLAUDE.md`:
   "always-on ECS/EKS/Fargate").

Against that: MCP has real, named value in this project already — `docs/phase2/THREAT-MODEL.md` names "MCP
argument validation" as the mechanism closing a tool-abuse residual risk, and `.claude/mcp.json` (named in
`TARGET-LAYOUT.md` since Phase 0) gives Claude Code itself a way to interactively inspect and exercise the
exact same tool contracts during development — a real, concrete benefit that has nothing to do with the
runtime hot path.

## Decision

**The LangGraph runtime calls MCP-server-defined tools in-process, as plain Python function calls — no wire
protocol, no subprocess, no client-server round trip on the call path.** `.claude/mcp.json` registers the
same servers for Claude Code's own dev-time use, where the wire protocol *does* run, because that use case has
no latency budget to protect.

**This is honest only if a specific, falsifiable property holds — Marco's requirement, stated as the test
itself, not a design intention:**

> The same tool schemas must be servable over the wire without modifying the tool implementations. No shared
> state reaching around the interface. Schemas defined separately from handlers.

Concretely, this means:

- **Handlers are plain functions/classes, transport-agnostic.** `mcp/{policy,claims,contact,escalation}_server.py`
  defines the handler logic and its Pydantic input/output schema once. Neither the schema nor the handler
  imports anything from an MCP transport library.
- **Two thin adapters wrap the same handler, never a second implementation.** An in-process adapter
  (a plain function call from `agents/nodes/`) and an MCP-server adapter (the official `mcp` SDK's
  `Server`/`stdio` machinery, registering the same handler + schema as a tool) both call *into* the handler —
  neither reimplements it, and neither can see or mutate state the other doesn't also see through the
  handler's own explicit arguments and return value. "No shared state reaching around the interface" means
  concretely: no module-level mutable object that the in-process caller mutates and the MCP-server adapter
  reads (or vice versa) as a side channel outside the handler's declared signature.
- **Falsifiable, not asserted**: Stage 2 ships an automated test (`tests/unit/test_mcp_wire_protocol.py` or
  equivalent) that launches the actual server subprocess — the same command `.claude/mcp.json` would run —
  and drives it with a real MCP client (the `mcp` SDK's `ClientSession` over stdio), calling each tool and
  asserting the result matches what calling the handler directly, in-process, produces for the same input.
  **If this test cannot be written without touching the handler's internals, or requires the handler to know
  it might be called over the wire, the property is false and this ADR's framing is dishonest** — in that
  case the correct fix is not to force the test to pass, it is to rename these modules to what they actually
  are (plain internal tool functions) and drop the MCP claim, per Marco's own framing: "if that property
  doesn't hold, we're calling functions 'MCP' and should say so instead."

## Consequences

**Positive:**
- Zero transport overhead on the call path — the latency cost of a tool call is exactly the cost of the
  Python function call plus whatever it does (a JSON read today, a DynamoDB read once Phase 8 provisions the
  real table), nothing added for the sake of the framing.
- The MCP claim in this project's own documentation and portfolio narrative is backed by a repeatable,
  automated test, not an assertion — consistent with `CLAUDE.md`'s "nothing may be stubbed out and labelled
  as if present" rule applied to an architecture claim, not just a feature claim.
- `.claude/mcp.json` gives Claude Code (or any other MCP client) a working, interactive way to call these
  exact tools during development — genuinely useful, and genuinely the same code as production, not a parallel
  demo implementation that could silently drift from it.
- Closes `docs/phase2/THREAT-MODEL.md`'s named residual risk ("MCP argument validation not yet built") with a
  concrete mechanism: schema validation happens once, at the handler boundary, and both adapters inherit it.

**Negative / accepted residual risk:**
- This project cannot claim "the agent talks MCP at runtime" — because it doesn't, and shouldn't, given the
  latency budget. Anyone reading the architecture closely enough to ask "does the wire protocol run on every
  turn?" gets an honest "no, and here's why, and here's the test proving the interface would still work if it
  did" rather than a vague implication otherwise.
- Two adapters (in-process, MCP-server) is marginally more code than one, and both must be kept passing the
  Stage 2 wire-protocol test as the handlers evolve — accepted because the alternative (one adapter, silently
  becoming the only tested path) is exactly how the "no shared state" property would rot unnoticed.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| MCP wire protocol on the runtime hot path (subprocess or persistent server process per Lambda) | Rejected | Direct latency cost against the 1,800 ms budget; collides with `ADR-009`'s SnapStart connection-revalidation constraint; a persistent server process is an always-on compute resource, banned by default |
| Drop the MCP framing entirely, plain internal Python modules, no `.claude/mcp.json` | Rejected | Gives up real dev-time value (interactive tool inspection via Claude Code) for no latency benefit, since in-process-only was already the fallback either way |
| **In-process calls at runtime; MCP wire protocol proven servable (not assumed) via a falsifiable Stage 2 test; `.claude/mcp.json` for dev-time use only** | **Chosen** | Keeps the latency budget intact, keeps the MCP claim honest and checkable, and gets real dev-time value from the same, un-duplicated handler code |

## Sources

Internal — this ADR resolves a gap in prior Phase 0/2 planning rather than a new external fact-finding pass.
`ADR-009` (SnapStart constraints) and `docs/phase2/THREAT-MODEL.md` (MCP argument validation residual risk)
are the load-bearing prior decisions this one has to be consistent with.
