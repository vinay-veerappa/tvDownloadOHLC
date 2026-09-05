"""
Institutional Research Suite: Unified CLI Entry Point
"""
import os
import sys
import argparse
import re
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any

# Ensure project root is in path
PROJECT_ROOT = os.getcwd()
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.trading_framework.config.config_loader import load_config
from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.strategies.registry import get_strategy
from scripts.trading_framework.research.objective import (
    EMBARGO_BARS,
    EXIT_BUFFER_BARS,
    assert_grid_is_live,
    build_folds,
    make_cv_objective,
    probe_causality,
)
from scripts.trading_framework.provenance.run_record import (
    UNDECLARED,
    RunRecord,
    trade_count,
)
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.core.nt8_parity_backtester import NT8ParityBacktester
from scripts.trading_framework.core.mfe_mae import compute_mfe_mae
from scripts.trading_framework.reporting.tearsheet import (
    compute_institutional_metrics,
    generate_tearsheet,
)
from scripts.trading_framework.reporting.mfe_mae_report import (
    generate_mfe_mae_summary,
    plot_mfe_mae_analysis,
)
from scripts.trading_framework.reporting.chop_filter_report import generate_chop_report
from scripts.trading_framework.ml.prop_firm_simulator import (
    PropFirmSimulator,
    FIRM_PROFILES,
    PropFirmProfile,
)
from scripts.trading_framework.ml.optimizer import OptunaOptimizer

import optuna


def _extract_horizons(mfe_mae_df: pd.DataFrame, configured_horizons) -> list[int]:
    if configured_horizons:
        return list(configured_horizons)

    inferred = []
    for col in mfe_mae_df.columns:
        match = re.fullmatch(r"mfe_(\d+)", str(col))
        if match:
            inferred.append(int(match.group(1)))
    return sorted(set(inferred))


def compute_prop_eval_stats(trade_returns_pct: pd.Series, _mc_config=None) -> Dict[str, Any]:
    """
    Backward-compatible shim retained for legacy test callers.
    New code should use PropFirmSimulator.run_all_profiles() directly.
    Converts per-trade % returns to approximate daily P&L before simulation.
    """
    # Treat each trade return as a synthetic daily P&L unit (approximate)
    account_size = 50_000.0
    daily_pnl = trade_returns_pct / 100.0 * account_size
    sim = PropFirmSimulator(account_size=account_size)
    profile = FIRM_PROFILES["apex_50k"]
    # Build a minimal trades_detailed-compatible DataFrame
    synthetic = pd.DataFrame({"pnl_pct": trade_returns_pct.values})
    mc = sim.run_monte_carlo(synthetic, profile, n_simulations=2000)
    return {"pass_rate": mc.pass_rate_pct / 100.0, "msg": mc.grade}


def generate_mfe_mae_report(
    mfe_mae_df: pd.DataFrame,
    mfe_mae_config,
    ticker: str,
    output_dir: str,
) -> None:
    """MFE/MAE report writer. `output_dir` is REQUIRED and is the run directory.

    It used to default to `scripts/trading_framework/reporting/outputs`, a fixed
    TRACKED path shared by every run of every strategy. So each run silently
    overwrote the previous one's numbers in a committed file that names no
    strategy, no date range, no parameters and no data -- and a `git diff` after a
    backtest showed a tracked report changing for reasons nobody could attribute.
    Measured on this very file: two workflow runs moved the 5-bar efficiency ratio
    from 0.82 to 1.27 with no record of which run produced either.

    Same defect as the fixed-path tearsheet (STRATEGY_WORKFLOW.md section 7.3).
    Removing the default rather than changing it: a default is what made this
    reachable without anybody choosing it.
    """
    if mfe_mae_df is None or mfe_mae_df.empty:
        return

    os.makedirs(output_dir, exist_ok=True)
    configured_horizons = getattr(mfe_mae_config, "forward_horizons_minutes", None)
    horizons = _extract_horizons(mfe_mae_df, configured_horizons)
    if not horizons:
        return

    summary = generate_mfe_mae_summary(mfe_mae_df, horizons)
    summary_path = os.path.join(output_dir, f"mfe_mae_summary_{ticker}.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    for horizon in horizons:
        if f"mfe_{horizon}" in mfe_mae_df.columns and f"mae_{horizon}" in mfe_mae_df.columns:
            plot_mfe_mae_analysis(mfe_mae_df, horizon, output_dir)


def _compute_mfe_mae_compat(signals: pd.DataFrame, df: pd.DataFrame, mfe_mae_config):
    """Compute MFE/MAE by mapping canonical signals back to OHLC DataFrame."""
    horizons = getattr(mfe_mae_config, "forward_horizons_minutes", [5, 15, 30, 60, 120])
    work_df = df.copy()

    if "signal" not in work_df.columns:
        work_df["signal"] = 0
        
    if "atr_14" not in work_df.columns:
        work_df["atr_14"] = 1.0

    if isinstance(signals, pd.DataFrame) and {"signal_time", "direction"}.issubset(signals.columns):
        for _, row in signals.iterrows():
            ts = row.get("signal_time")
            if ts in work_df.index:
                direction = str(row.get("direction", "")).lower()
                work_df.at[ts, "signal"] = 1 if direction == "long" else -1 if direction == "short" else 0

    return compute_mfe_mae(work_df, "signal", horizons)


def run_optimization(args, config, df, engine=None):
    """Optuna study over the STRATEGY'S OWN grid, on embargoed windows.

    Two defects lived here, both measured 2026-09-04 on NQ1:

    1. The parameter space was HARDCODED to BoxReversion's keys (`min_dist`,
       `sl_dist`, `tp_buffer`, `filter_high_vol`) regardless of `--strategy`.
       Every other strategy ignores those keys and falls back to its own
       defaults, so three widely separated points in that space produced
       BYTE-IDENTICAL signal frames for mean_reversion (176 signals),
       ema_pullback (146) and ib_pullback (95). The study spent its whole trial
       budget on a space that could not change the answer, then printed "Best IS
       Parameters" and "Estimated CV Sharpe". `assert_grid_is_live` now refuses
       that before any trial runs.

    2. `generate_signals(fold_train)` was scored against `fold_test` -- two
       different frames. `Index.get_indexer(..., method='bfill')` snaps every
       out-of-range timestamp onto bar 0 of the test frame and returns -1 only
       when no later bar exists, so the whole signal set scored as if it had
       entered on the first bar of the window. Identical to the defect in
       `ResearchLifecycleRunner`; the framing rules are now shared rather than
       duplicated, so there is one place to get it right.
    """
    strategy = get_strategy(args.strategy, args.ticker)
    grid = strategy.get_param_grid()
    print(f"[*] Starting Institutional Optimization for {args.ticker}...")
    print(f"[*] Grid: {sorted(grid.keys())}")

    probe = assert_grid_is_live(strategy, df, grid)
    print(f"[*] Grid precheck: {probe['reason']}")

    folds = build_folds(len(df), n_splits=3)
    width = folds[0]['test_end'] - folds[0]['test_start']
    print(f"[*] Evaluation windows: {len(folds)} x {width} bars "
          f"(+{EXIT_BUFFER_BARS} exit buffer, {EMBARGO_BARS} embargo)")

    objective = make_cv_objective(
        strategy, df, engine or VectorizedBacktester(), args.ticker, grid, folds)

    study_name = f"opt_{args.ticker}_{args.strategy}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    optimizer = OptunaOptimizer(study_name=study_name)
    study = optimizer.run_optimization(objective, n_trials=args.trials)

    print(f"[*] Best IS Parameters: {study.best_params}")
    print(f"[*] Estimated CV Sharpe: {study.best_value:.2f}")
    return study.best_params, {"gridProbe": probe, "folds": folds,
                               "studyName": study_name,
                               "bestValue": float(study.best_value),
                               # The per-trial frame, for the optimisation report.
                               # Kept OUT of the run record deliberately: a
                               # DataFrame is not JSON-serialisable and the record
                               # must stay writable.
                               "_trialsDf": study.trials_dataframe()}


def run_research_pipeline(args, rec=None, output_dir=None):
    """Executes the 7-layer research pipeline under a run record.

    IN-SAMPLE REPORTING. This function used to optimise on `df` and then report
    on `df`. With `--optimize` that made the tearsheet an in-sample result of a
    searched parameter set -- the most reliable way to produce a number that
    will not replicate -- and nothing in the output said so. `--oos-start` is
    now REQUIRED whenever `--optimize` is passed: the search sees only bars
    before it, the reported metrics come only from bars after it. Without
    `--optimize` there is no search, so a full-sample run is a legitimate
    backtest of fixed parameters and no split is demanded (it is recorded as
    in-sample either way).

    OUTPUT PATHS were `tearsheet_{ticker}_{strategy}.md`, so consecutive runs
    with different parameters silently overwrote each other and no history
    existed. Artifacts now live under a run id.
    """
    print(f"[*] Initializing Research Pipeline for {args.ticker} using {args.strategy}...")

    config = load_config(args.config)
    strategy = get_strategy(args.strategy, args.ticker)

    # The caller may OWN the record: `workflow.py` runs NT8 validation and
    # trade-set parity as further stages of the SAME run, and two records for one
    # workflow fragments exactly the provenance the record exists to hold.
    owns_record = rec is None
    if owns_record:
        RUN_ID = RunRecord.new_run_id(args.ticker, args.strategy)
        output_dir = os.path.join("results", "RESEARCH", "_pipeline", args.ticker, RUN_ID)
        rec = RunRecord.open(RUN_ID, strategy_key=args.strategy, ticker=args.ticker)
    else:
        RUN_ID = rec.run_id
        if output_dir is None:
            raise ValueError(
                "a caller that supplies `rec` must supply `output_dir` too -- "
                "otherwise the artifacts land somewhere the record does not name")
    os.makedirs(output_dir, exist_ok=True)
    rec.declare_strategy(name=getattr(strategy, "strategy_name", args.strategy),
                         cls_name=type(strategy).__name__,
                         param_grid=strategy.get_param_grid())
    print(f"[*] run id: {RUN_ID}")

    try:
        with rec.stage("load_data") as st:
            print("* Loading data...")
            loader = DataLoader(config)
            df = loader.load_enriched(args.ticker)
            st.detail(rows=int(len(df)), columns=int(len(df.columns)))
        rec.declare_data(df, ticker=args.ticker,
                         loader="DataLoader.load_enriched",
                         adjustment=args.price_adjustment)

        with rec.stage("split") as st:
            oos_start = getattr(args, "oos_start", None)
            if args.optimize and not oos_start:
                raise ValueError(
                    "--optimize without --oos-start would report the SAME bars "
                    "the search selected on, which is an in-sample result. Pass "
                    "--oos-start YYYY-MM-DD: the search then sees only earlier "
                    "bars and the report only later ones.")
            if oos_start:
                cut = pd.Timestamp(oos_start)
                if df.index.tz is not None and cut.tz is None:
                    cut = cut.tz_localize(df.index.tz)
                df_search = df[df.index < cut]
                df_report = df[df.index >= cut]
                if df_search.empty or df_report.empty:
                    raise ValueError(
                        "--oos-start {} splits the data into {} search bars and "
                        "{} report bars; one side is empty.".format(
                            oos_start, len(df_search), len(df_report)))
            else:
                df_search, df_report = df, df
            st.detail(oosStart=str(oos_start) if oos_start else None,
                      searchBars=int(len(df_search)),
                      reportBars=int(len(df_report)),
                      reportIsOutOfSample=bool(oos_start),
                      reportFirstBar=str(df_report.index[0]),
                      reportLastBar=str(df_report.index[-1]))
            if not oos_start:
                rec.warn("no --oos-start: reported metrics cover the SAME bars "
                         "the pipeline ran on. Valid for fixed parameters, not "
                         "for a searched result.")

        best_params = {}
        trials_df = None
        if args.optimize:
            with rec.stage("optimize") as st:
                best_params, opt_meta = run_optimization(args, config, df_search)
                trials_df = opt_meta.pop("_trialsDf", None)
                st.detail(requestedTrials=int(args.trials),
                          studyName=opt_meta["studyName"],
                          bestValue=opt_meta["bestValue"],
                          completedTrials=(int(len(trials_df))
                                           if trials_df is not None else None))
            rec.declare_folds(opt_meta["folds"])
            rec._doc["gridProbe"] = opt_meta["gridProbe"]
        rec.declare_strategy(params=best_params)

        # The "generate once over the full frame, score a later slice"
        # construction below is only sound if the generator is causal. Nothing
        # checked that until now.
        with rec.stage("causality_probe") as st:
            probe = probe_causality(strategy, df_report, best_params)
            st.detail(**{k: v for k, v in probe.items() if k != "perCutoff"})
            print(f"* Causality probe: {probe['reason']}")
            if probe.get("causal") is False:
                rec.refuse("causality probe: " + probe["reason"])
            elif probe.get("causal") is None:
                rec.warn("causality probe inconclusive: " + probe["reason"])

        print("* Generating signals...")
        with rec.stage("generate_signals") as st:
            signals = strategy.generate_signals(df, best_params)
            n_all = 0 if signals is None else len(signals)
            if signals is not None and len(signals) and oos_start:
                _st = pd.to_datetime(signals["signal_time"])
                signals = signals[(_st >= df_report.index[0])
                                  & (_st <= df_report.index[-1])]
            st.detail(signalsGenerated=int(n_all),
                      signalsInReportWindow=int(0 if signals is None else len(signals)))
    
        # 4. Backtest Engine Execution
        print(f"* Running backtest engine ({args.engine})...")
        if getattr(args, "engine", "nt8_parity") == "nt8_parity":
            # THESE WERE READ OFF THE WRONG CONFIG OBJECT. Every one of the
            # session-risk knobs below lives on `config.session_risk`, not
            # `config.account_risk`, and four of the five were fetched with
            # `getattr(config.account_risk, ..., <default>)` -- so they silently
            # resolved to the hardcoded defaults 3 / 2 / 30 / 3 rather than to
            # anything in sessions.yaml. The fifth used direct attribute access
            # and raised `AttributeError: 'AccountRiskConfig' object has no
            # attribute 'daily_loss_limit'`, which is the ONLY reason this was
            # visible at all: `--engine nt8_parity` is the ADR-024 DEFAULT, so a
            # default invocation of this pipeline had never completed. Had that
            # one also used getattr, the run would have succeeded with entirely
            # fabricated risk limits.
            #
            # Read from session_risk, and let a missing field raise rather than
            # substituting a number nobody chose -- a default and an erasure are
            # indistinguishable once they are in a result.
            sr = config.session_risk
            engine_cfg = {
                "account_size": config.account_risk.starting_equity,
                "max_trades_per_day": sr.max_trades_per_day,
                "max_consecutive_losers": sr.max_consecutive_losers,
                "pause_minutes": sr.pause_after_consecutive_minutes,
                "hard_stop_losers": sr.hard_stop_consecutive_losers,
                "daily_max_loss": sr.daily_max_loss,
                "contracts": 2,
            }
            rec._doc.setdefault("executionPolicy", {}).update(engine_cfg)
            engine = NT8ParityBacktester(**engine_cfg)
            risk_dict = {
                'ticker': args.ticker,
                'queen_bps': 10.0,
                'runner_bps': 30.0,
                'earliest_entry_hhmm': 945,
                'latest_entry_hhmm': 1530,
                'flatten_hhmm': 1555,
                'filter_lunch': True,
            }
            # Recorded because these were hardcoded here and reached no
            # artifact: a result produced under a 09:45-15:30 entry window with
            # lunch filtered is not comparable to one without, and nothing said
            # which had been used.
            rec._doc.setdefault("executionPolicy", {}).update(risk_dict)
            result = engine.run(signals, df_report, risk_dict)
        else:
            engine = VectorizedBacktester()
            # `ticker` was omitted, so the engine silently fell back to its
            # NQ1 point multiplier for every instrument.
            result = engine.run(signals, df_report, {'leverage': 1.0, 'ticker': args.ticker})
    
        # 5. Advanced Research Analysis (MFE/MAE)
        rec.declare_engine(engine)
        rec.record_alignment("report", result.get('signal_alignment'))
        rec.set_metrics(result)
        # trade_count() rather than .get(..., 0): the two engines name this
        # key differently and a default of 0 refused a run that had taken 38
        # trades at a 71%% win rate.
        if trade_count(result) == 0:
            rec.refuse("the reporting window produced ZERO trades; every "
                       "metric below is the null result, not a measurement")

        # PERSIST THE TRADES. Trade-set parity compares trades, not metrics, and
        # a pipeline that reports a win rate while keeping its trade list only in
        # memory cannot be checked against NT8 at all. Written under the run id,
        # so the trades and the record that describes them cannot be separated.
        trades_df = result.get('trades_detailed')
        if trades_df is not None and not getattr(trades_df, 'empty', True):
            trades_path = os.path.join(output_dir, 'python_trades.csv')
            trades_df.to_csv(trades_path, index=False)
            rec.add_artifact('pythonTrades', trades_path)
            print(f"* Python trades: {len(trades_df)} rows -> {trades_path}")
        else:
            rec.warn("no trades_detailed frame was produced, so this run cannot "
                     "be compared to an NT8 trade list")

        print("* Computing MFE/MAE excursions...")
        mfe_mae_signals = _compute_mfe_mae_compat(signals, df_report, config.mfe_mae)
    
        # 6. ML / Prop Evaluation (ADR-021: Unified PropFirmSimulator)
        print("* Computing Prop Firm evaluation (Monte Carlo across all firm profiles)...")
        trades_detailed = result.get('trades_detailed', pd.DataFrame())
        pf_config = config.prop_firm

        # Build overridden profiles from config
        sim_profiles: list[PropFirmProfile] = []
        for key in pf_config.run_profiles:
            if key not in FIRM_PROFILES:
                print(f"  *  Unknown profile key '{key}' in config * skipping.")
                continue
            base = FIRM_PROFILES[key]
            overrides = pf_config.overrides.get(key, {})
            if overrides:
                # Rebuild with overrides applied (frozen dataclass needs replace)
                from dataclasses import replace
                base = replace(base, **overrides)
            sim_profiles.append(base)

        pf_sim = PropFirmSimulator(
            account_size=config.account_risk.starting_equity,
            point_value=config.execution.point_value.get(args.ticker, 2.0),
        )

        all_pf_results = {}
        primary_det = None
        primary_mc = None
        pf_summary_md = ""

        if not trades_detailed.empty and sim_profiles:
            for profile in sim_profiles:
                det = pf_sim.run_deterministic(trades_detailed, profile)
                mc  = pf_sim.run_monte_carlo(trades_detailed, profile, n_simulations=pf_config.n_simulations)
                all_pf_results[profile.name] = (det, mc)
                print(f"  * {profile.name}: Pass Rate {mc.pass_rate_pct:.1f}% (Grade {mc.grade}) | Blow {mc.blow_rate_pct:.1f}%")
                if profile.name == FIRM_PROFILES.get(pf_config.primary_profile, sim_profiles[0]).name:
                    primary_det, primary_mc = det, mc

            if primary_det is None and all_pf_results:
                primary_det, primary_mc = next(iter(all_pf_results.values()))

            # Build multi-profile summary markdown
            pf_summary_md = pf_sim.format_multi_report(
                {k: v for k, v in all_pf_results.items()}
            )
            if primary_det is not None:
                pf_summary_md += pf_sim.format_report(primary_det, primary_mc)
        else:
            print("  *  No trades_detailed available * skipping prop firm simulation.")

        # 7. Reporting Suite
        print("* Generating institutional reports...")

        class MockResult:
            def __init__(self, res, primary_det, primary_mc, pf_summary_md, config):
                self.combined_equity_curve = res['equity_curve']
            
                trades_df = res.get('trades_detailed', pd.DataFrame())
                class MockTrade:
                    def __init__(self, pnl):
                        self.realized_pnl = pnl

                # Convert pnl_pct to dollar PNL
                starting_equity = config.account_risk.starting_equity
                if not trades_df.empty and 'pnl_pct' in trades_df.columns:
                    self.combined_trades = [MockTrade((pnl / 100.0) * starting_equity) for pnl in trades_df['pnl_pct']]
                else:
                    self.combined_trades = []

                self.prop_eval_passed = (primary_mc.pass_rate_pct >= 65.0) if primary_mc else False
                self.prop_firm_grade = primary_mc.grade if primary_mc else 'N/A'
                self.prop_firm_summary_md = pf_summary_md
                self.days_to_pass = primary_mc.avg_days_to_pass if primary_mc else None
                self.account_summary = {
                    'starting_equity': config.account_risk.starting_equity,
                    'risk_per_trade': config.session_risk.daily_max_loss / config.session_risk.max_trades_per_day,
                    'peak_equity': res['equity_curve'].max(),
                    'current_balance': res['equity_curve'].iloc[-1],
                    'current_drawdown': (res['equity_curve'].iloc[-1] / res['equity_curve'].max()) - 1,
                    'max_trailing_drawdown': config.account_risk.trailing_drawdown
                }

        perf_result = MockResult(result, primary_det, primary_mc, pf_summary_md, config)
    
        # RUIN BASIS. Decided 2026-09-04: ruin is the prop firm's TRAILING
        # DRAWDOWN, not the account size. The old code used the whole account,
        # which put ~200-400 in an exponent and made risk of ruin report 0.00%
        # for every profitable system -- the spec's own bands were unreachable.
        ruin_basis = None
        try:
            from scripts.trading_framework.reporting.institutional_metrics import (
                ruin_basis_from_profile)
            _profile = FIRM_PROFILES.get(pf_config.primary_profile)
            _risk = config.session_risk.daily_max_loss / config.session_risk.max_trades_per_day
            if _profile is not None:
                ruin_basis = ruin_basis_from_profile(_profile, _risk)
                rec.note("ruinBasis", ruin_basis.source)
                print(f"  * Risk-of-ruin basis: {ruin_basis.source} "
                      f"= {ruin_basis.units:.1f} losing trades")
        except (ValueError, AttributeError, KeyError) as exc:
            # Refuse quietly to the DEFAULT basis rather than to the account
            # size, and say so -- an undeclared basis is what made the number
            # meaningless before.
            rec.warn(f"could not derive a ruin basis from the prop profile: {exc}")
        perf_result.ruin_basis = ruin_basis

        # OPTIMISATION SUMMARY. Only meaningful when a search ran; it renders the
        # per-trial table saying WHICH arms were tried -- the half of an
        # optimisation result that a "best params" line throws away, and the half
        # deflated statistics need (plan 2.5).
        if trials_df is not None and not trials_df.empty:
            from scripts.trading_framework.reporting.optimization_summary import (
                OptimizationReporter)
            _risk = (config.session_risk.daily_max_loss
                     / config.session_risk.max_trades_per_day)
            _risk_metrics = compute_institutional_metrics(
                perf_result.combined_trades, perf_result.combined_equity_curve,
                config.account_risk.starting_equity, _risk,
                ruin_basis=ruin_basis)
            _summary = OptimizationReporter(output_dir).generate_report(
                run_id=RUN_ID, ticker=args.ticker, strategy_name=args.strategy,
                best_params=best_params, risk_metrics=_risk_metrics,
                trials_df=trials_df)
            rec.add_artifact("optimizationSummary", str(_summary))
            print(f"* Optimization summary: {_summary}")

        # Generate Tearsheet
        tearsheet = generate_tearsheet(perf_result)
    
        # Save Outputs
        # output_dir is the run-id'd directory created above; the old fixed path
        # overwrote the previous run on every invocation.
        os.makedirs(output_dir, exist_ok=True)
    
        ts_path = f"{output_dir}/tearsheet_{args.ticker}_{args.strategy}.md"
        with open(ts_path, "w", encoding="utf-8") as f:
            f.write(tearsheet)
        
        # Generate Plots
        generate_mfe_mae_report(mfe_mae_signals, config.mfe_mae,
                                args.ticker, output_dir)
        # generate_chop_report(df, signals, args.ticker) # Needs specific internal data
    
        print(f"\n* Research Pipeline Complete!")
        print(f"* Tearsheet: {ts_path}")
        print(f"* Plots saved to: {output_dir}")
        rec.add_artifact("tearsheet", ts_path)

        # THE GATE. Reporting has already happened above, so this refuses the
        # RESULT rather than the file: a non-attributable run is marked as such
        # in the record and in the ledger, and `assert_attributable` will refuse
        # it to anything downstream that tries to read it.
        # When the caller owns the record it finalizes AFTER its own stages;
        # finalizing here would close the run before parity had been measured.
        if not owns_record:
            # The caller closes the run after ITS stages. `attribution()` is a
            # non-mutating preview and carries only the attributability fields --
            # printing the finalize summary from it raised KeyError('warnings')
            # and turned a healthy pipeline into a failed run.
            return rec.attribution()

        record = rec.finalize(output_dir)
        print(f"[*] attributable: {record['attributable']}  "
              f"warnings: {len(record['warnings'])}  refusals: {len(record['refusals'])}")
        for r in record['refusals']:
            print(f"      refusal: {r}")
        for w in record['warnings']:
            print(f"      warning: {w}")
        print(f"[*] Run Record: {os.path.join(output_dir, 'run_record.json')}")
        if not record['attributable'] and not args.allow_unattributable:
            print("[!] This result is NOT attributable. Downstream readers will "
                  "refuse it; re-run with --allow-unattributable to override "
                  "(the override is recorded).")
        return record

    except BaseException as exc:
        if owns_record:
            rec.fail(exc, output_dir)
        print(f"\n[!] Pipeline FAILED and was recorded: {type(exc).__name__}: {exc}")
        print(f"    Record: {os.path.join(output_dir, 'run_record.json')}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Institutional Research Suite - Unified CLI")
    parser.add_argument("--ticker", type=str, default="NQ1", help="Ticker symbol (e.g., NQ1, ES1)")
    parser.add_argument("--strategy", type=str, default="box_reversion", help="Strategy key from registry")
    parser.add_argument("--config", type=str, default="scripts/trading_framework/config/sessions.yaml", help="Path to YAML config")
    parser.add_argument("--optimize", action="store_true", help="Run Optuna optimization study")
    parser.add_argument("--trials", type=int, default=20, help="Number of optimization trials")
    parser.add_argument("--engine", type=str, default="nt8_parity", choices=["nt8_parity", "vectorized"], help="Backtest engine: nt8_parity (ADR-024) or legacy vectorized")
    parser.add_argument(
        "--oos-start", type=str, default=None,
        help="First bar of the reporting window (YYYY-MM-DD). REQUIRED with "
             "--optimize: the search sees only earlier bars and the report only "
             "later ones. Without it, --optimize would report the same bars the "
             "search selected on, which is an in-sample result.")
    parser.add_argument(
        "--price-adjustment", type=str, default=UNDECLARED,
        choices=[UNDECLARED, "unadjusted", "back_adjusted", "ratio_adjusted"],
        help="Price basis of the loaded parquet. There is no honest default: "
             "back-adjusted continuous futures and per-contract unadjusted "
             "prices are different series, and a result cannot be compared to "
             "an NT8 run without knowing which one it used.")
    parser.add_argument(
        "--allow-unattributable", action="store_true",
        help="Do not warn when the run record refuses the result. The override "
             "is recorded in run_record.json, so it stays auditable.")

    args = parser.parse_args()
    run_research_pipeline(args)
