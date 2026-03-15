import pandas as pd, numpy as np, pytz
from pathlib import Path

ET = pytz.timezone('America/New_York')
d = Path('scripts/indicators/htf_ema_analysis')
w = pd.read_csv(d/'CME_MINI_NQ1!, 1W_f166a.csv')
w['dt'] = pd.to_datetime(w['time'], unit='s', utc=True).dt.tz_convert(ET)
w = w.sort_values('dt').reset_index(drop=True)
w['ema'] = w['close'].ewm(span=5, adjust=False).mean()

df = pd.read_csv(d/'CME_MINI_NQ1!, 1D_a1cee.csv')
df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert(ET)
df = df.sort_values('dt').reset_index(drop=True)
last = w.iloc[-1]['dt']
df = df[(df['dt'] < last)].copy().reset_index(drop=True)

# For each daily bar, find which weekly bar it belongs to
def find_week_idx(t):
    idx = -1
    for i in range(len(w)):
        if w.loc[i,'dt'] <= t:
            idx = i
        else:
            break
    return idx

df['wk_idx'] = df['dt'].apply(find_week_idx)
df['dow_py'] = df['dt'].dt.dayofweek
df['day_name'] = df['dt'].dt.day_name()

print("=== Last 15 daily bars and their wk_idx ===")
for _, row in df.tail(15).iterrows():
    print(f"  {row['dt']}  dow_py={row['dow_py']}  {row['day_name']}  wk_idx={int(row['wk_idx'])}")

print()
print("=== Last 8 weekly bars ===")
for i in range(max(0, len(w)-8), len(w)):
    print(f"  i={i}  {w.loc[i,'dt']}  ema={w.loc[i,'ema']:.2f}")

print()
print("=== Pine's weeklyEmaStable: what EMA does each daily bar get? ===")
print("    Pine fires isNewDailySec at NEXT bar after daily close")
print("    So Thursday data collects at the NEXT intraday bar (Mon 18:00 ET = start of NEXT week)")
print()

# Simulate Pine's exact behavior:
# isNewDailySec fires => prev daily bar's stats collected using CURRENT weeklyEmaStable
# dTimePrevSec = prev daily open time, wk_idx of the CURRENT bar decides EMA
# For each daily bar in df, the 'collection event' fires at the NEXT daily bar's first intraday bar
# So if daily[j] spans Mon-Tue, collection fires at first intraday bar in Tue which is in week W_k
# EMA used = wk_idx of THAT intraday bar - 1

# For daily bars Mon-Thu in week W_k: they get collected at the start of the NEXT daily bar
# Mon -> fires at Tue 18:00 ET bar (still in W_k) => wk_idx = k => EMA = w[k-1]  (CORRECT vs Python)
# Tue -> fires at Wed 18:00 ET bar (still in W_k) => wk_idx = k => EMA = w[k-1]  (CORRECT)
# Wed -> fires at Thu 18:00 ET bar (still in W_k) => wk_idx = k => EMA = w[k-1]  (CORRECT)
# Thu -> fires at Mon 18:00 ET bar (NEXT week W_{k+1}) => wk_idx = k+1 => EMA = w[k] (WRONG, should be k-1)
# But Python assigns Thursday to week W_k and uses w[k-1]
# So for Thu: Pine uses w[k].ema but Python uses w[k-1].ema -> Pine is 1 week AHEAD for Thu

# But we measured Pine gives HitDn=59.6% for Thu vs Python's 57.7%
# That's a small diff - maybe it's Thursday OR maybe it's the Mon-Sun issue

# For Monday data:
# There's a SUNDAY daily bar (Sun 18:00 ET = start of week W_k) 
# Pine's f_calendar_dow_from_ts(Sun 18:00 ET) -> extracts day=Sunday -> dow = dayofweek.sunday = 1
# f_day_idx(1) -> -1 -> EXCLUDED
# Then Monday 18:00 ET bar is collected:
# - dTimePrevSec might be Sunday 18:00 ET OR Thursday 18:00 ET depending on how many bars there are
# Actually: Sunday 18:00 ET IS a daily bar, so:
# Mon 18:00 ET fires => dTimePrevSec = Sun 18:00 ET bar
# f_calendar_dow_from_ts(Sun 18:00 ET) extracts Sun -> dow=sunday -> idx=-1 -> SKIP!
# So Monday data is NEVER collected from Mon's perspective!

# Instead, Mon data would be collected when collecting "Sun" data (which is skipped)
# and "Tue" fires with dTimePrevSec = Mon 18:00 ET

# WAIT: let me recheck. dTimePrevSec = time[1] from daily security
# So when daily bar changes from Mon to Tue:
#   dTimeSec = Tue 18:00 ET (current daily bar open)
#   dTimePrevSec = Mon 18:00 ET (prev daily bar open)
#   isNewDailySec fires
#   dDowTs = dTimePrevSec = Mon 18:00 ET
#   f_calendar_dow_from_ts(Mon 18:00 ET) -> extracts Mon -> dow=monday -> idx=0 -> COLLECT into monUp/monDn
# OK so Mon IS being collected correctly

# Now what about the Monday bar between Sunday and Monday?
# daily bar sequence: ... Thu -> Sun -> Mon -> Tue -> ...
# When Tue fires: dTimePrevSec = Mon -> Mon data collected OK (wk_idx of Tue bar = k) => EMA = w[k-1] OK
# When Mon fires: dTimePrevSec = Sun -> Sun data, idx=-1, SKIP
# So Mon data is collected when Tue fires (good).
# For Tue: when Wed fires: dTimePrevSec = Tue -> idx=1 -> wk_idx(Wed bar in W_k) = k => EMA = w[k-1] OK
# For Wed: when Thu fires: dTimePrevSec = Wed -> idx=2 -> wk_idx(Thu bar in W_k) = k => EMA = w[k-1] OK
# For Thu: when next fires? After Thu is Sun (next week W_{k+1}). When Mon fires:
#   dTimePrevSec = Sun 18:00 ET of W_{k+1} start -> dow = sunday -> idx=-1 -> SKIP!
# Wait, no! After Thu we have a Sun bar, then Mon:
# Sun fires: dTimePrevSec = Thu -> idx=3 -> wk_idx(Sun bar) = k+1 => EMA = w[k] (WRONG! one week ahead)
# Mon fires: dTimePrevSec = Sun -> idx=-1 -> SKIP
#
# SO: Thu data is collected on Sun with wk_idx = k+1 using w[k], NOT w[k-1]

print("Summary of Pine data collection for each day of week:")
print("  Mon data: collected when Tue fires, Tue is in week W_k => EMA = w[k-1]  (same as Python)")
print("  Tue data: collected when Wed fires, Wed is in week W_k => EMA = w[k-1]  (same as Python)")
print("  Wed data: collected when Thu fires, Thu is in week W_k => EMA = w[k-1]  (same as Python)")
print("  Thu data: collected when Sun fires, Sun is in week W_{k+1} => EMA = w[k]  (ONE WEEK AHEAD of Python)")
print()
print("This explains why Thu rows are slightly different but not drastically wrong")
print("Mon/Tue show bigger discrepancies - let me check if there's a different mechanism...")

# Is there also a case where Mon/Tue data gets wrong week?  
# Check the Sun bars and their wk_idx
sun_bars = df[df['dow_py'] == 6]
print()
print("=== Sunday bars and their wk_idx ===")
for _, row in sun_bars.tail(5).iterrows():
    print(f"  {row['dt']}  wk_idx={int(row['wk_idx'])}")

# So when Sun bar fires isNewDailySec:
# dTimePrevSec = Thu (prior daily bar open, last bar before weekend)
# Thu is in week W_{k} but Sun is in week W_{k+1}
# weeklyEmaStable at Sun 18:00 ET in W_{k+1} = w[k+1-1].ema = w[k].ema  (current week that just closed)
# Python uses w[k-1].ema for Thu
# Pine uses w[k].ema for Thu => ONE WEEK AHEAD

# For Mon bars the question is whether there's a Sunday bar at all
# From the data above, we see Sunday bars exist with dow_py=6
# So Mon fires => dTimePrevSec = Sun 18:00 ET => idx=-1 => SKIP (Mon data missed here)
# Mon data captured when Tue fires in same week W_k => EMA = w[k-1]  (CORRECT for Mon)

# Then why are Mon numbers so wrong?
# Check: is there actually a case where Mon is in a different week than Tue?
# Let's look at sequences where there's no Sunday bar
print()
print("=== Finding Mon bars WITHOUT a preceding Sunday bar ===")
for i in range(1, len(df)):
    row = df.iloc[i]
    prev = df.iloc[i-1]
    if row['dow_py'] == 0:  # Monday
        if prev['dow_py'] != 6:  # prev is NOT Sunday
            print(f"  Mon at {row['dt']}  prev was {prev['dt']} ({prev['day_name']})")
