import pandas as pd
import os
from scripts.libs.nqstats.engine import NQStatsEngine

DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\live"

def check_symbol(symbol):
    safe_symbol = symbol.replace("/", "-")
    path = os.path.join(DATA_DIR, f"live_storage_{safe_symbol}.parquet")
    if not os.path.exists(path):
        print(f"❌ {symbol} Parquet not found")
        return
        
    df = pd.read_parquet(path)
    if 'timestamp' in df.columns:
         df['timestamp'] = pd.to_datetime(df['timestamp'])
         df.set_index('timestamp', inplace=True)
         
    engine = NQStatsEngine(df, ticker=symbol)
    try:
        print(engine.get_report())
    except Exception as e:
        print(f"❌ Report failed: {e}")

if __name__ == "__main__":
    check_symbol("/NQ")
    check_symbol("/ES")
