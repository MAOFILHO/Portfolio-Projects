"""Generate captions for incident images using Azure OpenAI GPT-4o Vision."""

import base64
import json
import os

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import AZURE_GPT_DEPLOYMENT, DATA_DIR, IMAGES_DIR, get_openai_client

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


@retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(5))
def _caption_image(client, b64_image: str) -> str:
    response = client.chat.completions.create(
        model=AZURE_GPT_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": "You are an assistant that describes the content of urban safety images (e.g., accidents, floods, fire, damaged roads).",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in 1-2 sentences:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
                ],
            },
        ],
        max_tokens=100,
    )
    return response.choices[0].message.content


def extract_all_image_captions(
    image_dir: str | os.PathLike | None = None,
    output_path: str | os.PathLike | None = None,
    skip_existing: bool = True,
) -> list[dict]:
    image_dir = image_dir or IMAGES_DIR
    output_path = output_path or (DATA_DIR / "parsed_images.json")

    if skip_existing and os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if existing:
            print(f"  Skipping image captioning ({len(existing)} captions already in {output_path})")
            return existing

    client = get_openai_client()

    image_files = sorted(
        f
        for f in os.listdir(image_dir)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    )
    total = len(image_files)
    captions = []

    for i, filename in enumerate(image_files, 1):
        filepath = os.path.join(image_dir, filename)
        print(f"  [{i}/{total}] Captioning: {filename}")
        try:
            with open(filepath, "rb") as img_file:
                b64_image = base64.b64encode(img_file.read()).decode("utf-8")

            caption_text = _caption_image(client, b64_image)
            captions.append({
                "id": filename,
                "content": caption_text,
                "source": filename,
            })
        except Exception as e:
            print(f"    ERROR on {filename}: {e}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(captions, f, indent=2)

    print(f"  Saved {len(captions)} image captions to {output_path}")
    return captions


if __name__ == "__main__":
    extract_all_image_captions(skip_existing=False)
