"""Run BB Python engine with $0 costs (NT8 parity) and compare to NT8 backtest."""
import sys, pandas as pd
sys.path.insert(0, '.')
from scripts.analysis.range_strategy_comparison import (
    run_comparison, BBRsiMeanReversionStrategy
)
from scripts.utils.fused_data_loader import load_fused_data

df = load_fused_data('ES')
df.index = pd.to_datetime(df.index, utc=True).tz_convert('America/New_York').tz_localize(None)
df1 = df[df.index >= '2025-01-01'].copy()
df1['trade_date'] = df1.index.date
df5 = df1.resample('5min', label='left', closed='left').agg(
    {'open':'first','high':'max','low':'min','close':'last','volume':'sum'}
).dropna()

strats = [BBRsiMeanReversionStrategy(
    rsi_period=14, bb_period=20, bb_std=2.0,
    adx_threshold=25, allow_2bar_hook=True, use_kaufman_er=False
)]

results = run_comparison(
    symbol='ES',
    df_1m=df1,
    df_5m=df5,
    strategies=strats,
    start_year=2025,
    end_year=2026,
    ib_minutes=30,
)

if results.empty:
    print("No trades")
else:
    bb = results[results['strategy_name'].str.contains('BBRsi', na=False)]
    print(f"Python BB (Wilder RSI + 2-bar hook, $0 comm/slip, 1/session)")
    print(f"Trades: {len(bb)}")
    pnls = bb['pnl']
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    wr = len(wins)/len(pnls)*100 if len(pnls) > 0 else 0
    pf = wins.sum()/abs(losses.sum()) if losses.sum() != 0 else 999
    net = pnls.sum()
    print(f"WR: {wr:.1f}%")
    print(f"PF: {pf:.2f}")
    print(f"Net: ${net:.0f}")

print()
print("NT8 BB (Wilder RSI + 2-bar hook, FixedTP1TP2, $0 comm/slip)")
print("Trades: 82 (41 entries x 2 legs)")
print("WR: 56.1%")
print("PF: 1.53")
print("Net: $7,262")