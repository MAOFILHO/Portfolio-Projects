# Every pattern module is an A/B pair, and one control serves four of them

A pattern module produces no absolute score. It produces a difference against a
baseline server running the identical reference scenario and the identical
tasks. Modules 1, 2, 4 and 5 all describe the same control in different words:
a flat 1:1 wrapper over every backend endpoint, vendor-named, unnamespaced,
returning raw payloads and opaque errors. Only module 3 needs its own baseline.
Five pattern servers plus two baselines is seven servers.

## Consequences

The control is measured four times, once per module's task set, so a reviewer
may call it a strawman reused. It is defensible because it is the wrapper teams
actually ship first, and because four independent measurements of one control
is a cleaner experiment than four controls measured once each.
