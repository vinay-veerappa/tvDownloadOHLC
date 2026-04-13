"""
Institutional Research Suite: Unified CLI Entry Point
"""
import os
import sys
import argparse
import re
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any

# Ensure project root is in path
PROJECT_ROOT = os.getcwd()
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scripts.trading_framework.config.config_loader import load_config
from scripts.libs.data.loader import DataLoader
from scripts.trading_framework.strategies.registry import get_strategy
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.core.mfe_mae import compute_mfe_mae
from scripts.trading_framework.reporting.tearsheet import generate_tearsheet
from scripts.trading_framework.reporting.mfe_mae_report import (
    generate_mfe_mae_summary,
    plot_mfe_mae_analysis,
)
from scripts.trading_framework.reporting.chop_filter_report import generate_chop_report
from scripts.trading_framework.ml.prop_eval_mc import run_prop_mc_simulation
from scripts.trading_framework.ml.optimizer import OptunaOptimizer
from scripts.trading_framework.ml.walk_forward import PurgedKFold
import optuna


def _extract_horizons(mfe_mae_df: pd.DataFrame, configured_horizons) -> list[int]:
    if configured_horizons:
        return list(configured_horizons)

    inferred = []
    for col in mfe_mae_df.columns:
        match = re.fullmatch(r"mfe_(\d+)", str(col))
        if match:
            inferred.append(int(match.group(1)))
    return sorted(set(inferred))


def compute_prop_eval_stats(trade_returns_pct: pd.Series, _mc_config=None) -> Dict[str, Any]:
    """Backward-compatible alias used by legacy tests/callers."""
    return run_prop_mc_simulation(trade_returns_pct)


def generate_mfe_mae_report(
    mfe_mae_df: pd.DataFrame,
    mfe_mae_config,
    ticker: str,
    output_dir: str = "scripts/trading_framework/reporting/outputs",
) -> None:
    """Backward-compatible report writer for MFE/MAE analysis."""
    if mfe_mae_df is None or mfe_mae_df.empty:
        return

    os.makedirs(output_dir, exist_ok=True)
    configured_horizons = getattr(mfe_mae_config, "forward_horizons_minutes", None)
    horizons = _extract_horizons(mfe_mae_df, configured_horizons)
    if not horizons:
        return

    summary = generate_mfe_mae_summary(mfe_mae_df, horizons)
    summary_path = os.path.join(output_dir, f"mfe_mae_summary_{ticker}.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    for horizon in horizons:
        if f"mfe_{horizon}" in mfe_mae_df.columns and f"mae_{horizon}" in mfe_mae_df.columns:
            plot_mfe_mae_analysis(mfe_mae_df, horizon, output_dir)


def _compute_mfe_mae_compat(signals: pd.DataFrame, df: pd.DataFrame, mfe_mae_config):
    """Support both legacy and current compute_mfe_mae call signatures."""
    try:
        return compute_mfe_mae(signals, df, mfe_mae_config)
    except TypeError:
        horizons = getattr(mfe_mae_config, "forward_horizons_minutes", [5, 15, 30, 60, 120])
        work_df = df.copy()

        if "signal" not in work_df.columns:
            work_df["signal"] = 0

        if isinstance(signals, pd.DataFrame) and {"signal_time", "direction"}.issubset(signals.columns):
            for _, row in signals.iterrows():
                ts = row.get("signal_time")
                if ts in work_df.index:
                    direction = str(row.get("direction", "")).lower()
                    work_df.at[ts, "signal"] = 1 if direction == "long" else -1 if direction == "short" else 0

        return compute_mfe_mae(work_df, "signal", horizons)


def run_optimization(args, config, df):
    """
    Runs a robust Optuna study with PurgedKFold cross-validation.
    """
    print(f"🔍 Starting Institutional Optimization for {args.ticker}...")
    print(f"📊 Method: PurgedKFold CV (k=3), TPE Sampler, Median Pruning")
    
    def objective(trial):
        # 1. Parameter Space (Defaulting to BoxReversion logic)
        params = {
            "min_dist": trial.suggest_float("min_dist", 0.0005, 0.0030, step=0.0005),
            "sl_dist": trial.suggest_float("sl_dist", 0.0030, 0.0100, step=0.0010),
            "tp_buffer": trial.suggest_float("tp_buffer", 0.0000, 0.0005, step=0.0001),
            "filter_high_vol": trial.suggest_categorical("filter_high_vol", [True, False])
        }
        
        # 2. Cross-Validation Loop
        pkf = PurgedKFold(n_splits=3, purge_window=100)
        fold_sharpes = []
        
        for fold_idx, (train_idx, test_idx) in enumerate(pkf.split(df)):
            fold_train = df.iloc[train_idx]
            fold_test = df.iloc[test_idx]
            
            strategy = get_strategy(args.strategy, args.ticker)
            signals = strategy.generate_signals(fold_train, params)
            
            engine = VectorizedBacktester()
            result = engine.run(signals, fold_test, {'leverage': 1.0})
            
            sharpe = result['sharpe_ratio']
            fold_sharpes.append(sharpe)
            
            # report to optuna for pruning
            trial.report(sharpe, fold_idx)
            if trial.should_prune():
                raise optuna.exceptions.TrialPruned()
                
        # Return the conservative mean Sharpe to avoid overfitting
        return np.mean(fold_sharpes) if fold_sharpes else 0.0
        
    study_name = f"opt_{args.ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    optimizer = OptunaOptimizer(study_name=study_name)
    study = optimizer.run_optimization(objective, n_trials=args.trials)
    
    print(f"🏆 Best IS Parameters: {study.best_params}")
    print(f"📈 Estimated CV Sharpe: {study.best_value:.2f}")
    return study.best_params

def run_research_pipeline(args):
    """
    Executes the 7-layer research pipeline.
    """
    print(f"🚀 Initializing Research Pipeline for {args.ticker} using {args.strategy}...")
    
    # 1. Load Config
    config = load_config(args.config)
    
    # 2. Data Loading & Enrichment
    print("📂 Loading data...")
    loader = DataLoader(config)
    df = loader.load_enriched(args.ticker)
    
    # 3. Strategy Discovery & Signal Generation
    best_params = {}
    if args.optimize:
        best_params = run_optimization(args, config, df)
    
    strategy = get_strategy(args.strategy, args.ticker)
    
    # 4. Final Parameter Run
    print("📡 Generating signals...")
    signals = strategy.generate_signals(df, best_params) 
    
    # 4. Vectorized Backtest
    print("📈 Running backtest engine...")
    engine = VectorizedBacktester()
    # Mocking result structure for now (matches engine.run output)
    result = engine.run(signals, df, {'leverage': 1.0})
    
    # 5. Advanced Research Analysis (MFE/MAE)
    print("🔬 Computing MFE/MAE excursions...")
    mfe_mae_signals = _compute_mfe_mae_compat(signals, df, config.mfe_mae)
    
    # 6. ML / Prop Evaluation
    print("🧪 Computing Prop Firm evaluation (Monte Carlo)...")
    pm_stats = compute_prop_eval_stats(result['trade_returns_pct'], config.optimization.monte_carlo)
    
    # 7. Reporting Suite
    print("📄 Generating institutional reports...")
    
    # Wrap result in the expected 'PortfolioResult' structure for tearsheet
    # Mapping engine output to what tearsheet.py expects
    class MockResult:
        def __init__(self, res, pm_stats, config):
            self.combined_equity_curve = res['equity_curve']
            self.combined_trades = res.get('trades_detailed', pd.DataFrame())
            self.prop_eval_passed = pm_stats['pass_rate'] > 0.8  # Threshold from config
            self.days_to_pass = None
            self.account_summary = {
                'starting_equity': config.account_risk.starting_equity,
                'risk_per_trade': config.session_risk.daily_max_loss / config.session_risk.max_trades_per_day, # Approximation
                'peak_equity': res['equity_curve'].max(),
                'current_balance': res['equity_curve'].iloc[-1],
                'current_drawdown': (res['equity_curve'].iloc[-1] / res['equity_curve'].max()) - 1,
                'max_trailing_drawdown': config.account_risk.trailing_drawdown
            }
            
    perf_result = MockResult(result, pm_stats, config)
    
    # Generate Tearsheet
    tearsheet = generate_tearsheet(perf_result)
    
    # Save Outputs
    output_dir = "scripts/trading_framework/reporting/outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    ts_path = f"{output_dir}/tearsheet_{args.ticker}_{args.strategy}.md"
    with open(ts_path, "w", encoding="utf-8") as f:
        f.write(tearsheet)
        
    # Generate Plots
    generate_mfe_mae_report(mfe_mae_signals, config.mfe_mae, args.ticker)
    # generate_chop_report(df, signals, args.ticker) # Needs specific internal data
    
    print(f"\n✅ Research Pipeline Complete!")
    print(f"📊 Tearsheet: {ts_path}")
    print(f"📈 Plots saved to: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Institutional Research Suite - Unified CLI")
    parser.add_argument("--ticker", type=str, default="NQ1", help="Ticker symbol (e.g., NQ1, ES1)")
    parser.add_argument("--strategy", type=str, default="box_reversion", help="Strategy key from registry")
    parser.add_argument("--config", type=str, default="scripts/trading_framework/config/sessions.yaml", help="Path to YAML config")
    parser.add_argument("--optimize", action="store_true", help="Run Optuna optimization study")
    parser.add_argument("--trials", type=int, default=20, help="Number of optimization trials")
    
    args = parser.parse_args()
    run_research_pipeline(args)
