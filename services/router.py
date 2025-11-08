# services/router.py
import os
import asyncio
import httpx
import hashlib
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from fastapi.responses import JSONResponse
from fastapi import Body, HTTPException # Need to make sure these are imported at the top


from services import lens, draft, review, docs
from services.integrations import story, icp, dag  

router = APIRouter()

DJANGO_CALLBACK_URL = os.getenv(
    "DJANGO_CALLBACK_URL",
    "http://localhost:8000/documents/agent/callback/"
)

# ---------------------------------------------------------
# AGENT EXECUTION PIPELINE (Lens, Draft, Review)
# ---------------------------------------------------------
async def run_and_report(module, payload: dict):
    document_id = payload.get("document_id")
    print(f"[Agent Task] Starting processing for document_id={document_id} using {module.__name__}")

    # 1 Run AI module
    try:
        result, generated_text = await module.process(payload)
        status_value = "completed"
        print(f"[Agent Task] AI module completed for document_id={document_id}")
    except Exception as e:
        result = {"error": str(e)}
        generated_text = ""
        status_value = "failed"
        print(f"[Agent Task] AI module failed for document_id={document_id}: {e}")

    # 2 Register with Story / ICP / DAG (only when generated_text exists)
    story_id = icp_id = dag_id = ipfs_cid = None
    if generated_text:
        try:
            content_hash = hashlib.sha256(generated_text.encode("utf-8")).hexdigest()

            # Story
            story_id = await asyncio.to_thread(
                story.register_document,
                payload.get("title"),
                generated_text,
                payload.get("metadata", {})
            )

            # ICP
            icp_id = await icp.register_metadata_hash(document_id, payload.get("metadata", {}))

            # DAG / Constellation (optional)
            try:
                dag_result = await dag.push_document(
                    document_id=document_id,
                    content_hash=content_hash,
                    metadata=payload.get("metadata", {}),
                    title=payload.get("title", "Untitled"),
                )
                dag_id = dag_result.get("dag_tx")
                ipfs_cid = dag_result.get("ipfs_cid")
                print(f"[DAG] document_id={document_id} DAG_TX={dag_id}, IPFS_CID={ipfs_cid}")
            except Exception as dag_err:
                print(f"[DAG Error] document_id={document_id}: {dag_err}")

            print(f"[Integration] Story={story_id}, ICP={icp_id}, DAG={dag_id}")
        except Exception as e:
            print(f"[Integration Error] Document {document_id}: {e}")

    # 3 Callback to Django
    callback_payload = {
        "document_id": document_id,
        "status": status_value,
        "result": result,
        "generated_text": generated_text,
        "story_id": story_id,
        "icp_id": icp_id,
        "dag_id": dag_id,
        "ipfs_cid": ipfs_cid,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(DJANGO_CALLBACK_URL, json=callback_payload, timeout=10)
            resp.raise_for_status()
            print(f"[Agent Callback] Updated document {document_id} in Django with proofs")
        except Exception as e:
            print(f"[Agent Callback Error] Document {document_id}: {e}")


# ---------------------------------------------------------
# BACKGROUND ENDPOINTS (use BackgroundTasks safely)
# ---------------------------------------------------------
@router.post("/lens/")
async def run_lens(payload: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_and_report, lens, payload)
    return {"message": "HakiLens research started."}


@router.post("/draft/")
async def run_draft(payload: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_and_report, draft, payload)
    return {"message": "HakiDraft generation started."}


@router.post("/review/")
async def run_review(payload: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_and_report, review, payload)
    return {"message": "HakiReview analysis started."}


# ---------------------------------------------------------
# DOCS: ONLY PUSH HASHES + METADATA (no AI inference)
# ---------------------------------------------------------
@router.post("/docs/")
async def run_docs(payload: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(push_document_to_integrations, payload)
    return {"message": "HakiDocs push started (metadata + hashes only)."}


# ---------------------------------------------------------
# AGENT NOTIFY HANDLER (safe + resilient)
# ---------------------------------------------------------
@router.post("/notify/")
async def agent_notify(payload: dict, background_tasks: BackgroundTasks):
    """
    Handles callbacks from Django or external events.
    Only Lens, Draft, and Review trigger AI + integrations.
    Docs just push metadata/hashes directly.
    """
    doc_type = (payload.get("doc_type") or "").lower()
    document_id = payload.get("document_id")

    print(f"[Router] Received notify for doc_type={doc_type}, document_id={document_id}")

    if doc_type in ("lens", "hakilens"):
        background_tasks.add_task(run_and_report, lens, payload)
    elif doc_type in ("draft", "hakidraft"):
        background_tasks.add_task(run_and_report, draft, payload)
    elif doc_type in ("review", "hakireview"):
        background_tasks.add_task(run_and_report, review, payload)
    elif doc_type in ("docs", "hakidocs", "repository", "ip", "intellectual property"):
        background_tasks.add_task(push_document_to_integrations, payload)

    else:
        print(f"[Router] Ignored notify: Unknown doc_type={doc_type}")
        return {"status": "ignored", "reason": "Unknown doc_type"}

    return {"status": "accepted", "doc_type": doc_type, "document_id": document_id}


# ---------------------------------------------------------
# STORY + ICP + DAG REGISTER ENDPOINT (unchanged)
# ---------------------------------------------------------
async def push_document_to_integrations(payload: dict):
    document_id = payload.get("document_id")
    title = payload.get("title")
    content = payload.get("content", "")
    metadata = payload.get("metadata", {})
    content_hash = payload.get("hash") or hashlib.sha256(content.encode("utf-8")).hexdigest()

    story_id = icp_id = dag_id = ipfs_cid = None

    try:
        story_id = await asyncio.to_thread(story.register_document, title, content, metadata)
    except Exception as e:
        print(f"[Story Push Error] Document {document_id}: {e}")

    try:
        icp_id = await icp.register_metadata_hash(document_id, metadata)
    except Exception as e:
        print(f"[ICP Push Error] Document {document_id}: {e}")

    try:
        dag_result = await dag.push_document(
            document_id=document_id,
            content_hash=content_hash,
            metadata=payload.get("metadata", {}),
            title=payload.get("title", "Untitled"),
        )
        dag_id = dag_result.get("dag_tx")
        ipfs_cid = dag_result.get("ipfs_cid")
        print(f"[DAG Push] document_id={document_id} DAG_TX={dag_id}, IPFS_CID={ipfs_cid}")
    except Exception as e:
        print(f"[DAG Push Error] Document {document_id}: {e}")

    callback_payload = {
        "document_id": document_id,
        "story_id": story_id,
        "icp_id": icp_id,
        "dag_id": dag_id,
        "hash": content_hash,
        "ipfs_cid": ipfs_cid,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(DJANGO_CALLBACK_URL, json=callback_payload, timeout=10)
            resp.raise_for_status()
            print(f"[Callback] Document {document_id} updated in Django.")
    except Exception as e:
        print(f"[Callback Error] Document {document_id}: {e}")


@router.post("/story/register")
async def register_story_endpoint(payload: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(push_document_to_integrations, payload)
    return {"status": "accepted", "message": "Document push started in background"}


# services/router.py (ADD THIS SECTION)
# ... [existing code up to the last function] ...
# Pydantic Model definition (must be defined or imported here)
class EvidencePayload(BaseModel):
    document_id: int
    title: str
    url: str
    similarity: float
    excerpt: Optional[str] = None
    owner: str

# ---------------------------------------------------------
# CASE CREATION & FETCH ENDPOINTS (Moved from main.py)
# Note: They are defined WITHOUT the /agent prefix here.
# ---------------------------------------------------------

@router.post("/evidence") # Will become /agent/evidence
async def mark_as_evidence(payload: EvidencePayload = Body(...)):
    """
    When the user marks a detected match as evidence, 
    create a 'case' record on ICP using document_id.
    """
    try:
        # NOTE: You need to ensure the logic here is correct, 
        # specifically the call to icp.register_metadata_hash
        
        metadata = {
            "title": payload.title,
            "url": payload.url,
            "similarity": payload.similarity,
            "excerpt": payload.excerpt or "",
            "owner": payload.owner
        }

        # Assuming this function call is correctly imported from your icp.py
        record_id = await icp.register_metadata_hash(
            document_id=payload.document_id,
            metadata=metadata
        )

        if record_id:
            return {"status": "ok", "record_id": record_id, "message": "Case stored successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create case on ICP")

    except Exception as e:
        # print("❌ Error creating case:", e) # (Remove this print as traceback is usually enough)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases") # Will become /agent/cases
async def list_cases():
    """
    Fetch all recorded cases from ICP.
    Returns an array of case metadata for Cases.tsx.
    """
    try:
        records = await icp.list_records()
        formatted_cases = []
        
        # ... (rest of your list_cases logic from main.py goes here) ...

        for rec in records:
            if not isinstance(rec, dict):
                continue
            val = rec.get("value", {}) if "value" in rec else rec
            formatted_cases.append({
                "record_id": val.get("record_id"),
                "document_id": val.get("document_id"),
                "metadata": val.get("metadata"),
                "owner": val.get("owner"),
                "timestamp": val.get("timestamp"),
                "metadata_hash": val.get("metadata_hash"),
            })

        return {"status": "ok", "cases": formatted_cases}

    except Exception as e:
        # print("❌ Failed to list cases:", e)
        raise HTTPException(status_code=500, detail=str(e))