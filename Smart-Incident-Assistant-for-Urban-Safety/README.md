# 🏙️ Smart Incident Assistant for Urban Safety
### Multimodal RAG on Azure | AI-Powered Municipal Intelligence System

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Azure OpenAI](https://img.shields.io/badge/Azure%20OpenAI-GPT--4o-0078D4?style=flat&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com/products/ai-services/openai-service)
[![Azure AI Search](https://img.shields.io/badge/Azure%20AI%20Search-Vector%20+%20Hybrid-0078D4?style=flat&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com/products/ai-services/ai-search)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📋 Table of Contents

- [Scenario](#-scenario)
- [Architecture Overview](#-architecture-overview)
- [Azure Services Used](#-azure-services-used)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Setup & Installation](#-setup--installation)
- [Environment Configuration](#-environment-configuration)
- [Running the Pipeline](#-running-the-pipeline)
- [Sample Queries](#-sample-queries)
- [Key Concepts](#-key-concepts)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Scenario

You are part of a **municipal development team** building an AI-powered assistant to enhance the analysis of urban safety incidents. The assistant integrates three categories of data sources:

| Data Type | Source | Example |
|---|---|---|
| **Structured** | Incident report PDFs | Traffic accident reports, fire logs |
| **Visual** | Incident images | Flood photos, road damage imagery |
| **Procedural** | SOP text files | Fire response protocol, pothole repair SOP |

Using a **Retrieval-Augmented Generation (RAG)** approach, the assistant delivers accurate, context-grounded answers to queries like:

- *"What incidents were reported in the west zone?"*
- *"Show me all fire-related incidents from May, including photos."*
- *"What actions were taken for road damage shown in image X?"*
- *"Which SOP applies to electrical hazards near Zone B?"*

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION LAYER                         │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Incident    │  │  Incident    │  │   Standard Operating     │  │
│  │  PDFs        │  │  Images      │  │   Procedures (.txt)      │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
│         │                 │                        │                │
│         ▼                 ▼                        ▼                │
│  ┌─────────────┐  ┌───────────────┐  ┌────────────────────────┐    │
│  │  Azure Doc  │  │  Azure OpenAI │  │  extract_sops.py       │    │
│  │Intelligence │  │  GPT-4o Vision│  │  (direct text parsing) │    │
│  └──────┬──────┘  └──────┬────────┘  └────────────┬───────────┘    │
│         │                │                         │                │
│         ▼                ▼                         ▼                │
│    parsed_incidents  parsed_images            parsed_sops           │
│         .json            .json                    .json             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      EMBEDDING & INDEXING LAYER                     │
│                                                                     │
│          Azure OpenAI text-embedding-3-small (1536-dim)            │
│                              │                                      │
│                              ▼                                      │
│              Azure AI Search — HNSW Vector Index                   │
│              (Hybrid: vector + keyword, API v2024-07-01)           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        RAG QUERY LAYER                              │
│                                                                     │
│   User Query → Embed → Hybrid Search → Top-k Docs → GPT-4o →      │
│                                                   Context-aware     │
│                                                   Response          │
│                    (with Chat History Memory: last 10 turns)       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ☁️ Azure Services Used

| Service | Purpose | Model / Config |
|---|---|---|
| **Azure AI Foundry** | Unified hub for deploying and managing AI models | — |
| **Azure OpenAI — GPT-4o** | Image captioning, RAG answer generation | `gpt-4o` (2024-11-20) |
| **Azure OpenAI — Embeddings** | Convert text to semantic vectors | `text-embedding-3-small` (1536-dim) |
| **Azure Document Intelligence** | Extract text from incident report PDFs | `prebuilt-document` layout model |
| **Azure AI Vision** | OCR and image understanding for incident photos | Standard S1 |
| **Azure AI Search** | Hybrid vector + keyword search index | HNSW, API `2024-07-01` |

> **Estimated Lab Cost:** ~$2.00 USD (depending on volume). Deploy all resources in the **same region** (e.g., East US) to avoid regional mismatch errors.

---

## 📁 Project Structure

```
smart-incident-assistant/
│
├── 📂 data/                        # Auto-generated parsed JSON outputs
│   ├── parsed_incidents.json       # Extracted text from incident PDFs
│   ├── parsed_images.json          # AI-generated captions for incident images
│   └── parsed_sops.json            # Structured SOP content from .txt files
│
├── 📂 pdfs/                        # Incident report PDF files (input)
├── 📂 images/                      # Incident image files (input — .jpg/.png)
├── 📂 sops/                        # SOP plain text files (input)
│
├── 🐍 extract_incidents.py         # Step 1a: Extract text from PDFs via Azure Doc Intelligence
├── 🐍 extract_images_caption.py    # Step 1b: Caption images via Azure OpenAI GPT-4o Vision
├── 🐍 extract_sops.py              # Step 1c: Parse and structure SOP .txt files
│
├── 🐍 create_vector_index.py       # Step 2a: Create HNSW vector index in Azure AI Search
├── 🐍 prepare_search_documents.py  # Step 2b: Generate embeddings and upload to index
│
├── 🐍 hybrid_search.py             # Step 3: Run hybrid (vector + keyword) search queries
├── 🐍 rag_response.py              # Step 4: Full RAG pipeline with chat history and GPT-4o
│
├── 🐍 script.py                    # Dependency verification script
├── 📄 requirements.txt             # Python dependencies
└── 📄 .env                         # Environment variables (not committed to source control)
```

---

## ✅ Prerequisites

- **Python 3.10+**
- An active **Azure subscription** (Free Tier or Paid)
- The following Azure resources provisioned (all in the same region):
  - Azure AI Foundry with a project
  - Azure OpenAI deployments: `gpt-4o` and `text-embedding-3-small`
  - Azure Document Intelligence (Free F0 tier is sufficient for labs)
  - Azure AI Vision (Standard S1)
  - Azure AI Search (Standard tier — required for vector search)

---

## ⚙️ Setup & Installation

**1. Clone the repository**

```bash
git clone https://github.com/MAOFILHO/Smart-Incident-Assistant-for-Urban-Safety.git
cd smart-incident-assistant
```

**2. Create a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Verify installation**

```bash
python script.py
# No import errors = environment is ready
```

---

## 🔐 Environment Configuration

Create a `.env` file in the project root and populate with your Azure resource keys and endpoints:

```env
# Azure Document Intelligence
DOC_INTELLIGENCE_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
DOC_INTELLIGENCE_KEY=<your-document-intelligence-key>

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://<your-foundry-resource>.openai.azure.com/
AZURE_OPENAI_KEY=<your-openai-key>
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_GPT_DEPLOYMENT=gpt-4o

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://<your-search-resource>.search.windows.net
AZURE_SEARCH_KEY=<your-search-admin-key>
AZURE_SEARCH_INDEX=urban-index
```

> ⚠️ **Never commit your `.env` file.** Add it to `.gitignore`.

Where to find these values in the Azure Portal:
- **OpenAI key/endpoint** → AI Foundry resource → Keys and Endpoint → OpenAI tab
- **Document Intelligence key** → Resource → Keys and Endpoint
- **Search key** → Search service → Settings → Keys

---

## 🚀 Running the Pipeline

Run the scripts in order. Each step feeds into the next.

### Step 1 — Data Extraction

```bash
# Extract text from incident report PDFs
python extract_incidents.py
# Output: data/parsed_incidents.json

# Generate AI captions for incident images
python extract_images_caption.py
# Output: data/parsed_images.json

# Parse Standard Operating Procedure text files
python extract_sops.py
# Output: data/parsed_sops.json
```

### Step 2 — Embedding & Indexing

```bash
# Create the vector index in Azure AI Search
python create_vector_index.py
# Creates index: urban-index (HNSW, 1536-dim, cosine similarity)

# Generate embeddings and upload all documents to the index
python prepare_search_documents.py
# Uploads: incidents + images + SOPs with embeddings
```

### Step 3 — Hybrid Search (Test)

```bash
python hybrid_search.py
# Prompt: What happens on King Fahd Road involving fire?
```

### Step 4 — RAG Response (Full Assistant)

```bash
python rag_response.py
# Interactive multi-turn assistant with chat history (last 10 turns)
# Type 'exit' to quit
```

---

## 💬 Sample Queries

Test the assistant with these queries using `rag_response.py` or `hybrid_search.py`:

```
What happened on King Fahd Road involving fire?
What incidents occurred in Zone B during May?
Show me all road damage incidents with photos.
Which SOP is used for minor fires?
List pothole incidents and their actions taken.
Was any flooding reported in East Zone?
Show the SOP used for blocked roads.
Were there incidents reported from Exit 10?
Give me reports involving both fire and flooding.
What actions were taken for severe incidents in Zone C?
```

---

## 📚 Key Concepts

### Retrieval-Augmented Generation (RAG)
Combines a retrieval system (Azure AI Search) with a generative LLM (GPT-4o). The workflow:
1. Embed the user query using `text-embedding-3-small`
2. Retrieve the top-k semantically similar documents from the vector index
3. Inject retrieved documents as context into the GPT-4o prompt
4. Generate a grounded, accurate response

### Hybrid Search
Combines **keyword-based** and **semantic vector** search in a single query, capturing both exact term matches (e.g., "King Fahd Road") and fuzzy semantic matches (e.g., "fire near western zone").

### Chat History Memory
The RAG assistant maintains a rolling window of the last **10 conversation turns**, injecting prior Q&A into the prompt to support multi-turn, context-aware dialogue.

### Multimodal Ingestion
Incident images are processed through GPT-4o Vision to generate natural language captions, which are then embedded and indexed alongside text documents — enabling image content to be retrieved via text queries.

---

## 🔧 Troubleshooting

**`AttributeError: 'NoneType' object has no attribute 'strip'`**

Some image entries may have empty content fields. In `prepare_search_documents.py`, replace:
```python
text = entry.get("content", "").strip()
```
with:
```python
text = (entry.get("content") or "").strip()
```

**Error Code 400 in `rag_response.py`**

- Double-check that `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, and `AZURE_EMBEDDING_DEPLOYMENT` in `.env` exactly match the values shown in Azure AI Foundry → Keys and Endpoint
- Ensure all three resources (AI Foundry, Search, Document Intelligence) are deployed in the **same Azure region**
- Confirm your deployment names match — they are case-sensitive

**Search returns no results**

- Verify the index `urban-index` exists in your Azure AI Search resource (Indexes blade)
- Confirm `prepare_search_documents.py` completed successfully and shows "Uploaded X docs"
- Check that `AZURE_SEARCH_INDEX` in `.env` matches the index name exactly

---

## 📖 Reference Documentation

- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/overview)
- [Azure AI Search Vector Search](https://learn.microsoft.com/azure/search/vector-search-overview)
- [Azure Document Intelligence](https://learn.microsoft.com/azure/ai-services/document-intelligence/)
- [Retrieval-Augmented Generation on Azure](https://learn.microsoft.com/azure/machine-learning/concept-retrieval-augmented-generation)
- [text-embedding-3-small Model](https://learn.microsoft.com/azure/ai-services/openai/tutorials/embeddings)

---

## 🙌 Acknowledgements

Project Guide — Multimodal RAG on Azure.
