"""
Simulate Pine's EXACT DOW collection logic to identify the EMA mismatch.

Pine collection logic:
- isNewDailySec fires at the first intraday bar of each new daily session D_k
- Collects D_{k-1}'s high/low
- Uses weeklyEmaStable = request.security("W", ta.ema(close,5)[1], lookahead_off)

weeklyEmaStable semantics at each D_k firing:
  With lookahead_off: the W context is at the last COMPLETED weekly bar.
  The `[1]` shift goes one FURTHER back from the last completed bar.

  KEY QUESTION: 
  - When D_k is the FIRST bar of a new week W_m (i.e., Sunday 18:00 ET),
    what is the "last completed weekly bar"?
    Option A: W_{m-1} (just closed before D_k started) → [1] = W_{m-2} = w[m-2].ema
    Option B: Still W_{m-1} but the W context moves to W_m at its CLOSE time
              → at the OPEN of W_m (Sun 18:00 ET), last completed = W_{m-1}, [1] = W_{m-2}

  - When D_k is NOT the first bar of its week (e.g., Mon/Tue/Wed/Thu within W_k),
    last completed = W_{k-1}, [1] = W_{k-2}

So EITHER way, weeklyEmaStable should always = w[k-2].ema relative to the WEEK the intraday bar is in.

But Python uses w[k-1] for Thu and gets the right answer (57.7% ≈ Pine's 59.6%)...
And Pine Mon gets km2 (63.5%) which implies w[k-2]...
And Pine Wed gets km1 (55.8%) which implies w[k-1]...

This is contradictory unless there's something about the Wed collection specifically.

Let me trace each day's collection event and WHICH weekly bar it lands in.
"""

import pandas as pd, numpy as np, pytz
from pathlib import Path

ET = pytz.timezone('America/New_York')
d = Path('scripts/indicators/htf_ema_analysis')
w = pd.read_csv(d / 'CME_MINI_NQ1!, 1W_f166a.csv')
w['dt'] = pd.to_datetime(w['time'], unit='s', utc=True).dt.tz_convert(ET)
w = w.sort_values('dt').reset_index(drop=True)
w['ema'] = w['close'].ewm(span=5, adjust=False).mean()

df = pd.read_csv(d / 'CME_MINI_NQ1!, 1D_a1cee.csv')
df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert(ET)
df = df.sort_values('dt').reset_index(drop=True)
last = w.iloc[-1]['dt']
df = df[(df['dt'] < last)].copy().reset_index(drop=True)
df['dow_py'] = df['dt'].dt.dayofweek
df['day_name'] = df['dt'].dt.day_name()

def find_week_idx(t):
    """Find which weekly bar this daily bar belongs to"""
    idx = -1
    for i in range(len(w)):
        if w.loc[i, 'dt'] <= t:
            idx = i
        else:
            break
    return idx

df['wk_idx'] = df['dt'].apply(find_week_idx)

def cal_dow(ts):
    """Same as f_calendar_dow_from_ts: extract calendar day at 12:00 noon"""
    noon = ts.replace(hour=12, minute=0, second=0, microsecond=0)
    return noon.dayofweek  # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun

def day_idx(dow):
    """0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, else -1"""
    if dow in [0,1,2,3,4]:
        return dow
    return -1

# True Pine data reference
PINE_ACTUAL = {0: ('Mon',63.5,3.15), 1: ('Tue',59.6,3.05), 2: ('Wed',55.8,2.62), 3: ('Thu',59.6,2.88)}

# Simulate Pine collection with different EMA source hypotheses
# At each firing of isNewDailySec (at daily bar D_k), we collect D_{k-1}'s data.
# The "collection bar" is D_k; the "data bar" is D_{k-1}.

# HYPOTHESIS 1: weeklyEmaStable = w[wk_idx_of_D_k - 2].ema (double shift: lookahead_off + [1])
# HYPOTHESIS 2: weeklyEmaStable = w[wk_idx_of_D_k - 1].ema (no [1]: lookahead_off only)
# HYPOTHESIS 3: weeklyEmaStable = w[wk_idx_of_D_{k-1} - 1].ema (based on DATA bar's week, no shift)

collections = []
for k in range(1, len(df)):
    Dk = df.iloc[k]       # collection event fires here
    Dk_prev = df.iloc[k-1]  # data bar (previous daily)
    
    # Compute DOW of data bar
    dow = cal_dow(Dk_prev['dt'])
    idx = day_idx(dow)
    if idx == -1:
        continue  # skip Sunday/Saturday
    
    # EMA for each hypothesis
    wk_collect = int(Dk['wk_idx'])         # week of collection bar
    wk_data = int(Dk_prev['wk_idx'])       # week of data bar
    
    ema_h1 = w.loc[wk_collect-2,'ema'] if wk_collect >= 2 else np.nan  # H1: collect-week - 2
    ema_h2 = w.loc[wk_collect-1,'ema'] if wk_collect >= 1 else np.nan  # H2: collect-week - 1
    ema_h3 = w.loc[wk_data-1,'ema'] if wk_data >= 1 else np.nan         # H3: data-week - 1 (Python)
    
    hi = Dk_prev['high']
    lo = Dk_prev['low']
    
    collections.append({
        'idx': idx,
        'wk_collect': wk_collect,
        'wk_data': wk_data,
        'wk_same': wk_collect == wk_data,
        'hi': hi,
        'lo': lo,
        'ema_h1': ema_h1,
        'ema_h2': ema_h2,
        'ema_h3': ema_h3,
    })

cdf = pd.DataFrame(collections)

# Filter: exclude current week (use last 52 per day)
# simulate the cap=52 with latest 52 per idx
lb = 52

def stats(g, ema_col):
    g = g.copy().tail(lb)
    dn = np.abs((g[ema_col] - g['lo']) / g[ema_col] * 100)
    dn = dn.dropna()
    if len(dn) == 0:
        return np.nan, np.nan
    return (dn >= 2).mean() * 100, dn.mean()

print("=== Comparison of EMA hypotheses vs Pine actual ===")
print(f"{'Day':4s} {'H1(km-2) HD':11s} {'H2(km-1) HD':11s} {'H3(data) HD':11s} {'Pine actual':12s}")
for idx, (name, pine_hd, pine_ml) in PINE_ACTUAL.items():
    g = cdf[cdf['idx'] == idx]
    h1_hd, h1_ml = stats(g, 'ema_h1')
    h2_hd, h2_ml = stats(g, 'ema_h2')
    h3_hd, h3_ml = stats(g, 'ema_h3')
    print(f"{name:4s} {h1_hd:.1f}%/{h1_ml:.2f}  {h2_hd:.1f}%/{h2_ml:.2f}  {h3_hd:.1f}%/{h3_ml:.2f}  {pine_hd:.1f}%/{pine_ml:.2f}")

print()
print("=== Collection distribution: how many fire in SAME week as data bar? ===")
for idx, (name, _, _) in PINE_ACTUAL.items():
    g = cdf[cdf['idx'] == idx]
    same = g['wk_same'].sum()
    diff = (~g['wk_same']).sum()
    print(f"{name:4s}: {same} fire in same week, {diff} fire in different week (week+1)")

print()
print("=== For Mon: does wk_collect == wk_data? ===")
mon = cdf[cdf['idx']==0].tail(10)
for _, row in mon.iterrows():
    print(f"  wk_data={int(row['wk_data'])}  wk_collect={int(row['wk_collect'])}  same={row['wk_same']}")

print()
print("=== Key: wk_collect vs wk_data for Wed ===") 
wed = cdf[cdf['idx']==2].tail(10)
for _, row in wed.iterrows():
    print(f"  wk_data={int(row['wk_data'])}  wk_collect={int(row['wk_collect'])}  same={row['wk_same']}")
