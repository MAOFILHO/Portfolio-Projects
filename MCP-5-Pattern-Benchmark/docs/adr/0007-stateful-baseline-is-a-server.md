# The Stateful Session Server's baseline is a stateless server, not a modified client

The reference table describes this baseline as a client that resends the whole
working state each turn. The agent is held fixed across every measurement, so
changing the client per module would make the agent a variable. The baseline is
therefore a server whose tools take the full working state as an argument on
every call, forcing the agent to carry and resend it. Input tokens is the metric
that moves.
