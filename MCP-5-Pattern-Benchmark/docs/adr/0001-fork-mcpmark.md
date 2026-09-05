# Fork MCPMark rather than build a harness

We need per-task setup and teardown, subprocess verification, token and turn
accounting, and multi-run aggregation. MCPMark already has all of it, and its
`SERVICES` registry is the exact seam a pattern server drops into. We forked it
and deleted the services we do not use, accepting that the harness carries
conventions we did not choose.
