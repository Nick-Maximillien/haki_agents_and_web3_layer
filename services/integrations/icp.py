import json
import asyncio
from ic.client import Client
from ic.identity import Identity
from ic.agent import Agent
from ic.candid import encode, Types
from ic.principal import Principal
import os

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
ICP_HOST = os.getenv("ICP_HOST", "http://127.0.0.1:4943")
CANISTER_ID = os.getenv("ICP_CANISTER_ID", "uxrrr-q7777-77774-qaaaq-cai")
TIMEOUT_SECONDS = 60  # Timeout for all update/query calls

# ---------------------------------------------------------
# AGENT INITIALIZATION
# ---------------------------------------------------------
identity = Identity()  # anonymous (can be replaced with PemIdentity)
client = Client(ICP_HOST)
agent = Agent(identity, client)

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
async def _safe_encode(metadata: dict):
    """Safely encode Python metadata dict into Candid text argument."""
    try:
        if not metadata:
            return "{}"
        return json.dumps(metadata, ensure_ascii=False)
    except Exception as e:
        print(f"[ICP Encode Error] Failed to encode metadata: {e}")
        return "{}"

# ---------------------------------------------------------
# CORE FUNCTION: REGISTER METADATA HASH
# ---------------------------------------------------------
async def register_metadata_hash(document_id: int, metadata: dict):
    """
    Stores metadata on ICP registry and returns record_id or None.
    """
    print(f"[ICP Debug] >>> Registering document {document_id}")
    try:
        metadata_json = await _safe_encode(metadata)
        print(f"[ICP Debug] metadata_json: {metadata_json}")
        print(f"[ICP Debug] Preparing to encode arguments:")
        print(f"    document_id type: {type(document_id)}, value: {document_id}")
        print(f"    metadata_json type: {type(metadata_json)}, value: {metadata_json}")

        args = encode([
            {"type": Types.Nat64, "value": document_id},
            {"type": Types.Text, "value": metadata_json},
        ])
        print(f"[ICP Debug] Encoded args length: {len(args)} bytes")

        # Synchronous update call with timeout
        response = await asyncio.wait_for(
            asyncio.to_thread(agent.update_raw, CANISTER_ID, "store_metadata", args),
            timeout=TIMEOUT_SECONDS
        )

        print(f"[ICP Debug] Raw response: {response}")

        record_id = None
        if isinstance(response, list) and len(response) > 0:
            rec = response[0].get("value", {})
            for k, v in rec.items():
                if isinstance(v, int):
                    record_id = v
                    break

        print(f"[ICP Success] document_id={document_id} → record_id={record_id}")
        return record_id

    except asyncio.TimeoutError:
        print(f"[ICP Error] register_metadata_hash timed out for document_id={document_id}")
        return None
    except Exception as e:
        print(f"[ICP Error] Failed to register document {document_id}: {e}")
        import traceback
        traceback.print_exc()
        return None

# ---------------------------------------------------------
# OPTIONAL QUERY METHODS
# ---------------------------------------------------------
async def get_record(record_id: int):
    try:
        args = encode([{"type": Types.Nat64, "value": record_id}])
        response = await asyncio.wait_for(
            asyncio.to_thread(agent.query_raw, CANISTER_ID, "get_record", args),
            timeout=TIMEOUT_SECONDS
        )
        print(f"[ICP Debug] get_record response: {response}")
        return response
    except asyncio.TimeoutError:
        print(f"[ICP Query Error] get_record timed out for record_id={record_id}")
        return None
    except Exception as e:
        print(f"[ICP Query Error] record_id={record_id}: {e}")
        return None

async def list_records():
    """
    Fetch and normalize all stored records from ICP into a structured list
    usable by the frontend.
    """
    try:
        args = encode([])
        response = await asyncio.wait_for(
            asyncio.to_thread(agent.query_raw, CANISTER_ID, "list_records", args),
            timeout=TIMEOUT_SECONDS
        )

        print(f"[ICP Debug] list_records response: {response}")

        normalized = []
        if not response:
            return []

        # Iterate over raw Candid response
        for entry in response:
            value = entry.get("value") if isinstance(entry, dict) else entry
            if isinstance(value, list):  # sometimes wrapped as a list
                value = value[0] if value else {}

            if not isinstance(value, dict):
                continue

            # Try to map known ICP record fields
            record = {
                "record_id": value.get("_676177343") or value.get("record_id"),
                "owner": str(value.get("_947296307") or value.get("owner") or ""),
                "metadata": None,
                "metadata_hash": value.get("_2404848094"),
                "timestamp": value.get("_2781795542"),
                "document_id": value.get("_676177343"),
            }

            try:
                # Safely parse metadata JSON if present
                raw_meta = value.get("_1075439471") or value.get("metadata")
                if isinstance(raw_meta, str):
                    record["metadata"] = json.loads(raw_meta)
                elif isinstance(raw_meta, dict):
                    record["metadata"] = raw_meta
            except Exception as parse_err:
                print(f"[ICP Decode Warning] Could not parse metadata: {parse_err}")
                record["metadata"] = {}

            normalized.append(record)

        return normalized

    except asyncio.TimeoutError:
        print("[ICP Query Error] list_records timed out")
        return []
    except Exception as e:
        print(f"[ICP Query Error] list_records: {e}")
        return []


# ---------------------------------------------------------
# NEW FUNCTION: REGISTER STORY METADATA HASH
# ---------------------------------------------------------
async def register_story_metadata_hash(document_id: int, metadata: dict, matches: list):
    """
    Stores story metadata along with detection matches on ICP.
    """
    try:
        metadata_json = await _safe_encode(metadata)

        # Prepare matches as proper list of dicts
        candid_matches = [{"url": m["url"], "similarity": m["similarity"]} for m in matches]

        # Define the Candid Record Type for a single match entry
        MatchRecordType = Types.Record({
            "url": Types.Text,
            "similarity": Types.Float64
        })

        args = encode([
            {"type": Types.Nat64, "value": document_id},
            {"type": Types.Text, "value": metadata_json},
            {"type": Types.Vec(MatchRecordType), "value": candid_matches} 
        ])

        response = await asyncio.wait_for(
            asyncio.to_thread(agent.update_raw, CANISTER_ID, "store_story_metadata", args),
            timeout=TIMEOUT_SECONDS
        )

        record_id = None
        if isinstance(response, list) and len(response) > 0:
            rec = response[0].get("value", {})
            for k, v in rec.items():
                if isinstance(v, int):
                    record_id = v
                    break

        print(f"[ICP Success] Stored story document_id={document_id} → record_id={record_id}")
        return record_id

    except asyncio.TimeoutError:
        print(f"[ICP Error] register_story_metadata_hash timed out for document_id={document_id}")
        return None
    except Exception as e:
        print(f"[ICP Error] Failed to store story metadata for document_id={document_id}: {e}")
        import traceback
        traceback.print_exc()
        return None

# ---------------------------------------------------------
# FETCH CASE FROM ICP
# ---------------------------------------------------------
async def fetch_case(document_id: int):
    """
    Fetches a story metadata record (case) by document_id from ICP.
    Returns a dict containing document + matches, or None if not found.
    """
    try:
        args = encode([{"type": Types.Nat64, "value": document_id}])

        response = await asyncio.wait_for(
            asyncio.to_thread(agent.query_raw, CANISTER_ID, "get_story_by_document", args),
            timeout=TIMEOUT_SECONDS
        )

        if not response:
            print(f"[ICP Debug] No case found for document_id={document_id}")
            return None

        # response is usually a list of dicts with "value"
        record = response[0].get("value", {})

        # Convert matches into standard structure
        matches = []
        if "matches" in record:
            for m in record["matches"]:
                matches.append({
                    "url": m.get("url", ""),
                    "similarity": m.get("similarity", 0.0),
                    "excerpt": m.get("excerpt", "")
                })

        case_data = {
            "record_id": record.get("record_id"),
            "document_id": record.get("document_id"),
            "metadata": record.get("metadata"),
            "owner": record.get("owner"),
            "timestamp": record.get("timestamp"),
            "metadata_hash": record.get("metadata_hash"),
            "matches": matches
        }

        print(f"[ICP Debug] Fetched case for document_id={document_id}: {case_data}")
        return case_data

    except asyncio.TimeoutError:
        print(f"[ICP Error] fetch_case timed out for document_id={document_id}")
        return None
    except Exception as e:
        print(f"[ICP Error] Failed to fetch case for document_id={document_id}: {e}")
        import traceback
        traceback.print_exc()
        return None



