# -*- coding: utf-8 -*-
"""
Optuna optimization of trade management parameters for a given strategy.

This takes the EXISTING signals from Phase 1 (already generated and saved
as MFE/MAE results) and searches for the optimal trade management policy 
and parameters.

ADR Alignment:
- ADR-002: Normalization
- ADR-009: Micro Multipliers
- ADR-011: Vectorized Research
- ADR-012: Traceability
"""

import os
import sys
import uuid
import json
import pickle
import logging
import argparse
import numpy as np
import pandas as pd
import optuna
import optuna.visualization.matplotlib as ovm
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# Framework Imports

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.trading_framework.config.config_loader import AppConfig, load_config
from scripts.trading_framework.core.mfe_mae import MfeMaeResult
from scripts.libs_py.data.loader import DataLoader
from scripts.libs_py.features.feature_registry import FeatureRegistry
from scripts.libs_py.risk.trade_policies import get_policy, TradePolicy
from scripts.trading_framework.reporting.reporter import QuantReporter
from scripts.trading_framework.reporting.risk_profiler import RiskProfiler
from scripts.trading_framework.reporting.optimization_summary import OptimizationReporter

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# SEARCH SPACE DEFINITION
# ═══════════════════════════════════════════════════════════════

def define_search_space(trial: optuna.Trial) -> dict:
    """Define the Optuna search space for trade management parameters."""
    params = {}

    # 1. Stop placement
    params["stop_atr_mult"] = trial.suggest_float("stop_atr_mult", 1.0, 6.0, step=0.25)

    # 2. Policy type
    params["policy_type"] = trial.suggest_categorical(
        "policy_type",
        ["cover_the_queen", "fixed_target", "scaled_exit", "breakeven_trail"]
    )

    # 3. Policy-specific parameters
    if params["policy_type"] == "cover_the_queen":
        params["partial_target_rr"] = trial.suggest_float("partial_target_rr", 0.5, 2.0, step=0.25)
        params["partial_exit_pct"] = trial.suggest_float("partial_exit_pct", 0.3, 0.7, step=0.1)
        params["trail_method"] = trial.suggest_categorical("trail_method", ["atr", "fixed"])
        if params["trail_method"] == "atr":
            params["trail_atr_mult"] = trial.suggest_float("trail_atr_mult", 1.0, 4.0, step=0.5)
        else:
            params["trail_atr_mult"] = 0.0

    elif params["policy_type"] == "fixed_target":
        params["target_rr"] = trial.suggest_float("target_rr", 0.5, 4.0, step=0.25)
        params["partial_target_rr"] = 0.0
        params["partial_exit_pct"] = 0.0
        params["trail_method"] = "none"
        params["trail_atr_mult"] = 0.0

    elif params["policy_type"] == "scaled_exit":
        params["exit1_rr"] = trial.suggest_float("exit1_rr", 0.5, 1.5, step=0.25)
        params["exit1_pct"] = trial.suggest_float("exit1_pct", 0.25, 0.5, step=0.05)
        params["exit2_rr"] = trial.suggest_float("exit2_rr", 1.5, 3.0, step=0.25)
        params["exit2_pct"] = trial.suggest_float("exit2_pct", 0.25, 0.5, step=0.05)
        params["trail_method"] = trial.suggest_categorical("trail_method_scaled", ["atr", "fixed"])
        if params["trail_method"] == "atr":
            params["trail_atr_mult"] = trial.suggest_float("trail_atr_mult_scaled", 1.0, 4.0, step=0.5)
        else:
            params["trail_atr_mult"] = 0.0
        params["partial_target_rr"] = params["exit1_rr"]
        params["partial_exit_pct"] = params["exit1_pct"]

    elif params["policy_type"] == "breakeven_trail":
        params["breakeven_trigger_rr"] = trial.suggest_float("breakeven_trigger_rr", 0.5, 2.0, step=0.25)
        params["trail_atr_mult"] = trial.suggest_float("trail_atr_mult_be", 1.0, 4.0, step=0.5)
        params["trail_method"] = "atr"
        params["partial_target_rr"] = 0.0
        params["partial_exit_pct"] = 0.0

    # 4. Time stop
    params["use_time_stop"] = trial.suggest_categorical("use_time_stop", [True, False])
    if params["use_time_stop"]:
        params["time_stop_bars"] = trial.suggest_int("time_stop_bars", 15, 90, step=5)
    else:
        params["time_stop_bars"] = 0

    return params

def define_search_space_from_dict(params_dict: dict) -> dict:
    """Helper to convert Optuna best_params back into full dict."""
    params = dict(params_dict)
    defaults = {
        "partial_target_rr": 0.0,
        "partial_exit_pct": 0.0,
        "trail_method": "none",
        "trail_atr_mult": 0.0,
        "target_rr": 2.0,
        "exit1_rr": 1.0,
        "exit1_pct": 0.33,
        "exit2_rr": 2.0,
        "exit2_pct": 0.33,
        "breakeven_trigger_rr": 1.0,
        "use_time_stop": False,
        "time_stop_bars": 0,
    }
    for key, default_val in defaults.items():
        if key not in params:
            params[key] = default_val

    if "trail_method_scaled" in params:
        params["trail_method"] = params.pop("trail_method_scaled")
    if "trail_atr_mult_scaled" in params:
        params["trail_atr_mult"] = params.pop("trail_atr_mult_scaled")
    if "trail_atr_mult_be" in params:
        params["trail_atr_mult"] = params.pop("trail_atr_mult_be")

    return params

# ═══════════════════════════════════════════════════════════════
# TRADE SIMULATOR
# ═══════════════════════════════════════════════════════════════

def simulate_trade_with_policy(
    mfe_result: MfeMaeResult,
    params: dict,
    tick_size: float = 0.25,
    point_value: float = 50.0,
    slippage_ticks: int = 1,
    commission_per_contract: float = 0.62,
) -> dict:
    """Simulate a single trade using the price path and policy rules."""
    path = mfe_result.path
    entry = mfe_result.entry_price
    direction = mfe_result.direction.lower()
    atr = mfe_result.atr_at_entry
    risk_points = params["stop_atr_mult"] * atr

    if risk_points <= 0 or len(path) == 0:
        return {"pnl_points": 0, "pnl_pct": 0, "pnl_dollars": 0,
                "exit_bar": 0, "exit_reason": "invalid", "partial_taken": False,
                "bars_in_trade": 0, "max_mfe": 0, "max_mae": 0, "timestamp": mfe_result.signal_time}

    if direction == "long":
        stop_price = entry - risk_points
    else:
        stop_price = entry + risk_points

    slip = tick_size * slippage_ticks
    fill_price = entry + slip if direction == "long" else entry - slip

    position_remaining = 1.0
    total_pnl_points = 0.0
    partial_taken = False
    trailing_stop = stop_price
    breakeven_moved = False
    exit1_taken = False
    exit2_taken = False

    exit_bar = len(path) - 1
    exit_reason = "end_of_path"
    
    observed_mfe = 0
    observed_mae = 0

    for bar_i, close_price in enumerate(path):
        curr_mfe = max(0, close_price - fill_price) if direction == "long" else max(0, fill_price - close_price)
        curr_mae = max(0, fill_price - close_price) if direction == "long" else max(0, close_price - fill_price)
        observed_mfe = max(observed_mfe, curr_mfe)
        observed_mae = max(observed_mae, curr_mae)

        if direction == "long" and close_price <= trailing_stop:
            exit_price = trailing_stop - slip
            total_pnl_points += (exit_price - fill_price) * position_remaining
            exit_bar, exit_reason, position_remaining = bar_i, "stop", 0
            break
        elif direction == "short" and close_price >= trailing_stop:
            exit_price = trailing_stop + slip
            total_pnl_points += (fill_price - exit_price) * position_remaining
            exit_bar, exit_reason, position_remaining = bar_i, "stop", 0
            break

        current_r = curr_mfe / risk_points if risk_points > 0 else 0

        if params["use_time_stop"] and bar_i >= params["time_stop_bars"]:
            exit_price = close_price - slip if direction == "long" else close_price + slip
            pnl = (exit_price - fill_price) if direction == "long" else (fill_price - exit_price)
            total_pnl_points += pnl * position_remaining
            exit_bar, exit_reason, position_remaining = bar_i, "time_stop", 0
            break

        policy = params["policy_type"]
        if policy == "cover_the_queen":
            if not partial_taken and current_r >= params["partial_target_rr"]:
                pct = params["partial_exit_pct"]
                exit_price = close_price - slip if direction == "long" else close_price + slip
                total_pnl_points += ((exit_price - fill_price) if direction == "long" else (fill_price - exit_price)) * pct
                position_remaining -= pct
                partial_taken = True
                trailing_stop = fill_price
            if partial_taken and params["trail_method"] == "atr":
                trail_dist = params["trail_atr_mult"] * atr
                trailing_stop = max(trailing_stop, close_price - trail_dist) if direction == "long" else min(trailing_stop, close_price + trail_dist)

        elif policy == "fixed_target":
            if current_r >= params["target_rr"]:
                exit_price = close_price - slip if direction == "long" else close_price + slip
                total_pnl_points += ((exit_price - fill_price) if direction == "long" else (fill_price - exit_price)) * position_remaining
                exit_bar, exit_reason, position_remaining = bar_i, "target", 0
                break

        elif policy == "scaled_exit":
            if not exit1_taken and current_r >= params["exit1_rr"]:
                pct = params["exit1_pct"]
                exit_price = close_price - slip if direction == "long" else close_price + slip
                total_pnl_points += ((exit_price - fill_price) if direction == "long" else (fill_price - exit_price)) * pct
                position_remaining -= pct
                exit1_taken, trailing_stop = True, fill_price
            if exit1_taken and not exit2_taken and current_r >= params["exit2_rr"]:
                pct = min(params["exit2_pct"], position_remaining)
                exit_price = close_price - slip if direction == "long" else close_price + slip
                total_pnl_points += ((exit_price - fill_price) if direction == "long" else (fill_price - exit_price)) * pct
                position_remaining -= pct
                exit2_taken = True
            if exit1_taken and params["trail_method"] == "atr":
                trail_dist = params["trail_atr_mult"] * atr
                trailing_stop = max(trailing_stop, close_price - trail_dist) if direction == "long" else min(trailing_stop, close_price + trail_dist)

        elif policy == "breakeven_trail":
            if not breakeven_moved and current_r >= params["breakeven_trigger_rr"]:
                trailing_stop, breakeven_moved = fill_price, True
            if breakeven_moved:
                trail_dist = params["trail_atr_mult"] * atr
                trailing_stop = max(trailing_stop, close_price - trail_dist) if direction == "long" else min(trailing_stop, close_price + trail_dist)

    if position_remaining > 0:
        close_price = path[-1]
        exit_price = close_price - slip if direction == "long" else close_price + slip
        total_pnl_points += ((exit_price - fill_price) if direction == "long" else (fill_price - exit_price)) * position_remaining

    return {
        "pnl_points": total_pnl_points,
        "pnl_pct": total_pnl_points / fill_price * 100 if fill_price > 0 else 0,
        "pnl_dollars": total_pnl_points * point_value - commission_per_contract,
        "exit_bar": exit_bar,
        "exit_reason": exit_reason,
        "partial_taken": partial_taken or exit1_taken,
        "bars_in_trade": exit_bar + 1,
        "max_mfe": observed_mfe,
        "max_mae": observed_mae,
        "timestamp": mfe_result.signal_time
    }

# ═══════════════════════════════════════════════════════════════
# BACKTEST WRAPPER
# ═══════════════════════════════════════════════════════════════

def run_backtest_with_params(
    mfe_results: list, 
    params: dict, 
    point_value: float = 50.0,
    signal_metadata: Optional[pd.DataFrame] = None
) -> dict:
    """Calculates aggregate metrics and detailed breakdowns."""
    trade_results = [simulate_trade_with_policy(r, params, point_value=point_value) for r in mfe_results]
    if not trade_results: return {"expectancy_per_trade": -999, "total_trades": 0}

    results_df = pd.DataFrame(trade_results)
    if signal_metadata is not None:
        results_df = results_df.join(signal_metadata.reset_index(drop=True), rsuffix='_meta')

    pnls = results_df["pnl_dollars"].values
    winners = results_df[results_df["pnl_dollars"] > 0]
    losers = results_df[results_df["pnl_dollars"] < 0]
    total_trades = len(pnls)
    
    total_pnl = np.sum(pnls)
    cum_pnl = np.cumsum(pnls)
    drawdown = cum_pnl - np.maximum.accumulate(cum_pnl)
    max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0
    years = total_trades / 250
    calmar = (total_pnl / max(years, 0.1)) / max(max_dd, 1) if max_dd > 0 else 0

    # MFE/MAE stats
    mfe_p25 = results_df["max_mfe"].quantile(0.25)
    mfe_p50 = results_df["max_mfe"].quantile(0.50)
    mfe_p75 = results_df["max_mfe"].quantile(0.75)
    
    mae_p25 = results_df["max_mae"].quantile(0.25)
    mae_p50 = results_df["max_mae"].quantile(0.50)
    mae_p75 = results_df["max_mae"].quantile(0.75)

    # Winner Heat
    winner_heat = winners["max_mae"].median() if not winners.empty else 0

    # Conditional Tables
    conditional_tables = {}
    group_cols = ["direction", "context_vix_regime", "context_session_block", "context_chop_regime"]
    for col in group_cols:
        if col in results_df.columns:
            grouped = results_df.groupby(col).agg(
                count=("pnl_dollars", "size"),
                expectancy=("pnl_dollars", "mean"),
                win_rate=("pnl_dollars", lambda x: (x > 0).mean()),
                mfe_median=("max_mfe", "median"),
                mae_median=("max_mae", "median")
            ).round(2).to_dict(orient="index")
            conditional_tables[col] = grouped

    return {
        "expectancy_per_trade": np.mean(pnls),
        "expectancy_pct": results_df["pnl_pct"].mean(),
        "total_pnl": total_pnl,
        "total_trades": total_trades,
        "win_rate": len(winners) / total_trades if total_trades > 0 else 0,
        "avg_winner": winners["pnl_dollars"].mean() if not winners.empty else 0,
        "avg_loser": losers["pnl_dollars"].mean() if not losers.empty else 0,
        "profit_factor": abs(winners["pnl_dollars"].sum() / losers["pnl_dollars"].sum()) if not losers.empty and losers["pnl_dollars"].sum() != 0 else 999,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "avg_bars_in_trade": results_df["bars_in_trade"].mean(),
        "partial_rate": results_df["partial_taken"].mean(),
        "exit_reasons": results_df["exit_reason"].value_counts().to_dict(),
        "mfe": {"p25": mfe_p25, "p50": mfe_p50, "p75": mfe_p75},
        "mae": {"p25": mae_p25, "p50": mae_p50, "p75": mae_p75},
        "winner_heat_mae": winner_heat,
        "conditional_metrics": conditional_tables,
        "raw_results": results_df # For reporting
    }

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Institutional Reporting Optimization Tool")
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--metric", default="expectancy_per_trade", 
                        choices=["expectancy_per_trade", "profit_factor", "calmar", "win_rate"])
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--embargo", type=int, default=5)
    parser.add_argument("--acc-size", type=float, default=100000.0)
    
    args = parser.parse_args()
    _ = load_config()
    
    pv = {"ES": 50.0, "NQ": 20.0, "MES": 5.0, "MNQ": 2.0}.get(args.symbol.upper(), 5.0)
    load_path = f"reports/{args.strategy}/{args.symbol}/raw/mfe_mae_results.pkl"
    if not os.path.exists(load_path):
        logger.error(f"Data missing: {load_path}")
        return

    with open(load_path, "rb") as f:
        data = pickle.load(f)
        results = data.get("approved_results", [])
        signals_df = data.get("approved_signals", None)
    
    if len(results) < 30:
        logger.error("Too few signals for optimization.")
        return

    test_size = len(results) // (args.folds + 1)
    folds = []
    for fold in range(args.folds):
        train_end = test_size * (fold + 1)
        test_start = train_end + args.embargo
        test_end = min(test_start + test_size, len(results))
        if test_start < len(results):
            folds.append((list(range(0, train_end)), list(range(test_start, test_end))))

    def objective(trial):
        params = define_search_space(trial)
        f_scores = []
        for i, (train_idx, test_idx) in enumerate(folds):
            test_signals = [results[idx] for idx in test_idx]
            metrics = run_backtest_with_params(test_signals, params, point_value=pv)
            f_scores.append(metrics.get(args.metric, -999))
            trial.report(np.mean(f_scores), step=i)
            if trial.should_prune(): raise optuna.TrialPruned()
        return np.mean(f_scores)

    study = optuna.create_study(
        direction="maximize", 
        pruner=optuna.pruners.MedianPruner(n_startup_trials=30, n_warmup_steps=2),
        study_name=f"{args.strategy}_{args.symbol}_trade_opt",
    )
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(objective, n_trials=args.trials, show_progress_bar=True)

    # evaluate Best Result
    best_params = define_search_space_from_dict(study.best_params)
    full_metrics = run_backtest_with_params(results, best_params, point_value=pv, signal_metadata=signals_df)
    results_df = full_metrics["raw_results"]
    
    # --- NEW: Calculate Institutional Risk Metrics ---
    risk_profiler = RiskProfiler(account_size=args.acc_size, risk_per_trade=args.acc_size * 0.01)
    raw_risk_metrics = risk_profiler.calculate_metrics(
        results_df["pnl_pct"] / 100, # RiskProfiler expects decimal returns
        results_df["pnl_dollars"].cumsum().min() / args.acc_size * 100, # Simple max DD estimation
        formatted=False
    )

    # ═══════════════════════════════════════════════════════════════
    # INSTITUTIONAL REPORTING (PNG + HTML)
    # ═══════════════════════════════════════════════════════════════
    run_id = f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{args.symbol}_{args.strategy}_FINAL"
    out_dir = Path(f"results/OPTIMIZATION/{run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    reporter = QuantReporter(output_dir="results/OPTIMIZATION", run_id=run_id)
    
    # 1. PnL Returns Series
    returns_df = results_df[["timestamp", "pnl_dollars"]].copy()
    returns_df["timestamp"] = pd.to_datetime(returns_df["timestamp"])
    returns_df = returns_df.set_index("timestamp").sort_index()
    # Normalize to daily returns for QuantStats
    daily_pnl = returns_df["pnl_dollars"].resample("D").sum()
    daily_returns = daily_pnl / args.acc_size
    
    # 2. Generate Visual Artifacts
    tearsheet_path = reporter.generate_tear_sheet(daily_returns, strategy_name=args.strategy)
    equity_curve_path = reporter.plot_equity_curve(daily_pnl.cumsum().fillna(0), strategy_name=args.strategy)
    
    # 3. Optuna Optimization History Plot
    try:
        plt.figure(figsize=(10, 6))
        ovm.plot_optimization_history(study)
        plt.tight_layout()
        opt_history_path = out_dir / "optimization_history.png"
        plt.savefig(opt_history_path)
        plt.close()
    except Exception as e:
        logger.warning(f"Failed to generate Optuna visualization: {e}")
        opt_history_path = "N/A"

    # Export Trials to CSV
    study.trials_dataframe().to_csv(out_dir / "all_trials.csv", index=False)

    # 4. Institutional Optimization Summary HTML
    logger.info("Generating Institutional Optimization Summary...")
    opt_reporter = OptimizationReporter(str(out_dir))
    summary_path = opt_reporter.generate_report(
        run_id=run_id,
        ticker=args.symbol,
        strategy_name=args.strategy,
        best_params=best_params,
        risk_metrics=raw_risk_metrics,
        trials_df=study.trials_dataframe()
    )

    report = {
        "symbol": args.symbol, "strategy": args.strategy, "best_params": best_params,
        "best_score": study.best_value, 
        "improvement": full_metrics[args.metric],
        "artifacts": {
            "tearsheet": str(tearsheet_path),
            "equity_curve": str(equity_curve_path),
            "opt_history": str(opt_history_path)
        }
    }
    
    with open(out_dir / "optimization_report.json", "w") as f: json.dump(report, f, indent=2, default=str)

    # Terminal Outputs
    print("\n" + "="*70)
    print(f"INSTITUTIONAL GRAPHICAL REPORTING: {args.symbol} / {args.strategy}")
    print("="*70)
    print(f"\nArticfacts Generated:")
    print(f"  - Tear Sheet:    {tearsheet_path}")
    print(f"  - Equity Curve:  {equity_curve_path}")
    print(f"  - Opt Progress:  {opt_history_path}")
    print(f"  - Summary HTML:  {summary_path}")
    print(f"\nFinal {args.metric}: {study.best_value:.4f}")
    print(f"Report saved to: {out_dir}")

if __name__ == "__main__":
    main()
