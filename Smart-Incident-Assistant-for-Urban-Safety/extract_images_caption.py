import os
import json
import base64
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_GPT_DEPLOYMENT = os.getenv("AZURE_GPT_DEPLOYMENT")

client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-02-15-preview",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

image_dir = "images/"
output_file = "data/parsed_images.json"
image_extensions = [".jpg", ".jpeg", ".png"]

captions = []

for folder, _, files in os.walk(image_dir):
    for file in files:
        if not any(file.lower().endswith(ext) for ext in image_extensions):
            continue

        file_path = os.path.join(folder, file)
        with open(file_path, "rb") as img_file:
            b64_image = base64.b64encode(img_file.read()).decode("utf-8")

        print(f"🖼 Captioning: {file}")

        try:
            response = client.chat.completions.create(
                model=AZURE_GPT_DEPLOYMENT,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an assistant that describes the content of urban safety images (e.g., accidents, floods, fire, damaged roads)."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image in 1-2 sentences:"},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}"
                            }}
                        ]
                    }
                ],
                max_tokens=100
            )

            caption = response.choices[0].message.content
            captions.append({
                "id": file,
                "content": caption,
                "source": file
            })
        except Exception as e:
            print(f"❌ Failed to caption {file}: {e}")

# Save to JSON
os.makedirs("data", exist_ok=True)
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(captions, f, indent=2)

print(f"\n📁 Saved {len(captions)} image captions to: {output_file}")
