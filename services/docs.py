# services/docs.py
import asyncio
import hashlib
from .utils import run_vertex_async
from .integrations import dag  


async def process(payload: dict):
    """
    Document repository storage with optional AI metadata extraction.
    After processing, automatically push document hash to DAG/IPFS.
    """
    document_id = payload.get("document_id", "N/A")
    print("=" * 80)
    print(f"[Agent Docs] Starting processing for document_id={document_id}")
    print(f"[DEBUG] Incoming payload keys: {list(payload.keys())}")
    print(f"[DEBUG] Payload title={payload.get('title')}, file_url={payload.get('file_url')}")

    system_msg = (
        "You are an AI document assistant. Generate structured metadata tags and "
        "a concise summary for the document suitable for repository indexing."
    )

    user_msg = (
        f"Document title: {payload.get('title', '')}\n"
        f"Description: {payload.get('description', '')}\n"
        f"File URL: {payload.get('file_url', '')}\n"
        f"Requirements: {payload.get('requirements', {})}\n"
        f"Metadata: {payload.get('metadata', {})}"
    )

    print("[DEBUG] Calling run_vertex_async() for metadata generation...")
    generated_text = await run_vertex_async(user_msg, system_prompt=system_msg)
    print("[DEBUG] run_vertex_async() completed.")
    print(f"[Agent Docs Output Preview] {generated_text[:300]}{'...' if len(generated_text) > 300 else ''}")

    result = {
        "repository_generated": bool(generated_text),
        "file_url": payload.get("file_url"),
        "metadata_tags": generated_text,
    }

    # --------------------------
    # Compute hash and push to DAG/IPFS
    # --------------------------
    if generated_text:
        try:
            print(f"[DAG/IPFS] Preparing push for document {document_id}...")
            content_hash = hashlib.sha256(generated_text.encode('utf-8')).hexdigest()
            print(f"[DEBUG] Computed SHA256 hash: {content_hash}")
            print(f"[DEBUG] Calling dag.push_document() for document {document_id}...")

            dag_result = await dag.push_document(
                document_id=document_id,
                content_hash=content_hash,
                metadata=payload.get("metadata", {}),
                title=payload.get("title", "Untitled"),
                user_wallet=payload.get("user_wallet"),
            )

            print(f"[DEBUG] dag.push_document() returned: {dag_result}")
            dag_tx = dag_result.get("dag_tx")
            ipfs_cid = dag_result.get("ipfs_cid")

            print(f"[DAG/IPFS] ✅ Document {document_id} anchored successfully.")
            print(f"[DAG/IPFS] TX={dag_tx}, IPFS CID={ipfs_cid}, HASH={content_hash}")

        except Exception as e:
            print(f"[DAG/IPFS Error] Document {document_id}: {e}")

    else:
        print(f"[WARN] No generated_text for document {document_id}, skipping DAG/IPFS push.")

    print(f"[DEBUG] process() completed for document_id={document_id}")
    print("=" * 80)
    await asyncio.sleep(0.5)
    return result, generated_text
