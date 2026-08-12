# Costs — per-run log

Every real (non-mock, non-`local`) AWS call this project makes gets a row here, per `CLAUDE.md`'s standing
Bedrock approval ("$5 total across Phases 3–7, logged per-run"). Provisioned resources remain individually
gated regardless of this log.

| Date | Phase | What ran | Real AWS call? | Tokens | Est. cost | Running total |
|---|---|---|---|---|---|---|
| — | 3 | `make ingest` (default: mock embeddings + local moto table) | No — `--embeddings mock`, `--vector-store local`, both zero-cost/zero-credential defaults (`src/fnol_voice_agent/knowledge/ingest.py`) | 0 | $0.00 | $0.00 |
| 2026-08-11 | 3 | **First real spend.** One real `InvokeModel` call, `amazon.titan-embed-text-v2:0`, `us-west-2`, one chunk (`example-mutual-oap-policy-wording.md`'s DCPD section) — cost-gate approved by Marco explicitly, ahead of Phase 4, to verify the manifest's asserted model ID/dimension against an observed response rather than an untested assumption | **Yes** | 515 input | $0.0000103 (515 × $0.02 / 1,000,000) | $0.0000103 |
| 2026-08-11 | 4 | **Closing verification.** Five real `Converse` calls, `us-west-2`, against the exact system prompts drafted in `docs/phase4/PROMPT-REGISTRY.md` — cost-gate approved by Marco explicitly, to check the length-discipline specs against real model output rather than assert them. Breakdown: (1) `us.amazon.nova-micro-v1:0`, forced tool-use `classify_turn`, 751 in / 42 out → $0.0000322; (2) `us.amazon.nova-micro-v1:0`, unconstrained tight-turn generation (ambiguity clarifier), 77 in / 24 out → $0.0000061; (3) `us.amazon.nova-lite-v1:0`, `CoverageQuestion` mandatory (DCPD), 243 in / 13 out → $0.0000177; (4) `us.amazon.nova-lite-v1:0`, `CoverageQuestion` optional (IRB), 270 in / 38 out → $0.0000253; (5) `us.amazon.nova-lite-v1:0`, `RentalTowingEntitlement` compound, 265 in / 36 out → $0.0000245 | **Yes** | 1,606 input / 153 output | $0.0001058 | $0.0001161 |

**Bedrock standing-approval cap consumed to date: $0.0001161 of $5.00** — effectively all of it still
unused. See `PROJECT_STATE.md`'s 2026-08-11 session log for what each phase's calls verified.
