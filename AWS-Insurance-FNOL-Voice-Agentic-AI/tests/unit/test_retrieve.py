"""Unit tests for src/fnol_voice_agent/knowledge/retrieve.py.

Same standing constraint as test_ingest.py: moto for DynamoDB, MockEmbedder for embeddings -- these tests
must never be able to spend money or require AWS access, per this project's "everything runs locally without
AWS" constraint. The end-to-end tests below seed their moto table by running `ingest.py`'s real
`run_ingestion` against the real synthetic policy corpus (`data/synthetic/policy/*.md`), not a hand-built
fixture, so retrieval is exercised against the exact schema Phase 3's writer actually produces.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from moto import mock_aws

from fnol_voice_agent.knowledge.ingest import (
    DEFAULT_CORPUS_DIR,
    DynamoVectorStore,
    Manifest,
    MockEmbedder,
    run_ingestion,
)
from fnol_voice_agent.knowledge.retrieve import (
    RetrievedChunk,
    cosine_similarities,
    load_all_chunks,
    search,
    top_k_by_cosine_similarity,
)

# --- cosine_similarities: hand-checkable math, not just plausible end-to-end output ------------------


def test_cosine_similarities_hand_checked_values():
    query = [1.0, 0.0]
    matrix = np.array(
        [
            [1.0, 0.0],  # identical direction -> 1.0
            [0.0, 1.0],  # orthogonal -> 0.0
            [1.0, 1.0],  # 45 degrees -> 1/sqrt(2)
            [-1.0, 0.0],  # opposite direction -> -1.0
        ],
        dtype=np.float64,
    )
    similarities = cosine_similarities(query, matrix)
    expected = [1.0, 0.0, 1 / math.sqrt(2), -1.0]
    assert similarities == pytest.approx(expected)


def test_cosine_similarities_zero_vector_is_similarity_zero_not_a_crash():
    query = [1.0, 0.0]
    matrix = np.array([[0.0, 0.0], [1.0, 0.0]], dtype=np.float64)
    similarities = cosine_similarities(query, matrix)
    assert similarities[0] == 0.0
    assert similarities[1] == pytest.approx(1.0)


# --- top_k_by_cosine_similarity: ranking + limiting on a small, fully-known set -----------------------


def _chunk(pk_suffix: str, embedding: list[float], **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "pk": f"CHUNK#doc-{pk_suffix}.md#0",
        "source_file": f"doc-{pk_suffix}.md",
        "section_title": f"Section {pk_suffix}",
        "chunk_index": 0,
        "text": f"text {pk_suffix}",
        "as_of_date": "2026-08-11",
        "embedding": [
            str(v) for v in embedding
        ],  # exact on-disk shape ingest.py's put_chunk writes
    }
    base.update(overrides)
    return base


def test_top_k_by_cosine_similarity_ranks_highest_first_and_limits_to_k():
    chunks = [
        _chunk("a", [1.0, 0.0]),  # sim to query [1, 0] = 1.0
        _chunk("b", [0.0, 1.0]),  # sim = 0.0
        _chunk("c", [0.9, 0.1]),  # sim close to 1.0 but strictly less
        _chunk("d", [-1.0, 0.0]),  # sim = -1.0
    ]
    results = top_k_by_cosine_similarity([1.0, 0.0], chunks, top_k=2)
    assert len(results) == 2
    assert [r.source_file for r in results] == ["doc-a.md", "doc-c.md"]
    assert results[0].similarity > results[1].similarity
    assert results[0].similarity == pytest.approx(1.0)


def test_top_k_by_cosine_similarity_top_k_larger_than_corpus_returns_all():
    chunks = [_chunk("a", [1.0, 0.0]), _chunk("b", [0.0, 1.0])]
    results = top_k_by_cosine_similarity([1.0, 0.0], chunks, top_k=10)
    assert len(results) == 2


def test_top_k_by_cosine_similarity_zero_or_negative_k_returns_empty():
    chunks = [_chunk("a", [1.0, 0.0])]
    assert top_k_by_cosine_similarity([1.0, 0.0], chunks, top_k=0) == []


def test_top_k_by_cosine_similarity_empty_corpus_returns_empty():
    assert top_k_by_cosine_similarity([1.0, 0.0], [], top_k=5) == []


def test_top_k_by_cosine_similarity_preserves_metadata():
    chunks = [_chunk("a", [1.0, 0.0], as_of_date="2026-01-01", section_title="Deductibles")]
    [result] = top_k_by_cosine_similarity([1.0, 0.0], chunks, top_k=1)
    assert isinstance(result, RetrievedChunk)
    assert result.source_file == "doc-a.md"
    assert result.section_title == "Deductibles"
    assert result.as_of_date == "2026-01-01"
    assert result.text == "text a"
    assert result.chunk_index == 0


# --- End-to-end: seed a moto table via ingest.py's real ingestion, query it via retrieve.py -----------


@pytest.fixture
def seeded_store(tmp_path: Path) -> Any:
    """Seed a moto-backed table by running the actual Phase 3 ingestion (`run_ingestion`) against the real
    synthetic policy corpus, mock embeddings only -- so this test exercises the real write schema
    retrieve.py must read, not a hand-built fixture that could quietly drift from it.
    """
    with mock_aws():
        store = DynamoVectorStore("test-retrieve-table", region="us-west-2")
        manifest = run_ingestion(
            DEFAULT_CORPUS_DIR,
            store,
            MockEmbedder(),
            "local (moto)",
            manifest_path=tmp_path / "manifest.json",
        )
        yield store, manifest


def test_load_all_chunks_matches_manifest_total_and_excludes_state_items(
    seeded_store: tuple[DynamoVectorStore, Manifest],
) -> None:
    store, manifest = seeded_store
    chunks = load_all_chunks(store)
    assert len(chunks) == manifest.total_chunks
    assert (
        manifest.total_chunks > 5
    )  # sanity: real corpus is big enough for a meaningful top-k test
    assert all(c["pk"].startswith("CHUNK#") for c in chunks)


def test_search_returns_the_chunk_whose_text_the_query_embedding_matches(
    seeded_store: tuple[DynamoVectorStore, Manifest],
) -> None:
    store, _ = seeded_store
    embedder = MockEmbedder()
    chunks = load_all_chunks(store)
    known_chunk = chunks[len(chunks) // 2]  # any real chunk from the real corpus

    # MockEmbedder is a deterministic hash of the input text (see ingest.py). Embedding the exact same
    # text the chunk was embedded from at ingestion time reproduces its exact vector, so a query built
    # from that text must retrieve it as the #1 result (identical embeddings -> cosine similarity 1.0).
    results = search(known_chunk["text"], store, embedder, top_k=3)

    assert len(results) == 3
    top = results[0]
    assert top.source_file == known_chunk["source_file"]
    assert top.section_title == known_chunk["section_title"]
    assert top.chunk_index == known_chunk["chunk_index"]
    assert top.similarity == pytest.approx(1.0, abs=1e-9)


def test_search_metadata_survives_the_round_trip(
    seeded_store: tuple[DynamoVectorStore, Manifest],
) -> None:
    store, _ = seeded_store
    embedder = MockEmbedder()
    chunks = load_all_chunks(store)
    known_chunk = chunks[0]

    [top] = search(known_chunk["text"], store, embedder, top_k=1)
    assert top.source_file == known_chunk["source_file"]
    assert top.section_title == known_chunk["section_title"]
    assert top.as_of_date == known_chunk["as_of_date"]
    assert top.text == known_chunk["text"]


def test_search_top_k_limits_and_ranks_result_count(
    seeded_store: tuple[DynamoVectorStore, Manifest],
) -> None:
    store, manifest = seeded_store
    embedder = MockEmbedder()
    assert manifest.total_chunks > 5
    results = search("towing and rental coverage after an accident", store, embedder, top_k=5)
    assert len(results) == 5
    similarities = [r.similarity for r in results]
    assert similarities == sorted(similarities, reverse=True)


def test_measured_brute_force_search_latency_over_real_corpus(
    seeded_store: tuple[DynamoVectorStore, Manifest],
) -> None:
    """Not a correctness assertion -- ADR-002 labels its "low tens of milliseconds" cosine-search latency
    claim engineering judgment, not a verified benchmark, and asks Phase 6/9 to record a real figure. This
    test measures (does not assume) end-to-end `search()` latency over the actual corpus chunk count, on
    this machine, and prints it for that record -- generously bounded so it documents rather than enforces
    a performance SLA (the 1,800 ms voice turn-latency budget, not a tight number, is the only thing this
    guards against regressing to).
    """
    store, manifest = seeded_store
    embedder = MockEmbedder()

    start = time.perf_counter()
    results = search("what is my deductible for collision coverage", store, embedder, top_k=5)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert len(results) == 5
    print(
        f"\n[measured] search() over {manifest.total_chunks} real chunks: {elapsed_ms:.3f} ms "
        f"(includes a moto DynamoDB Scan + embed + brute-force cosine)"
    )
    assert elapsed_ms < 1_800  # the voice turn-latency budget itself (CLAUDE.md), not a tight bound
