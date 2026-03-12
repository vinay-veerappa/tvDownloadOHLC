"""Test if reference Mode uses daily close-to-EMA distribution rather than weekly high/low"""
import pandas as pd
import numpy as np

df = pd.read_parquet(r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d.parquet")
df.index = df.index.tz_convert('US/Eastern')

weekly = df.resample('W-FRI').agg({'close': 'last'})
weekly['ema5'] = weekly['close'].ewm(span=5, adjust=False).mean()
daily_ema = weekly['ema5'].reindex(df.index, method='ffill')

df['pct_dist'] = (df['close'] - daily_ema) / daily_ema * 100
cutoff = df.index[-1] - pd.DateOffset(weeks=52)
recent = df[df.index >= cutoff].dropna(subset=['pct_dist'])
pct_vals = recent['pct_dist'].values

def mode_near_mean(arr, b):
    mu = np.mean(arr)
    bins = np.round(arr / b) * b
    u, c = np.unique(bins, return_counts=True)
    mx = c.max()
    cands = u[c == mx]
    return float(cands[np.argmin(np.abs(cands - mu))]), int(mx)

print(f"Daily bars in last 52 weeks: {len(recent)}")
print(f"Mean pct_dist: {np.mean(pct_vals):.2f}%")
print(f"Median pct_dist: {np.median(pct_vals):.2f}%")
print()
for bsz in [0.1, 0.25, 0.5]:
    m, cnt = mode_near_mean(pct_vals, bsz)
    m2, cnt2 = mode_near_mean(np.abs(pct_vals), bsz)
    print(f"  bin={bsz}: mode(signed)={m:.2f}(n={cnt})  mode(abs)={m2:.2f}(n={cnt2})")

print()
print("Open stats header check (reference: Mean 0.72%, Med 1.08%, Mode 1.5%):")
print(f"  Mean: {np.mean(pct_vals):.2f}%  Median: {np.median(pct_vals):.2f}%")

# Also check weekly up/dn with prevWeeklyEma
e5_p2 = weekly['ema5'].shift(1)
stats = pd.DataFrame({'high': df.resample('W-FRI')['high'].max(),
                       'low': df.resample('W-FRI')['low'].min(),
                       'ema': e5_p2}).dropna().iloc[:-1]
last52 = stats.iloc[-52:]
up = ((last52['high'] - last52['ema']) / last52['ema'] * 100).values
dn = ((last52['ema'] - last52['low'])  / last52['ema'] * 100).values
print()
print(f"Weekly: N={len(up)}, Mean_Hi={np.mean(up):.2f}, Med_Hi={np.median(up):.2f}")
print(f"Weekly: N={len(dn)}, Mean_Lo={np.mean(dn):.2f}, Med_Lo={np.median(dn):.2f}")
for bsz in [0.05, 0.1, 0.25]:
    mhi, ci = mode_near_mean(up, bsz)
    mlo, cj = mode_near_mean(dn, bsz)
    print(f"  Week bin={bsz}: mode_hi={mhi:.2f}(n={ci})  mode_lo={mlo:.2f}(n={cj})")
