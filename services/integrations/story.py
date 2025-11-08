# services/integrations/story.py
import os
import json
from pathlib import Path
from web3 import Web3

# -------------------------
# Config / Environment
# -------------------------
STORY_MODE = os.getenv("STORY_MODE", "false").lower() in ["1", "true", "yes"]

# Use Aeneid RPC and deployed contract address
RPC_PROVIDER_URL = os.getenv(
    "RPC_PROVIDER_URL",
    "https://aeneid.storyrpc.io"  # updated RPC
)
CHAIN_ID = int(os.getenv("AENEID_CHAIN_ID", "1315"))  # Aeneid chain ID
CONTRACT_ADDRESS = os.getenv("STORY_CONTRACT_ADDRESS", "0x2afce5b30DFD0d53a98e65d23E7D620701023f3C")  # updated contract

# Expect a private key in .env
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY")
if not WALLET_PRIVATE_KEY:
    raise EnvironmentError("Missing WALLET_PRIVATE_KEY in environment.")

# -------------------------
# ABI Loading
# -------------------------
# Resolve the path to services/StoryIPRegister.json
BASE_DIR = Path(__file__).resolve().parent.parent  # points to /services
CONTRACT_ABI_PATH = BASE_DIR / "StoryIPRegister.json"

if not CONTRACT_ABI_PATH.exists():
    raise FileNotFoundError(f"Contract ABI not found at {CONTRACT_ABI_PATH}")

with open(CONTRACT_ABI_PATH, "r") as f:
    CONTRACT_ABI = json.load(f)["abi"]  # read only the ABI field

# -------------------------
# Web3 Connection
# -------------------------
web3 = Web3(Web3.HTTPProvider(RPC_PROVIDER_URL))
if not web3.is_connected():
    raise ConnectionError(f"Web3 cannot connect to provider at {RPC_PROVIDER_URL}")

account = web3.eth.account.from_key(WALLET_PRIVATE_KEY)
contract = web3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=CONTRACT_ABI
)

# -------------------------
# Register Document
# -------------------------
def register_document(title: str, content: str, metadata: dict) -> str:
    """
    Registers a document on-chain (Aeneid network).
    Returns the on-chain asset ID.
    """
    content_hash = Web3.to_hex(Web3.keccak(text=content))
    metadata_json = json.dumps(metadata)

    nonce = web3.eth.get_transaction_count(account.address)
    tx = contract.functions.registerAsset(title, content_hash, metadata_json).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "chainId": CHAIN_ID,
        "gas": 1_000_000,
        "gasPrice": web3.eth.gas_price
    })

    signed_tx = account.sign_transaction(tx)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt.status != 1:
        raise Exception(f"Transaction failed for {title}")

    logs = contract.events.AssetRegistered().process_receipt(receipt)
    if not logs:
        raise Exception("No AssetRegistered event emitted.")

    asset_id = logs[0]['args']['assetId']
    network_name = "Aeneid Story"  # updated network name
    print(f"[{network_name}] ✅ Registered asset {asset_id} (tx={tx_hash.hex()})")
    return str(asset_id)
