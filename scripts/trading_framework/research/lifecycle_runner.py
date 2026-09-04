import os
import sys
import json
import asyncio
from pathlib import Path

# This module prints emoji at every stage. On a default Windows console stdout
# is cp1252, which cannot encode them, so the FIRST status line raised
# UnicodeEncodeError and killed the run before any data was loaded. Reconfigure
# rather than strip the emoji: the same hazard reaches anything this module
# prints, including exception text from deeper in the stack.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
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

from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.strategies.registry import get_strategy
from scripts.trading_framework.ml.walk_forward import sequential_evaluation_folds
from scripts.trading_framework.reporting.risk_profiler import RiskProfiler
from scripts.trading_framework.reporting.optimization_summary import OptimizationReporter
from scripts.trading_framework.provenance.run_record import UNDECLARED, RunRecord

class ResearchLifecycleRunner:
    """
    Standardized institutional lifecycle for strategy research.
    Implements Layers 5, 6, and 7 of the framework.
    """
    def __init__(self, ticker="NQ1", strategy_key="box_reversion",
                 price_adjustment=UNDECLARED):
        self.ticker = ticker
        self.strategy_key = strategy_key
        # Back-adjusted continuous futures and per-contract unadjusted prices are
        # different price series, and the NT8 side inherited MergeBackAdjusted
        # from a machine-wide global for an unknown length of time. There is no
        # honest default here, so the record stores "undeclared" until a caller
        # says which basis its parquet is on.
        self.price_adjustment = price_adjustment
        self._eval_folds = None
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

    # Bars a trade is allowed to search forward for its exit. Must match
    # VectorizedBacktester's MAX_SEARCH, or the buffer reserved per fold does
    # not cover the search the engine actually performs.
    EXIT_BUFFER_BARS = 1440
    # Bars skipped between consecutive evaluation windows.
    EMBARGO_BARS = 1440

    def _optimize_params(self, data, trials=10):
        """Standardized Layer 6 Optuna optimization.

        HISTORY. This objective used to call `generate_signals(fold_train)` and
        then `backtester.run(signals, fold_test)`. Those are two DIFFERENT
        frames. `Index.get_indexer(..., method='bfill')` snaps an out-of-range
        timestamp to the next available bar with no distance limit and returns
        -1 only when no later bar exists at all, so every train-fold signal
        mapped to index 0 of the test frame and passed the engine's `!= -1`
        validity check. The objective was therefore "score N signals as if all
        of them entered on the first bar of the test window", which Optuna
        maximised for as many trials as it was given. The PurgedKFold wrapper
        could not detect this: the signals had never been indexed to the test
        fold at all, so there was nothing for a purge to do.

        The construction now keeps the three boundaries separate -- see
        `sequential_evaluation_folds` -- and passes `strict_alignment=True`, so
        if signals and frame ever diverge again the run RAISES instead of
        returning a plausible number.

        Caveat worth carrying: `VectorizedBacktester` builds Sharpe from a
        per-BAR series that is zero except at exit bars, so the value scales
        with frame length. Fold Sharpes are comparable to EACH OTHER because the
        windows are equal-length; they are NOT comparable to the OOS Sharpe,
        which is measured over a much longer frame.
        """
        folds = sequential_evaluation_folds(
            len(data), n_splits=3,
            exit_buffer=self.EXIT_BUFFER_BARS, embargo=self.EMBARGO_BARS,
        )
        self._eval_folds = folds
        width = folds[0]['test_end'] - folds[0]['test_start']
        print(f"   Evaluation windows: {len(folds)} x {width} bars "
              f"(+{self.EXIT_BUFFER_BARS} exit buffer, {self.EMBARGO_BARS} embargo)")

        def objective(trial):
            # Dynamic grid from strategy architecture (ADR-017)
            grid = self.strategy.get_param_grid()
            params = {}
            for k, v in grid.items():
                params[k] = self._suggest_from_grid(trial, k, v)

            fold_sharpes = []
            for f in folds:
                # The generator sees history up to the END of the window and no
                # further, so a signal inside the window cannot be informed by a
                # bar after it.
                gen_df = data.iloc[: f['gen_end']]
                signals = self.strategy.generate_signals(gen_df, params)
                if signals is None or len(signals) == 0:
                    fold_sharpes.append(-1.0)
                    continue

                # Only signals raised INSIDE this window are this window's
                # evidence. Everything earlier belongs to a previous fold and is
                # exactly what used to be collapsed onto bar 0.
                w_start = data.index[f['test_start']]
                w_end = data.index[f['test_end'] - 1]
                st = pd.to_datetime(signals['signal_time'])
                signals = signals[(st >= w_start) & (st <= w_end)]
                if signals.empty:
                    fold_sharpes.append(-1.0)
                    continue

                # Scored on a frame that BEGINS at the window (so every
                # signal_time is an exact index member) and runs past its end
                # (so a late trade can still resolve).
                score_df = data.iloc[f['score_start']: f['score_end']]
                metrics = self.backtester.run(signals, score_df, {
                    'leverage': 1.0,
                    'ticker': self.ticker,
                    'strict_alignment': True,
                })

                # A fold that produced NO trades must not outscore a fold that
                # lost money. `_null_metrics` returns sharpe 0.0, which is
                # better than any real loss, so scoring it as-is rewards
                # parameter sets that stop trading. Measured 2026-09-04 on
                # mean_reversion: an empty fold scored 0.0000 and outranked a
                # trading fold at -0.0222 in the same objective.
                if int(metrics.get('num_trades', 0)) == 0:
                    fold_sharpes.append(-1.0)
                    continue

                fold_sharpes.append(metrics.get('sharpe_ratio', -1.0))

                trial.report(fold_sharpes[-1], f['fold'])
                if trial.should_prune():
                    raise optuna.exceptions.TrialPruned()

            return float(np.mean(fold_sharpes)) if fold_sharpes else -1.0

        study = optuna.create_study(
            study_name=f"{self.strategy_name}_{self.ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            storage="sqlite:///optuna_research.db",
            direction="maximize",
            load_if_exists=True
        )
        study.optimize(objective, n_trials=trials, n_jobs=4)
        return study

    async def _persist_to_hub(self, run_id, ticker, best_params, oos_metrics, run_dir, git_hash=None):
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
                # `gitHash` has been in the ResearchRun schema since it was
                # written and was never populated, so every stored run in the hub
                # is unattributable to any code state. The full record lives in
                # run_record.json beside the artifacts; this is the joinable key.
                'gitHash': git_hash,
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

    def run_full_cycle(self, trials=10, persist_to_hub=True,
                       allow_unattributable=False):
        """Run the lifecycle under a run record, and refuse to REPORT a result
        that cannot be attributed.

        Every stage is recorded, including one that fails, and the run appears in
        `results/RESEARCH/_run_ledger.jsonl` from the moment it opens -- so a
        crashed or abandoned arm leaves a trace rather than vanishing. An arm
        that disappears from the ledger is how a search launders its own
        multiple-testing problem.
        """
        RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results/RESEARCH")
        RUN_ID = RunRecord.new_run_id(self.ticker, self.strategy_key)
        RUN_DIR = os.path.join(RESULTS_ROOT, self.strategy_name, self.ticker, RUN_ID)
        os.makedirs(RUN_DIR, exist_ok=True)

        rec = RunRecord.open(RUN_ID, strategy_key=self.strategy_key, ticker=self.ticker)
        rec.declare_strategy(name=self.strategy_name,
                             cls_name=type(self.strategy).__name__,
                             param_grid=self.strategy.get_param_grid())
        rec.declare_engine(self.backtester)

        print(f"\U0001f680 Initializing Institutional Lifecycle for {self.ticker} [{self.strategy_name}]...")
        print(f"   run id: {RUN_ID}")

        try:
            # 1. Load Data (Layer 1/2)
            with rec.stage("load_data") as st:
                loader = DataLoader(load_config())
                df = loader.load_enriched(self.ticker)
                st.detail(rows=int(len(df)), columns=int(len(df.columns)))
            rec.declare_data(df, ticker=self.ticker,
                             loader="DataLoader.load_enriched",
                             adjustment=self.price_adjustment)

            # 2. In-Sample / Out-of-Sample Split (Layer 5)
            with rec.stage("split") as st:
                df_is = df[df.index.year <= 2023]
                df_oos = df[df.index.year >= 2024]
                # Boundaries are RECORDED rather than described in a comment: the
                # comment here read "IS: 2018-2023" while the loader actually
                # returns bars from 2016, and a stale comment is how an
                # unreproducible split survives.
                st.detail(
                    rule="IS = year <= 2023, OOS = year >= 2024",
                    is_rows=int(len(df_is)), oos_rows=int(len(df_oos)),
                    is_first=str(df_is.index[0]) if len(df_is) else None,
                    is_last=str(df_is.index[-1]) if len(df_is) else None,
                    oos_first=str(df_oos.index[0]) if len(df_oos) else None,
                    oos_last=str(df_oos.index[-1]) if len(df_oos) else None,
                )
                if df_is.empty:
                    rec.refuse("in-sample window is EMPTY; nothing was optimised")
                if df_oos.empty:
                    rec.refuse("out-of-sample window is EMPTY; the reported metrics "
                               "are not an out-of-sample result")

            # 3. Optimize (Layer 6)
            print(f"\U0001f52c Running In-Sample Optimization ({trials} trials)...")
            with rec.stage("optimize") as st:
                study = self._optimize_params(df_is, trials=trials)
                best_params = study.best_params
                states = {}
                for t in study.trials:
                    states[t.state.name] = states.get(t.state.name, 0) + 1
                st.detail(requestedTrials=int(trials), bestValue=float(study.best_value),
                          bestParams=best_params, trialStates=states,
                          studyName=study.study_name)
            rec.declare_folds(self._eval_folds)
            rec.declare_strategy(params=best_params)
            print(f"\U0001f3c6 Best Params: {best_params}")

            # 4. Validate (OOS)
            print("\U0001f52c Running Out-of-Sample Validation...")
            with rec.stage("oos") as st:
                oos_signals = self.strategy.generate_signals(df_oos, best_params)
                # `ticker` was previously omitted here, so the engine silently fell
                # back to its NQ1 point multiplier for every instrument.
                # `strict_alignment` is deliberately FALSE: signals are generated
                # on df_oos itself so they should align exactly, and if they ever
                # do not we want the counted report recorded and the run marked
                # unattributable, rather than an exception that discards it.
                oos_metrics = self.backtester.run(oos_signals, df_oos, {
                    'leverage': 1.0,
                    'ticker': self.ticker,
                    'strict_alignment': False,
                })
                st.detail(signals=int(0 if oos_signals is None else len(oos_signals)),
                          trades=int(oos_metrics.get('num_trades', 0)))
            rec.record_alignment("oos", oos_metrics.get('signal_alignment'))
            rec.set_metrics(oos_metrics)

            if int(oos_metrics.get('num_trades', 0)) == 0:
                rec.refuse("out-of-sample produced ZERO trades; every reported "
                           "metric is the null result, not a measurement")

            # 5. Risk profile
            with rec.stage("risk_profile"):
                risk_profiler = RiskProfiler(account_size=50000.0, risk_per_trade=500.0)
                raw_risk_metrics = risk_profiler.calculate_metrics(
                    oos_metrics['trade_returns_pct'], oos_metrics['max_drawdown_%'],
                    formatted=False)

            # 6. THE GATE. Reporting is refused before it happens, not after.
            check = rec.attribution()
            if not check['attributable']:
                print("\n\u274c This run is NOT attributable and will not be reported:")
                for r in check['refusals']:
                    print(f"     refusal: {r}")
                for m in check['missingRequired']:
                    print(f"     missing: {m}")
                if not allow_unattributable:
                    rec.finalize(RUN_DIR, status="refused")
                    print(f"\n   Record written: {os.path.join(RUN_DIR, 'run_record.json')}")
                    print("   Re-run with --allow-unattributable to produce a report anyway.")
                    return None
                # A bypass that is not itself recorded is a bypass nobody can
                # audit, so the record carries the fact that it was overridden.
                rec.warn("REPORTED DESPITE REFUSAL: --allow-unattributable was set, "
                         "overriding {} refusal(s)".format(len(check['refusals'])))
                print("   \u26a0\ufe0f  --allow-unattributable set; reporting anyway "
                      "and recording the override.")

            # 7. Persist & Sync (Layer 7)
            if persist_to_hub:
                can_persist, reason = self._can_persist_to_hub()
                if not can_persist:
                    print(f"\u26a0\ufe0f Skipping hub persistence: {reason}.")
                    rec.warn(f"hub persistence skipped: {reason}")
                else:
                    if reason != 'ok':
                        print(f"\u2139\ufe0f {reason}")
                    with rec.stage("persist_hub") as st:
                        try:
                            asyncio.run(self._persist_to_hub(
                                RUN_ID, self.ticker, best_params, oos_metrics, RUN_DIR,
                                git_hash=rec.doc['code'].get('commit')))
                            st.detail(persisted=True)
                        except Exception as exc:
                            st.detail(persisted=False, error=str(exc))
                            st.status = "ok"  # non-fatal, but recorded as not persisted
                            rec.warn(f"hub persistence failed: {exc}")
                            print(f"\u26a0\ufe0f Hub persistence failed: {exc}")
            else:
                print("\u2139\ufe0f Skipping hub persistence (--skip-persist enabled).")
                rec.warn("hub persistence skipped by caller (--skip-persist)")

            # 8. Report
            print("\U0001f4ca Generating Institutional Research Summary...")
            with rec.stage("report") as st:
                opt_reporter = OptimizationReporter(RUN_DIR)
                trials_df = study.trials_dataframe()
                summary_path = opt_reporter.generate_report(
                    run_id=RUN_ID,
                    ticker=self.ticker,
                    strategy_name=self.strategy_name,
                    best_params=best_params,
                    risk_metrics=raw_risk_metrics,
                    trials_df=trials_df,
                )
                st.detail(summary=str(summary_path))
            rec.add_artifact("optimizationSummary", str(summary_path))

        except BaseException as exc:
            # The record is written on the way out, so a crashed run is still an
            # entry in the ledger with the stage that killed it named.
            rec.fail(exc, RUN_DIR)
            print(f"\n\u274c Run FAILED and was recorded: {type(exc).__name__}: {exc}")
            print(f"   Record: {os.path.join(RUN_DIR, 'run_record.json')}")
            raise

        record = rec.finalize(RUN_DIR)

        print(f"\U0001f4ca OOS Sharpe: {oos_metrics.get('sharpe_ratio', 0):.2f}")
        print(f"   attributable: {record['attributable']}  "
              f"warnings: {len(record['warnings'])}  refusals: {len(record['refusals'])}")
        for w in record['warnings']:
            print(f"     warning: {w}")
        print(f"\u2705 Lifecycle Test Complete. Artifacts in {RUN_DIR}")
        print(f"\U0001f4c2 Summary Report: {summary_path}")
        print(f"\U0001f9fe Run Record: {os.path.join(RUN_DIR, 'run_record.json')}")
        return record


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
    parser.add_argument(
        "--price-adjustment", default=UNDECLARED,
        choices=[UNDECLARED, "unadjusted", "back_adjusted", "ratio_adjusted"],
        help="Price basis of the loaded parquet. There is no honest default: "
             "back-adjusted continuous futures and per-contract unadjusted "
             "prices are different series, and a result cannot be compared to "
             "an NT8 run without knowing which one it used.")
    parser.add_argument(
        "--allow-unattributable", action="store_true",
        help="Produce a report even when the run record refuses. The override "
             "is itself recorded in run_record.json, so a bypassed refusal "
             "stays auditable.")
    args = parser.parse_args()

    runner = ResearchLifecycleRunner(ticker=args.ticker, strategy_key=args.strategy,
                                     price_adjustment=args.price_adjustment)
    runner.run_full_cycle(trials=args.trials, persist_to_hub=not args.skip_persist,
                          allow_unattributable=args.allow_unattributable)
