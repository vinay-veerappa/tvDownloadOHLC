import pandas as pd
import numpy as np

w_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df = pd.read_csv(w_path)
df['time'] = pd.to_datetime(df['time'], utc=True)
df = df.sort_values('time').reset_index(drop=True)

df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()

for low_shift in range(0, 4):
    for ema_shift in range(0, 4):
        for clip in [False, True]:
            val = ((df['ema5'].shift(ema_shift) - df['low'].shift(low_shift)) / df['ema5'].shift(ema_shift)) * 100
            if clip:
                val = val.clip(lower=0)
                
            for length in [12, 26, 48, 52, 104, 200, 500]:
                u = val.iloc[-length:]
                if len(u) > 0:
                    mu = u.mean()
                    md = u.median()
                    
                    if (round(mu, 2) >= 3.15 and round(mu, 2) <= 3.25) or (round(md, 2) >= 3.15 and round(md, 2) <= 3.25):
                        print(f"MATCH DN (low[{low_shift}], ema[{ema_shift}], clip={clip}, n={length}): Mean={mu:.2f}%, Median={md:.2f}%")
