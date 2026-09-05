# MCP Pattern Evaluation

Measures what an MCP server's architecture costs an agent. Each architecture is
compared against a weaker architecture serving the identical scenario, so the
difference is attributable to the design and nothing else.

## Language

**Pattern module**:
One MCP server architecture under evaluation, together with its reference
scenario and its baseline. Six exist; five are in scope.
_Avoid_: pattern, row, module, Direct API Wrapper, Composite Service,
MCP-to-Agent, Event-Driven, Hierarchical MCP, Local Resource Access

**Reference scenario**:
The realistic situation a pattern module is measured in. Held identical between
a pattern server and its baseline.
_Avoid_: use case, domain, workload

**MCP surface**:
What a server advertises to the agent: its tools, resources and prompts, with
their names and shapes. The only thing a pattern module varies.
_Avoid_: tool list, API surface, capabilities

**Pattern server**:
The server that implements a pattern module's MCP surface.
_Avoid_: candidate, treatment

**Baseline**:
The weaker server a pattern server is measured against, serving the same
reference scenario. A pattern module has no score of its own, only a difference
from its baseline.
_Avoid_: control, strawman, reference

**Backend**:
The single synthetic system all servers front: one Postgres database behind one
small HTTP API, split into four namespaces (repos, tickets, runbooks,
deploys). Seeded fresh per task.
_Avoid_: database, API, fixture, environment

**Internal notes**:
The part of a runbook's content withheld from its resource: the pattern
server never includes it, the flat control tool always does. The one
property Resource Gateway's tasks measure structurally rather than by state.
_Avoid_: secret, redacted section, confidential text

**Runbook acknowledgement**:
The write action recording that a runbook's guidance was applied, holding
the agent's note. The verifiable action for Resource Gateway's otherwise
read-only surface.
_Avoid_: comment, log entry, note (bare)

## Pattern modules

**Resource Gateway**:
Exposes sanitized resources plus narrow read and query tools.

**Tool Orchestrator**:
Exposes one tool that drives a multi-step outcome.

**Stateful Session Server**:
Holds working state across turns behind session tools.

**Proxy Aggregator**:
Fronts several upstream services with namespaced tools and task-scoped
discovery.

**Domain-Specific Adapter**:
Exposes semantic tools named for business outcomes.

**Code-First Hybrid Adapter**:
Exposes a small discovery and execution surface the agent writes code against.
Out of scope for the first release.
