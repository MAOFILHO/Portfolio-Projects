# Resource Gateway measures sanitization by scanning agent output, not by state equality

Every other pattern module's verifier checks that the right row landed in
Postgres. Resource Gateway adds a second, different check: a runbook's
internal notes are withheld from its resource by construction, but the
control's flat tool returns them raw, so a task's verifier also fails if
that text appears in the agent's final write. This is the benchmark's first
content-shape check rather than a state-equality one — a deliberate
commitment to measuring a real behavioral gap (does the agent reproduce raw
text it was given), not just a turns/tokens cost difference like the other
four modules.
