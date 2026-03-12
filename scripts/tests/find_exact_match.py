import pandas as pd
import numpy as np

df = pd.read_parquet(r'data/NQ1_1W.parquet')
df.index = df.index.tz_convert('US/Eastern')
df = df.dropna()
e5 = df['close'].ewm(span=5, adjust=False).mean()

print("Searching for: MeanHi=2.67, MedHi=2.59, MeanLo=2.05")

found = False
for h_shift in [0, 1]:
    for e_shift in [0, 1, 2]:
        h = df['high'].shift(h_shift)
        l = df['low'].shift(h_shift)
        e = e5.shift(e_shift)
        
        upPct = ((h - e) / e) * 100
        dnPct = ((e - l) / e) * 100
        
        for offset in range(10):
            if offset == 0:
                u = upPct.iloc[-52:]
                d = dnPct.iloc[-52:]
            else:
                u = upPct.iloc[-(52 + offset) : -offset]
                d = dnPct.iloc[-(52 + offset) : -offset]
                
            m_hi = np.mean(u)
            med_hi = np.median(u)
            m_lo = np.mean(d)
            
            if abs(m_hi - 2.67) < 0.2 and abs(med_hi - 2.59) < 0.2 and abs(m_lo - 2.05) < 0.2:
                print(f"MATCH! H[{h_shift}] vs E[{e_shift}], offset={offset}: MeanHi={m_hi:.2f}, MedHi={med_hi:.2f}, MeanLo={m_lo:.2f}")
                found = True

if not found:
    print("No matching distribution exists in the data across any recent offset or shift combination.")

