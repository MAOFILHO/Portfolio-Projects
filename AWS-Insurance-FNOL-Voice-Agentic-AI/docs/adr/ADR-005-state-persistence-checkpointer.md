# ADR-005: LangGraph state persistence — adopt `langgraph-checkpoint-aws`'s DynamoDB backend, keyed on the Connect contact ID; do not hand-write a custom `BaseCheckpointSaver`

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

`PROJECT_STATE.md` carried an assumption from Phase 0/1 into the Phase 2 required-ADR list: *"No official
`langgraph-checkpoint-dynamodb` exists; we write a `BaseCheckpointSaver`."* That assumption is **corrected
here, openly, rather than carried forward uncorrected** — a live check today (2026-08-11) found it is no
longer accurate, and `CLAUDE.md`'s own instruction to "prefer boring, well-supported libraries... justify
every new dependency" cuts against writing a custom implementation the day a maintained one exists.

### What changed since Phase 0/1

**`langgraph-checkpoint-aws`** (PyPI, maintained under the `langchain-ai` GitHub org, in the
`langchain-ai/langchain-aws` repo) currently ships a DynamoDB-backed checkpoint saver — with automatic S3
offloading for any checkpoint exceeding 350 KB — alongside Bedrock AgentCore Memory and Valkey/Redis
backends. Current version **1.2.1, released 2026-08-07**, four days before this ADR. This is materially
different from the community, single-maintainer packages that also surfaced in the same search
(`langgraph-checkpoint-amazon-dynamodb`, maintained by one individual off a personal GitHub repo, not an
org) — provenance matters here, and this ADR distinguishes them rather than treating "something on PyPI
called langgraph-checkpoint-*-dynamodb" as fungible.

### The security finding that had to be checked before adopting it

A checkpoint-deserialization vulnerability chain was found in the same research pass and had to be run down
rather than left as a search-snippet title: **CVE-2026-28277**, unsafe msgpack deserialization in
`langgraph`'s checkpoint decoder allowing arbitrary-callable execution from a forged checkpoint payload,
chained in practice with **CVE-2025-67644** (SQL injection into `get_state_history()` used to plant the
forged row) against **SQLite** checkpointers, and a parallel **CVE-2026-27022** against **Redis**
checkpointers. Fixes: `langgraph` ≥1.0.10, `langgraph-checkpoint-sqlite` ≥3.0.1,
`@langchain/langgraph-checkpoint-redis` ≥1.0.2, patched December 2025–March 2026.
(<https://labs.cloudsecurityalliance.org/research/csa-research-note-langgraph-rce-chain-20260614-csa-styled/>)

**Verified as not blocking, but treated as a live constraint, not dismissed:** the reported exploit chain is
specific to SQLite and Redis checkpointers — it is not reported against DynamoDB, and this project was never
going to use SQLite or Redis regardless (SQLite has no place in a serverless Lambda architecture with
concurrent invocations; Redis/ElastiCache is not on this project's service list and would add a new stateful
service outside constraint 17's fixed list). The root-cause primitive (unsafe msgpack deserialization) is
fixed at the `langgraph` core level in ≥1.0.10; the version this project will pin (current: **1.2.11**,
released today) is already far past the patched line. This ADR does not treat "unaffected backend" as
license to skip hardening: **`LANGGRAPH_STRICT_MSGPACK=true` (or an explicit `allowed_msgpack_modules`
allow-list) is adopted as defense-in-depth regardless of backend**, consistent with this project's existing
posture of hardening beyond the minimum a specific reported exploit requires (the same posture that bans
`cert_reqs='CERT_NONE'` and hardcoded OTP bypasses found in the Phase 0 source corpus, rather than waiting
for a specific proof of exploitability against *this* architecture).

## Decision

**Adopt `langgraph-checkpoint-aws`'s DynamoDB backend.** Do not write a custom `BaseCheckpointSaver`. Key
every checkpoint's `thread_id` on the **Connect contact ID**, exactly as already committed to in Phase 0/1
design — this ADR changes the implementation, not the partitioning scheme.

**Concretely:**
- Pin `langgraph==1.2.11`, `langgraph-checkpoint==4.2.0`, `langgraph-checkpoint-aws==1.2.1` — exact versions,
  not floors, per `CLAUDE.md`'s "pin exact versions, justify every new dependency in one line" rule. One
  line: *`langgraph-checkpoint-aws` gives a maintained, security-patched DynamoDB checkpointer with S3
  overflow handling for free, avoiding ~150–300 lines of custom persistence code and its own test surface.*
- Set `LANGGRAPH_STRICT_MSGPACK=true` unconditionally, as defense-in-depth against the deserialization
  primitive in CVE-2026-28277, independent of this backend's exposure to the specific reported chain.
- Accept the S3-offload dependency for any checkpoint over 350 KB. A short FNOL conversation's graph state
  (slot values, a short reasoning trace, tool-call summaries) is expected to sit well under that threshold,
  but **this is an assumption to verify empirically in Phase 5/9 with a real checkpoint-size measurement, not
  asserted as certain here** — consistent with the project's "no invented metrics" discipline applied to
  engineering assumptions, not only documentation claims.
- **Phase 9 must include a contract test asserting the installed `BaseCheckpointSaver` interface matches
  what `langgraph-checkpoint-aws` implements against**, because the checkpointer ecosystem has shipped two
  major version bumps (`langgraph-checkpoint` 3.0.0 → 4.0.0) in the last ten months, and separate GitHub
  issues report breaking changes even within minor version bumps. A version-pinned dependency that silently
  drifts out of contract on an unrelated upgrade is exactly the kind of failure this project's "test first,
  watch it fail" discipline exists to catch before it reaches a live call.

### Rejected: hand-written custom `BaseCheckpointSaver` (the Phase 0/1 assumption)

**Rejected because the premise it rested on — "no official/maintained DynamoDB checkpointer exists" — is no
longer true**, verified today. Writing ~150–300 lines of custom persistence/serialization code and its own
test suite, against a `BaseCheckpointSaver` contract that has itself changed twice in ten months (adding
`copy_thread`/`prune`), would mean maintaining that surface ourselves indefinitely for no capability gain
over the maintained package. This is recorded as a correction to a carried-forward assumption, not a quiet
substitution — the same standard this project holds itself to elsewhere (see the D15/D16 corrections in
`PROJECT_STATE.md`'s Phase 1 log).

### Rejected: other community DynamoDB checkpointer packages

`langgraph-checkpoint-amazon-dynamodb` and similar single-maintainer PyPI packages were found in the same
search. Rejected on provenance grounds: a personal GitHub repo with one listed maintainer, versus
`langgraph-checkpoint-aws` maintained under the `langchain-ai` org with an Aug 7, 2026 release four days
before this ADR — the same standard of "boring, well-supported" this project already applies to every other
dependency choice.

### Rejected: SQLite or Redis-backed checkpointers

Never live options under constraint 17 (DynamoDB is the fixed state-store service for this region) or the
banned-services list (Redis/ElastiCache is not on the approved list and would add a new stateful service
with its own operational surface). Noted here only because both were the two backends actually named in the
CVE chain above — not the deciding factor, since they were already excluded on architectural grounds, but
worth recording that the exclusion also happens to avoid the two backends with a documented exploit history.

## Consequences

**Positive:**
- Avoids building and maintaining custom persistence/serialization code against a contract that has already
  changed twice in ten months.
- Gets S3 checkpoint-overflow handling, a real edge case for a multi-slot conversation with a long
  reasoning trace, without designing it ourselves.
- The security review this ADR required (running down the CVE chain rather than citing the search snippet
  uncritically) is now on record, and the mitigation (`LANGGRAPH_STRICT_MSGPACK`) is adopted regardless of
  whether DynamoDB specifically was ever named in the exploit.

**Negative / accepted residual risk:**
- A third-party (if `langchain-ai`-maintained) dependency now sits on the state-persistence critical path
  instead of code this project fully controls. Mitigated by exact version pinning and the Phase 9 contract
  test, not eliminated.
- The 350 KB S3-offload threshold assumption is unverified until Phase 5/9 measures real checkpoint sizes —
  flagged explicitly rather than assumed silently.
- If a future `langgraph-checkpoint` major bump changes the `BaseCheckpointSaver` contract again, this
  dependency requires a coordinated upgrade of both packages together, verified by the contract test before
  either is bumped in production.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| Hand-written custom `BaseCheckpointSaver` (Phase 0/1 assumption) | Rejected — premise no longer holds | A maintained, `langchain-ai`-org DynamoDB checkpointer now exists; writing one from scratch buys nothing over adopting it |
| Community single-maintainer DynamoDB checkpointer packages | Rejected | Provenance — personal repo vs. org-maintained package updated four days before this ADR |
| SQLite / Redis checkpointers | Never live | Excluded by constraint 17 / banned-services list; also the two backends named in the CVE-2026-28277 exploit chain |
| **`langgraph-checkpoint-aws` (DynamoDB backend)** | **Chosen** | Maintained, actively updated, S3-overflow handling included; adopted with exact version pinning, `LANGGRAPH_STRICT_MSGPACK`, and a Phase 9 contract test as explicit mitigations |

## Sources

- <https://pypi.org/project/langgraph-checkpoint-aws/>
- <https://pypi.org/project/langgraph-checkpoint-amazon-dynamodb/>
- <https://pypi.org/project/langgraph/>
- <https://pypi.org/project/langgraph-checkpoint/>
- <https://github.com/langchain-ai/langgraph/releases/latest>
- <https://labs.cloudsecurityalliance.org/research/csa-research-note-langgraph-rce-chain-20260614-csa-styled/>
- <https://blog.langchain.com/langgraph-v0-2/>
- <https://github.com/langchain-ai/langgraph/issues/5862>, <https://github.com/langchain-ai/langgraph/issues/5385>

All facts fetched live on 2026-08-11 via a background research agent, per the project's standing rule to
verify against current sources rather than memory. Corrects the Phase 0/1 carried-forward assumption in
`PROJECT_STATE.md`'s Phase 2 ADR table; that table is updated to point here rather than left saying "no
official package exists."
