"""Extract text from incident report PDFs using Azure Document Intelligence."""

import json
import os

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

from src.config import DATA_DIR, DOC_INTELLIGENCE_ENDPOINT, DOC_INTELLIGENCE_KEY, PDFS_DIR


def extract_all_incidents(
    pdf_dir: str | os.PathLike | None = None,
    output_path: str | os.PathLike | None = None,
    skip_existing: bool = True,
) -> list[dict]:
    pdf_dir = pdf_dir or PDFS_DIR
    output_path = output_path or (DATA_DIR / "parsed_incidents.json")

    if skip_existing and os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if existing:
            print(f"  Skipping incident extraction ({len(existing)} docs already in {output_path})")
            return existing

    client = DocumentAnalysisClient(
        endpoint=DOC_INTELLIGENCE_ENDPOINT,
        credential=AzureKeyCredential(DOC_INTELLIGENCE_KEY),
    )

    pdf_files = sorted(f for f in os.listdir(pdf_dir) if f.endswith(".pdf"))
    total = len(pdf_files)
    documents = []

    for i, filename in enumerate(pdf_files, 1):
        filepath = os.path.join(pdf_dir, filename)
        print(f"  [{i}/{total}] Extracting: {filename}")
        try:
            with open(filepath, "rb") as f:
                poller = client.begin_analyze_document("prebuilt-document", document=f)
                result = poller.result()

            full_text = "\n".join(p.content for p in result.paragraphs)
            documents.append({
                "id": filename,
                "content": full_text,
                "source": filename,
            })
        except Exception as e:
            print(f"    ERROR on {filename}: {e}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2)

    print(f"  Saved {len(documents)} incident docs to {output_path}")
    return documents


if __name__ == "__main__":
    extract_all_incidents(skip_existing=False)
