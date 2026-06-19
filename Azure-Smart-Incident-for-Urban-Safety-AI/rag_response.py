import os
import requests
import json
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load .env vars
load_dotenv()
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")

AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_GPT_DEPLOYMENT = os.getenv("AZURE_GPT_DEPLOYMENT")
AZURE_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_EMBEDDING_DEPLOYMENT")

# OpenAI client
client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version="2025-04-01-preview"
)

# Chat history to store up to 10 turns (user query and assistant response)
chat_history = []

# Embedding
def get_embedding(text: str):
    if not text.strip():  # Ensure non-empty string
        print("❌ Input text is empty.")
        return None
    
    try:
        response = client.embeddings.create(
            model=AZURE_EMBEDDING_DEPLOYMENT,
            input=[text]  # Ensure it's in list format
        )
        embedding = response.data[0].embedding
        print(f"✅ Got embedding of length {len(embedding)}")
        return embedding
    except Exception as e:
        print(f"❌ Failed to generate embedding: {e}")
        return None


# Search
def retrieve_docs(query_text):
    vector = get_embedding(query_text)
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
                "vector": vector,
                "fields": "embedding",
                "k": 5
            }
        ],
        "select": "id,content,type,source"
    }
    response = requests.post(url, headers=headers, json=payload)
    results = response.json().get("value", [])
    return results

# Build RAG prompt with chat history
def build_prompt(query, docs):
    context = "\n\n---\n\n".join([doc["content"] for doc in docs])
    
    # Add chat history context
    history_context = "\n\n".join([f"User: {entry['content']}\nAssistant: {entry['response']}" for entry in chat_history])

    return f"""You are an assistant helping city officials understand incident data.

Use the following retrieved information to answer the question.

Context:
{context}

Chat History:
{history_context}

Question:
{query}

Answer:
"""

# Generate GPT response
def generate_answer(prompt):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a smart incident response assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

# Run
if __name__ == "__main__":
    while True:
        query = input("🧠 Ask something about incidents: ").strip()
        if query.lower() == 'exit':
            break
        docs = retrieve_docs(query)
        if not docs:
            print("⚠️ No documents found.")
        else:
            prompt = build_prompt(query, docs)
            answer = generate_answer(prompt)
            print(f"\n💬 Answer:\n{answer}")

            # Append the current query and response to the chat history
            chat_history.append({"content": query, "response": answer})

            # Keep chat history to a maximum of 10 turns
            if len(chat_history) > 10:
                chat_history.pop(0)  # Remove the oldest turn
