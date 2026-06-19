import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AzureOpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PDFS_DIR = PROJECT_ROOT / "pdfs"
IMAGES_DIR = PROJECT_ROOT / "images"
SOPS_DIR = PROJECT_ROOT / "sops"

OPENAI_API_VERSION = "2024-12-01-preview"
SEARCH_API_VERSION = "2024-07-01"

load_dotenv(PROJECT_ROOT / ".env")

_REQUIRED_VARS = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_KEY",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_KEY",
    "DOC_INTELLIGENCE_ENDPOINT",
    "DOC_INTELLIGENCE_KEY",
]


def _get(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and not val:
        print(f"ERROR: Missing required environment variable: {name}", file=sys.stderr)
        print(f"  Copy .env.template to .env and fill in your values,", file=sys.stderr)
        print(f"  or run: python -m src.provision", file=sys.stderr)
        sys.exit(1)
    return val or ""


DOC_INTELLIGENCE_ENDPOINT = _get("DOC_INTELLIGENCE_ENDPOINT")
DOC_INTELLIGENCE_KEY = _get("DOC_INTELLIGENCE_KEY")

AZURE_OPENAI_ENDPOINT = _get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = _get("AZURE_OPENAI_KEY")
AZURE_GPT_DEPLOYMENT = _get("AZURE_GPT_DEPLOYMENT", "gpt-4o")
AZURE_EMBEDDING_DEPLOYMENT = _get("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

AZURE_SEARCH_ENDPOINT = _get("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = _get("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX = _get("AZURE_SEARCH_INDEX", "urban-index")

SERP_API_KEY = _get("SERP_API_KEY")


def validate_env():
    missing = [v for v in _REQUIRED_VARS if not os.getenv(v)]
    if missing:
        print("ERROR: Missing required environment variables:", file=sys.stderr)
        for v in missing:
            print(f"  - {v}", file=sys.stderr)
        print("\nRun: python -m src.provision  (or copy .env.template to .env)", file=sys.stderr)
        sys.exit(1)


def get_openai_client() -> AzureOpenAI:
    validate_env()
    return AzureOpenAI(
        api_key=AZURE_OPENAI_KEY,
        api_version=OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
    )
