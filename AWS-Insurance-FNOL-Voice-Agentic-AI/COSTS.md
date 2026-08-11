# Costs — per-run log

Every real (non-mock, non-`local`) AWS call this project makes gets a row here, per `CLAUDE.md`'s standing
Bedrock approval ("$5 total across Phases 3–7, logged per-run"). Provisioned resources remain individually
gated regardless of this log.

| Date | Phase | What ran | Real AWS call? | Est. cost | Running total |
|---|---|---|---|---|---|
| — | 3 | `make ingest` (default: mock embeddings + local moto table) | **No** — `--embeddings mock`, `--vector-store local`, both explicitly zero-cost/zero-credential defaults (`src/fnol_voice_agent/knowledge/ingest.py`) | $0.00 | $0.00 |

**Nothing has been run against real Bedrock or real AWS DynamoDB yet.** The ingestion pipeline supports it
(`--embeddings bedrock`, `--vector-store aws`), but no run in this project has passed those flags. A real
Titan Embed V2 run over the current 21-chunk corpus would cost a small fraction of a cent
(`$0.02/1M tokens`, per `CLAUDE.md`'s verified pricing table) — nowhere near the $5 cap — but is not
triggered automatically by `make ingest`, and hasn't been triggered manually either.

Bedrock standing-approval cap consumed to date: **$0.00 of $5.00**.
