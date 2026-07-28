"""
parity_check.py
================
Reconcile the NT8 Strategy Analyzer (SA) backtest with the Python ORB validation
framework for a single trade_date.

Resolves the discrepancy documented in scratch/parity_loop_result.json:
  - H2 (stop/target fill resolution) was moderated as the dominant root cause.
  - H1 (entry-timing slippage) is the secondary contributor.
  - First tracer: a CHOP day (maximum false breakouts / intrabar wicks).

ADR compliance:
  - ADR-001 Timezone: explicit ET localization; UTC-naive parquet is localized.
  - ADR-002 Statistical Normalization: pnl reported as price %.
  - ADR-017 Zero-Loop: vectorized entry detection; a single bounded loop resolves
    the stop/target tie-break (commented as the bounded-loop exception).
  - ADR-020 Prop Firm RTH Liquidation: exit on the close of the 15:59 ET bar
    (NOT 16:00) -- matches the NT8 16:00 fence semantics.

Usage:
    # 1. Run the Python side for one day:
    python -m scripts.orb_generic.parity_check \
        --ticker NQ1 --date 2026-03-15 --or-duration 30 --target-r 2.0

    # 2. Run the NT8 side via the MCP bridge and save the JSON:
    #    mcp_nt-mcp-server_nt_backtest(
    #        strategy="ORB_AllDay_MultiTP", symbol="MNQ",
    #        from="2026-03-15", to="2026-03-15",
    #        period="Minute", periodValue=1, maxTrades=50)
    #    -> save the returned JSON to scratch/nt8_sa_2026-03-15.json

    # 3. Diff the two:
    python -m scripts.orb_generic.parity_check \
        --ticker NQ1 --date 2026-03-15 \
        --nt8-json scratch/nt8_sa_2026-03-15.json

The diff flags same-bar stop/target tie-breaks (H2) with a `tie_break` column.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Data loading -- LIVE storage per CLAUDE.md data architecture.
# ---------------------------------------------------------------------------
LIVE_STORAGE_TEMPLATE = "data/live/live_storage_-{ticker}.parquet"
RTH_OPEN_ET = time(9, 30)
RTH_CLOSE_ET = time(16, 0)                 # exclusive upper bound for entry scan
LIQUIDATION_BAR_CLOSE_ET = time(15, 59)    # ADR-020: exit on close of 15:59 bar


def load_rth_bars(ticker: str, trade_date: str) -> pd.DataFrame:
    """Load one trade_date of 1-min RTH bars from live storage.

    Returns a DataFrame indexed by ET-localized datetime with columns
    [open, high, low, close, volume]. Raises FileNotFoundError if the
    requested date is missing from live storage.
    """
    path = Path(LIVE_STORAGE_TEMPLATE.format(ticker=ticker))
    if not path.exists():
        # Fallback: fused loader covers historical + live (per CLAUDE.md)
        try:
            from scripts.utils.fused_data_loader import load_fused_data  # type: ignore
            df = load_fused_data(ticker)
        except Exception as exc:  # pragma: no cover - fallback path
            raise FileNotFoundError(
                f"Live storage {path} missing and fused_data_loader unavailable: {exc}"
            ) from exc
    else:
        df = pd.read_parquet(path)

    # Normalize timestamp column (live storage uses 'datetime' or index)
    if "datetime" in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    if "timestamp" not in df.columns:
        df = df.reset_index().rename(columns={df.columns[0]: "timestamp"})

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    # Localize to ET for session math (ADR-001)
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
    df["timestamp"] = df["timestamp"].dt.tz_convert("America/New_York")

    target_date = pd.Timestamp(trade_date, tz="America/New_York").date()
    day_df = df[df["timestamp"].dt.date == target_date].copy()
    if day_df.empty:
        raise FileNotFoundError(f"No bars for {ticker} on {trade_date} in live storage")

    day_df = day_df.set_index("timestamp").sort_index()
    mask = (day_df.index.time >= RTH_OPEN_ET) & (day_df.index.time < RTH_CLOSE_ET)
    day_df = day_df.loc[mask]
    if day_df.empty:
        raise ValueError(f"No RTH bars for {trade_date}")
    return day_df[["open", "high", "low", "close", "volume"]].astype(float)


# ---------------------------------------------------------------------------
# Python ORB simulation -- vectorized entry detection + bounded exit loop.
# ---------------------------------------------------------------------------
def run_orb_simulation(
    bars: pd.DataFrame,
    or_duration: int = 30,
    target_r: float = 2.0,
    fee_per_trade: float = 0.0,
) -> Dict[str, Any]:
    """Replicates the or_breakout logic from signal_generators.py.

    - OR window: 9:30 + or_duration minutes.
    - Long entry: first close > OR high, AFTER the OR window closes.
    - Short entry: first close < OR low.
    - Stop: opposite side of OR (OR low for long, OR high for short).
    - Target: target_r * risk.
    - Exit: stop, target, or close-of-15:59 liquidation (ADR-020).

    Returns a dict with entry/exit fields and an explicit `tie_break` flag
    set when stop AND target were both touched on the same exit bar (the H2
    discrepancy signature).
    """
    or_bars = bars.iloc[:or_duration]
    if len(or_bars) < or_duration:
        return {"error": "insufficient_or_bars", "n_bars": len(or_bars)}
    or_high = float(or_bars["high"].max())
    or_low = float(or_bars["low"].min())
    risk = or_high - or_low
    if risk <= 0:
        return {"error": "zero_range", "or_high": or_high, "or_low": or_low}

    trade_df = bars.iloc[or_duration:]
    # Vectorized entry detection (ADR-017)
    long_sig = trade_df["close"] > or_high
    short_sig = trade_df["close"] < or_low

    long_idx = trade_df.index[long_sig].min() if long_sig.any() else None
    short_idx = trade_df.index[short_sig].min() if short_sig.any() else None
    if long_idx is None and short_idx is None:
        return {"error": "no_breakout", "or_high": or_high, "or_low": or_low}

    # First breakout wins
    if long_idx is not None and (short_idx is None or long_idx <= short_idx):
        side = "LONG"
        entry_idx = long_idx
    else:
        side = "SHORT"
        entry_idx = short_idx

    entry_price = float(bars.loc[entry_idx, "close"])
    if side == "LONG":
        stop_price = or_low
        target_price = entry_price + risk * target_r
    else:
        stop_price = or_high
        target_price = entry_price - risk * target_r

    # Bounded trade-resolution loop (ADR-017 exception: tie-break needs sequence).
    # Starts on the bar AFTER entry. Same-bar stop+target touches are flagged.
    post = bars.loc[entry_idx:].iloc[1:]
    exit_price: Optional[float] = None
    exit_time = None
    exit_reason = "none"
    tie_break = False

    for ts, row in post.iterrows():
        stop_touched = (
            row["low"] <= stop_price if side == "LONG" else row["high"] >= stop_price
        )
        target_touched = (
            row["high"] >= target_price if side == "LONG" else row["low"] <= target_price
        )
        if stop_touched and target_touched:
            # H2 signature: same-bar tie-break. Python resolves to stop (conservative);
            # NT8 tick-level may resolve to target. Flag for the diff.
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
        # ADR-020: liquidate on the close of the 15:59 ET bar (not 16:00)
        if ts.time() >= LIQUIDATION_BAR_CLOSE_ET:
            exit_price = float(row["close"])
            exit_time = ts
            exit_reason = "liquidation_1559"
            break

    if exit_price is None:
        last_ts = post.index[-1] if not post.empty else entry_idx
        exit_price = float(bars.loc[last_ts, "close"])
        exit_time = last_ts
        exit_reason = "end_of_data"

    gross = (exit_price - entry_price) if side == "LONG" else (entry_price - exit_price)
    net = gross - fee_per_trade
    pnl_pct = (net / entry_price) * 100.0  # ADR-002

    return {
        "side": side,
        "or_high": or_high,
        "or_low": or_low,
        "risk": risk,
        "entry_time": str(entry_idx),
        "entry_price": entry_price,
        "stop": stop_price,
        "target": target_price,
        "exit_time": str(exit_time),
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "tie_break": tie_break,            # H2 discrepancy flag
        "gross_pnl": gross,
        "net_pnl": net,
        "pnl_pct": pnl_pct,
        "fee_per_trade": fee_per_trade,
    }


# ---------------------------------------------------------------------------
# NT8 SA JSON parsing -- tolerant of schema variations across NT8 versions.
# ---------------------------------------------------------------------------
def parse_nt8_trades(nt8_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract a normalized trade list from an nt_backtest JSON payload.

    The MCP `nt_backtest` tool returns trades under varying keys across
    NT8 builds (`trades`, `Trades`, `Results.Trades`). Tolerant; returns
    [] if no trade list is found.
    """
    if not isinstance(nt8_json, dict):
        return []
    for key in ("trades", "Trades", "results"):
        val = nt8_json.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return val
        if isinstance(val, dict):
            inner = val.get("trades") or val.get("Trades")
            if isinstance(inner, list):
                return inner
    # Some payloads nest under "SelectedResult"
    sel = nt8_json.get("SelectedResult") or nt8_json.get("selectedResult")
    if isinstance(sel, dict):
        for key in ("trades", "Trades"):
            inner = sel.get(key)
            if isinstance(inner, list):
                return inner
    return []


def normalize_nt8_trade(trade: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort normalization of a single NT8 trade dict to the keys
    the diff table expects."""
    def _get(*keys: str, default=None):
        for k in keys:
            if k in trade and trade[k] is not None:
                return trade[k]
        return default

    return {
        "side": str(_get("side", "Side", "direction", "Direction", default="")).upper(),
        "entry_time": str(_get("entryTime", "EntryTime", "entry_time", "EntryDate", default="")),
        "entry_price": float(_get("entryPrice", "EntryPrice", "entry_price", "entry", "Entry", default=float("nan"))),
        "stop": float(_get("stop", "Stop", "stopPrice", "StopPrice", default=float("nan"))),
        "target": float(_get("target", "Target", "targetPrice", "TargetPrice", "limit", "Limit", default=float("nan"))),
        "exit_time": str(_get("exitTime", "ExitTime", "exit_time", "ExitDate", default="")),
        "exit_price": float(_get("exitPrice", "ExitPrice", "exit_price", "exit", "Exit", default=float("nan"))),
        "exit_reason": str(_get("exitReason", "ExitReason", "reason", "Reason", default="")),
        "pnl": float(_get("pnl", "PnL", "Profit", "profit", default=float("nan"))),
    }


def nt8_pnl_pct(trade: Dict[str, Any]) -> Optional[float]:
    """Compute ADR-002 pnl_pct from an NT8 trade if entry_price is nonzero."""
    entry = trade.get("entry_price")
    pnl = trade.get("pnl")
    if entry is None or pnl is None or entry in (0, float("nan")) or pnl != pnl:
        return None
    return (pnl / entry) * 100.0


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------
def diff_trades(py: Dict[str, Any], nt8: Dict[str, Any]) -> None:
    rows = [
        ("entry_time", str(py.get("entry_time")), str(nt8.get("entry_time"))),
        ("entry_price", py.get("entry_price"), nt8.get("entry_price")),
        ("stop", py.get("stop"), nt8.get("stop")),
        ("target", py.get("target"), nt8.get("target")),
        ("exit_time", str(py.get("exit_time")), str(nt8.get("exit_time"))),
        ("exit_price", py.get("exit_price"), nt8.get("exit_price")),
        ("exit_reason", py.get("exit_reason"), nt8.get("exit_reason")),
        ("pnl_pct", py.get("pnl_pct"), nt8_pnl_pct(nt8)),
    ]
    print("\n" + "=" * 78)
    print("PARITY DIFF  (Python vs NT8 Strategy Analyzer)")
    print("=" * 78)
    print(f"{'metric':<14} | {'python':<22} | {'nt8':<22} | {'match'}")
    print("-" * 78)
    for name, pv, nv in rows:
        match = "?"
        try:
            match = "OK" if abs(float(pv) - float(nv)) < 1e-6 else "DIFF"
        except (TypeError, ValueError):
            match = "OK" if str(pv) == str(nv) else "DIFF"
        print(f"{name:<14} | {str(pv):<22} | {str(nv):<22} | {match}")

    # H2 signature banner
    if py.get("tie_break"):
        print("\n[H2 SIGNATURE] Python resolved a same-bar stop+target tie-break")
        print("               to STOP (conservative). If NT8 shows target exit, the")
        print("               discrepancy root cause is stop/target fill resolution.")
    if py.get("exit_reason", "").startswith("liquidation") and nt8.get("exit_reason") not in (
        "", "liquidation_1559", "liquidation", "Liquidation"
    ):
        print("\n[ADR-020 FENCE] Python liquidated at close of 15:59 ET bar; NT8")
        print("                did not. Check NT8 session template / FlattenBy setting.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="ORB Python<->NT8 parity checker")
    ap.add_argument("--ticker", required=True, help="e.g. NQ1, ES1")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD trade date")
    ap.add_argument("--or-duration", type=int, default=30)
    ap.add_argument("--target-r", type=float, default=2.0)
    ap.add_argument("--fee-per-trade", type=float, default=0.0,
                    help="Round-turn commission in price units (e.g. 1.5 for MNQ)")
    ap.add_argument("--nt8-json", help="Path to saved nt_backtest JSON result")
    args = ap.parse_args()

    print(f"[parity] {args.ticker} {args.date}  OR={args.or_duration}m  R={args.target_r}  fee={args.fee_per_trade}")

    # 1. Python side
    try:
        bars = load_rth_bars(args.ticker, args.date)
    except (FileNotFoundError, ValueError) as e:
        print(f"[parity] data error: {e}")
        return 2
    print(f"[parity] loaded {len(bars)} RTH bars for {args.date}")

    py = run_orb_simulation(bars, args.or_duration, args.target_r, args.fee_per_trade)
    if "error" in py:
        print(f"[parity] python sim: {py['error']}  ({py})")
        if not args.nt8_json:
            return 0
    else:
        print(f"[parity] python: {py['side']} entry={py['entry_price']} stop={py['stop']} "
              f"target={py['target']} exit={py['exit_price']} ({py['exit_reason']}) "
              f"tie_break={py['tie_break']} pnl_pct={py['pnl_pct']:.4f}")

    # 2. NT8 side
    if not args.nt8_json:
        print("\n[parity] No --nt8-json provided. Run this via the MCP bridge and")
        print("         save the JSON, then rerun with --nt8-json <path>:")
        print("         mcp_nt-mcp-server_nt_backtest(")
        print(f"             strategy='ORB_AllDay_MultiTP', symbol='{args.ticker}',")
        print(f"             from='{args.date}', to='{args.date}',")
        print(f"             period='Minute', periodValue=1, maxTrades=50)")
        return 0

    with open(args.nt8_json, "r", encoding="utf-8") as f:
        nt8_payload = json.load(f)
    trades = parse_nt8_trades(nt8_payload)
    if not trades:
        print(f"[parity] no trades parsed from {args.nt8_json} -- schema may differ.")
        print("         Inspect the JSON and extend parse_nt8_trades() if needed.")
        return 3
    print(f"[parity] parsed {len(trades)} NT8 trade(s)")
    nt8 = normalize_nt8_trade(trades[0])

    # 3. Diff
    if "error" not in py:
        diff_trades(py, nt8)
    else:
        print(f"[parity] python produced no trade ({py['error']}); NT8 has {len(trades)}.")
        print("         If NT8 traded where Python did not, suspect entry-timing (H1)")
        print("         or session-filter mismatch (H3).")
    return 0


if __name__ == "__main__":
    sys.exit(main())