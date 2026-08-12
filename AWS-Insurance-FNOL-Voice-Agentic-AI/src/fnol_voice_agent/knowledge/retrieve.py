"""Phase 5 Stage 3: retrieval — the read half of `ADR-002`'s vector-store design.

`ingest.py` (Phase 3) only wrote `CHUNK#<file>#<index>` and `STATE#<file>` items to DynamoDB; nothing read
them back until this module. This is agent/tool-layer code in the sense that `agents/nodes/` (Stage 6) will
call `search()` directly from the `CoverageQuestion` and `RentalTowingEntitlement` nodes — but it has no
LangGraph or conversation-state concerns of its own, same "just a function that returns data" posture as
`ingest.py`'s own module docstring claims for itself.

**Retrieval strategy, per `ADR-002`:** exact brute-force cosine similarity, computed as a single vectorized
numpy operation over every stored chunk's embedding — no ANN index, because this corpus (Phase 3's synthetic
policy wordings, chunked to low hundreds of chunks) is far below the scale where an approximate index would
earn its cost. `ADR-002` labels the "low tens of milliseconds" latency claim engineering judgment, not a
measured benchmark, pending a real number from Phase 6/9; this module does not repeat that label as fact.

**Reuses, does not reinvent:**
- `DynamoVectorStore` (`ingest.py`) for the underlying table access — same `pk` schema, no parallel store.
- `Embedder` / `MockEmbedder` / `BedrockEmbedder` (`ingest.py`) for embedding the *query* text — the exact
  same abstraction `ingest.py` uses to embed chunks at write time, so query and corpus embeddings are always
  produced by comparable model/dimension pairs.

**Two-axis mock/real pattern, same as `ingest.py`:** every function here takes an already-constructed
`DynamoVectorStore` and `Embedder` — the caller decides mock-vs-real for both, exactly as `ingest.py`'s CLI
does via `--vector-store` and `--embeddings`. This module adds no new AWS-touching code path of its own: it
either reads a moto-backed in-memory table (the only backend this project's tests ever use, since no real
`fnol-knowledge-chunks` table exists yet — that's Phase 8 scope, per `docs/phase5/BUILD-PLAN.md` §2) or a
real one, decided entirely by what `DynamoVectorStore` instance it's handed.

**Why embeddings round-trip through `str`, not `Decimal`/`float`, on read:** `ingest.py`'s `put_chunk` stores
each embedding component as `str(v)` (see its comment on `DynamoVectorStore.put_chunk`) rather than relying on
boto3's float->Decimal coercion. Reading them back means parsing each stored string back to `float` before any
numpy operation — done once per chunk, in `_chunk_embedding_matrix`, not scattered across call sites.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from boto3.dynamodb.conditions import Attr

from fnol_voice_agent.knowledge.ingest import DynamoVectorStore, Embedder

# --- Result shape -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RetrievedChunk:
    """One ranked search result. Carries every metadata field `ingest.py` wrote for this chunk — dropping
    `as_of_date` or `section_title` here would silently defeat the staleness/manifest design Phase 3 built
    them for (see `ingest.py`'s module docstring on idempotency and the manifest)."""

    source_file: str
    section_title: str
    text: str
    as_of_date: str
    chunk_index: int
    similarity: float


# --- Loading chunks back out of DynamoDB -------------------------------------------------------------


def load_all_chunks(store: DynamoVectorStore) -> list[dict[str, Any]]:
    """Scan `store`'s table for every `CHUNK#*` item, paginating past DynamoDB's per-`Scan` 1 MB limit.

    `STATE#<file>` items (Phase 3's idempotency bookkeeping) are filtered out server-side via
    `begins_with(pk, "CHUNK#")` — retrieval has no use for them, and shipping them to the client just to
    discard them locally would be wasted read capacity for no benefit.
    """
    items: list[dict[str, Any]] = []
    scan_kwargs: dict[str, Any] = {"FilterExpression": Attr("pk").begins_with("CHUNK#")}
    while True:
        response = store.table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if last_key is None:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key
    return items


def _chunk_embedding_matrix(chunks: list[dict[str, Any]]) -> np.ndarray[Any, np.dtype[np.float64]]:
    """Parse each chunk's `embedding` (stored as `list[str]`, per `ingest.py`'s `put_chunk`) back to float
    and stack into one `(n_chunks, dimension)` matrix for a single vectorized cosine computation."""
    return np.array(
        [[float(component) for component in chunk["embedding"]] for chunk in chunks],
        dtype=np.float64,
    )


# --- Cosine similarity --------------------------------------------------------------------------------


def cosine_similarities(
    query_embedding: list[float], matrix: np.ndarray[Any, np.dtype[np.float64]]
) -> np.ndarray[Any, np.dtype[np.float64]]:
    """Cosine similarity of one query vector against every row of `matrix`, vectorized (per `ADR-002`:
    "computed as a single vectorized numpy operation" is the design, not an incidental implementation
    detail). A zero-norm row (never expected from a real embedder, but guarded rather than raising
    `ZeroDivisionError` mid-`Converse`-call in production) is treated as similarity 0.0 to that chunk,
    never selected ahead of any chunk with a genuine embedding unless every candidate is degenerate.
    """
    query_vector = np.asarray(query_embedding, dtype=np.float64)
    query_norm = float(np.linalg.norm(query_vector))
    matrix_norms = np.linalg.norm(matrix, axis=1)

    denominators = matrix_norms * query_norm
    similarities: np.ndarray[Any, np.dtype[np.float64]] = np.divide(
        matrix @ query_vector,
        denominators,
        out=np.zeros(matrix.shape[0], dtype=np.float64),
        where=denominators != 0,
    )
    return similarities


def top_k_by_cosine_similarity(
    query_embedding: list[float],
    chunks: list[dict[str, Any]],
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Rank `chunks` (as returned by `load_all_chunks`) against `query_embedding` and return the `top_k`
    highest-cosine-similarity chunks, highest first, each carrying its full metadata."""
    if not chunks or top_k <= 0:
        return []

    matrix = _chunk_embedding_matrix(chunks)
    similarities = cosine_similarities(query_embedding, matrix)

    k = min(top_k, len(chunks))
    # argpartition for the top-k candidate set, then an exact sort of just those k -- avoids a full O(n
    # log n) sort of the whole corpus for a k that's normally small relative to corpus size.
    top_indices = np.argpartition(-similarities, k - 1)[:k]
    ranked_indices = top_indices[np.argsort(-similarities[top_indices])]

    return [
        RetrievedChunk(
            source_file=str(chunks[i]["source_file"]),
            section_title=str(chunks[i]["section_title"]),
            text=str(chunks[i]["text"]),
            as_of_date=str(chunks[i]["as_of_date"]),
            chunk_index=int(chunks[i]["chunk_index"]),
            similarity=float(similarities[i]),
        )
        for i in ranked_indices
    ]


# --- End-to-end search ---------------------------------------------------------------------------------


def search(
    query: str,
    store: DynamoVectorStore,
    embedder: Embedder,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Embed `query` with `embedder`, load every chunk from `store`, and return the `top_k` best matches
    by cosine similarity. The single entry point Stage 6's `CoverageQuestion` / `RentalTowingEntitlement`
    nodes are expected to call — everything above this function is decomposed for direct unit testing of
    the math (`cosine_similarities`, `top_k_by_cosine_similarity`), not because callers need it separately.
    """
    query_embedding = embedder.embed(query)
    chunks = load_all_chunks(store)
    return top_k_by_cosine_similarity(query_embedding, chunks, top_k)
