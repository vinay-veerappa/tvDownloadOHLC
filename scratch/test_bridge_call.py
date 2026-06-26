import asyncio
import httpx
import os
import sys
import time
from datetime import datetime, timezone, timedelta

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
    print("Testing Schwab price history with start/end datetime parameters...")
    # Create a 15-minute gap range from 30 mins ago to 15 mins ago
    now = datetime.now(timezone.utc)
    end_dt = now - timedelta(minutes=15)
    start_dt = now - timedelta(minutes=30)
    
    gap_start_ms = int(start_dt.timestamp() * 1000)
    gap_end_ms = int(end_dt.timestamp() * 1000)
    
    print(f"Requesting range (UTC): {start_dt} -> {end_dt}")
    print(f"Requesting range (ms): {gap_start_ms} -> {gap_end_ms}")
    
    params = {
        "symbol": "/NQ",
        "frequency_type": "minute",
        "frequency": 1,
        "start_datetime": gap_start_ms,
        "end_datetime": gap_end_ms,
        "need_extended_hours_data": True
    }
    
    resp = await hub_request("get_price_history", params)
    print(f"Status: {resp.get('status')}")
    if resp.get("status") == "success":
        data = resp.get("data", {})
        candles = data.get('candles', [])
        print(f"Total candles returned: {len(candles)}")
        if candles:
            print("\nFirst 3 candles:")
            for c in candles[:3]:
                dt_utc = datetime.fromtimestamp(c.get("datetime")/1000, tz=timezone.utc)
                print(f"  Time: {c.get('datetime')}, UTC: {dt_utc}, O: {c.get('open')}, C: {c.get('close')}")
            print("\nLast 3 candles:")
            for c in candles[-3:]:
                dt_utc = datetime.fromtimestamp(c.get("datetime")/1000, tz=timezone.utc)
                print(f"  Time: {c.get('datetime')}, UTC: {dt_utc}, O: {c.get('open')}, C: {c.get('close')}")
    else:
        print(f"Error: {resp.get('message')}")

if __name__ == "__main__":
    asyncio.run(main())
