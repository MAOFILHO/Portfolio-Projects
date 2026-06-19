"""Parse and structure Standard Operating Procedure text files."""

import json
import os

from src.config import DATA_DIR, SOPS_DIR


def extract_all_sops(
    sop_dir: str | os.PathLike | None = None,
    output_path: str | os.PathLike | None = None,
    skip_existing: bool = True,
) -> list[dict]:
    sop_dir = sop_dir or SOPS_DIR
    output_path = output_path or (DATA_DIR / "parsed_sops.json")

    if skip_existing and os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if existing:
            print(f"  Skipping SOP extraction ({len(existing)} docs already in {output_path})")
            return existing

    sop_files = sorted(f for f in os.listdir(sop_dir) if f.lower().endswith(".txt"))
    total = len(sop_files)
    documents = []

    for i, filename in enumerate(sop_files, 1):
        filepath = os.path.join(sop_dir, filename)
        print(f"  [{i}/{total}] Parsing: {filename}")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                documents.append({
                    "id": filename,
                    "content": text,
                    "source": filename,
                })
        except Exception as e:
            print(f"    ERROR on {filename}: {e}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2)

    print(f"  Saved {len(documents)} SOP docs to {output_path}")
    return documents


if __name__ == "__main__":
    extract_all_sops(skip_existing=False)
