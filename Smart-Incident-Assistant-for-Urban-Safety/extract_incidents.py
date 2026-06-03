import os
import json
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

load_dotenv()

AI_DOC_KEY = os.getenv("DOC_INTELLIGENCE_KEY")
AI_DOC_ENDPOINT = os.getenv("DOC_INTELLIGENCE_ENDPOINT")

pdf_dir = "pdfs/"
output_file = "data/parsed_incidents.json"

client = DocumentAnalysisClient(
    endpoint=AI_DOC_ENDPOINT,
    credential=AzureKeyCredential(AI_DOC_KEY)
)

documents = []

for file in os.listdir(pdf_dir):
    if file.endswith(".pdf"):
        filepath = os.path.join(pdf_dir, file)
        with open(filepath, "rb") as f:
            poller = client.begin_analyze_document("prebuilt-document", document=f)
            result = poller.result()

            full_text = "\n".join([p.content for p in result.paragraphs])
            documents.append({
                "id": file,
                "content": full_text,
                "source": file
            })
            print(f"✅ Extracted from {file}")

# Save to output JSON
os.makedirs("data", exist_ok=True)
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(documents, f, indent=2)

print(f"\n📁 Saved {len(documents)} incident docs to: {output_file}")
