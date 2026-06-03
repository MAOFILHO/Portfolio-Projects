
import os
import json
import uuid
import requests
from dotenv import load_dotenv
from openai import AzureOpenAI
from time import sleep
import re

# Load .env
load_dotenv()

# Azure AI Search
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX")

# Azure OpenAI
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_EMBEDDING_DEPLOYMENT")

# Init OpenAI
client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version="2024-02-15-preview"
)

# Helper: sanitize ID
def sanitize_id(value):
    value = os.path.splitext(value)[0]  # Remove extension like .pdf
    return re.sub(r'[^A-Za-z0-9_\-=]', '_', value)  # Replace invalid chars

# Helper: get embedding
def get_embedding(text: str):
    try:
        response = client.embeddings.create(
            model=AZURE_EMBEDDING_DEPLOYMENT,
            input=[text]
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ Embedding error: {e}")
        return None

# Helper: load JSON data
def load_data():
    docs = []
    sources = [
        ("data/parsed_incidents.json", "incident"),
        ("data/parsed_images.json", "image"),
        ("data/parsed_sops.json", "sop")
    ]
    for path, dtype in sources:
        print(f"🔍 Checking file: {path}")
        if not os.path.exists(path):
            print(f"⚠️ Skipped missing file: {path}")
            continue
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            print(f"📂 Loaded {len(loaded)} entries from {path}")
            for entry in loaded:
                text = entry.get("content", "").strip()
                if not text:
                    print(f"⚠️ Empty content in entry: {entry}")
                    continue
                original_id = entry.get("id", str(uuid.uuid4()))
                safe_id = sanitize_id(original_id)
                docs.append({
                    "id": safe_id,
                    "content": text,
                    "type": dtype,
                    "source": entry.get("source", os.path.basename(path))
                })
    return docs

# Helper: upload batch
def upload_batch(batch):
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/index?api-version=2024-07-01"
    headers = {
        "Content-Type": "application/json",
        "api-key": SEARCH_KEY
    }
    response = requests.post(url, headers=headers, json={"value": batch})
    if response.status_code in [200, 201]:
        print(f"✅ Uploaded {len(batch)} docs")
    else:
        print(f"❌ Upload failed: {response.status_code}")
        print(response.text)

# Main
if __name__ == "__main__":
    all_docs = load_data()
    print(f"📄 Total docs to embed & upload: {len(all_docs)}")

    batch = []
    for i, doc in enumerate(all_docs):
        embedding = get_embedding(doc["content"])
        if not embedding or len(embedding) != 1536:
            print(f"⚠️ Skipping: Embedding issue or wrong length")
            continue

        batch.append({
            "@search.action": "upload",
            "id": doc["id"],
            "content": doc["content"],
            "type": doc["type"],
            "source": doc["source"],
            "embedding": embedding
        })

        if len(batch) == 10 or i == len(all_docs) - 1:
            upload_batch(batch)
            batch = []
            sleep(1)
