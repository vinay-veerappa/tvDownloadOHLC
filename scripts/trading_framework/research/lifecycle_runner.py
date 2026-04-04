import os
import sys
import json
import asyncio
from pathlib import Path
import pandas as pd
import numpy as np
import optuna
from datetime import datetime

# --- Failsafe Root Detection (ADR-017) ---
# 3 levels up from scripts/trading_framework/research/ -> root/
script_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(script_dir, "../../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.libs.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.strategies.registry import get_strategy
from scripts.trading_framework.ml.walk_forward import PurgedKFold
from scripts.trading_framework.reporting.risk_profiler import RiskProfiler

class ResearchLifecycleRunner:
    """
    Standardized institutional lifecycle for strategy research.
    Implements Layers 5, 6, and 7 of the framework.
    """
    def __init__(self, ticker="NQ1", strategy_key="box_reversion"):
        self.ticker = ticker
        self.strategy_key = strategy_key
        self.strategy = get_strategy(strategy_key, ticker)
            
        self.strategy_name = self.strategy.strategy_name
        self.backtester = VectorizedBacktester()

    @staticmethod
    def _suggest_from_grid(trial, key, spec):
        # Supports ADR-017 tuple specs like ('int', 10, 50) and list/categorical specs.
        if isinstance(spec, tuple) and len(spec) >= 2 and isinstance(spec[0], str):
            kind = spec[0]
            if kind == 'int':
                if len(spec) < 3:
                    raise ValueError(f"int spec for '{key}' must be ('int', low, high)")
                return trial.suggest_int(key, int(spec[1]), int(spec[2]))
            if kind == 'float':
                if len(spec) < 3:
                    raise ValueError(f"float spec for '{key}' must be ('float', low, high)")
                return trial.suggest_float(key, float(spec[1]), float(spec[2]))
            if kind == 'categorical':
                choices = spec[1]
                if not isinstance(choices, (list, tuple)):
                    raise ValueError(f"categorical spec for '{key}' must provide list/tuple choices")
                return trial.suggest_categorical(key, list(choices))

        if isinstance(spec, (list, tuple)) and len(spec) > 0:
            if all(isinstance(x, bool) for x in spec):
                return trial.suggest_categorical(key, list(spec))
            if all(isinstance(x, int) and not isinstance(x, bool) for x in spec):
                return trial.suggest_int(key, min(spec), max(spec))
            if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in spec):
                return trial.suggest_float(key, float(min(spec)), float(max(spec)))
            return trial.suggest_categorical(key, list(spec))

        raise ValueError(f"Unsupported param grid spec for '{key}': {spec}")

    def _optimize_params(self, data, trials=10):
        """Standardized Layer 6 Optuna optimization."""
        def objective(trial):
            # Dynamic grid from strategy architecture (ADR-017)
            grid = self.strategy.get_param_grid()
            params = {}
            for k, v in grid.items():
                params[k] = self._suggest_from_grid(trial, k, v)
            
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
        # --- Prisma Environment Setup (ADR-017) ---
        if 'DATABASE_URL' not in os.environ:
            # Standard location for the Hub Database (SQLite)
            db_path = os.path.join(PROJECT_ROOT, "web/prisma/dev.db")
            os.environ['DATABASE_URL'] = f"file:{db_path}"
            
        from prisma import Prisma

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

            base_metrics = {
                'sharpe': float(oos_metrics.get('sharpe_ratio', 0)),
                'drawdown': float(oos_metrics.get('max_drawdown_%', 0)),
                'win_rate': float(oos_metrics.get('win_rate_%', 0)),
                'total_trades': int(oos_metrics.get('total_trades', 0)),
                'grading': risk_metrics.get('Institutional Grade', 'C')
            }

            base_payload = {
                'runId': run_id,
                'ticker': ticker,
                'metricsJson': json.dumps(base_metrics),
                'configJson': json.dumps(best_params),
                'grade': risk_metrics.get('Institutional Grade', 'C'),
                'filePath': run_dir,
            }

            create_variants = [
                {
                    **base_payload,
                    'strategyId': strategy_record.id,
                    'equityCurvePath': equity_path,
                },
                {
                    **base_payload,
                    'strategy': {'connect': {'id': strategy_record.id}},
                    'equityCurvePath': equity_path,
                },
                {
                    **base_payload,
                    'strategy': {'connect': {'id': strategy_record.id}},
                    # Compatibility fallback for older/generated Prisma clients
                    # that reject equityCurvePath in create input.
                    'thumbnailJson': equity_path,
                },
                {
                    **base_payload,
                    'strategy': {'connect': {'id': strategy_record.id}},
                },
            ]

            last_error = None
            for payload in create_variants:
                try:
                    await db.researchrun.create(data=payload)
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc

            if last_error is not None:
                raise last_error

            print(f"✅ Research Hub Sync Complete for {run_id}")
        finally:
            await db.disconnect()

    @staticmethod
    def _can_persist_to_hub() -> tuple[bool, str]:
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            db_file = Path(PROJECT_ROOT) / 'web' / 'prisma' / 'dev.db'
            db_file.parent.mkdir(parents=True, exist_ok=True)
            os.environ['DATABASE_URL'] = f"file:{db_file.as_posix()}"
            return True, f"DATABASE_URL not set; defaulted to {os.environ['DATABASE_URL']}"
        return True, "ok"

    def run_full_cycle(self, trials=10, persist_to_hub=True):
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
        
        if persist_to_hub:
            can_persist, reason = self._can_persist_to_hub()
            if not can_persist:
                print(f"⚠️ Skipping hub persistence: {reason}.")
                print("ℹ️ Set DATABASE_URL (and ensure Prisma client is generated) to enable persistence.")
            else:
                if reason != 'ok':
                    print(f"ℹ️ {reason}")
                try:
                    asyncio.run(self._persist_to_hub(RUN_ID, self.ticker, best_params, oos_metrics, RUN_DIR))
                except Exception as exc:
                    print(f"⚠️ Hub persistence failed: {exc}")
                    print("ℹ️ Continuing without persistence. Use --skip-persist to silence this path.")
        else:
            print("ℹ️ Skipping hub persistence (--skip-persist enabled).")
        
        print(f"📊 OOS Sharpe: {oos_metrics.get('sharpe_ratio', 0):.2f}")
        print(f"✅ Lifecycle Test Complete. Artifacts in {RUN_DIR}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="NQ1")
    parser.add_argument(
        "--strategy",
        default="box_reversion",
        choices=[
            "ib_pullback",
            "box_reversion",
            "mean_reversion",
            "ema_pullback",
            "vwap_reclaim",
            "failed_auction",
            "six_am_reversal",
        ],
    )
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--skip-persist", action="store_true")
    args = parser.parse_args()

    runner = ResearchLifecycleRunner(ticker=args.ticker, strategy_key=args.strategy)
    runner.run_full_cycle(trials=args.trials, persist_to_hub=not args.skip_persist)
