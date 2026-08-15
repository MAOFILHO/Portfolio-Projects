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

## 4. Two review tiers

Process change, Marco, 2026-08-14. Classify every proposed action against these two tiers **before**
reporting on it — the tier decides whether a report is a proposal awaiting approval or an outcome already
reached, and picking the wrong one in either direction is itself a defect: asking permission for something
approve-and-go already covers wastes a round trip on nothing; running something full-review requires without
stopping first removes the one point where it could have been caught before it happened.

**FULL REVIEW — propose, stop, wait for approval:**

- Anything touching `C1` or its measurement.
- Anything producing a number that enters `RESULTS.md` as a result.
- Real spend above ≈$1, or an irreversible change.
- `terraform apply`, a redeploy, or anything altering deployed state.
- A new defect class, or a headline conclusion changing.

**APPROVE AND GO — do it, then report once with the outcome:**

- Measurements under ≈$1.
- $0 local diagnostics, profiling, doc reads, CloudWatch reads.
- Reversible code changes not yet deployed.
- Record fixes, write-ups, corrections to committed docs.

**For approve-and-go: do not ask permission and do not propose options for selection.** Pick the approach,
state the choice in one line, run it, report the result. This is the same discipline §2 already applies to
*when* to report, extended to *whether to ask first* — a decision point earns a stop; routine execution
inside an already-approved bound does not, and asking anyway is a cost of its own, paid in round trips instead
of dollars.

**If something reclassifies mid-task, stop there and say why.** A task that starts approve-and-go and turns
up a `C1` interaction, an unplanned deploy, or a number bound for `RESULTS.md` does not finish under the tier
it started in — it stops at the point of reclassification, not at the end, and the report states which
condition fired and where.

**Standing constraints are unchanged and outrank both tiers — neither tier can license what these forbid:**

- No billable AWS resource without `APPROVED: <phase name>`.
- Never create the Connect instance or DID.
- `PROJECT_STATE.md` updated before any session ends.
- `C1` is a gate, not a tradeable term.

## 5. Phase close-out completeness

Added 2026-08-14 (`D85`), Marco, after `CF4` was assigned to Phase 9 (2026-08-12) and Phase 9's close-out
(`RESULTS.md` §11.23, `PROJECT_STATE.md` 2026-08-14) named zero of the carry-forward items by number —
`CF4` did not appear, discharged or otherwise, and the gap was found only because the next phase's scoping
went back to the "Carried forward" table directly rather than trusting the close-out's own summary. The
carry-forward table records an *assignment*; nothing before this section enforced that assignment against
completion, so a close-out could — and did — drop an item silently, in the direction that looks like
nothing is wrong.

**A phase close must enumerate every carry-forward item whose `Owner phase` names the phase closing**, and
resolve each one exactly one of three ways — no fourth option:

- **discharged** — the item's own row updated with how and where;
- **re-assigned** — to a named future phase, with the re-assignment itself written into the "Carried
  forward" table's `Owner phase` column, not left implicit in prose;
- **explicitly dropped**, with a stated reason.

An item silently absent from a close-out is not equivalent to any of these — it is the defect this section
exists to prevent. This is additional to, not a substitute for, §3's report header: "Open defects:" invites
whatever the closing session happened to remember, while this requires an affirmative pass over the
carry-forward table itself, row by row, for every row owned by the phase closing.
