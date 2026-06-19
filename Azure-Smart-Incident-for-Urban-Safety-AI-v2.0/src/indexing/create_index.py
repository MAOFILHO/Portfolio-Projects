"""Create HNSW vector index in Azure AI Search."""

import requests

from src.config import (
    AZURE_EMBEDDING_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_KEY,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    AZURE_SEARCH_KEY,
    SEARCH_API_VERSION,
)


def index_exists() -> bool:
    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}?api-version={SEARCH_API_VERSION}"
    resp = requests.get(url, headers={"api-key": AZURE_SEARCH_KEY})
    return resp.status_code == 200


def create_or_update_index(delete_existing: bool = False) -> bool:
    headers = {"Content-Type": "application/json", "api-key": AZURE_SEARCH_KEY}
    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}?api-version={SEARCH_API_VERSION}"

    if delete_existing:
        print("  Deleting existing index...")
        resp = requests.delete(url, headers=headers)
        if resp.status_code in (200, 204):
            print(f"    Index '{AZURE_SEARCH_INDEX}' deleted")
        elif resp.status_code != 404:
            print(f"    Warning: delete returned {resp.status_code}")
    elif index_exists():
        print(f"  Index '{AZURE_SEARCH_INDEX}' already exists, skipping creation")
        return True

    index_schema = {
        "name": AZURE_SEARCH_INDEX,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "content", "type": "Edm.String", "searchable": True, "retrievable": True},
            {"name": "content_text", "type": "Edm.String", "searchable": True, "retrievable": True},
            {"name": "source", "type": "Edm.String", "filterable": True, "retrievable": True},
            {"name": "type", "type": "Edm.String", "filterable": True, "retrievable": True},
            {"name": "document_title", "type": "Edm.String", "retrievable": True, "searchable": True},
            {
                "name": "embedding",
                "type": "Collection(Edm.Single)",
                "dimensions": 1536,
                "vectorSearchProfile": "default-profile",
            },
        ],
        "vectorSearch": {
            "algorithms": [
                {
                    "name": "default-algo",
                    "kind": "hnsw",
                    "hnswParameters": {
                        "metric": "cosine",
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                    },
                }
            ],
            "profiles": [
                {
                    "name": "default-profile",
                    "algorithm": "default-algo",
                    "vectorizer": "azureOpenAI-vectorizer",
                }
            ],
            "vectorizers": [
                {
                    "name": "azureOpenAI-vectorizer",
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": AZURE_OPENAI_ENDPOINT,
                        "deploymentId": AZURE_EMBEDDING_DEPLOYMENT,
                        "apiKey": AZURE_OPENAI_KEY,
                        "modelName": "text-embedding-3-small",
                    },
                }
            ],
        },
    }

    print(f"  Creating index '{AZURE_SEARCH_INDEX}'...")
    resp = requests.put(url, headers=headers, json=index_schema)

    if resp.status_code in (200, 201):
        print(f"    Index '{AZURE_SEARCH_INDEX}' created (HNSW, 1536-dim, cosine)")
        return True

    print(f"    ERROR creating index: {resp.status_code}")
    print(f"    {resp.text}")
    return False


if __name__ == "__main__":
    from src.config import validate_env
    validate_env()
    create_or_update_index(delete_existing=True)
