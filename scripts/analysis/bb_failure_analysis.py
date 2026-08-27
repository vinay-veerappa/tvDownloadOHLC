"""Deep failure analysis: WHY does BB fail in Globex/Asia/London?

Analyze losing vs winning trades across sessions:
1. What do losers look like? (direction, RSI depth, ADX, bandwidth, time of day, FVG/HTF/liquidity confluence)
2. Are we entering WITH the trend instead of against it? (missing directional bias)
3. Are we missing key confluences that would filter bad trades?
"""
import sys, pandas as pd, numpy as np
sys.path.insert(0, '.')
from scripts.analysis.range_strategy_comparison import (
    BBRsiMeanReversionStrategy, build_day_context, BacktestEngine, _wilder_rsi, _adx
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

# Collect detailed trade data with context at entry
all_trades = []
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
            trade = engine.simulate_trade(sig, ctx)
            if trade is not None:
                trade.strategy_name = strat.name
                all_trades.append({
                    'session': sess,
                    'date': trade.date,
                    'direction': trade.direction,
                    'entry_time': trade.entry_time,
                    'exit_time': trade.exit_time,
                    'entry_price': trade.entry_price,
                    'pnl': trade.total_pnl_dollars,
                    'r_mult': trade.r_multiple,
                    't1_hit': trade.t1_hit,
                    't2_hit': trade.t2_hit,
                    'stopped': trade.stopped_out,
                    'rsi': sig.metadata.get('rsi', np.nan),
                    'adx': sig.metadata.get('adx', np.nan),
                    'bw': sig.metadata.get('bw', np.nan),
                    'risk_pts': sig.risk_points,
                })
                after_time = trade.exit_time
            else:
                break

tdf = pd.DataFrame(all_trades)
tdf['win'] = tdf['pnl'] > 0
tdf['hour'] = pd.to_datetime(tdf['entry_time']).dt.hour
tdf['is_overnight'] = tdf['session'].isin(['GLOBEX', 'ASIA', 'LONDON'])

print(f"\nTotal trades: {len(tdf)}")
print(f"\n{'='*80}")
print("1. WIN RATE BY SESSION + DIRECTION")
print(f"{'='*80}")
for sess in tdf['session'].unique():
    for d in ['LONG', 'SHORT']:
        sub = tdf[(tdf['session']==sess) & (tdf['direction']==d)]
        if len(sub) == 0: continue
        wr = sub['win'].mean()*100
        avg_r = sub['r_mult'].mean()
        net = sub['pnl'].sum()
        print(f"  {sess:<12} {d:<5} n={len(sub):>4}  WR={wr:>5.1f}%  AvgR={avg_r:>+.3f}  Net=${net:>+.0f}")

print(f"\n{'='*80}")
print("2. LOSERS ANALYSIS: WHY DO TRADES FAIL?")
print(f"{'='*80}")
losers = tdf[~tdf['win']]
winners = tdf[tdf['win']]
print(f"\n  Winners: n={len(winners)}, avg R={winners['r_mult'].mean():.3f}, avg ADX={winners['adx'].mean():.1f}")
print(f"  Losers:  n={len(losers)}, avg R={losers['r_mult'].mean():.3f}, avg ADX={losers['adx'].mean():.1f}")

print(f"\n  {'Metric':<25} {'Winners':>10} {'Losers':>10} {'Diff':>10}")
print(f"  {'-'*55}")
for metric in ['rsi', 'adx', 'bw', 'risk_pts', 'hour']:
    w_med = winners[metric].median()
    l_med = losers[metric].median()
    print(f"  {metric:<25} {w_med:>10.2f} {l_med:>10.2f} {l_med-w_med:>+10.2f}")

print(f"\n{'='*80}")
print("3. STOPPED OUT vs TP1 HIT (exit quality)")
print(f"{'='*80}")
for sess in tdf['session'].unique():
    sub = tdf[tdf['session']==sess]
    stopped = sub['stopped'].sum()
    t1_only = (sub['t1_hit'] & ~sub['t2_hit'] & ~sub['stopped']).sum()
    t2_hit = sub['t2_hit'].sum()
    eod = (~sub['t1_hit'] & ~sub['stopped'] & ~sub['t2_hit']).sum()
    print(f"  {sess:<12} stopped={stopped:>4}  TP1_only={t1_only:>4}  TP2_hit={t2_hit:>4}  EOD={eod:>4}")

print(f"\n{'='*80}")
print("4. LONG vs SHORT BY SESSION (directional bias)")
print(f"{'='*80}")
for sess in tdf['session'].unique():
    sub = tdf[tdf['session']==sess]
    longs = sub[sub['direction']=='LONG']
    shorts = sub[sub['direction']=='SHORT']
    if len(longs) > 0:
        print(f"  {sess:<12} LONG  n={len(longs):>4} WR={longs['win'].mean()*100:>5.1f}% Net=${longs['pnl'].sum():>+.0f}")
    if len(shorts) > 0:
        print(f"  {sess:<12} SHORT n={len(shorts):>4} WR={shorts['win'].mean()*100:>5.1f}% Net=${shorts['pnl'].sum():>+.0f}")

print(f"\n{'='*80}")
print("5. TIME OF DAY ANALYSIS (hour of entry)")
print(f"{'='*80}")
hourly = tdf.groupby('hour').agg(
    n=('pnl','count'), wr=('win','mean'), net=('pnl','sum'), avg_r=('r_mult','mean')
).reset_index()
for _, r in hourly.iterrows():
    print(f"  {int(r['hour']):>2}:00  n={int(r['n']):>4}  WR={r['wr']*100:>5.1f}%  Net=${r['net']:>+.0f}  AvgR={r['avg_r']:>+.3f}")

print(f"\n{'='*80}")
print("6. BANDWIDTH REGIME (squeeze vs wide)")
print(f"{'='*80}")
for sess in tdf['session'].unique():
    sub = tdf[tdf['session']==sess]
    if len(sub) == 0: continue
    med_bw = sub['bw'].median()
    narrow = sub[sub['bw'] < med_bw]
    wide = sub[sub['bw'] >= med_bw]
    if len(narrow) > 0 and len(wide) > 0:
        print(f"  {sess:<12} narrow(bw<{med_bw:.3f}): n={len(narrow):>4} WR={narrow['win'].mean()*100:>5.1f}% PF={narrow[narrow['pnl']>0]['pnl'].sum()/abs(narrow[narrow['pnl']<0]['pnl'].sum()) if narrow[narrow['pnl']<0]['pnl'].sum()!=0 else 999:.2f}")
        print(f"  {'':<12} wide  (bw>={med_bw:.3f}): n={len(wide):>4} WR={wide['win'].mean()*100:>5.1f}% PF={wide[wide['pnl']>0]['pnl'].sum()/abs(wide[wide['pnl']<0]['pnl'].sum()) if wide[wide['pnl']<0]['pnl'].sum()!=0 else 999:.2f}")

print(f"\n{'='*80}")
print("7. RSI DEPTH AT ENTRY (how extreme?)")
print(f"{'='*80}")
for sess in tdf['session'].unique():
    sub = tdf[tdf['session']==sess]
    if len(sub) == 0: continue
    longs = sub[sub['direction']=='LONG']
    shorts = sub[sub['direction']=='SHORT']
    if len(longs) > 0:
        print(f"  {sess:<12} LONG  RSI: med={longs['rsi'].median():.1f} (winners={longs[longs['win']]['rsi'].median():.1f}, losers={longs[~longs['win']]['rsi'].median():.1f})")
    if len(shorts) > 0:
        print(f"  {sess:<12} SHORT RSI: med={shorts['rsi'].median():.1f} (winners={shorts[shorts['win']]['rsi'].median():.1f}, losers={shorts[~shorts['win']]['rsi'].median():.1f})")