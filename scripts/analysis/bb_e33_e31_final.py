"""E33 + E31 — final falsification arm and two-engine portfolio sim.

E33  VWAP-anchored exits — same E22 entries (overnight BB touch + ADX25), same wide-target
     geometry, but TP1 anchored on session VWAP instead of the BB midband.
       E33a: TP1 = GLOBEX session VWAP (progressive, zero-lookahead)
       E33b: TP1 = day-anchored VWAP (09:30 anchor — RTH-anchored, usually above overnight price)
     If E33a ≈ E22 (midband) -> the alpha is "fade to the mean", BB can be dropped.
     If E22 > E33a -> the midband specifically earns its keep; BB stays.

E31  Two-engine portfolio — E22 (overnight BB reversion, ES) + STTrendBot clone
     (5m Supertrend 10,2 + 1.5xATR trail, same supertrend_intraday_cost.py logic),
     1xMES each, combined daily equity curve: correlation, combined DD, prop sim.

Usage:
  .\\.venv\\Scripts\\python.exe scripts/analysis/bb_e33_e31_final.py
"""
import sys
import warnings

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

import numpy as np
import pandas as pd

from scripts.analysis.bb_e16_e21_queue import load_nt
from scripts.analysis.range_strategy_comparison import (
    BacktestEngine,
    TradeSignal,
    _adx,
    _wilder_rsi,
    build_day_context,
)
from scripts.trading_framework.ml.prop_firm_simulator import FIRM_PROFILES, PropFirmSimulator

warnings.filterwarnings("ignore", category=FutureWarning)

HOURS_FULL = set(range(19, 24)) | set(range(0, 8))


# ----------------------------------------------------------------------------
# E22-family signal scan with configurable TP1 anchor
# ----------------------------------------------------------------------------
def scan_e22_anchored(bars5: pd.DataFrame, tp1_anchor: str,
                      progressive_vwap_5m: pd.Series = None,
                      adx_threshold: float = 25.0, bb_period: int = 20,
                      std_dev: float = 1.8) -> list:
    """E22 entry (BB touch + RSI hook + ADX25, long-only) with configurable TP1.
    tp1_anchor: 'midband' (E22 baseline) | 'vwap' (E33a) | 'dayvwap' (E33b)
    TP2 = upper band (all arms); SL identical (band extreme - 1.5xATR5).
    """
    if bars5 is None or len(bars5) < bb_period + 10:
        return []
    close = bars5["close"]
    high = bars5["high"]
    low = bars5["low"]

    sma = close.rolling(bb_period).mean()
    std = close.rolling(bb_period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    rsi = _wilder_rsi(close, 14)
    adx_s = _adx(high, low, close, 14)
    atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14.0

    signals = []
    for i in range(2, len(bars5)):
        t = bars5.index[i]
        adx_val = adx_s.iloc[i]
        if not (np.isnan(adx_val) or adx_val < adx_threshold):
            continue
        cond = (
            close.iloc[i - 1] < lower.iloc[i - 1]
            and rsi.iloc[i - 1] < 33
            and close.iloc[i] > lower.iloc[i]
            and rsi.iloc[i] > rsi.iloc[i - 1]
            and close.iloc[i] < sma.iloc[i]
            and rsi.iloc[i] < 50
        )
        if not cond:
            continue

        entry = float(close.iloc[i])
        a5 = float(atr5.iloc[i])
        if np.isnan(a5) or a5 <= 0:
            continue

        if tp1_anchor == "midband":
            tp1 = float(sma.iloc[i])
        elif tp1_anchor == "vwap":
            if progressive_vwap_5m is None:
                continue
            v = progressive_vwap_5m.reindex([t]).iloc[0] if hasattr(progressive_vwap_5m, "reindex") else None
            if v is None or np.isnan(v) or v <= entry:
                continue
            tp1 = float(v)
        elif tp1_anchor == "dayvwap":
            if progressive_vwap_5m is None:
                continue
            v = progressive_vwap_5m.reindex([t]).iloc[0] if hasattr(progressive_vwap_5m, "reindex") else None
            if v is None or np.isnan(v) or v <= entry:
                continue
            tp1 = float(v)
        else:
            raise ValueError(tp1_anchor)

        tp2 = float(upper.iloc[i])
        sl = float(min(lower.iloc[i], close.iloc[i]) - 1.5 * a5)
        sl = min(sl, entry - a5)
        risk = entry - sl
        if risk <= 0 or tp1 <= entry:
            continue
        signals.append(TradeSignal(
            direction="LONG", entry_price=entry, stop_loss=sl,
            tp1_price=tp1, tp2_price=tp2, risk_points=risk,
            entry_time=t, session_name="GLOBEX",
            metadata={"tp1_anchor": tp1_anchor},
        ))
    return signals


# ----------------------------------------------------------------------------
# ST engine (clone of supertrend_intraday_cost run_one, trade-level detail)
# ----------------------------------------------------------------------------
def supertrend(high, low, close, period, mult):
    hl2 = (high + low) / 2.0
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    fu = upper.copy()
    fl = lower.copy()
    for i in range(1, len(upper)):
        if fu.iloc[i] > fu.iloc[i - 1]:
            fu.iloc[i] = fu.iloc[i - 1]
        if fl.iloc[i] < fl.iloc[i - 1]:
            fl.iloc[i] = fl.iloc[i - 1]
    st = pd.Series(np.nan, index=close.index)
    for i in range(1, len(close)):
        if close.iloc[i] > fu.iloc[i - 1]:
            st.iloc[i] = 1
        elif close.iloc[i] < fl.iloc[i - 1]:
            st.iloc[i] = -1
        else:
            st.iloc[i] = st.iloc[i - 1]
    return st


def run_st_trades(df1: pd.DataFrame, df5: pd.DataFrame, unique_dates, period=14, mult=2.0,
                  trail_mult=1.5, point_val=5.0) -> pd.DataFrame:
    trades = []
    for t_date in unique_dates:
        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5 or ts.year < 2025:
            continue
        ctx = build_day_context(ts, df1, df5, daily_atr_of(df1), ib_minutes=30)
        if ctx is None:
            continue
        bars5 = ctx.day_bars_5m
        if bars5 is None or len(bars5) < period + 5:
            continue
        close = bars5["close"]; high = bars5["high"]; low = bars5["low"]
        st = supertrend(high, low, close, period, mult)
        atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14
        pos = 0; entry = 0.0; stop = 0.0; entry_t = None
        for i in range(1, len(bars5)):
            a5 = atr5.iloc[i]
            if np.isnan(a5) or a5 <= 0:
                continue
            st0, st1 = st.iloc[i], st.iloc[i - 1]
            if pd.isna(st0) or pd.isna(st1):
                continue
            c0, h0, l0 = close.iloc[i], high.iloc[i], low.iloc[i]
            if pos == 1:
                stop = max(stop, h0 - trail_mult * a5)
                if l0 <= stop:
                    trades.append({"date": str(ts.date()), "entry_time": entry_t, "exit_time": bars5.index[i],
                                   "total_pnl_dollars": (stop - entry) * point_val, "engine": "ST"})
                    pos = 0
            elif pos == -1:
                stop = min(stop, l0 + trail_mult * a5)
                if h0 >= stop:
                    trades.append({"date": str(ts.date()), "entry_time": entry_t, "exit_time": bars5.index[i],
                                   "total_pnl_dollars": (entry - stop) * point_val, "engine": "ST"})
                    pos = 0
            if pos == 0:
                if st0 == 1 and st1 == -1:
                    pos = 1; entry = c0; stop = entry - trail_mult * a5; entry_t = bars5.index[i]
                elif st0 == -1 and st1 == 1:
                    pos = -1; entry = c0; stop = entry + trail_mult * a5; entry_t = bars5.index[i]
    return pd.DataFrame(trades)


_ATR_CACHE = {}
def daily_atr_of(df1: pd.DataFrame) -> pd.Series:
    key = id(df1)
    if key not in _ATR_CACHE:
        d = df1.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        tr = pd.concat([d["high"] - d["low"], (d["high"] - d["close"].shift(1)).abs(),
                        (d["low"] - d["close"].shift(1)).abs()], axis=1).max(axis=1)
        _ATR_CACHE[key] = tr.rolling(10, min_periods=1).mean()
    return _ATR_CACHE[key]


def summarize(pnl: pd.Series) -> dict:
    if len(pnl) == 0:
        return dict(trades=0, wr=0, pf=0, net=0, dd=0)
    cum = pnl.cumsum()
    dd = (cum - cum.cummax()).min()
    gp, gl = pnl[pnl > 0].sum(), abs(pnl[pnl < 0].sum())
    return dict(trades=len(pnl), wr=round((pnl > 0).mean() * 100, 1),
                pf=round(gp / gl, 2) if gl > 0 else 999.0,
                net=round(pnl.sum()), dd=round(abs(dd)))


# ----------------------------------------------------------------------------
def main():
    print("Loading NT MergeBA ES...")
    df1, df5 = load_nt("ES")
    daily_atr = daily_atr_of(df1)
    df1["trade_date"] = df1.index.date
    evening = df1.index.hour >= 18
    df1.loc[evening, "trade_date"] = (df1.loc[evening].index + pd.Timedelta(days=1)).date
    unique_dates = sorted(df1["trade_date"].unique())

    engine = BacktestEngine("ES", tick_size=0.25, entry_mode="market")

    # ------------------------------------------------------------------ E33
    print("\n" + "=" * 78)
    print("E33 — TP1 anchor comparison (E22 entry, overnight full block, 1 trade/hour/day)")
    print("=" * 78)
    arms = {"E22_midband": "midband", "E33a_vwap": "vwap", "E33b_dayvwap": "dayvwap"}
    e33_trades = {}
    for label, anchor in arms.items():
        all_t = []
        for k, t_date in enumerate(unique_dates):
            ts = pd.Timestamp(t_date)
            if ts.weekday() >= 5 or ts.year < 2025 or ts.year > 2026:
                continue
            ctx = build_day_context(ts, df1, df5, daily_atr, ib_minutes=30)
            if ctx is None:
                continue
            bars_gx = ctx.session_5m.get("GLOBEX")
            if bars_gx is None:
                continue
            # progressive VWAP for anchor (GLOBEX session, zero-lookahead via ctx's precomputed series)
            vwap_series = ctx.progressive_vwap.get("GLOBEX")
            if anchor in ("vwap", "dayvwap") and vwap_series is None:
                continue
            sigs = scan_e22_anchored(bars_gx, anchor, progressive_vwap_5m=vwap_series)
            used_hours = set()
            for sig in sigs:
                if sig.entry_time.hour not in (set(range(19, 24)) | set(range(0, 8))):
                    continue
                if sig.entry_time.hour in used_hours:
                    continue
                used_hours.add(sig.entry_time.hour)
                sig.metadata["strategy_name"] = label
                res = engine.simulate_trade(sig, ctx)
                if res is not None:
                    res.strategy_name = label
                    all_t.append(res.__dict__.copy())
        e33_trades[label] = pd.DataFrame(all_t)
        s = summarize(e33_trades[label]["total_pnl_dollars"]) if all_t else dict(trades=0, wr=0, pf=0, net=0, dd=0)
        print(f"  {label:<14} {s['trades']:>4} trades  WR{s['wr']:5.1f}%  PF{s['pf']:5.2f}  "
              f"Net${s['net']:>6.0f}  DD${s['dd']:>5.0f}")

    # ------------------------------------------------------------------ E31
    print("\n" + "=" * 78)
    print("E31 — Two-engine portfolio: E22 (BB reversion) + ST(14,2) trail 1.5xATR")
    print("=" * 78)
    # E22 trade series (exact E22 config: full overnight block, band exits)
    e22_t = e33_trades["E22_midband"].copy()
    st_t = run_st_trades(df1, df5, unique_dates)

    e22_daily = e22_t.groupby(pd.to_datetime(e22_t["exit_time"]).dt.date)["total_pnl_dollars"].sum()
    st_daily = st_t.groupby(pd.to_datetime(st_t["exit_time"]).dt.date)["total_pnl_dollars"].sum()
    cal = pd.date_range("2025-01-01", "2026-08-31", freq="D").date
    e22_d = e22_daily.reindex(cal, fill_value=0.0).fillna(0.0)
    st_d = st_daily.reindex(cal, fill_value=0.0).fillna(0.0)

    corr = e22_d.corr(st_d)
    comb_d = e22_d + st_d
    s_e22, s_st, s_comb = summarize(e22_d), summarize(st_d), summarize(comb_d)
    print(f"  E22 alone : {s_e22['trades']:>4}d active  WR{s_e22['wr']:5.1f}%  PF{s_e22['pf']:5.2f}  Net${s_e22['net']:>6.0f}  DD${s_e22['dd']:>5.0f}")
    print(f"  ST alone  : {s_st['trades']:>4}d active  WR{s_st['wr']:5.1f}%  PF{s_st['pf']:5.2f}  Net${s_st['net']:>6.0f}  DD${s_st['dd']:>5.0f}")
    print(f"  Combined  : {'':>10} WR{s_comb['wr']:5.1f}%  PF{s_comb['pf']:5.2f}  Net${s_comb['net']:>6.0f}  DD${s_comb['dd']:>5.0f}")
    print(f"  Daily-return correlation: {corr:+.3f}")
    print(f"  DD diversification: combined ${s_comb['dd']} vs max(single) ${max(s_e22['dd'], s_st['dd'])}")

    # prop sim on combined (10xMES scale, same honest convention as E27)
    combined_pnl = st_t["total_pnl_dollars"].tolist() + e22_t["total_pnl_dollars"].tolist()
    td = pd.DataFrame({
        "exit_time": st_t["exit_time"].tolist() + e22_t["exit_time"].tolist(),
        "pnl_pct": np.array(combined_pnl) / 50_000.0 * 100.0 * 10,
    }).sort_values("exit_time").reset_index(drop=True)
    sim = PropFirmSimulator(account_size=50_000.0, point_value=5.0)
    for key in ["apex_50k", "topstep_50k", "ftmo_50k"]:
        mc = sim.run_monte_carlo(td, FIRM_PROFILES[key], n_simulations=5000)
        det = sim.run_deterministic(td, FIRM_PROFILES[key])
        print(f"  {FIRM_PROFILES[key].name:<14} pass {mc.pass_rate_pct:5.1f}% (grade {mc.grade})  "
              f"blow {mc.blow_rate_pct:5.1f}%  det-passed {det.passed}")

    e22_t.to_csv("data/derived/bb_e31_e22_trades.csv", index=False)
    st_t.to_csv("data/derived/bb_e31_st_trades.csv", index=False)
    print("\nSaved data/derived/bb_e31_e22_trades.csv + bb_e31_st_trades.csv")


if __name__ == "__main__":
    main()