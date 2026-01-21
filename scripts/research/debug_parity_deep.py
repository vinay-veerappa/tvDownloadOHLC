import pandas as pd
import numpy as np
import pytz
from datetime import time
from pathlib import Path

DATA_DIR = Path("c:/Users/vinay/tvDownloadOHLC/data")
NY_TZ = pytz.timezone("America/New_York")

def load_data(ticker: str, tf: str):
    path = DATA_DIR / f"{ticker}_{tf}.parquet"
    df = pd.read_parquet(path)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY_TZ)
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    return df

def debug_parity_deep(d_str):
    d = pd.to_datetime(d_str).date()
    df_1m = load_data("NQ1", "1m")
    df_1h = load_data("NQ1", "1h")
    
    m = df_1m[df_1m['date'] == d]
    h = df_1h[df_1h['date'] == d]
    
    or_candle = m[m['time_only'] == time(9, 30)]
    or_h, or_l = or_candle.iloc[0]['high'], or_candle.iloc[0]['low']
    print(f"\nDEBUG {d_str}: OR={or_l}-{or_h}")
    
    # Check late price up to 16:00
    late = m.between_time('15:00', '16:00')
    last_return = None
    for t, row in late.iterrows():
        if row['high'] >= or_l and row['low'] <= or_h:
            last_return = t
            break
    if last_return:
        print(f"Late Return detected at {last_return.time()}")
    else:
        print("No return after 15:00")

    # Hourly boxes 10:00-15:00
    rth_h = h[(h['time_only'] >= time(10, 0)) & (h['time_only'] <= time(15, 0))]
    tolerance = 2.0 * 0.25 # 0.5
    
    print(f"Hourly Analytics (Pinescript indices):")
    touches = 0
    broke_idx = -1
    ret_idx = -1
    
    for i, (t, row) in enumerate(rth_h.iterrows()):
        hh, hl = row['high'], row['low']
        overlap = hh >= (or_l - tolerance) and hl <= (or_h + tolerance)
        broke = hl > (or_h + tolerance) or hh < (or_l - tolerance)
        
        status = "Overlap" if overlap else "Broke"
        print(f"Idx {i} ({t.time()}): {status} | H={hh}, L={hl}")
        
        if broke and broke_idx == -1:
            broke_idx = i
        elif not broke and overlap:
            touches += 1
            if broke_idx != -1 and ret_idx == -1:
                ret_idx = i
                
    win_start = 2 # 11:00
    ret_after = (ret_idx >= win_start)
    sep = ret_idx - broke_idx
    enough_sep = (sep >= 1)
    
    print(f"Touches={touches}, BrokeIdx={broke_idx}, RetIdx={ret_idx}")
    print(f"Ret_after_11={ret_after}, Enough_sep={enough_sep}")
    print(f"R2 Candidate: {broke_idx != -1 and ret_idx != -1 and ret_after and enough_sep}")

if __name__ == "__main__":
    debug_parity_deep("2025-11-17")
    debug_parity_deep("2026-01-07")
    debug_parity_deep("2026-01-08")
    debug_parity_deep("2025-12-22")
