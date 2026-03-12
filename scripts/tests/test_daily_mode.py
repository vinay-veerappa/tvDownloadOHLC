import pandas as pd
import numpy as np

df_d = pd.read_parquet(r'data/NQ1_1d.parquet')
df_w = pd.read_parquet(r'data/NQ1_1W.parquet')

if not pd.api.types.is_datetime64tz_dtype(df_d.index):
    df_d.index = pd.to_datetime(df_d.index, utc=True).tz_convert('US/Eastern')
else:
    df_d.index = df_d.index.tz_convert('US/Eastern')
df_d = df_d.dropna()

df_w.index = df_w.index.tz_convert('US/Eastern')
df_w = df_w.dropna()

e5_w = df_w['close'].ewm(span=5, adjust=False).mean()

# We need the prevWeeklyEma for each daily bar
# prevWeeklyEma is the EMA of the week that ENDED before the current week started.
daily_emas = pd.Series(index=df_d.index, dtype=float)

for daily_idx in df_d.index:
    # Find the most recent weekly bar that ended BEFORE this daily bar's week
    # In parquet, weekly bars are stamped with Monday or Sunday. 
    # The week ends on Friday. Let's just do a backward fill from the weekly index.
    past_weeks = e5_w[e5_w.index < daily_idx - pd.Timedelta(days=3)]
    if len(past_weeks) > 1:
        # Get the one from [2] weeks ago basically
        daily_emas.loc[daily_idx] = past_weeks.iloc[-1]

df_d['prevWeeklyEma'] = daily_emas
df_d = df_d.dropna()

up_daily = ((df_d['high'] - df_d['prevWeeklyEma']) / df_d['prevWeeklyEma']) * 100

for offset in [0, 10, 20]:
    u = up_daily.iloc[-(260+offset):-offset] if offset > 0 else up_daily.iloc[-260:]
    u_rounded = np.round(u, 1)
    vc = u_rounded.value_counts()
    modes = vc[vc == vc.max()].index.tolist()
    print(f"Daily Mode(s) offset {offset}: {modes} (count={vc.max()})")
