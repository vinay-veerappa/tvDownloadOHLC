import pandas as pd
import numpy as np

df = pd.read_parquet(r'data/NQ1_1W.parquet')
df.index = df.index.tz_convert('US/Eastern')
df = df.dropna()

e5 = df['close'].ewm(span=5, adjust=False).mean()
h = df['high'].shift(1)
l = df['low'].shift(1)
e2 = e5.shift(2)

mask = ~h.isna() & ~e2.isna()
h = h[mask].tail(52)
l = l[mask].tail(52)
e2 = e2[mask].tail(52)

up = ((h - e2) / e2 * 100).values
dn = ((e2 - l) / e2 * 100).values

print(f"Base data: MeanHi={np.mean(up):.2f} MeanLo={np.mean(dn):.2f}")

for b in [0.5, 1.0, 0.1]:
    # Binning by Floor (e.g. 0.0 to 0.49 -> 0.0)
    b_floor = np.floor(up / b) * b
    u, c = np.unique(b_floor, return_counts=True)
    mx = c.max()
    best_bins = u[c == mx]
    
    for bb in best_bins:
        in_bin = up[(b_floor == bb)]
        avg_in_bin = np.mean(in_bin)
        print(f"Floor Bin={b}, bin_start={bb:.2f}, count={mx}: avg of items in bin = {avg_in_bin:.3f}%")

    # Binning by Round
    b_round = np.round(up / b) * b
    u, c = np.unique(b_round, return_counts=True)
    mx = c.max()
    best_bins = u[c == mx]
    
    for bb in best_bins:
        in_bin = up[(b_round == bb)]
        avg_in_bin = np.mean(in_bin)
        print(f"Round Bin={b}, bin_center={bb:.2f}, count={mx}: avg of items in bin = {avg_in_bin:.3f}%")

# Let's also check dn
for b in [0.5, 1.0, 0.1]:
    b_floor = np.floor(dn / b) * b
    u, c = np.unique(b_floor, return_counts=True)
    mx = c.max()
    best_bins = u[c == mx]
    
    for bb in best_bins:
        in_bin = dn[(b_floor == bb)]
        avg_in_bin = np.mean(in_bin)
        print(f"DN Floor Bin={b}, bin_start={bb:.2f}, count={mx}: avg of items in bin = {avg_in_bin:.3f}%")
