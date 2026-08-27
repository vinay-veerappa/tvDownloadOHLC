"""Three-archetype strategy comparison: Trend vs Mean Revert vs Scalping.

Each archetype has its own risk model, return profile, and is measured with
MAE (Maximum Adverse Excursion) and MFE (Maximum Favourable Excursion).

All strategies use mandatory micros (MES $5/pt), $0 commission/slippage.

ARCHETYPES:
  1. TREND    — Supertrend(14,2) trail 1.0xATR, 1 trade/session, EOD exit
                Stop: 2xATR, Target: runner (trail), R:R variable (1:2+)
                Sessions: all (trend works overnight + RTH)

  2. MEANREVERT — BB(20,2) + RSI + ADX gate, HTF level required, no sweep
                  TP1=BB mid (50%), TP2=opposite band (runner, BE after TP1)
                  Stop: band + 1.5xATR, R:R ~1:1.5
                  Sessions: NY_PM only (mean reversion regime)

  3. SCALPING  — Quick entries on 5m BB touch + 1m confirmation
                  TP=8 ticks ($20), Stop=12 ticks ($30), R:R 1:0.67
                  High win rate target (>65%), very short hold (<15min)
                  Sessions: NY_AM + NY_MIDDAY (high volume, tight ranges)
"""
import sys, pandas as pd, numpy as np
from dataclasses import dataclass
from typing import Optional, List
sys.path.insert(0, '.')
from scripts.analysis.range_strategy_comparison import (
    build_day_context, _wilder_rsi, _adx
)
from scripts.utils.fused_data_loader import load_fused_data

# ─── Data ──────────────────────────────────────────────────────────────────

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

# Load HTF levels
htf_df = pd.read_parquet('data/derived/ICT/ES1_htf_levels.parquet')
htf_df['trading_date'] = pd.to_datetime(htf_df['trading_date'])

POINT_VAL = 5.0  # 1x MES (mandatory micro)


@dataclass
class TradeRecord:
    archetype: str
    session: str
    date: str
    direction: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    stop_price: float
    pnl: float
    r_mult: float
    mae: float  # max adverse excursion in points
    mfe: float  # max favourable excursion in points
    hold_bars: int
    exit_reason: str


def compute_mae_mfe(entry_time, exit_time, direction, entry_price, session_bars_1m):
    """Compute MAE (worst excursion against) and MFE (best excursion for) in points."""
    bars = session_bars_1m.loc[entry_time:exit_time]
    if len(bars) == 0:
        return 0.0, 0.0
    if direction == 'LONG':
        mae = entry_price - bars['low'].min()  # how far below entry
        mfe = bars['high'].max() - entry_price  # how far above entry
    else:
        mae = bars['high'].max() - entry_price  # how far above entry (short)
        mfe = entry_price - bars['low'].min()  # how far below entry (short)
    return max(mae, 0), max(mfe, 0)


# ─── 1. TREND: Supertrend ──────────────────────────────────────────────────

def supertrend(high, low, close, period, mult):
    atr = (high.rolling(period).max() - low.rolling(period).min()) / period
    mid = (high + low) / 2
    fu = mid + mult * atr
    fl = mid - mult * atr
    st = pd.Series(0, index=close.index, dtype=float)
    for i in range(1, len(close)):
        if close.iloc[i] > fu.iloc[i-1]: st.iloc[i] = 1
        elif close.iloc[i] < fl.iloc[i-1]: st.iloc[i] = -1
        else: st.iloc[i] = st.iloc[i-1]
    return st

def run_trend(ctx, session_name, after_time=None):
    """Supertrend trend-following. Trail 1.0xATR, EOD exit."""
    bars_5m = ctx.session_5m.get(session_name)
    bars_1m = ctx.session_bars.get(session_name)
    if bars_5m is None or len(bars_5m) < 20:
        return None
    if bars_1m is None:
        return None

    high, low, close = bars_5m['high'], bars_5m['low'], bars_5m['close']
    st = supertrend(high, low, close, 14, 2.0)
    atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14

    for i in range(1, len(bars_5m)):
        curr_time = bars_5m.index[i]
        if after_time and curr_time <= after_time:
            continue
        st0, st1 = st.iloc[i], st.iloc[i-1]
        if pd.isna(st0) or pd.isna(st1): continue
        a5 = atr5.iloc[i]
        if np.isnan(a5) or a5 <= 0: continue

        if st0 == 1 and st1 == -1:
            entry = float(close.iloc[i])
            stop = entry - 2.0 * a5
            if stop >= entry: continue
            direction = 'LONG'
        elif st0 == -1 and st1 == 1:
            entry = float(close.iloc[i])
            stop = entry + 2.0 * a5
            if stop <= entry: continue
            direction = 'SHORT'
        else:
            continue

        # Simulate trade on 1m bars
        sim = bars_1m.loc[curr_time + pd.Timedelta(minutes=5):]
        if len(sim) == 0: return None

        risk = abs(entry - stop)
        trail_stop = stop
        exit_price = None
        exit_time = None
        exit_reason = None
        mae, mfe = 0.0, 0.0
        hold_bars = 0

        for j, (t_bar, row) in enumerate(sim.iterrows()):
            hold_bars += 1
            if direction == 'LONG':
                mae = max(mae, entry - row['low'])
                mfe = max(mfe, row['high'] - entry)
                new_trail = row['high'] - 1.0 * a5
                if new_trail > trail_stop and j > 0:
                    trail_stop = new_trail
                if row['low'] <= trail_stop:
                    exit_price = trail_stop
                    exit_time = t_bar
                    exit_reason = 'trail'
                    break
            else:
                mae = max(mae, row['high'] - entry)
                mfe = max(mfe, entry - row['low'])
                new_trail = row['low'] + 1.0 * a5
                if new_trail < trail_stop and j > 0:
                    trail_stop = new_trail
                if row['high'] >= trail_stop:
                    exit_price = trail_stop
                    exit_time = t_bar
                    exit_reason = 'trail'
                    break

        if exit_price is None:
            exit_price = float(sim['close'].iloc[-1])
            exit_time = sim.index[-1]
            exit_reason = 'EOD'

        pnl = (exit_price - entry) * POINT_VAL if direction == 'LONG' else (entry - exit_price) * POINT_VAL
        r_mult = (exit_price - entry) / risk if direction == 'LONG' else (entry - exit_price) / risk

        return TradeRecord('TREND', session_name, str(ctx.trade_date.date()),
                          direction, curr_time, entry, exit_time, exit_price, stop,
                          pnl, r_mult, mae, mfe, hold_bars, exit_reason)
    return None


# ─── 2. MEAN REVERT: BB + HTF ──────────────────────────────────────────────

def run_meanrevert(ctx, session_name, htf_row, after_time=None):
    """BB mean reversion with HTF level requirement. NY_PM only."""
    if session_name != 'NY_PM':
        return None

    bars_5m = ctx.session_5m.get(session_name)
    bars_1m = ctx.session_bars.get(session_name)
    if bars_5m is None or len(bars_5m) < 30:
        return None
    if bars_1m is None:
        return None

    close, high, low = bars_5m['close'], bars_5m['high'], bars_5m['low']
    sma = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = sma + 2.0 * std
    lower = sma - 2.0 * std
    rsi = _wilder_rsi(close, 14)
    adx_s = _adx(high, low, close, 14)

    pdh = htf_row['pdh'] if htf_row is not None else np.nan
    pdl = htf_row['pdl'] if htf_row is not None else np.nan

    for i in range(2, len(bars_5m)):
        curr_time = bars_5m.index[i]
        if after_time and curr_time <= after_time:
            continue
        adx_val = adx_s.iloc[i]
        if not np.isnan(adx_val) and adx_val >= 25:
            continue

        # SHORT: prior bar above upper + RSI>67, now closes back inside, near PDH
        short_setup = (
            close.iloc[i-1] > upper.iloc[i-1] and rsi.iloc[i-1] > 67
            and close.iloc[i] < upper.iloc[i] and rsi.iloc[i] < rsi.iloc[i-1]
            and close.iloc[i] > sma.iloc[i] and rsi.iloc[i] > 50
        )
        if short_setup:
            entry = float(close.iloc[i])
            # Require near PDH (within 10 pts)
            if not np.isnan(pdh) and abs(entry - pdh) > 10:
                continue
            atr_5m = float((high.rolling(14).max() - low.rolling(14).min()).iloc[i] / 14)
            if np.isnan(atr_5m) or atr_5m <= 0: atr_5m = 2.0
            sl = float(max(upper.iloc[i], close.iloc[i]) + 1.5 * atr_5m)
            sl = max(sl, entry + 1.0 * atr_5m)
            risk = sl - entry
            if risk <= 0: continue
            tp1 = float(sma.iloc[i])
            tp2 = float(lower.iloc[i])
            if tp1 >= entry: continue
            return _simulate_two_leg(ctx, bars_1m, curr_time, 'SHORT', entry, sl, tp1, tp2, risk, session_name)

        # LONG: prior bar below lower + RSI<33, now closes back inside, near PDL
        long_setup = (
            close.iloc[i-1] < lower.iloc[i-1] and rsi.iloc[i-1] < 33
            and close.iloc[i] > lower.iloc[i] and rsi.iloc[i] > rsi.iloc[i-1]
            and close.iloc[i] < sma.iloc[i] and rsi.iloc[i] < 50
        )
        if long_setup:
            entry = float(close.iloc[i])
            if not np.isnan(pdl) and abs(entry - pdl) > 10:
                continue
            atr_5m = float((high.rolling(14).max() - low.rolling(14).min()).iloc[i] / 14)
            if np.isnan(atr_5m) or atr_5m <= 0: atr_5m = 2.0
            sl = float(min(lower.iloc[i], close.iloc[i]) - 1.5 * atr_5m)
            sl = min(sl, entry - 1.0 * atr_5m)
            risk = entry - sl
            if risk <= 0: continue
            tp1 = float(sma.iloc[i])
            tp2 = float(upper.iloc[i])
            if tp1 <= entry: continue
            return _simulate_two_leg(ctx, bars_1m, curr_time, 'LONG', entry, sl, tp1, tp2, risk, session_name)
    return None


def _simulate_two_leg(ctx, bars_1m, signal_time, direction, entry, sl, tp1, tp2, risk, session_name):
    """Simulate 2-leg trade: TP1 at middle band, TP2 at opposite band, BE after TP1."""
    sim = bars_1m.loc[signal_time + pd.Timedelta(minutes=5):]
    if len(sim) == 0: return None

    is_long = direction == 'LONG'
    leg1_pnl, leg2_pnl = 0.0, 0.0
    t1_hit = False
    t2_hit = False
    stopped = False
    exit_time = None
    exit_price = None
    exit_reason = None
    mae, mfe = 0.0, 0.0
    hold_bars = 0

    for t_bar, row in sim.iterrows():
        hold_bars += 1
        if is_long:
            mae = max(mae, entry - row['low'])
            mfe = max(mfe, row['high'] - entry)
        else:
            mae = max(mae, row['high'] - entry)
            mfe = max(mfe, entry - row['low'])

        if not t1_hit:
            if is_long and row['low'] <= sl:
                leg1_pnl = sl - entry
                leg2_pnl = sl - entry
                stopped = True
                exit_time, exit_price, exit_reason = t_bar, sl, 'stop'
                break
            elif not is_long and row['high'] >= sl:
                leg1_pnl = entry - sl
                leg2_pnl = entry - sl
                stopped = True
                exit_time, exit_price, exit_reason = t_bar, sl, 'stop'
                break
            if is_long and row['high'] >= tp1:
                t1_hit = True
                leg1_pnl = tp1 - entry
                sl = entry  # BE
            elif not is_long and row['low'] <= tp1:
                t1_hit = True
                leg1_pnl = entry - tp1
                sl = entry  # BE
        else:
            if is_long and row['low'] <= sl:
                leg2_pnl = sl - entry
                exit_time, exit_price, exit_reason = t_bar, sl, 'BE' if sl == entry else 'stop'
                break
            elif not is_long and row['high'] >= sl:
                leg2_pnl = entry - sl
                exit_time, exit_price, exit_reason = t_bar, sl, 'BE' if sl == entry else 'stop'
                break
            if is_long and row['high'] >= tp2:
                t2_hit = True
                leg2_pnl = tp2 - entry
                exit_time, exit_price, exit_reason = t_bar, tp2, 'TP2'
                break
            elif not is_long and row['low'] <= tp2:
                t2_hit = True
                leg2_pnl = entry - tp2
                exit_time, exit_price, exit_reason = t_bar, tp2, 'TP2'
                break

    if exit_time is None:
        exit_price = float(sim['close'].iloc[-1])
        exit_time = sim.index[-1]
        if not t1_hit:
            leg1_pnl = (exit_price - entry) if is_long else (entry - exit_price)
        leg2_pnl = (exit_price - entry) if is_long else (entry - exit_price)
        exit_reason = 'EOD'

    total_pts = leg1_pnl + leg2_pnl
    pnl = total_pts * POINT_VAL
    r_mult = total_pts / (2 * risk) if risk > 0 else 0

    return TradeRecord('MEANREVERT', session_name, str(ctx.trade_date.date()),
                      direction, signal_time, entry, exit_time, exit_price, sl,
                      pnl, r_mult, mae, mfe, hold_bars, exit_reason)


# ─── 3. SCALPING: Quick BB touch + 1m confirmation ────────────────────────

def run_scalp(ctx, session_name, after_time=None):
    """Scalping: 5m BB touch + 1m RSI confirmation. TP=8 ticks, Stop=12 ticks.
    Target high win rate, very short hold. NY_AM + NY_MIDDAY only.
    Uses BB(10) to fit in short session windows.
    """
    if session_name not in ('NY_AM', 'NY_MIDDAY', 'NY_PM'):
        return None

    bars_5m = ctx.session_5m.get(session_name)
    bars_1m = ctx.session_bars.get(session_name)
    if bars_5m is None or len(bars_5m) < 15:
        return None
    if bars_1m is None:
        return None

    close, high, low = bars_5m['close'], bars_5m['high'], bars_5m['low']
    sma = close.rolling(10).mean()
    std = close.rolling(10).std()
    upper = sma + 1.5 * std  # tighter bands for more touches
    lower = sma - 1.5 * std
    rsi = _wilder_rsi(close, 7)  # faster RSI

    TP_TICKS = 8 * 0.25   # 2.0 points = $10 per MES
    SL_TICKS = 12 * 0.25  # 3.0 points = $15 per MES

    for i in range(2, len(bars_5m)):
        curr_time = bars_5m.index[i]
        if after_time and curr_time <= after_time:
            continue

        # Short scalp: close tags upper band, RSI > 70
        if close.iloc[i] > upper.iloc[i] and rsi.iloc[i] > 70:
            entry = float(close.iloc[i])
            sl = entry + SL_TICKS
            tp = entry - TP_TICKS
            risk = sl - entry
            if risk <= 0: continue

            sim = bars_1m.loc[curr_time + pd.Timedelta(minutes=5):]
            if len(sim) == 0: continue

            exit_price, exit_time, exit_reason = None, None, None
            mae, mfe, hold_bars = 0.0, 0.0, 0
            for t_bar, row in sim.iterrows():
                hold_bars += 1
                mae = max(mae, row['high'] - entry)
                mfe = max(mfe, entry - row['low'])
                if row['high'] >= sl:
                    exit_price, exit_time, exit_reason = sl, t_bar, 'stop'
                    break
                if row['low'] <= tp:
                    exit_price, exit_time, exit_reason = tp, t_bar, 'TP'
                    break
            if exit_price is None:
                exit_price = float(sim['close'].iloc[-1])
                exit_time = sim.index[-1]
                exit_reason = 'EOD'
            pnl = (entry - exit_price) * POINT_VAL
            r_mult = (entry - exit_price) / risk
            return TradeRecord('SCALP', session_name, str(ctx.trade_date.date()),
                              'SHORT', curr_time, entry, exit_time, exit_price, sl,
                              pnl, r_mult, mae, mfe, hold_bars, exit_reason)

        # Long scalp: close tags lower band, RSI < 30
        if close.iloc[i] < lower.iloc[i] and rsi.iloc[i] < 30:
            entry = float(close.iloc[i])
            sl = entry - SL_TICKS
            tp = entry + TP_TICKS
            risk = entry - sl
            if risk <= 0: continue

            sim = bars_1m.loc[curr_time + pd.Timedelta(minutes=5):]
            if len(sim) == 0: continue

            exit_price, exit_time, exit_reason = None, None, None
            mae, mfe, hold_bars = 0.0, 0.0, 0
            for t_bar, row in sim.iterrows():
                hold_bars += 1
                mae = max(mae, entry - row['low'])
                mfe = max(mfe, row['high'] - entry)
                if row['low'] <= sl:
                    exit_price, exit_time, exit_reason = sl, t_bar, 'stop'
                    break
                if row['high'] >= tp:
                    exit_price, exit_time, exit_reason = tp, t_bar, 'TP'
                    break
            if exit_price is None:
                exit_price = float(sim['close'].iloc[-1])
                exit_time = sim.index[-1]
                exit_reason = 'EOD'
            pnl = (exit_price - entry) * POINT_VAL
            r_mult = (exit_price - entry) / risk
            return TradeRecord('SCALP', session_name, str(ctx.trade_date.date()),
                              'LONG', curr_time, entry, exit_time, exit_price, sl,
                              pnl, r_mult, mae, mfe, hold_bars, exit_reason)
    return None


# ─── Run all three archetypes ──────────────────────────────────────────────

trend_sessions = ['GLOBEX', 'ASIA', 'LONDON', 'NY_AM', 'NY_MIDDAY', 'NY_PM']
meanrevert_sessions = ['NY_PM']
scalp_sessions = ['NY_AM', 'NY_MIDDAY', 'NY_PM']

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

    htf_row = htf_df[htf_df['trading_date'] == ts]
    htf_row = htf_row.iloc[0] if len(htf_row) > 0 else None

    # Trend — all sessions, 1 trade per session
    for sess in trend_sessions:
        trade = run_trend(ctx, sess)
        if trade:
            all_trades.append(trade)

    # Mean revert — NY_PM only, 1 trade
    trade = run_meanrevert(ctx, 'NY_PM', htf_row)
    if trade:
        all_trades.append(trade)

    # Scalping — NY_AM + NY_MIDDAY, 1 trade per session
    for sess in scalp_sessions:
        trade = run_scalp(ctx, sess)
        if trade:
            all_trades.append(trade)

tdf = pd.DataFrame(all_trades)
print(f"\nTotal trades: {len(tdf)}")

# ─── Report ────────────────────────────────────────────────────────────────

for arch in ['TREND', 'MEANREVERT', 'SCALP']:
    sub = tdf[tdf['archetype'] == arch]
    if len(sub) == 0:
        print(f"\n{arch}: No trades")
        continue
    wins = sub[sub['pnl'] > 0]
    losses = sub[sub['pnl'] < 0]
    wr = len(wins)/len(sub)*100
    pf = wins['pnl'].sum() / abs(losses['pnl'].sum()) if losses['pnl'].sum() != 0 else 999
    net = sub['pnl'].sum()
    avg_r = sub['r_mult'].mean()
    avg_mae = sub['mae'].mean()
    avg_mfe = sub['mfe'].mean()
    avg_hold = sub['hold_bars'].mean()
    med_hold = sub['hold_bars'].median()

    print(f"\n{'='*70}")
    print(f"{arch}")
    print(f"{'='*70}")
    print(f"  Trades: {len(sub)}")
    print(f"  WR:     {wr:.1f}%")
    print(f"  PF:     {pf:.2f}")
    print(f"  Net:    ${net:+.0f}")
    print(f"  AvgR:   {avg_r:+.3f}")
    print(f"  MAE:    {avg_mae:.2f} pts (avg)  p25={sub['mae'].quantile(.25):.2f}  p50={sub['mae'].median():.2f}  p75={sub['mae'].quantile(.75):.2f}")
    print(f"  MFE:    {avg_mfe:.2f} pts (avg)  p25={sub['mfe'].quantile(.25):.2f}  p50={sub['mfe'].median():.2f}  p75={sub['mfe'].quantile(.75):.2f}")
    print(f"  Hold:   {avg_hold:.0f} bars avg ({med_hold:.0f} median) = {avg_hold*5:.0f}min avg")
    print(f"  Exit:   {sub['exit_reason'].value_counts().to_dict()}")

    # Per session
    print(f"  Per session:")
    for sess in sub['session'].unique():
        ss = sub[sub['session'] == sess]
        sw = ss[ss['pnl']>0]
        sl = ss[ss['pnl']<0]
        wr_s = len(sw)/len(ss)*100
        pf_s = sw['pnl'].sum()/abs(sl['pnl'].sum()) if sl['pnl'].sum() != 0 else 999
        print(f"    {sess:<12} n={len(ss):>4} WR={wr_s:>5.1f}% PF={pf_s:.2f} Net=${ss['pnl'].sum():>+.0f} AvgR={ss['r_mult'].mean():>+.3f}")

    # Direction
    for d in ['LONG', 'SHORT']:
        ss = sub[sub['direction'] == d]
        if len(ss) == 0: continue
        sw = ss[ss['pnl']>0]
        wr_s = len(sw)/len(ss)*100
        pf_s = sw['pnl'].sum()/abs(ss[ss['pnl']<0]['pnl'].sum()) if ss[ss['pnl']<0]['pnl'].sum() != 0 else 999
        print(f"    {d:<12} n={len(ss):>4} WR={wr_s:>5.1f}% PF={pf_s:.2f} Net=${ss['pnl'].sum():>+.0f} AvgR={ss['r_mult'].mean():>+.3f}")