import pandas as pd

w_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df = pd.read_csv(w_path)
df['time'] = pd.to_datetime(df['time'], utc=True)
df = df.sort_values('time').reset_index(drop=True)

df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()

# user confirmed N-48
n_weeks = 48

# Calculate for [2] offset
up_pct_2 = ((df['high'].shift(1) - df['ema5'].shift(2)) / df['ema5'].shift(2)) * 100
up_pct_clipped_2 = up_pct_2.clip(lower=0)
u2 = up_pct_clipped_2.iloc[-n_weeks:]

# Calculate for [1] offset
up_pct_1 = ((df['high'].shift(1) - df['ema5'].shift(1)) / df['ema5'].shift(1)) * 100
up_pct_clipped_1 = up_pct_1.clip(lower=0)
u1 = up_pct_clipped_1.iloc[-n_weeks:]

print(f"--- N={n_weeks} ---")
print(f"[2] Clipped Mean Hi: {u2.mean():.2f}%")
print(f"[2] Clipped Median Hi: {u2.median():.2f}%")

print(f"[1] Clipped Mean Hi: {u1.mean():.2f}%")
print(f"[1] Clipped Median Hi: {u1.median():.2f}%")

print("Let's test unclipped too...")
u2_un = up_pct_2.iloc[-n_weeks:]
print(f"[2] Unclipped Mean Hi: {u2_un.mean():.2f}%")
print(f"[2] Unclipped Median Hi: {u2_un.median():.2f}%")

u1_un = up_pct_1.iloc[-n_weeks:]
print(f"[1] Unclipped Mean Hi: {u1_un.mean():.2f}%")
print(f"[1] Unclipped Median Hi: {u1_un.median():.2f}%")

