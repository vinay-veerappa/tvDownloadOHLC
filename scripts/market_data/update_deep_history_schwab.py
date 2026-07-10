import os
import sys
import asyncio
import httpx
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

# Ensure we can import data_utils from local dir
current_dir = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.abspath(os.path.join(current_dir, "../utils"))
sys.path.append(utils_dir)

import data_utils

# We must append the project root so scripts.streaming is found
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from scripts.streaming.options.config import HUB_URL

# Map App Ticker -> Schwab Ticker
SCHWAB_MAP = {
    # Indices
    "SPX": "$SPX", 
    "VIX": "$VIX",
    "VVIX": "$VVIX",
    "NDX": "$NDX",
    "RUT": "$RUT",
    "DJI": "$DJI",
    
    # ETFs
    "SPY": "SPY", 
    "QQQ": "QQQ", 
    "IWM": "IWM", 
    "DIA": "DIA", 
    "GLD": "GLD", 
    "TLT": "TLT", 
    
    # Key Stocks
    "NVDA": "NVDA", "AAPL": "AAPL", "MSFT": "MSFT", 
    "AMD": "AMD", "TSLA": "TSLA", "AMZN": "AMZN",
    "META": "META", "GOOGL": "GOOGL",
    "PLTR": "PLTR", "JPM": "JPM", "GS": "GS",

    # Futures
    "ES1": "/ES", 
    "NQ1": "/NQ",
    "RTY1": "/RTY",
    "YM1": "/YM",
    "ES": "/ES",
    "NQ": "/NQ",
    "RTY": "/RTY",
    "YM": "/YM",
    "CL": "/CL",
    "GC": "/GC"
}

async def hub_request(method, params):
    """Send a REST request through the Hub's proxy."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=60.0)
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, dict) and "status" not in result:
                    return {"status": "success", "data": result}
                return result
            else:
                return {"status": "error", "message": f"Hub Error [{resp.status_code}]: {resp.text}"}
        except Exception as e:
            return {"status": "error", "message": f"Hub Connection Error: {str(e)}"}

async def fetch_15m_history(symbol):
    print(f"Fetching 2yr 15m data for {symbol} via Hub...")
    
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=730) # 2 Years
    
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    try:
        resp = await hub_request("get_price_history", {
            "symbol": symbol,
            "period_type": "day",
            "frequency_type": "minute",
            "frequency": 15,
            "start_date": start_ms,
            "end_date": end_ms,
            "need_extended_hours_data": True
        })
        
        if resp.get("status") != "success":
            print(f"Fetch Error {symbol}: {resp.get('message')}")
            return None
            
        data = resp.get("data", {})
        candles = data.get('candles', [])
        
        if not candles:
            print(f"No candles found for {symbol}.")
            return None
            
        print(f"  Got {len(candles)} rows.")
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        
        # Normalize to App Standard
        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
        df = df.set_index('datetime')
        
        df = df.rename(columns={
            "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"
        })
        
        return df[['open', 'high', 'low', 'close', 'volume']]
        
    except Exception as e:
        print(f"Fetch Error {symbol}: {e}")
        return None

async def update_deep_history():
    for app_ticker, schwab_ticker in SCHWAB_MAP.items():
        print(f"\n--- Processing {app_ticker} ({schwab_ticker}) ---")
        
        new_df = await fetch_15m_history(schwab_ticker)
        if new_df is None or new_df.empty:
            continue
            
        filename = f"{app_ticker}_15m.parquet"
        filepath = os.path.join(data_utils.DATA_DIR, filename)
        
        # Merge Logic
        if os.path.exists(filepath):
            try:
                old_df = pd.read_parquet(filepath)
                # Ensure index
                if not isinstance(old_df.index, pd.DatetimeIndex):
                    if 'datetime' in old_df.columns:
                        old_df['datetime'] = pd.to_datetime(old_df['datetime'])
                        old_df = old_df.set_index('datetime')
                
                print(f"  Merging with existing {len(old_df)} rows...")
                combined = pd.concat([old_df, new_df])
                combined = combined[~combined.index.duplicated(keep='last')] # Keep new data for overlaps
                combined = combined.sort_index()
            except Exception as e:
                print(f"  Merge error: {e}. Overwriting.")
                combined = new_df
        else:
            combined = new_df
            
        # Save
        try:
            data_utils.safe_save_parquet(combined, filepath)
            print(f"  Saved {len(combined)} rows to {filename}")
        except Exception as e:
            print(f"  Save Failed: {e}")
            
        # Rate limit kindness
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(update_deep_history())
