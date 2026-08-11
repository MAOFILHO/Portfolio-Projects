"""Unit tests for src/fnol_voice_agent/knowledge/ingest.py.

Uses moto for DynamoDB (no AWS credentials, no network) and MockEmbedder for embeddings (no Bedrock calls,
no cost) — these tests must never be able to spend money or require AWS access, per this project's standing
"everything runs locally without AWS" constraint.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from moto import mock_aws

from fnol_voice_agent.knowledge.ingest import (
    DynamoVectorStore,
    MockEmbedder,
    chunk_markdown,
    run_ingestion,
)

# --- chunk_markdown --------------------------------------------------------------------------------


def test_chunk_markdown_splits_on_headings():
    text = "# Title\n\nIntro text.\n\n## Section One\n\nBody one.\n\n## Section Two\n\nBody two.\n"
    chunks = chunk_markdown(text, max_chunk_chars=10_000)
    titles = [c.section_title for c in chunks]
    assert titles == ["Preamble", "Section One", "Section Two"]
    assert "Body one." in chunks[1].text
    assert "Body two." in chunks[2].text


def test_chunk_markdown_no_headings_is_single_preamble_chunk():
    text = "Just plain text, no markdown headings at all."
    chunks = chunk_markdown(text, max_chunk_chars=10_000)
    assert len(chunks) == 1
    assert chunks[0].section_title == "Preamble"


def test_chunk_markdown_splits_oversized_section_on_paragraph_boundaries():
    paragraphs = [f"Paragraph {i}. " + ("x" * 200) for i in range(10)]
    body = "## Big Section\n\n" + "\n\n".join(paragraphs)
    chunks = chunk_markdown(body, max_chunk_chars=500)
    assert len(chunks) > 1
    assert all(c.section_title == "Big Section" for c in chunks)
    assert all(
        len(c.text) <= 700 for c in chunks
    )  # some slack for a single paragraph slightly over the cap
    # No paragraph's text content is lost across the split:
    rejoined = "\n\n".join(c.text for c in chunks)
    for i in range(10):
        assert f"Paragraph {i}." in rejoined


def test_chunk_markdown_drops_empty_chunks():
    chunks = chunk_markdown("## Empty\n\n\n\n## Real\n\nContent here.", max_chunk_chars=10_000)
    assert all(c.text for c in chunks)
    assert [c.section_title for c in chunks] == ["Real"]


# --- run_ingestion: manifest shape and required fields (Marco's explicit requirement) --------------


@pytest.fixture
def corpus_dir(tmp_path: Path) -> Path:
    d = tmp_path / "policy"
    d.mkdir()
    (d / "corpus-metadata.json").write_text(json.dumps({"as_of_date": "2026-08-11"}))
    (d / "doc-a.md").write_text("## Section A1\n\nContent A1.\n\n## Section A2\n\nContent A2.\n")
    (d / "doc-b.md").write_text("## Section B1\n\nContent B1.\n")
    return d


def test_manifest_records_required_fields(corpus_dir: Path, tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    with mock_aws():
        store = DynamoVectorStore("test-table", region="us-west-2")
        manifest = run_ingestion(corpus_dir, store, MockEmbedder(), "local (moto)", manifest_path)

    d = manifest.to_dict()
    # The four fields Marco explicitly required, present at the top level:
    assert d["corpus_as_of_date"] == "2026-08-11"
    assert d["embedding_model_id"] == MockEmbedder.model_id
    assert d["embedding_dimension"] == MockEmbedder.dimension
    assert len(d["files"]) == 2
    for f in d["files"]:
        assert "sha256" in f and len(f["sha256"]) == 64
        assert "chunk_count" in f and f["chunk_count"] > 0
    assert d["total_chunks"] == 3  # doc-a: 2 sections, doc-b: 1 section
    assert manifest_path.exists()
    on_disk = json.loads(manifest_path.read_text())
    assert on_disk == d


def test_run_ingestion_is_idempotent_on_unchanged_files(corpus_dir: Path, tmp_path: Path):
    with mock_aws():
        store = DynamoVectorStore("test-table", region="us-west-2")
        first = run_ingestion(
            corpus_dir, store, MockEmbedder(), "local (moto)", tmp_path / "m1.json"
        )
        assert first.files_embedded == 2
        assert first.files_skipped == 0

        # Second run, same store, same files -- must skip everything, no re-embedding.
        second = run_ingestion(
            corpus_dir, store, MockEmbedder(), "local (moto)", tmp_path / "m2.json"
        )
        assert second.files_embedded == 0
        assert second.files_skipped == 2
        assert second.total_chunks == first.total_chunks


def test_run_ingestion_reembeds_only_the_changed_file(corpus_dir: Path, tmp_path: Path):
    with mock_aws():
        store = DynamoVectorStore("test-table", region="us-west-2")
        run_ingestion(corpus_dir, store, MockEmbedder(), "local (moto)", tmp_path / "m1.json")

        (corpus_dir / "doc-a.md").write_text("## Section A1 changed\n\nNew content entirely.\n")
        second = run_ingestion(
            corpus_dir, store, MockEmbedder(), "local (moto)", tmp_path / "m2.json"
        )

        statuses = {f.path.split("/")[-1]: f.status for f in second.files}
        assert statuses["doc-a.md"] == "embedded"
        assert statuses["doc-b.md"] == "skipped_unchanged"


def test_dynamo_vector_store_ensure_table_is_idempotent():
    with mock_aws():
        store = DynamoVectorStore("test-table", region="us-west-2")
        store.ensure_table()
        store.ensure_table()  # must not raise on a second call
