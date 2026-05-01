import os
import pandas as pd
from datetime import datetime

DATA_DIR = "data"
live_map = {"NQ1": "-NQ", "ES1": "-ES", "YM1": "-YM", "RTY1": "-RTY", "CL1": "-CL", "GC1": "-GC"}

def check_freshness(ticker):
    safe_ticker = live_map.get(ticker, ticker)
    live_path = os.path.join(DATA_DIR, "live", f"live_storage_{safe_ticker}.parquet")
    if not os.path.exists(live_path):
        return f"{ticker}: File not found at {live_path}"
    
    try:
        df = pd.read_parquet(live_path)
        if df.empty:
            return f"{ticker}: Empty storage"
            
        last_ts = pd.to_datetime(df['time'].max(), unit='ms')
        now = datetime.utcnow()
        gap_mins = (now - last_ts).total_seconds() / 60
        
        status = "CURRENT" if gap_mins < 15 else "STALE"
        return f"{ticker}: {status} (Last: {last_ts.isoformat()}, Gap: {round(gap_mins, 2)}m)"
    except Exception as e:
        return f"{ticker}: Error - {str(e)}"

tickers = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
for t in tickers:
    print(check_freshness(t))
