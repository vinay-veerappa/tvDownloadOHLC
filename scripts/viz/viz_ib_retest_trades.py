#!/usr/bin/env python
"""Visualize IBRetestBot (Play 2) trades reconstructed from the NT8 backtest JSON.

For each trade day, reconstruct the 1-min bars and draw:
  - IB range box (09:30-09:59 ET) with high/low/mid labels
  - The first break direction (arrow at the break bar)
  - The IB-window FVG zone (if present) with alignment note
  - The retest-depth excursion (shaded area past mid in break direction)
  - Entry / exit markers with the exit reason
  - Stop-loss and target price lines
  - The H1/H2 regime tag and depth tier (weak/moderate/strong)

Outputs PNGs to scratch/viz_retest/<date>_<side>.png — one chart per trade.

Usage:
    python -m scripts.viz.viz_ib_retest_trades                  # all 65 trades
    python -m scripts.viz.viz_ib_retest_trades --n 5           # first 5
    python -m scripts.viz.viz_ib_retest_trades --date 2025-01-10
    python -m scripts.viz.viz_ib_retest_trades --show          # plt.show() instead of save
    python -m scripts.viz.viz_ib_retest_trades --json scratch/mnq_overlay_on_full.json

Prerequisites:
    - data/live/live_storage_-NQ.parquet (NQ trades) — uses 'timestamp' col (UTC naive)
    - data/derived/ib_confluence_NQ1.parquet (FVG + depth + break fields)
    - the NT8 backtest JSON (default scratch/nt8_ib_retest_fvg_sep26_full.json)
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")  # non-interactive by default; --show flips to TkAgg
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import numpy as np

# 1-minute bar width in matplotlib date units (1 min = 1/1440 day)
_BAR_W = 0.6 / 1440  # 60% of one minute (leaves a gap between candles)
import pandas as pd

ET = "America/New_York"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "data")
LIVE_NQ = os.path.join(DATA, "live", "live_storage_-NQ.parquet")
LIVE_ES = os.path.join(DATA, "live", "live_storage_-ES.parquet")
CONFLUENCE_NQ = os.path.join(DATA, "derived", "ib_confluence_NQ1.parquet")
DEFAULT_JSON = os.path.join(ROOT, "scratch", "nt8_ib_retest_fvg_sep26_full.json")
OUT_DIR = os.path.join(ROOT, "scratch", "viz_retest")

IB_START, IB_END = dt.time(9, 30), dt.time(9, 59)
RTH_START, RTH_END = dt.time(9, 30), dt.time(15, 50)


# ── data loading ────────────────────────────────────────────────────────────

def load_live_bars(ticker: str = "NQ") -> pd.DataFrame:
    path = {"NQ": LIVE_NQ, "ES": LIVE_ES}.get(ticker, LIVE_NQ)
    if not os.path.exists(path):
        raise FileNotFoundError(f"live_storage parquet not found: {path}")
    df = pd.read_parquet(path)
    # harness convention: 'timestamp' col is UTC-naive datetime
    if "timestamp" in df.columns:
        idx = pd.to_datetime(df["timestamp"])
        if idx.dt.tz is None:
            idx = idx.dt.tz_localize("UTC").dt.tz_convert(ET)
        df.index = idx
    elif "time" in df.columns:
        idx = pd.to_datetime(df["time"], unit="ms")
        idx = idx.dt.tz_localize("UTC").dt.tz_convert(ET)
        df.index = idx
    else:
        df.index = pd.to_datetime(df.index)
    df = df[~df.index.isna()].sort_index()
    # Drop tz — matplotlib date2num mishandles tz-aware timestamps (shifts by UTC offset).
    # All times are ET; strip to naive so the x-axis renders 09:30 (not 14:30).
    df.index = df.index.tz_localize(None)
    return df[["open", "high", "low", "close", "volume"]].copy()


def load_confluence() -> pd.DataFrame:
    if not os.path.exists(CONFLUENCE_NQ):
        raise FileNotFoundError(f"confluence parquet not found: {CONFLUENCE_NQ}")
    c = pd.read_parquet(CONFLUENCE_NQ)
    if "trading_day" in c.columns:
        c["date"] = pd.to_datetime(c["trading_day"]).dt.date
    return c


def load_trades(path: str) -> pd.DataFrame:
    with open(path, encoding="utf-8-sig") as f:
        d = json.load(f)
    rows = []
    for t in d["trades"]:
        et = pd.to_datetime(t["entryTime"]).tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")
        xt = pd.to_datetime(t["exitTime"]).tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")
        # Strip tz — match the naive ET bars index (matplotlib tz fix)
        et = et.tz_localize(None) if et.tzinfo else et
        xt = xt.tz_localize(None) if xt.tzinfo else xt
        rows.append(dict(
            date=et.date(), entry_dt=et, exit_dt=xt,
            side=t["marketPosition"], qty=t["quantity"],
            entry=float(t["entryPrice"]), exit=float(t["exitPrice"]),
            pnl=float(t["profitCurrency"]), pts=float(t["profitPoints"]),
            exit_name=t["exitName"],
            win=int(float(t["profitCurrency"]) > 0),
            instrument=t.get("instrument", "NQ"),
        ))
    return pd.DataFrame(rows).sort_values("entry_dt").reset_index(drop=True)


# ── per-day geometry ────────────────────────────────────────────────────────

def day_geometry(bars: pd.DataFrame, c_row: pd.Series | dict | None) -> dict:
    """Compute IB range, mid, first break, depth, stop/target for a day's bars."""
    day = bars.index.date[0] if len(bars) else None
    ib_mask = (bars.index.time >= IB_START) & (bars.index.time <= IB_END)
    ib = bars[ib_mask]
    if len(ib) < 5:
        raise ValueError(f"insufficient IB bars for {day} (n={len(ib)})")
    ib_high, ib_low = ib["high"].max(), ib["low"].min()
    ib_mid = (ib_high + ib_low) / 2
    ib_range = ib_high - ib_low
    ib_open = ib["open"].iloc[0]
    ib_close = ib["close"].iloc[-1]

    # first break: first 1-min CLOSE beyond ib_high or ib_low after 09:59
    post_ib = bars[bars.index.time > IB_END]
    first_break_dir = 0
    first_break_idx = None
    first_break_time = None
    for i, (ts, row) in enumerate(post_ib.iterrows()):
        if row["close"] > ib_high:
            first_break_dir = 1
            first_break_idx = post_ib.index.get_loc(ts)
            first_break_time = ts
            break
        if row["close"] < ib_low:
            first_break_dir = -1
            first_break_idx = post_ib.index.get_loc(ts)
            first_break_time = ts
            break

    # depth: max excursion past mid in break direction, BEFORE entry (or full day if no entry)
    max_excursion = 0.0
    if first_break_dir != 0:
        for ts, row in post_ib.iterrows():
            if first_break_dir == 1:
                exc = row["high"] - ib_mid
            else:
                exc = ib_mid - row["low"]
            if exc > max_excursion:
                max_excursion = exc

    depth_ratio = max_excursion / ib_range if ib_range > 0 else 0.0

    return dict(
        day=day, ib_high=ib_high, ib_low=ib_low, ib_mid=ib_mid, ib_range=ib_range,
        ib_open=ib_open, ib_close=ib_close,
        first_break_dir=first_break_dir, first_break_time=first_break_time,
        max_excursion=max_excursion, depth_ratio=depth_ratio,
    )


def depth_tier(ratio: float, weak=0.6, strong=0.9) -> str:
    if ratio < weak:
        return "weak (<0.6)"
    if ratio < strong:
        return "moderate (0.6-0.9)"
    return "strong (>=0.9)"


def depth_size_mult(ratio: float, weak=0.6, strong=0.9,
                    w_mult=0.10, m_mult=0.50) -> float:
    if ratio < weak:
        return w_mult
    if ratio < strong:
        return m_mult
    return 1.0


def h1_h2(day) -> str:
    """H1 = Jan-Jun, H2 = Jul-Dec."""
    m = day.month
    return "H1" if m <= 6 else "H2"


# ── FVG from confluence ─────────────────────────────────────────────────────

def fvg_info(c_row: pd.Series | dict | None) -> dict:
    if c_row is None or (isinstance(c_row, pd.Series) and c_row.empty):
        return dict(bias_fvg=0, fvg_low=None, fvg_high=None, aligned=False, note="no confluence row")
    bias = int(c_row.get("bias_fvg", 0)) if c_row is not None else 0
    fvg_low = float(c_row.get("ib_fvg_bottom", np.nan)) if c_row is not None else None
    fvg_high = float(c_row.get("ib_fvg_top", np.nan)) if c_row is not None else None
    aligned = False
    if bias != 0 and fvg_low is not None and fvg_high is not None and not np.isnan(fvg_low):
        # alignment vs first_break_dir (from confluence row directly)
        fbd = int(c_row.get("first_break_dir", 0)) if c_row is not None else 0
        aligned = (bias == fbd) and (fbd != 0)
    return dict(bias_fvg=bias, fvg_low=fvg_low, fvg_high=fvg_high,
                aligned=aligned,
                note="aligned" if aligned else ("misaligned" if bias != 0 else "no FVG in IB"))


# ── plotting ─────────────────────────────────────────────────────────────────

def plot_trade_day(ax, bars: pd.DataFrame, geo: dict, fvg: dict, trade: pd.Series,
                   title: str) -> None:
    """Draw one trade day on the given axes."""
    t = bars.index
    # candlesticks: wick (vline) + body (rectangle)
    for ts, row in bars.iterrows():
        up = row["close"] >= row["open"]
        color = "#26a69a" if up else "#ef5350"
        # wick
        ax.vlines(ts, row["low"], row["high"], color=color, linewidth=0.8, alpha=0.9, zorder=3)
        # body
        body_lo = min(row["open"], row["close"])
        body_hi = max(row["open"], row["close"])
        ax.add_patch(Rectangle(
            (mdates.date2num(ts) - _BAR_W / 2, body_lo),
            _BAR_W, max(body_hi - body_lo, 0.25),  # min height for doji visibility
            facecolor=color, edgecolor=color, linewidth=0.5, alpha=0.95, zorder=3))

    # IB range box
    ib_start_ts = bars.index[bars.index.time == IB_START][0]
    ib_end_ts = bars.index[bars.index.time == IB_END][-1]
    ax.add_patch(Rectangle(
        (mdates.date2num(ib_start_ts) - 1/1440, geo["ib_low"]),
        mdates.date2num(ib_end_ts) + 1/1440 - mdates.date2num(ib_start_ts) + 1/1440,
        geo["ib_high"] - geo["ib_low"],
        facecolor="#3b82f6", alpha=0.12, edgecolor="#3b82f6", linewidth=1.0, zorder=2,
    ))
    ax.axhline(geo["ib_high"], color="#3b82f6", ls="--", lw=1.0, alpha=0.7,
               label=f'IB high {geo["ib_high"]:.2f}')
    ax.axhline(geo["ib_low"], color="#3b82f6", ls="--", lw=1.0, alpha=0.7,
               label=f'IB low {geo["ib_low"]:.2f}')
    ax.axhline(geo["ib_mid"], color="#f59e0b", ls=":", lw=1.2, alpha=0.9,
               label=f'IB mid {geo["ib_mid"]:.2f}')

    # FVG zone — drawn as a positioned rectangle within the IB window.
    # The confluence parquet stores the FVG as ib_fvg_bottom/ib_fvg_top (the gap
    # price band) with ib_fvg_fin_time (when the 3rd bar finalized, prior-day
    # convention). We draw the band across the IB window so it's visible as a
    # box, colored by direction (bull=green, bear=red).
    if fvg["bias_fvg"] != 0 and fvg["fvg_low"] is not None and not np.isnan(fvg["fvg_low"]):
        fvg_lo = fvg["fvg_low"]
        fvg_hi = fvg["fvg_high"]
        fvg_color = "#22c55e" if fvg["bias_fvg"] == 1 else "#ef4444"
        fvg_label = f'FVG {"bull" if fvg["bias_fvg"]==1 else "bear"} [{fvg_lo:.1f}-{fvg_hi:.1f}] ({fvg["note"]})'
        # box spanning the IB window (so the gap location is anchored to time)
        ib_x0 = mdates.date2num(ib_start_ts) - 1 / 1440
        ib_x1 = mdates.date2num(ib_end_ts) + 1 / 1440
        ax.add_patch(Rectangle(
            (ib_x0, fvg_lo), ib_x1 - ib_x0, fvg_hi - fvg_lo,
            facecolor=fvg_color, edgecolor=fvg_color, linewidth=1.2, alpha=0.25, zorder=2))
        # also extend a thin dashed line across the full chart for the gap mid
        fvg_mid = (fvg_lo + fvg_hi) / 2
        ax.axhline(fvg_mid, color=fvg_color, ls="-.", lw=0.9, alpha=0.5, zorder=2,
                   label=fvg_label)

    # first break marker
    if geo["first_break_dir"] != 0 and geo["first_break_time"] is not None:
        bts = geo["first_break_time"]
        bprice = geo["ib_high"] if geo["first_break_dir"] == 1 else geo["ib_low"]
        ax.scatter([bts], [bprice], marker="v" if geo["first_break_dir"] == -1 else "^",
                   s=120, color="#fbbf24", edgecolor="black", zorder=5,
                   label=f'1st break {"UP" if geo["first_break_dir"]==1 else "DOWN"}')

    # depth excursion shade (max high past mid up, or max low past mid down)
    if geo["first_break_dir"] == 1:
        ax.axhspan(geo["ib_mid"], geo["ib_mid"] + geo["max_excursion"],
                   facecolor="#22c55e", alpha=0.08, zorder=0)
    elif geo["first_break_dir"] == -1:
        ax.axhspan(geo["ib_mid"] - geo["max_excursion"], geo["ib_mid"],
                   facecolor="#22c55e", alpha=0.08, zorder=0)

    # entry / exit / stop / target
    if trade is not None:
        side = trade["side"]
        entry, exit_p = trade["entry"], trade["exit"]
        stop = geo["ib_low"] if side == "Long" else geo["ib_high"]
        target = (geo["ib_high"] + 0.5 * geo["ib_range"]) if side == "Long" else (geo["ib_low"] - 0.5 * geo["ib_range"])
        win = trade["win"]
        # entry
        ax.scatter([trade["entry_dt"]], [entry], marker="o", s=140,
                   color="#16a34a" if side == "Long" else "#dc2626", edgecolor="black", zorder=6,
                   label=f'ENTRY {side} @ {entry:.2f}')
        # exit
        ax.scatter([trade["exit_dt"]], [exit_p], marker="X", s=160,
                   color="#16a34a" if win else "#dc2626", edgecolor="black", zorder=6,
                   label=f'EXIT ({trade["exit_name"]}) {"WIN" if win else "LOSS"} {trade["pnl"]:+.0f}')
        # stop + target lines
        ax.axhline(stop, color="#dc2626", ls="-", lw=1.0, alpha=0.6, label=f'STOP {stop:.2f}')
        ax.axhline(target, color="#16a34a", ls="-", lw=1.0, alpha=0.6, label=f'TARGET {target:.2f}')
        # trade hold line
        ax.plot([trade["entry_dt"], trade["exit_dt"]], [entry, exit_p],
                color="black", lw=1.5, alpha=0.5, zorder=4)

    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Time (ET)")
    ax.set_ylabel("Price")

    # ── fixed x-axis: always 09:25-16:05 ET with 30-min ticks ──
    # Anchor to the day of the first bar so the range is consistent across all charts.
    if len(bars) > 0:
        day = bars.index[0].normalize()
        # strip tz for date2num (matplotlib works with naive datetimes)
        if day.tzinfo is not None:
            day = day.tz_localize(None)
        x0 = day + dt.timedelta(hours=9, minutes=25)
        x1 = day + dt.timedelta(hours=16, minutes=5)
        ax.set_xlim(mdates.date2num(x0), mdates.date2num(x1))
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=15))

    ax.legend(loc="upper right", fontsize=7, ncol=2, framealpha=0.9)
    ax.grid(True, alpha=0.2)


# ── main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Visualize IBRetestBot Play 2 trades")
    ap.add_argument("--json", default=DEFAULT_JSON, help="NT8 backtest JSON path")
    ap.add_argument("--n", type=int, default=0, help="only first N trades (0 = all)")
    ap.add_argument("--date", default=None, help="single date YYYY-MM-DD")
    ap.add_argument("--show", action="store_true", help="plt.show() instead of saving PNG")
    ap.add_argument("--out", default=OUT_DIR, help="output dir for PNGs")
    args = ap.parse_args()

    if args.show:
        matplotlib.use("TkAgg")

    trades = load_trades(args.json)
    if args.n > 0:
        trades = trades.head(args.n)
    if args.date:
        d = pd.to_datetime(args.date).date()
        trades = trades[trades["date"] == d].reset_index(drop=True)
    if trades.empty:
        print(f"no trades match filter (json={args.json}, n={args.n}, date={args.date})")
        return

    # infer ticker from instrument
    inst = str(trades["instrument"].iloc[0]).upper()
    ticker = "ES" if "ES" in inst else "NQ"
    bars_all = load_live_bars(ticker)
    confl = load_confluence()
    confl_by_date = {r["date"]: r for _, r in confl.iterrows()} if "date" in confl.columns else {}

    os.makedirs(args.out, exist_ok=True)
    print(f"visualizing {len(trades)} trades from {args.json}")
    print(f"  instrument={ticker}  live_bars={len(bars_all)}  confluence_rows={len(confl)}")
    print(f"  out -> {args.out}")

    for i, trade in trades.iterrows():
        d = trade["date"]
        day_mask = bars_all.index.date == d
        day_bars = bars_all[day_mask].between_time("09:25", "16:00")
        if len(day_bars) < 10:
            print(f"  [{i+1}] {d} SKIP (no bars)")
            continue
        c_row = confl_by_date.get(d, None)
        try:
            geo = day_geometry(day_bars, c_row)
        except ValueError as e:
            print(f"  [{i+1}] {d} SKIP ({e})")
            continue
        fvg = fvg_info(c_row)

        tier = depth_tier(geo["depth_ratio"])
        size_mult = depth_size_mult(geo["depth_ratio"])
        regime = h1_h2(d)
        title = (f"{d} {trade['side']} q{trade['qty']} | {trade['exit_name']} "
                 f"{'WIN' if trade['win'] else 'LOSS'} {trade['pnl']:+.0f} | "
                 f"depth={geo['depth_ratio']:.2f} [{tier}] size×{size_mult:.2f} | "
                 f"FVG {fvg['note']} | {regime}")

        fig, ax = plt.subplots(figsize=(16, 8), dpi=110)
        plot_trade_day(ax, day_bars, geo, fvg, trade, title)
        fig.tight_layout()
        fname = f"{d}_{trade['side'].lower()}.png"
        fpath = os.path.join(args.out, fname)
        if args.show:
            plt.show()
        else:
            fig.savefig(fpath, bbox_inches="tight")
            print(f"  [{i+1}/{len(trades)}] {fname}  depth={geo['depth_ratio']:.2f} {tier} {regime}")
        plt.close(fig)

    print("done")


if __name__ == "__main__":
    main()