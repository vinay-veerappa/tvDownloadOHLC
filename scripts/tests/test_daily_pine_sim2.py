import pandas as pd
import numpy as np

# Load Daily
d_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1D_96a65.csv'
df_d = pd.read_csv(d_path)
df_d['time'] = pd.to_datetime(df_d['time'], utc=True)
df_d = df_d.sort_values('time').reset_index(drop=True)

# Build weekly series exact same way Pine Script does:
# Weekly bars in Pine script are just aggregation of daily bars (Mon-Sun).
# Let's resample daily to weekly (ending on Sunday, label='left' like TV)
df_d.set_index('time', inplace=True)
# TradingView weekly starts on Monday for most assets, or Sunday 18:00
# Let's use W-SUN or W-MON.
df_w = df_d.resample('W-MON', closed='left', label='left').agg({
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last'
}).dropna()

df_w['ema5'] = df_w['close'].ewm(span=5, adjust=False).mean()

# Now go back to daily
df_d = df_d.reset_index()
df_d['week_start'] = df_d['time'].dt.to_period('W-SUN').dt.start_time

df_d['isNewWeek'] = df_d['week_start'] != df_d['week_start'].shift(1)

up_pct_arr = []

for i in range(1, len(df_d)):
    if df_d['isNewWeek'].iloc[i]:
        d_time = df_d['time'].iloc[i]
        # Past weeks that are fully closed by d_time
        past_w = df_w[df_w.index < d_time]
        
        if len(past_w) >= 3:
            prevWeekHigh = past_w['high'].iloc[-1]   # The week that just closed
            prevWeekEma = past_w['ema5'].iloc[-2]    # The EMA of the week before that
            
            up_pct = max(0.0, ((prevWeekHigh - prevWeekEma) / prevWeekEma) * 100.0)
            up_pct_arr.append(up_pct)

u = pd.Series(up_pct_arr[-52:])
print(f"Daily-Simulated Pine Mean Hi: {u.mean():.2f}%")
print(f"Daily-Simulated Pine Median Hi: {u.median():.2f}%")
