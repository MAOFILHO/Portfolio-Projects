# Review criteria

Process change, Marco, 2026-08-14, adopted mid-`D83`. Every report gets self-reviewed against §1 before it
is sent, reports fire only at the points §2 names, and every report opens with §3's header. This document
is short on purpose, same reasoning as `TESTING-CONVENTIONS.md` — a convention nobody re-reads is worth
less than a checklist actually run before sending.

---

## 1. The checklist

Run before sending any report. State in the report which of these were run and what each one caught (or
that it caught nothing, if nothing applied) — a checklist that isn't shown as run is indistinguishable from
one that wasn't.

1. **Could this protocol have produced the opposite result?** If a check can only ever confirm what was
   already believed, it isn't a check. Ask what evidence would have shown the opposite conclusion, and
   confirm that evidence was actually looked for.
2. **Is any "verified" claim actually asserted-but-unchecked?** `D80`, `D82`, the `D83` etag claim, the
   unrun cleanup step — one class of defect, repeated: a comment, a plan description, or a prior report
   said something was true, and nobody checked it against the artifact before relying on it again.
3. **Can an infra error be scored as a result?** Every harness needs an invalid state that aborts rather
   than silently producing a number. `D81`: a codehook exception must not be recorded as an intent
   classification, a cost, or a pass/fail — it has to be its own outcome.
4. **Cost below estimate → liveness check before reading results.** `§11.3` in `RESULTS.md`: an unexplained
   underspend is at least as likely to mean part of the pipeline never ran as it is to mean the system got
   cheaper. Check what actually executed before trusting any accuracy or recall number from the same run.
5. **Do identical markers cover genuinely different paths?** The provenance split (`detection-pregraph` /
   `detection-graph`) exists because tagging both paths `"detection"` hid that they were different
   mechanisms with different failure modes. A shared label across distinct code paths is a place a real
   difference can go unnoticed.
6. **Has this check ever failed for the right reason?** A check that has only ever passed is untested — it
   has never been shown to distinguish the good case from the bad one it exists to catch. Prefer a check
   with a demonstrated failure (or a synthetic negative) over one whose green is unearned.
7. **Does this change a headline number's interpretation?** If yes, it goes in `RESULTS.md`, not a
   footnote or a status-line aside. A number that changes what a reader should conclude is a finding, not
   a detail.
8. **Anything touching `C1` is a gate, never a tradeable term.** `C1` does not get scored to unblock other
   work, does not get marked passing on partial evidence, and does not move because something else is
   waiting on it. Verified or not verified — nothing in between counts as progress on it.

## 2. When to report

Report at decision points only:

- Anything touching `C1`.
- Before any apply.
- Anything that gets scored or recorded.
- A new defect class (not a recurrence of one already filed).
- Anything that changes a headline number's interpretation.

Batch everything else — intermediate greps, ruled-out hypotheses, routine passes — into the next
decision-point report rather than sending it separately.

## 3. Report header

Every report leads with this header verbatim, filled in, then states only what changed since the last one:

```
Phase/Stage:
Open defects:
C1 status:
Blocked on:
Last apply + gate result:
```
