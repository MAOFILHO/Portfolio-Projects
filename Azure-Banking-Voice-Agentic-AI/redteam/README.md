# `redteam/` — attack ideas, one file per idea

Each YAML file is one **idea**: a distinct way somebody might try to reach a banking operation
without authenticating. Concrete **cases** are the cross-product of an idea with tool, agent, and
point in the call, expanded by `tests/redteam_harness.py`. No case list is written out anywhere, and
none is maintained by hand.

**Both numbers are reported wherever this suite is described** — distinct ideas as well as concrete
cases. A case count with no idea count behind it is the same empty claim as a percentile with no N,
which this project already forbids for B5. `tests/test_redteam.py` prints both.

Ideas are **genuinely distinct from one another**. Near-duplicates are never added to make a total
look larger; if fewer real ideas exist than were aimed for, the real number is what gets reported
and the shortfall is explained.

## The shape of an idea file

```yaml
id: kebab-case-and-unique
title: one line, what the attacker is trying
rationale: >
  why this is a real thing to try, and what would have to be broken for it to work
matrix:
  tool:  [get_balance, transfer, list_accounts]   # may name undeclared tools too
  agent: [triage, banking]
  point: [before_entry, mid_entry, after_clear, after_wrong_pin, after_exhaustion]
arguments: valid        # valid | malformed | injected | empty   (default: valid)
backend: healthy        # healthy | unavailable                  (default: healthy)
repeat: 1               # how many times the attempt is made     (default: 1)
```

`point` is what the caller has keyed by the time the model makes its attempt. Every value leaves the
call anonymous — that is the whole purpose of the dimension. `after_exhaustion` is the one that has
already ended the call, so nothing is left to refuse the attempt; those cases are counted separately
as well as together, and the harness explains why.
