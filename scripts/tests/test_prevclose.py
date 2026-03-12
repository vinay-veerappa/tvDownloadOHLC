import pandas as pd
import numpy as np

df = pd.read_parquet(r'data/NQ1_1W.parquet')
df.index = df.index.tz_convert('US/Eastern')
df = df.dropna()

print("Testing (High - PrevClose) / PrevClose for Weekly Stats...")

for offset in range(5):
    h = df['high'].shift(1)
    l = df['low'].shift(1)
    prev_c = df['close'].shift(2)
    
    up = ((h - prev_c) / prev_c) * 100
    dn = ((prev_c - l) / prev_c) * 100
    
    if offset == 0:
        u = up.iloc[-52:]
        d = dn.iloc[-52:]
    else:
        u = up.iloc[-(52+offset):-offset]
        d = dn.iloc[-(52+offset):-offset]
        
    m_hi = np.mean(u)
    m_lo = np.mean(d)
    
    print(f"Offset {offset}: MeanHi={m_hi:.2f}%, MeanLo={m_lo:.2f}%")

print("\nTesting (Close - PrevClose) / PrevClose ...")
for offset in range(3):
    c = df['close'].shift(1)
    prev_c = df['close'].shift(2)
    
    pct = ((c - prev_c) / prev_c) * 100
    
    if offset == 0:
        p = pct.iloc[-52:]
    else:
        p = pct.iloc[-(52+offset):-offset]

    up_c = p[p > 0]
    dn_c = np.abs(p[p < 0])
    
    print(f"Offset {offset}: Mean Close Up={np.mean(up_c):.2f}%, Mean Close Dn={np.mean(dn_c):.2f}%")

