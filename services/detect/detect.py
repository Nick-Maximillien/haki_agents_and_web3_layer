import os
import json
import numpy as np
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity
from vertexai import init as vertex_init
from vertexai.language_models import TextEmbeddingModel

# ----------------------------
# Vertex AI Setup (unchanged)
# ----------------------------
SA_PATH = Path("/etc/secrets/gcp_sa.json")
if SA_PATH.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(SA_PATH)
else:
    SA_PATH = Path(r"C:/Users/hp/Desktop/agents/central-accord-475812-g4-6d21ba7b0230.json")
    if not SA_PATH.exists():
        raise RuntimeError(f"Service account JSON not found at {SA_PATH}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(SA_PATH)

GOOGLE_APPLICATION_CREDENTIALS = os.environ["GOOGLE_APPLICATION_CREDENTIALS"].replace("\\", "/")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

GCP_PROJECT_ID = "central-accord-475812-g4"
GCP_LOCATION = "us-central1"

vertex_init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
model = TextEmbeddingModel.from_pretrained("text-embedding-004")

# ----------------------------
# Path to suspects.json
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent  # services/detect/
SUSPECTS_PATH = BASE_DIR / "suspects.json"

# ----------------------------
# Detection Logic as Function
# ----------------------------
def run_detection(
    registered_text: str = None,
    metadata_description: str = "",
    metadata_tags: list = None,
    include_suspect_urls: bool = True
):
    """
    Run detection on suspects.json against registered_text plus optional
    metadata description and tags for more accurate matching.
    
    Optionally includes suspect URLs in embeddings for higher accuracy.
    """
    metadata_tags = metadata_tags or []

    # Combine text with metadata description and tags for embedding
    combined_text = registered_text or ""
    if metadata_description:
        combined_text += f" {metadata_description}"
    if metadata_tags:
        combined_text += " " + " ".join(metadata_tags)

    with open(SUSPECTS_PATH) as f:
        suspects = json.load(f)

    print(f"📄 Loaded {len(suspects)} suspect entries.")

    # Prepare texts to embed: include suspect text + their tags + optionally URL
    texts_to_embed = [combined_text]
    for s in suspects:
        suspect_text = s.get("text", "")
        suspect_tags = " ".join(s.get("tags", []))
        suspect_url = s.get("url", "") if include_suspect_urls else ""
        combined_suspect = f"{suspect_text} {suspect_tags} {suspect_url}".strip()
        texts_to_embed.append(combined_suspect)

    print("🧠 Generating embeddings in one batch call...")
    embeddings = model.get_embeddings(texts_to_embed)

    registered_emb = embeddings[0].values
    suspect_embs = embeddings[1:]

    results = []
    for s, emb in zip(suspects, suspect_embs):
        similarity = cosine_similarity(
            np.array(registered_emb).reshape(1, -1),
            np.array(emb.values).reshape(1, -1)
        )[0][0]

        result = {
            "url": s["url"],
            "text": s["text"],
            "similarity": round(float(similarity), 3),
            "infringement": similarity > 0.85
        }

        results.append(result)

        if similarity > 0.85:
            print(f"⚠️ Potential infringement detected for {s['url']}")
        else:
            print(f"✅ No infringement for {s['url']}")

    print("🏁 Detection completed.")
    return {"registered_text": combined_text, "results": results}
