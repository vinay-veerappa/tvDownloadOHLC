"""Verify HTF EMA stats using weekly parquet data directly."""
import pandas as pd
import numpy as np

DATA = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1W.parquet"
LOOKBACK = 52
OPEN_LB = 48
ZONE_S = 2.0
ZONE_E = 3.0

def pine_median(arr):
    s = np.sort(arr)
    n = len(s)
    mid = int(np.floor(n * 0.5))
    return s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) * 0.5

def pine_mode(arr, b=0.1):
    mu = np.mean(arr)
    bins = np.round(arr / b) * b
    u, c = np.unique(bins, return_counts=True)
    mx = c.max()
    cands = u[c == mx]
    return float(cands[np.argmin(np.abs(cands - mu))])

df = pd.read_parquet(DATA)
df.index = df.index.tz_convert('US/Eastern')
print(f"Weekly data: {df.index[0].date()} to {df.index[-1].date()}, rows={len(df)}")

e5 = df['close'].ewm(span=5, adjust=False).mean()

# Drop last (possibly incomplete) week
completed = df.iloc[:-1].copy()
completed['ema'] = e5.iloc[:-1]
completed['ema_s1'] = e5.shift(1).iloc[:-1]
completed = completed.dropna()

last52 = completed.iloc[-LOOKBACK:]
last48 = completed.iloc[-OPEN_LB:]

# Pine: upPct = (prevWeekHigh - weeklyEma) / weeklyEma * 100
# weeklyEma = ta.ema(close,5)[1] on weekly TF = same-row EMA in Python
up = ((last52['high'] - last52['ema']) / last52['ema'] * 100).values
dn = ((last52['ema'] - last52['low']) / last52['ema'] * 100).values

print(f"\n{'='*50}")
print(f"STATISTICAL SUMMARY (N={len(up)})")
print(f"{'='*50}")
print(f"  Mean  Hi: {np.mean(up):.2f}%   ref: 2.67%")
print(f"  Mean  Lo: {np.mean(dn):.2f}%   ref: 2.05%")
print(f"  Med   Hi: {pine_median(up):.2f}%   ref: 2.59%")
print(f"  Med   Lo: {pine_median(dn):.2f}%   ref: 0.68%")
print(f"  Mode  Hi: {pine_mode(up):.2f}%   ref: 0.30%")
print(f"  Mode  Lo: {pine_mode(dn):.2f}%   ref: 0.30%")

# Open above: prevWeeklyEma = ema[2] = ema.shift(1) in Python
oa = (last48['open'] >= last48['ema_s1']).mean() * 100
print(f"\nOPEN ABOVE EMA (N={OPEN_LB}): {oa:.1f}%   ref: 70.8%")

# Zone
eu = (up >= ZONE_S).mean() * 100
ed = (dn >= ZONE_S).mean() * 100
cu = (up >= ZONE_E).mean() * 100
cd = (dn >= ZONE_E).mean() * 100
print(f"\nZONE METRICS")
print(f"  Entry up: {eu:.1f}%  ref: 59.6%")
print(f"  Entry dn: {ed:.1f}%  ref: 34.6%")
print(f"  Comp  up: {cu:.1f}%  ref: 53.8%")
print(f"  Comp  dn: {cd:.1f}%  ref: 23.1%")
