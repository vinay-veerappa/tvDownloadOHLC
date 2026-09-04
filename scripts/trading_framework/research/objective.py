r"""The single cross-validation objective, and a precheck that the search space
is actually connected to the strategy.

WHY ONE MODULE. This framing logic existed twice -- in
`ResearchLifecycleRunner._optimize_params` and in `run_backtest.run_optimization`
-- and both copies had the same defect: signals generated on a train fold and
scored against a test fold, which `Index.get_indexer(..., method='bfill')`
silently absorbs by snapping every out-of-range timestamp onto bar 0 of the test
frame. Fixing one copy leaves the other. There is one copy now.

THE GRID PRECHECK is here because of a second, worse defect found in the same
place. `run_optimization` hardcoded BoxReversion's parameter space --
`min_dist`, `sl_dist`, `tp_buffer`, `filter_high_vol` -- regardless of which
strategy `--strategy` selected. Every other strategy ignores those keys and
falls back to its own defaults, so measured 2026-09-04 on 353k bars of 2023 NQ1,
three widely separated points in that space produced BYTE-IDENTICAL signal
frames for mean_reversion (310 signals), ema_pullback (257) and ib_pullback
(171). The optimizer ran its full trial budget over a space that could not
change the answer, then printed "Best IS Parameters" and "Estimated CV Sharpe".

A search whose parameters cannot move the output is not a weak search; it is a
random draw wearing the costume of one. So before any trial budget is spent,
`assert_grid_is_live` evaluates the strategy at the corners of its OWN grid and
requires the resulting signal frames to actually differ. It compares the WHOLE
frame, not just signal times, because a legitimate exit-only parameter
(`sl_atr_mult`, `tp_r_mult`) changes stop and target prices while leaving entry
timing untouched -- checking timestamps alone would refuse a perfectly good grid.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np
import optuna
import pandas as pd

from scripts.trading_framework.ml.walk_forward import sequential_evaluation_folds

# Must match VectorizedBacktester's MAX_SEARCH, or the buffer reserved per fold
# does not cover the forward search the engine actually performs.
EXIT_BUFFER_BARS = 1440
EMBARGO_BARS = 1440

# Score for a fold that produced nothing. Deliberately NOT 0.0: `_null_metrics`
# returns sharpe 0.0, which is better than any real loss, so scoring an empty
# fold as-is rewards parameter sets that stop trading. Measured 2026-09-04 on
# mean_reversion: an empty fold scored 0.0000 and outranked a trading fold at
# -0.0222 inside the same objective.
EMPTY_FOLD_SCORE = -1.0

# Bars used by the grid precheck. Bounded because the check runs before the
# search and its only job is to detect insensitivity, not to measure anything.
PRECHECK_BARS = 200_000


def suggest_from_grid(trial: "optuna.Trial", key: str, spec: Any) -> Any:
    """Map an ADR-017 param-grid spec onto an Optuna suggestion.

    Raises on a spec it does not understand rather than guessing a distribution:
    a silently misread spec searches the wrong space and still returns a "best".
    """
    # A tuple naming a known kind is handled HERE and never falls through. The
    # length check used to be `>= 2`, so a truncated `('int',)` skipped this
    # branch entirely and was read by the list branch below as a categorical
    # with the single choice "int" -- a malformed spec silently searching a
    # one-point space, which is the failure this function exists to refuse.
    if isinstance(spec, tuple) and len(spec) >= 1 and spec[0] in ("int", "float",
                                                                  "categorical"):
        kind = spec[0]
        if kind == "int":
            if len(spec) < 3:
                raise ValueError(f"int spec for '{key}' must be ('int', low, high)")
            return trial.suggest_int(key, int(spec[1]), int(spec[2]))
        if kind == "float":
            if len(spec) < 3:
                raise ValueError(f"float spec for '{key}' must be ('float', low, high)")
            return trial.suggest_float(key, float(spec[1]), float(spec[2]))
        if len(spec) < 2:
            raise ValueError(
                f"categorical spec for '{key}' must be ('categorical', choices)")
        choices = spec[1]
        if not isinstance(choices, (list, tuple)):
            raise ValueError(
                f"categorical spec for '{key}' must provide list/tuple choices")
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


def grid_corners(grid: Dict[str, Any]) -> List[Dict[str, Any]]:
    """A few concrete points spanning the grid, for the sensitivity precheck.

    Not a sweep -- three points is enough to prove a grid can move the output,
    and the check must be cheap enough that nobody is tempted to skip it.
    """
    low: Dict[str, Any] = {}
    high: Dict[str, Any] = {}
    mid: Dict[str, Any] = {}
    for k, spec in grid.items():
        if isinstance(spec, tuple) and len(spec) >= 3 and spec[0] == "int":
            low[k], high[k] = int(spec[1]), int(spec[2])
            mid[k] = int((int(spec[1]) + int(spec[2])) // 2)
        elif isinstance(spec, tuple) and len(spec) >= 3 and spec[0] == "float":
            low[k], high[k] = float(spec[1]), float(spec[2])
            mid[k] = (float(spec[1]) + float(spec[2])) / 2.0
        elif isinstance(spec, tuple) and len(spec) >= 2 and spec[0] == "categorical":
            ch = list(spec[1])
            low[k], high[k], mid[k] = ch[0], ch[-1], ch[len(ch) // 2]
        elif isinstance(spec, (list, tuple)) and len(spec) > 0:
            ch = list(spec)
            low[k], high[k], mid[k] = ch[0], ch[-1], ch[len(ch) // 2]
        else:
            low[k] = high[k] = mid[k] = spec
    return [low, mid, high]


def _frame_digest(signals: Optional[pd.DataFrame]) -> str:
    """Content digest of a signal frame, over the WHOLE frame.

    Entry timing alone is not enough: a legitimate exit-only parameter changes
    stop and target prices while leaving signal_time identical, and refusing
    such a grid would be a false positive.
    """
    if signals is None or len(signals) == 0:
        return "empty"
    cols = [c for c in ("signal_time", "direction", "entry_price",
                        "stop_price", "target1_price") if c in signals.columns]
    h = hashlib.sha256()
    h.update(str(len(signals)).encode())
    for c in cols:
        h.update(c.encode())
        h.update(signals[c].astype(str).str.cat(sep="|").encode("utf-8", "replace"))
    return h.hexdigest()


def probe_grid(strategy: Any, data: pd.DataFrame, grid: Dict[str, Any],
               precheck_bars: int = PRECHECK_BARS) -> Dict[str, Any]:
    """Measure whether the grid can change what the strategy emits. Never raises."""
    if not grid:
        return {"live": False, "reason": "strategy exposes an EMPTY parameter grid; "
                                         "there is nothing to search",
                "digests": [], "signalCounts": [], "barsProbed": 0}

    probe = data.iloc[-precheck_bars:] if len(data) > precheck_bars else data
    digests: List[str] = []
    counts: List[int] = []
    for params in grid_corners(grid):
        try:
            sig = strategy.generate_signals(probe, params)
        except Exception as exc:  # a corner that raises is itself a finding
            return {"live": False,
                    "reason": "strategy raised at a grid corner {}: {}: {}".format(
                        params, type(exc).__name__, exc),
                    "digests": digests, "signalCounts": counts,
                    "barsProbed": int(len(probe))}
        digests.append(_frame_digest(sig))
        counts.append(0 if sig is None else int(len(sig)))

    result = {
        "digests": digests,
        "signalCounts": counts,
        "barsProbed": int(len(probe)),
        "probeFirstBar": str(probe.index[0]) if len(probe) else None,
        "probeLastBar": str(probe.index[-1]) if len(probe) else None,
        "gridKeys": sorted(grid.keys()),
    }

    if all(c == 0 for c in counts):
        result["live"] = False
        result["reason"] = (
            "strategy emitted ZERO signals at every grid corner over {} bars "
            "({} -> {}); there is nothing to optimise".format(
                result["barsProbed"], result["probeFirstBar"], result["probeLastBar"]))
        return result

    if len(set(digests)) == 1:
        result["live"] = False
        result["reason"] = (
            "the parameter grid does NOT affect this strategy: {} grid corners "
            "produced byte-identical signal frames ({} signals each). The search "
            "space is disconnected from the strategy -- most likely the grid "
            "belongs to a different strategy, or the params are not threaded "
            "through generate_signals.".format(len(digests), counts[0]))
        return result

    result["live"] = True
    result["reason"] = "grid moves the signal frame ({} distinct outputs from {} corners)".format(
        len(set(digests)), len(digests))
    return result


def assert_grid_is_live(strategy: Any, data: pd.DataFrame, grid: Dict[str, Any],
                        precheck_bars: int = PRECHECK_BARS) -> Dict[str, Any]:
    """Refuse to spend a trial budget on a search that cannot change the answer."""
    probe = probe_grid(strategy, data, grid, precheck_bars)
    if not probe["live"]:
        raise ValueError("grid precheck FAILED: " + probe["reason"])
    return probe


def _causality_at_cutoff(strategy: Any, data: pd.DataFrame,
                         params: Dict[str, Any], m: int) -> Dict[str, Any]:
    """One cutoff: do bars after `m` change signals emitted before `m`?"""
    truncated = strategy.generate_signals(data.iloc[:m], params)
    full = strategy.generate_signals(data, params)
    cutoff = data.index[m - 1]

    def before(sig):
        if sig is None or len(sig) == 0:
            return sig
        return sig[pd.to_datetime(sig["signal_time"]) <= cutoff]

    a, b = before(truncated), before(full)
    na = 0 if a is None else len(a)
    nb = 0 if b is None else len(b)
    same = _frame_digest(a) == _frame_digest(b)

    return {
        "cutoffIndex": int(m),
        "cutoff": str(cutoff),
        "signalsBeforeCutoff_truncatedRun": int(na),
        "signalsBeforeCutoff_fullRun": int(nb),
        "identical": bool(same),
        "vacuous": bool(na == 0 and nb == 0),
    }


def probe_causality(strategy: Any, data: pd.DataFrame, params: Dict[str, Any],
                    split_fracs: Sequence[float] = (0.3, 0.5, 0.7)) -> Dict[str, Any]:
    """Does adding FUTURE bars change signals the strategy already emitted?

    Generating signals once over a whole frame and then scoring a later slice of
    it is only sound if the generator is causal. Nothing checked that, and the
    check is cheap: generate on `data.iloc[:m]` and on all of `data`, then
    compare only the signals whose signal_time falls before bar `m`. Those bars
    are identical in both runs, so any difference in what the strategy emitted
    there was caused by bars that had not happened yet.

    This is a stronger statement than a feature/future-return correlation --
    which is what `LeakageGuard.identify_future_leakage` measures, and which can
    only flag suspicion. A signal that CHANGES when the future is appended is
    lookahead, demonstrated rather than inferred.

    SENSITIVITY LIMIT, stated because it was found by a fixture that should have
    failed and did not. A cutoff can only expose a lookahead of horizon `h` if
    some signal sits within `h` bars BEFORE that cutoff -- otherwise every
    signal's future is already inside the truncated frame and the two runs agree.
    A strategy signalling every 300 bars with a 50-bar lookahead therefore passes
    a single cutoff roughly 5 times out of 6. Several cutoffs are used for that
    reason, and a PASS here is evidence, not proof: it means no lookahead was
    exposed at these cutoffs, which is why the result records the cutoffs it
    used rather than just a boolean.

    Never raises: an unrunnable probe is reported as `checked: False` with the
    reason, because a probe that throws would take down the run it was meant to
    qualify.
    """
    n = len(data)
    cutoffs = sorted({int(n * f) for f in split_fracs if 0.0 < f < 1.0})
    cutoffs = [m for m in cutoffs if 100 <= m < n]
    if not cutoffs:
        return {"checked": False, "causal": None, "vacuous": False,
                "reason": "frame too short to split for a causality probe "
                          "({} bars)".format(n)}

    per_cutoff = []
    for m in cutoffs:
        try:
            per_cutoff.append(_causality_at_cutoff(strategy, data, params, m))
        except Exception as exc:
            return {"checked": False, "causal": None, "vacuous": False,
                    "perCutoff": per_cutoff,
                    "reason": "strategy raised during the causality probe: {}: {}"
                              .format(type(exc).__name__, exc)}

    informative = [c for c in per_cutoff if not c["vacuous"]]
    out = {
        "checked": True,
        "barsFull": int(n),
        "cutoffsTried": cutoffs,
        "perCutoff": per_cutoff,
        "informativeCutoffs": len(informative),
    }

    # With no signals before ANY cutoff there is nothing that COULD have
    # changed, and "empty == empty" passes everywhere. That is a green with no
    # reachable red, so it is reported as vacuous rather than as a pass --
    # measured on six_am_reversal, which emitted 0 signals in the first half of
    # 2023 and therefore "proved" causality over an empty set.
    if not informative:
        out["causal"] = None
        out["vacuous"] = True
        out["reason"] = ("VACUOUS: the strategy emitted no signals before any of "
                         "the {} cutoffs, so nothing could have been changed by "
                         "future bars. Causality is UNTESTED here, not confirmed."
                         .format(len(cutoffs)))
        return out

    broken = [c for c in informative if not c["identical"]]
    out["vacuous"] = False
    if broken:
        c = broken[0]
        out["causal"] = False
        out["reason"] = (
            "LOOKAHEAD at {} of {} informative cutoff(s). At {} the signals "
            "before the cutoff changed when future bars were appended ({} -> {} "
            "signals). Signals the strategy emitted at a bar depend on bars "
            "after it.".format(len(broken), len(informative), c["cutoff"],
                               c["signalsBeforeCutoff_truncatedRun"],
                               c["signalsBeforeCutoff_fullRun"]))
    else:
        out["causal"] = True
        out["reason"] = (
            "no lookahead exposed at {} informative cutoff(s); appending future "
            "bars left every prior signal unchanged".format(len(informative)))
    return out


def evaluate_folds(strategy: Any, data: pd.DataFrame, params: Dict[str, Any],
                   engine: Any, ticker: str, folds: Sequence[Dict[str, Any]],
                   trial: Optional["optuna.Trial"] = None) -> List[float]:
    """Score one parameter set across pre-computed evaluation windows.

    The three framing rules, in one place:

      1. the generator sees history up to the END of the window and no further,
         so a signal inside the window cannot be informed by a bar after it;
      2. only signals raised INSIDE the window are that window's evidence --
         everything earlier belongs to a previous fold, and is exactly what used
         to be collapsed onto bar 0;
      3. scoring runs on a frame that BEGINS at the window (so each signal_time
         is an exact index member, not a snap) and extends past its end (so a
         late trade can still resolve). `strict_alignment=True` means a future
         divergence RAISES instead of returning a plausible number.
    """
    scores: List[float] = []
    for f in folds:
        gen_df = data.iloc[: f["gen_end"]]
        signals = strategy.generate_signals(gen_df, params)
        if signals is None or len(signals) == 0:
            scores.append(EMPTY_FOLD_SCORE)
            continue

        w_start = data.index[f["test_start"]]
        w_end = data.index[f["test_end"] - 1]
        st = pd.to_datetime(signals["signal_time"])
        in_window = signals[(st >= w_start) & (st <= w_end)]
        if in_window.empty:
            scores.append(EMPTY_FOLD_SCORE)
            continue

        score_df = data.iloc[f["score_start"]: f["score_end"]]
        metrics = engine.run(in_window, score_df, {
            "leverage": 1.0,
            "ticker": ticker,
            "strict_alignment": True,
        })

        if int(metrics.get("num_trades", 0)) == 0:
            scores.append(EMPTY_FOLD_SCORE)
        else:
            scores.append(float(metrics.get("sharpe_ratio", EMPTY_FOLD_SCORE)))

        if trial is not None:
            trial.report(scores[-1], f["fold"])
            if trial.should_prune():
                raise optuna.exceptions.TrialPruned()
    return scores


def build_folds(n_samples: int, n_splits: int = 3) -> List[Dict[str, Any]]:
    return sequential_evaluation_folds(
        n_samples, n_splits=n_splits,
        exit_buffer=EXIT_BUFFER_BARS, embargo=EMBARGO_BARS)


def make_cv_objective(strategy: Any, data: pd.DataFrame, engine: Any, ticker: str,
                      grid: Dict[str, Any],
                      folds: Sequence[Dict[str, Any]]) -> Callable:
    """An Optuna objective over the strategy's OWN grid, on fixed windows."""
    def objective(trial: "optuna.Trial") -> float:
        params = {k: suggest_from_grid(trial, k, spec) for k, spec in grid.items()}
        scores = evaluate_folds(strategy, data, params, engine, ticker, folds,
                                trial=trial)
        return float(np.mean(scores)) if scores else EMPTY_FOLD_SCORE

    return objective
