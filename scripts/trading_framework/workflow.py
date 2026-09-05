"""THE strategy workflow. One command, every stage, one run record.

    .venv\\Scripts\\python.exe -m scripts.trading_framework.workflow \\
        --strategy mean_reversion --ticker NQ1 \\
        --price-adjustment unadjusted --oos-start 2025-01-01 \\
        --optimize --trials 200 --nt8

WHY THIS EXISTS. The pipeline was designed once and then assembled ad hoc: there
are 35 `run_*` scripts in this repository, each wiring its own data load, its own
signal generation, its own execution model and its own reporting. Measured, only
ONE file imports `trading_framework.run_backtest`, and that file is its own smoke
test. So "the framework" was a library that nothing was obliged to use, and the
numbers different scripts produced were not comparable to each other -- which is
the same defect as Python and NT8 not being comparable, one level up.

This module is the single path. It does not add a new pipeline; it ORDERS the
ones that exist and holds them all under one run record, so that every result has
the same provenance and the same gates whichever question was being asked.

WHAT IT REFUSES TO DO. It will not quietly skip a stage. A stage that cannot run
is recorded as `skipped` WITH ITS REASON and is reported as NOT EVALUATED in the
promotion checklist at the end -- never as a pass. That distinction is the entire
point: the failure mode this project keeps hitting is not a red result, it is a
green one that was never actually measured. An empty comparison passing, a
tearsheet with no inputs, a backtest of whichever strategy happened to be loaded.

THE CHECKLIST IS THE OUTPUT. Metrics are secondary. The run ends by printing
every promotion criterion from STRATEGY_WORKFLOW.md section 9 with PASS, FAIL or
NOT EVALUATED, and the process exit code is non-zero if any criterion FAILED. A
criterion that could not be evaluated does not fail the run, but it does keep the
strategy out of `validated`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.trading_framework.provenance.run_record import RunRecord, UNDECLARED  # noqa: E402

# --------------------------------------------------------------------------- #
# Promotion criteria -- STRATEGY_WORKFLOW.md section 9.
#
# Each is a NAME plus the stage that decides it. Keeping the list here, in the
# runner, rather than in prose only, is what stops "validated" from meaning
# whatever the person saying it remembers.
# --------------------------------------------------------------------------- #
PASS = "PASS"
FAIL = "FAIL"
NOT_EVALUATED = "NOT EVALUATED"

CRITERIA = (
    ("registered", "strategy resolves through the registry and returns the canonical columns"),
    ("signal_geometry", "no signal has an impossible stop/target geometry"),
    ("grid_live", "the parameter grid can move the signal frame"),
    ("causal", "causality probe passes non-vacuously"),
    ("out_of_sample", "reported metrics are out-of-sample, or no search was run"),
    ("attributable", "run record is attributable and the price basis is declared"),
    ("has_bot", "a paired C# bot exists in the canonical location"),
    ("rule_parity", "shared-core rules agree between C# and Python"),
    ("nt8_ground_truth", "an NT8 trade list was captured for this run"),
    ("trade_set_parity", "trade-set parity meets its stated recall and precision"),
    ("prop_viability", "prop-firm viability evaluated by PropFirmSimulator only (ADR-021)"),
    ("reports_attributed", "every report names its inputs (section 7.3)"),
)


@dataclass
class Criterion:
    key: str
    text: str
    status: str = NOT_EVALUATED
    detail: str = ""


@dataclass
class Checklist:
    items: Dict[str, Criterion] = field(default_factory=dict)

    def __post_init__(self):
        for key, text in CRITERIA:
            self.items[key] = Criterion(key, text)

    def set(self, key: str, status: str, detail: str = "") -> None:
        if key not in self.items:
            raise KeyError("unknown promotion criterion: {}".format(key))
        if status not in (PASS, FAIL, NOT_EVALUATED):
            raise ValueError("bad status: {}".format(status))
        self.items[key] = Criterion(key, self.items[key].text, status, detail)

    @property
    def failed(self) -> List[Criterion]:
        return [c for c in self.items.values() if c.status == FAIL]

    @property
    def unevaluated(self) -> List[Criterion]:
        return [c for c in self.items.values() if c.status == NOT_EVALUATED]

    @property
    def validated(self) -> bool:
        """Every criterion must PASS. NOT EVALUATED is not a pass.

        Stated as `all(... == PASS)` rather than `not failed`, deliberately: with
        the latter, a workflow that evaluated NOTHING would report validated, and
        a green with no reachable red is the shape of defect this repo keeps
        finding.
        """
        return all(c.status == PASS for c in self.items.values())

    def render(self) -> str:
        mark = {PASS: "[PASS]", FAIL: "[FAIL]", NOT_EVALUATED: "[ -- ]"}
        lines = ["", "=" * 78, "PROMOTION CHECKLIST  (STRATEGY_WORKFLOW.md section 9)", "=" * 78]
        for c in self.items.values():
            lines.append("  {} {:<18} {}".format(mark[c.status], c.key, c.text))
            if c.detail:
                lines.append("           {}".format(c.detail))
        lines.append("-" * 78)
        if self.validated:
            lines.append("  VERDICT: validated -- every criterion passed.")
        elif self.failed:
            lines.append("  VERDICT: NOT validated -- {} criterion(a) FAILED.".format(len(self.failed)))
        else:
            lines.append("  VERDICT: NOT validated -- {} criterion(a) were never "
                         "evaluated. Nothing failed; nothing proved it either."
                         .format(len(self.unevaluated)))
        lines.append("=" * 78)
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validated": self.validated,
            "criteria": {k: {"status": c.status, "detail": c.detail, "text": c.text}
                         for k, c in self.items.items()},
        }


# --------------------------------------------------------------------------- #
# Stages
# --------------------------------------------------------------------------- #
@dataclass
class Ctx:
    """Everything a stage may read or write. Explicit so a stage cannot quietly
    depend on module state that another stage happened to set."""
    args: Any
    rec: RunRecord
    output_dir: str
    check: Checklist
    record: Optional[Dict[str, Any]] = None      # the python-research record view
    py_trades: Any = None                        # per-leg python trades
    nt8_trades: Any = None                       # per-leg NT8 trades
    bot_path: Optional[str] = None
    nt8_tz: Optional[str] = None
    notes: Dict[str, Any] = field(default_factory=dict)


def stage_resolve(ctx: Ctx) -> None:
    """Registry lookup + locate the paired C# bot.

    A Python-only strategy is a research artifact, not a strategy (section 1), so
    the absence of a bot is a real checklist failure rather than a warning.
    """
    from scripts.trading_framework.strategies.registry import STRATEGY_FACTORY_REGISTRY

    key = ctx.args.strategy
    if key not in STRATEGY_FACTORY_REGISTRY:
        ctx.check.set("registered", FAIL,
                      "'{}' is not in STRATEGY_FACTORY_REGISTRY".format(key))
        raise KeyError(
            "strategy '{}' is not registered. Known: {}".format(
                key, ", ".join(sorted(STRATEGY_FACTORY_REGISTRY))))
    ctx.check.set("registered", PASS, "registry key '{}'".format(key))

    bot = _find_bot(key, ctx.args.bot)
    ctx.bot_path = bot
    if bot:
        ctx.check.set("has_bot", PASS, os.path.relpath(bot, PROJECT_ROOT))
    else:
        ctx.check.set("has_bot", FAIL,
                      "no C# bot found for '{}' under scripts/ninjatrader/strategies/. "
                      "Pass --bot <ClassName> if the pairing is not name-derivable."
                      .format(key))
    ctx.rec.note("csharpBot", bot or None)


#: Pairings that name derivation cannot reach. Kept small on purpose -- a long
#: table here means the naming convention (section 1.1) is not being followed.
BOT_ALIASES = {
    "mean_reversion": ["BBMRReversionBot"],
    "ema_pullback": ["EMAPullBackBot"],
    "vwap_reclaim": ["VWAPReclaimBot"],
    "failed_auction": ["FailedAuctionBot"],
    "ib_pullback": ["IBRetestBot", "IBBreakoutBot", "IBFadeBot"],
    "ifvg_cisd": ["ICTFVGCISDBot"],
}


def _find_bot(key: str, override: Optional[str]) -> Optional[str]:
    root = os.path.join(PROJECT_ROOT, "scripts", "ninjatrader", "strategies")
    if not os.path.isdir(root):
        return None
    candidates = [override] if override else BOT_ALIASES.get(key, [])
    if not candidates:
        # derive PascalCase + "Bot" from the snake_case key
        candidates = ["".join(p.capitalize() for p in key.split("_")) + "Bot"]
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if not f.endswith(".cs"):
                continue
            if os.path.splitext(f)[0] in candidates:
                return os.path.join(dirpath, f)
    return None


def stage_python_research(ctx: Ctx) -> None:
    """Data, split, gates, optimisation, backtest, prop-firm sim, reports.

    Delegates to `run_backtest.run_research_pipeline` under THIS run record
    rather than reimplementing it -- a second copy of the pipeline is the defect
    this module exists to remove.
    """
    from scripts.trading_framework.run_backtest import run_research_pipeline

    ctx.record = run_research_pipeline(ctx.args, rec=ctx.rec, output_dir=ctx.output_dir)

    doc = ctx.rec.doc
    stages = {s.get("name"): s for s in doc.get("stages", [])}

    _signal_geometry(ctx, doc)

    # The grid precheck only runs inside the optimiser -- with fixed parameters
    # there is no search whose grid could be dead, so saying "did not run" would
    # read as a gap rather than as not applicable.
    if getattr(ctx.args, "optimize", False):
        _from_stage(ctx, stages, "grid_precheck", "grid_live")
    else:
        ctx.check.set("grid_live", NOT_EVALUATED,
                      "no search was run; the grid precheck applies to --optimize")
    _causality(ctx, stages)
    _out_of_sample(ctx)
    _prop_viability(ctx, stages)

    # §7.3 IS NOT BUILT, AND THAT IS WHAT THIS REPORTS.
    # The reporters are handed live objects and write whatever they are given;
    # nothing makes a report state which run record, price basis or date range
    # produced it. Until that is wired this criterion can only be NOT
    # EVALUATED -- which blocks `validated`, correctly, and is why §9 says no
    # strategy in this repository is validated today.
    ctx.check.set("reports_attributed", NOT_EVALUATED,
                  "section 7.3 not built: reports are generated from live objects, "
                  "not from the run record, so none of them names its inputs")


def _signal_geometry(ctx: "Ctx", doc: Dict[str, Any]) -> None:
    """Did any signal reach the engine with an impossible stop/target?

    THE READ LEVEL MATTERS. The geometry report is NESTED inside the alignment
    report, and the alignment report's own `signals_in` is the count AFTER
    geometry filtering. Read one level too high and a run in which the engine
    refused 527 of 3188 signals reports "2661 signals, none refused" -- which is
    what this printed on its first real run, on the very strategy whose
    wrong-sided stops started this whole effort.
    """
    align = _find_alignment(doc)
    if align is None:
        ctx.check.set("signal_geometry", NOT_EVALUATED,
                      "no signal_alignment was recorded by any stage")
        return

    geom = align.get("geometry")
    if not isinstance(geom, dict):
        ctx.check.set("signal_geometry", NOT_EVALUATED,
                      "alignment carried no geometry report; the engine predates "
                      "validate_signal_geometry")
        return

    drops = {k: int(geom.get(k, 0) or 0) for k in _GEOMETRY_DROPS}
    dropped = sum(drops.values())
    kept = int(geom.get("signals_kept", 0) or 0)
    n_in = int(geom.get("signals_in", 0) or 0)
    if kept == 0:
        ctx.check.set("signal_geometry", FAIL,
                      "no signals survived the geometry check ({} in)".format(n_in))
    elif dropped:
        ctx.check.set("signal_geometry", FAIL,
                      "{} of {} signal(s) refused: {}".format(
                          dropped, n_in,
                          ", ".join("{}={}".format(k.replace("dropped_", ""), v)
                                    for k, v in drops.items() if v)))
    else:
        ctx.check.set("signal_geometry", PASS, "{} signals, none refused".format(kept))


def _prop_viability(ctx: "Ctx", stages: Dict[str, Any]) -> None:
    """Did PropFirmSimulator -- and only it -- judge this survivable? (ADR-021)

    Read from the run record rather than from the result object on purpose: the
    criterion is about what the RUN did, and a number lifted off a live object
    cannot be attributed to a run afterwards.
    """
    st = stages.get("prop_firm_sim")
    if st is None:
        ctx.check.set("prop_viability", NOT_EVALUATED,
                      "the research stage recorded no prop_firm_sim stage")
        return
    # `_Stage.to_dict()` serialises `self.details` under the key "detail".
    # Reading "details" here returned {} on every real run, so the evaluator
    # check saw None and reported FAIL "evaluated by 'None'" -- accusing the
    # run of using an evaluator ADR-021 froze, on a run that had used the
    # right one. The two readers below this in the same file already had it
    # right; I did not look at them.
    d = st.get("detail") or {}
    if st.get("status") == "skipped":
        ctx.check.set("prop_viability", NOT_EVALUATED,
                      d.get("reason", "prop_firm_sim was skipped"))
        return
    if d.get("evaluator") != "PropFirmSimulator":
        # ADR-021 froze prop_eval_mc.py, 06_prop_sim.py and simulate_prop_pass.py.
        ctx.check.set("prop_viability", FAIL,
                      "evaluated by '{}', not PropFirmSimulator (ADR-021)".format(
                          d.get("evaluator")))
        return
    rate = d.get("passRatePct")
    if rate is None:
        ctx.check.set("prop_viability", NOT_EVALUATED,
                      d.get("skippedReason") or "no pass rate was computed")
        return
    thresh = float(d.get("passThresholdPct") or 65.0)
    detail = "{} pass rate {:.1f}% (grade {}), threshold {:.0f}%".format(
        d.get("primaryProfile"), rate, d.get("grade"), thresh)
    ctx.check.set("prop_viability", PASS if rate >= thresh else FAIL, detail)


def _out_of_sample(ctx: "Ctx") -> None:
    if getattr(ctx.args, "optimize", False):
        oos = getattr(ctx.args, "oos_start", None)
        ctx.check.set("out_of_sample", PASS if oos else FAIL,
                      "search before {}, report after".format(oos) if oos
                      else "optimised without --oos-start")
    else:
        ctx.check.set("out_of_sample", PASS, "no search was run; fixed parameters")


def _find_alignment(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The alignment report, wherever the record put it.

    `record_alignment` files it under `alignment[<stage>]`; older metrics dicts
    carried it in a stage detail. Looked for in one place only, this returned
    None on a healthy run and reported the geometry criterion as NOT EVALUATED
    while the engine had in fact refused 527 signals -- an unevaluated criterion
    standing in for a failed one.
    """
    align = doc.get("alignment") or {}
    if isinstance(align, dict):
        for stage in ("backtest", "generate_signals", "backtest_engine"):
            if isinstance(align.get(stage), dict):
                return align[stage]
        for value in align.values():
            # `geometry` alone is enough: an engine can report the geometry check
            # without the outer snap counters, and requiring `signals_kept` at
            # the OUTER level made this return None for exactly that shape --
            # caught by the clean-report negative control, not by a real run.
            if isinstance(value, dict) and ("signals_kept" in value or "geometry" in value):
                return value
    for s in doc.get("stages", []):
        d = s.get("detail") or {}
        if isinstance(d, dict) and "signals_kept" in d:
            return d
    return None


#: The geometry gate counts each drop against the FIRST rule it broke, so these
#: sum to the drop total without double counting.
_GEOMETRY_DROPS = ("dropped_stop_wrong_side", "dropped_target_wrong_side",
                   "dropped_stop_sub_tick", "dropped_non_finite")


def _from_stage(ctx: Ctx, stages: Dict[str, Any], stage_name: str, key: str) -> None:
    st = stages.get(stage_name)
    if st is None:
        ctx.check.set(key, NOT_EVALUATED, "stage '{}' did not run".format(stage_name))
        return
    status = st.get("status")
    if status in ("ok", "complete", "passed"):
        ctx.check.set(key, PASS, stage_name)
    elif status == "skipped":
        ctx.check.set(key, NOT_EVALUATED,
                      "stage '{}' skipped: {}".format(stage_name, st.get("reason", "no reason given")))
    else:
        ctx.check.set(key, FAIL, "stage '{}' -> {}".format(stage_name, status))


def _causality(ctx: Ctx, stages: Dict[str, Any]) -> None:
    """A vacuous probe is NOT a pass.

    The probe once reported `causal=True` for a strategy that emitted zero
    signals before the cutoff -- `empty == empty`. It reports `vacuous` now, and
    this is the reader that must not launder that back into a green.
    """
    st = stages.get("causality_probe")
    if st is None:
        ctx.check.set("causal", NOT_EVALUATED, "probe did not run")
        return
    detail = st.get("detail") or {}
    if detail.get("vacuous"):
        ctx.check.set("causal", NOT_EVALUATED,
                      "probe was vacuous: no signals before the cutoff to compare")
        return
    causal = detail.get("causal")
    if causal is None:
        ctx.check.set("causal", NOT_EVALUATED, "probe returned no verdict")
    else:
        ctx.check.set("causal", PASS if causal else FAIL, "causal={}".format(causal))


def stage_rule_parity(ctx: Ctx) -> None:
    """Layer 1 -- the shared core must mean the same thing in both languages."""
    if ctx.args.skip_rule_parity:
        ctx.check.set("rule_parity", NOT_EVALUATED, "--skip-rule-parity")
        ctx.rec.skip_stage("rule_parity", "--skip-rule-parity was passed")
        return

    families = _shared_core_families(ctx.args.strategy)
    if not families:
        ctx.check.set("rule_parity", NOT_EVALUATED,
                      "'{}' uses no shared C#/Python core, so there is no rule-level "
                      "comparison to make. It is covered only at the trade-set layer."
                      .format(ctx.args.strategy))
        return

    from scripts.parity import strat_core_parity as scp
    import tempfile

    cases = (scp.classify_cases() + scp.wick_cases() + scp.target_cases()
             + scp.entry_cases() + scp.ftfc_cases())
    tmp = tempfile.mkdtemp(prefix="wf_stratcore_")
    cases_csv, out_csv = os.path.join(tmp, "cases.csv"), os.path.join(tmp, "cs.csv")
    scp.write_cases(cases_csv, cases)
    try:
        scp.run_csharp(cases_csv, out_csv)
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        ctx.check.set("rule_parity", NOT_EVALUATED,
                      "StratCoreHarness unavailable (needs the dotnet SDK): {}".format(exc))
        return

    py = {c["id"]: scp.python_result(c) for c in cases}
    rows = scp.compare(cases, py, scp.read_results(out_csv))
    bad = [r for r in rows if not r["agree"]]
    ctx.notes["rule_parity"] = {"cases": len(rows), "divergent": len(bad)}
    if bad:
        ctx.check.set("rule_parity", FAIL,
                      "{} of {} cases diverge (functions: {})".format(
                          len(bad), len(rows), sorted({r["fn"] for r in bad})))
    else:
        ctx.check.set("rule_parity", PASS, "{} cases, zero divergence".format(len(rows)))


def _shared_core_families(key: str) -> List[str]:
    if key.startswith("strat") or key in ("the_strat",):
        return ["stratcore"]
    return []


def stage_nt8(ctx: Ctx) -> None:
    """Capture the authoritative trade set.

    Not attempted unless asked for: it needs a running NT8 with the bridge, and a
    recompile resets every static singleton in a live instance. Whether that is
    acceptable right now is the operator's call, not a step a runner should take
    on its own.
    """
    if not ctx.args.nt8:
        ctx.check.set("nt8_ground_truth", NOT_EVALUATED,
                      "--nt8 not passed; no NT8 run was attempted")
        ctx.check.set("trade_set_parity", NOT_EVALUATED,
                      "no NT8 trade set to compare against")
        ctx.rec.skip_stage("nt8_backtest", "--nt8 not passed")
        ctx.rec.skip_stage("trade_set_parity", "no NT8 trade set")
        return

    fixture = ctx.args.nt8_trades
    if not fixture:
        ctx.check.set("nt8_ground_truth", NOT_EVALUATED,
                      "--nt8 was passed without --nt8-trades. Live capture through "
                      "the MCP bridge is not driven from this process; export the "
                      "trade list with nt_backtest + nt_extract_trades and pass the "
                      "CSV. See STRATEGY_WORKFLOW.md section 5.")
        ctx.check.set("trade_set_parity", NOT_EVALUATED, "no NT8 trade set")
        return

    import pandas as pd
    if not os.path.exists(fixture):
        ctx.check.set("nt8_ground_truth", FAIL, "no such file: {}".format(fixture))
        ctx.check.set("trade_set_parity", NOT_EVALUATED, "no NT8 trade set")
        return

    ctx.nt8_trades = pd.read_csv(fixture)
    ctx.rec.note("nt8TradesFixture", fixture)

    # The timezone is DECLARED, never guessed. NT8's Strategy Analyzer exports
    # ET-naive timestamps; read as UTC they shift every trade by 4-5 hours, which
    # moves it to a different entry bar and destroys the join silently. A fixture
    # carries its own `.meta.json` stating the zone -- prefer that over a flag
    # the operator has to remember, and refuse when neither exists.
    meta_path = os.path.splitext(fixture)[0] + ".meta.json"
    tz = ctx.args.nt8_tz
    source = "--nt8-tz"
    if tz is None and os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        if meta.get("timestampsAreNaive") and meta.get("timestampZone"):
            tz, source = meta["timestampZone"], os.path.basename(meta_path)
        ctx.rec.note("nt8FixtureMeta", {k: meta.get(k) for k in
                                        ("strategy", "instrument", "from", "to",
                                         "barSeconds", "effectiveGlobals",
                                         "profileHash")})
        # SAME RULE AS THE TIMEZONE: the fixture knows, so ask it.
        # This defaulted to 300 and only WARNED on a disagreement. The
        # entry-bar join key is computed from it, so a 5-minute default against
        # a 1-minute capture mis-buckets every trade and the run still reports a
        # parity verdict -- a red that means "wrong join", indistinguishable
        # from "different trades".
        if meta.get("barSeconds"):
            declared = int(meta["barSeconds"])
            if ctx.args.bar_seconds is None:
                ctx.args.bar_seconds = declared
            elif int(ctx.args.bar_seconds) != declared:
                raise ValueError(
                    "--bar-seconds {} contradicts the fixture's own barSeconds "
                    "{}. The entry-bar join key is computed from it, so one of "
                    "these mis-buckets every trade. Fix the flag or the capture; "
                    "the run will not guess which is right.".format(
                        ctx.args.bar_seconds, declared))
    if ctx.args.bar_seconds is None:
        raise ValueError(
            "--bar-seconds is required with --nt8 and the fixture's .meta.json "
            "does not declare barSeconds. It is the entry-bar join key; there is "
            "no honest default, for the same reason --nt8-tz has none.")
    ctx.nt8_tz = tz
    ctx.check.set("nt8_ground_truth", PASS,
                  "{} NT8 rows from {} (tz {} via {}, {}s bars)".format(
                      len(ctx.nt8_trades), os.path.basename(fixture),
                      tz or "declared-aware", source, ctx.args.bar_seconds))


def stage_trade_set_parity(ctx: Ctx) -> None:
    """Layer 3 -- do the two implementations take the SAME trades?"""
    if ctx.nt8_trades is None:
        return   # already recorded NOT EVALUATED with its reason in stage_nt8

    from scripts.parity.legs import explode_legs
    from scripts.parity import trade_set_parity as tsp

    py_raw = _python_trades(ctx)
    if py_raw is None or py_raw.empty:
        ctx.check.set("trade_set_parity", FAIL,
                      "the Python side produced no trades to compare")
        return

    # NT8 counts each leg of a queen/runner bracket as its own trade, so Python
    # is projected onto NT8's convention -- never the reverse (see legs.py).
    try:
        py_trades = explode_legs(py_raw)
        ctx.notes["leg_convention"] = "python exploded to per-leg rows"
    except KeyError as exc:
        py_trades = py_raw
        ctx.notes["leg_convention"] = "NOT applied: {}".format(exc)
        ctx.rec.warn("per-leg projection unavailable, comparing whole trades against "
                     "NT8's per-leg rows -- recall will understate: {}".format(exc))

    result = tsp.run_parity(
        py_trades, ctx.nt8_trades,
        bar_seconds=ctx.args.bar_seconds,
        min_recall=ctx.args.min_recall,
        min_precision=ctx.args.min_precision,
        assume_tz_python=ctx.args.python_tz,
        assume_tz_nt8=ctx.nt8_tz,
    )
    report = tsp.format_report(result)
    path = os.path.join(ctx.output_dir, "trade_set_parity.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report)
    ctx.rec.add_artifact("tradeSetParity", path)
    print(report)

    v = result.get("verdict", {})
    call = v.get("verdict")
    reasons = "; ".join(v.get("reasons", []))
    if call == "VACUOUS":
        # An empty set matches an empty set. That is untested, not proven, and it
        # must not reach the checklist as a pass.
        ctx.check.set("trade_set_parity", NOT_EVALUATED, reasons)
    elif call == "PASS":
        ctx.check.set("trade_set_parity", PASS,
                      "recall {} / precision {}".format(
                          result["summary"].get("recall"),
                          result["summary"].get("precision")))
    elif call == "FAIL":
        ctx.check.set("trade_set_parity", FAIL, reasons)
    else:
        ctx.check.set("trade_set_parity", NOT_EVALUATED,
                      "parity returned an unrecognised verdict: {!r}".format(call))


def _python_trades(ctx: Ctx):
    doc = ctx.rec.doc
    for key in ("pythonTrades", "tradesDetailed"):
        p = (doc.get("artifacts") or {}).get(key)
        if p and os.path.exists(p):
            import pandas as pd
            return pd.read_csv(p)
    return ctx.py_trades


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
ORDERED_STAGES: List[tuple] = [
    ("resolve", stage_resolve, True),
    ("python_research", stage_python_research, True),
    ("rule_parity", stage_rule_parity, False),
    ("nt8_backtest", stage_nt8, False),
    ("trade_set_parity", stage_trade_set_parity, False),
]


def run_workflow(args) -> int:
    run_id = RunRecord.new_run_id(args.ticker, args.strategy)
    output_dir = os.path.join(PROJECT_ROOT, "results", "RESEARCH", "_workflow",
                              args.ticker, run_id)
    os.makedirs(output_dir, exist_ok=True)

    rec = RunRecord.open(run_id, strategy_key=args.strategy, ticker=args.ticker)
    rec.note("entryPoint", "scripts.trading_framework.workflow")
    ctx = Ctx(args=args, rec=rec, output_dir=output_dir, check=Checklist())

    print("=" * 78)
    print("STRATEGY WORKFLOW  {}  /  {}".format(args.strategy, args.ticker))
    print("run id     : {}".format(run_id))
    print("output dir : {}".format(os.path.relpath(output_dir, PROJECT_ROOT)))
    print("=" * 78)

    failed_hard = None
    for name, fn, required in ORDERED_STAGES:
        print("\n--- stage: {} ---".format(name))
        try:
            fn(ctx)
        except BaseException as exc:            # noqa: BLE001 - recorded, then re-raised or carried
            rec.refuse("stage '{}' raised {}: {}".format(name, type(exc).__name__, exc))
            traceback.print_exc()
            if required:
                failed_hard = exc
                break
            print("[!] stage '{}' failed but is not required; continuing.".format(name))

    # THE CRITERION SAYS "and the price basis is declared". It did not check.
    # `--price-adjustment` DOES have a default -- `undeclared` -- which records
    # honestly and warns, but `attribution()` counts only missing fields and
    # refusals, so a run with an undeclared basis passed this criterion while
    # carrying a warning that it "cannot be compared to an NT8 run". The whole
    # point of the flag is that a back-adjusted series and an unadjusted one
    # produce different trades; a run that cannot say which it used is not
    # attributable in the sense §9 means.
    att = rec.attribution()
    basis = ((rec.doc.get("data") or {}).get("adjustment")) or UNDECLARED
    missing = list(att.get("missingRequired", []))
    if basis == UNDECLARED:
        missing.append("data.adjustment (--price-adjustment not declared)")
    ctx.check.set("attributable",
                  PASS if (att["attributable"] and basis != UNDECLARED) else FAIL,
                  "; ".join(missing) or "basis {}".format(basis))

    rec.note("promotionChecklist", ctx.check.to_dict())
    record = rec.finalize(output_dir, status="failed" if failed_hard else "complete")

    print(ctx.check.render())
    print("\nrun record : {}".format(os.path.join(
        os.path.relpath(output_dir, PROJECT_ROOT), "run_record.json")))
    print("attributable: {}  warnings: {}  refusals: {}".format(
        record["attributable"], len(record["warnings"]), len(record["refusals"])))
    for r in record["refusals"]:
        print("   refusal: {}".format(r))

    with open(os.path.join(output_dir, "checklist.json"), "w", encoding="utf-8") as fh:
        json.dump(ctx.check.to_dict(), fh, indent=2)

    return exit_code(ctx.check, failed_hard)


def exit_code(check: "Checklist", failed_hard: Optional[str] = None) -> int:
    """Map a finished run onto a process exit code.

    EXIT 0 MEANS VALIDATED, NOT "NOTHING FAILED".

    This was written inline as `1 if check.failed else 0` -- the exact
    `not failed` semantics that `Checklist.validated` exists to reject and that
    §0.1 promises the workflow does not use. A run in which every criterion was
    NOT EVALUATED printed "NOT validated" and exited **0**, so the CI gate §11.1
    plans would have scored a run that measured nothing as a pass. A status with
    no reachable red is the defect this module was written to remove, and it was
    in this module.

    It lives here as a function, not inline in `main`, so that the mapping is
    callable by a test. Asserting it by reading the source would prove the text
    and not the behaviour.

        2  a required stage raised -- the run is inconclusive, not failed
        1  not validated: something FAILED, or something was never measured
        0  every criterion PASSED

    Note there is deliberately no code for "nothing failed but not everything
    was measured". That state is `1`, because it is not a pass.
    """
    if failed_hard is not None:
        return 2
    return 0 if check.validated else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m scripts.trading_framework.workflow",
        description="The single sanctioned strategy workflow. See "
                    "docs/architecture/STRATEGY_WORKFLOW.md.")
    p.add_argument("--strategy", required=True, help="registry key")
    p.add_argument("--ticker", default="NQ1")
    p.add_argument("--config", default="scripts/trading_framework/config/sessions.yaml")
    p.add_argument("--engine", default="nt8_parity", choices=["nt8_parity", "vectorized"],
                   help="nt8_parity models brackets and legs; use it for anything "
                        "that will be compared to NT8")
    p.add_argument("--optimize", action="store_true")
    p.add_argument("--trials", type=int, default=20)
    p.add_argument("--oos-start", default=None,
                   help="REQUIRED with --optimize: the search sees only earlier bars")
    p.add_argument("--price-adjustment", default=UNDECLARED,
                   choices=[UNDECLARED, "unadjusted", "back_adjusted", "ratio_adjusted"],
                   help="no honest default; an undeclared basis is recorded as such")
    p.add_argument("--allow-unattributable", action="store_true")

    p.add_argument("--bot", default=None,
                   help="C# bot class name, when it is not derivable from the key")
    p.add_argument("--skip-rule-parity", action="store_true",
                   help="recorded as a SKIP with its reason, never as a pass")

    p.add_argument("--nt8", action="store_true",
                   help="include the NT8 validation and trade-set parity stages")
    p.add_argument("--nt8-trades", default=None,
                   help="NT8 trade list CSV (nt_extract_trades output)")
    p.add_argument("--nt8-tz", default=None,
                   help="timezone of NAIVE timestamps in the NT8 CSV (e.g. "
                        "America/New_York). Read from the fixture's .meta.json "
                        "when present; there is no default, because reading "
                        "ET-naive exports as UTC shifts every trade by 4-5 hours "
                        "and silently destroys the entry-bar join.")
    p.add_argument("--python-tz", default=None,
                   help="same, for the Python trade list")
    p.add_argument("--bar-seconds", type=int, default=None,
                   help="bar size of the compared run, for the entry-bar join key")
    p.add_argument("--min-recall", type=float, default=0.95)
    p.add_argument("--min-precision", type=float, default=0.95)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.optimize and not args.oos_start:
        build_parser().error(
            "--optimize without --oos-start would report the SAME bars the search "
            "selected on, which is an in-sample result. Pass --oos-start YYYY-MM-DD.")
    return run_workflow(args)


if __name__ == "__main__":
    sys.exit(main())
