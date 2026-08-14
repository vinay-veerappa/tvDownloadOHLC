"""
Institutional VWAP Strategy Hyperparameter Optimization (Optuna).
===================================================================
Optimizes:
- Model Mode (retest vs sweep vs fade)
- ADX Trend Threshold (15 to 30)
- Volume Surge Multiplier (1.0 to 2.0x)
- Stop Loss Structural Multiplier (1.2 to 2.5x ATR)
- Target 1 / Target 2 R-multiples (0.8R to 3.5R)
- Initial Balance (IB) Directional Filter
- Max Trades / Day (1 vs 2)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parents[4])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import optuna
import pandas as pd
import numpy as np
from datetime import time
from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.strategies.vwap_reclaim.core.vwap_institutional import VWAPInstitutionalStrategy
from scripts.trading_framework.core.multi_contract_backtester import MultiContractBacktester

optuna.logging.set_verbosity(optuna.logging.WARNING)


def run_optimization(n_trials: int = 100, symbol: str = "NQ1"):
    print(f"\n================================================================================")
    print(f"       INSTITUTIONAL VWAP OPTUNA OPTIMIZATION — {symbol} ({n_trials} TRIALS)")
    print(f"================================================================================\n")

    config = load_config("scripts/trading_framework/config/sessions.yaml")
    loader = DataLoader(config)
    print(f"Loading {symbol} enriched dataset...")
    df = loader.load_enriched(symbol)
    print(f"Loaded {len(df):,} bars.\n")

    point_val = 2.0 if "NQ" in symbol else 5.0
    backtester = MultiContractBacktester(
        contracts=2,
        tp1_qty_pct=0.5,
        point_value=point_val,
        account_size=50000.0,
    )

    strat = VWAPInstitutionalStrategy(ticker=symbol)

    def objective(trial: optuna.Trial) -> float:
        model_mode = trial.suggest_categorical("model_mode", ["retest", "sweep_reclaim", "all"])
        min_retest_adx = trial.suggest_float("min_retest_adx", 16.0, 32.0, step=2.0)
        sl_atr_mult = trial.suggest_float("sl_atr_mult", 1.4, 2.6, step=0.2)
        tp1_r_mult = trial.suggest_float("tp1_r_mult", 0.8, 1.5, step=0.1)
        tp2_r_mult = trial.suggest_float("tp2_r_mult", 1.8, 4.0, step=0.2)
        max_trades_day = trial.suggest_int("max_trades_day", 1, 2)
        move_to_be = trial.suggest_categorical("move_to_be", [False, True])

        params = {
            "model_mode": model_mode,
            "min_retest_adx": min_retest_adx,
            "sl_atr_mult": sl_atr_mult,
            "tp1_r_mult": tp1_r_mult,
            "tp2_r_mult": tp2_r_mult,
            "max_trades_day": max_trades_day,
            "filter_lunch": True,
        }

        sigs = strat.hunt(df, params=params)
        if sigs.empty or len(sigs) < 100:
            return -999.0

        res = backtester.run(sigs, df, risk_params={"ticker": symbol, "move_to_be_on_tp1": move_to_be})
        pf = res["profit_factor"]
        win_rate = res["win_rate_%"]
        net_pnl = res["total_net_pnl_usd"]
        trades = res["num_trades"]

        # Objective: Maximize Profit Factor with penalty for low trade counts
        trial.set_user_attr("trades", trades)
        trial.set_user_attr("win_rate_%", win_rate)
        trial.set_user_attr("net_pnl_usd", net_pnl)
        trial.set_user_attr("profit_factor", pf)
        trial.set_user_attr("max_dd_usd", res["max_drawdown_usd"])
        trial.set_user_attr("sharpe", res["sharpe_ratio"])

        # Multi-metric score
        score = pf + (win_rate / 100.0) + (1.0 if net_pnl > 0 else -1.0)
        return score

    study = optuna.create_study(
        study_name=f"vwap_institutional_{symbol}",
        direction="maximize",
    )

    print("Starting optimization trials...")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    print("\n================================================================================")
    print("                           BEST TRIAL RESULTS")
    print("================================================================================")
    best = study.best_trial
    print(f"Trial #{best.number}")
    print(f"Score: {best.value:.4f}")
    print(f"Parameters: {best.params}")
    print(f"Metrics: Profit Factor = {best.user_attrs.get('profit_factor')}, "
          f"Win Rate = {best.user_attrs.get('win_rate_%')}%, "
          f"Trades = {best.user_attrs.get('trades')}, "
          f"Net PnL = ${best.user_attrs.get('net_pnl_usd'):,.2f}, "
          f"Max DD = ${best.user_attrs.get('max_dd_usd'):,.2f}, "
          f"Sharpe = {best.user_attrs.get('sharpe')}")
    print("================================================================================\n")

    # Export all trials to CSV
    trials_data = []
    for t in study.trials:
        if t.value is not None and t.value > -900:
            row = {"trial": t.number, "score": t.value, **t.params, **t.user_attrs}
            trials_data.append(row)
    
    if trials_data:
        df_trials = pd.DataFrame(trials_data).sort_values("score", ascending=False)
        out_path = Path(PROJECT_ROOT) / "reports" / "research" / f"vwap_optuna_{symbol.lower()}_trials.csv"
        df_trials.to_csv(out_path, index=False)
        print(f"Top 10 Parameter Sets saved to {out_path}:\n")
        print(df_trials.head(10).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--symbol", type=str, default="NQ1")
    args = parser.parse_args()
    run_optimization(args.trials, args.symbol)
