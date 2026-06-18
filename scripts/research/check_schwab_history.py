import json
import os
import sys
import asyncio
import httpx
from datetime import datetime, timedelta

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

async def check_schwab_history():
    print("=== Checking Schwab Price History Depth via Hub ===")
    
    # Test Ticker
    symbol = "SPY"
    
    print(f"Fetching 15m data for {symbol} (Target: 10 days)...")
    try:
        resp_raw = await hub_request("get_price_history", {
            "symbol": symbol,
            "period_type": 'day',
            "period": 10, 
            "frequency_type": 'minute',
            "frequency": 15,
            "need_extended_hours_data": True
        })
        
        if resp_raw.get("status") == "success" and "candles" in resp_raw.get("data", {}):
            resp = resp_raw["data"]
            candles = resp['candles']
            print(f"Success! Fetched {len(candles)} candles.")
            if candles:
                print(f"Start: {datetime.fromtimestamp(candles[0]['datetime']/1000)}")
                print(f"End:   {datetime.fromtimestamp(candles[-1]['datetime']/1000)}")
        else:
            print("10 Day Fetch Failed:", resp_raw.get("message") or resp_raw)

        print("\nAttempting 6 months via Timestamps...")
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=180) # 6 months
        
        # Convert to milliseconds
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        
        resp_deep_raw = await hub_request("get_price_history", {
            "symbol": symbol,
            "period_type": 'day',
            "frequency_type": 'minute',
            "frequency": 15,
            "start_date": start_ms, 
            "end_date": end_ms,
            "need_extended_hours_data": True
        })
        
        if resp_deep_raw.get("status") == "success" and "candles" in resp_deep_raw.get("data", {}):
             resp_deep = resp_deep_raw["data"]
             print(f"Timestamp Fetch: {len(resp_deep['candles'])} candles.")
             if resp_deep['candles']:
                 print(f"Start: {datetime.fromtimestamp(resp_deep['candles'][0]['datetime']/1000)}")
                 print(f"End:   {datetime.fromtimestamp(resp_deep['candles'][-1]['datetime']/1000)}")
        else:
            print("Timestamp Fetch Failed:", resp_deep_raw.get("message") or resp_deep_raw)

    except Exception as e:
        print(f"History Fetch Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_schwab_history())
