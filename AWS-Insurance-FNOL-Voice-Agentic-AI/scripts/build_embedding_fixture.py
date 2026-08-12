"""Generate the committed real-Titan embedding fixture. ONE cost-gated run, then never again.

Roughly $0.0003 against the Phases 3-7 standing cap. Regenerate only when the corpus text or the graded
query set changes -- `evals/retrieval.fixture_is_stale` detects that and fails loudly rather than
reporting confident numbers about text that no longer exists.

ADR-013: no mock_aws() anywhere. Every call here is real, deliberately.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from evals.queries import GRADED_QUERIES
from evals.retrieval import FIXTURE_PATH, corpus_fingerprint
from fnol_voice_agent.knowledge.ingest import (
    DEFAULT_CORPUS_DIR,
    TITAN_EMBED_V2_MODEL_ID,
    BedrockEmbedder,
    chunk_markdown,
)

REGION = "us-west-2"


def main() -> int:
    embedder = BedrockEmbedder(region=REGION)
    chunks: list[dict[str, object]] = []
    for path in sorted(DEFAULT_CORPUS_DIR.glob("*.md")):
        for index, chunk in enumerate(chunk_markdown(path.read_text())):
            chunks.append(
                {
                    "source_file": path.name,
                    "chunk_index": index,
                    "section_title": chunk.section_title,
                    "text": chunk.text,
                }
            )
    print(f"chunking: {len(chunks)} chunks from {DEFAULT_CORPUS_DIR}")

    total_chars = 0
    for chunk in chunks:
        text = str(chunk["text"])
        total_chars += len(text)
        chunk["embedding"] = embedder.embed(text)

    queries = []
    for case in GRADED_QUERIES:
        total_chars += len(case.query)
        queries.append(
            {
                "query_id": case.query_id,
                "query": case.query,
                "gold_source_file": case.gold_source_file,
                "gold_text_contains": case.gold_text_contains,
                "embedding": embedder.embed(case.query),
            }
        )

    fixture = {
        "model_id": TITAN_EMBED_V2_MODEL_ID,
        "generated_at": datetime.now(UTC).isoformat(),
        "fingerprint": corpus_fingerprint(
            [str(c["text"]) for c in chunks], [q["query"] for q in queries]  # type: ignore[misc]
        ),
        "chunks": chunks,
        "queries": queries,
    }
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(fixture))
    size_mb = FIXTURE_PATH.stat().st_size / 1e6

    # Titan Embed V2 is $0.02 / 1M input tokens. ~4 chars/token is the usual approximation; stated as an
    # approximation because the exact tokenisation is not exposed in the InvokeModel response.
    approx_tokens = total_chars / 4
    print(f"embedded {len(chunks)} chunks + {len(queries)} queries")
    print(f"~{approx_tokens:,.0f} tokens (approx, from {total_chars:,} chars) -> "
          f"~${approx_tokens * 0.02 / 1e6:.6f}")
    print(f"wrote {FIXTURE_PATH} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
