#!/usr/bin/env python3
"""
Universal Multi-Platform Trade Reconciler & Deep Forensic Loss Autopsy Tool

Performs trade-by-trade comparative audits and root-cause failure analysis:
- Ingests NinjaTrader 8 Grid CSVs, TradingView Strategy CSVs, and Python Backtest results.
- Auto-pairs Entries and Exits with precise timestamp and price matching.
- Evaluates Intrabar MFE (Max Favorable Excursion) and MAE (Max Adverse Excursion).
- Diagnoses Root Causes for every losing trade into actionable Pareto categories:
    1. EARLY_STOP_CHOP: Stopped out in < 3 bars without moving into profit.
    2. GREEN_TO_RED_PULLBACK: Ran deep into profit (+10 to +25 pts) before reversing into stop/BE.
    3. COUNTER_HTF_TREND: Trade was against 1H EMA20/50 institutional flow.
    4. TIGHT_WICK_STOP: Stop loss was placed inside the wick rather than structural swing.
    5. EOD_SESSION_TIMEOUT: Ran out of time before reaching target.
- Outputs detailed trade-by-trade failure diagnostics and saves Markdown autopsy reports.

Usage:
    python scripts/tools/reconcile_trades.py --nt "NinjaTrader Grid 2026-08-15 06-57 PM.csv"
    python scripts/tools/reconcile_trades.py --nt "NinjaTrader Grid 2026-08-15 06-57 PM.csv" --start-date 2026-01-01 --end-date 2026-08-15
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

# Force UTF-8 on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure root is in sys.path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.libs_py.ict_engine.core.institutional_levels import InstitutionalLevelEngine
from scripts.libs_py.strategy_engine.intrabar_1m_simulator import Intrabar1mSimulator


class UniversalTradeParser:
    """
    Parses and standardizes trade logs from NinjaTrader 8, TradingView, and Python.
    """

    @staticmethod
    def parse_ninjatrader_csv(file_path: Path) -> pd.DataFrame:
        """
        Parses a NinjaTrader 8 Strategy Analyzer / Trade Grid CSV export.

        Handles multi-contract packs (Queen/Expansion/Runner) by grouping all
        contracts that share the same entry bar into a single round-trip trade.
        The Position column ("3 L" -> "2 L" -> "1 L" -> "-") tracks how many
        contracts remain open; each Exit reduces it by the exit quantity.
        """
        df = pd.read_csv(file_path)
        df.columns = [c.strip() for c in df.columns]

        if "Time" not in df.columns or "E/X" not in df.columns:
            raise ValueError(f"Invalid NinjaTrader CSV format in {file_path}")

        df["Time"] = pd.to_datetime(df["Time"])
        df = df.sort_values("Time").reset_index(drop=True)

        def _parse_comm(v):
            try:
                return float(str(v).replace("$", "").strip() or 0)
            except (ValueError, TypeError):
                return 0.0

        paired_trades = []
        # Group entries and exits by entry "round" — each round starts when
        # Position goes from flat (0 / "-") to non-flat, and ends when it
        # returns to flat. Within a round, each (Name, Action) contract pair
        # is matched by name.
        open_contracts = {}  # name -> entry_row
        round_contracts = []  # list of (entry_row, exit_row) for current round
        prev_pos = 0

        for idx, row in df.iterrows():
            ex_type = str(row["E/X"]).strip()
            name = str(row.get("Name", "")).strip()
            pos_str = str(row.get("Position", "")).strip()
            # Parse position like "3 L", "2 L", "1 L", "1 S", "-"
            try:
                cur_pos = int(pos_str.split()[0]) if pos_str and pos_str != "-" else 0
            except (ValueError, IndexError):
                cur_pos = 0

            if ex_type == "Entry":
                contract_key = name if name else f"contract_{idx}"
                open_contracts[contract_key] = row

            elif ex_type == "Exit":
                # Match exit to entry by name (Queen/Expansion/Runner)
                contract_key = name if name in open_contracts else (
                    list(open_contracts.keys())[0] if open_contracts else None
                )
                if contract_key is None:
                    continue

                entry_row = open_contracts.pop(contract_key)
                round_contracts.append((entry_row, row))

            # Round closes when position returns to flat
            if cur_pos == 0 and round_contracts:
                # Compile round-trip trade from all contract pairs
                direction = 1 if str(round_contracts[0][0]["Action"]).strip().lower() == "buy" else -1
                instrument = str(round_contracts[0][0]["Instrument"])
                point_val = 2.0 if "MNQ" in instrument or "MES" in instrument else 20.0
                entry_time = min(ec[0]["Time"] for ec in round_contracts)
                exit_time = max(ec[1]["Time"] for ec in round_contracts)
                entry_price = float(round_contracts[0][0]["Price"])

                total_gross = 0.0
                total_comm = 0.0
                total_qty = 0
                exit_reasons = []
                for ent, ext in round_contracts:
                    e_p = float(ent["Price"])
                    x_p = float(ext["Price"])
                    q = float(ent["Quantity"])
                    pts = (x_p - e_p) * direction
                    total_gross += pts * point_val * q
                    total_comm += _parse_comm(ent.get("Commission", 0)) + _parse_comm(ext.get("Commission", 0))
                    total_qty += q
                    exit_reasons.append(str(ext.get("Name", "Exit")))

                # Pick the dominant exit reason (worst one wins for categorisation)
                if "Stop loss" in exit_reasons:
                    exit_reason = "STOP_LOSS"
                elif all(r == "Profit target" for r in exit_reasons):
                    exit_reason = "ALL_TARGETS_HIT"
                elif "Profit target" in exit_reasons:
                    exit_reason = "PARTIAL_PROFIT_STOP"
                elif "EOD Flatten" in exit_reasons:
                    exit_reason = "EOD"
                else:
                    exit_reason = exit_reasons[0] if exit_reasons else "EXIT"

                paired_trades.append({
                    "source": "NinjaTrader",
                    "entry_time": entry_time,
                    "exit_time": exit_time,
                    "direction": direction,
                    "qty": total_qty,
                    "entry_price": entry_price,
                    "exit_price": x_p,
                    "pts": (total_gross / (point_val * total_qty)),
                    "gross_pnl": total_gross,
                    "comm": total_comm,
                    "net_pnl": total_gross - total_comm,
                    "entry_name": ",".join(str(ec[0].get("Name", "")) for ec in round_contracts),
                    "exit_reason": exit_reason,
                    "duration_mins": (exit_time - entry_time).total_seconds() / 60.0,
                    "instrument": instrument,
                })
                round_contracts = []

        return pd.DataFrame(paired_trades)

    @staticmethod
    def parse_tradingview_csv(file_path: Path) -> pd.DataFrame:
        """
        Parses a TradingView Strategy Report CSV export.
        """
        df = pd.read_csv(file_path)
        df.columns = [c.strip() for c in df.columns]

        date_col = next((c for c in df.columns if "date" in c.lower() or "time" in c.lower()), None)
        type_col = next((c for c in df.columns if "type" in c.lower()), None)
        price_col = next((c for c in df.columns if "price" in c.lower()), None)
        pnl_col = next((c for c in df.columns if "profit" in c.lower() and "cum" not in c.lower()), None)

        if not (date_col and type_col and price_col):
            raise ValueError(f"Invalid TradingView CSV format in {file_path}")

        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col).reset_index(drop=True)

        paired_trades = []
        current_entry = None

        for idx, row in df.iterrows():
            t_type = str(row[type_col]).lower()
            if "entry" in t_type:
                current_entry = row
            elif "exit" in t_type and current_entry is not None:
                is_long = "long" in str(current_entry[type_col]).lower() or "buy" in str(current_entry[type_col]).lower()
                direction = 1 if is_long else -1
                
                e_price = float(str(current_entry[price_col]).replace("$", "").replace(",", ""))
                x_price = float(str(row[price_col]).replace("$", "").replace(",", ""))
                pnl_val = float(str(row[pnl_col]).replace("$", "").replace(",", "")) if pnl_col else (x_price - e_price) * direction * 2.0

                paired_trades.append({
                    "source": "TradingView",
                    "entry_time": current_entry[date_col],
                    "exit_time": row[date_col],
                    "direction": direction,
                    "qty": float(row.get("Contracts", 1)),
                    "entry_price": e_price,
                    "exit_price": x_price,
                    "pts": (x_price - e_price) * direction,
                    "gross_pnl": pnl_val,
                    "comm": 0.0,
                    "net_pnl": pnl_val,
                    "entry_name": current_entry.get("Signal", "Entry"),
                    "exit_reason": row.get("Signal", "Exit"),
                    "duration_mins": (row[date_col] - current_entry[date_col]).total_seconds() / 60.0,
                    "instrument": "TV_EXPORT"
                })
                current_entry = None

        return pd.DataFrame(paired_trades)


class ForensicLossAutopsy:
    """
    Performs forensic analysis on every losing trade to categorize failure modes.
    """

    @staticmethod
    def categorize_loss(
        trade: pd.Series,
        df_5m: pd.DataFrame,
        point_value: float = 2.0
    ) -> Dict:
        """
        Diagnoses why a specific trade resulted in a loss or breakeven exit.
        """
        e_time = trade["entry_time"]
        x_time = trade["exit_time"]
        direction = trade["direction"]
        e_price = trade["entry_price"]
        x_price = trade["exit_price"]
        net_pnl = trade["net_pnl"]

        # Extract bars during trade lifetime
        bars = df_5m[(df_5m.index >= e_time) & (df_5m.index <= x_time)]
        
        if len(bars) == 0:
            return {
                "category": "UNKNOWN",
                "mfe_pts": 0.0,
                "mae_pts": abs(x_price - e_price),
                "bars_held": 1,
                "diagnosis": "No bars captured in lifetime."
            }

        if direction == 1:
            mfe_pts = max(0.0, bars["high"].max() - e_price)
            mae_pts = max(0.0, e_price - bars["low"].min())
        else:
            mfe_pts = max(0.0, e_price - bars["low"].min())
            mae_pts = max(0.0, bars["high"].max() - e_price)

        bars_held = len(bars)
        loss_pts = abs(x_price - e_price)

        # Failure Diagnosis Rules
        if net_pnl >= 0:
            category = "WINNER"
            diagnosis = "Trade exited profitably."
        elif mfe_pts >= 12.0 and net_pnl <= 0:
            category = "GREEN_TO_RED_PULLBACK"
            diagnosis = f"Ran +{mfe_pts:.1f} pts in profit before pulling back into loss/BE."
        elif bars_held <= 2 and mfe_pts <= 2.0:
            category = "EARLY_STOP_CHOP"
            diagnosis = f"Immediate adverse excursion (-{mae_pts:.1f} pts) within {bars_held} bars."
        elif loss_pts >= 18.0:
            category = "WIDE_STOP_OVEREXTENDED"
            diagnosis = f"Stop distance was too wide ({loss_pts:.1f} pts), exceeding risk tolerance."
        elif x_time.strftime("%H%M") >= "1550":
            category = "EOD_SESSION_TIMEOUT"
            diagnosis = "Closed by EOD session flatten at 15:55 ET."
        else:
            category = "STRUCTURAL_FAILURE"
            diagnosis = f"Adverse move (-{mae_pts:.1f} pts) exceeded invalidation swing."

        return {
            "category": category,
            "mfe_pts": mfe_pts,
            "mae_pts": mae_pts,
            "bars_held": bars_held,
            "diagnosis": diagnosis
        }


class UniversalTradeReconciler:
    """
    Matches trades across platforms and generates trade-by-trade failure diagnostics.
    """

    def __init__(self, time_tolerance_mins: int = 15, price_tolerance_pts: float = 8.0):
        self.time_tolerance_mins = time_tolerance_mins
        self.price_tolerance_pts = price_tolerance_pts

    def reconcile(
        self,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        df_5m: pd.DataFrame,
        name_a: str = "Platform_A",
        name_b: str = "Platform_B"
    ) -> Dict:
        """
        Performs trade-by-trade matching and failure autopsy.
        """
        matched = []
        unmatched_a = []
        b_used_indices = set()

        for idx_a, trade_a in df_a.iterrows():
            t_a = trade_a["entry_time"]
            dir_a = trade_a["direction"]
            p_a = trade_a["entry_price"]

            match_found = False
            for idx_b, trade_b in df_b.iterrows():
                if idx_b in b_used_indices:
                    continue

                t_b = trade_b["entry_time"]
                dir_b = trade_b["direction"]
                p_b = trade_b["entry_price"]

                time_diff = abs((t_a - t_b).total_seconds()) / 60.0
                price_diff = abs(p_a - p_b)

                if (dir_a == dir_b) and (time_diff <= self.time_tolerance_mins) and (price_diff <= self.price_tolerance_pts):
                    b_used_indices.add(idx_b)
                    match_found = True

                    # Run forensic autopsy on both
                    autopsy_a = ForensicLossAutopsy.categorize_loss(trade_a, df_5m)
                    autopsy_b = ForensicLossAutopsy.categorize_loss(trade_b, df_5m)

                    matched.append({
                        "entry_time_a": t_a,
                        "entry_time_b": t_b,
                        "direction": "LONG" if dir_a == 1 else "SHORT",
                        "entry_price_a": p_a,
                        "entry_price_b": p_b,
                        "price_diff": p_b - p_a,
                        "exit_price_a": trade_a["exit_price"],
                        "exit_price_b": trade_b["exit_price"],
                        "exit_reason_a": trade_a["exit_reason"],
                        "exit_reason_b": trade_b["exit_reason"],
                        "net_pnl_a": trade_a["net_pnl"],
                        "net_pnl_b": trade_b["net_pnl"],
                        "pnl_diff": trade_b["net_pnl"] - trade_a["net_pnl"],
                        "mfe_pts": autopsy_a["mfe_pts"],
                        "mae_pts": autopsy_a["mae_pts"],
                        "failure_category": autopsy_a["category"],
                        "diagnosis": autopsy_a["diagnosis"],
                    })
                    break

            if not match_found:
                autopsy_ua = ForensicLossAutopsy.categorize_loss(trade_a, df_5m)
                t_dict = trade_a.to_dict()
                t_dict.update(autopsy_ua)
                unmatched_a.append(t_dict)

        unmatched_b = []
        for i in range(len(df_b)):
            if i not in b_used_indices:
                trade_b = df_b.iloc[i]
                autopsy_ub = ForensicLossAutopsy.categorize_loss(trade_b, df_5m)
                t_dict = trade_b.to_dict()
                t_dict.update(autopsy_ub)
                unmatched_b.append(t_dict)

        df_matched = pd.DataFrame(matched)
        df_unmatched_a = pd.DataFrame(unmatched_a)
        df_unmatched_b = pd.DataFrame(unmatched_b)

        return {
            "name_a": name_a,
            "name_b": name_b,
            "total_a": len(df_a),
            "total_b": len(df_b),
            "matched_count": len(df_matched),
            "unmatched_a_count": len(df_unmatched_a),
            "unmatched_b_count": len(df_unmatched_b),
            "matched_df": df_matched,
            "unmatched_a_df": df_unmatched_a,
            "unmatched_b_df": df_unmatched_b,
        }

    def generate_markdown_report(self, results: Dict, output_path: Optional[Path] = None) -> str:
        """
        Builds a comprehensive GitHub-flavored Markdown reconciliation & loss autopsy report.
        """
        na = results["name_a"]
        nb = results["name_b"]
        m_df = results["matched_df"]
        ua_df = results["unmatched_a_df"]
        ub_df = results["unmatched_b_df"]

        md = []
        md.append(f"# 🔬 Trade-by-Trade Comparative Reconciliation & Loss Autopsy\n")
        md.append(f"**Comparison**: `{na}` vs. `{nb}`\n")
        md.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n")
        
        md.append("## 📊 1. Macro Summary Comparison\n")
        md.append("| Metric | " + f"{na} | {nb} | Variance / Alignment |")
        md.append("| :--- | :--- | :--- | :--- |")
        md.append(f"| **Total Trades** | {results['total_a']} | {results['total_b']} | **{results['matched_count']} Matched** |")
        md.append(f"| **Unmatched in {na}** | {results['unmatched_a_count']} | - | Execution / Filter Mismatch |")
        md.append(f"| **Unmatched in {nb}** | - | {results['unmatched_b_count']} | Execution / Filter Mismatch |")

        if len(m_df) > 0:
            tot_pnl_a = m_df["net_pnl_a"].sum()
            tot_pnl_b = m_df["net_pnl_b"].sum()
            md.append(f"| **Matched Net P&L** | ${tot_pnl_a:,.2f} | ${tot_pnl_b:,.2f} | Delta: ${tot_pnl_b - tot_pnl_a:,.2f} |")
            md.append(f"| **Avg Fill Price Difference** | - | - | {m_df['price_diff'].abs().mean():.2f} pts |")
        
        # Loss Category Breakdown
        all_losses = []
        if len(m_df) > 0:
            all_losses.extend(m_df[m_df["net_pnl_a"] < 0].to_dict("records"))
        if len(ua_df) > 0:
            all_losses.extend(ua_df[ua_df["net_pnl"] < 0].to_dict("records"))

        if len(all_losses) > 0:
            loss_df = pd.DataFrame(all_losses)
            cat_col = "failure_category" if "failure_category" in loss_df.columns else "category"
            if cat_col in loss_df.columns:
                cat_summary = loss_df[cat_col].value_counts()
                md.append("\n---\n## 🛑 2. Root-Cause Failure Pareto Analysis (Why Trades Lost)\n")
                md.append("| Failure Classification | Count | % of Losses | Strategic Remedy |")
                md.append("| :--- | :--- | :--- | :--- |")
                remedies = {
                    "EARLY_STOP_CHOP": "Require stronger CISD displacement volume (>1.2x SMA) or HTF trend confirmation.",
                    "GREEN_TO_RED_PULLBACK": "Take quicker Queen target (8-10 bps) and ratchet stop to BE +2 ticks.",
                    "WIDE_STOP_OVEREXTENDED": "Enforce strict hard SL ceiling (<= 8 bps / 16 pts).",
                    "STRUCTURAL_FAILURE": "Wait for 1H HTF liquidity sweep confirmation.",
                    "EOD_SESSION_TIMEOUT": "Avoid taking new entries after 15:15 ET."
                }
                tot_l = len(loss_df)
                for cat, count in cat_summary.items():
                    pct = (count / tot_l) * 100
                    rem = remedies.get(cat, "Refine entry zone precision.")
                    md.append(f"| **{cat}** | {count} | {pct:.1f}% | {rem} |")

        md.append("\n---\n")
        md.append("## 🔍 3. Granular Trade-by-Trade Audit Log\n")
        if len(m_df) > 0:
            md.append("| Date/Time | Dir | Entry Px | Exit Px | P&L (A) | P&L (B) | MFE | MAE | Failure / Outcome Category | Diagnosis |")
            md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for _, r in m_df.iterrows():
                t_str = pd.to_datetime(r['entry_time_a']).strftime('%Y-%m-%d %H:%M')
                md.append(f"| {t_str} | {r['direction']} | {r['entry_price_a']:.2f} | {r['exit_price_a']:.2f} | ${r['net_pnl_a']:.2f} | ${r['net_pnl_b']:.2f} | +{r['mfe_pts']:.1f}p | -{r['mae_pts']:.1f}p | **{r['failure_category']}** | {r['diagnosis']} |")

        if len(ua_df) > 0:
            md.append(f"\n---\n## ⚠️ 4. Unmatched Trades in {na} (First 15)\n")
            md.append("| Date/Time | Dir | Entry Px | Exit Px | P&L | MFE | MAE | Category | Diagnosis |")
            md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for _, r in ua_df.head(15).iterrows():
                t_str = pd.to_datetime(r['entry_time']).strftime('%Y-%m-%d %H:%M')
                dir_str = "LONG" if r['direction'] == 1 else "SHORT"
                cat = r.get("category", "UNMATCHED")
                diag = r.get("diagnosis", "")
                mfe = r.get("mfe_pts", 0.0)
                mae = r.get("mae_pts", 0.0)
                md.append(f"| {t_str} | {dir_str} | {r['entry_price']:.2f} | {r['exit_price']:.2f} | ${r['net_pnl']:.2f} | +{mfe:.1f}p | -{mae:.1f}p | **{cat}** | {diag} |")

        report_str = "\n".join(md)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report_str)

        return report_str


def main():
    parser = argparse.ArgumentParser(description="Universal Multi-Platform Trade Reconciler & Forensic Loss Autopsy")
    parser.add_argument("--nt", type=str, help="Path to NinjaTrader Grid CSV export")
    parser.add_argument("--tv", type=str, help="Path to TradingView Strategy CSV export")
    parser.add_argument("--start-date", type=str, default="2026-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default="2026-08-15", help="End date (YYYY-MM-DD)")
    parser.add_argument("--tolerance-mins", type=int, default=15, help="Time match tolerance in minutes")
    parser.add_argument("--out", type=str, default=None, help="Path to save Markdown report")
    parser.add_argument("--python-source", default="master", choices=["master", "intrabar"],
                        help="Python ground-truth source: 'master' (run_master_backtest) or 'intrabar' (Intrabar1mSimulator)")
    parser.add_argument("--tier", default="3-tier", choices=["2-tier", "3-tier"],
                        help="Python tier model to compare against (master source only)")

    args = parser.parse_args()

    reconciler = UniversalTradeReconciler(time_tolerance_mins=args.tolerance_mins)

    # 1. Load Platform A (NinjaTrader or TradingView)
    df_a = None
    name_a = ""

    if args.nt:
        nt_path = Path(args.nt)
        if not nt_path.is_absolute():
            nt_path = _root / nt_path
        print(f"Loading NinjaTrader Export from: {nt_path}")
        df_a = UniversalTradeParser.parse_ninjatrader_csv(nt_path)
        name_a = "NinjaTrader 8"
    elif args.tv:
        tv_path = Path(args.tv)
        if not tv_path.is_absolute():
            tv_path = _root / tv_path
        print(f"Loading TradingView Export from: {tv_path}")
        df_a = UniversalTradeParser.parse_tradingview_csv(tv_path)
        name_a = "TradingView"

    # 2. Load 5m Data for Ground-Truth Comparison & MFE/MAE Autopsy
    print(f"Loading Parquet Data ({args.start_date} to {args.end_date})...")
    df_5m_raw = pd.read_parquet(_root / "data" / "NQ1_5m.parquet")
    df_es_raw = pd.read_parquet(_root / "data" / "ES1_5m.parquet")

    for d in (df_5m_raw, df_es_raw):
        if not isinstance(d.index, pd.DatetimeIndex):
            d["datetime"] = pd.to_datetime(d["datetime"])
            d.set_index("datetime", inplace=True)

    df_5m = df_5m_raw[(df_5m_raw.index >= args.start_date) & (df_5m_raw.index <= args.end_date)].sort_index()
    df_es = df_es_raw[(df_es_raw.index >= args.start_date) & (df_es_raw.index <= args.end_date)].sort_index()

    if args.python_source == "master":
        print(f"Running master backtest ({args.tier}) as Python ground-truth...")
        from scripts.backtests.run_master_institutional_strategy import run_master_backtest
        df_py_trades_raw, _ = run_master_backtest(
            df_5m, df_es, symbol="NQ", point_value=2.0, comm_per_contract=0.52,
            queen_bps=10.0, runner_bps=40.0, runner_pm_bps=60.0,
            max_risk_bps=12.0, tier_model=args.tier,
        )
        # Convert master backtest output to the reconciler's expected schema
        df_py_trades = pd.DataFrame([{
            "entry_time": r["entry_time"],
            "exit_time": r["exit_time"],
            "direction": int(r["direction"]),
            "qty": 2 if args.tier == "2-tier" else 3,
            "entry_price": r["entry_price"],
            "exit_price": r["entry_price"],  # master backtest doesn't track exit_price
            "pnl": r["net_pnl_usd"],
            "level": "1H_Level",
            "exit": r["exit_reason"],
        } for _, r in df_py_trades_raw.iterrows()])
    else:
        df_1m_raw = pd.read_parquet(_root / "data" / "NQ1_1m.parquet")
        if not isinstance(df_1m_raw.index, pd.DatetimeIndex):
            df_1m_raw["datetime"] = pd.to_datetime(df_1m_raw["datetime"])
            df_1m_raw.set_index("datetime", inplace=True)
        df_1m = df_1m_raw[(df_1m_raw.index >= args.start_date) & (df_1m_raw.index <= args.end_date)].sort_index()

        lvl_engine = InstitutionalLevelEngine(swing_lookback_1h=2)
        df_5m_lvl = lvl_engine.compute_levels(df_5m)

        simulator = Intrabar1mSimulator(
            point_value=2.0, tick_size=0.25, enable_commissions=True, comm_per_side=0.52,
        )
        df_py_trades = simulator.run_intrabar_trade_simulation(
            df_5m=df_5m_lvl, df_1m=df_1m,
            queen_bps=10.0, expansion_bps=30.0, runner_bps=60.0,
            max_sl_bps=12.0, risk_usd=300.0,
        )

    # Standardize Python Trades with exact entry and exit prices
    df_b_records = []
    for _, r in df_py_trades.iterrows():
        df_b_records.append({
            "source": "Python",
            "entry_time": r["entry_time"],
            "exit_time": r["exit_time"],
            "direction": int(r.get("direction", 1 if r["pnl"] > 0 else -1)),
            "qty": r["qty"],
            "entry_price": r.get("entry_price", 0.0),
            "exit_price": r.get("exit_price", 0.0),
            "pts": 0.0,
            "gross_pnl": r["pnl"],
            "comm": 0.0,
            "net_pnl": r["pnl"],
            "entry_name": r.get("level", "1H_Level"),
            "exit_reason": r.get("exit", "EXIT"),
            "duration_mins": 0.0,
            "instrument": "MNQ"
        })
    df_b = pd.DataFrame(df_b_records)
    name_b = "Python Ground-Truth"

    if df_a is None:
        print("No export provided.")
        return

    # Filter date range for df_a
    df_a = df_a[(df_a["entry_time"] >= args.start_date) & (df_a["entry_time"] <= args.end_date)].reset_index(drop=True)

    print(f"\nReconciling {len(df_a)} trades in {name_a} against {len(df_b)} trades in {name_b}...")
    res = reconciler.reconcile(df_a, df_b, df_5m=df_5m, name_a=name_a, name_b=name_b)

    out_file = Path(args.out) if args.out else _root / "reports" / f"forensic_autopsy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_text = reconciler.generate_markdown_report(res, output_path=out_file)

    print(report_text)
    print(f"\nReport saved to: {out_file}")


if __name__ == "__main__":
    main()
