import pandas as pd
import numpy as np

# Load Weekly for exact request.security mapping
w_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df_w = pd.read_csv(w_path)
df_w['time'] = pd.to_datetime(df_w['time'], utc=True)
df_w = df_w.sort_values('time').reset_index(drop=True)
df_w['ema5'] = df_w['close'].ewm(span=5, adjust=False).mean()

# Load Daily
d_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1D_96a65.csv'
df_d = pd.read_csv(d_path)
df_d['time'] = pd.to_datetime(df_d['time'], utc=True)
df_d = df_d.sort_values('time').reset_index(drop=True)

# Replicate isNewWeek logic:
# `isNewWeek` is true when the week of the year changes or day <= day[1]
df_d['week_of_year'] = df_d['time'].dt.isocalendar().week
df_d['isNewWeek'] = df_d['week_of_year'] != df_d['week_of_year'].shift(1)

# Now iterate daily.
# On a daily bar where isNewWeek == True:
# Pine: [weeklyEma, prevWeeklyEma, prevWeekHigh] = request.security("W", [ema[1], ema[2], high[1]])
# Since it's lookahead_on, at the start of Week N, request.security("W", val[1]) fetches the value of Week N-1.

up_pct_arr = []
dn_pct_arr = []

for i in range(1, len(df_d)):
    if df_d['isNewWeek'].iloc[i]:
        d_time = df_d['time'].iloc[i]
        # Find the weekly bar that just ended BEFORE or exactly AT this new week start?
        # Actually in TradingView, lookahead_on means on Monday (Week N), it knows the bounding of Week N.
        # "high[1]" on the Weekly scale means the High of Week N-1.
        # Let's find Week N-1 in df_w
        # Week N-1 is the latest week in df_w whose time is strictly strictly before this week?
        # TradingView weekly bars are stamped with the start of the week (e.g., Monday).
        
        past_weeks = df_w[df_w['time'] < d_time + pd.Timedelta(days=1)] 
        
        if len(past_weeks) >= 3:
            # past_weeks.iloc[-1] is Week N or Week N-1?
            # TV weekly bars are stamped with Monday.
            # If d_time is Monday, past_weeks.iloc[-1] is exactly that Monday's weekly bar (Week N).
            # So Week N-1 is past_weeks.iloc[-2].
            
            # prevWeekHigh = high[1] on Weekly scale -> high of Week N-1
            prevWeekHigh = past_weeks['high'].iloc[-2]
            prevWeekLow = past_weeks['low'].iloc[-2]
            
            # prevWeeklyEma = ema[2] on Weekly scale -> ema of Week N-2
            prevWeeklyEma = past_weeks['ema5'].iloc[-3]
            
            up_pct = max(0.0, ((prevWeekHigh - prevWeeklyEma) / prevWeeklyEma) * 100.0)
            dn_pct = max(0.0, ((prevWeeklyEma - prevWeekLow) / prevWeeklyEma) * 100.0)
            
            up_pct_arr.append(up_pct)
            dn_pct_arr.append(dn_pct)

# Limit to last 52
u = pd.Series(up_pct_arr[-52:])
d = pd.Series(dn_pct_arr[-52:])

print(f"Clipped Daily Mean Hi: {u.mean():.2f}%")
print(f"Clipped Daily Median Hi: {u.median():.2f}%")
print(f"Clipped Daily Mean Lo: {d.mean():.2f}%")
print(f"Clipped Daily Median Lo: {d.median():.2f}%")

# What if it wasn't clipped?
up_pct_un = []
for i in range(1, len(df_d)):
    if df_d['isNewWeek'].iloc[i]:
        d_time = df_d['time'].iloc[i]
        past_weeks = df_w[df_w['time'] < d_time + pd.Timedelta(days=1)] 
        if len(past_weeks) >= 3:
            prevWeekHigh = past_weeks['high'].iloc[-2]
            prevWeeklyEma = past_weeks['ema5'].iloc[-3]
            up_pct_un.append(((prevWeekHigh - prevWeeklyEma) / prevWeeklyEma) * 100.0)

u_un = pd.Series(up_pct_un[-52:])
print(f"Unclipped Daily Mean Hi: {u_un.mean():.2f}%")
print(f"Unclipped Daily Median Hi: {u_un.median():.2f}%")

