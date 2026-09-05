# 02: Full eight-task review suite

**What to build:** The remaining seven `stateful_session` tasks (eight
total with the Ticket 01 proof task), each asking the agent to post several
review comments on a seeded change request and submit a verdict.

**Status:** done

- [x] 8 change requests seeded across 4 repos (`billing-service`,
      `checkout-web`, `auth-service`, `notifications-service`), additive to
      `backend/seed.py`
- [x] 7 new tasks under `tasks/stateful_session/standard/reviews/`, varying
      verdict (`approved`/`changes_requested`) and comment count (2-3)
- [x] `tests/test_verify_stateful_session.py` generalized to a parametrized
      table across all 8 tasks (32 tests)
- [x] `test_task_neutrality_stateful_session.py` (already added in Ticket
      01) passes across all 8

**Design decision confirmed with the user:** every task's instruction adds
a checkpoint requirement so the baseline can't collapse its resend cost into
one call (see Ticket 01's flagged gap). Final wording avoids implying a
"save" step that only the baseline has: "Post these review comments one at
a time and in order — do not combine them into a single call."

**Two real bugs caught and fixed during live spot-checks** (`webhook_retry`,
3 comments, run against gpt-4.1-mini on both servers):

1. Neither server could look up a change request by title — only by id.
   The pattern agent guessed the wrong id and silently reviewed the wrong
   change request. Root cause: no discovery tool existed once the proof
   task's lucky id-1 guess wasn't available. Fixed by adding `GET
   /change-requests` to the backend and a symmetric `list_change_requests()`
   tool to both servers (read-only, identical on both, doesn't touch the
   resend-cost comparison).
2. The first checkpoint wording ("saving your progress after each one")
   led the agent to call `submit_review` early with an invented verdict
   `"pending"` to "save" its place — since the pattern flow has no separate
   save action, closing the session there lost nothing yet posted, but the
   agent then reopened a second session and redid all 3 comments, leaving a
   duplicate first comment and failing verification. Root cause: the
   checkpoint instruction has no pattern-side action to map to (`add_comment`
   already persists as it goes). Fixed by rewording the instruction to avoid
   implying a save step, and by documenting on `submit_review` itself that
   it finalizes exactly once and is not a checkpoint.

**Flag for Ticket 03 (not a bug, an experimental finding):** on the
2-3-comment scale these 8 tasks use, `session_server` needs one mandatory
extra tool call (`start_review`) that `session_baseline` doesn't, and every
tool call resends the whole conversation as input tokens regardless of
argument size. On `webhook_retry`, `session_baseline` came in at 6 turns /
7,024 input tokens and `session_server` at 7 turns / 8,503 — the opposite
of ADR 0007's prediction. The baseline's resend-cost argument bloat is real
but small at this scale; the fixed per-turn overhead dominates it. Ticket 03
should report this as a real result, not treat it as something to fix by
further reshaping the tasks — the aggregate over all 8 tasks and 3 runs may
still show the predicted direction on a bigger-comment-count task, but that
needs the actual run, not another live spot-check.

## Comments
