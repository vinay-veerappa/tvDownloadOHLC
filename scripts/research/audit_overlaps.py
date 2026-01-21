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

def audit_mismatches():
    df_1m = load_data("NQ1", "1m")
    df_1h = load_data("NQ1", "1h")
    
    # Target dates with known mismatches or interesting behavior
    dates = ["2025-10-06", "2025-11-17", "2025-12-18", "2025-12-22", "2025-12-26", "2026-01-05", "2026-01-07", "2026-01-08"]
    
    tolerance = 2.0 * 0.25 # 0.5 points
    
    for d_str in dates:
        d = pd.to_datetime(d_str).date()
        m = df_1m[df_1m['date'] == d]
        h = df_1h[df_1h['date'] == d]
        
        or_match = m[m['time_only'] == time(9, 30)]
        if or_match.empty: continue
        or_h, or_l = or_match.iloc[0]['high'], or_match.iloc[0]['low']
        
        # Hourly bars 09:00-15:00
        rth_h = h[(h['time_only'] >= time(9, 0)) & (h['time_only'] <= time(15, 0))]
        
        print(f"\nAUDIT {d_str} | OR: {or_l}-{or_h}")
        
        touches = 0
        broke_idx = -1
        ret_idx = -1
        gap_idx = -1
        
        for i, (t, row) in enumerate(rth_h.iterrows()):
            hh, hl = row['high'], row['low']
            # Pine logic: touchesOR
            overlap = hh >= (or_l - tolerance) and hl <= (or_h + tolerance)
            # Pine logic: brokeOR
            broke = hl > (or_h + tolerance) or hh < (or_l - tolerance)
            # Gap logic: Is the entire candle outside the range?
            full_gap = hl > or_h or hh < or_l
            
            if overlap:
                touches += 1
                if broke_idx != -1 and ret_idx == -1:
                    ret_idx = i
            elif broke:
                if broke_idx == -1: broke_idx = i
                if full_gap: gap_idx = i
            
            print(f"  {t.time()} | H={hh:<8} L={hl:<8} | {'Overlap' if overlap else 'Broke'}{' GAP' if full_gap else ''}")
        
        print(f"  Summary: Total Touches={touches}, BrokeIdx={broke_idx}, GapIdx={gap_idx}, RetIdx={ret_idx}")

if __name__ == "__main__":
    audit_mismatches()
