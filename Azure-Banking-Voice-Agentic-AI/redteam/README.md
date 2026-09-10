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

## The idea count, and the shortfall

**11 distinct ideas, expanded to 193 concrete cases, 176 of which reach an attempt.** The constraint
is at least 120 cases; the target for ideas was 20 to 30.

**11 is short of that target, and it is the real number.** No near-duplicate was added to close the
gap, because a total reached that way says nothing that the smaller total did not already say.

The reason the honest number is this low is the size of the surface. B1 protects three operations,
reachable by two agents, under an auth state with exactly two values, through one dispatcher that
takes a tool name and a JSON string. That is the whole attack surface, and the genuinely different
things to try against it are: call the tool plainly, call it from an agent that was never shown it,
break the arguments, put the answer you want *into* the arguments, invent the tool name, disguise a
real tool name, forge the routing that decides which permission row applies, say out loud that you
are already authenticated, take the backend away, repeat the attempt inside one response, and attack
the keypad rather than the gate. Eleven ideas, eleven files.

Two further ideas are real and are **not** counted here, because the loader did not generate them
and inflating the total with things it did not generate would be the same dishonesty as padding:
inheriting another call's authentication, and completing a PIN with characters that are digits to
Unicode but not to a keypad. Both are tested in `tests/test_redteam.py`.

Reaching 20 to 30 would take a wider system, not a longer list — more tools, more agents, or an auth
state with more than two values. When Phase 5 adds `list_transactions`, `block_card` and escalation,
every idea here widens with them for free, and the ideas that only make sense against a
confirmation-and-idempotency path become writable for the first time.
