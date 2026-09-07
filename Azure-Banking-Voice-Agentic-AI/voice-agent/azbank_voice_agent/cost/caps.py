"""Per-call cost caps (B4).

B4 (CLAUDE.md): no call exceeds 5 min / 20 turns, fails closed. What lives here is a
Phase-1-sized guard only -- a bare per-call counter and wall-clock timeout. Full B4
(per-session AND daily caps, a cost store, fail-closed if that store is unreachable,
T-B4-FAILCLOSED) is Phase 5 scope (docs/PLAN.md:621-624) -- not built here.

Moved out of the Phase 1 relay module unchanged (Phase 2.1 restructure, issue #17): same
values, same behaviour, now in the home docs/PLAN.md's layout gives them.
"""

MAX_CALL_TURNS = 20
MAX_CALL_SECONDS = 5 * 60


class CallLimitExceeded(Exception):
    """Raised when MAX_CALL_TURNS or MAX_CALL_SECONDS is hit. Ends the call -- not a relay
    failure, so the session logs and returns instead of propagating this."""
