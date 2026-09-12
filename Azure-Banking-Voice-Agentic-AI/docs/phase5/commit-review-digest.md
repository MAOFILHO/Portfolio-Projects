# `e42c063..HEAD` — a reading order for 27 commits

Written 2026-09-12 because Marco chose a digest over reading the raw log. **This is a reading order,
not a substitute for reading.** The project's own rule is that a human looks at the diff on the
never-auto-accept paths, not at a description of it, so every section below ends with the command
that shows the real thing.

**What I actually read, and what I did not.** I read the full cumulative diff of `dispatch/gate.py`,
`auth/authenticator.py` and `transport/acs.py`. For `dispatch/tools.py` and `realtime/session.py` I
read the changed function signatures and the commit messages, not every line — they are the two
largest surfaces here and the two I am least able to vouch for. Everything else below is
characterised from file statistics and commit messages. **Where I say "unchanged", I checked; where I
summarise, I did not.**

Phase 4 is commits 1 to 7, Phase 5 is 8 to 25, and 26 to 27 are this session's documentation.

---

## Tier 1 — the never-auto-accept paths, roughly 45 minutes

These are the four files the project rule names. Read them cumulatively rather than commit by
commit: the end state is what ships, and three of the four reach it in one or three steps.

### `dispatch/gate.py` — +86 / −26 across 3 commits

```
git diff e42c063..HEAD -- '*dispatch/gate.py'
```

Touched by `db34d10`, `777d8b2`, `9cd37e6`.

The permission table went from **4 rows to 6**. A third agent, Cards, was added. `list_transactions`
joined the banking authenticated row and `block_card` became the Cards authenticated row. Both are
banking operations and both sit behind authentication.

**The one change that moves B1's surface**: `escalate_to_human` is now granted in **every** row,
including the three anonymous ones. You signed this off on 2026-09-11 and the reasoning is in the
file. It is still the single thing on this path most worth re-confirming with the code in front of
you, because it is the sentence this project repeated for two phases and no longer holds.

**`is_allowed()` itself is untouched.** No hunk in the cumulative diff reaches the function body. The
whole change is the data table and its comments. Confirm that yourself, because it is what makes the
rest of this file a configuration review rather than a logic review.

### `auth/authenticator.py` — +39 / −13, one commit

```
git show 18d6a4a -- '*auth/authenticator.py'
```

Three changes, none of them to the keypad protocol. `_press` stopped returning a
`(outcome, submission)` tuple whose first half was empty exactly when the second was not, and now
returns either an outcome or a small object holding the completed entry. That object **refuses to
print itself**, so four keyed digits cannot reach a traceback or a debugger line. The success
sentence changed from "you're verified" to "that's confirmed", because the glossary proscribes
*verified* for the auth state.

The digit accumulation, the PIN length, the clear key, the pound key and the one-way settled check
all read the same before and after.

### `transport/acs.py` — +57 / −1, one commit

```
git show 395d6c5 -- '*transport/acs.py'
```

Pure addition: a table of spelled tone names mapped to single characters, and a function that
normalises one tone. It accepts both vocabularies because Azure documents no schema for this frame
and the two candidate vocabularies disagree on exactly the two keys that matter. Anything
unrecognised passes through unchanged rather than being dropped or guessed at, and the function never
raises.

**This does not settle the wire format.** The acceptance call must still press `*` and `#`.

### `dispatch/tools.py` — +220 / −12 across 5 commits

```
git diff e42c063..HEAD -- '*dispatch/tools.py'
```

Touched by `db34d10`, `777d8b2`, `9cd37e6`, `581b8f4`, `59a3d93`.

The largest of the four, and the one where my reading is thinnest. Every tool handler changed
signature from taking the core-banking client to taking a call scope object. Three handlers were
added: transactions, card block, and escalation. Helpers were added for idempotency keys and event
identifiers.

**Look hardest at `_escalate_to_human`.** It is reachable while the call is anonymous and it writes
to the call-record store, so it is a write path that exists before authentication. The gate's own
comments argue it never touches the core-banking client. Check that claim against this file rather
than against that comment.

---

## Tier 2 — the largest surface, roughly 30 minutes

### `realtime/session.py` — +433 / −27 across 12 commits

```
git diff e42c063..HEAD -- '*realtime/session.py'
```

Twelve commits and the largest single diff in the range. There is no clean way to read this
cumulatively, because it grew by accretion across the whole phase. New entry points appeared for the
budget check, the closed call, and minute recording, and `run_call` gained three parameters.

This is the file I can vouch for least and the one carrying the most new behaviour. If your hour runs
out, it should run out here rather than in Tier 1.

---

## Tier 3 — everything else, skim or skip

| what | commits | why it is low risk |
|---|---|---|
| The mock core banking service | `0270a63`, `754e746` | A separate service holding fake money. Its own 90 tests. |
| The call-record store | `9cd37e6`, `5510d1e`, `171f50f` | +354 lines, all new, no existing behaviour changed. Not yet reachable: no Storage account exists. |
| Cost caps | `5510d1e`, `581b8f4` | +50 / −5 on B4's brake. Small, and blocking in CI by construction. |
| Tests and red-team corpus | throughout | Roughly half the range by line count. 491 plus 90 passing. |
| Bicep modules | `6347342` | Written unapplied. Compile clean as of 2026-09-12. |
| Documentation and handoffs | `071d428`, `cb4f0e9`, `79ceb68`, `01a2df5`, `4c5abb6`, `3726248`, `b2ee47f`, `a80cbfb` | No code. |

---

## Three things to decide, not just read

1. **Escalation while anonymous.** Signed off, but it is the corollary change, and it is what the
   gate's own comments spend the most words defending.
2. **`realtime/session.py` at +433 lines.** Whether that is a review or a rewrite is your call.
3. **Two Bicep header edits are uncommitted**, waiting on you. They touch billable resources.
