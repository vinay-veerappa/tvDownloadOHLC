import os
import sys
import asyncio
import httpx
import pandas as pd
from datetime import datetime, timezone

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.abspath(os.path.join(current_dir, "../utils"))
sys.path.append(utils_dir)

import data_utils
from data_utils import DATA_DIR
LIVE_DIR = os.path.join(DATA_DIR, "live")

# We must append the project root so scripts.streaming is found
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.append(root_dir)

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

async def force_fill(symbol, start_dt, end_dt):
    print(f"Force fetching {symbol} from {start_dt} to {end_dt} via Hub...")
    
    # Hub uses ms timestamp for start/end datetimes
    start_ms = int(start_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(end_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
    
    resp = await hub_request("get_price_history", {
        "symbol": symbol,
        "frequency_type": "minute",
        "frequency": 1,
        "start_date": start_ms,
        "end_date": end_ms,
        "need_extended_hours_data": True
    })
    
    if resp.get("status") != "success":
        print(f"Failed: {resp.get('message')}")
        return
        
    data = resp.get("data", {})
    candles = data.get('candles', [])
    
    if not candles:
        print("No candles returned!")
        return
        
    print(f"Got {len(candles)} new candles.")
    
    # Process
    df_new = pd.DataFrame(candles)
    df_new['time'] = df_new['datetime']
    
    df_new = df_new.rename(columns={
        "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"
    })
    df_new = df_new[['time', 'open', 'high', 'low', 'close', 'volume']]
    
    # Load Existing Live Storage
    safe_symbol = symbol.replace("/", "-")
    path = os.path.join(LIVE_DIR, f"live_storage_{safe_symbol}.parquet")
    
    if os.path.exists(path):
        print(f"Merging with {path}...")
        df_old = pd.read_parquet(path)
        
        combined = pd.concat([df_old, df_new])
        
        original_len = len(combined)
        combined = combined.drop_duplicates(subset=['time'], keep='last')
        combined = combined.sort_values('time')
        
        print(f"Merged: {original_len} -> {len(combined)} rows.")
        combined.to_parquet(path, index=False)
        print("Saved.")
    else:
        print("Live storage not found to merge into!")

async def main():
    symbols = [
        "/CL", "/ES", "/GC", "/NQ", "/RTY", "/YM",
        "AAPL", "AMZN", "GOOGL", "META", "MSFT", 
        "NFLX", "NVDA", "QQQ", "RIVN", "SPY", "TSLA"
    ]
    
    start_dt = datetime(2026, 6, 1, 0, 0, 0)
    end_dt = datetime(2026, 6, 18, 23, 59, 59)
    
    for sym in symbols:
        try:
            await force_fill(sym, start_dt, end_dt)
        except Exception as e:
            print(f"Failed for {sym}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
