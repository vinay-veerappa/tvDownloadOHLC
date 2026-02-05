
import pandas as pd
import os
import json
from datetime import datetime, timedelta

DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\data"
SOURCE_1D = "NQ1_1d.parquet"
LIVE_PARQUET = r"c:\Users\vinay\tvDownloadOHLC\data\live\live_storage_-NQ.parquet"

def verify_levels():
    print("--- Loading Data for Verification ---")
    
    # 1. Load 1D Parquet
    path_1d = os.path.join(DATA_DIR, SOURCE_1D)
    df = pd.read_parquet(path_1d)
    
    # TZ Conversion
    if 'time' in df.columns and 'datetime' not in df.columns:
         df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
         df = df.set_index('datetime')
    
    df.index = df.index.tz_convert('US/Eastern')
    
    # 2. Filter January 2026
    start_jan = pd.Timestamp("2026-01-01", tz='US/Eastern')
    end_jan = pd.Timestamp("2026-02-01", tz='US/Eastern')
    
    jan_data = df[(df.index >= start_jan) & (df.index < end_jan)]
    
    print(f"\n--- January 2026 Data Analysis ({len(jan_data)} days) ---")
    print(jan_data[['high', 'low', 'close']].to_string())
    
    calc_h = jan_data['high'].max()
    calc_l = jan_data['low'].min()
    calc_m = (calc_h + calc_l) / 2
    
    print(f"\nCalculated Jan Profile:")
    print(f"High: {calc_h}")
    print(f"Low:  {calc_l}")
    print(f"Mid:  {calc_m}")
    
    # 2b. Current Month (Feb 2026) Analysis
    start_feb = pd.Timestamp("2026-02-01", tz='US/Eastern')
    feb_data = df[df.index >= start_feb]
    
    if not feb_data.empty:
        curr_h = feb_data['high'].max()
        curr_l = feb_data['low'].min()
        curr_r = curr_h - curr_l
        
        # 30% Levels
        # Bear Level: Usually High - 30% of Range? Or Low + 30%?
        # User said "Bear and Bull". 
        # Bull 30%: Low + 0.3 * Range (Holding this supports Bull case?)
        # Bear 30%: High - 0.3 * Range (Holding this supports Bear case?)
        bull_30 = curr_l + (curr_r * 0.3)
        bear_30 = curr_h - (curr_r * 0.3)
        
        print(f"\n--- Current Month (Feb) Developing Profile ---")
        print(f"High: {curr_h}")
        print(f"Low:  {curr_l}")
        print(f"Range: {curr_r}")
        print(f"30% Bull (Low + 0.3R): {bull_30:.2f}")
        print(f"30% Bear (High - 0.3R): {bear_30:.2f}")
        
    # 4. Check EMA5
    # Hypothesis: Use Weekly Data?
    # Resample to Weekly 'W-FRI'
    df_weekly = df.resample('W-FRI').agg({'close':'last'})
    df_weekly['ema5'] = df_weekly['close'].ewm(span=5, adjust=False).mean()
    
    last_week = df_weekly.iloc[-1]
    prev_week = df_weekly.iloc[-2] # Last Completed Week (Jan 30?)
    
    print(f"\n--- Weekly EMA 5 Verification ---")
    print(f"Prev Week Date: {prev_week.name}")
    print(f"Prev Week Close: {prev_week['close']}")
    print(f"Prev Week EMA5: {prev_week['ema5']:.2f}")
    
    # Calculate Daily EMA again for comparison
    df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
    last_day = df.iloc[-1]
    prev_day = df.iloc[-2]
    
    print(f"\n--- Daily EMA 5 Verification ---")
    print(f"Prev Day Date: {prev_day.name}")
    print(f"Prev Day EMA5: {prev_day['ema5']:.2f}")
    
    # 5. Zone Calc
    u_h = 1.03
    u_l = 1.025
    l_h = 0.975
    l_l = 0.970
    
    # Check Target 25693 against Candidates
    target = 25693.0
    cand_daily = prev_day['ema5']
    cand_weekly = prev_week['ema5']
    
    print(f"\n--- Target Match Check (Target: {target}) ---")
    print(f"Daily Diff: {cand_daily - target:.2f}")
    print(f"Weekly Diff: {cand_weekly - target:.2f}")
    
    # Use the closest for Zone Calc
    best_ema = cand_daily if abs(cand_daily - target) < abs(cand_weekly - target) else cand_weekly
    src_name = "Daily" if best_ema == cand_daily else "Weekly"
    
    print(f"\n--- Zone Verification using {src_name} EMA ({best_ema:.2f}) ---")
    print(f"Upper Zone: {best_ema * u_l:.2f} - {best_ema * u_h:.2f}")
    print(f"Lower Zone: {best_ema * l_l:.2f} - {best_ema * l_h:.2f}")
    
    print(f"\n--- EMA 5 Verification ---")
    print(f"Last Date in 1D File: {df.index[-1]}")
    print(f"Last Close: {last_day['close']}")
    print(f"Last EMA5:  {last_day['ema5']:.2f}")
    
    print(f"Prev Date: {df.index[-2]}")
    print(f"Prev Close: {prev_day['close']}")
    print(f"Prev EMA5:  {prev_day['ema5']:.2f}")
    
    # 5. Zone Calc
    u_h = 1.03
    u_l = 1.025
    l_h = 0.975
    l_l = 0.970
    
    ema = last_day['ema5']
    print(f"\n--- Zone Verification (Based on EMA {ema:.2f}) ---")
    print(f"Upper Zone: {ema * u_l:.2f} - {ema * u_h:.2f}")
    print(f"Lower Zone: {ema * l_l:.2f} - {ema * l_h:.2f}")

if __name__ == "__main__":
    verify_levels()
