# ADR-013: Mock scope and the real-AWS boundary — a runtime guard, not a convention; scoped to services moto does not faithfully implement

**Status:** Accepted (Phase 6). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-12

---

## Context

Phase 5 Stage 8 produced a bug worth an ADR rather than a fix-log line.

A verification script opened `with mock_aws():` to seed a moto DynamoDB table, and — still inside that
block — constructed a real `bedrock-runtime` client and issued a real `Converse` call. moto intercepted it
and answered with a fabricated 404, *"Not yet implemented."* The call never reached AWS. Nothing raised.
The script was one `print` away from reporting on a response AWS never sent.

Marco's framing at Phase 5 sign-off, which is the reason this is an ADR: **the pattern generalises.**
Phase 9's integration suite is where mocked and real backends get mixed most heavily, and the same
false-verification would recur there with nothing to catch it.

### Why this is worse than an ordinary bug

It fails **silently, in the direction of looking like it worked.** A test that wrongly fails is fixed within
minutes because it is loud. A test that wrongly passes is indistinguishable from a test that is right, and
can sit in the suite for the life of the project certifying a code path that was never exercised. Every
number this project publishes from Phase 6 onward rests on the assumption that a call reported as real *was*
real.

### The two facts that actually determine the rule

1. **`mock_aws()` is process-wide, for every AWS service, for the duration of its context.** It is not
   scoped to the service whose table you happened to be creating. This was the specific wrong assumption.
2. **moto's coverage is not uniform, and the difference matters more than the mocking does.**
   - moto **implements DynamoDB faithfully.** A DynamoDB call answered by moto is a *deliberate, correct
     substitution* — the basis of `make ingest`'s free default (`--vector-store local`), of
     `build_test_checkpointer`, and of most of this project's test suite.
   - moto **does not implement Bedrock.** It has just enough of a `bedrock-runtime` backend to intercept the
     request and return something error-shaped. There is no scenario in this project where a moto-answered
     Bedrock call is the intended behaviour.

A blanket "never mix moto and real clients" rule would be easy to state and would break the DynamoDB pattern
that is working correctly. The real distinction is not mocked-vs-real; it is **faithfully mocked vs.
fabricated.**

## Decision

### 1. The rule

**No real-AWS call may be made inside a `mock_aws()` scope.** Mock scopes are opened as narrowly as possible
and closed before any real client is constructed. Any test or script mixing both states, in a comment at the
mock boundary, which backend each call reaches.

### 2. Enforced at runtime, on the clients that can be fabricated

`src/fnol_voice_agent/aws/mock_guard.py` provides `moto_is_patching()` and `assert_real_aws_allowed(what)`.
The guard is called from the constructors of the clients for services this project only ever calls for real:

| Client | Guarded? | Why |
|---|---|---|
| `BotoBedrockConverseClient` (`aws/bedrock_router.py`) | **Yes** | moto fabricates. The exact Stage 8 locus |
| `BedrockEmbedder` (`knowledge/ingest.py`) | **Yes** | Same service, same fabrication risk |
| `DynamoVectorStore` | **No, deliberately** | Dual-mode by design; moto is faithful and is the default |
| `build_checkpointer` / `build_test_checkpointer` | **No, deliberately** | Same; `build_test_checkpointer` is *meant* to run inside `mock_aws()` |

The "no" rows are asserted by a test (`test_dynamodb_paths_are_deliberately_not_guarded`) rather than merely
omitted, so a future change that guards everything "for consistency" has to delete a test explaining why not.

### 3. No escape hatch

No `allow_inside_mock=True`, no environment variable, no opt-out. The correct remedy for tripping the guard
is always the one that actually fixed Stage 8: **narrow the mock scope.** An escape hatch would be reached
for first and understood second, and would end up certifying the precise pattern this ADR exists to stop.

### 4. The mechanism, and its honest weakness

`moto.core.models.botocore_stubber` is a module-level singleton whose `.enabled` flag is set True on
`mock_aws` entry and False on the outermost exit. Verified empirically against **moto 5.0.28** for the
context-manager form, the decorator form, and nesting.

**It is a moto internal, not a documented public API.** The Phase 6 build plan committed to attempting a
runtime guard and to stating its real strength rather than implying a guarantee — the guard turned out to be
fully buildable, so the planned fallback (convention plus a lexical CI grep) is not needed and was not built.
But the internal can move.

The failure mode of a moved internal is the same silent-permissive failure this ADR is about:
`moto_is_patching()` would return False forever and no other test would go red, because a disarmed guard
raises nothing and everything keeps passing. **`tests/unit/test_mock_guard.py::test_canary_moto_internal_still_flips`
is the countermeasure**: it asserts the flag observably flips inside a real `mock_aws()` block, so a moto
upgrade that relocates the internal fails the build loudly instead of disarming the guard. moto is pinned;
the canary is what makes the pin's expiry visible rather than silent.

This is the residual risk, stated rather than papered over: **the guard is only as reliable as the canary is
maintained.** Deleting the canary because "it does not test any of our code" would remove the only thing
standing between a moto upgrade and a silently disabled safety mechanism.

## Consequences

- The Stage 8 bug cannot recur for Bedrock: the client refuses to construct. Regression-tested directly.
- Phase 9's integration suite inherits the guard automatically — it is in the client constructors, not in
  test-local discipline that a new test author might not know about. This is `CF4`'s discharge mechanism.
- `docs/TESTING-CONVENTIONS.md` carries the authoring-side rule for cases the guard cannot see (a real HTTP
  call to a non-AWS service, a real call made through a client constructed before the mock scope opened).
- A moto major-version upgrade now has a required step: confirm the canary still passes, and re-point
  `moto_is_patching()` if it does not.

## Alternatives considered

**Convention plus a lexical CI grep** (the Phase 6 plan's stated fallback). Would flag a real-client
construction textually inside a `mock_aws()` block. Rejected once the runtime guard proved buildable: the
grep cannot see a client constructed in a helper three call-frames away, which is exactly how the Stage 8
bug would look after any refactor. Kept on record as the fallback if moto ever makes runtime detection
impossible.

**A pytest fixture that fails any test touching both.** Rejected: it protects the test suite and nothing
else. The Stage 8 bug was in a script, not a test, and Phase 6/7 will write more such scripts.

**Guarding every AWS client uniformly.** Rejected for the reason in Context: it would break the faithful,
intentional DynamoDB mocking this project's zero-cost default depends on. Uniformity here would be a rule
that is simpler to state and wrong.
