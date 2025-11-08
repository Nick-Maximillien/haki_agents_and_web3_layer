import asyncio
import httpx
import pdfplumber
from .utils import run_vertex_async

async def fetch_pdf_text(url: str) -> str:
    """Download PDF from URL and extract text."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        # Save to temp file
        temp_path = f"/tmp/temp_doc.pdf"
        with open(temp_path, "wb") as f:
            f.write(resp.content)
    # Extract text
    text = ""
    with pdfplumber.open(temp_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text.strip()

async def process(payload: dict):
    """
    Perform deep legal research via Vertex AI on actual document content.
    """
    document_id = payload.get("document_id", "N/A")
    print(f"[Agent Lens] Starting processing for document_id={document_id}")

    # Download and extract text if file_url is provided
    file_url = payload.get("file_url")
    document_text = ""
    if file_url:
        try:
            document_text = await fetch_pdf_text(file_url)
            print(f"[Agent Lens] Extracted {len(document_text)} characters from document")
        except Exception as e:
            print(f"[Agent Lens] Failed to fetch/extract PDF: {e}")

    system_msg = (
        "You are an expert legal researcher. "
        "Summarize key points, relevant cases, statutes, and any references relevant to the document."
    )

    user_msg = (
        f"Document title: {payload.get('title', '')}\n"
        f"Description: {payload.get('description', '')}\n"
        f"Document content:\n{document_text}\n"
        f"Requirements: {payload.get('requirements', {})}\n"
        f"Metadata: {payload.get('metadata', {})}"
    )

    generated_text = await run_vertex_async(user_msg, system_prompt=system_msg)
    print(f"[Agent Lens Output] {generated_text[:500]}{'...' if len(generated_text) > 500 else ''}")

    result = {
        "research_generated": bool(generated_text),
        "research_summary": generated_text,
        "references_found": []  # optional: parse structured references from AI output
    }

    await asyncio.sleep(0.5)
    return result, generated_text
