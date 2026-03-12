import pandas as pd
import numpy as np
import math

df = pd.read_parquet(r'data/NQ1_1W.parquet')
df.index = df.index.tz_convert('US/Eastern')
df = df.dropna()

e5 = df['close'].ewm(span=5, adjust=False).mean()
d = df.iloc[-53:-1]

h = d['high']
l = d['low']
c = d['close']
o = d['open']
e2 = e5.iloc[-53:-1].shift(1)  # EMA[1] for previous week

mask = ~h.isna() & ~e2.isna()
h = h[mask].tail(52)
l = l[mask].tail(52)
c = c[mask].tail(52)
o = o[mask].tail(52)
e2 = e2[mask].tail(52)

up_standard = ((h - e2) / e2 * 100).values
dn_standard = ((e2 - l) / e2 * 100).values

print("=== SCENARIO TESTING FOR MEAN & MEDIAN ===")
scenarios = [
    ("Standard: (H-E)/E", up_standard, dn_standard),
    ("Log Return: ln(H/E)", np.log(h/e2) * 100, np.log(e2/l) * 100),
    ("Div by Close: (H-E)/C", ((h - e2) / c) * 100, ((e2 - l) / c) * 100),
    ("Div by Open: (H-E)/O", ((h - e2) / o) * 100, ((e2 - l) / o) * 100)
]

for name, up, dn in scenarios:
    print(f"{name:20s} | MeanHi={np.mean(up):.2f} MedHi={np.median(up):.2f} | MeanLo={np.mean(dn):.2f} MedLo={np.median(dn):.2f}")

print("\n=== MODE SCENARIO TESTING (Standard Dist, Bin=0.1) ===")
# Test different mode strategies
bins = np.round(up_standard / 0.1) * 0.1
u, counts = np.unique(bins, return_counts=True)
mx = counts.max()
cands = u[counts == mx]

print(f"Candidates for exact tie (max count={mx}): {list(np.round(cands, 3))}")
print(f"Nearest to Mean ({np.mean(up_standard):.2f}): {cands[np.argmin(np.abs(cands - np.mean(up_standard)))]:.2f}")
print(f"Lowest candidate: {np.min(cands):.2f}")
print(f"Highest candidate: {np.max(cands):.2f}")
print(f"Median of candidates: {np.median(cands):.2f}")

print("\n=== MODE BINNING STRATEGIES ===")
for b in [0.05, 0.1, 0.25, 0.5]:
    b_round = np.round(up_standard / b) * b
    b_floor = np.floor(up_standard / b) * b
    b_ceil = np.ceil(up_standard / b) * b
    
    for label, binned in [("Round", b_round), ("Floor", b_floor), ("Ceil", b_ceil)]:
        u, c = np.unique(binned, return_counts=True)
        m_cands = u[c == c.max()]
        m_near = m_cands[np.argmin(np.abs(m_cands - np.mean(up_standard)))]
        if abs(m_near - 0.3) < 0.1:
            print(f"Bin={b} {label}: Mode={m_near:.2f} (count={c.max()})")

