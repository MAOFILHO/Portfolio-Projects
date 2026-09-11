"""Cost caps (B4). **The only brake that exists.**

`spendingLimit: Off` is confirmed on the subscription, so Azure will not stop spend at any
threshold. Nothing else in this system refuses a call on cost grounds, and B4's target is 0
overruns and **0 fail-open events** -- the second half being the one that needs care.

Two caps, completed in Phase 5 (issue #49):

  * **Per call**: 20 turns and 5 minutes. Phase 1 sized these and neither moves.
  * **Per day**: an aggregate minute cap across every call. There was none until Phase 5 -- a
    hundred calls in a day, each individually inside its five-minute limit, was a hundred calls
    this project had no mechanism to refuse.

**The daily cap fails closed, and the store is where that is decided.** A budget that cannot be
read takes the same branch as one that is spent, because an unknown budget is not permission. The
constants here are the numbers; `call_records/` holds the state and `realtime/session.py` holds the
branch.

Moved out of the Phase 1 relay module unchanged (Phase 2.1 restructure, issue #17): same
values, same behaviour, now in the home docs/PLAN.md's layout gives them.
"""

MAX_CALL_TURNS = 20
MAX_CALL_SECONDS = 5 * 60

#: The day's aggregate budget, in call minutes, across every call (issue #49).
#:
#: **120 minutes.** At the per-call ceiling of 5 minutes that is 24 full-length calls a day, and a
#: demo call is nearer 2 minutes, so it is roughly 60 real ones -- far more than this project's own
#: R-08 usage model needs and far less than an unbounded bill. The number is a ceiling on the
#: failure mode, not a forecast of usage: what it exists to stop is a loop, a wardialler, or a
#: number that ends up on a list somewhere, none of which care what the average call looks like.
MAX_DAILY_MINUTES = 120.0

#: How long the closed path is allowed to take, end to end. **The brake must not become the cost.**
#: Long enough for one short spoken sentence and no longer -- a refusal that ran for five minutes
#: would spend money to say it was not spending money.
MAX_CLOSED_CALL_SECONDS = 20.0

#: And the turn bound on the same path. One response cycle: the closed sentence, spoken once.
#: Enforced by the relay rather than by the model choosing to be brief.
MAX_CLOSED_CALL_TURNS = 1


class DailyBudgetSpent(Exception):
    """The day's minutes are gone, or the ledger could not be read. Both take the closed path.

    **The two are deliberately one exception.** B4's fail-closed rule is that an unknown budget
    never serves a call, and a caller who could tell "we are closed" from "we could not check"
    would have been handed a probing oracle for exactly the condition that costs money. One type,
    one branch, one sentence.
    """


class CallLimitExceeded(Exception):
    """Raised when MAX_CALL_TURNS or MAX_CALL_SECONDS is hit. Ends the call -- not a relay
    failure, so the session logs and returns instead of propagating this."""
