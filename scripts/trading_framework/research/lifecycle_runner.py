import os
import sys
import pandas as pd
import numpy as np
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
import concurrent.futures
from datetime import datetime, timedelta

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.getcwd(), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scripts.trading_framework.data.loader import FrameworkLoader
from scripts.trading_framework.strategies.logic.box_reversion import BoxMeanReversionSignal
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.ml.optimizer import OptunaOptimizer
from scripts.trading_framework.reporting.reporter import QuantReporter
from scripts.trading_framework.reporting.risk_profiler import RiskProfiler
from scripts.trading_framework.reporting.monte_carlo import MonteCarloSimulator
from scripts.trading_framework.ml.walk_forward import PurgedKFold

def run_lifecycle_test(ticker="NQ1", is_start="2018-01-01", is_end="2023-12-31", oos_end="2025-12-31"):
    """
    Executes the full 7-layer lifecycle test:
    1. IN-SAMPLE (IS) Optimization (Layer 6)
    2. OUT-OF-SAMPLE (OOS) Validation (Layer 5)
    3. Performance Contrast (Layer 7)
    4. Audit Recording (research.db)
    """
    print(f"🚀 Initializing Lifecycle Test for {ticker}...")
    
    # --- Layer 1: Data Loading (Full Range) ---
    loader = FrameworkLoader(ticker=ticker)
    df = loader.load(include_historical=True)
    
    # --- Purged & Embargoed Split (80/20 Rule) ---
    # Convert boundary years to integers for robust filtering
    is_yr_start = int(is_start.split('-')[0])
    is_yr_end = int(is_end.split('-')[0])
    oos_yr_end = int(oos_end.split('-')[0])
    
    # Robust year-based filtering to bypass string/TZ slicing pitfalls
    df_is = df[(df.index.year >= is_yr_start) & (df.index.year <= is_yr_end)]
    # Embargo: Leave a 3-day gap between IS and OOS to prevent spillover
    df_oos_full = df[(df.index.year > is_yr_end) & (df.index.year <= oos_yr_end)]
    df_oos = df_oos_full.iloc[4320:] if len(df_oos_full) > 4320 else pd.DataFrame()
    
    print(f"IS Range: {df_is.index.min()} to {df_is.index.max()} ({len(df_is)} bars)")
    print(f"OOS Range: {df_oos.index.min()} to {df_oos.index.max()} ({len(df_oos)} bars)")

    # --- Layer 6: In-Sample Optimization (Optuna) ---
    def objective(trial):
        # Multi-parameter Hyperparameter Grid
        config = {
            'filter_high_vol': trial.suggest_categorical('filter_high_vol', [True, False]),
            'filter_trend_sequence': trial.suggest_categorical('filter_trend_sequence', [True, False]),
            'require_london_breakout': trial.suggest_categorical('require_london_breakout', [True, False]),
            
            # Minimum distance from Mid required to enter a trade (~5 to 30 bps)
            'min_dist': trial.suggest_float('min_dist', 0.0005, 0.0030, step=0.0005),
            
            # Take Profit Touch Buffer (~0 to 5 bps)
            'tp_buffer': trial.suggest_float('tp_buffer', 0.0000, 0.0005, step=0.0001),
            
            # Stop Loss Maximum Distance (~30 to 100 bps)
            'sl_dist': trial.suggest_float('sl_dist', 0.0030, 0.0100, step=0.0010),
            
            'strategy_name': 'BoxReversion_MultiOpt'
        }
        
        # --- Layer 6: Purged Cross-Validation Optimization ---
        # Instead of one Sharpe, we calculate the Average Sharpe across 5 Purged Folds
        pkf = PurgedKFold(n_splits=3, purge_window=100) # 3 splits for speed in test, 100 bar purge
        fold_sharpes = []
        
        for fold_idx, (train_idx, test_idx) in enumerate(pkf.split(df_is)):
            fold_train = df_is.iloc[train_idx]
            fold_test = df_is.iloc[test_idx]
            
            strategy = BoxMeanReversionSignal()
            signals = strategy.generate_signals(fold_train, config)
            
            engine = VectorizedBacktester()
            metrics = engine.run(signals, fold_test, {'leverage': 1.0})
            
            sharpe = metrics['sharpe_ratio']
            fold_sharpes.append(sharpe)
            
            # --- Layer 6: Early Pruning (Inter-fold) ---
            # Report the intermediate sharpe to Optuna
            trial.report(sharpe, fold_idx)
            
            # Prune if the trial is performing significantly worse than the median
            if trial.should_prune():
                raise optuna.exceptions.TrialPruned()
            
        # Return the conservative Mean Sharpe across folds to prevent overfitting
        return np.mean(fold_sharpes) if fold_sharpes else 0.0

    # Increase n_trials to 20 for the multi-parameter space
    optimizer = OptunaOptimizer(study_name=f"multi_opt_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    study = optimizer.run_optimization(objective, n_trials=20, n_jobs=4)
    
    # Check if we have trials
    if len(study.trials) == 0:
        print("❌ No successful trials. Aborting.")
        return

    best_params = study.best_params
    print(f"🏆 Best IS Parameters: {best_params}")
    print(f"📈 Best IS Sharpe: {study.best_value:.2f}")

    # --- Layer 5: Out-of-Sample Validation ---
    print("🔬 Running OOS Validation...")
    strategy = BoxMeanReversionSignal()
    best_config = {**best_params, 'strategy_name': 'BoxReversion_MultiOpt'}
    
    # IS Performance
    is_signals = strategy.generate_signals(df_is, best_config)
    is_engine = VectorizedBacktester()
    is_metrics = is_engine.run(is_signals, df_is, {'leverage': 1.0})
    
    # OOS Performance
    oos_signals = strategy.generate_signals(df_oos, best_config)
    oos_engine = VectorizedBacktester()
    oos_metrics = oos_engine.run(oos_signals, df_oos, {'leverage': 1.0})
    
    print(f"📊 OOS Sharpe: {oos_metrics['sharpe_ratio']:.2f} (vs IS {is_metrics['sharpe_ratio']:.2f})")
    print(f"📉 OOS Max Drawdown: {oos_metrics['max_drawdown_%']:.2f}%")

    # --- Layer 7: Institutional Reporting ---
    reporter = QuantReporter()
    
    # Generate Contrast Visualization
    is_returns = is_metrics['equity_curve'].pct_change().fillna(0)
    oos_returns = oos_metrics['equity_curve'].pct_change().fillna(0)
    
    reporter.generate_tear_sheet(is_returns, "Lifecycle_Test_IS")
    reporter.generate_tear_sheet(oos_returns, "Lifecycle_Test_OOS")
    
    # --- Layer 7: Prop Firm Risk Profiling (Out of Sample) ---
    print("\n" + "="*50)
    print("📈 PROP FIRM RISK PROFILER (OOS 50K ACCOUNT)")
    print("="*50)
    # Assumes a typical $50k prop firm eval with $500 risk constraint per trade 
    # to measure EV, PF, Sqn, RoR, and DRR accurately according to the document
    risk_profiler = RiskProfiler(account_size=50000.0, risk_per_trade=500.0) 
    oos_risk_metrics = risk_profiler.calculate_metrics(oos_metrics['trade_returns_pct'], oos_metrics['max_drawdown_%'])
    
    for key, val in oos_risk_metrics.items():
        print(f"{key.ljust(25)}: {val}")
    print("="*50)
    
    # --- Layer 8: Monte Carlo Simulation Strings ---
    mc_sim = MonteCarloSimulator(iterations=10000, account_size=50000.0, risk_per_trade=500.0)
    mc_metrics = mc_sim.simulate(oos_metrics['trade_returns_pct'])
    mc_sim.print_report(mc_metrics)
    
    # --- Layer 6 audit persistence ---
    summary_metrics = {
        'is_sharpe': is_metrics['sharpe_ratio'],
        'oos_sharpe': oos_metrics['sharpe_ratio'],
        'is_drawdown': is_metrics['max_drawdown_%'],
        'oos_drawdown': oos_metrics['max_drawdown_%'],
        'mc_drr_99': mc_metrics.get('DRR_99%', 'N/A')
    }
    run_id = optimizer.log_experiment(best_config, summary_metrics)
    
    print(f"✅ Lifecycle Test Complete. Audit recorded as RUN_ID: {run_id}")
    print(f"📂 Tear sheets saved to: scripts/trading_framework/reporting/outputs/")

if __name__ == "__main__":
    run_lifecycle_test()
