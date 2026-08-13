"""Deployment entry points. The boundary between AWS's invocation contracts and this project's own code.

Nothing in here holds business logic. `lex_codehook` translates a Lex V2 codehook event into a call on
the agent and translates the result back into a `sessionState`; the agent itself lives in
`fnol_voice_agent.agents` and does not know it is being called by a telephone.

That split is what keeps `make simulate` honest — the simulator drives the same agent through the same
arguments, so a passing simulation is evidence about the shipped path rather than about a parallel one.
"""
