import os
import json

sop_dir = "sops/"
output_file = "data/parsed_sops.json"

documents = []

for filename in os.listdir(sop_dir):
    filepath = os.path.join(sop_dir, filename)
    if filename.lower().endswith(".txt"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read().strip()
                if text:
                    documents.append({
                        "id": filename,
                        "content": text,
                        "source": filename
                    })
                    print(f"✅ Extracted from {filename}")
        except Exception as e:
            print(f"❌ Error reading {filename}: {e}")

# Save result
os.makedirs("data", exist_ok=True)
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(documents, f, indent=2)

print(f"\n📁 Saved {len(documents)} SOP documents to: {output_file}")
