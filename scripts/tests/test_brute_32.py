import pandas as pd
import numpy as np

# Let's brute force any combination in the Weekly dataframe that yields exactly 3.2%
w_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df = pd.read_csv(w_path)
df['time'] = pd.to_datetime(df['time'], utc=True)
df = df.sort_values('time').reset_index(drop=True)

df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()

# Test different calculations for distance and tracking
formulas = {
    'prevWeekHigh_vs_prevWeekEma': ((df['high'].shift(1) - df['ema5'].shift(2)) / df['ema5'].shift(2)) * 100,
    'prevWeekHigh_vs_weekEma': ((df['high'].shift(1) - df['ema5'].shift(1)) / df['ema5'].shift(1)) * 100,
    'currWeekHigh_vs_prevWeekEma': ((df['high'] - df['ema5'].shift(1)) / df['ema5'].shift(1)) * 100,
    'currWeekHigh_vs_weekEma': ((df['high'] - df['ema5']) / df['ema5']) * 100,
}

for name, series in formulas.items():
    s_clipped = series.clip(lower=0)
    for length in [12, 26, 52, 104, 200, 500]:
        u = s_clipped.iloc[-length:]
        mu = u.mean()
        md = u.median()
        if round(mu, 2) == 3.20 or round(md, 2) == 3.20 or round(mu, 1) == 3.2 or round(md, 1) == 3.2:
            print(f"MATCH: {name} (N={length}) Mean={mu:.2f}%, Median={md:.2f}%")
