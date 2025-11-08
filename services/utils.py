import os
import asyncio
from pathlib import Path
from vertexai import init as vertex_init
from vertexai.generative_models import GenerativeModel, HarmCategory, HarmBlockThreshold


"""
# ----------------------------
#  Setup Local dev GCP Credentials
# ----------------------------
SA_PATH = Path(r"C:/Users/hp/Desktop/agents/central-accord-475812-g4-6d21ba7b0230.json")

if not SA_PATH.exists():
    raise RuntimeError(f" Service account JSON not found at {SA_PATH}")

# Set environment for Vertex AI
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(SA_PATH)
print(f" Using service account: {SA_PATH}")

"""
# ----------------------------
#  Setup GCP Credentials (Render-friendly)
# ----------------------------
# Prefer secret mounted on Render
SA_PATH = Path("/etc/secrets/gcp_sa.json")
if SA_PATH.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(SA_PATH)
else:
    # fallback to local dev
    SA_PATH = Path(r"C:/Users/hp/Desktop/agents/central-accord-475812-g4-6d21ba7b0230.json")
    if not SA_PATH.exists():
        raise RuntimeError(f"Service account JSON not found at {SA_PATH}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(SA_PATH)

# Normalize Windows paths (already done above, redundant but safe)
GOOGLE_APPLICATION_CREDENTIALS = os.environ["GOOGLE_APPLICATION_CREDENTIALS"].replace("\\", "/")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

# ----------------------------
#  Vertex AI Initialization
# ----------------------------
GCP_PROJECT_ID = "central-accord-475812-g4"
GCP_LOCATION = "us-central1"

try:
    vertex_init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
    print(f" Vertex AI initialized for project {GCP_PROJECT_ID} at {GCP_LOCATION}")
except Exception as e:
    raise RuntimeError(f" Vertex AI init failed: {e}")

# ----------------------------
#  Load Gemini Model
# ----------------------------
try:
    model = GenerativeModel("gemini-2.5-flash")
    print("✅ Gemini 2.5 Flash model loaded")
except Exception as e:
    raise RuntimeError(f" Failed to load Gemini 2.5 Flash: {e}")

# ----------------------------
#  Safety Settings
# ----------------------------
safety_settings = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}

# ----------------------------
#  Generation Config
# ----------------------------
generation_config = {
    "temperature": 0.7,
    "top_p": 0.9,
    "max_output_tokens": 8192,
}

# ----------------------------
#  Prompt Utilities
# ----------------------------
def sanitize_prompt(prompt: str) -> str:
    """Sanitize long prompts to reduce model blocking and improve JSON parsing."""
    if len(prompt) > 7000:
        prompt = prompt[:7000] + "\n\n[...truncated large data...]"
    prompt = prompt.replace("{", "\n{").replace("}", "}\n")
    return prompt

# ----------------------------
#  Async Vertex AI Query
# ----------------------------
async def run_vertex_async(prompt: str, system_prompt: str = None) -> str:
    """
    Generate text asynchronously with Gemini 2.5 Flash.
    Combines system instructions with user prompt, retries with fallback if blocked or empty.
    """
    full_prompt = ""
    if system_prompt:
        full_prompt += f"System instruction: {system_prompt}\n\n"
    full_prompt += sanitize_prompt(prompt)

    print("[Vertex AI] Sending prompt to Gemini 2.5 Flash...")

    def generate_sync(p):
        return model.generate_content(
            [p],
            generation_config=generation_config,
            safety_settings=safety_settings
        )

    try:
        response = await asyncio.to_thread(generate_sync, full_prompt)
        text = getattr(response, "text", "").strip()

        if not text:
            print("[Vertex AI Warning] Response empty, retrying with short summary...")
            short_prompt = "Summarize the input briefly in plain English.\n\n" + full_prompt[:4000]
            response = await asyncio.to_thread(generate_sync, short_prompt)
            text = getattr(response, "text", "(empty Gemini response)").strip()

        print("[Vertex AI] Response received.")
        return text

    except Exception as e:
        print(f"[Vertex AI Error] Failed to generate content: {e}")
        raise

# ----------------------------
#  Model Getter
# ----------------------------
def get_vertex_model():
    """Return the initialized Gemini model instance."""
    return model
