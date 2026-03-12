import pandas as pd

w_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df_full = pd.read_csv(w_path)
df_full['time'] = pd.to_datetime(df_full['time'], utc=True)
df_full = df_full.sort_values('time').reset_index(drop=True)

# The user's chart only has ~48 weeks of history.
# We must start EMA calculation on exactly a 48-week dataset.
# Actually, the user's N=48 means 48 weeks were *processed*.
# Let's take the last 48+2 weeks so we have high[1] and ema[2].
n_weeks = 50 
df = df_full.iloc[-n_weeks:].copy().reset_index(drop=True)

# TradingView calculates EMA using SMA for the initial value
# ewma with adjust=False is standard, but the key is the short history.
df['ema5'] = df['close'].ewm(span=5, adjust=False, min_periods=5).mean()

# Calculate [2] offset
df['up_pct'] = ((df['high'].shift(1) - df['ema5'].shift(2)) / df['ema5'].shift(2)) * 100
df['up_pct_clipped'] = df['up_pct'].clip(lower=0)

u = df['up_pct_clipped'].dropna()
print(f"Chart-Limited History (N={len(u)})")
print(f"Mean Hi: {u.mean():.2f}%")
print(f"Median Hi: {u.median():.2f}%")

# Let's try 52 weeks just in case
df2 = df_full.iloc[-54:].copy().reset_index(drop=True)
df2['ema5'] = df2['close'].ewm(span=5, adjust=False, min_periods=5).mean()
df2['up_pct'] = ((df2['high'].shift(1) - df2['ema5'].shift(2)) / df2['ema5'].shift(2)) * 100
u2 = df2['up_pct'].clip(lower=0).dropna()
print(f"\nChart-Limited History 52 (N={len(u2)})")
print(f"Mean Hi: {u2.mean():.2f}%")
print(f"Median Hi: {u2.median():.2f}%")
