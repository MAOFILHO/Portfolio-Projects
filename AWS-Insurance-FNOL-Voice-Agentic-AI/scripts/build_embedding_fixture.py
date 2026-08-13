"""Generate the committed real-Titan embedding fixture. ONE cost-gated run, then never again.

Roughly $0.0003 against the Phases 3-7 standing cap. Regenerate only when the corpus text or the graded
query set changes -- `evals/retrieval.fixture_is_stale` detects that and fails loudly rather than
reporting confident numbers about text that no longer exists. (Until Phase 7 Stage R that sentence was
false: no such function existed. It does now, and `evaluate_retrieval` calls it.)

    --labels-only    Rewrite the fixture's gold labels from `GRADED_QUERIES` and nothing else. **$0.00,
                     no model calls.** A gold label is not an embedding input -- correcting one changes
                     which chunk counts as right, not what any vector is -- so paying for a full
                     re-embedding to fix a label is spending money to change a string.

ADR-013: no mock_aws() anywhere. Every call in the default path is real, deliberately.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from evals.queries import GRADED_QUERIES
from evals.retrieval import (
    FIXTURE_PATH,
    corpus_fingerprint,
    label_fingerprint,
    refresh_labels,
)
from fnol_voice_agent.knowledge.ingest import (
    DEFAULT_CORPUS_DIR,
    TITAN_EMBED_V2_MODEL_ID,
    BedrockEmbedder,
    chunk_markdown,
)

REGION = "us-west-2"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels-only",
        action="store_true",
        help="rewrite gold labels from GRADED_QUERIES; no embedding calls, $0.00",
    )
    args = parser.parse_args()

    if args.labels_only:
        changes = refresh_labels()
        for change in changes:
            print(f"  label  {change}")
        print(f"refreshed {len(changes)} label(s) in {FIXTURE_PATH} — $0.00, no model calls")
        return 0

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
    for record in chunks:
        text = str(record["text"])
        total_chars += len(text)
        record["embedding"] = embedder.embed(text)

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
        "label_fingerprint": label_fingerprint(
            (case.query_id, case.gold_source_file, case.gold_text_contains)
            for case in GRADED_QUERIES
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
    print(
        f"~{approx_tokens:,.0f} tokens (approx, from {total_chars:,} chars) -> "
        f"~${approx_tokens * 0.02 / 1e6:.6f}"
    )
    print(f"wrote {FIXTURE_PATH} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
