import os
import sys
import pandas as pd
import numpy as np
import optuna
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
        # Hyperparameters to tune
        config = {
            'filter_high_vol': trial.suggest_categorical('filter_high_vol', [True, False]),
            'strategy_name': 'BoxReversion_Lifecycle_Test'
        }
        
        strategy = BoxMeanReversionSignal()
        signals = strategy.generate_signals(df_is, config)
        
        engine = VectorizedBacktester()
        # Layer 5 engine uses .run(signals, data, risk_params)
        metrics = engine.run(signals, df_is, {'leverage': 1.0})
        
        # We optimize for Sharpe Ratio
        return metrics['sharpe_ratio']

    optimizer = OptunaOptimizer(study_name=f"lifecycle_{ticker}_{datetime.now().strftime('%Y%m%d')}")
    study = optimizer.run_optimization(objective, n_trials=2)
    
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
    best_config = {**best_params, 'strategy_name': 'BoxReversion_Lifecycle_Test'}
    
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
    
    # --- Layer 6 audit persistence ---
    summary_metrics = {
        'is_sharpe': is_metrics['sharpe_ratio'],
        'oos_sharpe': oos_metrics['sharpe_ratio'],
        'is_drawdown': is_metrics['max_drawdown_%'],
        'oos_drawdown': oos_metrics['max_drawdown_%']
    }
    run_id = optimizer.log_experiment(best_config, summary_metrics)
    
    print(f"✅ Lifecycle Test Complete. Audit recorded as RUN_ID: {run_id}")
    print(f"📂 Tear sheets saved to: scripts/trading_framework/reporting/outputs/")

if __name__ == "__main__":
    run_lifecycle_test()
