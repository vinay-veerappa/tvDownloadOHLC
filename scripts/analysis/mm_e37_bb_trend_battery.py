"""E37 — Bollinger Bands as a TREND strategy (not mean reversion).

Inverts the E32 falsification ladder: E32 varied entries under BAD fixed exits.
E37 varies entries under the PROVEN-GOOD exit (Supertrend-parity 1.5xATR trail, the
incumbent trend engine's geometry) and separately varies exits under one fixed entry.
If entries were meaningless (E32's conclusion), T-arms should all hover at ST-parity
levels. If any entry stack beats ST on net or DD, it earns a seat test.

Arms:
  T0   time-only negative control: enter every N bars, trail exit (expect ~0 or loss)
  T1   band-break only (close beyond band, no squeeze)
  T2   squeeze + band-break (BBW below p20 of trailing 100, then close outside band)
  T3   T2 + strict HH/HL structure gate (E36-proven gate)
  T4   T3 with Keltner(20, 2.0) instead of BB (ATR-band A/B)
  EL1  fixed T2 entries, midband-recross exit (close back through SMA20)
  EL2  fixed T2 entries, opposite-band exit
  EL3  fixed T2 entries, 1.5xATR trail (= T2 reference, printed for the ladder)

All arms: ES 5m, both directions, 1 trade/hour/day frequency cap, 16:00 flat,
next-open fill, 2-15 bps risk bracket, micro sizing ($5/pt), ST(14,2) incumbent
recomputed inline for head-to-head.

Usage:
  .\\.venv\\Scripts\\python.exe scripts/analysis/mm_e37_bb_trend_battery.py
"""
from __future__ import annotations

import sys
import warnings
from typing import Dict, List, Optional

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

import numpy as np
import pandas as pd

from scripts.analysis.bb_e16_e21_queue import load_nt
from scripts.analysis.range_strategy_comparison import _adx  # noqa: F401 (unused, reference parity)

warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------
def atr_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - df["close"].shift(1)).abs(),
                    (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def band_envelopes(high: pd.Series, low: pd.Series, close: pd.Series,
                   period: int = 20, n_std: float = 2.0,
                   keltner: bool = False, atr_mult: float = 2.0):
    """Bollinger (std) or Keltner (ATR) channel around SMA20."""
    mid = close.rolling(period).mean()
    if keltner:
        a = atr_wilder(pd.DataFrame({"high": high, "low": low, "close": close}), period)
        up, lo = mid + atr_mult * a, mid - atr_mult * a
    else:
        sd = close.rolling(period).std(ddof=1).clip(lower=1e-12)
        up, lo = mid + n_std * sd, mid - n_std * sd
    return mid, up, lo


def bbw_percentile(close: pd.Series, period: int = 20, n_std: float = 2.0,
                   lookback: int = 100) -> pd.Series:
    """Bandwidth percentile vs trailing window (causal)."""
    mid = close.rolling(period).mean()
    sd = close.rolling(period).std(ddof=1).clip(lower=1e-12)
    bw = (2 * n_std * sd) / mid
    return bw.rolling(lookback, min_periods=lookback // 2).rank(pct=True)


def hhhl_gate(high: pd.Series, low: pd.Series, piv_len: int = 3) -> pd.Series:
    """Strict HH/HL structure gate (E36 semantics): last two confirmed pivot lows
    ascending AND last two pivot highs ascending. Vectorized via pivot markers."""
    n = len(high)
    h = high.to_numpy(float)
    l = low.to_numpy(float)
    gate = pd.Series(False, index=high.index)
    gate_dn = pd.Series(False, index=high.index)
    hi_piv: List[tuple] = []
    lo_piv: List[tuple] = []
    last_eval = 0
    for j in range(piv_len, n - piv_len):
        w = h[j - piv_len: j + piv_len + 1]
        if h[j] == w.max() and int(np.argmax(w)) == piv_len:
            hi_piv.append((j, h[j]))
        w = l[j - piv_len: j + piv_len + 1]
        if l[j] == w.min() and int(np.argmin(w)) == piv_len:
            lo_piv.append((j, l[j]))
    # reconstruct gate per bar
    hi_p = []
    lo_p = []
    hi_i = lo_i = 0
    for i in range(n):
        while hi_i < len(hi_piv) and hi_piv[hi_i][0] + piv_len <= i:
            hi_p.append(hi_piv[hi_i])
            hi_i += 1
        while lo_i < len(lo_piv) and lo_piv[lo_i][0] + piv_len <= i:
            lo_p.append(lo_piv[lo_i])
            lo_i += 1
        if len(hi_p) >= 2 and len(lo_p) >= 2:
            up = hi_p[-1][1] > hi_p[-2][1] and lo_p[-1][1] > lo_p[-2][1]
            dn = hi_p[-1][1] < hi_p[-2][1] and lo_p[-1][1] < lo_p[-2][1]
            gate.iloc[i] = up
            gate_dn.iloc[i] = dn
    return gate, gate_dn


# ---------------------------------------------------------------------------
# Entry stacks
# ---------------------------------------------------------------------------
def entry_signals(bars5: pd.DataFrame, mode: str,
                  bb_period: int = 20, n_std: float = 2.0) -> list:
    """Return list of (time, direction) entry triggers for the mode.
    All evaluated on bar close, next-open fill by simulator."""
    if len(bars5) < bb_period + 60:
        return []
    c = bars5["close"]
    hi = bars5["high"]
    lo = bars5["low"]
    mid, up, lo_b = band_envelopes(hi, lo, c, bb_period, n_std)
    mid_k, up_k, lo_k = band_envelopes(hi, lo, c, bb_period, keltner=True, atr_mult=2.0)
    squeeze = bbw_percentile(c, bb_period, n_std) <= 0.20
    gate_up, gate_dn = hhhl_gate(hi, lo)

    sigs = []
    last_t = None
    for i in range(bb_period + 10, len(bars5)):
        t = bars5.index[i]
        if last_t is not None and (t - last_t) < pd.Timedelta(minutes=60):
            continue  # 1/hour frequency cap
        if pd.isna(up.iloc[i]):
            continue
        up_break = c.iloc[i] > up.iloc[i] and c.iloc[i - 1] <= up.iloc[i - 1]
        lo_break = c.iloc[i] < lo_b.iloc[i] and c.iloc[i - 1] >= lo_b.iloc[i - 1]
        up_break_k = c.iloc[i] > mid_k.iloc[i] + 2.0 * (mid_k.iloc[i] - lo_k.iloc[i]) / 2.0  # not used; placeholder
        mode_dir = None
        if mode == "T1":
            if up_break:
                mode_dir = 1
            elif lo_break:
                mode_dir = -1
        elif mode == "T2":
            sq = bool(squeeze.iloc[max(0, i - lookback_sq_window(bars5))]) if False else bool(squeeze.iloc[i - 6: i + 1].any())
            if sq and up_break:
                mode_dir = 1
            elif sq and lo_break:
                mode_dir = -1
        elif mode == "T3":
            sq = bool(squeeze.iloc[i - 6: i + 1].any())
            if sq and up_break and bool(gate_up.iloc[i]):
                mode_dir = 1
            elif sq and lo_break and bool(gate_dn.iloc[i]):
                mode_dir = -1
        elif mode == "T4":
            # Keltner channel break (ATR bands), no squeeze. Recomputed per day
            # inside band_envelopes; reuse the precomputed series instead.
            if c.iloc[i] > mid_k.iloc[i] + (mid_k.iloc[i] - lo_k.iloc[i]):
                mode_dir = 1
            elif c.iloc[i] < lo_k.iloc[i]:
                mode_dir = -1
        if mode_dir is not None:
            sigs.append((t, "LONG" if mode_dir > 0 else "SHORT"))
            last_t = t
    return sigs


def lookback_sq_window(bars5):
    return 6


def up_k(hi, lo, c, i):
    mid, up, lo_b = band_envelopes(hi, lo, c, keltner=True, atr_mult=2.0)
    return up.iloc[i]


def dn_k(hi, lo, c, i):
    mid, up, lo_b = band_envelopes(hi, lo, c, keltner=True, atr_mult=2.0)
    return lo_b.iloc[i]


# ---------------------------------------------------------------------------
# Exit engines (fixed T2-style entry stream, exit varies)
# ---------------------------------------------------------------------------
def run_trade(bars5: pd.DataFrame, t_entry: str, direction: str,
              exit_mode: str, trail_mult: float = 1.5,
              atr_period: int = 14, bb_period: int = 20, n_std: float = 2.0,
              pt_val: float = 5.0) -> Optional[dict]:
    t0 = pd.Timestamp(t_entry)
    i0 = bars5.index.get_loc(t0)
    if i0 is None or i0 + 1 >= len(bars5):
        return None
    is_long = direction == "LONG"
    entry = float(bars5["open"].iloc[i0 + 1])
    a_s = atr_wilder(bars5, atr_period)
    stop = entry - trail_mult * float(a_s.iloc[i0]) if is_long else entry + trail_mult * float(a_s.iloc[i0])
    risk = abs(entry - stop)
    if risk <= 0 or np.isnan(risk):
        return None

    mid, up, lo_b = band_envelopes(bars5["high"], bars5["low"], bars5["close"], bb_period, n_std)
    exit_price = None
    exit_reason = None
    exit_t = None
    for j in range(i0 + 1, len(bars5)):
        h = float(bars5["high"].iloc[j])
        l = float(bars5["low"].iloc[j])
        cl = float(bars5["close"].iloc[j])
        a = float(a_s.iloc[j])
        # trail update (ST-parity: only in favorable direction)
        if is_long:
            stop = max(stop, h - trail_mult * a)
            if l <= stop:
                exit_price, exit_reason, exit_t = stop, "TRAIL", bars5.index[j]
                break
        else:
            stop = min(stop, l + trail_mult * a)
            if h >= stop:
                exit_price, exit_reason, exit_t = stop, "TRAIL", bars5.index[j]
                break
        if exit_mode == "midband":
            if is_long and cl < mid.iloc[j]:
                exit_price, exit_reason, exit_t = cl, "MIDBAND", bars5.index[j]
                break
            if not is_long and cl > mid.iloc[j]:
                exit_price, exit_reason, exit_t = cl, "MIDBAND", bars5.index[j]
                break
        elif exit_mode == "opposite_band":
            if is_long and cl < lo_b.iloc[j]:
                exit_price, exit_reason, exit_t = cl, "OPPBAND", bars5.index[j]
                break
            if not is_long and cl > up.iloc[j]:
                exit_price, exit_reason, exit_t = cl, "OPPBAND", bars5.index[j]
                break
    if exit_price is None:
        exit_price = float(bars5["close"].iloc[-1])
        exit_reason, exit_t = "EOD", bars5.index[-1]
    move = (exit_price - entry) if is_long else (entry - exit_price)
    return {
        "date": str(t0.date()),
        "direction": direction,
        "entry_time": t0,
        "exit_time": exit_t,
        "exit_reason": exit_reason,
        "entry": entry,
        "exit_price": exit_price,
        "risk_points": risk,
        "pnl_pts": move,
        "pnl_dollars": move * pt_val,
    }


# ---------------------------------------------------------------------------
def run_arm(df1: pd.DataFrame, df5: pd.DataFrame, mode: str, exit_mode: str,
            only_sessions: Optional[tuple] = None) -> pd.DataFrame:
    df1 = df1.copy()
    df1["trade_date"] = df1.index.date
    evening = df1.index.hour >= 18
    df1.loc[evening, "trade_date"] = (df1.loc[evening].index + pd.Timedelta(days=1)).date
    dates = sorted(df1["trade_date"].unique())

    rows = []
    for d in dates:
        ts = pd.Timestamp(d)
        if ts.weekday() >= 5 or ts.year < 2025:
            continue
        start = pd.Timestamp(f"{(ts - pd.Timedelta(days=1)).date()} 18:00:00")
        end = pd.Timestamp(f"{ts.date()} 16:00:00")
        bars5 = df5.loc[start:end]
        if len(bars5) < 120:
            continue
        for t, drc in entry_signals(bars5, mode):
            res = run_trade(bars5, t, drc, exit_mode)
            if res:
                rows.append(res)
    return pd.DataFrame(rows)


def summarize(tdf) -> dict:
    """Accepts a trade DataFrame OR a daily PnL Series."""
    if tdf is None or len(tdf) == 0:
        return dict(trades=0, wr=0.0, pf=0.0, net=0.0, dd=0.0)
    if isinstance(tdf, pd.Series):
        pnl = tdf
    else:
        pnl = tdf["pnl_dollars"]
    cum = pnl.cumsum()
    dd = (cum - cum.cummax()).min()
    gp, gl = pnl[pnl > 0].sum(), abs(pnl[pnl < 0].sum())
    return dict(trades=len(tdf), wr=round((pnl > 0).mean() * 100, 1),
                pf=round(gp / gl, 2) if gl > 0 else 999.0,
                net=round(pnl.sum()), dd=round(abs(dd)))


def print_arm(tag: str, label: str, tdf: pd.DataFrame):
    s = summarize(tdf)
    if len(tdf):
        sp = summarize(tdf[tdf["direction"] == "LONG"])
        ss = summarize(tdf[tdf["direction"] == "SHORT"])
        print(f"  {tag:<4} {label:<44} {s['trades']:>5}  WR{s['wr']:5.1f}%  PF{s['pf']:5.2f}  "
              f"Net${s['net']:>7.0f}  DD${s['dd']:>5.0f}   [L {sp['pf']:5.2f}/{sp['trades']}  S {ss['pf']:5.2f}/{ss['trades']}]")
    else:
        print(f"  {tag:<4} {label:<44} 0 trades")
    return s


def st_incumbent(df1: pd.DataFrame, df5: pd.DataFrame) -> pd.DataFrame:
    """Supertrend(14,2) + 1.5xATR trail head-to-head, same bars, same caps."""
    rows = []
    df1 = df1.copy()
    df1["trade_date"] = df1.index.date
    evening = df1.index.hour >= 18
    df1.loc[evening, "trade_date"] = (df1.loc[evening].index + pd.Timedelta(days=1)).date
    dates = sorted(df1["trade_date"].unique())

    def supertrend(high, low, close, period, mult):
        hl2 = (high + low) / 2.0
        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        upper = hl2 + mult * atr
        lower = hl2 - mult * atr
        fu, fl = upper.copy(), lower.copy()
        for i in range(1, len(upper)):
            if fu.iloc[i] < fu.iloc[i - 1]:
                fu.iloc[i] = fu.iloc[i - 1]
            if fl.iloc[i] > fl.iloc[i - 1]:
                fl.iloc[i] = fl.iloc[i - 1]
        st = pd.Series(np.nan, index=close.index)
        for i in range(1, len(close)):
            if close.iloc[i] > upper.iloc[i - 1]:
                st.iloc[i] = 1
            elif close.iloc[i] < lower.iloc[i - 1]:
                st.iloc[i] = -1
            else:
                st.iloc[i] = st.iloc[i - 1]
        return st

    for d in dates:
        ts = pd.Timestamp(d)
        if ts.weekday() >= 5 or ts.year < 2025:
            continue
        start = pd.Timestamp(f"{(ts - pd.Timedelta(days=1)).date()} 18:00:00")
        end = pd.Timestamp(f"{ts.date()} 16:00:00")
        bars5 = df5.loc[start:end]
        if len(bars5) < 40:
            continue
        c = bars5["close"]
        st = supertrend(bars5["high"], bars5["low"], c, 14, 2.0)
        a = atr_wilder(bars5, 14)
        pos = 0
        entry = stop = 0.0
        e_t = None
        for i in range(1, len(bars5)):
            if pd.isna(st.iloc[i]) or pd.isna(st.iloc[i - 1]) or pd.isna(a.iloc[i]):
                continue
            ai = float(a.iloc[i])
            if ai <= 0:
                continue
            h, l = float(bars5["high"].iloc[i]), float(bars5["low"].iloc[i])
            if pos == 1:
                stop = max(stop, h - 1.5 * ai)
                if l <= stop:
                    rows.append({"date": str(ts.date()), "direction": "LONG",
                                 "entry_time": e_t, "exit_time": bars5.index[i],
                                 "exit_reason": "TRAIL", "entry": entry, "exit_price": stop,
                                 "risk_points": abs(entry - stop),
                                 "pnl_pts": stop - entry, "pnl_dollars": (stop - entry) * 5.0})
                    pos = 0
            elif pos == -1:
                stop = min(stop, l + 1.5 * ai)
                if h >= stop:
                    rows.append({"date": str(ts.date()), "direction": "SHORT",
                                 "entry_time": e_t, "exit_time": bars5.index[i],
                                 "exit_reason": "TRAIL", "entry": entry, "exit_price": stop,
                                 "risk_points": abs(entry - stop),
                                 "pnl_pts": entry - stop, "pnl_dollars": (entry - stop) * 5.0})
                    pos = 0
            if pos == 0:
                if st.iloc[i] == 1 and st.iloc[i - 1] == -1:
                    pos, entry, stop, e_t = 1, float(c.iloc[i]), float(c.iloc[i]) - 1.5 * ai, bars5.index[i]
                elif st.iloc[i] == -1 and st.iloc[i - 1] == 1:
                    pos, entry, stop, e_t = -1, float(c.iloc[i]), float(c.iloc[i]) + 1.5 * ai, bars5.index[i]
    return pd.DataFrame(rows)


def main():
    print("E37 — BB-as-TREND battery (ES 5m, ST-parity exits, 1/hour/day, 16:00 flat)")
    df1, df5 = load_nt("ES")

    print("\n== Arms under identical 1.5xATR trail exits ==")
    res = {}
    run_cache = {}
    run_cache["T1"] = run_arm(df1, df5, "T1", "trail")
    run_cache["T2"] = run_arm(df1, df5, "T2", "trail")
    run_cache["T3"] = run_arm(df1, df5, "T3", "trail")
    res["T1"] = print_arm("T1", "band-break only", run_cache["T1"])
    res["T2"] = print_arm("T2", "squeeze + band-break", run_cache["T2"])
    res["T3"] = print_arm("T3", "squeeze + break + HH/HL gate", run_cache["T3"])

    print("\n== Exit ladder on fixed squeeze+break entries ==")
    run_cache["EL1"] = run_arm(df1, df5, "T2", "midband")
    run_cache["EL2"] = run_arm(df1, df5, "T2", "opposite_band")
    res["EL1"] = print_arm("EL1", "T2 entries / midband-recross exit", run_cache["EL1"])
    res["EL2"] = print_arm("EL2", "T2 entries / opposite-band exit", run_cache["EL2"])
    res["EL3"] = print_arm("EL3", "T2 entries / 1.5xATR trail (ref)", run_cache["T2"])  # same run

    print("\n== Keltner A/B (channel family): band-break under trail ==")
    run_cache["T4"] = run_arm(df1, df5, "T4", "trail")
    res["T4"] = print_arm("T4", "Keltner(20, 2.0xATR) break", run_cache["T4"])

    print("\n== Incumbent head-to-head + correlation ==")
    st_t = st_incumbent(df1, df5)
    s_st = summarize(st_t)
    print(f"  ST    Supertrend(14,2) 1.5xATR            {s_st['trades']:>5}  WR{s_st['wr']:5.1f}%  PF{s_st['pf']:5.2f}  "
          f"Net${s_st['net']:>7.0f}  DD${s_st['dd']:>5.0f}   [L {summarize(st_t[st_t['direction']=='LONG'])['pf']:5.2f}  "
          f"S {summarize(st_t[st_t['direction']=='SHORT'])['pf']:5.2f}]")

    best = max([k for k in ("T1", "T2", "T3", "T4") if k in res and len(res[k])], key=lambda k: res[k]["pf"], default=None) if any(len(res.get(k, pd.DataFrame())) for k in ("T1", "T2", "T3", "T4")) else None
    if best:
        best_t = [r for r in [None]]
        bt = run_arm(df1, df5, {"T1": "T1", "T2": "T2", "T3": "T3", "T4": "T4"}[best], "trail")
        cal = pd.date_range("2025-01-01", "2026-08-31", freq="D").date
        b_daily = bt.groupby(pd.to_datetime(bt["exit_time"]).dt.date)["pnl_dollars"].sum().reindex(cal, fill_value=0.0)
        s_daily = st_t.assign(d=pd.to_datetime(st_t["exit_time"]).dt.date).groupby("d")["pnl_dollars"].sum().reindex(cal, fill_value=0.0)
        print(f"\n  corr({best}, ST) daily: {b_daily.corr(s_daily):+.3f}")
        comb = b_daily + s_daily
        sc = summarize(comb)
        print(f"  combined: PF{sc['pf']:5.2f}  Net${sc['net']:>7.0f}  DD${sc['dd']:>5.0f}")

    frames = []
    for k in ("T1", "T2", "T3", "T4", "EL1", "EL2", "EL3"):
        if k in run_cache and len(run_cache[k]):
            frames.append(run_cache[k].assign(arm=k))
    if len(st_t):
        frames.append(st_t.assign(arm="ST"))
    if frames:
        pd.concat(frames, ignore_index=True).to_csv("data/derived/mm_e37_es_trade_detail.csv", index=False)
        print("\nSaved data/derived/mm_e37_es_trade_detail.csv")


if __name__ == "__main__":
    main()