import optuna
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, Any, Callable, List
from datetime import datetime
import uuid

class OptunaOptimizer:
    """
    Hyper-parameter Optimization & Experiment Tracker.
    Layer 6: Optuna integration with persistent SQLite recording.
    """
    
    def __init__(self, study_name: str, db_path: str = "scripts/trading_framework/research.db"):
        self.study_name = study_name
        self.db_path = db_path
        # Study storage is also handled by optuna sqlite storage for robustness
        self.storage = f"sqlite:///{db_path.replace('.db', '_optuna.db')}"
        
    def run_optimization(self, objective: Callable, n_trials: int = 100, n_jobs: int = 1) -> optuna.study.Study:
        """
        Run the optimization study with pruning and parallelization support.
        """
        study = optuna.create_study(
            study_name=self.study_name,
            direction="maximize",
            storage=optuna.storages.RDBStorage(
                url=self.storage,
                engine_kwargs={"connect_args": {"timeout": 30}}  # Handle SQLite contention in parallel
            ),
            load_if_exists=True,
            pruner=optuna.pruners.MedianPruner(
                n_startup_trials=5, 
                n_warmup_steps=1, 
                interval_steps=1
            )
        )
        study.optimize(objective, n_trials=n_trials, n_jobs=n_jobs)
        return study

    def log_experiment(self, config: Dict[str, Any], metrics: Dict[str, Any], regime: str = "None"):
        """
        Record the best result into the primary framework research audit trail.
        """
        run_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        
        # Mapping metrics to our experiments table
        data = (
            run_id,
            datetime.now().isoformat(),
            config.get('git_hash', 'None'),
            config.get('config_hash', 'None'),
            regime,
            config.get('strategy_name', 'DefaultStrategy'),
            metrics.get('is_sharpe', 0.0),
            metrics.get('oos_sharpe', 0.0),
            metrics.get('is_drawdown', 0.0),
            metrics.get('oos_drawdown', 0.0),
            f"reporting/outputs/{run_id}/"
        )
        
        query = """INSERT INTO experiments 
                   (run_id, timestamp, git_hash, config_hash, regime_model, strategy_name, is_sharpe, oos_sharpe, is_drawdown, oos_drawdown, artifacts_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        
        conn.execute(query, data)
        conn.commit()
        conn.close()
        return run_id
