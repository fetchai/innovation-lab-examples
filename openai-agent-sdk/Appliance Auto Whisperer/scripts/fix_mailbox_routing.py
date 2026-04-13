"""
Fix the Agentverse mailbox routing for repair-orchestrator.

This script does what the Inspector 'Connect to Mailbox' button does:
  1. POSTs to the local agent's /connect endpoint
  2. The agent then registers itself with the correct mailbox endpoint in Agentverse

Run while the orchestrator is RUNNING in another terminal:
  python scripts/fix_mailbox_routing.py
"""

import asyncio
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

AV_KEY = os.getenv("AGENTVERSE_API_KEY", "").strip()
AV_BASE = "https://agentverse.ai"
AGENT_ADDR = "agent1qv5c0vjykr5j3qd0rl9qx423jdy7tz92ph2dr4l0stalgm20er2usfew9cc"
LOCAL_URL = "http://127.0.0.1:8001"

HEADERS = {
    "Authorization": f"Bearer {AV_KEY}",
    "Content-Type": "application/json",
}


async def check_agent_registration():
    """Check what endpoint the agent currently has registered in Agentverse."""
    async with httpx.AsyncClient(timeout=15) as client:
        url = f"{AV_BASE}/v2/agents/{AGENT_ADDR}"
        r = await client.get(url, headers=HEADERS)
        print("\n[1] Agent registration (v2 API)")
        print(f"    Status : {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"    Name   : {data.get('name', 'N/A')}")
            print(f"    Status : {data.get('status', 'N/A')}")
            print(
                f"    Endpoint : {data.get('endpoint', data.get('endpoints', 'N/A'))}"
            )
            print(f"    Full response: {data}")
        else:
            print(f"    Response: {r.text[:500]}")


async def connect_mailbox():
    """
    Call the local agent's /connect endpoint.
    This triggers register_in_agentverse() inside the agent,
    which sets the agent's endpoint to the Agentverse mailbox URL.
    This is EXACTLY what the Inspector 'Connect to Mailbox' button does.
    """
    print(f"\n[2] Connecting mailbox via POST {LOCAL_URL}/connect")
    payload = {
        "user_token": AV_KEY,
        "agent_type": "mailbox",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{LOCAL_URL}/connect",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            print(f"    Status : {r.status_code}")
            print(f"    Response: {r.text[:500]}")
            if r.status_code == 200:
                print("    SUCCESS - mailbox connected!")
                return True
            else:
                print("    FAILED - see response above")
                return False
    except httpx.ConnectError:
        print("    ERROR: Could not connect to agent at 127.0.0.1:8001")
        print("    Make sure the orchestrator is running in another terminal!")
        return False
    except Exception as e:
        print(f"    ERROR: {e}")
        return False


async def verify_after_connect():
    """Check the registration again after connecting."""
    await asyncio.sleep(2)
    async with httpx.AsyncClient(timeout=15) as client:
        url = f"{AV_BASE}/v2/agents/{AGENT_ADDR}"
        r = await client.get(url, headers=HEADERS)
        print("\n[3] Agent registration AFTER connect")
        print(f"    Status : {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            endpoint = data.get("endpoint", data.get("endpoints", "N/A"))
            print(f"    Endpoint : {endpoint}")
            if "mailbox" in str(endpoint).lower():
                print("    Mailbox routing is CORRECT")
            else:
                print("    WARNING: Endpoint may not be the mailbox URL")
        else:
            print(f"    Response: {r.text[:300]}")


async def main():
    if not AV_KEY:
        print("ERROR: AGENTVERSE_API_KEY not set in .env")
        sys.exit(1)

    print("=" * 60)
    print("Agentverse Mailbox Fix")
    print(f"Agent   : {AGENT_ADDR}")
    print(f"Local   : {LOCAL_URL}")
    print("=" * 60)

    await check_agent_registration()
    ok = await connect_mailbox()
    if ok:
        await verify_after_connect()
        print("\n" + "=" * 60)
        print("DONE. Now send a test message from ASI:One.")
        print("You should see '[orch] context=...' in the orchestrator terminal.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("MANUAL FIX: Open this URL in Chrome and click 'Connect to Mailbox':")
        inspector = (
            f"https://agentverse.ai/inspect/"
            f"?uri=http%3A//127.0.0.1%3A8001"
            f"&address={AGENT_ADDR}"
        )
        print(f"  {inspector}")
        print("\nNote: Chrome may show a security prompt — click 'Allow' to permit")
        print("localhost access, then click 'Connect to Mailbox'.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
