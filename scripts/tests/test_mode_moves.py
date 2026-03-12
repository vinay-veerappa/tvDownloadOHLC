import pandas as pd
import numpy as np

df = pd.read_parquet(r'data/NQ1_1W.parquet')
df.index = df.index.tz_convert('US/Eastern')
df = df.dropna()

print("Testing Close-to-Close 'move' for weekly bars...")

# Percentage change from previous week's close
# If close > prev_close -> upward move
# If close < prev_close -> downward move

pct_change = df['close'].pct_change() * 100

upward_moves = pct_change[pct_change > 0]
downward_moves = np.abs(pct_change[pct_change < 0])

up_rounded = np.round(upward_moves, 1)
dn_rounded = np.round(downward_moves, 1)

# Last 52 weeks
up_52 = up_rounded.loc[df.index[-52]:]
dn_52 = dn_rounded.loc[df.index[-52]:]

print(f"Upward Moves Count: {len(up_52)}, Downward Moves Count: {len(dn_52)}")

print("UPWARD MODES:")
print(up_52.value_counts().head(5))

print("DOWNWARD MODES:")
print(dn_52.value_counts().head(5))

# Also test High to Low range?
range_pct = (df['high'] - df['low']) / df['low'] * 100
range_52 = np.round(range_pct.iloc[-52:], 1)
print("\nRANGE MODES:")
print(range_52.value_counts().head(5))

# Also test Distance from Open to High (up move) and Open to Low (down move)
up_open = (df['high'] - df['open']) / df['open'] * 100
dn_open = (df['open'] - df['low']) / df['open'] * 100
u_o_52 = np.round(up_open.iloc[-52:], 1)
d_o_52 = np.round(dn_open.iloc[-52:], 1)
print("\nOPEN TO HIGH MODES:")
print(u_o_52.value_counts().head(5))
print("\nOPEN TO LOW MODES:")
print(d_o_52.value_counts().head(5))

