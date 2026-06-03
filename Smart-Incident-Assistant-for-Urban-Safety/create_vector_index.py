import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
admin_key = os.getenv("AZURE_SEARCH_KEY")
index_name = os.getenv("AZURE_SEARCH_INDEX")
openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
openai_key = os.getenv("AZURE_OPENAI_KEY")
deployment_id = os.getenv("AZURE_EMBEDDING_DEPLOYMENT")

# API version that supports vectorizers
api_version = "2024-07-01"
url = f"{endpoint}/indexes/{index_name}?api-version={api_version}"

# Headers
headers = {
    "Content-Type": "application/json",
    "api-key": admin_key
}

# Step 1: Delete existing index
delete_url = f"{endpoint}/indexes/{index_name}?api-version={api_version}"
delete_resp = requests.delete(delete_url, headers=headers)

if delete_resp.status_code in (200, 204):
    print(f"✅ Index '{index_name}' deleted successfully.")
else:
    print(f"❌ Error {delete_resp.status_code} while deleting index:")
    print(delete_resp.text)

# Step 2: Create new index with updated schema
index_schema = {
    "name": index_name,
    "fields": [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
        {"name": "content", "type": "Edm.String", "searchable": True, "retrievable": True},
        {"name": "content_text", "type": "Edm.String", "searchable": True, "retrievable": True},  # Add content_text field
        {"name": "source", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "type", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "document_title", "type": "Edm.String", "retrievable": True, "searchable": True},  # Add document_title field
        {
            "name": "embedding",
            "type": "Collection(Edm.Single)",
            "dimensions": 1536,
            "vectorSearchProfile": "default-profile"
        }
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
                    "efSearch": 500
                }
            }
        ],
        "profiles": [
            {
                "name": "default-profile",
                "algorithm": "default-algo",
                "vectorizer": "azureOpenAI-vectorizer"
            }
        ],
        "vectorizers": [
            {
                "name": "azureOpenAI-vectorizer",
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": openai_endpoint,
                    "deploymentId": deployment_id,
                    "apiKey": openai_key,
                    "modelName": "text-embedding-3-small"  # Corrected model name
                }
            }
        ]
    }
}

# Send request to create new index
resp = requests.put(url, headers=headers, json=index_schema)

if resp.status_code in (200, 201):
    print(f"✅ Index '{index_name}' created successfully using 2024-07-01 API.")
else:
    print(f"❌ Error {resp.status_code} while creating index:")
    print(resp.text)
