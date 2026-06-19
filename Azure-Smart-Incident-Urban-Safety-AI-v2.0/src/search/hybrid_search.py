"""Hybrid (vector + keyword) search against Azure AI Search."""

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import (
    AZURE_EMBEDDING_DEPLOYMENT,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    AZURE_SEARCH_KEY,
    SEARCH_API_VERSION,
    get_openai_client,
)


@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def _get_embedding(client, text: str) -> list[float]:
    response = client.embeddings.create(
        model=AZURE_EMBEDDING_DEPLOYMENT,
        input=[text],
    )
    return response.data[0].embedding


def hybrid_search(query_text: str, top_k: int = 5) -> list[dict]:
    client = get_openai_client()
    embedding = _get_embedding(client, query_text)

    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}/docs/search?api-version={SEARCH_API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": AZURE_SEARCH_KEY}

    payload = {
        "search": query_text,
        "vectorQueries": [
            {
                "kind": "vector",
                "vector": embedding,
                "fields": "embedding",
                "k": top_k,
            }
        ],
        "select": "id,content,type,source,document_title",
        "top": top_k,
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code not in (200, 201):
        print(f"  Search error: {response.status_code} — {response.text[:200]}")
        return []

    return response.json().get("value", [])


if __name__ == "__main__":
    from src.config import validate_env
    validate_env()
    query = input("Enter your query: ").strip()
    if query:
        results = hybrid_search(query)
        for r in results:
            print(f"\n  [{r.get('type', '?')}] {r.get('source', '?')}")
            print(f"  {r.get('content', '')[:200]}...")
