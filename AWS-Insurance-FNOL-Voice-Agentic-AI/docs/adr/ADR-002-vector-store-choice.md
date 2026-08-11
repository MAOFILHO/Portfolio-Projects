# ADR-002: Vector store — DynamoDB (already in the fixed service list) with in-process brute-force cosine similarity, not S3 Vectors, not FAISS/sqlite-vec baked into the Lambda package

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

`PROJECT_STATE.md`'s Q4 named three candidates: S3 Vectors (GA in us-west-2 since Dec 2025), FAISS/sqlite-vec
baked into the Lambda deployment package, or DynamoDB with in-memory cosine similarity — explicitly **not**
OpenSearch Serverless, which is on the banned-by-default list. The synthetic policy corpus this vector store
serves (`CoverageQuestion`, the primary groundedness eval target, and `RentalTowingEntitlement`) is, by this
project's own design, small: a handful of synthetic policy documents authored in Phase 3, chunked into what
is expected to be low hundreds to low thousands of chunks — not a production insurer's full policy library.

S3 Vectors pricing was re-verified today, live, rather than estimated: **$0.06/GB-month storage, $0.20/GB
PUT, and a three-part query cost** — a request fee ($2.50/million queries), a tiered data-processed fee
($0.004/TB for the first 100K vectors in an index, down to $0.0004/TB above 10M), and a data-returned fee
($0.01/GB, with the first 512 KB per query free). No free tier exists for this service.

## Decision

**DynamoDB stores the embedding vectors and chunk text; retrieval is exact brute-force cosine similarity,
computed with numpy inside the Lambda process, over vectors loaded once per warm execution environment and
cached in memory across invocations of that environment.**

**Why this beats S3 Vectors at this project's actual scale:** at low hundreds to low thousands of chunks, an
approximate-nearest-neighbor index (S3 Vectors' actual value proposition) buys nothing — exact brute-force
cosine similarity over that many vectors, computed as a single vectorized numpy operation, is an
order-of-magnitude estimate of low tens of milliseconds, negligible against the 1,800 ms turn budget. **This
estimate is engineering judgment, not a verified benchmark, and is labeled as such** — consistent with this
project's discipline (constraint 13, already extended to engineering claims in `ADR-009`) of not asserting a
number that hasn't actually been measured. Phase 6/9 should record the real figure once measured.

Choosing DynamoDB also means **no new AWS service is introduced for this purpose at all** — DynamoDB is
already on constraint 17's fixed single-region service list, already has IAM policies and monitoring this
project will build regardless, and already gets a 25 GB always-free storage allowance (confirmed today —
though on-demand tables get **no** free RCU/WCU offset, only storage; re-verified during this same research
pass and folded into the Phase 2 cost model). S3 Vectors would be a new service surface — new IAM policies,
a new thing to provision, monitor, and tear down cleanly — bought for a scalability property (approximate NN
at high vector counts) this project's corpus size does not need.

**Why this beats FAISS/sqlite-vec baked into the Lambda deployment package:** this option directly conflicts
with `ADR-009`'s already-accepted first-line cold-start mitigation — "smaller deployment package." A baked-in
FAISS index or sqlite-vec extension adds package weight and a build/sync step to keep the index consistent
with the source policy documents, for the same "no benefit below this corpus size" reason S3 Vectors doesn't
earn its cost either. It also means the index is versioned inside the deployment artifact rather than in a
data store the corpus-ingestion pipeline (Phase 3) can update independently — a real operational
disadvantage next to a DynamoDB table an ingestion job can write to without a redeploy.

**Explicit scale threshold for revisiting this decision:** if the synthetic corpus grows to a size where
brute-force cosine (all vectors loaded and compared per query) becomes a real fraction of the 1,800 ms
budget, or where reading the full corpus into a cold execution environment materially worsens `ADR-009`'s
cold-start posture, that is the trigger to move to S3 Vectors — not before. This project does not expect to
cross that threshold at its stated scope (six intents, a synthetic policy corpus authored for eval purposes,
not a production document library), but the threshold is named here so a future phase doesn't have to
rediscover it from scratch.

## Consequences

**Positive:**
- Zero new AWS service surface for retrieval — one less thing to provision, secure, monitor, and tear down.
- Retrieval quality is exact (brute-force cosine), not approximate — removing one source of the groundedness
  eval's own noise, which matters directly since `CoverageQuestion` is this project's primary groundedness
  target.
- Consistent with `ADR-009`'s package-size-first cold-start posture, rather than working against it.

**Negative / accepted residual risk:**
- In-memory caching across warm invocations means a corpus update (Phase 3 re-ingestion) may not be visible
  to an already-warm execution environment until it naturally recycles, or until a cache-invalidation
  mechanism (e.g., a version/ETag check on each invocation) is added. Not built in Phase 2; recorded as a
  known limitation for a demo-scale corpus that changes rarely, not solved preemptively.
- If a SnapStart-snapshotted environment (`ADR-009`) resumes with a stale in-memory cache from before a
  corpus update, the same staleness risk applies at cold start too, not just across warm invocations. Same
  disposition: accepted at this scale, not solved in Phase 2.
- This decision is scale-contingent by design, not a permanent architectural stance — the threshold above
  exists precisely so that contingency is visible rather than implicit.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| OpenSearch Serverless | Never live | Banned by default in `CLAUDE.md` (~$350–700/mo, per Phase 0 archaeology) |
| S3 Vectors | Rejected at this scale | Its value (approximate NN at scale) doesn't apply to a low-thousands-of-chunks corpus; adds a new service surface for no benefit here. Explicit revisit threshold stated above |
| FAISS/sqlite-vec baked into the Lambda package | Rejected | Conflicts with `ADR-009`'s package-size-first cold-start mitigation; couples the index to the deployment artifact instead of the ingestion pipeline |
| **DynamoDB + in-process brute-force cosine similarity** | **Chosen** | No new service; exact retrieval; consistent with the cold-start strategy; matches actual corpus scale |

## Sources

- AWS Price List API (`AmazonS3`, us-west-2, S3 Vectors SKUs), fetched live 2026-08-11
- <https://aws.amazon.com/s3/pricing/> (S3 Vectors section)
- <https://aws.amazon.com/dynamodb/pricing/on-demand/> — 25 GB always-free storage confirmed; on-demand RCU/WCU confirmed **not** covered by the free-tier allowance

All pricing above fetched live on 2026-08-11 via a background research agent, per the project's standing
rule to verify against current sources rather than memory. The cosine-similarity latency estimate is
explicitly labeled as engineering judgment pending Phase 6/9 measurement, not a verified benchmark.
