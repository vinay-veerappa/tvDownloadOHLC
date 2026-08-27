"""Cross-reference BB trades with ICT features to find filtering confluences.

For each BB trade, check at entry time:
1. Was there a nearby FVG (within 5 pts)? Did it support or resist the trade?
2. Was entry near a PDH/PDL/PWH/PWL? (entering into HTF resistance = bad)
3. Was there a recent liquidity sweep? (entering after sweep = good for fade)
4. Was entry aligned with HTF bias? (price below PDL = bad for SHORT)
"""
import sys, pandas as pd, numpy as np
sys.path.insert(0, '.')
from scripts.analysis.range_strategy_comparison import (
    BBRsiMeanReversionStrategy, build_day_context, BacktestEngine
)
from scripts.utils.fused_data_loader import load_fused_data

# Load ICT features and normalize to ET-naive
fvg_df = pd.read_parquet('data/derived/ICT/ES1_imbalance_5m.parquet')
fvg_df.index = fvg_df.index.tz_localize('UTC').tz_convert('America/New_York').tz_localize(None)

liq_df = pd.read_parquet('data/derived/ICT/ES1_liquidity_5m.parquet')
liq_df.index = liq_df.index.tz_localize('UTC').tz_convert('America/New_York').tz_localize(None)

htf_df = pd.read_parquet('data/derived/ICT/ES1_htf_levels.parquet')
htf_df['trading_date'] = pd.to_datetime(htf_df['trading_date'])

# Load price data
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

# Collect trades with ICT context
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

    # Get HTF levels for this date
    htf_row = htf_df[htf_df['trading_date'] == ts]
    pdh = htf_row['pdh'].values[0] if len(htf_row) > 0 and not pd.isna(htf_row['pdh'].values[0]) else np.nan
    pdl = htf_row['pdl'].values[0] if len(htf_row) > 0 and not pd.isna(htf_row['pdl'].values[0]) else np.nan
    pwh = htf_row['pwh'].values[0] if len(htf_row) > 0 and not pd.isna(htf_row['pwh'].values[0]) else np.nan
    pwl = htf_row['pwl'].values[0] if len(htf_row) > 0 and not pd.isna(htf_row['pwl'].values[0]) else np.nan

    for sess in strat.get_active_sessions():
        after_time = None
        for trade_num in range(3):
            sig = strat.detect_signal(ctx, sess, after_time=after_time)
            if sig is None:
                break
            trade = engine.simulate_trade(sig, ctx)
            if trade is None:
                break

            entry = trade.entry_price
            entry_t = trade.entry_time
            is_long = trade.direction == 'LONG'

            # Check FVG near entry (within 5 pts)
            fvg_near = fvg_df.loc[entry_t - pd.Timedelta(minutes=30):entry_t]
            bullish_fvg = fvg_near[fvg_near['fvg_type'] == 1]
            bearish_fvg = fvg_near[fvg_near['fvg_type'] == -1]
            has_bull_fvg = len(bullish_fvg) > 0
            has_bear_fvg = len(bearish_fvg) > 0
            fvg_aligned = (is_long and has_bull_fvg) or (not is_long and has_bear_fvg)
            fvg_against = (is_long and has_bear_fvg) or (not is_long and has_bull_fvg)

            # Check HTF level proximity (within 10 pts)
            near_pdh = abs(entry - pdh) < 10 if not np.isnan(pdh) else False
            near_pdl = abs(entry - pdl) < 10 if not np.isnan(pdl) else False
            near_pwh = abs(entry - pwh) < 10 if not np.isnan(pwh) else False
            near_pwl = abs(entry - pwl) < 10 if not np.isnan(pwl) else False

            # LONG near PDH/PWH = entering into resistance (bad)
            # SHORT near PDL/PWL = entering into support (bad)
            htf_against = (is_long and (near_pdh or near_pwh)) or (not is_long and (near_pdl or near_pwl))
            htf_aligned = (is_long and (near_pdl or near_pwl)) or (not is_long and (near_pdh or near_pwh))

            # Check recent liquidity sweep (within 1h before entry)
            liq_recent = liq_df.loc[entry_t - pd.Timedelta(hours=1):entry_t]
            bsl_sweep = len(liq_recent[liq_recent['liq_kind'] == 'BSL']) > 0 if 'liq_kind' in liq_recent.columns else False
            ssl_sweep = len(liq_recent[liq_recent['liq_kind'] == 'SSL']) > 0 if 'liq_kind' in liq_recent.columns else False
            # BSL swept before SHORT = selling after buy-side liquidity taken (good for fade)
            # SSL swept before LONG = buying after sell-side liquidity taken (good for fade)
            sweep_aligned = (is_long and ssl_sweep) or (not is_long and bsl_sweep)

            all_trades.append({
                'session': sess,
                'direction': trade.direction,
                'pnl': trade.total_pnl_dollars,
                'r_mult': trade.r_multiple,
                'win': trade.total_pnl_dollars > 0,
                'entry_price': entry,
                'rsi': sig.metadata.get('rsi', np.nan),
                'adx': sig.metadata.get('adx', np.nan),
                'fvg_aligned': fvg_aligned,
                'fvg_against': fvg_against,
                'htf_against': htf_against,
                'htf_aligned': htf_aligned,
                'sweep_aligned': sweep_aligned,
                'near_pdh': near_pdh,
                'near_pdl': near_pdl,
                'near_pwh': near_pwh,
                'near_pwl': near_pwl,
            })
            after_time = trade.exit_time

tdf = pd.DataFrame(all_trades)
print(f"\nTotal trades: {len(tdf)}")

print(f"\n{'='*80}")
print("A. FVG CONFLUENCE: Does FVG alignment help?")
print(f"{'='*80}")
for label, mask in [('FVG aligned', tdf['fvg_aligned']), ('FVG against', tdf['fvg_against']), ('No FVG', ~tdf['fvg_aligned'] & ~tdf['fvg_against'])]:
    sub = tdf[mask]
    if len(sub) == 0: continue
    wr = sub['win'].mean()*100
    pf = sub[sub['pnl']>0]['pnl'].sum() / abs(sub[sub['pnl']<0]['pnl'].sum()) if sub[sub['pnl']<0]['pnl'].sum() != 0 else 999
    net = sub['pnl'].sum()
    print(f"  {label:<15} n={len(sub):>4}  WR={wr:>5.1f}%  PF={pf:.2f}  Net=${net:>+.0f}")

print(f"\n{'='*80}")
print("B. HTF LEVEL CONFLUENCE: Does entering near HTF levels hurt/help?")
print(f"{'='*80}")
for label, mask in [('HTF against', tdf['htf_against']), ('HTF aligned', tdf['htf_aligned']), ('No HTF near', ~tdf['htf_against'] & ~tdf['htf_aligned'])]:
    sub = tdf[mask]
    if len(sub) == 0: continue
    wr = sub['win'].mean()*100
    pf = sub[sub['pnl']>0]['pnl'].sum() / abs(sub[sub['pnl']<0]['pnl'].sum()) if sub[sub['pnl']<0]['pnl'].sum() != 0 else 999
    net = sub['pnl'].sum()
    print(f"  {label:<15} n={len(sub):>4}  WR={wr:>5.1f}%  PF={pf:.2f}  Net=${net:>+.0f}")

print(f"\n{'='*80}")
print("C. LIQUIDITY SWEEP CONFLUENCE")
print(f"{'='*80}")
for label, mask in [('Sweep aligned', tdf['sweep_aligned']), ('No sweep', ~tdf['sweep_aligned'])]:
    sub = tdf[mask]
    if len(sub) == 0: continue
    wr = sub['win'].mean()*100
    pf = sub[sub['pnl']>0]['pnl'].sum() / abs(sub[sub['pnl']<0]['pnl'].sum()) if sub[sub['pnl']<0]['pnl'].sum() != 0 else 999
    net = sub['pnl'].sum()
    print(f"  {label:<15} n={len(sub):>4}  WR={wr:>5.1f}%  PF={pf:.2f}  Net=${net:>+.0f}")

print(f"\n{'='*80}")
print("D. COMBINED: FVG aligned + NOT HTF against")
print(f"{'='*80}")
combined = tdf[tdf['fvg_aligned'] & ~tdf['htf_against']]
rest = tdf[~(tdf['fvg_aligned'] & ~tdf['htf_against'])]
for label, sub in [('Combined filter', combined), ('Rest', rest)]:
    if len(sub) == 0: continue
    wr = sub['win'].mean()*100
    pf = sub[sub['pnl']>0]['pnl'].sum() / abs(sub[sub['pnl']<0]['pnl'].sum()) if sub[sub['pnl']<0]['pnl'].sum() != 0 else 999
    net = sub['pnl'].sum()
    print(f"  {label:<15} n={len(sub):>4}  WR={wr:>5.1f}%  PF={pf:.2f}  Net=${net:>+.0f}")

print(f"\n{'='*80}")
print("E. SHORT-ONLY + HTF not against")
print(f"{'='*80}")
short_filter = tdf[(tdf['direction']=='SHORT') & ~tdf['htf_against']]
long_filter = tdf[(tdf['direction']=='LONG') & ~tdf['htf_against']]
for label, sub in [('SHORT + no HTF against', short_filter), ('LONG + no HTF against', long_filter)]:
    if len(sub) == 0: continue
    wr = sub['win'].mean()*100
    pf = sub[sub['pnl']>0]['pnl'].sum() / abs(sub[sub['pnl']<0]['pnl'].sum()) if sub[sub['pnl']<0]['pnl'].sum() != 0 else 999
    net = sub['pnl'].sum()
    print(f"  {label:<25} n={len(sub):>4}  WR={wr:>5.1f}%  PF={pf:.2f}  Net=${net:>+.0f}")