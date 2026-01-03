
import pandas as pd
import numpy as np
import os
import pytz
from datetime import time, timedelta

# --- Configuration ---
TICKERS = ['NQ1', 'ES1', 'YM1', 'RTY1', 'GC1', 'CL1']
DATA_DIR = 'data'
START_YEAR = 2015

def load_data(ticker):
    # Same standard loader
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    if not os.path.exists(path): return None
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('datetime', inplace=True)
    df = df.tz_convert('US/Eastern')
    return df[df.index.year >= START_YEAR]

def verify_ib_breaks(ticker):
    df = load_data(ticker)
    if df is None: return None
    
    # Iterate Days
    daily_groups = df.groupby(df.index.date)
    
    results = []
    
    for date, day_data in daily_groups:
        # Define IB Window: 09:30 - 10:30
        ib_start = pd.Timestamp.combine(date, time(9,30)).tz_localize('US/Eastern')
        ib_end = pd.Timestamp.combine(date, time(10,30)).tz_localize('US/Eastern')
        
        ib_data = day_data.loc[ib_start:ib_end]
        if len(ib_data) < 10: continue # Need data
        
        ib_high = ib_data['high'].max()
        ib_low = ib_data['low'].min()
        ib_close = ib_data['close'].iloc[-1] # Close of the 10:30 candle (or range end)
        
        # Determine Half
        ib_range = ib_high - ib_low
        if ib_range == 0: continue
            
        midpoint = ib_low + (ib_range * 0.5)
        close_half = "Upper" if ib_close >= midpoint else "Lower"
        
        # Check Breaks Before Noon
        noon_ts = pd.Timestamp.combine(date, time(12,0)).tz_localize('US/Eastern')
        pre_noon_data = day_data.loc[ib_end:noon_ts] # From 10:30 end to Noon
        
        broke_high_noon = (pre_noon_data['high'] > ib_high).any()
        broke_low_noon = (pre_noon_data['low'] < ib_low).any()
        
        # Check Breaks Before Close (16:00)
        close_ts = pd.Timestamp.combine(date, time(16,0)).tz_localize('US/Eastern')
        full_day_data = day_data.loc[ib_end:close_ts]
        
        broke_high_day = (full_day_data['high'] > ib_high).any()
        broke_low_day = (full_day_data['low'] < ib_low).any()
        
        res = {
            'Close_Half': close_half,
            'Break_Noon': broke_high_noon or broke_low_noon,
            'Break_Day': broke_high_day or broke_low_day,
            'Hit_Bias_Noon': (close_half == 'Upper' and broke_high_noon) or (close_half == 'Lower' and broke_low_noon),
            'Hit_Bias_Day': (close_half == 'Upper' and broke_high_day) or (close_half == 'Lower' and broke_low_day)
        }
        results.append(res)
        
    res_df = pd.DataFrame(results)
    if res_df.empty: return None

    summary = []
    total = len(res_df)
    
    # 1. Broad Probabilities
    summary.append({'Metric': 'Break Before Noon', 'Rate': res_df['Break_Noon'].mean()})
    summary.append({'Metric': 'Break Before Close', 'Rate': res_df['Break_Day'].mean()})
    
    # 2. Bias (Upper Half -> Break High) probability
    upper = res_df[res_df['Close_Half'] == 'Upper']
    lower = res_df[res_df['Close_Half'] == 'Lower']
    
    if len(upper) > 0:
        summary.append({'Metric': 'Upper Half -> Break High (Day)', 'Rate': upper['Hit_Bias_Day'].mean()})
        
    if len(lower) > 0:
        summary.append({'Metric': 'Lower Half -> Break Low (Day)', 'Rate': lower['Hit_Bias_Day'].mean()})

    return pd.DataFrame(summary).assign(Ticker=ticker)

def main():
    all_res = []
    for t in TICKERS:
        print(f"Verifying IB Breaks for {t}...")
        res = verify_ib_breaks(t)
        if res is not None:
            all_res.append(res)
            print(res.to_string())
            
    if all_res:
        pd.concat(all_res).to_csv('scripts/nqstats/results/ib_breaks_verification.csv', index=False)
        print("\nSaved to scripts/nqstats/results/ib_breaks_verification.csv")

if __name__ == "__main__":
    main()
