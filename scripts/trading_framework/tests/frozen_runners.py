"""FROZEN INVENTORY of modules that drive a backtest engine outside the one
sanctioned entry point. Enforced by `test_no_new_runners.py`.

A module is on this list because it (a) names a backtest engine or the research
pipeline AND (b) is executable. That is a BEHAVIOURAL test, not a filename test:
only 6 of these 32 are called `run_*.py`, so freezing the filename would have
frozen 6 and missed 26.

DO NOT ADD A LINE HERE to make the gate pass. The gate exists to stop the
population growing. Use the entry point:

    python -m scripts.trading_framework.workflow --strategy <key>         --ticker <T> --price-adjustment <basis>

See docs/architecture/STRATEGY_WORKFLOW.md section 4.1.

Deleting one of these scripts IS good news -- remove its line in the same
commit; `test_the_inventory_has_no_stale_entries` requires it.

THIS IS A .py AND NOT A .txt ON PURPOSE. It was written as `frozen_runners.txt`
and `.gitignore` line 69 is a blanket `*.txt`, so the commit silently dropped
it and the gate would have failed on any fresh clone -- a gate whose data is
untracked is not a gate. Same hazard as line 46's blanket `*.csv`, which is
still hiding the NT8 ground-truth capture.
"""

FROZEN = frozenset({
    "scripts/analysis/bb_e16_e21_queue.py",
    "scripts/analysis/bb_e26_e28_queue.py",
    "scripts/analysis/bb_e32_falsification.py",
    "scripts/analysis/bb_e33_e31_final.py",
    "scripts/analysis/bb_grid_optim.py",
    "scripts/analysis/bb_sweep_optim.py",
    "scripts/analysis/comprehensive_experiments.py",
    "scripts/analysis/mm_e34_battery.py",
    "scripts/analysis/price_action_characteristics.py",
    "scripts/analysis/range_strategy_comparison.py",
    "scripts/analysis/strategy_statistical_eval.py",
    "scripts/analysis/supertrend_daily.py",
    "scripts/analysis/supertrend_experiments.py",
    "scripts/analysis/vwap_acceptance.py",
    "scripts/analysis/vwap_acceptance_optim.py",
    "scripts/analysis/vwap_experiments.py",
    "scripts/analysis/vwap_fade.py",
    "scripts/knowledge_bridge/ib_backtest_fast.py",
    "scripts/knowledge_bridge/ib_backtest_runner.py",
    "scripts/research/ablation_cisd_filters_and_sessions.py",
    "scripts/research/measure_cv_objective_defect.py",
    "scripts/research/measure_risk_limit_contribution.py",
    "scripts/research/validate_apples_to_apples.py",
    "scripts/research/verify_mtf_framework.py",
    "scripts/strategies/ict/runners/run_fvg_cisd_sweep.py",
    "scripts/strategies/ict/runners/run_fvg_cisd_sweep_parallel.py",
    "scripts/strategies/initial_balance/analysis/evaluate_pullback_mechanisms.py",
    "scripts/strategies/initial_balance/core/run_ib_backtest.py",
    "scripts/strategies/initial_balance/core/run_pullback_backtest.py",
    "scripts/strategies/nine_thirty_breakout/core/run_930_v2_strategy.py",
    "scripts/trading_framework/research/lifecycle_runner.py",
    "scripts/trading_framework/research/lifecycle_v3.py",
})
