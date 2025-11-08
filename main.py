import os
import uvicorn
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from services.router import router as services_router
from services.detect.detect import run_detection
from services.integrations import icp  # <-- ICP integration -->
from pydantic import BaseModel
from typing import List, Optional
from fastapi import Body
import asyncio
from services.integrations import icp

AI_AGENT_PORT = int(os.getenv("AI_AGENT_PORT", 8001))
AI_AGENT_HOST = os.getenv("AI_AGENT_HOST", "0.0.0.0")

app = FastAPI(
    title="HakiChain Vertex AI Agent",
    description="FastAPI + Google Vertex AI agent for HakiLens, HakiDraft, HakiReview, and HakiDocs",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(services_router, prefix="/agent", tags=["Agent Services"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "HakiChain Vertex AI Agent is running."}

# ----------------------------
# Pydantic Models
# ----------------------------
class Metadata(BaseModel):
    description: Optional[str] = ""
    tags: List[str] = []

class DetectionPayload(BaseModel):
    assetId: int
    title: str
    contentHash: str
    metadata: Metadata
    owner: str
    text: str = ""

class Match(BaseModel):
    url: str
    similarity: float
    excerpt: Optional[str] = None

class DetectionResponse(BaseModel):
    matches: List[Match]

# ----------------------------
# Detection Endpoint
# ----------------------------
@app.post("/detect", response_model=DetectionResponse)
async def detect_ip(payload: DetectionPayload):
    try:
        print(f"🚀 Detection triggered for asset ID {payload.assetId} by {payload.owner}")
        
        # Run detection
        results = run_detection(
            registered_text=payload.text,
            metadata_description=payload.metadata.description,
            metadata_tags=payload.metadata.tags
        )

        # Transform to frontend structure
        matches = [
            {
                "url": r["url"],
                "similarity": r["similarity"],
                "excerpt": r["text"][:200]
            }
            for r in results["results"]
        ]

        # --- NEW: Trigger ICP store_story_metadata asynchronously ---
        try:
            icp_matches = [
                {
                    "url": m["url"],
                    "similarity": m["similarity"],
                    "excerpt": m["excerpt"] or ""
                }
                for m in matches
            ]

            # Fire-and-forget
            asyncio.create_task(
                icp.register_story_metadata_hash(
                    document_id=payload.assetId,
                    metadata={
                        "description": payload.metadata.description,
                        "tags": payload.metadata.tags,
                        "text": payload.text
                    },
                    matches=icp_matches
                )
            )
        except Exception as e:
            print("❌ Warning: Failed to trigger ICP store_story_metadata:", e)

        return {"matches": matches}

    except Exception as e:
        print("❌ Detection failed:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------
# Optional manual store endpoint
# ----------------------------
class StoryDetectionPayload(BaseModel):
    document_id: int
    metadata: Metadata
    text: str
    matches: List[Match]

@app.post("/detect/store")
async def detect_and_store(payload: StoryDetectionPayload):
    try:
        print(f"🚀 Storing detection payload for document ID {payload.document_id}")

        icp_matches = [
            {
                "url": m.url,
                "similarity": m.similarity,
                "excerpt": m.excerpt or ""
            }
            for m in payload.matches
        ]

        record_id = await icp.register_story_metadata_hash(
            document_id=payload.document_id,
            metadata={
                "description": payload.metadata.description,
                "tags": payload.metadata.tags,
                "text": payload.text
            },
            matches=icp_matches
        )

        return {"status": "ok", "record_id": record_id}

    except Exception as e:
        print("❌ Failed to store story metadata:", e)
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    uvicorn.run("main:app", host=AI_AGENT_HOST, port=AI_AGENT_PORT, reload=True)
