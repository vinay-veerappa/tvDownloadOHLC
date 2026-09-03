import pandas as pd
import numpy as np
from pathlib import Path
import sys

_root = Path('.').resolve()
sys.path.insert(0, str(_root))
from scripts.execution.nt8_parity_engine import NT8ParityEngine

df_1m = pd.read_parquet('data/NQ1_1m.parquet')
df_1m = df_1m[df_1m.index >= '2026-01-01'].copy()
if df_1m.index.tz is None:
    df_1m.index = df_1m.index.tz_localize('UTC').tz_convert('America/New_York')
else:
    df_1m.index = df_1m.index.tz_convert('America/New_York')

df_5m = df_1m.resample('5min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
df_4h = df_5m.resample('4h').agg({'close': 'last'}).dropna()
df_4h['ema50'] = df_4h['close'].ewm(span=50).mean()
df_4h_reindexed = df_4h.reindex(df_5m.index, method='ffill')
htf_bias_arr = np.where(df_5m['close'] > df_4h_reindexed['ema50'], 1, -1)

c5 = df_5m['close'].to_numpy()
o5 = df_5m['open'].to_numpy()
h5 = df_5m['high'].to_numpy()
l5 = df_5m['low'].to_numpy()
times_5m = df_5m.index
n5 = len(df_5m)
time_strs_5m = times_5m.strftime('%H%M')

signals_5m = np.zeros(n5, dtype=np.int32)
vibes = 0
bagholder = np.nan
pain = np.nan

def consult_cb(bias: int, idx: int):
    max_lb = min(15, idx)
    ext_o = o5[idx - 1]
    for k in range(1, max_lb + 1):
        is_opp = (c5[idx - k] < o5[idx - k]) if bias == 1 else (c5[idx - k] > o5[idx - k])
        if is_opp:
            ext_o = o5[idx - k]
            break
    return ext_o

for i in range(50, n5):
    c0, o0, h0, l0 = c5[i], o5[i], h5[i], l5[i]
    hhmm = time_strs_5m[i]
    pers = 1 if c0 > o0 else (-1 if c0 < o0 else 0)
    if vibes == 0:
        vibes = pers if pers != 0 else 1
        bagholder = consult_cb(vibes, i)
        pain = h0 if vibes == 1 else l0

    if vibes == 1 and h0 > pain:
        pain = h0
        bagholder = consult_cb(1, i)
    elif vibes == -1 and l0 < pain:
        pain = l0
        bagholder = consult_cb(-1, i)

    in_time = ('0945' <= hhmm <= '1530') and not ('1200' <= hhmm <= '1330')
    if in_time:
        if vibes == -1 and c0 > bagholder and htf_bias_arr[i] == 1:
            vibes = 1
            pain = h0
            bagholder = consult_cb(1, i)
            signals_5m[i] = 1
        elif vibes == 1 and c0 < bagholder and htf_bias_arr[i] == -1:
            vibes = -1
            pain = l0
            bagholder = consult_cb(-1, i)
            signals_5m[i] = -1

sig_series_5m = pd.Series(signals_5m, index=times_5m)

engine = NT8ParityEngine(
    point_value=2.0, # Micro MNQ ($2/pt)
    tick_size=0.25,
    max_trades_per_day=3,
    max_consecutive_losers=2,
    pause_minutes=30,
    hard_stop_losers=3,
    daily_max_loss=150.0,
    contracts=2,
    commission_per_contract_rt=0.70,
    slippage_ticks=0.5,
)

trades = engine.simulate_mtf(
    df_5m=df_5m,
    df_1m=df_1m,
    signals_5m=sig_series_5m,
    queen_bps=10.0,
    runner_bps=30.0,
    stop_loss_bps=5.0, # 5.0 bps hard stop
    earliest_entry_hhmm=945,
    latest_entry_hhmm=1530,
    flatten_hhmm=1555,
    filter_lunch=True,
    allow_reentry=True
)

df_t = pd.DataFrame(trades)
pnl = df_t['total_pnl_usd'].sum()
gp = df_t[df_t['total_pnl_usd'] > 0]['total_pnl_usd'].sum()
gl = abs(df_t[df_t['total_pnl_usd'] < 0]['total_pnl_usd'].sum())
pf = gp / gl if gl > 0 else 0
wr = (df_t['total_pnl_usd'] > 0).mean() * 100.0

print(f"Total Trades: {len(df_t)}")
print(f"Net Realized PnL (MNQ):  ${pnl:,.2f}")
print(f"Net Realized PnL (NQ):   ${pnl * 10:,.2f}")
print(f"Gross Profit:            ${gp:,.2f}")
print(f"Gross Loss:             -${gl:,.2f}")
print(f"Profit Factor:           {pf:.2f}")
print(f"Win Rate:                {wr:.1f}%")
