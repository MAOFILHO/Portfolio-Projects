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

⚠ **That paragraph was false for two phases, and how it was false is the point.** Until Phase 7 Stage R,
`fixture_is_stale()` **did not exist**. `FixtureStaleError` was defined and never raised. The fingerprint
was computed, written into the fixture, and never read back or compared by anything. Two docstrings --
this one and `scripts/build_embedding_fixture.py`'s -- asserted a guard that had never been written, and
both read as true. `RESULTS.md` §3.5's pattern in its purest form: the previous four instances at least
had a guard that ran and checked the wrong thing. This one had prose.

## Two fingerprints, not one

Separated at Stage R because they invalidate different things and cost different amounts to repair:

* **`corpus_fingerprint`** covers the *embedding inputs* -- chunk texts and query texts. If it moves, the
  committed vectors describe text that no longer exists and the fixture must be **re-embedded** (a real,
  billed Titan run).
* **`label_fingerprint`** covers the *ground-truth gold labels*. If it moves, the vectors are still
  perfectly valid and only the labels are out of date, so the fixture is repaired **offline at $0.00**
  (`refresh_labels()`).

Before the split, gold labels were copied into the fixture and covered by **neither** hash. `RESULTS.md`
§6 records Phase 6 correcting two broken labels; that correction only took effect because the fixture
happened to be regenerated in the same pass. **A label-only correction, committed to `queries.py` without
a paid re-embedding run, would have changed nothing and reported the old number with no warning.**
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
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


def label_fingerprint(labels: Iterable[tuple[str, str, str]]) -> str:
    """Hash of the gold labels — `(query_id, gold_source_file, gold_text_contains)` per query.

    Separate from `corpus_fingerprint` because a label change does not invalidate a single vector. The
    null byte separates the fields so that `("cq-1", "a", "bc")` and `("cq-1", "ab", "c")` cannot hash
    alike; concatenating without a separator is the classic way to make two different label sets agree.
    """
    hasher = hashlib.sha256()
    for query_id, source_file, contains in sorted(labels):
        hasher.update(f"{query_id}\x00{source_file}\x00{contains}\x00".encode())
    return hasher.hexdigest()


def current_fingerprints() -> tuple[str, str]:
    """`(corpus, labels)` recomputed from the live corpus and the live query set."""
    # Deferred imports, both deliberate: `evals.queries` imports `RetrievalCase` from this module, so a
    # module-level import here is a cycle; and `ingest` pulls in the knowledge package for a pure
    # function, which Tier A should not pay for at import time.
    from fnol_voice_agent.knowledge.ingest import DEFAULT_CORPUS_DIR, chunk_markdown

    from .queries import GRADED_QUERIES

    chunk_texts = [
        chunk.text
        for path in sorted(DEFAULT_CORPUS_DIR.glob("*.md"))
        for chunk in chunk_markdown(path.read_text())
    ]
    return (
        corpus_fingerprint(chunk_texts, [q.query for q in GRADED_QUERIES]),
        label_fingerprint(
            (q.query_id, q.gold_source_file, q.gold_text_contains) for q in GRADED_QUERIES
        ),
    )


def fixture_is_stale(path: Path = FIXTURE_PATH) -> list[str]:
    """Reasons the committed fixture no longer matches the live corpus, queries or labels. Empty = current.

    Each reason names its own repair, because the two are not the same price and a reader who conflates
    them will either pay for an embedding run they did not need or skip one they did.

    Drift is detected from **the fixture's own label rows**, not from the `label_fingerprint` field it
    carries. The first draft of this function compared the stored hash against the live query set and
    never looked at the rows the hash was supposed to describe — so hand-editing a gold label in the
    fixture passed cleanly, because the hash and the query set still agreed with each other. That is
    `RESULTS.md` §3.5's pattern reappearing inside the fix for §3.5's pattern, one test later
    (`test_a_gold_label_correction_cannot_silently_report_the_old_number`). Checking the artifact that
    stands in for the data, rather than the data, is apparently the default state of a guard unless
    something forces otherwise.

    The stored field is still compared — against the rows, as an integrity check — so that it is not a
    second hash written and never read.
    """
    fixture = load_fixture(path)
    corpus_now, labels_now = current_fingerprints()
    reasons: list[str] = []

    if fixture.get("fingerprint") != corpus_now:
        reasons.append(
            "corpus/query text has changed since the vectors were computed — the committed embeddings "
            "describe text that no longer exists. Repair: re-embed "
            "(scripts/build_embedding_fixture.py, a real billed Titan run)."
        )

    rows = [
        (q["query_id"], q["gold_source_file"], q["gold_text_contains"]) for q in fixture["queries"]
    ]
    labels_in_fixture = label_fingerprint(rows)
    if labels_in_fixture != labels_now:
        reasons.append(
            "the gold labels stored in the fixture differ from evals/queries.py. The vectors are "
            "still valid — a label is not an embedding input. Repair: "
            "scripts/build_embedding_fixture.py --labels-only ($0.00)."
        )

    stored = fixture.get("label_fingerprint")
    if stored is None:
        reasons.append(
            "fixture predates label fingerprinting, so its labels carry no integrity hash. Repair: "
            "scripts/build_embedding_fixture.py --labels-only ($0.00)."
        )
    elif stored != labels_in_fixture:
        reasons.append(
            "the fixture's stored label_fingerprint does not match its own label rows — the file has "
            "been edited by hand or written by a builder that disagrees with this module. Repair: "
            "scripts/build_embedding_fixture.py --labels-only ($0.00)."
        )
    return reasons


def assert_fixture_current(path: Path = FIXTURE_PATH) -> None:
    """Raise `FixtureStaleError` if the fixture is stale. Called by `evaluate_retrieval`.

    This is the call the module docstring claimed existed for two phases. It is wired into the metric
    rather than offered as a helper on purpose: a staleness check nobody invokes is the same artifact
    the previous version was.
    """
    reasons = fixture_is_stale(path)
    if reasons:
        raise FixtureStaleError(f"{path} is stale:\n  - " + "\n  - ".join(reasons))


def refresh_labels(path: Path = FIXTURE_PATH) -> list[str]:
    """Rewrite the fixture's gold labels from `GRADED_QUERIES`, offline, at $0.00. Returns what changed.

    **Refuses if the corpus fingerprint is also stale.** A label refresh that silently accepted a
    changed corpus would paper over exactly the condition that needs a paid re-embedding, and would do
    it while printing a reassuring message.
    """
    from .queries import GRADED_QUERIES

    fixture = load_fixture(path)
    corpus_now, labels_now = current_fingerprints()
    if fixture.get("fingerprint") != corpus_now:
        raise FixtureStaleError(
            "corpus/query text has changed, so labels are not the only thing out of date. Re-embed "
            "instead: scripts/build_embedding_fixture.py (no --labels-only)."
        )

    by_id = {q.query_id: q for q in GRADED_QUERIES}
    changes: list[str] = []
    for entry in fixture["queries"]:
        case = by_id.get(entry["query_id"])
        if case is None:
            raise FixtureStaleError(
                f"{entry['query_id']} is in the fixture but not in GRADED_QUERIES; the query set "
                f"changed, which requires a re-embed, not a label refresh."
            )
        old = (entry["gold_source_file"], entry["gold_text_contains"])
        new = (case.gold_source_file, case.gold_text_contains)
        if old != new:
            changes.append(f"{case.query_id}: {old[0]}/{old[1]!r} -> {new[0]}/{new[1]!r}")
            entry["gold_source_file"], entry["gold_text_contains"] = new

    fixture["label_fingerprint"] = labels_now
    path.write_text(json.dumps(fixture))
    return changes


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
    assert_fixture_current(path)
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
