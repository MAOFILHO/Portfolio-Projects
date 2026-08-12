"""The single, shared no-input/no-match retry ladder -- `docs/phase4/DIALOGUE-POLICIES.md` §7, reused
UNMODIFIED by the barge-in repair path (§6.2). **One counter, not two** -- Marco's explicit integration
requirement, since a second, uncounted loop is exactly the failure mode this design exists to prevent.

Nothing else anywhere in `agents/` increments a retry count by any other mechanism -- `nodes/repair.py`'s
`handle_no_match_or_barge_in` node is the ONLY place this module's `record_attempt` is called, regardless
of whether the triggering event was a normal no-match or an inconclusive barge-in (see that module's
docstring for how the two triggers are unified into one code path, not just one counter).
"""

from __future__ import annotations

RETRY_CEILING = (
    2  # DIALOGUE-POLICIES.md §7: two consecutive no-input/no-match events, then escalate
)


def record_attempt(retry_counts: dict[str, int], key: str) -> dict[str, int]:
    """Increments the shared counter for `key` (a slot name, or a turn-level clarifying-question key for
    intent-level ambiguity per `INTENT-TAXONOMY.md` §3). Returns a NEW dict -- state updates in this
    codebase are always read-then-write-the-whole-value, never an in-place mutation of what a node was
    handed, so a node can never accidentally share a mutable dict object with a previous state snapshot.
    """
    updated = dict(retry_counts)
    updated[key] = updated.get(key, 0) + 1
    return updated


def ceiling_reached(retry_counts: dict[str, int], key: str) -> bool:
    return retry_counts.get(key, 0) >= RETRY_CEILING


def reset_attempts(retry_counts: dict[str, int], key: str) -> dict[str, int]:
    """Called on a successful capture. Clears `key`'s counter so an earlier failed attempt on the same
    slot doesn't count against a *later, unrelated* struggle on that same slot within a longer call.
    """
    updated = dict(retry_counts)
    updated.pop(key, None)
    return updated
