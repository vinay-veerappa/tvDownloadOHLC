"""BB multi-session multi-trade data collection.

Tests BB mean reversion across all sessions (Globex, Asia, London, NY_AM, NY_MIDDAY, NY_PM)
with up to 3 trades per session. Outputs per-session breakdown to decide what to keep.
"""
import sys, pandas as pd, numpy as np
sys.path.insert(0, '.')
from scripts.analysis.range_strategy_comparison import (
    BBRsiMeanReversionStrategy, build_day_context, BacktestEngine
)
from scripts.utils.fused_data_loader import load_fused_data

df = load_fused_data('ES1')
df = df[df.index >= '2025-01-01'].copy()
df5 = df.resample('5min', label='left', closed='left').agg(
    {'open':'first','high':'max','low':'min','close':'last','volume':'sum'}
).dropna()

df_daily = df.resample('D').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
tr = pd.concat([
    df_daily['high']-df_daily['low'],
    (df_daily['high']-df_daily['close'].shift(1)).abs(),
    (df_daily['low']-df_daily['close'].shift(1)).abs()
], axis=1).max(axis=1)
daily_atr = tr.rolling(10, min_periods=1).mean()

df['trade_date'] = df.index.date
evening = df.index.hour >= 18
df.loc[evening, 'trade_date'] = (df.loc[evening].index + pd.Timedelta(days=1)).date
unique_dates = sorted(df['trade_date'].unique())

strat = BBRsiMeanReversionStrategy(
    symbol='ES', bb_period=20, std_dev=2.0,
    rsi_period=14, adx_threshold=25.0, use_adx=True,
    max_trades_per_session=3
)
engine = BacktestEngine(symbol='ES', entry_mode='market')

all_trades = []
trade_nums = {}  # id(trade) -> trade_num_session
for i, t_date in enumerate(unique_dates):
    if i % 100 == 0:
        print(f"  Day {i}/{len(unique_dates)}...")
    ts = pd.Timestamp(t_date)
    if ts.weekday() >= 5:
        continue
    ctx = build_day_context(ts, df, df5, daily_atr, ib_minutes=30)
    if ctx is None:
        continue
    for sess in strat.get_active_sessions():
        after_time = None
        for trade_num in range(3):
            sig = strat.detect_signal(ctx, sess, after_time=after_time)
            if sig is None:
                break
            sig.metadata['strategy_name'] = strat.name
            sig.metadata['trade_num_session'] = trade_num + 1
            trade = engine.simulate_trade(sig, ctx)
            if trade is not None:
                trade.strategy_name = strat.name
                all_trades.append(trade)
                trade_nums[id(trade)] = trade_num + 1
                after_time = trade.exit_time
            else:
                break

print(f"\nTotal trades: {len(all_trades)}")

if all_trades:
    # Per-session breakdown
    results = []
    for sess in strat.get_active_sessions():
        sess_trades = [t for t in all_trades if t.session_name == sess]
        if not sess_trades:
            continue
        pnls = [t.total_pnl_dollars for t in sess_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        wr = len(wins)/len(pnls)*100 if pnls else 0
        pf = sum(wins)/abs(sum(losses)) if losses else 999
        net = sum(pnls)
        avg_r = np.mean([t.r_multiple for t in sess_trades])

        # Per trade-num breakdown
        t1 = [t for t in sess_trades if trade_nums.get(id(t)) == 1]
        t2 = [t for t in sess_trades if trade_nums.get(id(t)) == 2]
        t3 = [t for t in sess_trades if trade_nums.get(id(t)) == 3]
        results.append({
            'session': sess,
            'trades': len(sess_trades),
            't1': len(t1), 't2': len(t2), 't3': len(t3),
            'wr': f"{wr:.1f}%",
            'pf': f"{pf:.2f}",
            'net': f"${net:.0f}",
            'avg_r': f"{avg_r:.3f}",
        })

    print(f"\n{'Session':<12} {'Trades':>6} {'T1':>4} {'T2':>4} {'T3':>4} {'WR':>6} {'PF':>5} {'Net':>8} {'AvgR':>7}")
    print("-" * 60)
    for r in results:
        print(f"{r['session']:<12} {r['trades']:>6} {r['t1']:>4} {r['t2']:>4} {r['t3']:>4} {r['wr']:>6} {r['pf']:>5} {r['net']:>8} {r['avg_r']:>7}")

    # Overall
    pnls = [t.total_pnl_dollars for t in all_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    wr = len(wins)/len(pnls)*100
    pf = sum(wins)/abs(sum(losses)) if losses else 999
    net = sum(pnls)
    print(f"\n{'ALL':<12} {len(all_trades):>6} {'':>4} {'':>4} {'':>4} {wr:>5.1f}% {pf:>5.2f} ${net:>7.0f}")