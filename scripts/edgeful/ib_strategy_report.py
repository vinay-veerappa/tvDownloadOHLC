"""
IB Strategy Statistics Report Generator (PRD §8 success criteria).

Produces a comprehensive breakdown of every IB strategy's statistics:
- Overall WR, expectancy, N, profit factor, avg MFE/MAE
- By year, by month, by day-of-week
- By regime (trend/normal/range/skip)
- By session (NY AM IB, NY PM IB, London, Tokyo, Globex, Midnight OR)
- By target level (0.25x, 0.5x, 0.75x, 1.0x)
- Filter lift table (top filters per play)

Reads:  data/derived/ib_play_detail_{SYM}.parquet
        data/derived/ib_facts_{SYM}.parquet
        data/derived/ib_confluence_{SYM}.parquet
        data/derived/ib_regime_{SYM}.parquet
        data/derived/ib_filter_effectiveness.parquet
        data/derived/ib_optimal_stops.parquet
        data/derived/ib_optimal_ladders.parquet
        data/derived/ib_break_speed_stats.parquet
        data/derived/ib_time_decay_curves.parquet
        data/derived/ib_empirical_baselines.json

Writes: docs/strategies/initial_balance_break/STRATEGY_STATISTICS.md
        (human-readable markdown report)
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "derived"
REPORT_DIR = ROOT / "docs" / "strategies" / "initial_balance_break"
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
PLAY_NAMES = {1: "Play 1 — IB Breakout", 2: "Play 2 — IB Retest", 3: "Play 3 — IB Fade"}
MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
DOW_NAMES = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}


def _stats(g: pd.DataFrame) -> Dict:
    """Core stats for a group of trades."""
    n = len(g)
    if n == 0:
        return {"n": 0, "wr": np.nan, "expectancy": np.nan, "pf": np.nan,
                "avg_mfe": np.nan, "avg_mae": np.nan, "avg_rr": np.nan}
    wins = g[g["result"] == 1]
    losses = g[g["result"] == -1]
    n_w = len(wins)
    n_l = len(losses)
    gross_win = float(wins["realized_r"].sum()) if n_w else 0.0
    gross_loss = float(losses["realized_r"].abs().sum()) if n_l else 0.0
    return {
        "n": n, "wr": round(n_w / n, 4) if n else np.nan,
        "expectancy": round(float(g["realized_r"].mean()), 4),
        "pf": round(gross_win / gross_loss, 4) if gross_loss > 0 else np.nan,
        "avg_mfe": round(float(g["mfe"].mean()), 4),
        "avg_mae": round(float(g["mae"].mean()), 4),
        "avg_rr": round(float(g["realized_r"].mean()), 4),
        "n_wins": n_w, "n_losses": n_l,
    }


def _fmt_table(rows: List[Dict], cols: List[str], headers: List[str]) -> str:
    """Render list-of-dicts as a markdown table."""
    if not rows:
        return "*(no data)*\n"
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) if not pd.isna(r.get(c, np.nan)) else "—" for c in cols) + " |")
    return "\n".join(lines) + "\n"


def build_report(symbols: List[str]) -> str:
    sections = []
    sections.append("# IB Strategy Statistics — Comprehensive Report\n")
    sections.append(f"**Generated:** 2026-07-25  \n**Symbols:** {', '.join(symbols)}\n")

    # ── Empirical baselines ──
    baselines_path = DERIVED / "ib_empirical_baselines.json"
    if baselines_path.exists():
        bl = json.load(open(baselines_path))
        sections.append("\n## 1. Empirical Baselines (No-Filter Reference)\n")
        sections.append("These are the reference win rates every filter's lift is measured against.\n")
        sections.append("\n### TrevorTrades 10-Year ES Priors\n")
        tt = bl.get("trevortrades_es", {})
        tt_rows = [{"metric": k.replace("_", " ").title(), "value": v} for k, v in tt.items()]
        sections.append(_fmt_table(tt_rows, ["metric", "value"], ["Metric", "Value"]))
        sections.append("\n### Per-Symbol Baselines (from this pipeline)\n")
        for sym, sb in bl.get("per_symbol", {}).items():
            sections.append(f"\n**{sym}:**\n")
            sb_rows = [{"target": k, "baseline_wr": v} for k, v in sb.items()]
            sections.append(_fmt_table(sb_rows, ["target", "baseline_wr"], ["Target", "Baseline WR"]))

    # ── Per-symbol per-play overall stats ──
    sections.append("\n## 2. Overall Strategy Statistics by Symbol\n")
    for sym in symbols:
        play_path = DERIVED / f"ib_play_detail_{sym}.parquet"
        if not play_path.exists():
            continue
        df = pd.read_parquet(play_path)
        df["trading_day"] = pd.to_datetime(df["trading_day"])
        sections.append(f"\n### {sym} — Overall (all sessions, all target levels)\n")
        rows = []
        for play in [1, 2, 3]:
            g = df[df["play"] == play]
            s = _stats(g)
            s["play"] = PLAY_NAMES.get(play, f"Play {play}")
            rows.append(s)
        sections.append(_fmt_table(rows,
            ["play", "n", "wr", "expectancy", "pf", "avg_mfe", "avg_mae", "n_wins", "n_losses"],
            ["Play", "N", "Win Rate", "Expectancy (R)", "Profit Factor", "Avg MFE", "Avg MAE", "Wins", "Losses"]))

        # By session
        sections.append(f"\n### {sym} — By Session\n")
        rows = []
        for (sess, play), g in df.groupby(["session_slot", "play"], sort=False):
            s = _stats(g)
            s["session"] = sess
            s["play"] = PLAY_NAMES.get(play, f"Play {play}")
            rows.append(s)
        sections.append(_fmt_table(rows,
            ["session", "play", "n", "wr", "expectancy", "pf"],
            ["Session", "Play", "N", "WR", "Exp (R)", "PF"]))

        # By target level
        sections.append(f"\n### {sym} — By Target Level (extension multiplier)\n")
        rows = []
        for (play, lvl), g in df.groupby(["play", "target_lvl"], sort=False):
            s = _stats(g)
            s["play"] = PLAY_NAMES.get(play, f"Play {play}")
            s["target_lvl"] = f"{lvl}x"
            rows.append(s)
        sections.append(_fmt_table(rows,
            ["play", "target_lvl", "n", "wr", "expectancy", "pf"],
            ["Play", "Target", "N", "WR", "Exp (R)", "PF"]))

        # By year
        sections.append(f"\n### {sym} — By Year\n")
        df["year"] = df["trading_day"].dt.year
        rows = []
        for (year, play), g in df.groupby(["year", "play"], sort=False):
            s = _stats(g)
            s["year"] = year
            s["play"] = PLAY_NAMES.get(play, f"Play {play}")
            rows.append(s)
        sections.append(_fmt_table(rows,
            ["year", "play", "n", "wr", "expectancy", "pf"],
            ["Year", "Play", "N", "WR", "Exp (R)", "PF"]))

        # By month
        sections.append(f"\n### {sym} — By Month (aggregated across all years)\n")
        df["month"] = df["trading_day"].dt.month
        rows = []
        for (month, play), g in df.groupby(["month", "play"], sort=False):
            s = _stats(g)
            s["month"] = MONTH_NAMES.get(month, str(month))
            s["play"] = PLAY_NAMES.get(play, f"Play {play}")
            rows.append(s)
        sections.append(_fmt_table(rows,
            ["month", "play", "n", "wr", "expectancy", "pf"],
            ["Month", "Play", "N", "WR", "Exp (R)", "PF"]))

        # By day of week
        sections.append(f"\n### {sym} — By Day of Week\n")
        df["dow"] = df["trading_day"].dt.dayofweek
        rows = []
        for (dow, play), g in df.groupby(["dow", "play"], sort=False):
            s = _stats(g)
            s["dow"] = DOW_NAMES.get(dow, str(dow))
            s["play"] = PLAY_NAMES.get(play, f"Play {play}")
            rows.append(s)
        sections.append(_fmt_table(rows,
            ["dow", "play", "n", "wr", "expectancy", "pf"],
            ["Day", "Play", "N", "WR", "Exp (R)", "PF"]))

    # ── Regime breakdown ──
    sections.append("\n## 3. Regime-Adjusted Statistics\n")
    for sym in symbols:
        regime_path = DERIVED / f"ib_regime_{sym}.parquet"
        play_path = DERIVED / f"ib_play_detail_{sym}.parquet"
        if not regime_path.exists() or not play_path.exists():
            continue
        regime = pd.read_parquet(regime_path)
        plays = pd.read_parquet(play_path)
        plays["trading_day"] = plays["trading_day"].astype(str)
        regime["trading_day"] = regime["trading_day"].astype(str)
        merged = plays.merge(regime[["trading_day", "session_slot", "time_basis", "ib_regime"]],
                             on=["trading_day", "session_slot", "time_basis"], how="left")
        sections.append(f"\n### {sym} — By Regime\n")
        rows = []
        for (reg, play), g in merged.groupby(["ib_regime", "play"], sort=False):
            if pd.isna(reg):
                continue
            s = _stats(g)
            s["regime"] = reg
            s["play"] = PLAY_NAMES.get(play, f"Play {play}")
            rows.append(s)
        sections.append(_fmt_table(rows,
            ["regime", "play", "n", "wr", "expectancy", "pf"],
            ["Regime", "Play", "N", "WR", "Exp (R)", "PF"]))

    # ── Filter effectiveness ──
    eff_path = DERIVED / "ib_filter_effectiveness.parquet"
    if eff_path.exists():
        sections.append("\n## 4. Top Filter Lifts (Phase 4a)\n")
        eff = pd.read_parquet(eff_path)
        sections.append("\n### Top 15 filters by lift vs without-flag (all targets pooled)\n")
        top = eff.sort_values("lift_vs_without", ascending=False).head(15)
        rows = top[["symbol", "target", "flag", "lift_vs_without", "rate_with", "rate_without", "n_with"]].to_dict("records")
        sections.append(_fmt_table(rows,
            ["symbol", "target", "flag", "lift_vs_without", "rate_with", "rate_without", "n_with"],
            ["Symbol", "Target", "Filter", "Lift", "WR (flag on)", "WR (flag off)", "N (flag on)"]))

    # ── Optimal stops ──
    stops_path = DERIVED / "ib_optimal_stops.parquet"
    if stops_path.exists():
        sections.append("\n## 5. MAE-Calibrated Stops (Phase 5.1)\n")
        stops = pd.read_parquet(stops_path)
        sections.append("\n### Sample: NY AM IB / ET_fixed, by play × target\n")
        sample = stops[(stops.session_slot == "NY AM IB") & (stops.time_basis == "ET_fixed")]
        rows = sample[["symbol", "play", "target_lvl", "p95_mae_winners", "p99_mae_winners",
                      "optimal_stop_r", "wr_at_optimal_stop", "expectancy_at_optimal_stop",
                      "n_winners", "n_trades"]].to_dict("records")
        sections.append(_fmt_table(rows,
            ["symbol", "play", "target_lvl", "p95_mae_winners", "p99_mae_winners",
             "optimal_stop_r", "wr_at_optimal_stop", "expectancy_at_optimal_stop", "n_winners", "n_trades"],
            ["Symbol", "Play", "Target", "P95 MAE", "P99 MAE", "Stop (R)", "WR @ stop", "Exp @ stop", "N win", "N total"]))

    # ── Optimal ladders ──
    lad_path = DERIVED / "ib_optimal_ladders.parquet"
    if lad_path.exists():
        sections.append("\n## 6. Optimal Profit Ladders (Phase 5.3)\n")
        lad = pd.read_parquet(lad_path)
        sections.append("\n### Sample: NY AM IB / ET_fixed, by play × target\n")
        sample = lad[(lad.session_slot == "NY AM IB") & (lad.time_basis == "ET_fixed")]
        rows = sample[["symbol", "play", "target_lvl", "tp1_pct", "tp2_pct", "tp3_pct",
                       "runner_pct", "ladder_expectancy", "baseline_expectancy", "n_trades"]].to_dict("records")
        sections.append(_fmt_table(rows,
            ["symbol", "play", "target_lvl", "tp1_pct", "tp2_pct", "tp3_pct",
             "runner_pct", "ladder_expectancy", "baseline_expectancy", "n_trades"],
            ["Symbol", "Play", "Target", "TP1%", "TP2%", "TP3%", "Runner%", "Ladder Exp", "Baseline Exp", "N"]))

    # ── Break speed ──
    bs_path = DERIVED / "ib_break_speed_stats.parquet"
    if bs_path.exists():
        sections.append("\n## 7. Break Speed Statistics (Phase 5.4)\n")
        bs = pd.read_parquet(bs_path)
        sections.append("\n### Sample: NQ1, NY AM IB / ET_fixed, by play × speed bucket\n")
        sample = bs[(bs.symbol == "NQ1") & (bs.session_slot == "NY AM IB") & (bs.time_basis == "ET_fixed")]
        rows = sample[["play", "target_lvl", "speed_bucket", "n_trades", "win_rate",
                       "expectancy", "mean_speed"]].to_dict("records")
        sections.append(_fmt_table(rows,
            ["play", "target_lvl", "speed_bucket", "n_trades", "win_rate", "expectancy", "mean_speed"],
            ["Play", "Target", "Speed", "N", "WR", "Exp (R)", "Mean Speed"]))

    # ── CISD breakdown ──
    sections.append("\n## 8. CISD (Change in State of Delivery) Impact\n")
    for sym in symbols:
        conf_path = DERIVED / f"ib_confluence_{sym}.parquet"
        play_path = DERIVED / f"ib_play_detail_{sym}.parquet"
        if not conf_path.exists() or not play_path.exists():
            continue
        conf = pd.read_parquet(conf_path)
        plays = pd.read_parquet(play_path)
        if "ib_cisd_dir" not in conf.columns:
            sections.append(f"\n### {sym}: CISD fields not yet computed\n")
            continue
        conf["trading_day"] = conf["trading_day"].astype(str)
        plays["trading_day"] = plays["trading_day"].astype(str)
        merged = plays.merge(conf[["trading_day", "session_slot", "time_basis", "ib_cisd_dir",
                                     "ib_cisd_bullish", "ib_cisd_bearish"]],
                              on=["trading_day", "session_slot", "time_basis"], how="left")
        sections.append(f"\n### {sym} — Play outcomes by CISD direction\n")
        rows = []
        for (cisd, play), g in merged.groupby(["ib_cisd_dir", "play"], sort=False):
            if pd.isna(cisd):
                continue
            s = _stats(g)
            s["cisd_dir"] = {1: "Bullish CSD", -1: "Bearish CSD", 0: "No CSD"}.get(int(cisd), "Unknown")
            s["play"] = PLAY_NAMES.get(play, f"Play {play}")
            rows.append(s)
        sections.append(_fmt_table(rows,
            ["cisd_dir", "play", "n", "wr", "expectancy", "pf"],
            ["CISD Direction", "Play", "N", "WR", "Exp (R)", "PF"]))

    # ── Conviction score distribution ──
    sections.append("\n## 9. Conviction Score v2 Distribution\n")
    for sym in symbols:
        conf_path = DERIVED / f"ib_confluence_{sym}.parquet"
        if not conf_path.exists():
            continue
        conf = pd.read_parquet(conf_path)
        if "conviction_score_v2" not in conf.columns:
            continue
        cs = conf["conviction_score_v2"].dropna()
        sections.append(f"\n### {sym}\n")
        sections.append(f"- Rows: {len(cs)}\n")
        sections.append(f"- Mean: {cs.mean():.3f}\n")
        sections.append(f"- Median: {cs.median():.3f}\n")
        sections.append(f"- Range: {cs.min():.3f} – {cs.max():.3f}\n")
        sections.append(f"- Score > 0: {(cs > 0).sum()} rows ({(cs > 0).mean()*100:.1f}%)\n")
        sections.append(f"- Score ≥ 0.5: {(cs >= 0.5).sum()} rows ({(cs >= 0.5).mean()*100:.1f}%)\n")
        sections.append(f"- Score ≥ 0.7: {(cs >= 0.7).sum()} rows ({(cs >= 0.7).mean()*100:.1f}%)\n")

    # ── Filter stacks ──
    stk_path = DERIVED / "ib_filter_stacks.parquet"
    if stk_path.exists():
        sections.append("\n## 10. Optimal Filter Stacks (Phase 4c — Greedy Forward Selection)\n")
        stk = pd.read_parquet(stk_path)
        rows = stk[["symbol", "target", "filter_stack", "n_filters", "n_trades",
                    "wr", "baseline_wr", "expectancy"]].to_dict("records")
        sections.append(_fmt_table(rows,
            ["symbol", "target", "filter_stack", "n_filters", "n_trades", "wr", "baseline_wr", "expectancy"],
            ["Symbol", "Target", "Filter Stack", "# Filters", "N Trades", "WR", "Baseline WR", "Exp (R)"]))

    sections.append("\n## 11. Strategy Catalog Reference\n")
    sections.append("See [PRD §10](../../../plans/2026-07-24-ib-data-gathering-plan.md) for the full 83-strategy catalog, 21 entry techniques, 17 stops, 20 take-profit techniques.\n")
    sections.append("\n## 12. Methodology Notes\n")
    sections.append("- **Win Rate (WR):** fraction of trades with result == 1.\n")
    sections.append("- **Expectancy:** mean of `realized_r` (in R-multiples).\n")
    sections.append("- **Profit Factor:** gross win R / gross loss R.\n")
    sections.append("- **MFE/MAE:** max favorable / max adverse excursion in R.\n")
    sections.append("- **Lift:** WR(flag on) − WR(flag off). Measured against per-symbol baseline, not naive 50%.\n")
    sections.append("- **Regime:** from `ib_regime_{SYM}.parquet` (Phase 6 classifier: trend/normal/range/skip).\n")
    sections.append("- **CISD:** from `ib_cisd_dir` in confluence (1=bullish CSD fired, -1=bearish, 0=none). Per the CISD document, a CSD fires when price trades through the candidate candle's open (not close-based).\n")
    sections.append("- All stats are in-sample (no train/test split in this report). Phase 4's validation harness applies bootstrap CIs and min-N guards for production use.\n")

    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default=",".join(INSTRUMENTS))
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]
    report = build_report(symbols)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / "STRATEGY_STATISTICS.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"Wrote {len(report)} chars to {out_path}")


if __name__ == "__main__":
    main()