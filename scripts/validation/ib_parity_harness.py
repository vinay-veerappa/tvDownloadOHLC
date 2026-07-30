"""
ib_parity_harness.py
=====================
Trade-by-trade parity validation: Python IB framework vs NT8 Strategy Analyzer.

Purpose
-------
Rebuild the Python IB trade ledger (entry/exit time, price, side, result) from
1-minute bars + ib_facts, and diff it against the NT8 Strategy Analyzer trade
ledger for the same window. The goal is to find WHERE the bar-level Python
framework diverges from tick-level NT8, quantify each divergence class, and
identify the changes needed to make Python statistics hold in live.

AVWAP feed-dependency limitation
--------------------------------
The ConfluenceFilter common gate (`break_vs_avwap_0930`) is volume-weighted
(cumulative TPV/Vol from 09:30). The Python live_storage continuous feed and
the NT8 ##-## continuous feed use DIFFERENT roll adjustment methods and volume
profiles (empirically: offset std=233pts, ratio std=0.0087 — neither constant).
This causes the AVWAP to land at different relative positions, flipping the
sign of (close > AVWAP) and filtering different trade days. IB range, break
direction, and win/loss are feed-invariant, but AVWAP is NOT.

The `--avwap-source` flag controls how the harness computes the AVWAP gate:
  - `parquet` (default): use the pre-computed ib_confluence parquet (built from
    the fused historical+live loader). Validates parity with the PRODUCTION
    Python pipeline.
  - `onthefly`: compute AVWAP on-the-fly from the SAME live_storage bars the
    harness uses for IB boundaries. Validates Python SELF-CONSISTENCY (AVWAP
    consistent with IB), not NT8 feed-matching.
  - `none`: ablation — disable the AVWAP common gate (set to 0), keep
    TrendMisaligned from the parquet if present. Shows the parity ceiling
    without the feed-dependent AVWAP filter.

Matching NT8 exactly requires loading NT8 raw contract bars into Python
(future work — Option D in NT8_PYTHON_PARITY_STANDARD.md §8).

ADR compliance:
  - ADR-001: explicit ET localization; parquet timestamps are UTC ms-epoch.
  - ADR-017: vectorized entry/exit detection; one bounded loop for the
    stop/target tie-break (the documented ADR-017 exception). On-the-fly AVWAP
    uses vectorized cumsum (no bar-level for-loop).
  - NT8 parity: liquidate on close of the 15:50 ET bar (matches NT8 FlattenBy=1550).

Usage
-----
    # 1. Run the NT8 backtest via the MCP bridge and save the JSON:
    #    nt_backtest(strategy='IBBreakoutBot', symbol='MNQ 06-26',
    #                from='2026-06-01', to='2026-06-30',
    #                period='Minute', periodValue=1, maxTrades=500, timeoutSec=300)
    #    -> save to scratch/nt8_ib_breakout_jun2026.json

    # 2. Run this harness:
    python -m scripts.validation.ib_parity_harness \
        --ticker NQ1 --play 1 --target 0.5 --stop-mult 2.0 \
        --from 2026-06-01 --to 2026-06-30 \
        --avwap-source onthefly \
        --nt8-json scratch/nt8_ib_breakout_jun2026.json \
        --out scratch/ib_parity_breakout_jun2026.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ─── Session config (matches SESSION_CONFIGS_V5 NY AM IB) ───────────────────
RTH_OPEN_ET = time(9, 30)
# NT8 parity: IBStrategyBase FlattenBy=1550 → Python liquidates at 15:50 bar close
# (out_end=15:51 means last in_out bar = 15:50, exclusive upper bound pattern)
RTH_CLOSE_ET = time(15, 51)              # exclusive upper bound (last bar = 15:50)
LIQUIDATION_BAR_CLOSE_ET = time(15, 50)  # NT8 parity: exit on close of 15:50 bar
IB_START_ET = time(9, 30)
IB_DURATION_MIN = 30                    # IBStrategyBase default (Phase F)

# ─── Data loading ──────────────────────────────────────────────────────────
LIVE_STORAGE_TMPL = "data/live/live_storage_-{ticker}.parquet"
FACTS_PATH_TMPL = "data/derived/ib_facts_{ticker}.parquet"
CONFLUENCE_PATH_TMPL = "data/derived/ib_confluence_{ticker}.parquet"


def load_confluence(ticker: str, session: str, d_from: str, d_to: str) -> pd.DataFrame:
    """Load ib_confluence parquet for the window, filtered to one session slot.

    Returns a DataFrame indexed by trading_day (date) with filter columns:
    break_vs_avwap_0930, trend_misaligned_with_break, ib_vcp_3day_contracting,
    is_opex_week, is_quarterly_opex, ib_low_body_close, ib_high_body_close.
    """
    path = CONFLUENCE_PATH_TMPL.format(ticker=ticker)
    try:
        df = pd.read_parquet(path)
    except FileNotFoundError:
        return pd.DataFrame()
    df = df[df["session_slot"] == session].copy()
    df["td"] = pd.to_datetime(df["trading_day"]).dt.date
    df = df.set_index("td")
    df = df.loc[pd.Timestamp(d_from).date() : pd.Timestamp(d_to).date()]
    return df


def load_1m_bars(ticker: str, d_from: str, d_to: str) -> pd.DataFrame:
    """Load 1-min bars from live storage, filtered to [d_from, d_to] ET.

    Returns DataFrame indexed by ET-localized timestamp with columns
    [open, high, low, close, volume].
    """
    path = LIVE_STORAGE_TMPL.format(ticker=ticker.replace("1", ""))
    df = pd.read_parquet(path)
    ts = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    ts_et = ts.dt.tz_convert("America/New_York")
    df = df.assign(ts_et=ts_et)
    df = df[(ts_et >= d_from) & (ts_et < d_to + " 23:59:59")]
    df = df.set_index("ts_et").sort_index()
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def load_ib_facts(ticker: str, session: str, d_from: str, d_to: str) -> pd.DataFrame:
    """Load ib_facts for the window, filtered to one session slot."""
    df = pd.read_parquet(FACTS_PATH_TMPL.format(ticker=ticker))
    df["td"] = pd.to_datetime(df["trading_day"])
    df = df[(df["session_slot"] == session)]
    df = df[(df["td"] >= d_from) & (df["td"] <= d_to)]
    return df


# ─── On-the-fly AVWAP (feed-consistent with the bars the harness uses) ──────
#
# The pre-computed ib_confluence parquet is built from the FUSED historical+
# live loader (scripts/edgeful/ib_avwap_trend.py), which uses a DIFFERENT
# continuous-contract construction than the live_storage-only bars the harness
# loads via load_1m_bars(). Empirically (scratch/diagnose_avwap_parity.py):
#   - Price offset std = 233.24 pts (NOT a constant roll)
#   - Ratio std = 0.0087 (NOT a multiplicative roll)
#   - break_vs_avwap_0930 sign FLIPS between the two feeds
# AVWAP is volume-weighted (cumulative TPV/Vol from 09:30), so different feeds
# with different absolute prices AND volume profiles land the AVWAP at different
# relative positions within the IB range, flipping the ConfluenceFilter common
# gate. The on-the-fly computation below uses the SAME bars_day the harness
# already uses for IB boundaries, making the AVWAP self-consistent with the IB.
#
# ADR-001: bars_day index is already ET-localized (load_1m_bars converts UTC
#          ms-epoch to America/New_York). between_time() is ET-correct.
# ADR-017: vectorized cumsum — no Python for-loop over bars.
#
# LIMITATION: this validates Python SELF-CONSISTENCY (AVWAP computed from the
# same feed as the IB), NOT NT8 feed-matching. NT8 uses its own ##-## continuous
# feed with different roll/volume. To match NT8 exactly, load NT8 raw contract
# bars into Python (future work — Option D in the parity standard).


def compute_break_vs_avwap_0930_onthefly(bars_day: pd.DataFrame) -> int:
    """Compute break_vs_avwap_0930 on-the-fly from the harness's own bars.

    Mirrors NT8 IBStrategyBase.UpdateConfluenceIndicators: 09:30-anchored AVWAP
    (cumulative TPV / cumulative Vol from 09:30 ET), evaluated at the first bar
    that closes beyond the IB boundary. Returns +1 if close > AVWAP, -1 if below,
    0 if no valid break/AVWAP.

    Parameters
    ----------
    bars_day : pd.DataFrame
        Day's 1-min bars with ET-localized DatetimeIndex and columns
        [open, high, low, close, volume]. Must be the same DataFrame used for
        IB boundary detection (ensures feed consistency).

    Returns
    -------
    int
        +1, -1, or 0 (no valid data / no break / AVWAP undefined).
    """
    if bars_day.empty:
        return 0

    # RTH bars only (09:30-15:50 ET) — ADR-001: index is ET-localized.
    rth = bars_day.between_time("09:30", "15:50")
    if len(rth) < IB_DURATION_MIN + 1:
        return 0

    # IB window = first 30 RTH bars (09:30-09:59). AVWAP anchors at 09:30.
    ib = rth.iloc[:IB_DURATION_MIN]
    ib_high = float(ib["high"].max())
    ib_low = float(ib["low"].min())
    ib_range = ib_high - ib_low
    if ib_range <= 0:
        return 0

    # Vectorized 09:30-anchored AVWAP (ADR-017: cumsum, no for-loop).
    tp = (rth["high"] + rth["low"] + rth["close"]) / 3.0
    tpv = tp * rth["volume"]
    cum_tpv = tpv.cumsum()
    cum_vol = rth["volume"].cumsum()
    with np.errstate(divide="ignore", invalid="ignore"):
        avwap = cum_tpv / cum_vol.replace(0, np.nan)

    # First break bar (first close beyond IB boundary AFTER the IB window).
    post_ib = rth.iloc[IB_DURATION_MIN:]
    long_break = post_ib[post_ib["close"] > ib_high]
    short_break = post_ib[post_ib["close"] < ib_low]
    if long_break.empty and short_break.empty:
        return 0  # no break → no break_vs_avwap to compute

    long_t = long_break.index[0] if not long_break.empty else pd.Timestamp("2099-12-31", tz=rth.index.tz)
    short_t = short_break.index[0] if not short_break.empty else pd.Timestamp("2099-12-31", tz=rth.index.tz)
    break_ts = min(long_t, short_t)

    # AVWAP at the break bar (positional lookup in the rth frame).
    break_pos = rth.index.get_loc(break_ts)
    break_avwap = float(avwap.iloc[break_pos])
    break_close = float(rth["close"].iloc[break_pos])

    if np.isnan(break_avwap):
        return 0
    if break_close > break_avwap:
        return 1
    if break_close < break_avwap:
        return -1
    return 0


def build_confluence_row(
    day: pd.Timestamp,
    conf_df: pd.DataFrame,
    bars_day: pd.DataFrame,
    avwap_source: str,
) -> Optional[pd.Series]:
    """Build the confluence_row for a trading day, honoring --avwap-source.

    Parameters
    ----------
    day : pd.Timestamp (date-only)
        The trading day.
    conf_df : pd.DataFrame
        Pre-loaded confluence parquet (indexed by date, filtered to session).
        May be empty if the parquet is missing.
    bars_day : pd.DataFrame
        Day's 1-min bars (ET-localized) — used for on-the-fly AVWAP.
    avwap_source : str
        One of 'parquet' (use pre-computed), 'onthefly' (compute from bars),
        'none' (disable AVWAP gate, keep TrendMisaligned from parquet if present).

    Returns
    -------
    pd.Series or None
        Confluence row with break_vs_avwap_0930 and trend_misaligned_with_break.
        None if no confluence data and avwap_source cannot synthesize a row.
    """
    # Try the pre-computed parquet first (handles missing/empty gracefully).
    # The confluence index is date objects (set in load_confluence), so convert
    # the Timestamp to a date for matching.
    row: Optional[pd.Series] = None
    lookup_day = day.date() if isinstance(day, pd.Timestamp) else day
    if not conf_df.empty and lookup_day in conf_df.index:
        sub = conf_df.loc[[lookup_day]]
        if isinstance(sub, pd.DataFrame) and not sub.empty:
            row = sub.iloc[0].copy()

    if avwap_source == "none":
        # Ablation: bypass the ENTIRE ConfluenceFilter (no AVWAP, no
        # TrendMisaligned). Returns None so simulate_play1_day skips the
        # filter block entirely — shows the no-filter parity ceiling.
        return None

    if avwap_source == "onthefly":
        # Compute AVWAP from the same bars the harness uses (feed-consistent).
        onthefly_bva = compute_break_vs_avwap_0930_onthefly(bars_day)
        if row is None:
            row = pd.Series(dtype=object)
        row["break_vs_avwap_0930"] = onthefly_bva
        # TrendMisaligned comes from the parquet (daily EMA) — keep if present,
        # else default to False (no trend filter when parquet absent).
        if "trend_misaligned_with_break" not in row.index:
            row["trend_misaligned_with_break"] = False
        return row

    # avwap_source == "parquet" (default): use pre-computed values as-is.
    return row


# ─── Python IB trade simulator (mirrors evaluate_all_plays_consolidated) ────
#
# The Python framework evaluates one trade per (day, play, target). Entry is
# the close of the first bar that closes beyond the IB boundary AFTER the IB
# window completes. Stop is the opposite IB boundary (Play 1) or
# StopRMult*range beyond the boundary (Play 3). Target is TargetLvl*range
# beyond the break side (Play 1) or TargetLvl*range reversion from entry (Play 3).
#
# Exit resolution (matches ib.py evaluate_all_plays_consolidated):
#   - Bar-level, high/low based.
#   - First bar where stop touched -> stop exit.
#   - First bar where target touched -> target exit.
#   - TIE-BREAK: if both touched on the same bar, STOP WINS (conservative).
#   - Liquidation at close of 15:50 ET bar (NT8 parity: FlattenBy=1550).
#   - MAE/MFE from intrabar high/low across the in-trade window.


def simulate_play1_day(
    bars_day: pd.DataFrame,
    ib_high: float,
    ib_low: float,
    ib_range: float,
    target_lvl: float,
    stop_mult: float,
    confluence_row: Optional[pd.Series] = None,
) -> Optional[Dict[str, Any]]:
    """Play 1 (breakout): one trade per day, first close beyond IB boundary.

    stop_mult is in units of TargetLvl*range (R = target distance), so the
    actual stop distance = stop_mult * target_lvl * ib_range.
    With stop_mult=2.0 and target_lvl=0.5, stop = 2.0*0.5*range = 1.0*range
    = opposite IB boundary (matches IBBreakoutBot.cs StopRMult=2.0).

    confluence_row: optional Series with NT8 ConfluenceFilter columns for this
    trading day. When provided, applies the break_vs_avwap_0930 common gate and
    the TrendMisaligned filter (mirrors NT8 IBStrategyBase default).
    """
    # NT8 parity: ConfluenceFilter gate (mirrors IBStrategyBase.ConfluenceFilter)
    if confluence_row is not None:
        bva = confluence_row.get("break_vs_avwap_0930", 0)
        if pd.isna(bva) or bva == 0:
            return None  # common gate: skip if no clear break-vs-AVWAP direction
        if confluence_row.get("trend_misaligned_with_break", False):
            pass  # TrendMisaligned filter ON — allow only when misaligned
        else:
            return None  # TrendMisaligned filter rejects
    if ib_range <= 0 or len(bars_day) < IB_DURATION_MIN + 1:
        return None

    # Filter to RTH bars only (09:30-16:00 ET) — NT8 trades the RTH session,
    # and ib_facts ib_high/ib_low are the 09:30-10:00 IB window. Overnight
    # Globex bars would produce false breakouts.
    rth = bars_day.between_time("09:30", "15:50")
    if len(rth) < IB_DURATION_MIN + 1:
        return None

    # Entry: first RTH bar AFTER the IB window (09:30 + 30min = 10:00) that
    # closes beyond ib_high or ib_low. The IB window is the first 30 RTH bars.
    ib_end_ts = rth.index[IB_DURATION_MIN - 1]  # 09:30 + 29min = 09:59 (last IB bar)
    post_ib = rth.loc[rth.index > ib_end_ts]
    long_entry = post_ib[post_ib["close"] > ib_high]
    short_entry = post_ib[post_ib["close"] < ib_low]

    if long_entry.empty and short_entry.empty:
        return None

    FAR_FUTURE = pd.Timestamp("2099-12-31", tz="America/New_York")
    long_t = long_entry.index[0] if not long_entry.empty else FAR_FUTURE
    short_t = short_entry.index[0] if not short_entry.empty else FAR_FUTURE

    if long_t <= short_t:
        side = "LONG"
        entry_idx = long_t
        entry_price = float(long_entry["close"].iloc[0])
        stop_price = ib_low   # IB-relative: opposite IB boundary (not entry-relative)
        target_price = ib_high + target_lvl * ib_range
        # TargetIsSane (mirrors NT8 IntradayStrategyBase.TargetIsSane):
        # if the breakout bar gapped past the target level, the target is
        # behind the entry — NT8 rejects this trade, so Python must too.
        if target_price <= entry_price:
            return None
    else:
        side = "SHORT"
        entry_idx = short_t
        entry_price = float(short_entry["close"].iloc[0])
        stop_price = ib_high  # IB-relative: opposite IB boundary (not entry-relative)
        target_price = ib_low - target_lvl * ib_range
        # TargetIsSane for SHORT: target must be below entry
        if target_price >= entry_price:
            return None

    return _resolve_exit(rth, entry_idx, entry_price, stop_price,
                         target_price, side, ib_range)


def simulate_play3_day(
    bars_day: pd.DataFrame,
    ib_high: float,
    ib_low: float,
    ib_range: float,
    target_lvl: float,
    stop_mult: float,
    overshoot_mult: float = 0.35,
) -> Optional[Dict[str, Any]]:
    """Play 3 (fade): overshoot beyond boundary, then close back inside.

    Matches IBFadeBot.cs: TargetLvl=1.0 (full reversion), StopRMult=0.5,
    LateBreakSizeMult=0.35 (overshoot threshold).
    """
    if ib_range <= 0 or len(bars_day) < IB_DURATION_MIN + 1:
        return None

    # Filter to RTH bars only (09:30-15:50 ET, NT8 FlattenBy=1550)
    rth = bars_day.between_time("09:30", "15:50")
    if len(rth) < IB_DURATION_MIN + 1:
        return None

    ib_end_ts = rth.index[IB_DURATION_MIN - 1]
    post_ib = rth.loc[rth.index > ib_end_ts]
    threshold = overshoot_mult * ib_range

    # Detect overshoot then close-back-inside (two-state, bar-close only)
    # NT8 parity: IBFadeBot enters via market order on the NEXT bar after the
    # close-back-inside signal. Entry price = next bar's open (not IB boundary).
    overshoot_above = False
    overshoot_below = False
    signal_ts = None
    for ts, row in post_ib.iterrows():
        if row["high"] > ib_high + threshold:
            overshoot_above = True
        if row["low"] < ib_low - threshold:
            overshoot_below = True

        # Fade the upside overshoot: close back below ib_high
        if overshoot_above and row["close"] < ib_high:
            signal_ts = ts
            signal_side = "SHORT"
            break

        # Fade the downside overshoot: close back above ib_low
        if overshoot_below and row["close"] > ib_low:
            signal_ts = ts
            signal_side = "LONG"
            break

    if signal_ts is None:
        return None

    # Entry = NEXT bar's open (NT8 market-order fill, not boundary price)
    after_signal = rth.loc[rth.index > signal_ts]
    if after_signal.empty:
        return None  # signal on last bar, no next bar to enter

    entry_idx = after_signal.index[0]
    entry_price = float(after_signal["open"].iloc[0])

    if signal_side == "SHORT":
        stop_price = ib_high + stop_mult * ib_range
        target_price = ib_high - target_lvl * ib_range
    else:
        stop_price = ib_low - stop_mult * ib_range
        target_price = ib_low + target_lvl * ib_range

    return _resolve_exit(rth, entry_idx, entry_price,
                         stop_price, target_price, signal_side, ib_range)


def _resolve_exit(
    bars_day: pd.DataFrame,
    entry_idx: pd.Timestamp,
    entry_price: float,
    stop_price: float,
    target_price: float,
    side: str,
    ib_range: float,
) -> Dict[str, Any]:
    """Resolve the exit bar-by-bar (matches Python's conservative stop-wins tie-break).

    Returns dict with entry/exit time+price, result (+1 win / -1 loss / 0 timeout),
    mae, mfe, exit_reason, and a tie_break flag (same-bar stop+target).
    """
    post = bars_day.loc[bars_day.index >= entry_idx].iloc[1:]  # bars after entry
    if post.empty:
        # No bars after entry — exit at entry (no movement)
        return {
            "entry_time": str(entry_idx), "entry_price": entry_price,
            "exit_time": str(entry_idx), "exit_price": entry_price,
            "side": side, "result": 0, "exit_reason": "no_post_bars",
            "mae": 0.0, "mfe": 0.0, "ib_range": ib_range, "tie_break": False,
        }

    exit_price: Optional[float] = None
    exit_time = None
    exit_reason = "none"
    tie_break = False
    is_long = side == "LONG"

    for ts, row in post.iterrows():
        stop_touched = (row["low"] <= stop_price) if is_long else (row["high"] >= stop_price)
        target_touched = (row["high"] >= target_price) if is_long else (row["low"] <= target_price)

        if stop_touched and target_touched:
            # TIE-BREAK: conservative — stop wins (matches ib.py line 404-405)
            tie_break = True
            exit_price = stop_price
            exit_time = ts
            exit_reason = "stop_tiebreak_conservative"
            break
        if stop_touched:
            exit_price = stop_price
            exit_time = ts
            exit_reason = "stop"
            break
        if target_touched:
            exit_price = target_price
            exit_time = ts
            exit_reason = "target"
            break
        if ts.time() >= LIQUIDATION_BAR_CLOSE_ET:
            exit_price = float(row["close"])
            exit_time = ts
            exit_reason = "liquidation_1550"
            break

    if exit_price is None:
        last_ts = post.index[-1]
        exit_price = float(post.loc[last_ts, "close"])
        exit_time = last_ts
        exit_reason = "end_of_data"

    # MAE/MFE from intrabar high/low across the in-trade window
    in_trade = bars_day.loc[(bars_day.index >= entry_idx) & (bars_day.index <= exit_time)]
    if is_long:
        mfe = float(in_trade["high"].max() - entry_price) if not in_trade.empty else 0.0
        mae = float(entry_price - in_trade["low"].min()) if not in_trade.empty else 0.0
    else:
        mfe = float(entry_price - in_trade["low"].min()) if not in_trade.empty else 0.0
        mae = float(in_trade["high"].max() - entry_price) if not in_trade.empty else 0.0

    # Result: +1 win (target hit), -1 loss (stop hit), 0 timeout/liquidation
    if exit_reason == "target":
        result = 1
    elif exit_reason.startswith("stop"):
        result = -1
    else:
        # Liquidation or end-of-data: win if favorable direction
        if is_long:
            result = 1 if exit_price > entry_price else -1
        else:
            result = 1 if exit_price < entry_price else -1

    # Realized R (R = target distance = target_lvl * ib_range for Play 1)
    # For parity with ib_play_detail's realized_r
    target_dist = abs(target_price - entry_price)
    if target_dist > 0:
        pnl = (exit_price - entry_price) if is_long else (entry_price - exit_price)
        realized_r = pnl / target_dist
    else:
        realized_r = 0.0

    return {
        "entry_time": str(entry_idx), "entry_price": round(entry_price, 2),
        "exit_time": str(exit_time), "exit_price": round(exit_price, 2),
        "side": side, "result": result, "exit_reason": exit_reason,
        "mae": round(mae, 2), "mfe": round(mfe, 2),
        "ib_range": round(ib_range, 2), "tie_break": tie_break,
        "realized_r": round(realized_r, 4),
    }


# ─── NT8 trade ledger parsing ──────────────────────────────────────────────
def parse_nt8_trades(nt8_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract and normalize the NT8 trade list from an nt_backtest JSON payload.

    Tolerant of schema variations. Returns one dict per trade with keys:
    side, entry_time, entry_price, exit_time, exit_price, pnl, exit_reason.
    """
    for key in ("trades", "Trades", "results"):
        val = nt8_json.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            trades = val
            break
        if isinstance(val, dict):
            inner = val.get("trades") or val.get("Trades")
            if isinstance(inner, list):
                trades = inner
                break
    else:
        sel = nt8_json.get("SelectedResult") or nt8_json.get("selectedResult")
        if isinstance(sel, dict):
            for key in ("trades", "Trades"):
                inner = sel.get(key)
                if isinstance(inner, list):
                    trades = inner
                    break
            else:
                return []
        else:
            return []

    out = []
    for t in trades:
        def g(*keys, default=None):
            for k in keys:
                if k in t and t[k] is not None:
                    return t[k]
            return default
        side_raw = str(g("marketPosition", "MarketPosition", "side", "Side", default="")).upper()
        side = "LONG" if "LONG" in side_raw or "BUY" in side_raw else ("SHORT" if "SHORT" in side_raw or "SELL" in side_raw else "?")
        out.append({
            "side": side,
            "entry_time": str(g("entryTime", "EntryTime", "entry_time", default="")),
            "entry_price": float(g("entryPrice", "EntryPrice", "entry_price", default=float("nan"))),
            "exit_time": str(g("exitTime", "ExitTime", "exit_time", default="")),
            "exit_price": float(g("exitPrice", "ExitPrice", "exit_price", default=float("nan"))),
            "pnl": float(g("profitCurrency", "ProfitCurrency", "pnl", "PnL", "profit", default=float("nan"))),
            "exit_reason": str(g("exitName", "ExitName", "exit_reason", "reason", default="")),
        })
    return out


# ─── Diff ──────────────────────────────────────────────────────────────────
def diff_ledgers(py: List[Dict], nt8: List[Dict], out_path: Optional[str] = None) -> pd.DataFrame:
    """Join Python and NT8 trades by (date, side) and diff entry/exit/result.

    NT8 may take multiple trades per day (re-entry); Python takes one per day.
    Match by closest entry time within ±60s on the same side. Unmatched trades
    are kept with the other side as NaN.
    """
    py_df = pd.DataFrame(py)
    nt8_df = pd.DataFrame(nt8)

    if py_df.empty:
        print("[parity] WARNING: Python produced 0 trades")
        py_df = pd.DataFrame(columns=["entry_time", "entry_price", "side", "result"])
    if nt8_df.empty:
        print("[parity] WARNING: NT8 produced 0 trades")
        nt8_df = pd.DataFrame(columns=["entry_time", "entry_price", "side", "pnl"])

    # Parse entry times to datetime for matching (normalize both to tz-aware ET)
    # Python entry_time is tz-aware ET (from simulate_play1_day which uses ET-localized bars).
    # NT8 entry_time is ET-naive (NT8 Strategy Analyzer exports in the chart timezone = ET).
    # Treating NT8 timestamps as UTC and converting to ET would shift them −4h/−5h — a bug.
    if "entry_time" in py_df.columns:
        py_df["entry_dt"] = pd.to_datetime(py_df["entry_time"], errors="coerce", utc=True).dt.tz_convert("America/New_York")
        py_df["date"] = py_df["entry_dt"].dt.date
    if "entry_time" in nt8_df.columns:
        # NT8 timestamps are ET-naive — localize directly to ET (do NOT treat as UTC)
        nt8_df["entry_dt"] = pd.to_datetime(nt8_df["entry_time"], errors="coerce").dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
        nt8_df["date"] = nt8_df["entry_dt"].dt.date

    # Aggregate stats
    print("\n" + "=" * 78)
    print("PARITY SUMMARY — Python vs NT8")
    print("=" * 78)
    print(f"{'metric':<28} | {'python':<18} | {'nt8':<18}")
    print("-" * 78)
    print(f"{'total trades':<28} | {len(py_df):<18} | {len(nt8_df):<18}")
    if "result" in py_df.columns and not py_df.empty:
        py_wr = (py_df["result"] == 1).mean() * 100 if len(py_df) else 0
        print(f"{'win rate %':<28} | {py_wr:<18.1f} | ", end="")
        if not nt8_df.empty and "pnl" in nt8_df.columns:
            nt8_wr = (nt8_df["pnl"] > 0).mean() * 100
            print(f"{nt8_wr:<18.1f}")
        else:
            print("N/A")
    if "exit_reason" in py_df.columns and not py_df.empty:
        print(f"\nPython exit reasons:")
        print(py_df["exit_reason"].value_counts().to_string())
        py_tiebreak = py_df.get("tie_break", pd.Series(dtype=bool)).sum() if "tie_break" in py_df.columns else 0
        print(f"  same-bar tie-breaks (stop won): {py_tiebreak}")
    if "exit_reason" in nt8_df.columns and not nt8_df.empty:
        print(f"\nNT8 exit reasons:")
        print(nt8_df["exit_reason"].value_counts().to_string())

    # Trade-by-trade match
    if not py_df.empty and not nt8_df.empty:
        matched = []
        used_nt8 = set()
        for _, prow in py_df.iterrows():
            d = prow["date"]
            side = prow["side"]
            cands = nt8_df[(nt8_df["date"] == d) & (nt8_df["side"] == side) & (~nt8_df.index.isin(used_nt8))]
            if cands.empty:
                cands = nt8_df[(nt8_df["date"] == d) & (~nt8_df.index.isin(used_nt8))]
            if cands.empty:
                matched.append({**{f"py_{k}": v for k, v in prow.items()}, **{f"nt8_{k}": np.nan for k in nt8_df.columns}})
                continue
            # Closest entry time
            cands = cands.copy()
            cands["dt_diff"] = abs((cands["entry_dt"] - prow["entry_dt"]).dt.total_seconds())
            best = cands.loc[cands["dt_diff"].idxmin()]
            used_nt8.add(cands["dt_diff"].idxmin())
            row = {f"py_{k}": v for k, v in prow.items()}
            row.update({f"nt8_{k}": v for k, v in best.items()})
            row["entry_time_diff_s"] = best["dt_diff"]
            row["entry_price_diff"] = prow["entry_price"] - best["entry_price"] if "entry_price" in prow and not pd.isna(best.get("entry_price")) else np.nan
            row["exit_price_diff"] = prow["exit_price"] - best["exit_price"] if "exit_price" in prow and "exit_price" in best and not pd.isna(best.get("exit_price")) else np.nan
            # Result agreement
            py_win = prow.get("result") == 1
            nt8_win = best.get("pnl", np.nan) > 0 if not pd.isna(best.get("pnl", np.nan)) else None
            row["result_match"] = (py_win == nt8_win) if nt8_win is not None else None
            matched.append(row)
        mdf = pd.DataFrame(matched)
        if out_path:
            mdf.to_csv(out_path, index=False)
            print(f"\n[saved] trade-by-trade diff: {out_path}")
        if "result_match" in mdf.columns and not mdf["result_match"].isna().all():
            agree = mdf["result_match"].sum()
            total = mdf["result_match"].notna().sum()
            print(f"\nResult agreement: {agree}/{total} trades ({100*agree/total:.1f}%)")
        return mdf
    return pd.DataFrame()


# ─── CLI ───────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="IB Python<->NT8 trade-by-trade parity harness")
    ap.add_argument("--ticker", default="NQ1")
    ap.add_argument("--play", type=int, default=1, choices=[1, 3])
    ap.add_argument("--target", type=float, default=0.5)
    ap.add_argument("--stop-mult", type=float, default=2.0, help="StopRMult (Play1: 2.0=ib_opposite; Play3: 0.5)")
    ap.add_argument("--overshoot", type=float, default=0.35, help="Play 3 overshoot threshold (default 0.35)")
    ap.add_argument("--from", dest="d_from", required=True)
    ap.add_argument("--to", dest="d_to", required=True)
    ap.add_argument("--session", default="NY AM IB")
    ap.add_argument("--nt8-json", help="Saved nt_backtest JSON for the same window")
    ap.add_argument("--out", help="Output CSV for the trade-by-trade diff")
    ap.add_argument(
        "--avwap-source",
        choices=["parquet", "onthefly", "none"],
        default="parquet",
        help=(
            "AVWAP gate source: 'parquet' (pre-computed ib_confluence, default), "
            "'onthefly' (vectorized from the harness's own bars — feed-consistent), "
            "or 'none' (ablation — disable AVWAP gate, keep TrendMisaligned)"
        ),
    )
    args = ap.parse_args()

    print(f"[parity] {args.ticker} Play {args.play} target={args.target} stop_mult={args.stop_mult}")
    print(f"         window {args.d_from} -> {args.d_to}  avwap-source={args.avwap_source}")

    # 1. Python side
    print("\n[1] Building Python trade ledger...")
    bars = load_1m_bars(args.ticker, args.d_from, args.d_to)
    print(f"    loaded {len(bars)} 1-min bars")
    facts = load_ib_facts(args.ticker, args.session, args.d_from, args.d_to)
    print(f"    loaded {len(facts)} ib_facts rows ({args.session})")
    conf_df = load_confluence(args.ticker, args.session, args.d_from, args.d_to)
    print(f"    loaded {len(conf_df)} confluence rows ({args.session})")

    py_trades = []
    skipped_by_filter = 0
    for _, frow in facts.iterrows():
        day = frow["td"].date()
        day_bars = bars[bars.index.date == day]
        if day_bars.empty:
            continue
        ib_high = float(frow["ib_high"])
        ib_low = float(frow["ib_low"])
        ib_range = float(frow["ib_range"])

        # Build the confluence row honoring --avwap-source (AVWAP feed fix).
        confluence_row = build_confluence_row(
            pd.Timestamp(day), conf_df, day_bars, args.avwap_source,
        )

        if args.play == 1:
            t = simulate_play1_day(
                day_bars, ib_high, ib_low, ib_range, args.target, args.stop_mult,
                confluence_row=confluence_row,
            )
        else:
            # Play 3 (fade) does not use the TrendMisaligned filter, but the
            # break_vs_avwap_0930 common gate still applies when confluence_row
            # is provided. simulate_play3_day currently ignores confluence_row;
            # pass it for forward-compat if the filter is later wired into P3.
            t = simulate_play3_day(
                day_bars, ib_high, ib_low, ib_range, args.target, args.stop_mult, args.overshoot,
            )
        if t is not None:
            t["date"] = day
            t["play"] = args.play
            t["avwap_source"] = args.avwap_source
            if confluence_row is not None:
                t["break_vs_avwap_0930"] = confluence_row.get("break_vs_avwap_0930", np.nan)
                t["trend_misaligned"] = confluence_row.get("trend_misaligned_with_break", np.nan)
            py_trades.append(t)
        else:
            skipped_by_filter += 1
    print(f"    Python produced {len(py_trades)} trades "
          f"({skipped_by_filter} skipped by ConfluenceFilter/avwap-source={args.avwap_source})")

    # 2. NT8 side
    nt8_trades = []
    if args.nt8_json:
        print(f"\n[2] Loading NT8 trade ledger from {args.nt8_json}...")
        with open(args.nt8_json, "r", encoding="utf-8") as f:
            payload = json.load(f)
        nt8_trades = parse_nt8_trades(payload)
        print(f"    NT8 produced {len(nt8_trades)} trades")
        # Also print the SA summary metrics if present
        m = payload.get("metrics") or payload.get("summary") or {}
        if m:
            print(f"    NT8 summary: {json.dumps(m, indent=2)[:400]}")
    else:
        print("\n[2] No --nt8-json. Run nt_backtest via the MCP bridge and save the JSON,")
        print("    then rerun with --nt8-json <path>.")

    # 3. Diff
    print("\n[3] Diffing...")
    diff_ledgers(py_trades, nt8_trades, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())