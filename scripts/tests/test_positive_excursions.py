import pandas as pd
import numpy as np

# Simulate Pine's exact logic on our (faulty but indicative) Parquet data
df = pd.read_parquet(r'data/NQ1_1W.parquet')
df.index = df.index.tz_convert('US/Eastern')
df = df.dropna()

e5 = df['close'].ewm(span=5, adjust=False).mean()

# "prevWeekHigh vs prevWeeklyEma" 
up = ((df['high'].shift(1) - e5.shift(2)) / e5.shift(2)) * 100
dn = ((e5.shift(2) - df['low'].shift(1)) / e5.shift(2)) * 100

for offset in range(5):
    if offset == 0:
        u = up.iloc[-52:]
        d = dn.iloc[-52:]
    else:
        u = up.iloc[-(52+offset):-offset]
        d = dn.iloc[-(52+offset):-offset]
        
    print(f"\n--- OFFSET {offset} ---")
    print(f"All values Mean Hi: {np.mean(u):.2f}%")
    
    u_pos = u[u > 0]
    d_pos = d[d > 0]
    
    print(f"Positive ONLY Mean Hi: {np.mean(u_pos):.2f}%")
    print(f"Positive ONLY Mean Lo: {np.mean(d_pos):.2f}%")
    print(f"Positive ONLY Median Hi: {np.median(u_pos):.2f}%")
    print(f"Positive ONLY Median Lo: {np.median(d_pos):.2f}%")

