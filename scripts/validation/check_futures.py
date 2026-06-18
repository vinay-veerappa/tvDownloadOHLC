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

async def check_futures():
    symbols = ["/ES", "/NQ", "ES", "NQ", "/ESH25", "/NQH25"] # Guesses
    
    print("Checking Futures Symbols via Hub...")
    for sym in symbols:
        try:
            print(f"--- {sym} ---")
            # Try getting quote
            resp_raw = await hub_request("get_quotes", {"symbols": [sym]})
            if resp_raw.get("status") != "success":
                print(f"  [X] Quote Fetch Error: {resp_raw.get('message')}")
                continue
                
            resp = resp_raw.get("data", {})
            if sym in resp or (len(resp) > 0 and isinstance(list(resp.values())[0], dict) and 'quote' in list(resp.values())[0]):
                print(f"  [OK] Quote Found: {resp}")
                
                # Try getting chain
                chain_raw = await hub_request("get_option_chain", {
                    "symbol": sym,
                    "strike_count": 2,
                    "strategy": "ANALYTICAL"
                })
                
                if chain_raw.get("status") != "success":
                    print(f"  [X] Option Chain Error: {chain_raw.get('message')}")
                    continue
                    
                chain = chain_raw.get("data", {})
                
                if chain.get('status') == 'FAILED':
                   print(f"  [X] Option Chain Failed.")
                else:
                   print(f"  [OK] Option Chain Found ({len(chain.get('callExpDateMap',{}))} expirations)")
            else:
                print(f"  [X] Quote Not Found.")
                
        except Exception as e:
            print(f"Error ({sym}): {e}")

if __name__ == "__main__":
    asyncio.run(check_futures())
