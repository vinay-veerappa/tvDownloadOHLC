import asyncio
import httpx
import os
import sys
from datetime import datetime, timezone

# Ensure repository root is in sys.path
repo_root = os.path.abspath(".")
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from scripts.streaming.options.config import HUB_URL

async def hub_request(method, params):
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
    print("Fetching NQ recent price history via Hub REST...")
    params = {
        "symbol": "/NQ",
        "period_type": "day",
        "period": 1,
        "frequency_type": "minute",
        "frequency": 1,
        "need_extended_hours_data": True
    }
    resp = await hub_request("get_price_history", params)
    if resp.get("status") == "success":
        data = resp.get("data", {})
        candles = data.get('candles', [])
        print(f"Total candles fetched: {len(candles)}")
        print("\nLast 15 candles from REST history API:")
        for c in candles[-15:]:
            dt_ms = c.get("datetime", 0)
            dt_utc = datetime.fromtimestamp(dt_ms / 1000, tz=timezone.utc)
            print(f"Time (raw): {dt_ms}, UTC: {dt_utc}, O: {c.get('open')}, H: {c.get('high')}, L: {c.get('low')}, C: {c.get('close')}, V: {c.get('volume')}")
    else:
        print(f"REST fetch failed: {resp.get('message')}")

if __name__ == "__main__":
    asyncio.run(main())
