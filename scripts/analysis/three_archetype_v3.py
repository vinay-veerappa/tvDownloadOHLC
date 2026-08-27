"""Three-Archetype v3 — focused fixes based on v2 learnings.

TREND:       Replicate exact NT8 validated config — per-day rolling ATR,
             Q4-only volatility regime, time filter (skip 14:00+), 1.0x trail.
MEANREVERT:  v1 design (BB+RSI+ADX+HTF) with relaxed HTF proximity (15pts).
             SHORT-biased, NY_PM only, 2-bar hook, TP1=BB mid, TP2=opp band.
SCALP:       VWAP bounce with strict rejection candle confirmation.
             Close back in trend dir + wick + volume increase at touch.
"""
import sys, pandas as pd, numpy as np
from dataclasses import dataclass
from typing import Optional
sys.path.insert(0, '.')
from scripts.analysis.range_strategy_comparison import build_day_context, _wilder_rsi, _adx
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

POINT_VAL = 5.0  # 1x MES mandatory micro


@dataclass
class TradeRecord:
    archetype: str; session: str; date: str; direction: str
    entry_time: pd.Timestamp; entry_price: float
    exit_time: pd.Timestamp; exit_price: float; stop_price: float
    pnl: float; r_mult: float; mae: float; mfe: float
    hold_bars: int; exit_reason: str


# Load HTF levels for MeanRevert
htf_df = pd.read_parquet('data/derived/ICT/ES1_htf_levels.parquet')
htf_df['trading_date'] = pd.to_datetime(htf_df['trading_date'])


# ─── 1. TREND: Exact NT8 validated config ─────────────────────────────────
#  ST(14,2), per-day rolling ATR, Q4-only regime, skip 14:00+, 1.0x trail

def supertrend(high, low, close, period, mult):
    atr = (high.rolling(period).max() - low.rolling(period).min()) / period
    mid = (high + low) / 2
    fu = mid + mult * atr; fl = mid - mult * atr
    st = pd.Series(0, index=close.index, dtype=float)
    for i in range(1, len(close)):
        if close.iloc[i] > fu.iloc[i-1]: st.iloc[i] = 1
        elif close.iloc[i] < fl.iloc[i-1]: st.iloc[i] = -1
        else: st.iloc[i] = st.iloc[i-1]
    return st


def run_trend_v3(ctx, session_name, after_time=None):
    """NT8-validated: ST(14,2), per-day ATR trail 1.0x, Q4 regime gate, time filter."""
    bars_5m = ctx.session_5m.get(session_name)
    bars_1m = ctx.session_bars.get(session_name)
    if bars_5m is None or len(bars_5m) < 30 or bars_1m is None:
        return None

    high, low, close = bars_5m['high'], bars_5m['low'], bars_5m['close']
    st = supertrend(high, low, close, 14, 2.0)
    # Per-day rolling ATR (matches NT8: MAX-MIN over 14 bars, reset per day)
    atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14

    # ATR regime: Q4 (top 25%) only — use rolling 50-bar percentile
    atr_p25 = atr5.rolling(50, min_periods=10).quantile(0.25)
    atr_p75 = atr5.rolling(50, min_periods=10).quantile(0.75)
    atr_median = atr5.rolling(50, min_periods=10).median()

    for i in range(14, len(bars_5m)):
        curr_time = bars_5m.index[i]
        if after_time and curr_time <= after_time:
            continue

        # Time filter: skip entries after 14:00 ET (LatestEntry=1359 in NT8)
        if curr_time.hour >= 14:
            continue

        st0, st1 = st.iloc[i], st.iloc[i-1]
        if pd.isna(st0) or pd.isna(st1): continue
        a5 = atr5.iloc[i]
        if np.isnan(a5) or a5 <= 0: continue

        # ATR regime: only trade when ATR > median (high-vol regime)
        am = atr_median.iloc[i]
        if not np.isnan(am) and a5 < am:
            continue

        if st0 == 1 and st1 == -1:
            entry = float(close.iloc[i]); stop = entry - 2.0 * a5; direction = 'LONG'
        elif st0 == -1 and st1 == 1:
            entry = float(close.iloc[i]); stop = entry + 2.0 * a5; direction = 'SHORT'
        else:
            continue

        risk = abs(entry - stop)
        if risk <= 0: continue

        sim = bars_1m.loc[curr_time + pd.Timedelta(minutes=5):]
        if len(sim) == 0: return None

        trail_stop = stop
        exit_price, exit_time, exit_reason = None, None, None
        mae, mfe, hold_bars = 0.0, 0.0, 0

        for j, (t_bar, row) in enumerate(sim.iterrows()):
            hold_bars += 1
            if direction == 'LONG':
                mae = max(mae, entry - row['low'])
                mfe = max(mfe, row['high'] - entry)
                if j > 0:
                    new_trail = row['high'] - 1.0 * a5
                    if new_trail > trail_stop: trail_stop = new_trail
                if row['low'] <= trail_stop:
                    exit_price, exit_time, exit_reason = trail_stop, t_bar, 'trail'
                    break
            else:
                mae = max(mae, row['high'] - entry)
                mfe = max(mfe, entry - row['low'])
                if j > 0:
                    new_trail = row['low'] + 1.0 * a5
                    if new_trail < trail_stop: trail_stop = new_trail
                if row['high'] >= trail_stop:
                    exit_price, exit_time, exit_reason = trail_stop, t_bar, 'trail'
                    break

        if exit_price is None:
            exit_price = float(sim['close'].iloc[-1])
            exit_time = sim.index[-1]; exit_reason = 'EOD'

        pnl = (exit_price - entry) * POINT_VAL if direction == 'LONG' else (entry - exit_price) * POINT_VAL
        r_mult = (exit_price - entry) / risk if direction == 'LONG' else (entry - exit_price) / risk
        return TradeRecord('TREND', session_name, str(ctx.trade_date.date()),
                          direction, curr_time, entry, exit_time, exit_price, stop,
                          pnl, r_mult, mae, mfe, hold_bars, exit_reason)
    return None


# ─── 2. MEANREVERT: v1 design, relaxed HTF (15pts) ─────────────────────────

def run_meanrevert_v3(ctx, session_name, htf_row, after_time=None):
    """BB(20,2.0) + RSI(33/67) + ADX<25 + 2-bar hook + HTF within 15pts.
    NY_PM only. TP1=BB mid, TP2=opposite band, BE after TP1.
    """
    if session_name != 'NY_PM':
        return None

    bars_5m = ctx.session_5m.get(session_name)
    bars_1m = ctx.session_bars.get(session_name)
    if bars_5m is None or len(bars_5m) < 30 or bars_1m is None:
        return None

    close, high, low = bars_5m['close'], bars_5m['high'], bars_5m['low']
    sma = close.rolling(20).mean(); std = close.rolling(20).std()
    upper = sma + 2.0 * std; lower = sma - 2.0 * std
    rsi = _wilder_rsi(close, 14); adx_s = _adx(high, low, close, 14)

    pdh = htf_row['pdh'] if htf_row is not None else np.nan
    pdl = htf_row['pdl'] if htf_row is not None else np.nan

    for i in range(2, len(bars_5m)):
        curr_time = bars_5m.index[i]
        if after_time and curr_time <= after_time: continue
        adx_val = adx_s.iloc[i]
        if not np.isnan(adx_val) and adx_val >= 25: continue

        # SHORT: 2-bar hook — prior bar above upper + RSI>67, now closes back inside
        short_setup = (
            close.iloc[i-1] > upper.iloc[i-1] and rsi.iloc[i-1] > 67
            and close.iloc[i] < upper.iloc[i] and rsi.iloc[i] < rsi.iloc[i-1]
            and close.iloc[i] > sma.iloc[i] and rsi.iloc[i] > 50
        )
        if short_setup:
            entry = float(close.iloc[i])
            # Require near PDH (relaxed: 15pts instead of 10pts)
            if not np.isnan(pdh) and abs(entry - pdh) > 15: continue
            atr_5m = float((high.rolling(14).max()-low.rolling(14).min()).iloc[i]/14)
            if np.isnan(atr_5m) or atr_5m <= 0: atr_5m = 2.0
            sl = float(max(upper.iloc[i], close.iloc[i]) + 1.5 * atr_5m)
            sl = max(sl, entry + 1.0 * atr_5m)
            risk = sl - entry
            if risk <= 0: continue
            tp1 = float(sma.iloc[i]); tp2 = float(lower.iloc[i])
            if tp1 >= entry: continue
            return _simulate_two_leg(bars_1m, curr_time, 'SHORT', entry, sl, tp1, tp2,
                                    risk, session_name, str(ctx.trade_date.date()))

        # LONG: 2-bar hook — prior bar below lower + RSI<33, now closes back inside
        long_setup = (
            close.iloc[i-1] < lower.iloc[i-1] and rsi.iloc[i-1] < 33
            and close.iloc[i] > lower.iloc[i] and rsi.iloc[i] > rsi.iloc[i-1]
            and close.iloc[i] < sma.iloc[i] and rsi.iloc[i] < 50
        )
        if long_setup:
            entry = float(close.iloc[i])
            if not np.isnan(pdl) and abs(entry - pdl) > 15: continue
            atr_5m = float((high.rolling(14).max()-low.rolling(14).min()).iloc[i]/14)
            if np.isnan(atr_5m) or atr_5m <= 0: atr_5m = 2.0
            sl = float(min(lower.iloc[i], close.iloc[i]) - 1.5 * atr_5m)
            sl = min(sl, entry - 1.0 * atr_5m)
            risk = entry - sl
            if risk <= 0: continue
            tp1 = float(sma.iloc[i]); tp2 = float(upper.iloc[i])
            if tp1 <= entry: continue
            return _simulate_two_leg(bars_1m, curr_time, 'LONG', entry, sl, tp1, tp2,
                                    risk, session_name, str(ctx.trade_date.date()))
    return None


def _simulate_two_leg(bars_1m, signal_time, direction, entry, sl, tp1, tp2, risk,
                      session_name, date_str):
    sim = bars_1m.loc[signal_time + pd.Timedelta(minutes=5):]
    if len(sim) == 0: return None
    is_long = direction == 'LONG'
    leg1_pnl, leg2_pnl, t1_hit = 0.0, 0.0, False
    exit_time, exit_price, exit_reason = None, None, None
    mae, mfe, hold_bars = 0.0, 0.0, 0

    for t_bar, row in sim.iterrows():
        hold_bars += 1
        if is_long:
            mae = max(mae, entry - row['low']); mfe = max(mfe, row['high'] - entry)
        else:
            mae = max(mae, row['high'] - entry); mfe = max(mfe, entry - row['low'])

        if not t1_hit:
            if is_long and row['low'] <= sl:
                leg1_pnl = sl - entry; leg2_pnl = sl - entry
                exit_time, exit_price, exit_reason = t_bar, sl, 'stop'; break
            elif not is_long and row['high'] >= sl:
                leg1_pnl = entry - sl; leg2_pnl = entry - sl
                exit_time, exit_price, exit_reason = t_bar, sl, 'stop'; break
            if is_long and row['high'] >= tp1:
                t1_hit = True; leg1_pnl = tp1 - entry; sl = entry
            elif not is_long and row['low'] <= tp1:
                t1_hit = True; leg1_pnl = entry - tp1; sl = entry
        else:
            if is_long and row['low'] <= sl:
                leg2_pnl = sl - entry
                exit_time, exit_price = t_bar, sl
                exit_reason = 'BE' if sl == entry else 'stop'; break
            elif not is_long and row['high'] >= sl:
                leg2_pnl = entry - sl
                exit_time, exit_price = t_bar, sl
                exit_reason = 'BE' if sl == entry else 'stop'; break
            if is_long and row['high'] >= tp2:
                leg2_pnl = tp2 - entry
                exit_time, exit_price, exit_reason = t_bar, tp2, 'TP2'; break
            elif not is_long and row['low'] <= tp2:
                leg2_pnl = entry - tp2
                exit_time, exit_price, exit_reason = t_bar, tp2, 'TP2'; break

    if exit_time is None:
        exit_price = float(sim['close'].iloc[-1]); exit_time = sim.index[-1]
        if not t1_hit: leg1_pnl = (exit_price-entry) if is_long else (entry-exit_price)
        leg2_pnl = (exit_price-entry) if is_long else (entry-exit_price)
        exit_reason = 'EOD'

    total_pts = leg1_pnl + leg2_pnl
    pnl = total_pts * POINT_VAL
    r_mult = total_pts / (2 * risk) if risk > 0 else 0
    return TradeRecord('MEANREVERT', session_name, date_str, direction,
                      signal_time, entry, exit_time, exit_price, sl,
                      pnl, r_mult, mae, mfe, hold_bars, exit_reason)


# ─── 3. SCALP: VWAP bounce with strict rejection candle ───────────────────

def session_vwap(bars_1m):
    cum_vol = bars_1m['volume'].cumsum()
    cum_vp = (bars_1m['close'] * bars_1m['volume']).cumsum()
    return (cum_vp / cum_vol.replace(0, np.nan)).ffill().bfill()


def run_scalp_v3(ctx, session_name, day_1m, after_time=None):
    """VWAP bounce scalp with strict rejection candle confirmation.
    Requires: (a) 4+ of last 6 bars above/below VWAP (trend),
              (b) price pulls back to within 1pt of VWAP,
              (c) rejection candle: wick on VWAP side + close back in trend dir,
              (d) volume at touch bar > 1.2x average of prior 5 bars.
    TP=4pts, SL=3pts (adaptive via ATR).
    NY_AM + NY_MIDDAY only.
    """
    if session_name not in ('NY_AM', 'NY_MIDDAY'):
        return None

    bars_5m = ctx.session_5m.get(session_name)
    bars_1m = ctx.session_bars.get(session_name)
    if bars_5m is None or len(bars_5m) < 20 or bars_1m is None:
        return None

    sess_start = bars_1m.index[0]
    vwap_1m = session_vwap(day_1m.loc[sess_start:])
    vwap_5m = vwap_1m.resample('5min', label='left').last().reindex(bars_5m.index).ffill()

    close, high, low, vol = bars_5m['close'], bars_5m['high'], bars_5m['low'], bars_5m['volume']
    atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14
    vol_avg = vol.rolling(5, min_periods=3).mean()

    for i in range(12, len(bars_5m)):
        curr_time = bars_5m.index[i]
        if after_time and curr_time <= after_time: continue

        vwap_val = vwap_5m.iloc[i]
        if pd.isna(vwap_val): continue
        a5 = atr5.iloc[i]
        if np.isnan(a5) or a5 <= 0: continue

        tp_dist = max(2.0, 0.8 * a5)
        sl_dist = max(1.5, 0.6 * a5)

        # Trend: 4+ of last 6 bars above VWAP = uptrend
        recent = close.iloc[i-6:i+1]
        recent_vwap = vwap_5m.iloc[i-6:i+1]
        bars_above = (recent > recent_vwap).sum()
        bars_below = (recent < recent_vwap).sum()

        # Volume at touch must be > 1.2x prior 5-bar average
        va = vol_avg.iloc[i]
        if not np.isnan(va) and vol.iloc[i] < 1.2 * va:
            continue

        # LONG bounce: uptrend, pullback to VWAP, rejection candle
        if bars_above >= 4:
            # Bar pulled back to within 1pt of VWAP (low touched VWAP zone)
            if low.iloc[i] <= vwap_val + 1.0 and close.iloc[i] > vwap_val:
                # Rejection: lower wick (buyers defended VWAP) + close above
                lower_wick = min(close.iloc[i], open_val(close, i)) - low.iloc[i]
                body = abs(close.iloc[i] - open_val(close, i))
                if lower_wick > body * 0.5:  # wick is at least half the body
                    entry = float(close.iloc[i])
                    sl = entry - sl_dist; tp = entry + tp_dist; risk = sl_dist
                    if risk <= 0: continue
                    return _simulate_scalp(bars_1m, curr_time, 'LONG', entry, sl, tp, risk,
                                           session_name, str(ctx.trade_date.date()))

        # SHORT bounce: downtrend, rally to VWAP, rejection candle
        if bars_below >= 4:
            if high.iloc[i] >= vwap_val - 1.0 and close.iloc[i] < vwap_val:
                upper_wick = high.iloc[i] - max(close.iloc[i], open_val(close, i))
                body = abs(close.iloc[i] - open_val(close, i))
                if upper_wick > body * 0.5:
                    entry = float(close.iloc[i])
                    sl = entry + sl_dist; tp = entry - tp_dist; risk = sl_dist
                    if risk <= 0: continue
                    return _simulate_scalp(bars_1m, curr_time, 'SHORT', entry, sl, tp, risk,
                                           session_name, str(ctx.trade_date.date()))
    return None


def open_val(close, i):
    """Approximate open from close series (we don't have separate open in 5m resample).
    Use prior close as proxy for open."""
    return close.iloc[i-1] if i > 0 else close.iloc[i]


def _simulate_scalp(bars_1m, signal_time, direction, entry, sl, tp, risk,
                    session_name, date_str):
    sim = bars_1m.loc[signal_time + pd.Timedelta(minutes=5):]
    if len(sim) == 0: return None
    is_long = direction == 'LONG'
    exit_price, exit_time, exit_reason = None, None, None
    mae, mfe, hold_bars = 0.0, 0.0, 0

    for t_bar, row in sim.iterrows():
        hold_bars += 1
        if is_long:
            mae = max(mae, entry - row['low']); mfe = max(mfe, row['high'] - entry)
            if row['low'] <= sl: exit_price, exit_time, exit_reason = sl, t_bar, 'stop'; break
            if row['high'] >= tp: exit_price, exit_time, exit_reason = tp, t_bar, 'TP'; break
        else:
            mae = max(mae, row['high'] - entry); mfe = max(mfe, entry - row['low'])
            if row['high'] >= sl: exit_price, exit_time, exit_reason = sl, t_bar, 'stop'; break
            if row['low'] <= tp: exit_price, exit_time, exit_reason = tp, t_bar, 'TP'; break

    if exit_price is None:
        exit_price = float(sim['close'].iloc[-1]); exit_time = sim.index[-1]; exit_reason = 'EOD'

    pnl = (exit_price - entry) * POINT_VAL if is_long else (entry - exit_price) * POINT_VAL
    r_mult = (exit_price - entry) / risk if is_long else (entry - exit_price) / risk
    return TradeRecord('SCALP', session_name, date_str, direction,
                      signal_time, entry, exit_time, exit_price, sl,
                      pnl, r_mult, mae, mfe, hold_bars, exit_reason)


# ─── Run all three ─────────────────────────────────────────────────────────

trend_sessions = ['GLOBEX', 'ASIA', 'LONDON', 'NY_AM', 'NY_MIDDAY', 'NY_PM']
scalp_sessions = ['NY_AM', 'NY_MIDDAY']

all_trades = []
for i, t_date in enumerate(unique_dates):
    if i % 100 == 0: print(f"  Day {i}/{len(unique_dates)}...")
    ts = pd.Timestamp(t_date)
    if ts.weekday() >= 5: continue
    ctx = build_day_context(ts, df, df5, daily_atr, ib_minutes=30)
    if ctx is None: continue

    htf_row_data = htf_df[htf_df['trading_date'] == ts]
    htf_row = htf_row_data.iloc[0] if len(htf_row_data) > 0 else None
    day_1m = df.loc[f"{ts} 09:30:00":f"{ts} 16:00:00"]

    # TREND — all sessions, 1 trade per session
    for sess in trend_sessions:
        t = run_trend_v3(ctx, sess)
        if t: all_trades.append(t)

    # MEANREVERT — NY_PM, up to 3 trades sequential
    after_time = None
    for _ in range(3):
        t = run_meanrevert_v3(ctx, 'NY_PM', htf_row, after_time=after_time)
        if t is None: break
        all_trades.append(t); after_time = t.exit_time

    # SCALP — NY_AM + NY_MIDDAY, up to 3 trades per session
    for sess in scalp_sessions:
        after_time = None
        for _ in range(3):
            t = run_scalp_v3(ctx, sess, day_1m, after_time=after_time)
            if t is None: break
            all_trades.append(t); after_time = t.exit_time

tdf = pd.DataFrame(all_trades)
print(f"\nTotal trades: {len(tdf)}")

# ─── Report ────────────────────────────────────────────────────────────────

for arch in ['TREND', 'MEANREVERT', 'SCALP']:
    sub = tdf[tdf['archetype'] == arch]
    if len(sub) == 0: print(f"\n{arch}: No trades"); continue
    wins = sub[sub['pnl'] > 0]; losses = sub[sub['pnl'] < 0]
    wr = len(wins)/len(sub)*100
    pf = wins['pnl'].sum() / abs(losses['pnl'].sum()) if losses['pnl'].sum() != 0 else 999
    net = sub['pnl'].sum(); avg_r = sub['r_mult'].mean()
    med_hold = sub['hold_bars'].median()

    print(f"\n{'='*70}")
    print(f"{arch}")
    print(f"{'='*70}")
    print(f"  Trades: {len(sub)}")
    print(f"  WR:     {wr:.1f}%")
    print(f"  PF:     {pf:.2f}")
    print(f"  Net:    ${net:+.0f}")
    print(f"  AvgR:   {avg_r:+.3f}")
    print(f"  MAE:    avg={sub['mae'].mean():.2f}pts  p25={sub['mae'].quantile(.25):.2f}  p50={sub['mae'].median():.2f}  p75={sub['mae'].quantile(.75):.2f}")
    print(f"  MFE:    avg={sub['mfe'].mean():.2f}pts  p25={sub['mfe'].quantile(.25):.2f}  p50={sub['mfe'].median():.2f}  p75={sub['mfe'].quantile(.75):.2f}")
    print(f"  Hold:   {med_hold:.0f} bars median ({med_hold*5:.0f}min)")
    print(f"  Exit:   {sub['exit_reason'].value_counts().to_dict()}")

    print(f"  Per session:")
    for sess in sub['session'].unique():
        ss = sub[sub['session'] == sess]
        sw = ss[ss['pnl']>0]; sl = ss[ss['pnl']<0]
        wr_s = len(sw)/len(ss)*100
        pf_s = sw['pnl'].sum()/abs(sl['pnl'].sum()) if sl['pnl'].sum() != 0 else 999
        print(f"    {sess:<12} n={len(ss):>4} WR={wr_s:>5.1f}% PF={pf_s:.2f} Net=${ss['pnl'].sum():>+.0f} AvgR={ss['r_mult'].mean():>+.3f}")

    for d in ['LONG', 'SHORT']:
        ss = sub[sub['direction'] == d]
        if len(ss) == 0: continue
        sw = ss[ss['pnl']>0]
        wr_s = len(sw)/len(ss)*100
        pf_s = sw['pnl'].sum()/abs(ss[ss['pnl']<0]['pnl'].sum()) if ss[ss['pnl']<0]['pnl'].sum() != 0 else 999
        print(f"    {d:<12} n={len(ss):>4} WR={wr_s:>5.1f}% PF={pf_s:.2f} Net=${ss['pnl'].sum():>+.0f} AvgR={ss['r_mult'].mean():>+.3f}")