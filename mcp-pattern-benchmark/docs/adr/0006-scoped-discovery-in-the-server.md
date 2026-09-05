# Proxy Aggregator does scoped discovery through a tool, not a changing tool list

The Proxy Aggregator's task-scoped discovery could be built by having the
harness re-list tools every turn, but that call would apply to all seven servers
and make the harness itself a variable in the experiment. Instead the server
exposes a `discover_tools` tool the agent calls to get the scoped set. The
harness is untouched, and this is how real aggregators do scoped discovery.
