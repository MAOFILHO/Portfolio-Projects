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

## 6. Grep/sweep-based claims — recall is bounded by the search terms, not the corpus

Added 2026-08-15, Marco, after a git-mediated claim sweep (`RESULTS.md` §13.3) reported "zero new overclaim
types" from five search terms (`landed`/`pushed`/`merged`/`in the repo`/`committed`, 321 raw hits), and a
recall check (`RESULTS.md` §14.2) found the corpus's own vocabulary for the same class of claim
(`shipped`/`deployed`/`in place`/`at the monorepo root`/`verified at`) produced 573 *more* raw hits the
original sweep never touched — the conclusion happened to still hold, but the first pass's wording did not
say it was scoped to five words, and read as a claim about the corpus.

**A grep/sweep-based "zero found" or "N found" claim is a claim about the search terms run, not about the
text it was run over, until a recall check — an independent pass with differently-worded terms for the same
underlying claim — has been run and still agrees.** Same shape as `D80`/`D82` (§1.2): a check that only
confirms what it already looked for is not evidence about what it didn't.

**Every sweep report must state three things, not just the count:**

1. **The term list** — the exact strings searched, not "the usual terms" or a description of their intent.
2. **The raw hit count**, per term and total.
3. **Whether the non-matching-claim remainder was individually inspected or pattern-classified** — these are
   different strength claims (§14.2's own finding: a table reading "every hit is X or Y" is the latter, and
   saying so plainly is not a weaker report, it is an accurate one). If pattern-classified, keep the raw
   grep output on disk (not just its summary) until the next recall check, the way `/private/tmp/claimsweep/
   raw.txt` made this section's own finding checkable instead of asserted.

A sweep that has only ever been run with one term list is the same defect class as §1.6's check that has
only ever passed — not wrong, just unproven at the scope its conclusion is being read at.

## 7. Activity signals are not effect signals

Added 2026-08-16, Marco, after `D88`: the deployed OUTPUT guardrail's `ApplyGuardrail` call on a real
`CheckClaimStatus` fulfillment returned `sensitiveInformationPolicyUnits: 1` — the policy ran, a unit was
billed, the call succeeded, `FunctionError` was absent — and `masked: false`, `blocked: false`. Every
signal that looks like "this ran and something happened" was green. Whether the thing it exists to do
(intervene) actually happened required a separate, deliberate check of `action`/`masked`/`blocked`, not
the unit count. Scoping `D88` then found the guardrail was doing exactly what a Marco-approved v2->v3
config change (`docs/phase7/NOT-FIXED.md` #8) had deliberately made it do — but the finding that matters
here survives that outcome regardless: **a non-zero usage counter or a successful call proves the control
ran, never that it did what it exists to do.**

Same family as `D87`: fulfillment was broken for four of five ordinary intents while `LastUpdateStatus:
Successful`, a matching `CodeSha256`, and a bare `StatusCode: 200` all read healthy (`§1.2`'s own
precedent). `D87` was an activity signal standing in for an effect signal at the deploy-verification
layer; `D88` is the identical shape one layer up, at the safety-control layer. Two instances in one
session is enough to name the pattern rather than wait for a third.

**A control is unverified until something asserts its effect, not merely its activity.** Before treating
any of the following as evidence the control worked, name what effect-level signal was actually checked:

- A non-zero usage/cost counter (`guardrail_usage`'s `*PolicyUnits`, a billed-call count) — proves the
  policy was evaluated, not that it intervened. Check `action`/`masked`/`blocked` (or the equivalent
  outcome field), not the unit count.
- A `StatusCode: 200` / absent `FunctionError` / successful `Invoke` — proves the call returned cleanly,
  not that the intended code path ran (`D80`) or that the response means what it appears to (`D87`'s own
  `Delegate`-vs-`Close` distinction).
- A legal `dialogAction.type` (`Close`/`ElicitSlot`/`Delegate`) with `intent.state=Fulfilled` — proves
  *some* node reached a terminal state, not that it was the *intended* node (`RESULTS.md` §33's own finding:
  `_close()` echoes the event's original Lex-supplied intent name regardless of which internally-routed
  node actually produced the message, so a silent misroute to a different intent's node can still return
  a well-formed `Close`/`Fulfilled` for the intent Lex thinks is still in progress).

## 8. A defect fixed at one call site is not fixed until every site of that class is enumerated

Added 2026-08-16, Marco, after `D90` part 2 (`RESULTS.md` §34): `D84` (Phase 9) fixed `_elicit_slot()`'s
echoed-Lex-intent defect — building the returned intent from the graph's own `result["intent"]` instead of
`_intent_from(event)` — but left `_close()`, the sibling call site of the identical defect class, carrying
it for two more phases. The reason it survived that long: `ElicitSlot` raised a live Lex `ValidationException`
when the echoed intent and the elicited slot disagreed, which is what forced the fix to be found and forced
it to be verified; `Close` has no equivalent check, produces no loud failure either way, and was never
revisited once the noisy sibling went quiet.

**Absence of a loud failure is not evidence of correctness.** Same family as §1.6's never-failed check and
§7's activity-vs-effect distinction, one level further back: the risk here is not a signal being misread,
it is that the signal never fires at all for one member of a defect class while it does for another — and
that asymmetry alone, not anything about the underlying correctness, is what decided where the fix stopped.

**Before closing a defect described as "fixed," enumerate every call site of the same defect class, not
only the one whose failure was loud enough to be noticed.** Grep for the defect's shape (here,
`_intent_from(event)`), name every site found, and give each one an explicit disposition — fixed,
deliberately left as-is with a stated reason (`D90`'s escalation call sites, where echoing Lex's intent is
a different claim, not the same defect), or filed open — the same three-way disposition §5 already requires
for carry-forward items, applied here to call sites of one defect instead of phases of one project.

## 9. A summary carrying a scoped claim must cite its source line, and the scope must be verified against it

Added 2026-08-16, Marco, after a handoff document (`docs/handoffs/2026-08-16-phase11-midflight.md`, `RESULTS.md`
§38) was **explicitly instructed** to keep `C1`'s three canonical scope qualifiers intact — "these must
survive intact — this is the thing most likely to compress into 'C1 verified'" — and still, on first draft,
dropped one (topology-scope, collapsed into build-scope) and substituted a real-but-non-canonical item in
its place (k=1 sampling) without labelling it as a different kind of caveat.

**The direct instruction to preserve the claim was not sufficient to preserve it.** Summarization degrades
scoped claims by default — merging distinct axes that happen to co-occur (here: build identity and
topology, both properties of "the same `C1` run," but answering different questions), or restating a
qualifier from memory of its gist rather than from the words that state it. Telling the summarizer to be
careful is not a mechanism; re-reading the source is.

**Any summary, handoff, or post-`/compact` continuation that carries a scoped or qualified claim (a
"VERIFIED, but only under conditions X/Y/Z" statement, a caveat-bearing metric, a scope-restated finding)
must cite the specific file:line the claim was checked against, and that scope must be re-verified against
the cited source at write time — not restated from memory of an earlier read, however recent.** If the
claim has more than one independent qualifier, state each as its own bullet against its own citation rather
than merging them into prose that can silently drop or blend one. The mitigation that actually worked in
the `C1` case was not "write more carefully" — it was Marco asking for a source-checked verification before
accepting the summary's phrasing, which is the check this section now requires by default rather than on
request.
