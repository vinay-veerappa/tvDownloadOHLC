import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# Institutional Framework Imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.getcwd(), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scripts.trading_framework.data.loader import FrameworkLoader
from scripts.trading_framework.features.feature_registry import FeatureRegistry
from scripts.trading_framework.regime.regime_models import EnsembleRegimeModel
from scripts.trading_framework.strategies.logic.box_reversion import BoxMeanReversionSignal
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.ml.signal_classifier import SignalClassifier
from scripts.trading_framework.ml.walk_forward import PurgedKFold
from scripts.trading_framework.reporting.reporter import QuantReporter
from scripts.trading_framework.reporting.risk_profiler import RiskProfiler
from scripts.trading_framework.reporting.monte_carlo import MonteCarloSimulator

def run_v3_lifecycle(ticker="NQ1"):
    """
    The Ultimate Institutional Lifecycle (v3):
    L1: News Fusion -> L2: Feature Registry -> L3: Regime Ensemble -> 
    L4: Signal Generation -> L8: ML Filtering -> L5: Backtest -> L7: Risk Profiling
    """
    print(f"\n{'='*60}")
    print(f"🚀 STARTING INSTITUTIONAL V3 LIFECYCLE: {ticker}")
    print(f"{'='*60}\n")

    # --- 1. Data Ingestion (Layer 1 with ADR-007 News Fusion) ---
    loader = FrameworkLoader(ticker=ticker)
    df = loader.load(include_historical=True)
    
    # --- 2. Feature Engineering (Layer 2) ---
    registry = FeatureRegistry()
    df_featured = registry.compute_all(df)
    
    # --- 3. Regime Detection (Layer 3 Ensemble) ---
    print("📊 Computing Regime Ensemble (HMM + GMM + Threshold)...")
    regime_model = EnsembleRegimeModel()
    df_featured['regime'] = regime_model.predict_regime(df_featured)
    
    # --- 4. Split Data (Purged Walk-Forward Standard) ---
    # We use 2018-2022 for Training/Optimization, 2023-2025 for OOS
    is_mask = (df_featured.index.year >= 2018) & (df_featured.index.year <= 2022)
    oos_mask = (df_featured.index.year >= 2023)
    
    train_df = df_featured[is_mask].copy()
    test_df = df_featured[oos_mask].copy()
    
    print(f"IS Training Samples: {len(train_df)}")
    print(f"OOS Testing Samples: {len(test_df)}")

    # --- 5. ML Strategy Training (Layer 8) ---
    print("\n🧠 Training Signal Classifier (Layer 8)...")
    strategy = BoxMeanReversionSignal()
    # Generate labels for training (we need target/stop results)
    engine = VectorizedBacktester()
    
    # Initial mechanical signals across training set
    raw_train_signals = strategy.generate_signals(train_df, {'strategy_name': 'v3_base'})
    
    # Collect Labels (Success = 1, Fail = 0)
    labels_df = engine.collect_ml_labels(raw_train_signals, train_df)
    
    if not labels_df.empty:
        classifier = SignalClassifier(model_path=f"models/v3_{ticker}_classifier.joblib")
        # Features used for signal classification (exclude target, timing, price)
        feature_cols = [c for c in train_df.columns if c not in ['open', 'high', 'low', 'close', 'volume', 'returns', 'log_returns']]
        classifier.train(labels_df[feature_cols], labels_df['label'])
    else:
        print("⚠️ No labels collected in training set. Skipping ML filtering.")
        classifier = None

    # --- 6. Execution & Filtering (OOS Validation) ---
    print("\n🔬 Executing OOS Validation with ML Filtering...")
    oos_signals = strategy.generate_signals(test_df, {'strategy_name': 'v3_oos'})
    
    if classifier and not oos_signals.empty:
        # Convert Series signals to the Schema DataFrame format for classifier
        # SignalClassifier expects a signals DataFrame with 'signal_time'
        signals_df = pd.DataFrame({
            'signal_time': oos_signals[oos_signals != 0].index,
            'signal': oos_signals[oos_signals != 0].values
        })
        filtered_signals_df = classifier.filter_signals(signals_df, test_df)
        
        # Re-map filtered signals back to index
        final_oos_signals = pd.Series(0, index=test_df.index)
        final_oos_signals.loc[filtered_signals_df['signal_time']] = filtered_signals_df['signal']
    else:
        final_oos_signals = oos_signals

    # --- 7. Backtest Results (Layer 5) ---
    oos_metrics = engine.run(final_oos_signals, test_df, {'leverage': 1.0})
    
    # --- 8. Institutional Reporting (Layer 7 & 8) ---
    print("\n" + "="*50)
    print("📈 FINAL INSTITUTIONAL RISK REPORT")
    print("="*50)
    risk_profiler = RiskProfiler(account_size=50000.0, risk_per_trade=500.0) 
    risk_metrics = risk_profiler.calculate_metrics(oos_metrics['trade_returns_pct'], oos_metrics['max_drawdown_%'])
    
    for key, val in risk_metrics.items():
        print(f"{key.ljust(25)}: {val}")
        
    mc_sim = MonteCarloSimulator(iterations=10000)
    mc_results = mc_sim.simulate(oos_metrics['trade_returns_pct'])
    mc_sim.print_report(mc_results)
    
    # Tear sheet
    reporter = QuantReporter()
    oos_returns = oos_metrics['equity_curve'].pct_change().fillna(0)
    reporter.generate_tear_sheet(oos_returns, f"Institutional_v3_{ticker}_OOS")

    print(f"\n✅ Lifecycle v3 Complete for {ticker}.")
    print(f"📂 Report: scripts/trading_framework/reporting/outputs/Institutional_v3_{ticker}_OOS_tearsheet.html")

if __name__ == "__main__":
    run_v3_lifecycle()
