# Testing conventions

`ADR-013` decides the mock-scope boundary and builds the runtime guard. This document is the authoring-side
companion: what to actually do when writing a test or a verification script. It is short on purpose — a
convention nobody re-reads is worth less than a guard that raises, which is why most of the rule lives in
code.

---

## 1. The mock-scope rule

**No real-AWS call inside a `mock_aws()` scope.** Three facts behind it, in order of how often they are
misremembered:

1. **`mock_aws()` patches botocore process-wide, for every AWS service**, for the duration of its context —
   not just the service whose table you were creating.
2. **moto implements DynamoDB faithfully.** Running this project's DynamoDB paths against moto is the
   intended default, not a compromise.
3. **moto does not implement Bedrock.** It intercepts the call and returns something error-shaped. A
   moto-answered Bedrock call is never what you meant.

### What the guard does for you

`BotoBedrockConverseClient` and `BedrockEmbedder` refuse to construct while moto is patching, raising
`RealAWSCallInsideMockError`. You cannot make the Stage 8 mistake with those two.

**The remedy when you trip it is always the same: narrow the mock scope.** There is deliberately no override.
Concretely, the shape that fixed Stage 8:

```python
# Seed the moto-backed table, then LEAVE the mock scope before anything real happens.
with mock_aws():
    store = DynamoVectorStore(table_name="...", region=REGION)
    store.ensure_table()

# Real Bedrock, entirely outside the mock. The guard permits this; inside the block above it would not.
caller = BotoBedrockConverseClient(region=REGION)
```

Note what this shape costs: the moto table does **not** survive the scope exit, so it only works when the
real-call path does not need the mocked resource. When it does need both simultaneously, you have a genuine
design problem, not a scoping one — use a real resource for both, or fake at a higher level (inject a
`FakeBedrockConverseClient`) rather than reaching for a mock scope that spans a real call.

### What the guard cannot see

It fires on **client construction**, so these remain your responsibility:

- A client constructed *before* the mock scope opens and *used* inside it. Legal Python, still wrong.
- Real HTTP to anything that is not AWS. moto does not touch it, and neither does the guard.
- Any AWS service added later whose client is not guarded. If moto's coverage of it is partial, guard it —
  `ADR-013`'s table is the decision record, and adding a row is the change.

### Comment the boundary

Any test or script that mixes both backends states, at the mock boundary, which backend each call reaches.
One line. The Stage 8 script's own comment is the model — it names the bug it is avoiding, so a later reader
does not "simplify" the structure back into the failure.

---

## 2. Mock-by-default

Every AWS-touching component defaults to a local or mocked backend; reaching real AWS requires an explicit
flag, and reaching a *billable* real AWS requires cost-gate approval on top of that. This is Phase 3's
two-axis pattern (`--embeddings {mock,bedrock}`, `--vector-store {local,aws}`) and it holds everywhere.

Consequence for tests: **the unit suite runs with no AWS credentials and spends $0.00.** A test that needs
credentials to pass is misplaced — it belongs in a cost-gated verification script, not `tests/unit`.

---

## 3. Fakes vs. mocks vs. real

| Layer | Use | Example |
|---|---|---|
| **Injected fake** | Model behaviour. Deterministic, no network, no moto | `FakeBedrockConverseClient` — every router and graph test |
| **moto** | AWS services moto implements faithfully — DynamoDB here | `DynamoVectorStore`, `build_test_checkpointer` |
| **Real, cost-gated** | Verifying that the real thing behaves as the fakes assume | Phase 5 Stage 8; Phase 6's Tier B eval runs |

The third row is not optional garnish. Stage 8 exists because a fake asserts what its author expected, and
the two real divergences it found (`RentalTowingEntitlement` redundancy recurring; classification matching
assumptions exactly) could not have come from the fakes. Fakes prove the wiring; only real calls prove the
assumption.

---

## 4. Canary tests

A test whose job is to detect that an **external mechanism this project depends on has moved** — not to test
this project's code. Currently one: `test_canary_moto_internal_still_flips`.

They look deletable during a cleanup, because they assert something about a dependency rather than about us.
They are not. The one we have is the only thing preventing a moto upgrade from silently disarming
`ADR-013`'s guard, and its failure mode without the canary is a mechanism that quietly permits everything
while every test still passes. **Mark them, keep them, and treat a canary failure as "the mechanism moved,"
not as a flaky test to skip.**
