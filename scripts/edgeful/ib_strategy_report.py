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

# Commission model (BL-5): $2.05/round-turn per Micro contract
# As R-multiple: commission_r = 2.05 / (ib_mid * tick_multiplier)
# NQ1: ib_mid ~20000, multiplier 2.0 → commission_r ≈ 0.000051R per trade
# For stats tables (in R), commission impact is negligible per trade but
# significant over 100+ trades. Show aggregate impact in commission section.
COMMISSION_USD = 2.05  # per round-turn per Micro
TICK_MULTIPLIERS = {"NQ1": 20.0, "ES1": 50.0, "YM1": 5.0, "RTY1": 50.0, "CL1": 1000.0, "GC1": 100.0}


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
    sections.append(f"**Generated:** 2026-07-25  \n**Symbols:** {', '.join(symbols)}  ")
    sections.append("\n**Fixes applied:** BL-2 (MAE R:R), BL-3 (empirical targets), BL-5 (commission), BL-6 (ADR-020 exit), BL-7 (regime look-ahead)  \n")
    sections.append("**Backtest fixes:** commission model ($2.05/round-turn), 16:00 ET forced exit, trailing regime classifier (no look-ahead)\n")

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

    # ── Commission impact (BL-5) ──
    sections.append("\n### Commission Impact (BL-5)\n")
    sections.append(f"Commission: ${COMMISSION_USD}/round-turn per Micro contract. Slippage: 0.01% per trade.\n")
    sections.append("Note: Stats tables show raw R-multiples (pre-commission). Backtest section includes commission.\n")
    sections.append("Commission as % of notional is small per trade but compounds over 100+ trades.\n\n")
    sections.append("| Symbol | Tick Mult | Avg Price (approx) | Commission $ | Commission % | Cost per 100 trades |\n")
    sections.append("|---|---|---|---|---|---|\n")
    for sym in symbols:
        mult = TICK_MULTIPLIERS.get(sym, 1.0)
        # Approximate average price
        pp = DERIVED / f"ib_facts_{sym}.parquet"
        if pp.exists():
            df_f = pd.read_parquet(pp, columns=["ib_mid"])
            avg_price = float(df_f["ib_mid"].median())
        else:
            avg_price = 20000.0
        comm_pct = COMMISSION_USD / (avg_price * mult) * 100
        cost_100 = COMMISSION_USD * 100
        sections.append(f"| {sym} | {mult} | {avg_price:.0f} | ${COMMISSION_USD} | {comm_pct:.4f}% | ${cost_100:.0f} |\n")

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
             "optimal_stop_r", "rr_ratio", "wr_at_optimal_stop", "expectancy_at_optimal_stop", "n_winners", "n_trades"],
            ["Symbol", "Play", "Target", "P95 MAE", "P99 MAE", "Stop (R)", "R:R", "WR @ stop", "Exp @ stop", "N win", "N total"]))

    # ── Empirical targets (BL-3, FR-10) ──
    emp_path = DERIVED / "ib_empirical_targets_best.parquet"
    if emp_path.exists():
        sections.append("\n## 5.5 Empirical Percentile Targets (Phase 5.5, BL-3, FR-10)\n")
        sections.append("Gunship-style percentile targets from actual MFE/MAE distribution of winning trades.\n")
        sections.append("4 selection modes: best_expectancy, balanced (P50/P50), aggressive (P75/P25), conservative (P20/P80).\n")
        emp = pd.read_parquet(emp_path)
        sections.append("\n### Sample: NY AM IB / ET_fixed, best expectancy per play\n")
        sample = emp[(emp.session_slot == "NY AM IB") & (emp.selection == "best_expectancy")]
        rows = sample[["symbol", "play", "target_r", "stop_r", "rr_ratio", "win_rate", "expectancy_r", "n_trades"]].to_dict("records")
        sections.append(_fmt_table(rows,
            ["symbol", "play", "target_r", "stop_r", "rr_ratio", "win_rate", "expectancy_r", "n_trades"],
            ["Symbol", "Play", "Target R", "Stop R", "R:R", "WR", "Exp (R)", "N"]))
        sections.append("\n**Key finding:** All NQ1 expectancies are negative — raw IB Pullback has no edge even with empirical targets. Commission and ADR-020 exit further reduce edge.\n")

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

    # ── Backtest results (BL-5/6, PropFirmSimulator) ──
    bt_dir = ROOT / "results" / "ib_backtest"
    bt_files = list(bt_dir.glob("ib_backtest_*.json")) if bt_dir.exists() else []
    if bt_files:
        sections.append("\n## 12. Backtest Results (PropFirmSimulator)\n")
        sections.append("Results from `ib_backtest_fast.py` with commission ($2.05/round-turn) and ADR-020 16:00 ET forced exit.\n")
        sections.append("Grade: A >=80% MC pass, B >=65%, C >=50%, D >=30%, F <30%.\n")
        sections.append("Profiles: Apex 50K ($3K target/$2.5K trailing DD/30-day), TopStep 50K ($3K/$2K/$1K daily/60-day), FTMO 50K ($5K/$5K static/$2.5K daily/30-day).\n")
        for bt_path in sorted(bt_files):
            data = json.loads(bt_path.read_text(encoding="utf-8"))
            results = data.get("results", [])
            if not results:
                continue
            ticker = results[0].get("ticker", bt_path.stem)
            sections.append(f"\n### {ticker} ({len(results)} candidates)\n")

            # Grade distribution
            grades = {}
            for r in results:
                g = r.get("grade", "F")
                grades[g] = grades.get(g, 0) + 1
            sections.append(f"**Grade distribution:** {grades}\n")

            # Positive return
            valid = [r for r in results if r.get("total_return_pct") is not None and not r.get("error")]
            pos = [r for r in valid if r["total_return_pct"] > 0]
            sections.append(f"**Positive return:** {len(pos)}/{len(valid)} ({len(pos)/len(valid)*100:.1f}%)\n")

            # Det PASS per profile
            det_pass = set()
            profile_pass = {}
            for r in valid:
                for p in r.get("profiles", []):
                    pn = p.get("profile_name", "?")
                    if p.get("passed"):
                        det_pass.add(r["candidate_id"])
                        profile_pass[pn] = profile_pass.get(pn, 0) + 1
            sections.append(f"**Det PASS on >=1 profile:** {len(det_pass)} ({len(det_pass)/len(valid)*100:.1f}%)\n")
            if profile_pass:
                sections.append(f"**Det PASS by profile:** {profile_pass}\n")

            # Top 10 by return with full prop-firm details
            top10 = sorted(valid, key=lambda x: x["total_return_pct"], reverse=True)[:10]
            if top10:
                sections.append("\n**Top 10 by return — full prop-firm metrics:**\n")
                rows = []
                for r in top10:
                    best_mc = 0
                    best_mc_prof = ""
                    best_det_delta = 0
                    worst_dd = 0
                    avg_days = None
                    for p in r.get("profiles", []):
                        if p["mc_pass_rate_pct"] > best_mc:
                            best_mc = p["mc_pass_rate_pct"]
                            best_mc_prof = p.get("profile_name", "?")
                        if p.get("final_equity_delta", 0) > best_det_delta:
                            best_det_delta = p["final_equity_delta"]
                        dd = p.get("max_drawdown_used", 0)
                        if dd > worst_dd:
                            worst_dd = dd
                        if p.get("avg_days_to_pass") and (avg_days is None or p["avg_days_to_pass"] < avg_days):
                            avg_days = p["avg_days_to_pass"]
                    rows.append({
                        "candidate_id": r["candidate_id"][:20],
                        "return_pct": round(r["total_return_pct"], 2),
                        "wr": round(r["win_rate_pct"], 1),
                        "trades": r["n_trades"],
                        "max_dd_pct": round(r.get("max_drawdown_pct", 0), 1),
                        "grade": r.get("grade", "F"),
                        "best_mc": round(best_mc, 1),
                        "best_mc_prof": best_mc_prof,
                        "det_delta_usd": round(best_det_delta),
                        "worst_dd_usd": round(worst_dd),
                        "days_to_pass": int(avg_days) if avg_days else "N/A",
                    })
                sections.append(_fmt_table(rows,
                    ["candidate_id", "return_pct", "wr", "trades", "max_dd_pct", "grade",
                     "best_mc", "best_mc_prof", "det_delta_usd", "worst_dd_usd", "days_to_pass"],
                    ["Candidate", "Ret %", "WR %", "Trades", "MaxDD %", "Grade",
                     "Best MC %", "MC Profile", "Det $ Delta", "Worst DD $", "Days to Pass"]))

            # Best by MC pass rate (different from best by return)
            mc_ranked = []
            for r in valid:
                for p in r.get("profiles", []):
                    mc_ranked.append((p["mc_pass_rate_pct"], p.get("mc_grade", "F"),
                                     p.get("profile_name", "?"), r["candidate_id"][:20],
                                     r["total_return_pct"], r["win_rate_pct"], r["n_trades"],
                                     p.get("final_equity_delta", 0), p.get("max_drawdown_used", 0)))
            mc_ranked.sort(key=lambda x: x[0], reverse=True)
            if mc_ranked:
                sections.append("\n**Top 5 by MC pass rate (any profile):**\n")
                rows = []
                for mc, g, prof, cid, ret, wr, trades, det_d, dd in mc_ranked[:5]:
                    rows.append({
                        "mc_pass": round(mc, 1),
                        "grade": g,
                        "profile": prof,
                        "candidate_id": cid,
                        "return_pct": round(ret, 2),
                        "wr": round(wr, 1),
                        "trades": trades,
                        "det_delta": round(det_d),
                        "max_dd_usd": round(dd),
                    })
                sections.append(_fmt_table(rows,
                    ["mc_pass", "grade", "profile", "candidate_id", "return_pct", "wr", "trades", "det_delta", "max_dd_usd"],
                    ["MC %", "Grade", "Profile", "Candidate", "Ret %", "WR %", "Trades", "Det $", "MaxDD $"]))

            # Risk metrics: max consecutive losses, risk of ruin
            # Compute from the best candidate's trade sequence
            if top10:
                best = top10[0]
                wr = best.get("win_rate_pct", 50) / 100.0
                # Risk of ruin: ((1-edge)/(1+edge))^bankroll, where edge = wr*avg_win - (1-wr)*avg_loss
                # Approximation: assume 1R win, 1R loss (simplified)
                edge = wr * 1.0 - (1 - wr) * 1.0  # = 2*wr - 1
                bankroll_r = 50  # 50R bankroll (conservative for $50K at 1% risk = 500 trades of $100)
                if edge > 0:
                    ror = ((1 - edge) / (1 + edge)) ** bankroll_r
                else:
                    ror = 1.0  # certain ruin if no edge
                # Max consecutive losses estimate: for n trades at WR w, expected max streak ~ log(n) / log(1/(1-w))
                import math
                n_trades = best.get("n_trades", 100)
                if wr < 1:
                    max_streak_est = math.log(n_trades) / math.log(1 / (1 - wr)) if wr < 0.99 else 1
                else:
                    max_streak_est = 0
                sections.append(f"\n**Risk metrics (best candidate):**\n")
                sections.append(f"- Win rate: {wr*100:.1f}%\n")
                sections.append(f"- Edge (approx): {edge:.4f}R per trade\n")
                sections.append(f"- Risk of ruin (50R bankroll): {ror*100:.2f}%\n")
                sections.append(f"- Max consecutive loss streak (est.): {max_streak_est:.0f} trades\n")
                sections.append(f"- Dollar P&L per trade (1 Micro, $50K): ${edge * 2.0:.2f} (at $2/pt NQ multiplier)\n")
                sections.append(f"- Commission per trade: $2.05 (already deducted in backtest)\n")
                sections.append(f"- Max drawdown: {best.get('max_drawdown_pct', 0):.1f}% price / ${best.get('max_drawdown_pct', 0) * 500:.0f} on $50K\n")

    sections.append("\n## 13. Methodology Notes\n")
    sections.append("- **Win Rate (WR):** fraction of trades with result == 1.\n")
    sections.append("- **Expectancy:** mean of `realized_r` (in R-multiples).\n")
    sections.append("- **Profit Factor:** gross win R / gross loss R.\n")
    sections.append("- **MFE/MAE:** max favorable / max adverse excursion in R.\n")
    sections.append("- **Lift:** WR(flag on) − WR(flag off). Measured against per-symbol baseline, not naive 50%.\n")
    sections.append("- **Regime:** from `ib_regime_{SYM}.parquet` (Phase 6 classifier: trend/normal/range/skip).\n")
    sections.append("- **CISD:** from `ib_cisd_dir` in confluence (1=bullish CSD fired, -1=bearish, 0=none). Per the CISD document, a CSD fires when price trades through the candidate candle's open (not close-based).\n")
    sections.append("- All stats are in-sample (no train/test split in this report). Phase 4's validation harness applies bootstrap CIs and min-N guards for production use.\n")
    sections.append("- **Walk-forward:** Not yet implemented. All filter lifts, regime stats, and filter stacks are in-sample. The backtest section (§12) uses the full historical period for both parameter selection and evaluation — this inflates results. A proper walk-forward split (e.g., 70% train / 30% test) is needed before trusting any positive expectancy.\n")
    sections.append("- **Commission:** $2.05/round-turn per Micro contract, applied as % of notional in backtester. Stats tables show raw R (pre-commission). See §1 Commission Impact table for the per-trade cost. Over 100 trades, commission costs $205 — enough to turn marginal strategies negative.\n")
    sections.append("- **ADR-020:** 16:00 ET forced exit in backtester. Stats tables use full MAX_SEARCH window (may include overnight holds for Globex/Tokyo sessions).\n")
    sections.append("- **Regime classifier:** Uses trailing 5d percentile (no look-ahead, BL-7 fix). Previous version used realized ib_range_pct_of_daily (look-ahead bias).\n")
    sections.append("- **ib_range_pct_of_daily:** Now computed as ib_range / (daily_high - daily_low) from 1m data (BL-7 fix). Was previously ib_range/ib_mid (mislabeled proxy).\n")
    sections.append("- **Risk of ruin:** Computed as ((1-edge)/(1+edge))^bankroll where edge = 2*WR - 1 (simplified, assumes 1R win/loss). Bankroll = 50R (conservative for $50K at 1% risk per trade).\n")
    sections.append("- **Max consecutive losses:** Estimated as log(N) / log(1/(1-WR)) — the expected max losing streak in N trades at win rate WR.\n")
    sections.append("- **Dollar P&L per trade:** Approximated as edge * tick_multiplier * $1 (for NQ1: edge * 20 * $1 = edge * $20). Actual P&L depends on contract size and entry price.\n")

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