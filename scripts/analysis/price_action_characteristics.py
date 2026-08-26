"""
Price-Action Characteristic Analyzer
=====================================
As an experienced trader would: studies the RELATIONSHIP between price and
indicator values at signal bars, then correlates those characteristics with
trade outcomes (win/loss, MFE, MAE, R-multiple) to find the statistical edge
that determines which setups to trade and which to filter.

For BB (mean reversion):
  - Displacement beyond band (bps) — how far price pierced the band before hook
  - RSI extreme depth — how oversold/overbought at the touch
  - RSI hook velocity — how fast RSI is turning (rate of change)
  - Bandwidth regime — squeeze vs expansion
  - Distance to VWAP — is price extended from session VWAP?
  - Distance to PDH/PDL — is the touch at a liquidity level?
  - FVG confluence — is there an unfilled FVG near the entry?
  - Prior bar range vs ATR — displacement candle characteristics
  - Number of consecutive bars outside band — persistence of extreme

For Supertrend (trend following):
  - Flip displacement (bps) — how far close pierced the band to trigger flip
  - ATR regime at flip — volatility state (daily ATR percentile)
  - Band distance at entry — how far entry is from the ST band
  - Trail efficiency — MFE/MAE ratio per trade (how well the trail captures)
  - Time since last flip — is this a fresh trend or a whipsaw regime?
  - FVG confluence — did the flip happen inside/near an FVG?
  - Liquidity sweep — did the prior session sweep liquidity before the flip?
  - Distance to PDH/PDL — is the flip at a key level?

Output:
  - docs/research/PRICE_ACTION_CHARACTERISTICS.md
  - data/derived/bb_characteristics.csv
  - data/derived/st_characteristics.csv
"""
import sys, io
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

from scripts.analysis.range_strategy_comparison import (
    BBRsiMeanReversionStrategy, BacktestEngine, build_day_context,
    _wilder_rsi, _adx,
)
from scripts.libs_py.fvg import compute_fvg
from scripts.libs_py.liquidity import compute_liquidity_levels

# ─── Data ───────────────────────────────────────────────────────────────────

def load_data(sym="ES"):
    df1 = pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df5 = pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_5m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df1 = df1[(df1.index.year>=2025)&(df1.index.year<=2026)]
    df5 = df5[(df5.index.year>=2025)&(df5.index.year<=2026)]
    tr2 = pd.concat([
        df1.resample("D").agg({"high":"max","low":"min"}).dropna().pipe(lambda d: d["high"]-d["low"]),
        (df1.resample("D").agg({"high":"max","close":"last"}).dropna()["high"] - df1.resample("D").agg({"close":"last"}).dropna()["close"].shift(1)).abs(),
        (df1.resample("D").agg({"low":"min","close":"last"}).dropna()["low"] - df1.resample("D").agg({"close":"last"}).dropna()["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    daily_atr = tr2.rolling(10, min_periods=1).mean()
    df1["trade_date"] = df1.index.date
    df1.loc[df1.index.hour>=18, "trade_date"] = (df1.loc[df1.index.hour>=18].index + pd.Timedelta(days=1)).date
    return df1, df5, daily_atr


def load_htf_levels(sym="ES1"):
    """Load PDH/PDL/PWH/PWL from pre-computed ICT features."""
    path = Path(f"data/derived/ICT/{sym}_htf_levels.parquet")
    if path.exists():
        df = pd.read_parquet(path)
        return df
    return None


def load_fvg_5m(sym="ES1"):
    """Load pre-computed 5m FVG features."""
    path = Path(f"data/derived/ICT/{sym}_imbalance_5m.parquet")
    if path.exists():
        df = pd.read_parquet(path)
        return df
    return None


def load_liquidity_5m(sym="ES1"):
    """Load pre-computed 5m liquidity levels."""
    path = Path(f"data/derived/ICT/{sym}_liquidity_5m.parquet")
    if path.exists():
        df = pd.read_parquet(path)
        return df
    return None


# ─── VWAP computation ───────────────────────────────────────────────────────

def compute_session_vwap(bars_1m, session_start="09:30"):
    """Compute session VWAP from 1m bars."""
    bars = bars_1m.copy()
    bars["time"] = bars.index
    bars["date"] = bars.index.date
    bars.loc[bars.index.hour >= 18, "date"] = (bars.loc[bars.index.hour >= 18].index + pd.Timedelta(days=1)).date
    session = bars[bars.index.time >= pd.Timestamp(session_start).time()]
    tp = (session["high"] + session["low"] + session["close"]) / 3
    vol = session["volume"]
    cum_tp = tp.groupby(session["date"]).cumsum()
    cum_vol = vol.groupby(session["date"]).cumsum()
    vwap = cum_tp / cum_vol.replace(0, np.nan)
    return vwap


# ─── Confluence helpers ─────────────────────────────────────────────────────

def nearest_fvg(entry_time, entry_price, fvg_df, direction, lookback_bars=20):
    """Find the nearest FVG to the entry price — both unfilled and recently filled.
    For BB mean reversion: an FVG zone near the entry acts as a magnet/support.
    For ST trend: an FVG at the flip confirms displacement.
    We check if entry price is inside or near any FVG zone from the prior N bars.
    """
    if fvg_df is None or fvg_df.empty:
        return None
    # Look at FVGs from the prior 24 bars (2 hours on 5m)
    cutoff = entry_time - pd.Timedelta(minutes=120)
    prior = fvg_df[(fvg_df.index < entry_time) & (fvg_df.index >= cutoff) & (fvg_df["fvg_type"] != 0)]
    if prior.empty:
        return None

    # Check if entry is inside any FVG zone, or distance to nearest zone
    if direction == "LONG":
        # For LONG BB: bullish FVG (type=1) below or at entry = support
        candidates = prior[prior["fvg_type"] == 1].copy()
    else:
        # For SHORT BB: bearish FVG (type=-1) above or at entry = resistance
        candidates = prior[prior["fvg_type"] == -1].copy()

    if candidates.empty:
        return None

    # Distance from entry to nearest edge of FVG zone
    candidates = candidates.copy()
    candidates["zone_top"] = candidates["fvg_top"]
    candidates["zone_bot"] = candidates["fvg_bottom"]
    # If entry is inside the zone, distance = 0
    inside = (entry_price >= candidates["zone_bot"]) & (entry_price <= candidates["zone_top"])
    candidates.loc[inside, "dist"] = 0
    # Otherwise distance to nearest edge
    candidates["dist_to_top"] = abs(entry_price - candidates["zone_top"])
    candidates["dist_to_bot"] = abs(entry_price - candidates["zone_bot"])
    candidates["dist"] = candidates[["dist_to_top", "dist_to_bot"]].min(axis=1)
    candidates.loc[inside, "dist"] = 0

    nearest = candidates.iloc[candidates["dist"].argmin()]
    return {
        "fvg_dist_bps": float(nearest["dist"] / entry_price * 10000),
        "fvg_size_pts": float(abs(nearest["fvg_top"] - nearest["fvg_bottom"])),
        "fvg_age_bars": int((entry_time - nearest.name).total_seconds() / 300),
        "fvg_inside": bool(inside.iloc[candidates["dist"].argmin()]),
    }


def nearest_htf_level(entry_price, htf_df, direction, trade_date=None):
    """Find nearest PDH/PDL/PWH/PWL to entry price."""
    if htf_df is None or htf_df.empty:
        return None
    # If we have a trade_date, use the prior day's levels
    if trade_date is not None and "trading_date" in htf_df.columns:
        td = pd.Timestamp(trade_date)
        htf_df2 = htf_df.copy()
        htf_df2["td_ts"] = pd.to_datetime(htf_df2["trading_date"])
        prior = htf_df2[htf_df2["td_ts"] < td].tail(1)
    else:
        prior = htf_df.tail(1)
    if prior.empty:
        return None
    levels = {}
    for col in ["pdh", "pdl", "pwh", "pwl"]:
        if col in prior.columns:
            val = prior[col].iloc[0]
            if pd.notna(val):
                levels[col] = float(val)
                levels[f"{col}_dist_bps"] = float(abs(val - entry_price) / entry_price * 10000)
    return levels


def liquidity_sweep_near(entry_time, liq_df, lookback_bars=12):
    """Check if a liquidity sweep occurred within lookback 5m bars before entry."""
    if liq_df is None or liq_df.empty:
        return None
    prior = liq_df.loc[:entry_time].tail(lookback_bars)
    if prior.empty:
        return None
    # liq_type: 1 = sweep occurred. liq_kind: BSL (buy-side) or SSL (sell-side)
    sweeps = prior[prior.get("liq_type", 0) == 1]
    bsl = int((sweeps.get("liq_kind", "") == "BSL").sum())
    ssl = int((sweeps.get("liq_kind", "") == "SSL").sum())
    return {"bsl_sweeps": bsl, "ssl_sweeps": ssl, "any_sweep": int(len(sweeps) > 0)}


# ─── BB Characteristic Analysis ─────────────────────────────────────────────

def analyze_bb_characteristics(df1, df5, daily_atr, htf_df=None, fvg_df=None, liq_df=None):
    """Study BB signal characteristics and correlate with outcomes."""
    vwap_series = compute_session_vwap(df1)
    unique_dates = sorted(df1["trade_date"].unique())
    records = []

    for t_date in unique_dates:
        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5 or ts.year < 2025:
            continue
        ctx = build_day_context(ts, df1, df5, daily_atr, ib_minutes=30)
        if ctx is None:
            continue

        # IB filter
        ib_bars = ctx.session_5m.get("NY_AM")
        ib_ok = True
        if ib_bars is not None and len(ib_bars) >= 6:
            ib_range = ib_bars["high"].iloc[:6].max() - ib_bars["low"].iloc[:6].min()
            if ib_range > 0.40 * ctx.atr_val:
                ib_ok = False

        for sess in ("NY_MIDDAY", "NY_PM"):
            bars_5m = ctx.session_5m.get(sess)
            if bars_5m is None or len(bars_5m) < 30:
                continue

            close = bars_5m["close"]
            high = bars_5m["high"]
            low = bars_5m["low"]
            sma = close.rolling(20).mean()
            std = close.rolling(20).std()
            upper = sma + 2.0 * std
            lower = sma - 2.0 * std
            rsi = _wilder_rsi(close, 14)
            adx_s = _adx(high, low, close, 14)
            atr = ctx.atr_val if not np.isnan(ctx.atr_val) and ctx.atr_val > 0 else 20.0

            # Session VWAP at this time
            sess_vwap = vwap_series.reindex(bars_5m.index, method="ffill")

            # Count consecutive bars outside band
            outside_lower = close < lower
            outside_upper = close > upper
            consec_lower = outside_lower.astype(int).groupby((~outside_lower).cumsum()).cumsum()
            consec_upper = outside_upper.astype(int).groupby((~outside_upper).cumsum()).cumsum()

            for i in range(2, len(bars_5m)):
                curr_time = bars_5m.index[i]
                if curr_time.time() < pd.Timestamp("11:30:00").time():
                    continue

                # S0: Raw touch
                long_touch = close.iloc[i-1] < lower.iloc[i-1]
                short_touch = close.iloc[i-1] > upper.iloc[i-1]
                if not long_touch and not short_touch:
                    continue

                direction = "LONG" if long_touch else "SHORT"

                # Characteristics at touch
                displacement_bps = abs(close.iloc[i-1] - sma.iloc[i-1]) / sma.iloc[i-1] * 10000 if sma.iloc[i-1] > 0 else 0
                rsi_at_touch = float(rsi.iloc[i-1]) if not np.isnan(rsi.iloc[i-1]) else 50
                rsi_change = float(rsi.iloc[i] - rsi.iloc[i-1]) if not np.isnan(rsi.iloc[i]) else 0
                adx_at_touch = float(adx_s.iloc[i-1]) if not np.isnan(adx_s.iloc[i-1]) else 20
                bw = float((upper.iloc[i] - lower.iloc[i]) / sma.iloc[i]) if sma.iloc[i] > 0 else 0
                consec_bars_outside = int(consec_lower.iloc[i-1]) if long_touch else int(consec_upper.iloc[i-1])

                # Prior bar range vs ATR
                prior_bar_range = float(high.iloc[i-1] - low.iloc[i-1])
                atr_5m = float((high.rolling(14).max() - low.rolling(14).min()).iloc[i] / 14) if len(bars_5m) > 20 else atr / 6
                if np.isnan(atr_5m) or atr_5m <= 0:
                    atr_5m = atr / 6
                range_vs_atr = prior_bar_range / atr_5m if atr_5m > 0 else 0

                # VWAP distance
                vwap_val = float(sess_vwap.iloc[i]) if not sess_vwap.iloc[i] != sess_vwap.iloc[i] else 0
                vwap_dist_bps = abs(close.iloc[i] - vwap_val) / close.iloc[i] * 10000 if vwap_val > 0 and close.iloc[i] > 0 else 0

                # FVG confluence
                fvg_info = nearest_fvg(curr_time, float(close.iloc[i]), fvg_df, direction)

                # HTF level proximity
                htf_info = nearest_htf_level(float(close.iloc[i]), htf_df, direction, trade_date=ts.date())

                # Liquidity sweep
                liq_info = liquidity_sweep_near(curr_time, liq_df)

                # Hook back inside (S2)
                long_hook = long_touch and close.iloc[i] > lower.iloc[i] and rsi.iloc[i] > rsi.iloc[i-1] and close.iloc[i] < sma.iloc[i] and rsi.iloc[i] < 50
                short_hook = short_touch and close.iloc[i] < upper.iloc[i] and rsi.iloc[i] < rsi.iloc[i-1] and close.iloc[i] > sma.iloc[i] and rsi.iloc[i] > 50
                hooked = long_hook or short_hook

                # RSI extreme passed
                rsi_extreme = (long_touch and rsi_at_touch < 33) or (short_touch and rsi_at_touch > 67)

                # ADX gate passed
                adx_ok = not (not np.isnan(adx_at_touch) and adx_at_touch >= 25.0)

                # All E14 filters
                passes_all = hooked and rsi_extreme and adx_ok and ib_ok
                lunch_skip = not (curr_time.hour >= 13 and curr_time.hour < 14)
                passes_all = passes_all and lunch_skip

                # Simulate trade outcome (if passes all filters)
                outcome = None
                if passes_all:
                    strat = BBRsiMeanReversionStrategy("ES", bb_period=20, std_dev=2.0, rsi_period=14, adx_threshold=25.0, use_adx=True)
                    signal = strat.detect_signal(ctx, sess)
                    if signal is not None:
                        engine = BacktestEngine("ES", entry_mode="market")
                        result = engine.simulate_trade(signal, ctx)
                        if result is not None:
                            # MFE/MAE
                            trade_bars = df1.loc[result.entry_time:result.exit_time]
                            if not trade_bars.empty:
                                if direction == "LONG":
                                    mfe = trade_bars["high"].max() - result.entry_price
                                    mae = result.entry_price - trade_bars["low"].min()
                                else:
                                    mfe = result.entry_price - trade_bars["low"].min()
                                    mae = trade_bars["high"].max() - result.entry_price
                            else:
                                mfe = mae = 0
                            outcome = {
                                "pnl_dollars": result.total_pnl_dollars,
                                "r_multiple": result.r_multiple,
                                "mfe_pts": float(mfe),
                                "mae_pts": float(mae),
                                "is_win": result.total_pnl_dollars > 0,
                                "t1_hit": result.t1_hit,
                                "t2_hit": result.t2_hit,
                                "stopped": result.stopped_out,
                            }

                rec = {
                    "date": str(ts.date()),
                    "session": sess,
                    "time": str(curr_time.time()),
                    "hour": curr_time.hour,
                    "direction": direction,
                    "displacement_bps": round(displacement_bps, 2),
                    "rsi_at_touch": round(rsi_at_touch, 1),
                    "rsi_change": round(rsi_change, 2),
                    "rsi_extreme": rsi_extreme,
                    "adx_at_touch": round(adx_at_touch, 1),
                    "adx_ok": adx_ok,
                    "bandwidth": round(bw, 6),
                    "consec_bars_outside": consec_bars_outside,
                    "prior_bar_range_vs_atr": round(range_vs_atr, 3),
                    "vwap_dist_bps": round(vwap_dist_bps, 2),
                    "ib_ok": ib_ok,
                    "hooked": hooked,
                    "passes_all_e14": passes_all,
                }

                # Add confluence data
                if fvg_info:
                    rec["fvg_dist_bps"] = round(fvg_info["fvg_dist_bps"], 2)
                    rec["fvg_size_pts"] = round(fvg_info["fvg_size_pts"], 2)
                    rec["fvg_age_bars"] = fvg_info["fvg_age_bars"]
                    rec["fvg_inside"] = fvg_info["fvg_inside"]
                    rec["has_fvg_confluence"] = fvg_info["fvg_dist_bps"] < 15 or fvg_info["fvg_inside"]  # within 15 bps or inside
                else:
                    rec["fvg_dist_bps"] = 999
                    rec["has_fvg_confluence"] = False

                if htf_info:
                    rec["nearest_pdh_dist_bps"] = round(htf_info.get("pdh_dist_bps", 999), 2)
                    rec["nearest_pdl_dist_bps"] = round(htf_info.get("pdl_dist_bps", 999), 2)
                    rec["at_htf_level"] = min(htf_info.get("pdh_dist_bps", 999), htf_info.get("pdl_dist_bps", 999)) < 20
                else:
                    rec["at_htf_level"] = False

                if liq_info:
                    rec["had_liquidity_sweep"] = liq_info["any_sweep"] == 1
                    rec["bsl_sweeps"] = liq_info["bsl_sweeps"]
                    rec["ssl_sweeps"] = liq_info["ssl_sweeps"]
                else:
                    rec["had_liquidity_sweep"] = False

                if outcome:
                    rec.update(outcome)
                else:
                    rec.update({"pnl_dollars": None, "r_multiple": None, "mfe_pts": None,
                               "mae_pts": None, "is_win": None, "t1_hit": None,
                               "t2_hit": None, "stopped": None})

                records.append(rec)

    return pd.DataFrame(records)


# ─── Supertrend Characteristic Analysis ─────────────────────────────────────

def supertrend(high, low, close, period, mult):
    hl2 = (high + low) / 2.0
    tr = pd.concat([high-low, (high-close.shift(1)).abs(), (low-close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    upper = hl2 + mult * atr; lower = hl2 - mult * atr
    fu = upper.copy(); fl = lower.copy()
    for i in range(1, len(upper)):
        if fu.iloc[i] > fu.iloc[i-1]: fu.iloc[i] = fu.iloc[i-1]
        if fl.iloc[i] < fl.iloc[i-1]: fl.iloc[i] = fl.iloc[i-1]
    st = pd.Series(np.nan, index=close.index)
    for i in range(1, len(close)):
        if close.iloc[i] > fu.iloc[i-1]: st.iloc[i] = 1
        elif close.iloc[i] < fl.iloc[i-1]: st.iloc[i] = -1
        else: st.iloc[i] = st.iloc[i-1]
    return st, upper, lower, fu, fl, atr


def analyze_st_characteristics(df1, df5, daily_atr, htf_df=None, fvg_df=None, liq_df=None):
    """Study Supertrend signal characteristics and correlate with outcomes."""
    vwap_series = compute_session_vwap(df1)
    POINT_VAL = 5.0; COMM = 1.20; SLIP = 0.25
    unique_dates = sorted(df1["trade_date"].unique())
    records = []

    for t_date in unique_dates:
        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5 or ts.year < 2025:
            continue
        ctx = build_day_context(ts, df1, df5, daily_atr, ib_minutes=30)
        if ctx is None:
            continue
        bars5 = ctx.day_bars_5m
        if bars5 is None or len(bars5) < 19:
            continue
        close = bars5["close"]; high = bars5["high"]; low = bars5["low"]
        st, upper, lower, fu, fl, st_atr = supertrend(high, low, close, 14, 2.0)
        atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14
        sess_vwap = vwap_series.reindex(bars5.index, method="ffill")

        # Track flip frequency
        flip_count = 0
        last_flip_idx = -99
        pos = 0; entry = 0.0; stop = 0.0; entry_idx = 0; entry_time = None

        for i in range(1, len(bars5)):
            a5 = atr5.iloc[i]
            if np.isnan(a5) or a5 <= 0:
                continue
            st0 = st.iloc[i]; st1 = st.iloc[i - 1]
            if pd.isna(st0) or pd.isna(st1):
                continue
            c0 = close.iloc[i]; h0 = high.iloc[i]; l0 = low.iloc[i]

            # Check for exit first
            if pos != 0:
                if pos == 1:
                    stop = max(stop, h0 - 1.5 * a5)
                    if l0 <= stop:
                        exit_px = stop - SLIP
                        pnl = (exit_px - entry) * POINT_VAL - COMM
                        trade_bars = df1.loc[entry_time:bars5.index[i]]
                        if not trade_bars.empty:
                            mfe = trade_bars["high"].max() - entry
                            mae = entry - trade_bars["low"].min()
                        else:
                            mfe = mae = 0
                        risk = abs(1.5 * atr5.iloc[entry_idx])
                        records.append(_st_rec(
                            ts, bars5.index[i], "LONG", entry, exit_px, stop, pnl,
                            mfe, mae, risk, entry_time, bars5.index[i],
                            flip_count, last_flip_idx, entry_idx, i,
                            c0, h0, l0, a5, st_atr.iloc[i], upper.iloc[i], lower.iloc[i],
                            sess_vwap, curr_vwap_val(sess_vwap, i),
                            fvg_df, htf_df, liq_df, daily_atr, ts,
                        ))
                        pos = 0
                else:
                    stop = min(stop, l0 + 1.5 * a5)
                    if h0 >= stop:
                        exit_px = stop + SLIP
                        pnl = (entry - exit_px) * POINT_VAL - COMM
                        trade_bars = df1.loc[entry_time:bars5.index[i]]
                        if not trade_bars.empty:
                            mfe = entry - trade_bars["low"].min()
                            mae = trade_bars["high"].max() - entry
                        else:
                            mfe = mae = 0
                        risk = abs(1.5 * atr5.iloc[entry_idx])
                        records.append(_st_rec(
                            ts, bars5.index[i], "SHORT", entry, exit_px, stop, pnl,
                            mfe, mae, risk, entry_time, bars5.index[i],
                            flip_count, last_flip_idx, entry_idx, i,
                            c0, h0, l0, a5, st_atr.iloc[i], upper.iloc[i], lower.iloc[i],
                            sess_vwap, curr_vwap_val(sess_vwap, i),
                            fvg_df, htf_df, liq_df, daily_atr, ts,
                        ))
                        pos = 0

            # Check for entry (flip)
            if pos == 0:
                if st0 == 1 and st1 == -1:
                    pos = 1; entry = c0 + SLIP; entry_idx = i; entry_time = bars5.index[i]
                    stop = entry - 1.5 * a5
                    flip_count += 1; last_flip_idx = i
                elif st0 == -1 and st1 == 1:
                    pos = -1; entry = c0 - SLIP; entry_idx = i; entry_time = bars5.index[i]
                    stop = entry + 1.5 * a5
                    flip_count += 1; last_flip_idx = i

        # EOD exit
        if pos != 0:
            exit_px = close.iloc[-1] - SLIP if pos == 1 else close.iloc[-1] + SLIP
            pnl = ((exit_px - entry) if pos == 1 else (entry - exit_px)) * POINT_VAL - COMM
            trade_bars = df1.loc[entry_time:bars5.index[-1]]
            if not trade_bars.empty:
                if pos == 1:
                    mfe = trade_bars["high"].max() - entry; mae = entry - trade_bars["low"].min()
                else:
                    mfe = entry - trade_bars["low"].min(); mae = trade_bars["high"].max() - entry
            else:
                mfe = mae = 0
            risk = abs(1.5 * atr5.iloc[entry_idx])
            records.append(_st_rec(
                ts, bars5.index[-1], "LONG" if pos == 1 else "SHORT", entry, exit_px,
                stop, pnl, mfe, mae, risk, entry_time, bars5.index[-1],
                flip_count, last_flip_idx, entry_idx, len(bars5)-1,
                close.iloc[-1], high.iloc[-1], low.iloc[-1], atr5.iloc[-1],
                st_atr.iloc[-1], upper.iloc[-1], lower.iloc[-1],
                sess_vwap, curr_vwap_val(sess_vwap, len(bars5)-1),
                fvg_df, htf_df, liq_df, daily_atr, ts,
            ))

    return pd.DataFrame(records)


def curr_vwap_val(sess_vwap, i):
    try:
        v = sess_vwap.iloc[i]
        return float(v) if v == v else 0
    except:
        return 0


def _st_rec(ts, exit_time, direction, entry, exit_px, stop, pnl, mfe, mae, risk,
            entry_time, exit_time_val, flip_count, last_flip_idx, entry_idx, exit_idx,
            c0, h0, l0, a5, st_atr_val, upper_val, lower_val,
            sess_vwap, vwap_val, fvg_df, htf_df, liq_df, daily_atr, ts_date):
    """Build a Supertrend characteristic record."""
    # Flip displacement: how far close pierced the band
    if direction == "LONG":
        flip_disp_bps = abs(c0 - upper_val) / c0 * 10000 if c0 > 0 and upper_val > 0 else 0
        band_dist_bps = abs(entry - lower_val) / entry * 10000 if entry > 0 and lower_val > 0 else 0
    else:
        flip_disp_bps = abs(c0 - lower_val) / c0 * 10000 if c0 > 0 and lower_val > 0 else 0
        band_dist_bps = abs(upper_val - entry) / entry * 10000 if entry > 0 and upper_val > 0 else 0

    # Bars since last flip
    bars_since_flip = entry_idx - last_flip_idx if last_flip_idx >= 0 else 99

    # Daily ATR percentile (volatility regime)
    atr_val = daily_atr.get(ts_date, 20)
    atr_pct = float(daily_atr.rank(pct=True).get(ts_date, 0.5)) if hasattr(daily_atr, 'rank') else 0.5

    # VWAP distance
    vwap_dist_bps = abs(entry - vwap_val) / entry * 10000 if vwap_val > 0 and entry > 0 else 0

    # FVG confluence
    fvg_info = nearest_fvg(entry_time, entry, fvg_df, direction)
    # HTF level proximity
    htf_info = nearest_htf_level(entry, htf_df, direction, trade_date=ts_date.date() if hasattr(ts_date, 'date') else None)
    # Liquidity sweep
    liq_info = liquidity_sweep_near(entry_time, liq_df)

    rec = {
        "date": str(ts.date()),
        "entry_time": str(entry_time.time()) if hasattr(entry_time, 'time') else str(entry_time),
        "exit_time": str(exit_time_val.time()) if hasattr(exit_time_val, 'time') else str(exit_time_val),
        "hour": entry_time.hour if hasattr(entry_time, 'hour') else 0,
        "direction": direction,
        "flip_disp_bps": round(flip_disp_bps, 2),
        "band_dist_bps": round(band_dist_bps, 2),
        "atr_5m": round(float(a5), 2),
        "st_atr": round(float(st_atr_val), 2),
        "atr_regime_pct": round(atr_pct, 3),
        "daily_atr": round(float(atr_val), 2),
        "bars_since_flip": bars_since_flip,
        "flip_count_today": flip_count,
        "vwap_dist_bps": round(vwap_dist_bps, 2),
        "risk_pts": round(float(risk), 2),
        "pnl_dollars": round(float(pnl), 2),
        "r_multiple": round(float(((exit_px - entry) if direction == "LONG" else (entry - exit_px)) / risk), 3) if risk > 0 else 0,
        "mfe_pts": round(float(mfe), 2),
        "mae_pts": round(float(mae), 2),
        "mfe_r": round(float(mfe / risk), 2) if risk > 0 else 0,
        "mae_r": round(float(mae / risk), 2) if risk > 0 else 0,
        "is_win": pnl > 0,
        "stopped": abs(exit_px - stop) < 0.5,
        "duration_bars": exit_idx - entry_idx,
    }

    if fvg_info:
        rec["fvg_dist_bps"] = round(fvg_info["fvg_dist_bps"], 2)
        rec["has_fvg_confluence"] = fvg_info["fvg_dist_bps"] < 15 or fvg_info.get("fvg_inside", False)
    else:
        rec["fvg_dist_bps"] = 999
        rec["has_fvg_confluence"] = False

    if htf_info:
        rec["at_htf_level"] = min(htf_info.get("pdh_dist_bps", 999), htf_info.get("pdl_dist_bps", 999)) < 20
    else:
        rec["at_htf_level"] = False

    if liq_info:
        rec["had_liquidity_sweep"] = liq_info["any_sweep"] == 1
    else:
        rec["had_liquidity_sweep"] = False

    return rec


# ─── Statistical Correlation Analysis ───────────────────────────────────────

def correlate_characteristics_with_outcomes(df, strategy_name, characteristic_cols):
    """For each characteristic, bin the data and compute win rate / avg R by bin."""
    results = []
    trades_only = df[df["pnl_dollars"].notna()].copy()
    if trades_only.empty:
        return results

    for col in characteristic_cols:
        if col not in trades_only.columns:
            continue
        vals = trades_only[col].dropna()
        if vals.empty or vals.nunique() < 3:
            continue

        # Quartile bins
        try:
            bins = pd.qcut(vals, q=4, labels=["Q1(low)", "Q2", "Q3", "Q4(high)"], duplicates="drop")
        except:
            continue

        trades_only["_bin"] = bins
        agg_dict = {
            "n": ("pnl_dollars", "count"),
            "wr": ("is_win", "mean"),
            "avg_r": ("r_multiple", "mean"),
            "avg_pnl": ("pnl_dollars", "mean"),
            "total_pnl": ("pnl_dollars", "sum"),
        }
        if "mfe_r" in trades_only.columns:
            agg_dict["avg_mfe_r"] = ("mfe_r", "mean")
        if "mae_r" in trades_only.columns:
            agg_dict["avg_mae_r"] = ("mae_r", "mean")
        grouped = trades_only.groupby("_bin").agg(**agg_dict)
        grouped["wr"] = (grouped["wr"] * 100).round(1)

        for bin_label, row in grouped.iterrows():
            results.append({
                "strategy": strategy_name,
                "characteristic": col,
                "bin": str(bin_label),
                "n": int(row["n"]),
                "wr": float(row["wr"]),
                "avg_r": float(row["avg_r"]),
                "avg_pnl": float(row["avg_pnl"]),
                "total_pnl": float(row["total_pnl"]),
                "avg_mfe_r": float(row.get("avg_mfe_r", 0)),
                "avg_mae_r": float(row.get("avg_mae_r", 0)),
            })
    return results


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("PRICE-ACTION CHARACTERISTIC ANALYZER")
    print("=" * 80)

    print("\n[1/5] Loading data...")
    df1, df5, daily_atr = load_data("ES")
    print(f"  1m: {len(df1):,} | 5m: {len(df5):,}")

    print("  Loading ICT features (FVG, HTF levels, liquidity)...")
    htf_df = load_htf_levels("ES1")
    fvg_df = load_fvg_5m("ES1")
    liq_df = load_liquidity_5m("ES1")
    print(f"  HTF levels: {len(htf_df) if htf_df is not None else 0} | FVG: {len(fvg_df) if fvg_df is not None else 0} | Liquidity: {len(liq_df) if liq_df is not None else 0}")

    print("\n[2/5] Analyzing BB characteristics (all raw touches + E14 filtered)...")
    bb_chars = analyze_bb_characteristics(df1, df5, daily_atr, htf_df, fvg_df, liq_df)
    print(f"  BB raw touches: {len(bb_chars)}")
    bb_trades = bb_chars[bb_chars["pnl_dollars"].notna()]
    print(f"  BB trades (E14 filtered): {len(bb_trades)}")
    bb_chars.to_csv("data/derived/bb_characteristics.csv", index=False)

    print("\n[3/5] Analyzing Supertrend characteristics...")
    st_chars = analyze_st_characteristics(df1, df5, daily_atr, htf_df, fvg_df, liq_df)
    print(f"  ST trades: {len(st_chars)}")
    st_chars.to_csv("data/derived/st_characteristics.csv", index=False)

    print("\n[4/5] Correlating characteristics with outcomes...")
    bb_char_cols = [
        "displacement_bps", "rsi_at_touch", "rsi_change", "adx_at_touch",
        "bandwidth", "consec_bars_outside", "prior_bar_range_vs_atr",
        "vwap_dist_bps", "fvg_dist_bps",
    ]
    st_char_cols = [
        "flip_disp_bps", "band_dist_bps", "atr_5m", "st_atr",
        "atr_regime_pct", "bars_since_flip", "vwap_dist_bps",
        "fvg_dist_bps", "duration_bars",
    ]

    bb_corr = correlate_characteristics_with_outcomes(bb_chars, "BB_E14", bb_char_cols)
    st_corr = correlate_characteristics_with_outcomes(st_chars, "ST_S09", st_char_cols)

    print("\n  --- BB Characteristics vs Outcomes ---")
    for r in bb_corr:
        print(f"  {r['characteristic']:30s} {r['bin']:12s} n={r['n']:3d} WR={r['wr']:5.1f}% R={r['avg_r']:+.3f} PnL=${r['total_pnl']:+.0f}")

    print("\n  --- ST Characteristics vs Outcomes ---")
    for r in st_corr:
        print(f"  {r['characteristic']:30s} {r['bin']:12s} n={r['n']:3d} WR={r['wr']:5.1f}% R={r['avg_r']:+.3f} PnL=${r['total_pnl']:+.0f}")

    # Confluence analysis
    print("\n  --- Confluence Impact ---")
    for strat_name, chars_df in [("BB_E14", bb_trades), ("ST_S09", st_chars)]:
        if chars_df.empty:
            continue
        print(f"\n  {strat_name}:")
        for conf in ["has_fvg_confluence", "at_htf_level", "had_liquidity_sweep"]:
            if conf not in chars_df.columns:
                continue
            with_conf = chars_df[chars_df[conf] == True]
            without = chars_df[chars_df[conf] == False]
            if len(with_conf) > 0:
                print(f"    {conf}=True:  n={len(with_conf):3d} WR={with_conf['is_win'].mean()*100:.1f}% R={with_conf['r_multiple'].mean():+.3f} PnL=${with_conf['pnl_dollars'].sum():+.0f}")
            if len(without) > 0:
                print(f"    {conf}=False: n={len(without):3d} WR={without['is_win'].mean()*100:.1f}% R={without['r_multiple'].mean():+.3f} PnL=${without['pnl_dollars'].sum():+.0f}")

    print("\n[5/5] Writing report...")
    report_path = Path("docs/research/PRICE_ACTION_CHARACTERISTICS.md")
    report_lines = [
        "# Price-Action Characteristic Analysis",
        f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        f"\n_Data: ES 09-26 MergeBackAdjusted 5m, 2025-01-01 -> 2026-08-21_",
        f"\n_Confluence data: FVG 5m, HTF levels (PDH/PDL/PWH/PWL), Liquidity sweeps_",
        "\n---\n",
        "## 1. BB Mean Reversion — Signal Funnel Diagnosis\n",
        f"Total raw BB touches (close beyond band, 11:30-16:00 ET): **{len(bb_chars)}**",
        f"Touches with RSI extreme (<33/>67): **{bb_chars['rsi_extreme'].sum()}**",
        f"Touches with hook back inside: **{bb_chars['hooked'].sum()}**",
        f"Touches passing ADX<25: **{bb_chars['adx_ok'].sum()}**",
        f"Touches passing IB<0.4: **{bb_chars['ib_ok'].sum()}**",
        f"Touches passing ALL E14 filters: **{bb_chars['passes_all_e14'].sum()}**",
        f"Final trades (after risk cap + TP1 valid): **{len(bb_trades)}**",
        "\n### Filter Choke Points:",
        "| Filter | Rejected | Cumulative Pass |",
        "| :--- | :---: | :---: |",
        f"| Raw touches | - | {len(bb_chars)} |",
        f"| RSI extreme | {len(bb_chars) - bb_chars['rsi_extreme'].sum()} | {bb_chars['rsi_extreme'].sum()} |",
        f"| Hook back | {bb_chars['rsi_extreme'].sum() - bb_chars['hooked'].sum()} | {bb_chars['hooked'].sum()} |",
        f"| ADX<25 | {bb_chars['hooked'].sum() - bb_chars['adx_ok'].sum()} | {bb_chars['adx_ok'].sum()} |",
        f"| IB<0.4 | {bb_chars['adx_ok'].sum() - bb_chars['ib_ok'].sum()} | {bb_chars['ib_ok'].sum()} |",
        f"| All E14 | {bb_chars['ib_ok'].sum() - bb_chars['passes_all_e14'].sum()} | {bb_chars['passes_all_e14'].sum()} |",
        "",
    ]

    # BB characteristic correlation table
    report_lines.append("\n## 2. BB Characteristics vs Trade Outcomes (quartile bins)\n")
    if bb_corr:
        report_lines.append("| Characteristic | Bin | N | WR | Avg R | Total P&L | Avg MFE(R) | Avg MAE(R) |")
        report_lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for r in bb_corr:
            report_lines.append(
                f"| {r['characteristic']} | {r['bin']} | {r['n']} | "
                f"{r['wr']}% | {r['avg_r']:+.3f} | ${r['total_pnl']:+.0f} | "
                f"{r['avg_mfe_r']:.2f} | {r['avg_mae_r']:.2f} |"
            )

    # ST characteristic correlation table
    report_lines.append("\n## 3. Supertrend Characteristics vs Trade Outcomes (quartile bins)\n")
    if st_corr:
        report_lines.append("| Characteristic | Bin | N | WR | Avg R | Total P&L | Avg MFE(R) | Avg MAE(R) |")
        report_lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for r in st_corr:
            report_lines.append(
                f"| {r['characteristic']} | {r['bin']} | {r['n']} | "
                f"{r['wr']}% | {r['avg_r']:+.3f} | ${r['total_pnl']:+.0f} | "
                f"{r['avg_mfe_r']:.2f} | {r['avg_mae_r']:.2f} |"
            )

    # Confluence analysis
    report_lines.append("\n## 4. Confluence Impact (FVG, HTF Levels, Liquidity Sweeps)\n")
    for strat_name, chars_df in [("BB_E14", bb_trades), ("ST_S09", st_chars)]:
        if chars_df.empty:
            continue
        report_lines.append(f"\n### {strat_name}\n")
        report_lines.append("| Confluence | Filter | N | WR | Avg R | Total P&L |")
        report_lines.append("| :--- | :--- | :---: | :---: | :---: | :---: |")
        for conf in ["has_fvg_confluence", "at_htf_level", "had_liquidity_sweep"]:
            if conf not in chars_df.columns:
                continue
            for val, label in [(True, conf), (False, f"NOT {conf}")]:
                subset = chars_df[chars_df[conf] == val]
                if subset.empty:
                    continue
                wr = subset["is_win"].mean() * 100
                avg_r = subset["r_multiple"].mean()
                total = subset["pnl_dollars"].sum()
                report_lines.append(
                    f"| {conf} | {label} | {len(subset)} | "
                    f"{wr:.1f}% | {avg_r:+.3f} | ${total:+.0f} |"
                )

    # Key findings
    report_lines.append("\n## 5. Key Statistical Findings & Recommendations\n")

    # Find the best discriminating characteristics
    if bb_corr:
        bb_discrim = {}
        for r in bb_corr:
            key = r["characteristic"]
            if key not in bb_discrim:
                bb_discrim[key] = []
            bb_discrim[key].append(r)
        report_lines.append("### BB — Characteristics That Discriminate Winners\n")
        for char, rows in bb_discrim.items():
            q1 = next((r for r in rows if "Q1" in r["bin"]), None)
            q4 = next((r for r in rows if "Q4" in r["bin"]), None)
            if q1 and q4 and q1["n"] >= 3 and q4["n"] >= 3:
                delta = q4["wr"] - q1["wr"]
                if abs(delta) > 10:
                    direction = "HIGHER" if delta > 0 else "LOWER"
                    report_lines.append(
                        f"- **{char}**: Q1 WR={q1['wr']}% vs Q4 WR={q4['wr']}% "
                        f"(delta {delta:+.1f}%) -> {direction} values win more"
                    )

    if st_corr:
        st_discrim = {}
        for r in st_corr:
            key = r["characteristic"]
            if key not in st_discrim:
                st_discrim[key] = []
            st_discrim[key].append(r)
        report_lines.append("\n### Supertrend — Characteristics That Discriminate Winners\n")
        for char, rows in st_discrim.items():
            q1 = next((r for r in rows if "Q1" in r["bin"]), None)
            q4 = next((r for r in rows if "Q4" in r["bin"]), None)
            if q1 and q4 and q1["n"] >= 10 and q4["n"] >= 10:
                delta = q4["wr"] - q1["wr"]
                if abs(delta) > 5:
                    direction = "HIGHER" if delta > 0 else "LOWER"
                    report_lines.append(
                        f"- **{char}**: Q1 WR={q1['wr']}% vs Q4 WR={q4['wr']}% "
                        f"(delta {delta:+.1f}%) -> {direction} values win more"
                    )

    report_lines.append("\n---\n")
    report_lines.append("_Correlates indicator characteristics (displacement, RSI depth, ADX, bandwidth, "
                        "VWAP distance, FVG confluence, HTF level proximity, liquidity sweeps) with "
                        "trade outcomes to find the statistical edge for trade structuring._")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n  Report: {report_path}")
    print(f"  BB chars: data/derived/bb_characteristics.csv ({len(bb_chars)} rows)")
    print(f"  ST chars: data/derived/st_characteristics.csv ({len(st_chars)} rows)")


if __name__ == "__main__":
    main()