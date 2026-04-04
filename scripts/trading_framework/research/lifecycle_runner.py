import os
import sys
import json
import asyncio
import pandas as pd
import numpy as np
import optuna
from datetime import datetime
from prisma import Prisma

# --- Failsafe Root Detection (ADR-017) ---
# 3 levels up from scripts/trading_framework/research/ -> root/
script_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(script_dir, "../../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.libs.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.strategies.logic.box_reversion import BoxMeanReversionSignal as BoxStrategy
from scripts.strategies.logic.ib_breakout_modular import IBBreakoutModular as IBStrategy
from scripts.trading_framework.ml.walk_forward import PurgedKFold
from scripts.trading_framework.reporting.risk_profiler import RiskProfiler

class ResearchLifecycleRunner:
    """
    Standardized institutional lifecycle for strategy research.
    Implements Layers 5, 6, and 7 of the framework.
    """
    def __init__(self, ticker="NQ1", strategy_key="box"):
        self.ticker = ticker
        self.strategy_key = strategy_key
        
        # Select Strategy Class
        if strategy_key == "ib":
            self.strategy = IBStrategy()
        else:
            self.strategy = BoxStrategy()
            
        self.strategy_name = self.strategy.strategy_name
        self.backtester = VectorizedBacktester()

    def _optimize_params(self, data, trials=10):
        """Standardized Layer 6 Optuna optimization."""
        def objective(trial):
            # Dynamic grid from strategy architecture (ADR-017)
            grid = self.strategy.get_param_grid()
            params = {}
            for k, v in grid.items():
                if isinstance(v[0], bool):
                    params[k] = trial.suggest_categorical(k, [True, False])
                elif isinstance(v[0], str):
                    params[k] = trial.suggest_categorical(k, v)
                elif isinstance(v[0], int):
                    params[k] = trial.suggest_int(k, min(v), max(v))
                else:
                    params[k] = trial.suggest_float(k, min(v), max(v))
            
            # --- Layer 6: Purged Cross-Validation ---
            pkf = PurgedKFold(n_splits=3, purge_window=100)
            fold_sharpes = []
            
            for fold_idx, (train_idx, test_idx) in enumerate(pkf.split(data)):
                fold_train = data.iloc[train_idx]
                fold_test = data.iloc[test_idx]
                
                signals = self.strategy.generate_signals(fold_train, params)
                if signals.empty:
                    fold_sharpes.append(-1.0)
                    continue
                    
                metrics = self.backtester.run(signals, fold_test, {'leverage': 1.0})
                fold_sharpes.append(metrics.get('sharpe_ratio', -1.0))
                
                trial.report(fold_sharpes[-1], fold_idx)
                if trial.should_prune():
                    raise optuna.exceptions.TrialPruned()
                    
            return np.mean(fold_sharpes) if fold_sharpes else -1.0

        study = optuna.create_study(
            study_name=f"{self.strategy_name}_{self.ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            storage="sqlite:///optuna_research.db",
            direction="maximize",
            load_if_exists=True
        )
        study.optimize(objective, n_trials=trials, n_jobs=4)
        return study.best_params

    async def _persist_to_hub(self, run_id, ticker, best_params, oos_metrics, run_dir):
        """Syncs high-fidelity research results to the Hub Database."""
        db = Prisma()
        await db.connect()
        try:
            # 1. Ensure Strategy Container Exists
            strategy_record = await db.researchstrategy.upsert(
                where={'name': self.strategy_name},
                data={
                    'create': {'name': self.strategy_name, 'description': "Modular Vectorized Strategy"},
                    'update': {}
                }
            )
            
            # 2. Serialize 1m Equity Curve (High Fidelity)
            equity_full = oos_metrics['equity_curve']
            equity_path = os.path.join(run_dir, "equity_1m.json")
            with open(equity_path, 'w') as f:
                json.dump({
                    'timestamps': [t.isoformat() for t in equity_full.index],
                    'values': [float(v) for v in equity_full.values]
                }, f)
            
            # 3. Create Research Run
            risk_profiler = RiskProfiler(account_size=50000.0, risk_per_trade=500.0)
            risk_metrics = risk_profiler.calculate_metrics(oos_metrics['trade_returns_pct'], oos_metrics['max_drawdown_%'])
            
            await db.researchrun.create(
                data={
                    'runId': run_id,
                    'ticker': ticker,
                    'strategyId': strategy_record.id,
                    'metricsJson': json.dumps({
                        'sharpe': float(oos_metrics.get('sharpe_ratio', 0)),
                        'drawdown': float(oos_metrics.get('max_drawdown_%', 0)),
                        'win_rate': float(oos_metrics.get('win_rate_%', 0)),
                        'total_trades': int(oos_metrics.get('total_trades', 0)),
                        'grading': risk_metrics.get('Institutional Grade', 'C')
                    }),
                    'configJson': json.dumps(best_params),
                    'equityCurvePath': equity_path,
                    'grade': risk_metrics.get('Institutional Grade', 'C'),
                    'filePath': run_dir
                }
            )
            print(f"✅ Research Hub Sync Complete for {run_id}")
        finally:
            await db.disconnect()

    def run_full_cycle(self, trials=10):
        print(f"🚀 Initializing Institutional Lifecycle for {self.ticker} [{self.strategy_name}]...")
        
        # 1. Load Data (Layer 1/2)
        loader = DataLoader(load_config())
        df = loader.load_enriched(self.ticker)
        
        # 2. In-Sample / Out-of-Sample Split (Layer 5)
        # IS: 2018-2023 | OOS: 2024-Present
        df_is = df[df.index.year <= 2023]
        df_oos = df[df.index.year >= 2024]
        
        # 3. Optimize (Layer 6)
        print(f"🔬 Running In-Sample Optimization ({trials} trials)...")
        best_params = self._optimize_params(df_is, trials=trials)
        print(f"🏆 Best Params: {best_params}")
        
        # 4. Validate (OOS)
        print(f"🔬 Running Out-of-Sample Validation...")
        oos_signals = self.strategy.generate_signals(df_oos, best_params)
        oos_metrics = self.backtester.run(oos_signals, df_oos, {'leverage': 1.0})
        
        # 5. Persist & Sync (Layer 7)
        RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results/RESEARCH")
        TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
        RUN_ID = f"RUN_{TIMESTAMP}_{self.ticker}_{self.strategy_key.upper()}"
        RUN_DIR = os.path.join(RESULTS_ROOT, self.strategy_name, self.ticker, RUN_ID)
        os.makedirs(RUN_DIR, exist_ok=True)
        
        asyncio.run(self._persist_to_hub(RUN_ID, self.ticker, best_params, oos_metrics, RUN_DIR))
        
        print(f"📊 OOS Sharpe: {oos_metrics.get('sharpe_ratio', 0):.2f}")
        print(f"✅ Lifecycle Test Complete. Artifacts in {RUN_DIR}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="NQ1")
    parser.add_argument("--strategy", default="box", choices=["box", "ib"])
    parser.add_argument("--trials", type=int, default=10)
    args = parser.parse_args()

    runner = ResearchLifecycleRunner(ticker=args.ticker, strategy_key=args.strategy)
    runner.run_full_cycle(trials=args.trials)
