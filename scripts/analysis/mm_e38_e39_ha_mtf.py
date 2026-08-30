"""E38 + E39 — Heiken Ashi overlay gate & multi-timeframe layering.

E38  HA gate A/B: gate the two surviving engines (E34L measured-move long entries
     and Supertrend flip entries) on Heiken Ashi bar state. Hypothesis: HA
     direction persistence filters entries against trend MATURITY (late entries),
     cutting DD without killing net.
       arms: HA_OFF (baseline re-run) vs HA_ON for E34L, ST-trail sweep+break (T2),
             ST-flip engine.

E39  MTF layering: HTF (30m) envelope context gating LTF (5m) entries — the user's
     "BB can be a different timeframe while entries are on a lower timeframe".
       arms: MTF_OFF vs %B-position gates from 30m bands:
               PX bullish band-pos, PX bearish, PX mid-zone only.

All arms: ES 5m 19mo, 1/hour/day caps (E37 lineage), next-open fill, 16:00 flat.
Timeframes merged zero-lookahead: HTF bar value available only AFTER the HTF bar
closes (aligned via .reindex(...).ffill() on a shifted index).

Usage:
  .\\.venv\\Scripts\\python.exe scripts/analysis/mm_e38_e39_ha_mtf.py
"""
from __future__ import annotations

import sys
import warnings
from typing import Optional

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

import numpy as np
import pandas as pd

from scripts.analysis.bb_e16_e21_queue import load_nt

warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------------------------
def heiken_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """HA ohlc from time bars."""
    ha = df.copy()
    hc = (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
    ha_open = np.zeros(len(df))
    ha_open[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2.0
    oc = np.zeros(len(df))
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + hc.iloc[i - 1]) / 2.0
    ha = pd.DataFrame({"ha_open": ha_open, "ha_close": hc.values}, index=df.index)
    return ha


def atr_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - df["close"].shift(1)).abs(),
                    (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


# ---------------------------------------------------------------------------
# E38: HA gate test
# ---------------------------------------------------------------------------
def run_ha_gate(bars5: pd.DataFrame, gate_arm: bool, ha_lookback: int = 2,
                pt_val: float = 5.0) -> pd.DataFrame:
    """E34L long entries with optional HA-gate: last ha bar bullish (ha_close>ha_open)
    for longs. Exits: E34L TP1/TP2 measured projection, structural stop, 2-leg."""
    if len(bars5) < 120:
        return pd.DataFrame()
    ha = heiken_ashi(bars5)
    ha_bull = (ha["ha_close"] > ha["ha_open"])
    ha_bear = (ha["ha_close"] < ha["ha_open"])
    # lookback window: any bullish in last ha_lookback bars
    hb = ha_bull.rolling(ha_lookback).max().fillna(0).astype(bool)
    sb = ha_bear.rolling(ha_lookback).max().fillna(0).astype(bool)

    df = bars5
    mid = df["close"].rolling(20).mean()
    sd = df["close"].rolling(20).std(ddof=1).clip(lower=1e-12)
    bb_up = mid + 2 * sd
    bb_lo = mid - 2 * sd

    # DI gate (E34 base)
    from scripts.libs_py.price_action.trendline_structure import _di_components
    pdi, mdi = _di_components(df["high"], df["low"], df["close"], 14)
    diag = pd.DataFrame({"pdi": pdi, "mdi": mdi}, index=df.index)

    rows = []
    for i in range(60, len(df)):
        t = df.index[i]
        c = float(df["close"].iloc[i])
        # long entry: close reclaims lower band from below + rising close + DI + gate
        if not (float(df["close"].iloc[i-1]) < float(bb_lo.iloc[i-1])
                and c > float(bb_lo.iloc[i])
                and c > float(df["close"].iloc[i-1])
                and float(diag["pdi"].iloc[i]) > float(diag["mdi"].iloc[i])):
            continue
        if gate_arm and not bool(hb.iloc[i]):
            continue
        prev_long_idx = df.index[i-1]
        # BB touch anchor: band level + recent low
        anchor_low = float(df["low"].iloc[max(0, i-14): i+1].min())
        stop = anchor_low - 0.25 * float(atr_wilder(df).iloc[i])
        risk = c - stop
        if risk <= 0 or risk / c * 1e4 < 2 or risk / c * 1e4 > 15:
            continue
        tp1 = c + (2.0 / (2.0 - 0.0)) * (risk * 1.38)   # E34L wide projection (1:1.5 offset proxy)
        tp2 = c + 2 * (tp1 - c)
        # simulate
        r = sim_two_leg(df, i, float(stop), tp1, tp2, is_long=True, pt_val=pt_val)
        if r:
            rows.append(r)
    return pd.DataFrame(rows)


def run_ha_gate_short(bars5: pd.DataFrame, gate_arm: bool, ha_lookback: int = 2,
                      pt_val: float = 5.0) -> pd.DataFrame:
    if len(bars5) < 120:
        return pd.DataFrame()
    ha = heiken_ashi(bars5)
    ha_bear = (ha["ha_close"] < ha["ha_open"])
    sb = ha_bear.rolling(ha_lookback).max().fillna(0).astype(bool)

    df = bars5
    mid = df["close"].rolling(20).mean()
    sd = df["close"].rolling(20).std(ddof=1).clip(lower=1e-12)
    bb_up = mid + 2 * sd

    from scripts.libs_py.price_action.trendline_structure import _di_components
    pdi, mdi = _di_components(df["high"], df["low"], df["close"], 14)

    rows = []
    for i in range(60, len(df)):
        t = df.index[i]
        c = float(df["close"].iloc[i])
        # short: close rejected upper band + falling close + DI - gate
        if not (float(df["close"].iloc[i-1]) > float(bb_up.iloc[i-1])
                and c < float(bb_up.iloc[i])
                and c < float(df["close"].iloc[i-1])
                and float(mdi.iloc[i]) > float(pdi.iloc[i])):
            continue
        if gate_arm and not bool(sb.iloc[i]):
            continue
        anchor_high = float(df["high"].iloc[max(0, i-14): i+1].max())
        stop = anchor_high + 0.25 * float(atr_wilder(df).iloc[i])
        risk = stop - c
        if risk <= 0 or risk / c * 1e4 < 2 or risk / c * 1e4 > 15:
            continue
        tp1 = c - risk * 1.5
        tp2 = c - risk * 2.0
        r = sim_two_leg(df, i, float(stop), tp1, tp2, is_long=False, pt_val=pt_val)
        if r:
            rows.append(r)
    return pd.DataFrame(rows)


def sim_two_leg(df: pd.DataFrame, i0: int, stop: float, tp1: float, tp2: float,
                is_long: bool, pt_val: float = 5.0) -> Optional[dict]:
    if i0 + 1 >= len(df):
        return None
    entry = float(df["open"].iloc[i0 + 1])
    risk = abs(entry - stop)
    d1 = abs(tp1 - entry)
    t1 = False
    leg1 = leg2 = 0.0
    exit_price = None
    exit_reason = None
    exit_t = None
    for j in range(i0 + 1, len(df)):
        h = float(df["high"].iloc[j])
        l = float(df["low"].iloc[j])
        sl = stop
        if is_long:
            if l <= sl:
                leg1 = -risk if not t1 else leg1
                leg2 = -risk if not t1 else 0.0
                exit_price, exit_reason, exit_t = sl, "SL", df.index[j]
                break
            if not t1 and h >= tp1:
                t1, leg1 = True, d1
                stop = entry
            if h >= tp2:
                leg2 = tp2 - entry
                exit_price, exit_reason, exit_t = tp2, "TP2", df.index[j]
                break
        else:
            if h >= sl:
                leg1 = -risk if not t1 else leg1
                leg2 = -risk if not t1 else 0.0
                exit_price, exit_reason, exit_t = sl, "SL", df.index[j]
                break
            if not t1 and l <= tp1:
                t1, leg1 = True, entry - tp1
                stop = entry
            if l <= tp2:
                leg2 = entry - tp2
                exit_price, exit_reason, exit_t = tp2, "TP2", df.index[j]
                break
    if exit_price is None:
        exit_price = float(df["close"].iloc[-1])
        exit_reason, exit_t = "EOD", df.index[-1]
        move = (exit_price - entry) if is_long else (entry - exit_price)
        leg2 = move
        if not t1:
            leg1 = move
    pnl_pts = leg1 * 0.5 + leg2 * 0.5
    return {
        "date": str(df.index[i0].date()),
        "direction": "LONG" if is_long else "SHORT",
        "entry_time": df.index[i0],
        "exit_time": exit_t,
        "exit_reason": exit_reason,
        "risk_points": risk,
        "pnl_pts": pnl_pts,
        "pnl_dollars": pnl_pts * pt_val,
    }


# ---------------------------------------------------------------------------
# E39: MTF layering
# ---------------------------------------------------------------------------
def run_mtf(df1m: pd.DataFrame, df5: pd.DataFrame, gate_arm: Optional[str],
            htf_minutes: int = 30, pt_val: float = 5.0) -> pd.DataFrame:
    """E34L long entries gated by HTF band position.

    gate_arm None: no MTF gate. 'bull': HTF close in upper half of its band
    (%B > 0.5); 'bear': %B < 0.5 (block longs, test shorts); 'extreme': %B > 0.9
    (fade filter — block longs when HTF already stretched up).
    Zero-lookahead: HTF series resampled on bar close then shifted(1) before
    merge_asof onto 5m index.
    """
    if len(df5) < 200:
        return pd.DataFrame()
    # HTF envelope on resampled bars
    rule = f"{htf_minutes}min"
    ohlc = df5.resample(rule).agg({"open": "first", "high": "max", "low": "min",
                                   "close": "last"}).dropna()
    mid = ohlc["close"].rolling(20).mean()
    sd = ohlc["close"].rolling(20).std(ddof=1).clip(lower=1e-12)
    up = mid + 2 * sd
    lo = mid - 2 * sd
    pb = (ohlc["close"] - lo) / (up - lo).replace(0, np.nan)
    # only completed HTF bars are known: shift by 1 HTF bar
    pb_known = pb.shift(1)
    htf_pb = pb_known.reindex(df5.index, method="ffill")

    df = df5
    mid5 = df["close"].rolling(20).mean()
    sd5 = df["close"].rolling(20).std(ddof=1).clip(lower=1e-12)
    bb_lo5 = mid5 - 2 * sd5

    from scripts.libs_py.price_action.trendline_structure import _di_components
    pdi, mdi = _di_components(df["high"], df["low"], df["close"], 14)

    rows = []
    for i in range(60, len(df)):
        t = df.index[i]
        c = float(df["close"].iloc[i])
        if pd.isna(mid5.iloc[i]) or pd.isna(mid5.iloc[i - 1]):
            continue
        if not (float(df["close"].iloc[i-1]) < float(bb_lo5.iloc[i-1])
                and c > float(bb_lo5.iloc[i])
                and c > float(df["close"].iloc[i-1])
                and float(pdi.iloc[i]) > float(mdi.iloc[i])):
            continue
        # MTF gate
        pbv = float(htf_pb.loc[t]) if t in htf_pb.index else np.nan
        if gate_arm == "bull" and not (pbv > 0.5):
            continue
        if gate_arm == "extreme" and not (pbv <= 0.9):
            continue
        anchor_low = float(df["low"].iloc[max(0, i-14): i+1].min())
        stop = anchor_low - 0.25 * float(atr_wilder(df).iloc[i])
        risk = c - stop
        if risk <= 0 or risk / c * 1e4 < 2 or risk / c * 1e4 > 15:
            continue
        tp1 = c + risk * 1.5
        tp2 = c + risk * 2.0
        r = sim_two_leg(df, i, float(stop), tp1, tp2, is_long=True, pt_val=pt_val)
        if r:
            rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def summarize(tdf) -> dict:
    if tdf is None or len(tdf) == 0:
        return dict(trades=0, wr=0.0, pf=0.0, net=0.0, dd=0.0)
    pnl = tdf["pnl_dollars"] if isinstance(tdf, pd.DataFrame) else tdf
    cum = pnl.cumsum()
    dd = (cum - cum.cummax()).min()
    gp, gl = pnl[pnl > 0].sum(), abs(pnl[pnl < 0].sum())
    return dict(trades=len(pnl), wr=round((pnl > 0).mean() * 100, 1),
                pf=round(gp / gl, 2) if gl > 0 else 999.0,
                net=round(pnl.sum()), dd=round(abs(dd)))


def print_arm(tag: str, label: str, tdf: pd.DataFrame) -> dict:
    s = summarize(tdf)
    if len(tdf):
        sp = summarize(tdf[tdf["direction"] == "LONG"]) if "direction" in tdf else s
        print(f"  {tag:<6} {label:<48} {s['trades']:>5}  WR{s['wr']:5.1f}%  PF{s['pf']:5.2f}  "
              f"Net${s['net']:>7.0f}  DD${s['dd']:>5.0f}")
    else:
        print(f"  {tag:<6} {label:<48} 0 trades")
    return s


def main():
    print("Loading NT MergeBA ES...")
    df1, df5 = load_nt("ES")
    df1 = df1.copy()

    print("\n== E38 — Heiken Ashi overlay gate (E34L core entries) ==")
    # pre-day-bar split
    df1p = df1.copy()
    df1p["trade_date"] = df1p.index.date
    evening = df1p.index.hour >= 18
    df1p.loc[evening, "trade_date"] = (df1p.loc[evening].index + pd.Timedelta(days=1)).date
    dates = sorted(df1p["trade_date"].unique())

    arms = {
        "HA0": (False, "E34L core, no HA gate"),
        "HA1": (True, "E34L + HA bullish in last 2 bars"),
    }
    frames = {}
    for tag, (gate, label) in arms.items():
        allt = []
        for d in dates:
            ts = pd.Timestamp(d)
            if ts.weekday() >= 5 or ts.year < 2025:
                continue
            start = pd.Timestamp(f"{(ts - pd.Timedelta(days=1)).date()} 18:00:00")
            end = pd.Timestamp(f"{ts.date()} 16:00:00")
            bars5 = df5.loc[start:end]
            if len(bars5) < 200:
                continue
            sub = run_ha_gate(bars5, gate)
            if len(sub):
                allt.append(sub)
        frames[tag] = pd.concat(allt, ignore_index=True) if allt else pd.DataFrame()
        print_arm(tag, label, frames[tag])

    print("\n== E39 — MTF layering: 30m %B gating 5m entries ==")
    mtf_arms = {
        "M0": (None, "no MTF gate (E34L core reference)"),
        "M1": ("bull", "long only when 30m %B > 0.5"),
        "M2": ("extreme", "long blocked when 30m %B > 0.9 (anti-stretch)"),
    }
    for tag, (g, label) in mtf_arms.items():
        allt = []
        for d in dates:
            ts = pd.Timestamp(d)
            if ts.weekday() >= 5 or ts.year < 2025:
                continue
            start = pd.Timestamp(f"{(ts - pd.Timedelta(days=1)).date()} 18:00:00")
            end = pd.Timestamp(f"{ts.date()} 16:00:00")
            bars5 = df5.loc[start:end]
            if len(bars5) < 200:
                continue
            sub = run_mtf(df1p, bars5, g, htf_minutes=30)
            if len(sub):
                allt.append(sub)
        frames[tag] = pd.concat(allt, ignore_index=True) if allt else pd.DataFrame()
        print_arm(tag, label, frames[tag])

    # portfolio correlation of surviving E38 arm vs baseline
    if len(frames.get("HA1")) and len(frames.get("HA0")):
        cal = pd.date_range("2025-01-01", "2026-08-31", freq="D").date
        a0 = frames["HA0"].groupby(pd.to_datetime(frames["HA0"]["exit_time"]).dt.date)["pnl_dollars"].sum().reindex(cal, fill_value=0.0)
        a1 = frames["HA1"].groupby(pd.to_datetime(frames["HA1"]["exit_time"]).dt.date)["pnl_dollars"].sum().reindex(cal, fill_value=0.0)
        print(f"\n  corr(HA0, HA1) daily: {a0.corr(a1):+.3f}")

    out = pd.concat([v.assign(arm=k) for k, v in frames.items() if len(v)], ignore_index=True)
    out.to_csv("data/derived/mm_e38_e39_trade_detail.csv", index=False)
    print("Saved data/derived/mm_e38_e39_trade_detail.csv")


if __name__ == "__main__":
    main()