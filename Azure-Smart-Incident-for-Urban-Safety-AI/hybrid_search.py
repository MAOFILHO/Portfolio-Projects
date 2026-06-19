import os
import requests
import json
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_EMBEDDING_DEPLOYMENT")

# Init OpenAI client
client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version="2024-02-15-preview"
)

# Generate embedding
def get_embedding(text):
    try:
        print(f"🔎 Generating embedding for query...")
        response = client.embeddings.create(
            model=AZURE_EMBEDDING_DEPLOYMENT,
            input=[text]
        )
        embedding = response.data[0].embedding
        print(f"✅ Got embedding of length {len(embedding)}")
        return embedding
    except Exception as e:
        print(f"❌ Failed to generate embedding: {e}")
        return None

# Perform hybrid search
def hybrid_search(query_text):
    embedding = get_embedding(query_text)
    if not embedding:
        return

    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}/docs/search?api-version=2024-07-01"
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_SEARCH_KEY
    }

    payload = {
        "search": query_text,
        "vectorQueries": [
            {
                "kind": "vector",
                "vector": embedding,
                "fields": "embedding",
                "k": 10
            }
        ],
        "select": "id,content,type,source"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code not in (200, 201):
            print(f"❌ Search failed: {response.status_code}")
            print(response.text)
            return

        results = response.json().get("value", [])
        print(f"\n🔍 Top Results:")
        for item in results:
            print(f"\n📄 ID: {item['id']}")
            print(f"📘 Type: {item['type']}")
            print(f"📎 Source: {item['source']}")
            print(f"📝 Content: {item['content'][:300]}...\n")
    except Exception as e:
        print(f"❌ Error in search: {e}")

# Run
if __name__ == "__main__":
    query = input("📝 Enter your query: ").strip()
    if query:
        hybrid_search(query)
