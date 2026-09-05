# 01: Harness resource support

**What to build:** `MCPStdioServer` gains `list_resources()`/`read_resource(uri)`,
mirroring its existing `list_tools()`/`call_tool()`, wired into all 3 agent
call sites so resources reach the agent's context the same way tools do.
Proves the harness can discover and read MCP resources at all before
anything in this phase depends on it — the same "runtime risk first" move
Phase 1's ticket 01 made for tools.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `MCPStdioServer` gains `list_resources()` and `read_resource(uri)`,
      mirroring `list_tools()`/`call_tool()`
- [x] Both `mcpmark_agent.py` call sites and `react_agent.py`'s call site
      fetch resources and fold them into the agent's context alongside
      tools
- [x] A real, subprocess-backed test connects `MCPStdioServer` to a minimal
      fixture MCP server exposing one resource and confirms
      `list_resources()`/`read_resource()` return the right content — no
      mocks, no dependency on this phase's backend or pattern server
- [x] Resource discovery costs no extra turn (fetched once at connect, like
      tools); `read_resource` costs a turn like any tool call

**Design decision made mid-build, not fully specified upfront:** native
tool-calling APIs (Anthropic, OpenAI, and the ReAct prompt format) have no
"resource" primitive, only tools — so "fold resources into context alongside
tools" needed a concrete mechanism. Resolved by having each of the 3 agent
call sites append one synthetic tool, `read_resource(uri)`, to the real MCP
tools list right after fetching it — its description lists every discovered
resource's URI. Dispatch at all 3 tool-call sites now routes through one
shared `BaseMCPAgent._dispatch_tool_call`, which special-cases that name to
`mcp_server.read_resource(uri)` instead of `call_tool`. Confirmed with the
user before touching the agent files, since this is a shared-surface change
used by every phase, not just this one.

**Not separately unit-tested:** the dispatch wiring inside
`mcpmark_agent.py`/`react_agent.py` has no existing test seam (their
`call_tool` dispatch isn't unit-tested either) — proven live in ticket 02's
proof task instead, consistent with how tool dispatch has always been
verified in this codebase.

## Comments
