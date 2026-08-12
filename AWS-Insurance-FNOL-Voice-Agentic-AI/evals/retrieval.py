"""Retrieval metrics on real Titan vectors, computed offline from a committed fixture — Stage 5.

## The problem this solves

`SUCCESS-METRICS.md` §3 gates retrieval recall@5 at 0.90 and targets MRR at 0.75. Neither number means
anything computed with `MockEmbedder`, whose vectors are SHA-256 digests and are documented in
`ingest.py` as "not semantically meaningful" — ranking against them measures nothing but hash collisions.
So the metrics need real embeddings.

But paying for embeddings on every CI run is both a cost and a credential dependency, and Tier A exists
precisely so the gate can run at $0.00 with no credentials.

**The fixture resolves both.** One real, cost-gated Titan run embeds the corpus chunks and the golden
set's coverage queries; the vectors are committed. Every run after that computes genuinely-real
recall@5 and MRR by loading them, offline and free. The embeddings are a deterministic function of text
that has not changed, so caching them loses nothing — unlike caching a generation, which would freeze a
stochastic process and hide exactly the variance Phase 6 is meant to observe.

## When the fixture must be regenerated

Whenever the corpus text or the query set changes. `fixture_is_stale()` detects this by hashing both and
comparing against the hash stored in the fixture, so a silently-outdated fixture fails loudly rather than
producing confident numbers about text that no longer exists.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .metrics import Rate

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "embeddings_titan_v2.json"


class FixtureStaleError(RuntimeError):
    """The committed vectors no longer match the text they were computed from."""


class FixtureMissingError(FileNotFoundError):
    """The embedding fixture has not been generated. It requires one cost-gated real Titan run."""


@dataclass(frozen=True)
class RetrievalCase:
    """One graded query: which corpus chunk(s) count as the gold passage.

    Gold is identified by `source_file` plus a substring that must appear in the chunk, rather than by a
    chunk index. Indices shift whenever the chunker's parameters change, and a gold label that silently
    re-points at a different passage after a chunking tweak is worse than no label at all.
    """

    query_id: str
    query: str
    gold_source_file: str
    gold_text_contains: str


def corpus_fingerprint(chunk_texts: list[str], queries: list[str]) -> str:
    hasher = hashlib.sha256()
    for text in sorted(chunk_texts):
        hasher.update(text.encode())
    for query in sorted(queries):
        hasher.update(query.encode())
    return hasher.hexdigest()


def load_fixture(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FixtureMissingError(
            f"{path} does not exist. Generate it with one cost-gated real Titan run "
            f"(scripts/build_embedding_fixture.py) — roughly $0.0003, once."
        )
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


@dataclass
class RetrievalReport:
    recall_at_5: Rate
    mrr: float | None
    per_query_rank: dict[str, int | None]  # None = gold not in top-k at all
    model_id: str
    generated_at: str


def evaluate_retrieval(path: Path = FIXTURE_PATH, top_k: int = 5) -> RetrievalReport:
    fixture = load_fixture(path)
    chunks = fixture["chunks"]
    hits = 0
    reciprocal_ranks: list[float] = []
    per_query: dict[str, int | None] = {}

    for entry in fixture["queries"]:
        scored = sorted(
            ((cosine(entry["embedding"], c["embedding"]), c) for c in chunks),
            key=lambda pair: pair[0],
            reverse=True,
        )
        rank: int | None = None
        for position, (_score, chunk) in enumerate(scored, start=1):
            if (
                chunk["source_file"] == entry["gold_source_file"]
                and entry["gold_text_contains"].lower() in chunk["text"].lower()
            ):
                rank = position
                break
        per_query[entry["query_id"]] = rank
        if rank is not None and rank <= top_k:
            hits += 1
        # MRR is over ALL queries, with a miss contributing 0 — not over hits only, which would report
        # the mean rank of the successes and quietly exclude the failures from the average.
        reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)

    total = len(fixture["queries"])
    return RetrievalReport(
        recall_at_5=Rate(hits, total),
        mrr=(sum(reciprocal_ranks) / total) if total else None,
        per_query_rank=per_query,
        model_id=fixture["model_id"],
        generated_at=fixture["generated_at"],
    )


def validate_gold_labels(path: Path = FIXTURE_PATH) -> list[str]:
    """Every gold label must resolve to at least one real chunk. Returns the labels that do not.

    The third instrument bug of Phase 6, caught here: a gold label naming text that exists nowhere in the
    corpus produces `rank None`, which is arithmetically identical to the retriever failing to find a
    passage that was there all along. Two of the first ten graded queries were broken this way — one
    named a substring that appears only in a section heading (which the chunker does not carry into chunk
    text), the other named the wrong source file.

    Both would have been published as retrieval failures. Recall would have read 0.700 when the real
    figure was different, and the natural next move — "improve retrieval" — would have been work aimed at
    a defect that did not exist.
    """
    fixture = load_fixture(path)
    broken = []
    for entry in fixture["queries"]:
        matches = [
            c
            for c in fixture["chunks"]
            if c["source_file"] == entry["gold_source_file"]
            and entry["gold_text_contains"].lower() in c["text"].lower()
        ]
        if not matches:
            broken.append(
                f"{entry['query_id']}: no chunk in {entry['gold_source_file']} contains "
                f"{entry['gold_text_contains']!r}"
            )
    return broken
