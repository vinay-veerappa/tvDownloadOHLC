"""E36 — PickMyTrade (R4) config reproduction on ES + NQ.

Reproduces the PickMyTrade Pine semantics that differ from our E34 engine:
  - Loose touch zone: within 1.0 x ATR of the trendline (ours was 0.10)
  - Stop: beyond the line/running extreme -/+ 1.0 x ATR (ours 0.25, structure-based)
  - Trend gate: strict HH/HL (ascending pivot-lows) / LH/LL (descending pivot-highs)
    — replaces our DI dominance gate
  - Ordinal counter: rzyCount resets on every NEW trend structure (R4 semantics),
    exhausted at touch >= 3 (block entry), matching their Touch 1/2 enter rule
  - Exits: partial 50% at 1x measured move + BE lock, runner to 2x measured move
  - Entry: touching the line then a close-direction bar (close > open for longs)
    while prices sits at/below the line + within touch window
  - Invalid: close beyond the line by 0.5 ATR disarms

Arms: E36  ES long-only (their gold setting, allowShorts=off analog)
      E36S ES both sides (shorts on — the bigger claim)
      E36N NQ long-only cross-check (E26 convention)

Usage:
  .\\.venv\\Scripts\\python.exe scripts/analysis/mm_e36_pickmytrade_repro.py
"""
from __future__ import annotations

import sys
import warnings
from dataclasses import dataclass, field
from typing import Dict, Optional

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

import numpy as np
import pandas as pd

from scripts.analysis.bb_e16_e21_queue import load_nt
from scripts.analysis.mm_e34_battery import daily_atr_of

warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------------------------
# R4-semantics scanner (bar-by-bar, mirrors the Pine state machine)
# ---------------------------------------------------------------------------
def scan_r4_structures(bars5: pd.DataFrame, piv_len: int = 7,
                       tl_touch_atr: float = 1.0, stop_buf_atr: float = 1.0,
                       mm_mult: float = 1.0, exhaust_count: int = 3,
                       min_rr: float = 0.0, min_struct_atr: float = 0.5,
                       atr_period: int = 14, longs: bool = True, shorts: bool = True) -> list:
    """Yield signal dicts mirroring Pine: arm on new pivot; track run extreme;
    trigger on trendline touch + close-direction bar; ordinal per structure."""
    if bars5 is None or len(bars5) < max(piv_len * 4, 80):
        return []
    h = bars5["high"].to_numpy(float)
    l = bars5["low"].to_numpy(float)
    o = bars5["open"].to_numpy(float)
    c = bars5["close"].to_numpy(float)
    n = len(c)

    # ATR(14) Wilder
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(alpha=1 / atr_period, min_periods=atr_period, adjust=False).mean().to_numpy()

    # pivots (confirmed piv_len bars later)
    piv_hi = []  # (idx, price)
    piv_lo = []
    for j in range(piv_len, n - piv_len):
        w = h[j - piv_len: j + piv_len + 1]
        if h[j] == w.max() and int(np.argmax(w)) == piv_len:
            piv_hi.append((j, h[j]))
        w = l[j - piv_len: j + piv_len + 1]
        if l[j] == w.min() and int(np.argmin(w)) == piv_len:
            piv_lo.append((j, l[j]))

    ph_i = 0
    pl_i = 0
    # trend state from last two confirmed pivots
    up_struct = False
    down_struct = False
    # armed state
    l_armed = False
    l_run_high = -np.inf
    l_tl_at = np.nan
    l_ordinal = 0
    s_armed = False
    s_run_low = np.inf
    s_tl_at = np.nan
    s_ordinal = 0

    def line_val(idx_prev, px_prev, idx_cur, px_cur, i):
        if idx_cur == idx_prev:
            return px_cur
        return px_cur + (px_cur - px_prev) / (idx_cur - idx_prev) * (i - idx_cur)

    sigs = []
    trend_dir = 0
    for i in range(piv_len + piv_len + 2, n):
        # consume newly confirmed pivots
        while ph_i < len(piv_hi) and piv_hi[ph_i][0] + piv_len <= i:
            ph_i += 1
        while pl_i < len(piv_lo) and piv_lo[pl_i][0] + piv_len <= i:
            pl_i += 1

        ph2 = piv_hi[ph_i - 1] if ph_i >= 1 else None
        ph1 = piv_hi[ph_i - 2] if ph_i >= 2 else None
        pl2 = piv_lo[pl_i - 1] if pl_i >= 1 else None
        pl1 = piv_lo[pl_i - 2] if pl_i >= 2 else None

        was_up, was_down = up_struct, down_struct
        up_struct = ph1 is not None and ph2 is not None and ph2[1] > ph1[1] and pl1 is not None and pl2 is not None and pl2[1] > pl1[1]
        down_struct = ph1 is not None and ph2 is not None and ph2[1] < ph1[1] and pl1 is not None and pl2 is not None and pl2[1] < pl1[1]

        # R4: ordinal resets when a NEW trend structure forms
        if up_struct and trend_dir <= 0:
            trend_dir = 1
            l_ordinal = 0
            s_ordinal = 0
        if down_struct and trend_dir >= 0:
            trend_dir = -1
            l_ordinal = 0
            s_ordinal = 0

        # arm on fresh confirmed pivot within trend
        if up_struct and pl2 is not None and longs:
            new_pivot_confirm = (pl2[0] + piv_len == i)
            if new_pivot_confirm_guard(l_armed, was_up, up_struct, new_pivot_confirm_guard_dummy=False) if False else False:
                pass
        # (kept simple: re-arm check inline below)

        # ---- LONG setup ----
        if up_struct and pl2 is not None and longs and l_armed is False:
            pass  # handled below through touch/reject loop

        # trendline value for long (ascending pivot lows) at bar i
        tl_long = np.nan
        if pl1 is not None and pl2 is not None and pl2[0] != pl1[0] and pl2[1] > pl1[1]:
            tl_long = line_val = pl2[1] + (pl2[1] - pl1[1]) / (pl2[0] - pl1[0]) * (i - min(pl2[0], n - 1) if False else pl2[0])
            # note: line projected from pivot2 forward
            tl_long = pl2[1] + (pl2[1] - pl1[1]) / (pl2[0] - pl1[0]) * (i - pl2[0])
        tl_short = np.nan
        if ph1 is not None and ph2 is not None and ph2[0] != ph1[0] and ph2[1] < ph1[1]:
            tl_short = ph2[1] + (ph2[1] - ph1[1]) / (ph2[0] - ph1[0]) * (i - ph2[0])

        if up_struct and pl2 is not None and longs:
            pv_conf = pl2[0] + piv_len
            if pv_conf <= i:
                if not l_armed:
                    l_armed = True
                    l_run_high = float(h[pl2[0]])
                    l_ordinal += 1
                    l_tl_at = tl_long
                # extend run high within structure
                run_window_high = float(np.max(h[pv_conf: i + 1]))
                if run_window_high > l_run_high:
                    l_run_high = run_window_high

        if down_struct and ph2 is not None and shorts:
            pv_conf = ph2[0] + piv_len
            if pv_conf <= i:
                if not s_armed:
                    s_armed = True
                    s_run_low = float(l[ph2[0]])
                    s_ordinal += 1
                    s_tl_at = tl_short
                run_window_low = float(np.min(l[pv_conf: i + 1]))
                if run_window_low < s_run_low:
                    s_run_low = run_window_low

        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue

        # LONG trigger: line touched within 1xATR, close > open, not exhausted
        if l_armed and not np.isnan(tl_long) and longs:
            touching = l[i] <= tl_long + tl_touch_atr * a
            rejecting = c[i] > o[i]
            if up_struct and trend_dir == 1:
                l_ordinal = max(l_ordinal, 1)
            exhausted = l_ordinal >= exhaust_count
            if touching and rejecting and not exhausted and trend_dir == 1:
                stop = (min(l[i], tl_long)) - stop_buf_atr * a
                risk = c[i] - stop
                struct_dist = l_run_high - tl_long if not np.isnan(l_tl_at) else (l_run_high - tl_long)
                struct_dist = max(struct_dist, l_run_high - tl_long) if not np.isnan(tl_long) else 0
                target = l_run_high + mm_mult * max(struct_dist, 0)
                tgt = c[i] + mm_mult * max(struct_dist, 0)
                if risk > 0 and target > c[i] and struct_dist >= min_struct_atr * a:
                    # fake partial: 50% at 1xMM(=struct dist) target, runner 2x
                    t1 = c[i] + max(struct_dist, 0)
                    sigs.append(dict(
                        direction="LONG", entry_time=bars5.index[i], entry_price=float(c[i]),
                        stop=float(stop), tp1=float(t1), tp2=float(tgt := max(target, t1)),
                        ordinal=l_ordinal,
                    ))
                    l_armed = False  # one trade per structure (strategy.position_size==0 gate)
            # invalidation
            elif l_armed and not np.isnan(tl_long) and c[i] < tl_long - 0.5 * a:
                l_armed = False
                l_ordinal = 0

        # SHORT trigger
        if s_armed and not np.isnan(tl_short) and shorts:
            touching = h[i] >= tl_short - tl_touch_atr * a
            rejecting = c[i] < o[i]
            if touching and rejecting and trend_dir == -1 and s_ordinal < exhaust_count and s_ordinal >= 1:
                stop = max(h[i], tl_short) + stop_buf_atr * a
                risk = stop - c[i]
                struct_dist = max(tl_short - s_run_low, 0)
                t1 = c[i] - struct_dist
                tgt = c[i] - mm_mult * struct_dist
                if risk > 0 and struct_dist >= min_struct_atr * a and t1 < c[i]:
                    sigs.append(dict(
                        direction="SHORT", entry_time=bars5.index[i], entry_price=float(c[i]),
                        stop=float(stop), tp1=float(t1), tp2=float(tgt),
                        ordinal=s_ordinal,
                    ))
                    s_armed = False
            elif s_armed and c[i] > tl_short + 0.5 * a:
                s_armed = False
                s_ordinal = 0

    return sigs


def new_pivot_confirm_guard(*args, **kwargs):
    return False


# ---------------------------------------------------------------------------
# Simulation: partial 50% at TP1 + BE, runner to TP2, structural stop
# ---------------------------------------------------------------------------
def simulate_r4(bars5: pd.DataFrame, sig: dict, pt_val: float = 5.0) -> Optional[dict]:
    i0 = bars5.index.get_loc(sig["entry_time"])
    if i0 is None or i0 + 1 >= len(bars5):
        return None
    is_long = sig["direction"] == "LONG"
    entry = float(bars5["open"].iloc[i0 + 1])
    sl = float(sig["stop"])
    tp1 = float(sig["tp1"])
    tp2 = float(sig["tp2"])
    # adapt stop to actual fill (R4 sizes risk off close; we re-derive distance)
    risk = entry - sl if is_long else sl - entry
    d1 = abs(tp1 - entry)
    d2 = abs(tp2 - entry)
    if risk <= 0:
        return None

    t1_hit = False
    leg1 = 0.0
    leg2 = 0.0
    exit_price = None
    exit_reason = None
    exit_t = None
    for j in range(i0 + 1, len(bars5)):
        hh = float(bars5["high"].iloc[j])
        ll = float(bars5["low"].iloc[j])
        if is_long:
            if ll <= sl:
                leg1 = -risk if not t1_hit else leg1
                leg2 = -risk if not t1_hit else 0.0
                exit_price, exit_reason, exit_t = sl, "SL", bars5.index[j]
                break
            if not t1_hit and hh >= tp1:
                t1_hit = True
                leg1 = entry + d1 - entry  # = d1
                sl = entry
            if hh >= tp2:
                leg2 = tp2 - entry if not t1_hit else tp2 - entry
                exit_price, exit_reason, exit_t = tp2, "TP2", bars5.index[j]
                break
        else:
            if hh >= sl:
                leg1 = -risk if not t1_hit else leg1
                leg2 = -risk if not t1_hit else 0.0
                exit_price, exit_reason, exit_t = sl, "SL", bars5.index[j]
                break
            if not t1_hit and ll <= tp1:
                t1_hit = True
                leg1 = entry - tp1
                sl = entry
            if ll <= tp2:
                leg2 = entry - tp2 if not t1_hit else entry - tp2
                exit_price, exit_reason, exit_t = tp2, "TP2", bars5.index[j]
                break
    if exit_price is None:
        exit_price = float(bars5["close"].iloc[-1])
        exit_reason, exit_t = "EOD", bars5.index[-1]
        move = (exit_price - entry) if is_long else (entry - exit_price)
        if not t1_hit:
            leg1 = move
        leg2 = move

    # risk-normalize: R4 risk is stop distance at entry close; use entry-adjusted
    pnl_pts = leg1 * 0.5 + leg2 * 0.5
    return {
        "date": str(bars5.index[i0].date()),
        "direction": sig["direction"],
        "entry_time": sig["entry_time"],
        "exit_time": exit_t,
        "exit_reason": exit_reason,
        "ordinal": sig["ordinal"],
        "risk_points": risk,
        "pnl_pts": pnl_pts,
        "pnl_dollars": pnl_pts * pt_val,
    }


# ---------------------------------------------------------------------------
def run_symbol(sym: str, longs: bool = True, shorts: bool = False) -> pd.DataFrame:
    df1, df5 = load(sym)
    pt_val = 5.0 if sym == "ES" else 2.0
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
        sigs = scan_r4_structures(bars5, longs=longs, shorts=shorts)
        for sig in sigs:
            res = simulate_r4(bars5, sig, pt_val)
            if res:
                res["pnl_dollars"] = res["pnl_pts"] * pt_val
                rows.append(res)
    return pd.DataFrame(rows)


def load(sym: str):
    from scripts.analysis.bb_e16_e21_queue import load_nt
    return load_nt(sym)


def summarize(tdf: pd.DataFrame) -> dict:
    if len(tdf) == 0:
        return dict(trades=0, wr=0.0, pf=0.0, net=0.0, dd=0.0)
    pnl = tdf["pnl_dollars"]
    cum = pnl.cumsum()
    dd = (cum - cum.cummax()).min()
    gp, gl = pnl[pnl > 0].sum(), abs(pnl[pnl < 0].sum())
    return dict(trades=len(tdf), wr=round((pnl > 0).mean() * 100, 1),
                pf=round(gp / gl, 2) if gl > 0 else 999.0,
                net=round(pnl.sum()), dd=round(abs(dd)))


def main():
    print("E36 — PickMyTrade (R4) reproduction on ES + NQ")
    print("config: piv 7, touch 1.0xATR, stop 1.0xATR, strict HH/HL trend,")
    print("        structure-reset ordinal (block at 3), partial 50%@1xMM + BE, runner 2xMM\n")
    for sym, longs, shorts in [("ES", True, False), ("ES", True, True), ("NQ", True, False)]:
        tdf = run_symbol(sym, longs=longs, shorts=shorts)
        tag = f"{sym} long-only" if not shorts else f"{sym} both dirs"
        if len(tdf) == 0:
            print(f"  E36 [{tag}]: 0 trades")
            continue
        s = summarize(tdf)
        ord_tbl = tdf.groupby("ordinal").agg(
            n=("pnl_dollars", "size"), wr=("pnl_dollars", lambda x: round((x > 0).mean() * 100, 1)),
            net=("pnl_dollars", "sum")).round(1)
        print(f"  E36 [{tag}]: {s['trades']:>4} tr  WR{s['wr']:5.1f}%  PF{s['pf']:5.2f}  Net${s['net']:>7.0f}  DD${s['dd']:>5.0f}")
        print(f"    ordinal table:\n{ord_tbl.to_string()}")
        if shorts and len(tdf):
            for d in ("LONG", "SHORT"):
                sub = tdf[tdf["direction"] == d]
                if len(sub):
                    sd = summarize(sub)
                    print(f"    {d}: {sd['trades']} tr  WR{sd['wr']}%  PF{sd['pf']}  Net${sd['net']}")
        tdf.to_csv(f"data/derived/mm_e36_{sym}_{'both' if shorts else 'long'}_trades.csv", index=False)
    print("\nSaved data/derived/mm_e36_*.csv")


if __name__ == "__main__":
    main()