# `trading_framework` — package map

> **This file orients you inside the package. It is NOT the procedure.**
> The procedure — how to write a strategy, back-test it, validate it in NT8,
> compare the two, report on it, store it and promote it — is
> [`docs/architecture/STRATEGY_WORKFLOW.md`](../../docs/architecture/STRATEGY_WORKFLOW.md).
> Read that first and do not reconstruct a workflow from this file.
>
> **Rewritten 2026-09-04.** The previous version described a system that did not
> exist; every false claim it made is listed in the last section, because the
> shape of those errors is worth knowing.

## The one command

```powershell
.\.venv\Scripts\python.exe -m scripts.trading_framework.workflow `
    --strategy <registry_key> --ticker NQ1 --price-adjustment unadjusted `
    --optimize --trials 200 --oos-start 2025-01-01
```

`workflow.py` is the single sanctioned entry point. It runs every stage under one
run record and ends by printing the promotion checklist, each criterion PASS /
FAIL / **NOT EVALUATED**. Exit 0 = all passed, 1 = a criterion failed, 2 = a
required stage raised.

**Do not assemble a pipeline by hand.** 35 bespoke `run_*` scripts already exist
across this repo and are frozen; they are the reason results were not comparable
to each other.

## What is in here

| Path | Role |
|---|---|
| `workflow.py` | **the entry point.** Orders the stages, owns the run record, prints the checklist |
| `run_backtest.py` | the research pipeline `workflow.py` drives: load → split → gates → optimise → backtest → prop sim → reports |
| `core/backtest_engine.py` | `VectorizedBacktester` + `validate_signal_geometry` (refuses impossible stop/target geometry) |
| `core/nt8_parity_backtester.py` | the bracket/leg engine. **Use this for anything compared to NT8** |
| `core/execution.py`, `mfe_mae.py` | slippage/commission primitives, excursion maths |
| `provenance/run_record.py` | the run record + append-only ledger. A result is reportable only if attributable |
| `research/objective.py` | the **one** CV objective, the grid-liveness precheck and the causality probe |
| `research/lifecycle_runner.py`, `lifecycle_v3.py` | **legacy runners.** Not the sanctioned path. Do not extend |
| `ml/walk_forward.py` | `sequential_evaluation_folds` — equal windows, exit buffer reserved from the end |
| `ml/prop_firm_simulator.py` | **the only** prop-firm evaluator (ADR-021). `FIRM_PROFILES` lives here |
| `ml/optimizer.py` | `OptunaOptimizer` |
| `ml/leakage_guard.py` | NaN/feature-correlation audit. Not yet a workflow stage |
| `reporting/institutional_metrics.py` | **the one** implementation of The Edge System metrics |
| `reporting/tearsheet.py` | the markdown tearsheet (delegates its metrics) |
| `reporting/risk_profiler.py` | thin wrapper over the metrics module; adds `ror_pct` |
| `reporting/optimization_summary.py` | per-trial HTML report, emitted when `--optimize` ran |
| `reporting/mfe_mae_report.py` | excursion matrix + plots |
| `reporting/monte_carlo.py` | bootstrap drawdown distribution. **Unwired on purpose** — unseeded, and a second thing called "Monte Carlo" beside the prop simulator |
| `reporting/reporter.py` | `QuantReporter` (quantstats). Reachable only from the legacy runners |
| `strategies/registry.py` | `--strategy` resolves through `STRATEGY_FACTORY_REGISTRY` |
| `config/config_loader.py` | `load_config()`; `config/sessions.yaml` is the settings file |
| `library/adapters/` | adapters wrapping legacy evaluators (e.g. `NQStatsAdapter`) |
| `signals/signal_schema.py` | the canonical signal frame |
| `tests/` | run with `pytest scripts/trading_framework/tests -q` |

`research.db` / `research_optuna.db` are Optuna study storage and are **not
tracked**. Run artifacts go to `results/RESEARCH/_workflow/<TICKER>/<RUN_ID>/`,
never to a fixed path.

## Where the data comes from

The pipeline loads via `scripts/libs_py/data/loader.py::DataLoader.load_enriched`
(historical parquet + internals + session tags + 5m resample + VIX/VVIX). For
current/live analysis read `data/live/live_storage_-{ticker}.parquet` directly.
⚠️ Three classes are called `DataLoader` in this repo — **name the module**.

## Metrics

Defined in [`STRATEGY_WORKFLOW.md` §7.2](../../docs/architecture/STRATEGY_WORKFLOW.md)
and implemented once in `reporting/institutional_metrics.py`, which is tested against
the ten worked systems carried into `tests/test_institutional_metrics.py`. Two things worth
carrying:

- **Combined Edge is scale-free** (`EV_R × PF`). The dollar reading grades the
  account, not the strategy — the same edge scored D on $25k and A on $250k.
- **Risk of ruin is measured against the prop TRAILING DRAWDOWN**, not the
  account, and every report prints the basis beside the number. Measured against
  the account it had exactly two reachable values, `{0%, 100%}`.

## What the previous version of this file claimed, and why it was wrong

Kept because the failure modes recur, not as an apology.

| Claim | Reality |
|---|---|
| `FrameworkLoader` in `trading_framework/data/loader.py` | **neither the class nor the directory exists** |
| `config_loader.py` at the package root | it is in `config/` |
| "fully interactive HTML institutional Tear Sheets" | the tearsheet is **markdown** |
| outputs `Lifecycle_Test_IS_tearsheet.html` / `_OOS_tearsheet.html` | **no code anywhere produces those files** |
| run `lifecycle_runner.py` for a full test | it is legacy and is not the sanctioned path |
| Layers 2 & 3 splice macro catalysts from SQLite/Prisma and segment regimes | **no such code exists in the package** |
| "**Purged** Walk-Forward Cross-Validation to prevent data leakage" | `walk_forward_split` is marked `DEPRECATED -- expanding-window split with **NO purge and NO embargo**` |

The last one is the one to remember: **a document claiming a safety property the
code explicitly denies having.** It is worse than silence, because it stops the
reader checking. The same rule that governs
[`STRATEGY_WORKFLOW.md`](../../docs/architecture/STRATEGY_WORKFLOW.md) applies to
this file — never state that something is enforced without naming the enforcer in
the same edit, and never quote a number you did not just measure.
