import os
import json
import hashlib
import asyncio
import httpx
import tempfile
from web3 import Web3
from pathlib import Path
import tempfile
from pinatapy import PinataPy
import json
import httpx

NODE_DAG_API = "http://10.21.14.222:5001" 

# -------------------------
# Environment Config
# -------------------------
print("\n[INIT] Loading Constellation + Pinata integration config...")

PINATA_API_KEY = os.getenv("PINATA_API_KEY")
PINATA_SECRET_API_KEY = os.getenv("PINATA_SECRET_API_KEY")
PINATA_JWT = os.getenv("PINATA_JWT")

CONSTELLATION_API = os.getenv(
    "CONSTELLATION_API",
    "https://l0-lb-testnet.constellationnetwork.io"
)
CONSTELLATION_NETWORK = os.getenv("CONSTELLATION_NETWORK", "testnet")
CONSTELLATION_APP_NAME = os.getenv("CONSTELLATION_APP_NAME", "HakiChain")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY")

print(f"[CONFIG] CONSTELLATION_API={CONSTELLATION_API}")
print(f"[CONFIG] CONSTELLATION_NETWORK={CONSTELLATION_NETWORK}")
print(f"[CONFIG] CONSTELLATION_APP_NAME={CONSTELLATION_APP_NAME}")
print(f"[CONFIG] Pinata API Key present={bool(PINATA_API_KEY)}\n")

web3 = Web3()

# Initialize Pinata client
pinata = PinataPy(PINATA_API_KEY, PINATA_SECRET_API_KEY)

# -------------------------
# Utility
# -------------------------
def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of document content"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

# -------------------------
# IPFS (Pinata)
# -------------------------
async def push_to_ipfs(content: str) -> str:
    """
    Upload content to IPFS via Pinata (Windows-safe).
    Returns IPFS CID.
    """
    print("\n[IPFS] Preparing content upload...")

    tmp_file_path = None
    try:
        # Create a temp file in a safe location
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as tmp_file:
            tmp_file.write(content)
            tmp_file_path = Path(tmp_file.name).as_posix()

        print(f"[IPFS] Uploading {tmp_file_path} to Pinata...")
        result = pinata.pin_file_to_ipfs(tmp_file_path)
        print(f"[IPFS] Upload complete. Response: {result}")
        cid = result.get("IpfsHash")
        print(f"[IPFS] CID = {cid}\n")
        return cid
    except Exception as e:
        print(f"[IPFS Error] Upload failed: {e}")
        raise
    finally:
        if tmp_file_path:
            Path(tmp_file_path).unlink(missing_ok=True)



# -------------------------
# Constellation DAG
# -------------------------
async def push_to_dag(
    document_id: str,
    title: str,
    content_hash: str,
    metadata: dict,
    ipfs_cid: str = None,
    user_wallet: str = None,
    amount: float = 1
) -> str:
    """
    Push AI-generated content to Node DAG API as a transaction.
    Returns DAG transaction hash.
    """
    # Compose memo with AI content
    memo_content = {
        "document_id": document_id,
        "title": title,
        "hash": content_hash,
        "metadata": metadata,
        "ipfs_cid": ipfs_cid
    }

    tx_payload = {
        "to": "DAG0TwB7Yscws2cAbtKqfFnw4L4QFdr3pnpe3Vr4", 
        "amount": amount,
        "memo": json.dumps(memo_content, indent=2)
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{NODE_DAG_API}/send-dag", json=tx_payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("success"):
                raise Exception(data.get("error", "Unknown error from Node DAG API"))

            # Node returns the full DAG transaction object
            return data["tx"].get("transaction_hash") or data["tx"].get("hash")
        except Exception as e:
            print(f"[FastAPI -> Node DAG API Error]: {e}")
            raise

# -------------------------
# Combined Wrapper
# -------------------------
async def push_document(
    document_id: str,
    content_hash: str,
    metadata: dict,
    title: str = None,
    user_wallet: str = None,
):
    """
    Unified entrypoint used by router.py and docs.py.
    Uploads metadata to IPFS via Pinata, then anchors hash + CID on Constellation DAG.
    Returns a dict with both dag_tx and ipfs_cid.
    """
    print(f"\n[PIPELINE] Starting document push for ID={document_id}")
    ipfs_content = json.dumps(
        {
            "document_id": document_id,
            "metadata": metadata,
            "content_hash": content_hash,
        },
        indent=2,
    )

    ipfs_cid = None
    dag_tx = None

    try:
        print(f"[PIPELINE] → Step 1: Upload to IPFS")
        ipfs_cid = await push_to_ipfs(ipfs_content)
        print(f"[PIPELINE] IPFS CID received: {ipfs_cid}")
    except Exception as e:
        print(f"[PIPELINE] IPFS Error: {e}")

    try:
        print(f"[PIPELINE] → Step 2: Anchor to DAG")
        dag_tx = await push_to_dag(
            document_id=document_id,
            title=title or "Untitled",
            content_hash=content_hash,
            metadata=metadata,
            ipfs_cid=ipfs_cid,
            user_wallet=user_wallet,
        )
        print(f"[PIPELINE] DAG TX received: {dag_tx}")
    except Exception as e:
        print(f"[PIPELINE] DAG Error: {e}")

    result = {"dag_tx": dag_tx, "ipfs_cid": ipfs_cid}
    print(f"[PIPELINE] ✅ Completed for {document_id}: {result}\n")
    return result


def log_dag_proof(url, similarity):
    """
    Simulate storing detection proof on Constellation DAG.
    In production, this would call your DAG node API.
    """
    print(f"🧾 Logged to DAG: {url} with similarity {similarity:.2f}")
