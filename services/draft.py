import asyncio
from .utils import run_vertex_async

async def process(payload: dict):
    """
    Generate a professional legal draft asynchronously using Vertex AI.
    Incorporates category, document_type, client_name, requirements, and metadata.
    """

    # Extract payload fields safely
    user_id = payload.get("user_id")
    title = payload.get("title")
    description = payload.get("description", "")
    category = payload.get("category", "General Documents")
    document_type = payload.get("document_type", title)
    jurisdiction = payload.get("jurisdiction", "Unknown")
    requirements = payload.get("requirements", {})
    client_name = payload.get("client_name", "Client")
    metadata = payload.get("metadata", {})
    wallet = payload.get("wallet")
    case_id = payload.get("case_id")

    # System instructions for AI
    system_msg = (
        "You are an expert legal document generator. "
        "Use the provided case details to produce a structured legal document. "
        "Ensure it is suitable for professional legal review and complies with jurisdiction rules."
    )

    # Compose user instructions with all relevant fields
    user_msg = (
        f"Client Name: {client_name}\n"
        f"User ID: {user_id}\n"
        f"Title: {title}\n"
        f"Category: {category}\n"
        f"Document Type: {document_type}\n"
        f"Description: {description}\n"
        f"Jurisdiction: {jurisdiction}\n"
        f"Requirements: {requirements}\n"
        f"Case ID: {case_id}\n"
        f"Additional Metadata: {metadata}\n"
        f"Wallet: {wallet or 'N/A'}"
    )

    # Run Vertex AI to generate text
    generated_text = await run_vertex_async(user_msg, system_prompt=system_msg)
    print(f"[Agent Draft Output]\n{generated_text}\n")

    result = {
        "draft_generated": bool(generated_text),
        "draft_text": generated_text,
        "category": category,
        "document_type": document_type,
        "jurisdiction": jurisdiction,
        "requirements": requirements,
        "client_name": client_name,
        "case_id": case_id,
        "wallet": wallet,
        "metadata": metadata,
    }

    # Small delay to mimic previous behavior
    await asyncio.sleep(0.5)

    return result, generated_text
