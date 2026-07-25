"""Phase 5.5 — Empirical Target Engine (PRD FR-10, BL-3).

Gunship-style empirical percentile targets. Instead of fixed R-multiples
(0.25R, 0.5R, 1.0R), compute targets from the actual MFE distribution
of winning trades, split by direction (bull/bear) and filtered by outcome.

Outputs per (symbol, session_slot, time_basis, play):
  - P20/P50/P75/P90 MFE of winners → candidate target levels (in R)
  - P25/P50/P80 MAE of winners → candidate stop levels (in R)
  - R:R ratio for each target/stop combo
  - WR and expectancy at each combo
  - Recommended target/stop pair based on max expectancy

Reads:  data/derived/ib_play_detail_{SYM}.parquet (has mae, mfe, result, realized_r, target_lvl)
Writes: data/derived/ib_empirical_targets.parquet

Usage:
    python -m scripts.edgeful.ib_empirical_targets --instruments NQ1
    python -m scripts.edgeful.ib_empirical_targets --instruments NQ1,ES1,YM1,RTY1,CL1,GC1
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "derived"
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

GROUP_COLS = ["symbol", "session_slot", "time_basis", "play"]

# Percentile grid (Gunship-inspired)
MFE_PERCENTILES = [20, 50, 75, 90]
MAE_PERCENTILES = [25, 50, 80]


def compute_empirical_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Compute empirical percentile-based target and stop levels.

    For each (symbol, session, time_basis, play) group:
      1. Split trades by direction (bull = result in [0,1], bear = result in [-1,0])
      2. Among winners (result == 1), compute MFE percentiles → target candidates
      3. Among winners, compute MAE percentiles → stop candidates
      4. For each (target, stop) combo, compute WR and expectancy
      5. Select the best combo by expectancy

    Parameters
    ----------
    df : pd.DataFrame
        ib_play_detail with columns: mae, mfe, result, realized_r, target_lvl,
        direction (if available), session_slot, time_basis, play, symbol

    Returns
    -------
    pd.DataFrame
        One row per (symbol, session, time_basis, play, target_pctile, stop_pctile)
    """
    rows = []

    for key, g in df.groupby(GROUP_COLS, sort=False):
        winners = g[g["result"] == 1]
        n_win = len(winners)
        n_total = len(g)
        if n_win < 30:
            continue

        mfe_win = winners["mfe"].astype(float).abs()
        mae_win = winners["mae"].astype(float).abs()

        # Compute MFE percentiles (target candidates in R)
        mfe_pctiles = {}
        for p in MFE_PERCENTILES:
            mfe_pctiles[p] = float(mfe_win.quantile(p / 100.0))

        # Compute MAE percentiles (stop candidates in R)
        mae_pctiles = {}
        for p in MAE_PERCENTILES:
            mae_pctiles[p] = float(mae_win.quantile(p / 100.0))

        # For each target/stop combo, compute WR and expectancy
        for tp_name, tp_r in mfe_pctiles.items():
            for sl_name, sl_r in mae_pctiles.items():
                if sl_r <= 0 or tp_r <= 0:
                    continue

                # Simulate: trade is a winner if MFE >= target_r (hit target)
                # Trade is a loser if MAE >= stop_r first (hit stop)
                # Approximation: if mfe >= tp_r and mae < sl_r → win
                #                if mae >= sl_r → loss (stopped out)
                #                else: depends on which hit first (use mfe >= tp_r as proxy)
                g_mfe = g["mfe"].abs().values
                g_mae = g["mae"].abs().values

                hit_tp = g_mfe >= tp_r
                hit_sl = g_mae >= sl_r

                # Winner: hit TP before SL (approximation: MFE >= TP and not stopped first)
                # Conservative: if both hit, assume SL first (worst case)
                is_win = hit_tp & ~hit_sl
                is_loss = hit_sl
                is_no_hit = ~hit_tp & ~hit_sl

                # PnL: win = +tp_r, loss = -sl_r, no_hit = 0 (or close at end)
                pnl = np.where(is_win, tp_r, np.where(is_loss, -sl_r, 0.0))
                wr = float(is_win.sum() / n_total) if n_total else 0.0
                expectancy = float(pnl.mean()) if len(pnl) else 0.0
                rr = tp_r / sl_r if sl_r > 0 else 0.0

                rows.append({
                    **dict(zip(GROUP_COLS, key)),
                    "target_pctile": tp_name,
                    "target_r": round(tp_r, 4),
                    "stop_pctile": sl_name,
                    "stop_r": round(sl_r, 4),
                    "rr_ratio": round(rr, 4),
                    "win_rate": round(wr, 4),
                    "expectancy_r": round(expectancy, 4),
                    "n_trades": n_total,
                    "n_winners": n_win,
                })

    return pd.DataFrame(rows)


def select_best_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Select the best target/stop combo per group by expectancy.

    Also includes the "balanced" combo (P50 MFE / P50 MAE) for reference.
    """
    # Best by expectancy
    best = df.loc[df.groupby(GROUP_COLS)["expectancy_r"].idxmax()].copy()
    best["selection"] = "best_expectancy"

    # Balanced (P50/P50)
    balanced = df[(df["target_pctile"] == 50) & (df["stop_pctile"] == 50)].copy()
    if not balanced.empty:
        balanced["selection"] = "balanced_p50p50"
        best = pd.concat([best, balanced], ignore_index=True)

    # Aggressive (P75 MFE / P25 MAE — wider target, tighter stop)
    aggressive = df[(df["target_pctile"] == 75) & (df["stop_pctile"] == 25)].copy()
    if not aggressive.empty:
        aggressive["selection"] = "aggressive_p75p25"
        best = pd.concat([best, aggressive], ignore_index=True)

    # Conservative (P20 MFE / P80 MAE — tight target, wide stop)
    conservative = df[(df["target_pctile"] == 20) & (df["stop_pctile"] == 80)].copy()
    if not conservative.empty:
        conservative["selection"] = "conservative_p20p80"
        best = pd.concat([best, conservative], ignore_index=True)

    return best.sort_values(GROUP_COLS + ["selection"]).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(
        description="Compute empirical percentile targets (BL-3, FR-10)"
    )
    parser.add_argument("--instruments", default=",".join(INSTRUMENTS))
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]

    frames = []
    for sym in symbols:
        path = DERIVED / f"ib_play_detail_{sym}.parquet"
        if not path.exists():
            print(f"[WARN] {path} not found, skipping {sym}")
            continue
        df = pd.read_parquet(path)
        out = compute_empirical_targets(df)
        print(f"[{sym}] {len(out)} target/stop combos")
        frames.append(out)

    if frames:
        final = pd.concat(frames, ignore_index=True)
        final.to_parquet(DERIVED / "ib_empirical_targets.parquet", index=False)
        print(f"[ALL] wrote {len(final)} rows to {DERIVED / 'ib_empirical_targets.parquet'}")

        # Also write best selections
        best = select_best_targets(final)
        best.to_parquet(DERIVED / "ib_empirical_targets_best.parquet", index=False)
        print(f"[ALL] wrote {len(best)} best selections to {DERIVED / 'ib_empirical_targets_best.parquet'}")

        # Print summary for first symbol
        sym = symbols[0]
        sym_best = best[best["symbol"] == sym]
        print(f"\n=== Best targets for {sym} ===")
        print(sym_best[["session_slot", "play", "selection", "target_r", "stop_r",
                         "rr_ratio", "win_rate", "expectancy_r", "n_trades"]].to_string(index=False))


if __name__ == "__main__":
    main()