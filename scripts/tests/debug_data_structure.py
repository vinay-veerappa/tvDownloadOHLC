"""
Diagnose why Python Mean Hi=2.34% vs Pine/reference 2.67%.
Same futures instrument, same data — find the exact cause of the offset.
"""
import pandas as pd
import numpy as np

DATA_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d.parquet"

df = pd.read_parquet(DATA_PATH)
df.index = df.index.tz_convert('US/Eastern')

print("=== DATA STRUCTURE ===")
print(f"Index timezone: {df.index.tz}")
print(f"Date range: {df.index[0]} -> {df.index[-1]}")
print(f"Total rows: {len(df)}")
print(f"Columns: {list(df.columns)}")
print()

# Day of week distribution
dow_counts = df.index.day_name().value_counts()
print("Day of week counts:")
print(dow_counts.to_string())
print()

# Show last 10 rows with day-of-week
print("Last 10 rows with day of week:")
last10 = df.tail(10).copy()
last10['dow'] = last10.index.day_name()
print(last10[['open','high','low','close','dow']].to_string())
print()

# ── Compare W-FRI vs W-MON vs W-SUN resampling ───────────────────────────────
print("=== WEEKLY RESAMPLING COMPARISON ===")
for anchor in ['W-FRI', 'W-SAT', 'W-SUN', 'W-MON']:
    w = df.resample(anchor).agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
    e5 = w['close'].ewm(span=5, adjust=False).mean()
    e5_s1 = e5.shift(1)
    
    data = pd.DataFrame({'high':w['high'],'low':w['low'],'ema':e5,'ema_s1':e5_s1}).dropna().iloc[:-1]
    last52 = data.iloc[-52:]
    
    up_e5   = ((last52['high'] - last52['ema'])   / last52['ema']   * 100)
    up_s1   = ((last52['high'] - last52['ema_s1'])/ last52['ema_s1']* 100)
    
    print(f"{anchor}: N={len(last52)}  "
          f"mean_hi(same-week EMA)={up_e5.mean():.2f}%  "
          f"mean_hi(prev-week EMA)={up_s1.mean():.2f}%  "
          f"last_week_end={last52.index[-1].date()}")

print()

# ── Show specific weekly data for last 5 weeks ─────────────────────────────
print("=== LAST 5 WEEKS DETAIL (W-FRI) ===")
w_fri = df.resample('W-FRI').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
e5 = w_fri['close'].ewm(span=5, adjust=False).mean()
e5_s1 = e5.shift(1)
for i in range(-6, -1):
    row = w_fri.iloc[i]
    ema_val = e5.iloc[i]
    ema_s1_val = e5_s1.iloc[i]
    up_same = (row['high'] - ema_val) / ema_val * 100
    up_prev = (row['high'] - ema_s1_val) / ema_s1_val * 100
    print(f"  {w_fri.index[i].date()}: H={row['high']:.0f} C={row['close']:.0f} "
          f"EMA={ema_val:.1f} EMA_prev={ema_s1_val:.1f} "
          f"upPct_same={up_same:.2f}% upPct_prev={up_prev:.2f}%")
