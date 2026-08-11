# Costs — per-run log

Every real (non-mock, non-`local`) AWS call this project makes gets a row here, per `CLAUDE.md`'s standing
Bedrock approval ("$5 total across Phases 3–7, logged per-run"). Provisioned resources remain individually
gated regardless of this log.

| Date | Phase | What ran | Real AWS call? | Tokens | Est. cost | Running total |
|---|---|---|---|---|---|---|
| — | 3 | `make ingest` (default: mock embeddings + local moto table) | No — `--embeddings mock`, `--vector-store local`, both zero-cost/zero-credential defaults (`src/fnol_voice_agent/knowledge/ingest.py`) | 0 | $0.00 | $0.00 |
| 2026-08-11 | 3 | **First real spend.** One real `InvokeModel` call, `amazon.titan-embed-text-v2:0`, `us-west-2`, one chunk (`example-mutual-oap-policy-wording.md`'s DCPD section) — cost-gate approved by Marco explicitly, ahead of Phase 4, to verify the manifest's asserted model ID/dimension against an observed response rather than an untested assumption | **Yes** | 515 input | $0.0000103 (515 × $0.02 / 1,000,000) | $0.0000103 |

**Bedrock standing-approval cap consumed to date: $0.0000103 of $5.00** — effectively all of it still
unused. See `PROJECT_STATE.md`'s 2026-08-11 session log for what this single call verified (dimension,
normalization, response shape).
