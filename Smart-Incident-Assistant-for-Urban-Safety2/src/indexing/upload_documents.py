"""Generate embeddings and upload documents to Azure AI Search."""

import json
import os
import re
import uuid
from time import sleep

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import (
    AZURE_EMBEDDING_DEPLOYMENT,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    AZURE_SEARCH_KEY,
    DATA_DIR,
    SEARCH_API_VERSION,
    get_openai_client,
)


def _sanitize_id(value: str) -> str:
    value = os.path.splitext(value)[0]
    return re.sub(r"[^A-Za-z0-9_\-=]", "_", value)


def _derive_title(source: str) -> str:
    name = os.path.splitext(source)[0]
    return name.replace("_", " ").replace("-", " ").title()


@retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(5))
def _get_embedding(client, text: str) -> list[float] | None:
    response = client.embeddings.create(
        model=AZURE_EMBEDDING_DEPLOYMENT,
        input=[text],
    )
    return response.data[0].embedding


def _load_all_data(data_dir: str | os.PathLike) -> list[dict]:
    docs = []
    sources = [
        ("parsed_incidents.json", "incident"),
        ("parsed_images.json", "image"),
        ("parsed_sops.json", "sop"),
    ]
    for filename, dtype in sources:
        path = os.path.join(data_dir, filename)
        if not os.path.exists(path):
            print(f"  Warning: {path} not found, skipping")
            continue
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        print(f"  Loaded {len(loaded)} entries from {filename}")
        for entry in loaded:
            text = (entry.get("content") or "").strip()
            if not text:
                continue
            original_id = entry.get("id", str(uuid.uuid4()))
            docs.append({
                "id": _sanitize_id(original_id),
                "content": text,
                "content_text": text,
                "type": dtype,
                "source": entry.get("source", filename),
                "document_title": _derive_title(entry.get("source", original_id)),
            })
    return docs


def _upload_batch(batch: list[dict]) -> bool:
    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}/docs/index?api-version={SEARCH_API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": AZURE_SEARCH_KEY}
    resp = requests.post(url, headers=headers, json={"value": batch})
    if resp.status_code in (200, 201):
        print(f"    Uploaded batch of {len(batch)} docs")
        return True
    print(f"    ERROR uploading batch: {resp.status_code} — {resp.text[:200]}")
    return False


def embed_and_upload_all(
    data_dir: str | os.PathLike | None = None,
    batch_size: int = 10,
) -> int:
    data_dir = data_dir or DATA_DIR
    client = get_openai_client()

    all_docs = _load_all_data(data_dir)
    total = len(all_docs)
    print(f"  Total documents to embed & upload: {total}")

    uploaded = 0
    batch = []

    for i, doc in enumerate(all_docs, 1):
        print(f"  [{i}/{total}] Embedding: {doc['source']}")
        embedding = _get_embedding(client, doc["content"])
        if not embedding or len(embedding) != 1536:
            print(f"    Warning: skipping {doc['source']} (bad embedding)")
            continue

        batch.append({
            "@search.action": "upload",
            "id": doc["id"],
            "content": doc["content"],
            "content_text": doc["content_text"],
            "type": doc["type"],
            "source": doc["source"],
            "document_title": doc["document_title"],
            "embedding": embedding,
        })

        if len(batch) >= batch_size or i == total:
            if _upload_batch(batch):
                uploaded += len(batch)
            batch = []
            sleep(1)

    print(f"  Upload complete: {uploaded}/{total} documents indexed")
    return uploaded


if __name__ == "__main__":
    from src.config import validate_env
    validate_env()
    embed_and_upload_all()
