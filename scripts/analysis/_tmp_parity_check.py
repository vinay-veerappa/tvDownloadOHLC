"""Run BB Python engine with $0 costs (NT8 parity) and compare to NT8 backtest."""
import sys, pandas as pd, numpy as np
sys.path.insert(0, '.')
from scripts.analysis.range_strategy_comparison import (
    run_comparison, BBRsiMeanReversionStrategy, build_day_context
)
from scripts.utils.fused_data_loader import load_fused_data

df = load_fused_data('ES1')
df = df[df.index >= '2025-01-01'].copy()
# Fused loader returns naive UTC timestamps; convert to ET naive for session slicing
df.index = df.index.tz_localize('UTC').tz_convert('America/New_York').tz_localize(None)
df = df[df.index >= '2025-01-01'].copy()
df['trade_date'] = df.index.date
df5 = df.resample('5min', label='left', closed='left').agg(
    {'open':'first','high':'max','low':'min','close':'last','volume':'sum'}
).dropna()

# Daily ATR
df_daily = df.resample("D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
tr = pd.concat([
    df_daily["high"] - df_daily["low"],
    (df_daily["high"] - df_daily["close"].shift(1)).abs(),
    (df_daily["low"] - df_daily["close"].shift(1)).abs(),
], axis=1).max(axis=1)
daily_atr = tr.rolling(10, min_periods=1).mean()

strat = BBRsiMeanReversionStrategy(
    symbol='ES', bb_period=20, std_dev=2.0,
    rsi_period=14, adx_threshold=25.0, use_adx=True
)

# Test a few days manually
unique_dates = sorted(df['trade_date'].unique())
signal_count = 0
for d in unique_dates[:60]:
    ts = pd.Timestamp(d)
    if ts.weekday() >= 5:
        continue
    ctx = build_day_context(ts, df, df5, daily_atr, ib_minutes=30)
    if ctx is None:
        continue
    for sess in strat.get_active_sessions():
        sig = strat.detect_signal(ctx, sess)
        if sig is not None:
            signal_count += 1
            print(f"  Signal on {d} {sess}: {sig.direction} entry={sig.entry_price:.2f}")
print(f"Total signals (first 60 days): {signal_count}")

# Now full run
strats = [BBRsiMeanReversionStrategy(
    symbol='ES', bb_period=20, std_dev=2.0,
    rsi_period=14, adx_threshold=25.0, use_adx=True
)]

results = run_comparison(
    symbol='ES',
    df_1m=df,
    df_5m=df5,
    strategies=strats,
    start_year=2025,
    end_year=2026,
    ib_minutes=30,
    engine_kwargs={'entry_mode': 'market'},
)

if results.empty:
    print("No trades from run_comparison")
else:
    bb = results[results['strategy_name'].str.contains('BBRsi', na=False)]
    print(f"Python BB (Wilder RSI + 2-bar hook, $0 comm/slip, 1/session)")
    print(f"Trades: {len(bb)}")
    if len(bb) > 0:
        pnls = bb['pnl']
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        wr = len(wins)/len(pnls)*100 if len(pnls) > 0 else 0
        pf = wins.sum()/abs(losses.sum()) if losses.sum() != 0 else 999
        net = pnls.sum()
        print(f"WR: {wr:.1f}%")
        print(f"PF: {pf:.2f}")
        print(f"Net: ${net:.0f}")