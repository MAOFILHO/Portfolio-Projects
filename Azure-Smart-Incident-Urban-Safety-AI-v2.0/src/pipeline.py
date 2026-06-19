"""
End-to-end pipeline orchestrator.

Usage:
    python -m src.pipeline                  # Full pipeline (skip existing data)
    python -m src.pipeline --force          # Force re-extraction of all data
    python -m src.pipeline --steps extract  # Only run extraction
    python -m src.pipeline --steps index    # Only run indexing
"""

import argparse
import time

from src.config import DATA_DIR, validate_env


def step_extract(force: bool = False):
    print("\n" + "=" * 50)
    print("STEP 1: Data Extraction")
    print("=" * 50)
    skip = not force

    from src.extraction.extract_incidents import extract_all_incidents
    from src.extraction.extract_images import extract_all_image_captions
    from src.extraction.extract_sops import extract_all_sops

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("\n--- 1a. Extract Incident Reports from PDFs ---")
    incidents = extract_all_incidents(skip_existing=skip)
    print(f"  Result: {len(incidents)} incident documents")

    print("\n--- 1b. Caption Incident Images with GPT-4o Vision ---")
    images = extract_all_image_captions(skip_existing=skip)
    print(f"  Result: {len(images)} image captions")

    print("\n--- 1c. Parse Standard Operating Procedures ---")
    sops = extract_all_sops(skip_existing=skip)
    print(f"  Result: {len(sops)} SOP documents")

    total = len(incidents) + len(images) + len(sops)
    print(f"\n  Total extracted: {total} documents")
    return total


def step_index():
    print("\n" + "=" * 50)
    print("STEP 2: Embedding & Indexing")
    print("=" * 50)

    from src.indexing.create_index import create_or_update_index
    from src.indexing.upload_documents import embed_and_upload_all

    print("\n--- 2a. Create Vector Index in Azure AI Search ---")
    success = create_or_update_index(delete_existing=False)
    if not success:
        print("  ERROR: Failed to create index. Aborting.")
        return 0

    print("\n--- 2b. Embed & Upload Documents ---")
    uploaded = embed_and_upload_all()
    print(f"\n  Total indexed: {uploaded} documents")
    return uploaded


def main():
    parser = argparse.ArgumentParser(description="Smart Incident Assistant Pipeline")
    parser.add_argument("--steps", choices=["extract", "index", "all"], default="all")
    parser.add_argument("--force", action="store_true", help="Force re-extraction")
    args = parser.parse_args()

    print("=" * 50)
    print("Contoso Smart Incident Assistant — Pipeline")
    print("=" * 50)

    validate_env()
    start = time.time()

    if args.steps in ("extract", "all"):
        step_extract(force=args.force)

    if args.steps in ("index", "all"):
        step_index()

    elapsed = time.time() - start
    print(f"\n{'=' * 50}")
    print(f"Pipeline complete in {elapsed:.1f}s")
    print(f"{'=' * 50}")
    print("\nNext: streamlit run src/web/app.py")


if __name__ == "__main__":
    main()
