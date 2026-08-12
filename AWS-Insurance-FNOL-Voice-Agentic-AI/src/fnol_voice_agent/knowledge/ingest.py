"""Phase 3 ingestion pipeline: chunk the policy corpus, embed it, load it into the vector store (ADR-002).

Data-engineering script, not agent/orchestration code (that distinction is Phase 3 exit criterion 10's own
scope boundary) — this module has no LangGraph, no tool-calling, no conversation state. It reads markdown
files, calls an embedding backend, and writes rows to DynamoDB.

Two independent safety axes, both defaulting to the option that spends nothing and touches no real AWS
resource, per this project's cost-gate discipline:

  --embeddings   {mock, bedrock}   mock = deterministic fake vectors, $0, no credentials needed (default).
                                    bedrock = real Titan Embed v2 calls, billed against the $5 Phases 3-7
                                    standing-approval cap (CLAUDE.md), never the default.
  --vector-store {local, aws}      local = an in-memory table via moto, no AWS account needed (default).
                                    aws = a real DynamoDB table — will fail today, since that table is
                                    Phase 8 scope and hasn't been provisioned; wiring it up now means this
                                    script needs no changes once it has.

`make ingest` runs the all-default (mock + local) combination, so it is always free to run, including in CI
(Phase 10) with no AWS credentials configured at all.

Chunking strategy: markdown section-based (split on `## ` headings), with a secondary paragraph-boundary
split for any section over `max_chunk_chars`. Chosen over fixed-size sliding-window chunking because the
corpus's own sections (Third Party Liability, Accident Benefits, DCPD, ...) are already the right retrieval
granularity — a `CoverageQuestion` about DCPD should retrieve the DCPD section, not an arbitrary 500-character
window that might split a table or a worked example in half. AWS's own Titan Embed V2 guidance recommends
segmenting by "logical segments, such as paragraphs or sections" for exactly this reason (verified live
2026-08-11: `docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html`). Rejected alternative:
sentence-level chunking — too granular for this corpus; a single sentence out of context (e.g. a dollar
figure with no surrounding "what this is" text) makes for worse retrieval, not better, at this document size.

Idempotency: the DynamoDB table also stores one `STATE#<relative_path>` item per source file, holding the
last-ingested SHA-256 of that file. A run recomputes each file's current hash and skips (no embedding calls,
no writes) any file whose hash is unchanged — the requirement Marco set: an unchanged corpus makes `make
ingest` free to re-run, not a repeated Bedrock charge.

⚠ Note on the default `--vector-store local` backend: it's an in-memory `moto` table, torn down when the
process exits — so idempotency across two separate `make ingest` invocations is only observable end-to-end
against a persistent backend (`--vector-store aws`, once Phase 8 provisions the real table). The skip logic
itself is fully exercised and tested within a single run (`tests/unit/test_ingest.py` calls `run_ingestion`
twice against one shared store), which is what the correctness of the mechanism actually depends on —
persistence is an infrastructure property, not a logic one, and moto's zero-setup, zero-Docker profile is
worth keeping as the safe default even though it doesn't demonstrate cross-invocation skipping by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import boto3

from fnol_voice_agent.aws.mock_guard import assert_real_aws_allowed

TITAN_EMBED_V2_MODEL_ID = "amazon.titan-embed-text-v2:0"
TITAN_EMBED_V2_DIMENSION = (
    1024  # default output size; 512/256 also supported. Verified live 2026-08-11:
)
# docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-titan-text-embeddings-v2.html
TITAN_EMBED_V2_MAX_CHARS = (
    50_000  # ~8,192 tokens, same source. Our chunks stay far under this by design.
)

DEFAULT_MAX_CHUNK_CHARS = (
    4_000  # generous relative to any section in this corpus; a real safety margin
)
# under Titan's ~50,000-char ceiling, not a tight fit to it.
DEFAULT_TABLE_NAME = "fnol-knowledge-chunks"
DEFAULT_CORPUS_DIR = Path("data/synthetic/policy")
DEFAULT_MANIFEST_PATH = Path("data/synthetic/.ingest-manifest.json")


# --- Chunking -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Chunk:
    section_title: str
    chunk_index: int
    text: str


def chunk_markdown(text: str, max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> list[Chunk]:
    """Split markdown into section-based chunks. See module docstring for the strategy rationale."""
    sections = _split_on_headings(text)
    chunks: list[Chunk] = []
    for title, body in sections:
        body = _HEADING_RE.sub(
            "", body, count=1
        ).strip()  # the heading line lives in `section_title`
        # already; keeping it duplicated in the chunk text too would (a) waste embedding tokens on every
        # chunk restating its own heading, and (b) mean a heading-only, body-empty section isn't actually
        # empty text -- caught by test_chunk_markdown_drops_empty_chunks, which is why this line exists.
        if not body:
            continue
        if len(body) <= max_chunk_chars:
            chunks.append(Chunk(section_title=title, chunk_index=len(chunks), text=body))
            continue
        for piece in _split_on_paragraphs(body, max_chunk_chars):
            piece = piece.strip()
            if piece:
                chunks.append(Chunk(section_title=title, chunk_index=len(chunks), text=piece))
    return chunks


_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _split_on_headings(text: str) -> list[tuple[str, str]]:
    """Split on '## ' headings. Content before the first '## ' (title, intro) is its own 'Preamble' section."""
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [("Preamble", text)]

    sections: list[tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("Preamble", preamble))

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((title, text[start:end]))
    return sections


def _split_on_paragraphs(body: str, max_chunk_chars: int) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", body)
    pieces: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) > max_chunk_chars and current:
            pieces.append(current)
            current = para
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


# --- Embedding backends ---------------------------------------------------------------------------


class Embedder(Protocol):
    model_id: str
    dimension: int

    def embed(self, text: str) -> list[float]: ...


class MockEmbedder:
    """Deterministic, zero-cost, zero-credential embedder for tests and the default `make ingest` run.

    Not a real embedding — a stable hash-derived vector, useful only for proving the pipeline's plumbing
    (chunking, hashing, idempotency, manifest emission) works end to end without spending anything. Real
    retrieval quality requires `--embeddings bedrock`.
    """

    model_id = "mock-embedder-v1"
    dimension = TITAN_EMBED_V2_DIMENSION

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Repeat the 32-byte digest out to `dimension` floats in [-1, 1] — deterministic, cheap, not
        # semantically meaningful. Good enough to unit-test "did the pipeline write a vector of the right
        # shape," not good enough to unit-test retrieval quality (that needs real embeddings, Phase 6).
        values = (digest * ((self.dimension // len(digest)) + 1))[: self.dimension]
        return [(b - 128) / 128 for b in values]


class BedrockEmbedder:
    """Real Titan Embed V2 calls via `bedrock-runtime`. Billed against the $5 Phases 3-7 standing cap."""

    model_id = TITAN_EMBED_V2_MODEL_ID
    dimension = TITAN_EMBED_V2_DIMENSION

    def __init__(self, region: str) -> None:
        # ADR-013: moto does not implement Bedrock, so a moto-intercepted embedding call would
        # return a fabricated response rather than fail — refuse to build the client at all.
        # DynamoVectorStore below is deliberately NOT guarded: moto implements DynamoDB
        # faithfully, and running it against moto is this project's default, not an accident.
        assert_real_aws_allowed("bedrock-runtime / BedrockEmbedder")
        # Region is a parameter, never a literal default baked into this class, per constraint 17 —
        # the caller (CLI) supplies it from an explicit flag/env var, not a hardcoded fallback here.
        self._client = boto3.client("bedrock-runtime", region_name=region)

    def embed(self, text: str) -> list[float]:
        response = self._client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text, "dimensions": self.dimension, "normalize": True}),
        )
        payload = json.loads(response["body"].read())
        embedding: list[float] = payload["embedding"]
        return embedding


# --- Vector store (DynamoDB, per ADR-002) ---------------------------------------------------------


class DynamoVectorStore:
    """Single-table DynamoDB store: `CHUNK#<file>#<index>` items hold chunk text + embedding;
    `STATE#<file>` items hold each source file's last-ingested hash, for the idempotency check.
    """

    def __init__(self, table_name: str, region: str, endpoint_url: str | None = None) -> None:
        resource = boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint_url)
        self._client = boto3.client("dynamodb", region_name=region, endpoint_url=endpoint_url)
        self._table_name = table_name
        self.table = resource.Table(table_name)

    def ensure_table(self) -> None:
        existing = self._client.list_tables().get("TableNames", [])
        if self._table_name in existing:
            return
        self._client.create_table(
            TableName=self._table_name,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",  # on-demand, per ADR-002/cost model — no idle capacity charge
        )
        self._client.get_waiter("table_exists").wait(TableName=self._table_name)

    def get_file_state(self, relative_path: str) -> dict[str, Any] | None:
        resp = self.table.get_item(Key={"pk": f"STATE#{relative_path}"})
        return resp.get("Item")

    def put_file_state(self, relative_path: str, file_hash: str, chunk_count: int) -> None:
        self.table.put_item(
            Item={
                "pk": f"STATE#{relative_path}",
                "source_file_hash": file_hash,
                "chunk_count": chunk_count,
                "last_ingested_at": datetime.now(UTC).isoformat(),
            }
        )

    def put_chunk(
        self,
        relative_path: str,
        chunk: Chunk,
        embedding: list[float],
        file_hash: str,
        as_of_date: str,
        embedding_model_id: str,
        embedding_dimension: int,
    ) -> None:
        self.table.put_item(
            Item={
                "pk": f"CHUNK#{relative_path}#{chunk.chunk_index}",
                "source_file": relative_path,
                "section_title": chunk.section_title,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "embedding": [
                    str(v) for v in embedding
                ],  # DynamoDB Number requires Decimal-compatible
                # strings via boto3's default serializer when passed through table.put_item with floats;
                # stored as strings here and cast back to float on read, rather than depending on boto3's
                # float->Decimal coercion behavior.
                "source_file_hash": file_hash,
                "as_of_date": as_of_date,
                "embedding_model_id": embedding_model_id,
                "embedding_dimension": embedding_dimension,
                "ingested_at": datetime.now(UTC).isoformat(),
            }
        )


# --- Manifest --------------------------------------------------------------------------------------


@dataclass
class FileManifestEntry:
    path: str
    sha256: str
    chunk_count: int
    status: str  # "embedded" | "skipped_unchanged"


@dataclass
class Manifest:
    run_timestamp: str
    corpus_as_of_date: str
    embedding_model_id: str
    embedding_dimension: int
    vector_store_backend: str
    files: list[FileManifestEntry] = field(default_factory=list)

    @property
    def total_chunks(self) -> int:
        return sum(f.chunk_count for f in self.files)

    @property
    def files_embedded(self) -> int:
        return sum(1 for f in self.files if f.status == "embedded")

    @property
    def files_skipped(self) -> int:
        return sum(1 for f in self.files if f.status == "skipped_unchanged")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_timestamp": self.run_timestamp,
            "corpus_as_of_date": self.corpus_as_of_date,
            "embedding_model_id": self.embedding_model_id,
            "embedding_dimension": self.embedding_dimension,
            "vector_store_backend": self.vector_store_backend,
            "total_chunks": self.total_chunks,
            "files_embedded_this_run": self.files_embedded,
            "files_skipped_unchanged": self.files_skipped,
            "files": [
                {
                    "path": f.path,
                    "sha256": f.sha256,
                    "chunk_count": f.chunk_count,
                    "status": f.status,
                }
                for f in self.files
            ],
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")


# --- Orchestration -----------------------------------------------------------------------------------


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_ingestion(
    corpus_dir: Path,
    store: DynamoVectorStore,
    embedder: Embedder,
    vector_store_backend_label: str,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> Manifest:
    metadata = json.loads((corpus_dir / "corpus-metadata.json").read_text())
    as_of_date = metadata["as_of_date"]

    store.ensure_table()

    manifest = Manifest(
        run_timestamp=datetime.now(UTC).isoformat(),
        corpus_as_of_date=as_of_date,
        embedding_model_id=embedder.model_id,
        embedding_dimension=embedder.dimension,
        vector_store_backend=vector_store_backend_label,
    )

    corpus_files = sorted(p for p in corpus_dir.glob("*.md"))
    for path in corpus_files:
        # `corpus_dir` is expected to be expressed relative to the repo root (the CLI default and every
        # caller in this codebase does this) -- so the path itself, as given, already reads naturally in
        # the manifest (e.g. "data/synthetic/policy/coverage-logic.md") without extra relative_to() math.
        relative_path = str(path)
        file_hash = _file_sha256(path)
        prior_state = store.get_file_state(relative_path)

        if prior_state is not None and prior_state.get("source_file_hash") == file_hash:
            manifest.files.append(
                FileManifestEntry(
                    path=relative_path,
                    sha256=file_hash,
                    chunk_count=int(prior_state.get("chunk_count", 0)),
                    status="skipped_unchanged",
                )
            )
            continue

        chunks = chunk_markdown(path.read_text(), max_chunk_chars=max_chunk_chars)
        for chunk in chunks:
            embedding = embedder.embed(chunk.text)
            store.put_chunk(
                relative_path=relative_path,
                chunk=chunk,
                embedding=embedding,
                file_hash=file_hash,
                as_of_date=as_of_date,
                embedding_model_id=embedder.model_id,
                embedding_dimension=embedder.dimension,
            )
        store.put_file_state(relative_path, file_hash, len(chunks))
        manifest.files.append(
            FileManifestEntry(
                path=relative_path, sha256=file_hash, chunk_count=len(chunks), status="embedded"
            )
        )

    manifest.write(manifest_path)
    return manifest


# --- CLI -----------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--table-name", default=DEFAULT_TABLE_NAME)
    parser.add_argument(
        "--region", default="us-west-2"
    )  # constraint 17: never a literal in application
    # logic paths that matter for a region migration — this is a CLI default a caller can override, not a
    # hardcoded assumption baked into DynamoVectorStore/BedrockEmbedder themselves.
    parser.add_argument("--vector-store", choices=["local", "aws"], default="local")
    parser.add_argument("--embeddings", choices=["mock", "bedrock"], default="mock")
    parser.add_argument("--max-chunk-chars", type=int, default=DEFAULT_MAX_CHUNK_CHARS)
    args = parser.parse_args(argv)

    embedder: Embedder = (
        MockEmbedder() if args.embeddings == "mock" else BedrockEmbedder(region=args.region)
    )

    if args.vector_store == "local":
        from moto import mock_aws

        with mock_aws():
            store = DynamoVectorStore(args.table_name, region=args.region)
            manifest = run_ingestion(
                args.corpus_dir,
                store,
                embedder,
                "local (moto)",
                args.manifest_path,
                args.max_chunk_chars,
            )
    else:
        store = DynamoVectorStore(args.table_name, region=args.region)
        manifest = run_ingestion(
            args.corpus_dir, store, embedder, "aws", args.manifest_path, args.max_chunk_chars
        )

    print(
        f"Ingestion complete: {manifest.total_chunks} chunks across {len(manifest.files)} files "
        f"({manifest.files_embedded} embedded, {manifest.files_skipped} unchanged). "
        f"Manifest: {args.manifest_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
