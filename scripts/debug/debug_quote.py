import json
import os
import sys
import asyncio
import httpx

# Ensure repository root is in sys.path so scripts can find top-level packages
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from scripts.streaming.options.config import HUB_URL

async def hub_request(method, params):
    """Send a REST request through the Hub's proxy."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=30.0)
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, dict) and "status" not in result:
                    return {"status": "success", "data": result}
                return result
            else:
                return {"status": "error", "message": f"Hub Error [{resp.status_code}]: {resp.text}"}
        except Exception as e:
            return {"status": "error", "message": f"Hub Connection Error: {str(e)}"}

async def main():
    test_tickers = ['//ES', './ES', 'ES']
    
    print(f"----- DEBUGGING CHAIN ERRORS VIA HUB -----")
    for t in test_tickers:
        print(f"\n[Testing: {t}]")
        try:
             chain_raw = await hub_request("get_option_chain", {"symbol": t})
             
             if chain_raw.get("status") != "success":
                 print(f"    Request Failed: {chain_raw.get('message')}")
                 continue
                 
             chain = chain_raw.get("data", {})
             
             if 'errors' in chain:
                 print(f"    Failed with Errors: {chain['errors']}")
             elif 'underlying' in chain and chain['underlying']:
                 print(f"    Success! Underlying: {chain['underlying'].get('description')} Last: {chain['underlying'].get('last')}")
                 # Check first strike to verify asset class
                 call_map = chain.get('callExpDateMap', {})
                 if call_map:
                     first = list(call_map.keys())[0]
                     strikes = list(call_map[first].keys())[:3]
                     print(f"    Strikes: {strikes}")
             else:
                 print(f"    Unknown Response or None underlying: {list(chain.keys())}")
                 
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
