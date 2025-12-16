
import pandas as pd
from pathlib import Path

def debug_volatility(ticker):
    path = Path(f"data/{ticker}_1m.parquet")
    if not path.exists(): return

    df = pd.read_parquet(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df.index = df.index.tz_convert('US/Eastern')
        
    df['range'] = df['high'] - df['low']
    
    print(f"--- {ticker} Avg Range by Hour ---")
    grp = df.groupby(df.index.hour)['range'].mean()
    print(grp)

debug_volatility("RTY1")
debug_volatility("ES1")
