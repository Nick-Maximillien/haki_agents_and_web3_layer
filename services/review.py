import asyncio
from .utils import run_vertex_async

async def process(payload: dict):
    """
    AI-powered review of uploaded legal document.
    Identify errors, inconsistencies, and suggest improvements.
    """
    document_id = payload.get("document_id", "N/A")
    print(f"[Agent Review] Starting processing for document_id={document_id}")

    system_msg = (
        "You are a legal AI assistant. Analyze the uploaded document for errors, "
        "inconsistencies, missing clauses, and suggest improvements."
    )

    user_msg = (
        f"Document title: {payload.get('title', '')}\n"
        f"Description: {payload.get('description', '')}\n"
        f"File URL: {payload.get('file_url', '')}\n"
        f"Requirements: {payload.get('requirements', {})}\n"
        f"Extracted Text: {payload.get('extracted_text', '')}\n" 
        f"Metadata: {payload.get('metadata', {})}"
    )


    generated_text = await run_vertex_async(user_msg, system_prompt=system_msg)
    print(f"[Agent Review Output] {generated_text[:500]}{'...' if len(generated_text) > 500 else ''}")

    result = {
        "review_generated": bool(generated_text),
        "review_summary": generated_text,
        "issues_found": []  # optional: parse structured issues from AI output
    }

    await asyncio.sleep(0.5)
    return result, generated_text
