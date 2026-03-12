import pandas as pd
import numpy as np

# Load the exact weekly data
df = pd.read_parquet(r'data/NQ1_1W.parquet')
df.index = df.index.tz_convert('US/Eastern')
df = df.dropna()

e5 = df['close'].ewm(span=5, adjust=False).mean()

# Let's test standard shifts with the exact "round to 0.1%" rule
found = False

print("Testing exact 'round to 0.1%' mode on distances to EMA...")
for h_shift in [0, 1]:
    for e_shift in [0, 1, 2]:
        h = df['high'].shift(h_shift)
        l = df['low'].shift(h_shift)
        e = e5.shift(e_shift)
        
        upPct = ((h - e) / e) * 100
        # Round to nearest 0.1%
        up_rounded = np.round(upPct, 1)
        
        # Test recent 52 week windows
        for offset in range(5):
            if offset == 0:
                u = up_rounded.iloc[-52:]
                u_raw = upPct.iloc[-52:]
            else:
                u = up_rounded.iloc[-(52 + offset) : -offset]
                u_raw = upPct.iloc[-(52 + offset) : -offset]
            
            # Find mode
            val_counts = u.value_counts()
            if len(val_counts) == 0: continue
            
            max_count = val_counts.max()
            modes = val_counts[val_counts == max_count].index.tolist()
            
            m_hi = np.mean(u_raw)
            med_hi = np.median(u_raw)
            
            # We are looking for mode exactly 0.3
            if 0.3 in modes or 0.35 in modes:
                print(f"MATCH MODE! H[{h_shift}] vs E[{e_shift}], off={offset}: Mode={modes} (count={max_count}) | Mean={m_hi:.2f}, Med={med_hi:.2f}")

print("\nTesting 'move' as distance from OPEN instead of EMA...")
for h_shift in [0, 1]:
    h = df['high'].shift(h_shift)
    o = df['open'].shift(h_shift)
    
    upPct = ((h - o) / o) * 100
    up_rounded = np.round(upPct, 1)
    
    u = up_rounded.iloc[-52:]
    u_raw = upPct.iloc[-52:]
    
    vc = u.value_counts()
    modes = vc[vc == vc.max()].index.tolist()
    print(f"H[{h_shift}] vs O[{h_shift}]: Mode={modes} | Mean={np.mean(u_raw):.2f}")

