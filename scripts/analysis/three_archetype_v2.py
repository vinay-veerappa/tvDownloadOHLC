"""Three-Archetype Strategy Comparison v2 — Redesigned based on research.

ARCHETYPES:
  1. TREND    — Supertrend(14,3) + EMA200 filter + 1.5xATR trail + ATR regime gate
                Entry: ST flip aligned with EMA200 direction
                Exit: 1.5xATR trail ratchet (wider, fewer chop-outs)
                Sessions: all, but ATR regime filter only trades high-vol bars
                R:R: variable, target >2R (runner)

  2. MEANREVERT — VWAP regime classifier + BB(20, 2.5σ) + RSI
                Entry: BB extreme + RSI extreme + VWAP rotational regime confirmed
                TP1 = VWAP (institutional mean), TP2 = opposite BB band
                Sessions: ALL RTH (NY_AM + NY_MIDDAY + NY_PM) if rotational
                R:R: ~1:1.5

  3. SCALPING  — VWAP Bounce in trending sessions
                Entry: price pulls back to VWAP, rejection candle, bounce in trend dir
                TP = 4pts, SL = 3pts (adaptive via ATR)
                Sessions: NY_AM + NY_MIDDAY (9:30-13:30, high volume)
                R:R: ~1:1.3, target >65% WR

All use mandatory micros (MES $5/pt), $0 commission/slippage.
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
    mae: float
    mfe: float
    hold_bars: int
    exit_reason: str


def compute_mae_mfe_1m(entry_time, exit_time, direction, entry_price, session_bars_1m):
    bars = session_bars_1m.loc[entry_time:exit_time]
    if len(bars) == 0: return 0.0, 0.0
    if direction == 'LONG':
        mae = entry_price - bars['low'].min()
        mfe = bars['high'].max() - entry_price
    else:
        mae = bars['high'].max() - entry_price
        mfe = entry_price - bars['low'].min()
    return max(mae, 0), max(mfe, 0)


# ─── Shared: Session VWAP ──────────────────────────────────────────────────

def session_vwap(bars_1m):
    cum_vol = bars_1m['volume'].cumsum()
    cum_vp = (bars_1m['close'] * bars_1m['volume']).cumsum()
    return (cum_vp / cum_vol.replace(0, np.nan)).ffill().bfill()


def session_vwap_bands(bars_1m, vwap_series, n_std=2.0):
    """Volume-weighted std dev bands around VWAP."""
    tp = (bars_1m['high'] + bars_1m['low'] + bars_1m['close']) / 3
    cum_vol = bars_1m['volume'].cumsum()
    cum_var = (bars_1m['volume'] * (tp - vwap_series) ** 2).cumsum()
    vol_std = np.sqrt(cum_var / cum_vol.replace(0, np.nan)).ffill().bfill()
    upper = vwap_series + n_std * vol_std
    lower = vwap_series - n_std * vol_std
    return upper, lower, vol_std


def classify_vwap_regime(bars_5m, vwap_5m, lookback=12):
    """Classify session as rotational (mean-revert) or trending.

    Rotational: price crosses VWAP repeatedly, flat VWAP slope
    Trending: price holds one side of VWAP, sloped VWAP

    Returns: 'rotational' | 'trending' | 'unclear'
    """
    if len(bars_5m) < lookback:
        return 'unclear'

    close = bars_5m['close']
    # Count VWAP crossings in lookback window
    above = (close > vwap_5m).astype(int)
    crossings = (above.diff().abs() > 0).sum()

    # VWAP slope (linear regression of last N values)
    vwap_recent = vwap_5m.iloc[-lookback:]
    if len(vwap_recent) < 2 or vwap_recent.isna().all():
        return 'unclear'
    slope = (vwap_recent.iloc[-1] - vwap_recent.iloc[0]) / lookback

    # Classify: rotational = many crossings + flat slope
    #           trending = few crossings + significant slope
    avg_price = close.iloc[-lookback:].mean()
    norm_slope = slope / avg_price * 10000  # bps per bar

    if crossings >= 3 and abs(norm_slope) < 2.0:
        return 'rotational'
    elif crossings <= 2 and abs(norm_slope) >= 3.0:
        return 'trending'
    else:
        return 'unclear'


# ─── 1. TREND: Supertrend + EMA200 + 1.5xATR trail + ATR regime ───────────

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


def run_trend_v2(ctx, session_name, after_time=None):
    """Supertrend(14,2) + EMA200 filter + 1.0xATR(5m) trail + ATR regime gate.
    Uses the VALIDATED NT8 config: ST(14,2), 1.0x 5m-ATR trail, skip low-vol.
    Adds EMA200 trend alignment filter.
    """
    bars_5m = ctx.session_5m.get(session_name)
    bars_1m = ctx.session_bars.get(session_name)
    if bars_5m is None or len(bars_5m) < 30 or bars_1m is None:
        return None

    high, low, close = bars_5m['high'], bars_5m['low'], bars_5m['close']
    st = supertrend(high, low, close, 14, 2.0)  # back to 2.0 (validated)
    atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14
    ema200 = close.ewm(span=200, min_periods=20).mean()

    # ATR regime: only trade when current ATR > median (top 50%)
    atr_med = atr5.rolling(50, min_periods=10).median()
    if atr_med.isna().all():
        return None

    for i in range(1, len(bars_5m)):
        curr_time = bars_5m.index[i]
        if after_time and curr_time <= after_time:
            continue
        st0, st1 = st.iloc[i], st.iloc[i-1]
        if pd.isna(st0) or pd.isna(st1): continue
        a5 = atr5.iloc[i]
        if np.isnan(a5) or a5 <= 0: continue

        # ATR regime gate: skip low-vol bars
        atr_m = atr_med.iloc[i]
        if not np.isnan(atr_m) and a5 < atr_m:
            continue

        if st0 == 1 and st1 == -1:
            ema_val = ema200.iloc[i]
            if not pd.isna(ema_val) and close.iloc[i] < ema_val:
                continue
            entry = float(close.iloc[i])
            stop = entry - 2.0 * a5
            direction = 'LONG'
        elif st0 == -1 and st1 == 1:
            ema_val = ema200.iloc[i]
            if not pd.isna(ema_val) and close.iloc[i] > ema_val:
                continue
            entry = float(close.iloc[i])
            stop = entry + 2.0 * a5
            direction = 'SHORT'
        else:
            continue

        risk = abs(entry - stop)
        if risk <= 0: continue

        # Trail with 1.0x 5m-ATR (validated config), skip entry bar, ratchet only
        sim = bars_1m.loc[curr_time + pd.Timedelta(minutes=5):]
        if len(sim) == 0: return None

        trail_stop = stop
        exit_price, exit_time, exit_reason = None, None, None
        mae, mfe = 0.0, 0.0
        hold_bars = 0

        for j, (t_bar, row) in enumerate(sim.iterrows()):
            hold_bars += 1
            if direction == 'LONG':
                mae = max(mae, entry - row['low'])
                mfe = max(mfe, row['high'] - entry)
                if j > 0:  # skip entry bar (trailFirstBar parity)
                    new_trail = row['high'] - 1.0 * a5
                    if new_trail > trail_stop:
                        trail_stop = new_trail
                if row['low'] <= trail_stop:
                    exit_price, exit_time, exit_reason = trail_stop, t_bar, 'trail'
                    break
            else:
                mae = max(mae, row['high'] - entry)
                mfe = max(mfe, entry - row['low'])
                if j > 0:
                    new_trail = row['low'] + 1.0 * a5
                    if new_trail < trail_stop:
                        trail_stop = new_trail
                if row['high'] >= trail_stop:
                    exit_price, exit_time, exit_reason = trail_stop, t_bar, 'trail'
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


# ─── 2. MEAN REVERT: VWAP regime + BB(20, 2.5σ) + RSI ─────────────────────

def run_meanrevert_v2(ctx, session_name, bars_1m_full, after_time=None):
    """VWAP-regime-aware BB mean reversion.

    Only enters when VWAP regime is 'rotational'.
    Uses BB(20, 2.5σ) for wider bands (fewer but better signals).
    TP1 = VWAP (institutional mean), TP2 = opposite BB band.
    Works in ALL RTH sessions when rotational.
    """
    if session_name not in ('NY_AM', 'NY_MIDDAY', 'NY_PM'):
        return None

    bars_5m = ctx.session_5m.get(session_name)
    bars_1m = ctx.session_bars.get(session_name)
    if bars_5m is None or len(bars_5m) < 30 or bars_1m is None:
        return None

    # Compute session VWAP from 1m bars (RTH session start)
    sess_start = bars_1m.index[0]
    sess_1m = bars_1m_full.loc[sess_start:]
    vwap_1m = session_vwap(sess_1m)

    # Map VWAP to 5m bars (take last 1m VWAP in each 5m bar)
    vwap_5m = vwap_1m.resample('5min', label='left').last().reindex(bars_5m.index).ffill()

    # VWAP regime classification (using rolling 12-bar window)
    close, high, low = bars_5m['close'], bars_5m['high'], bars_5m['low']
    sma = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = sma + 2.5 * std  # wider bands (2.5 not 2.0)
    lower = sma - 2.5 * std
    rsi = _wilder_rsi(close, 14)
    adx_s = _adx(high, low, close, 14)

    for i in range(20, len(bars_5m)):
        curr_time = bars_5m.index[i]
        if after_time and curr_time <= after_time:
            continue

        # VWAP regime check (rolling window up to bar i)
        vwap_so_far = vwap_5m.iloc[:i+1]
        bars_so_far = bars_5m.iloc[:i+1]
        if len(vwap_so_far) < 12:
            continue
        regime = classify_vwap_regime(bars_so_far, vwap_so_far, lookback=12)
        if regime != 'rotational':
            continue

        adx_val = adx_s.iloc[i]
        if not np.isnan(adx_val) and adx_val >= 35:  # only block strong trends
            continue

        vwap_val = vwap_5m.iloc[i]
        if pd.isna(vwap_val): continue

        # SHORT: close above upper band + RSI > 67, now closing back inside
        short_setup = (
            close.iloc[i-1] > upper.iloc[i-1] and rsi.iloc[i-1] > 67
            and close.iloc[i] < upper.iloc[i] and rsi.iloc[i] < rsi.iloc[i-1]
            and close.iloc[i] > sma.iloc[i]
        )
        if short_setup:
            entry = float(close.iloc[i])
            atr_5m = float((high.rolling(14).max() - low.rolling(14).min()).iloc[i] / 14)
            if np.isnan(atr_5m) or atr_5m <= 0: atr_5m = 2.0
            sl = float(max(upper.iloc[i], close.iloc[i]) + 1.5 * atr_5m)
            sl = max(sl, entry + 1.0 * atr_5m)
            risk = sl - entry
            if risk <= 0: continue
            tp1 = float(vwap_val)   # TP1 = VWAP (not BB mid)
            tp2 = float(lower.iloc[i])
            if tp1 >= entry: continue
            return _simulate_two_leg(bars_1m, curr_time, 'SHORT', entry, sl, tp1, tp2, risk, session_name, str(ctx.trade_date.date()))

        # LONG: close below lower band + RSI < 33, now closing back inside
        long_setup = (
            close.iloc[i-1] < lower.iloc[i-1] and rsi.iloc[i-1] < 33
            and close.iloc[i] > lower.iloc[i] and rsi.iloc[i] > rsi.iloc[i-1]
            and close.iloc[i] < sma.iloc[i]
        )
        if long_setup:
            entry = float(close.iloc[i])
            atr_5m = float((high.rolling(14).max() - low.rolling(14).min()).iloc[i] / 14)
            if np.isnan(atr_5m) or atr_5m <= 0: atr_5m = 2.0
            sl = float(min(lower.iloc[i], close.iloc[i]) - 1.5 * atr_5m)
            sl = min(sl, entry - 1.0 * atr_5m)
            risk = entry - sl
            if risk <= 0: continue
            tp1 = float(vwap_val)   # TP1 = VWAP
            tp2 = float(upper.iloc[i])
            if tp1 <= entry: continue
            return _simulate_two_leg(bars_1m, curr_time, 'LONG', entry, sl, tp1, tp2, risk, session_name, str(ctx.trade_date.date()))
    return None


def _simulate_two_leg(bars_1m, signal_time, direction, entry, sl, tp1, tp2, risk, session_name, date_str):
    sim = bars_1m.loc[signal_time + pd.Timedelta(minutes=5):]
    if len(sim) == 0: return None

    is_long = direction == 'LONG'
    leg1_pnl, leg2_pnl = 0.0, 0.0
    t1_hit = False
    exit_time, exit_price, exit_reason = None, None, None
    mae, mfe, hold_bars = 0.0, 0.0, 0

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
                leg1_pnl = sl - entry; leg2_pnl = sl - entry
                exit_time, exit_price, exit_reason = t_bar, sl, 'stop'
                break
            elif not is_long and row['high'] >= sl:
                leg1_pnl = entry - sl; leg2_pnl = entry - sl
                exit_time, exit_price, exit_reason = t_bar, sl, 'stop'
                break
            if is_long and row['high'] >= tp1:
                t1_hit = True; leg1_pnl = tp1 - entry; sl = entry
            elif not is_long and row['low'] <= tp1:
                t1_hit = True; leg1_pnl = entry - tp1; sl = entry
        else:
            if is_long and row['low'] <= sl:
                leg2_pnl = sl - entry
                exit_time, exit_price = t_bar, sl
                exit_reason = 'BE' if sl == entry else 'stop'
                break
            elif not is_long and row['high'] >= sl:
                leg2_pnl = entry - sl
                exit_time, exit_price = t_bar, sl
                exit_reason = 'BE' if sl == entry else 'stop'
                break
            if is_long and row['high'] >= tp2:
                leg2_pnl = tp2 - entry
                exit_time, exit_price, exit_reason = t_bar, tp2, 'TP2'
                break
            elif not is_long and row['low'] <= tp2:
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

    return TradeRecord('MEANREVERT', session_name, date_str, direction,
                      signal_time, entry, exit_time, exit_price, sl,
                      pnl, r_mult, mae, mfe, hold_bars, exit_reason)


# ─── 3. SCALP: VWAP Bounce in trending sessions ───────────────────────────

def run_scalp_v2(ctx, session_name, bars_1m_full, after_time=None):
    """VWAP Bounce scalp — highest WR strategy per research (72%).

    Only enters when VWAP regime is 'trending'.
    Entry: price pulls back to VWAP, shows rejection (close back in trend dir).
    TP = 4pts, SL = 3pts (adaptive: scaled by ATR).
    Sessions: NY_AM + NY_MIDDAY (high volume, 9:30-13:30).
    """
    if session_name not in ('NY_AM', 'NY_MIDDAY', 'NY_PM'):
        return None

    bars_5m = ctx.session_5m.get(session_name)
    bars_1m = ctx.session_bars.get(session_name)
    if bars_5m is None or len(bars_5m) < 20 or bars_1m is None:
        return None

    # Session VWAP
    sess_start = bars_1m.index[0]
    sess_1m = bars_1m_full.loc[sess_start:]
    vwap_1m = session_vwap(sess_1m)
    vwap_5m = vwap_1m.resample('5min', label='left').last().reindex(bars_5m.index).ffill()

    close, high, low = bars_5m['close'], bars_5m['high'], bars_5m['low']
    atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14

    for i in range(12, len(bars_5m)):
        curr_time = bars_5m.index[i]
        if after_time and curr_time <= after_time:
            continue

        vwap_val = vwap_5m.iloc[i]
        if pd.isna(vwap_val): continue
        a5 = atr5.iloc[i]
        if np.isnan(a5) or a5 <= 0: continue

        # Adaptive TP/SL based on ATR
        tp_dist = max(2.0, 0.8 * a5)   # ~4pts typical, adapts to vol
        sl_dist = max(1.5, 0.6 * a5)   # ~3pts typical

        # Determine trend: last 6 bars consistently above/below VWAP
        recent = close.iloc[i-6:i+1]
        recent_vwap = vwap_5m.iloc[i-6:i+1]
        bars_above = (recent > recent_vwap).sum()
        bars_below = (recent < recent_vwap).sum()

        # LONG bounce: uptrend (4+ bars above VWAP), pullback to VWAP, close above
        if bars_above >= 4:
            # Current bar pulls back to within 1pt of VWAP and closes above
            if low.iloc[i] <= vwap_val + 1.0 and close.iloc[i] > vwap_val:
                # Rejection candle: close above VWAP with lower wick
                entry = float(close.iloc[i])
                sl = entry - sl_dist
                tp = entry + tp_dist
                risk = sl_dist
                if risk <= 0: continue
                return _simulate_scalp(bars_1m, curr_time, 'LONG', entry, sl, tp, risk,
                                       session_name, str(ctx.trade_date.date()))

        # SHORT bounce: downtrend, price rallies to VWAP, closes below
        if bars_below >= 4:
            if high.iloc[i] >= vwap_val - 1.0 and close.iloc[i] < vwap_val:
                entry = float(close.iloc[i])
                sl = entry + sl_dist
                tp = entry - tp_dist
                risk = sl_dist
                if risk <= 0: continue
                return _simulate_scalp(bars_1m, curr_time, 'SHORT', entry, sl, tp, risk,
                                       session_name, str(ctx.trade_date.date()))
    return None


def _simulate_scalp(bars_1m, signal_time, direction, entry, sl, tp, risk, session_name, date_str):
    sim = bars_1m.loc[signal_time + pd.Timedelta(minutes=5):]
    if len(sim) == 0: return None

    is_long = direction == 'LONG'
    exit_price, exit_time, exit_reason = None, None, None
    mae, mfe, hold_bars = 0.0, 0.0, 0

    for t_bar, row in sim.iterrows():
        hold_bars += 1
        if is_long:
            mae = max(mae, entry - row['low'])
            mfe = max(mfe, row['high'] - entry)
            if row['low'] <= sl:
                exit_price, exit_time, exit_reason = sl, t_bar, 'stop'
                break
            if row['high'] >= tp:
                exit_price, exit_time, exit_reason = tp, t_bar, 'TP'
                break
        else:
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

    pnl = (exit_price - entry) * POINT_VAL if is_long else (entry - exit_price) * POINT_VAL
    r_mult = (exit_price - entry) / risk if is_long else (entry - exit_price) / risk

    return TradeRecord('SCALP', session_name, date_str, direction,
                      signal_time, entry, exit_time, exit_price, sl,
                      pnl, r_mult, mae, mfe, hold_bars, exit_reason)


# ─── Run all three ─────────────────────────────────────────────────────────

trend_sessions = ['GLOBEX', 'ASIA', 'LONDON', 'NY_AM', 'NY_MIDDAY', 'NY_PM']
meanrevert_sessions = ['NY_AM', 'NY_MIDDAY', 'NY_PM']
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

    # Full-day 1m bars for VWAP computation
    day_1m = df.loc[f"{ts} 09:30:00":f"{ts} 16:00:00"]

    # TREND — all sessions, 1 trade per session
    for sess in trend_sessions:
        trade = run_trend_v2(ctx, sess)
        if trade:
            all_trades.append(trade)

    # MEANREVERT — RTH sessions, up to 3 trades (sequential)
    for sess in meanrevert_sessions:
        after_time = None
        for _ in range(3):
            trade = run_meanrevert_v2(ctx, sess, day_1m, after_time=after_time)
            if trade is None: break
            all_trades.append(trade)
            after_time = trade.exit_time

    # SCALP — RTH sessions, up to 3 trades
    for sess in scalp_sessions:
        after_time = None
        for _ in range(3):
            trade = run_scalp_v2(ctx, sess, day_1m, after_time=after_time)
            if trade is None: break
            all_trades.append(trade)
            after_time = trade.exit_time

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
    med_hold = sub['hold_bars'].median()

    print(f"\n{'='*70}")
    print(f"{arch}")
    print(f"{'='*70}")
    print(f"  Trades: {len(sub)}")
    print(f"  WR:     {wr:.1f}%")
    print(f"  PF:     {pf:.2f}")
    print(f"  Net:    ${net:+.0f}")
    print(f"  AvgR:   {avg_r:+.3f}")
    print(f"  MAE:    avg={avg_mae:.2f}pts  p25={sub['mae'].quantile(.25):.2f}  p50={sub['mae'].median():.2f}  p75={sub['mae'].quantile(.75):.2f}")
    print(f"  MFE:    avg={avg_mfe:.2f}pts  p25={sub['mfe'].quantile(.25):.2f}  p50={sub['mfe'].median():.2f}  p75={sub['mfe'].quantile(.75):.2f}")
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