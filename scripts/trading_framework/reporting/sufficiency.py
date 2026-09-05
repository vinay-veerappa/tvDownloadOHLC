"""Is there enough evidence to call this an edge, or just enough to plot one?

STRATEGY_WORKFLOW.md section 8 has said "at least 120 trades per configuration
across at least 3 regimes" and "for a marginal PF of 0.8-1.2, bootstrap a
confidence interval on per-session returns; if it crosses zero there is no edge
to deploy" since it was written. NOTHING MEASURED EITHER. The `out_of_sample`
criterion checked that `--oos-start` was passed -- that a split EXISTS, not that
what landed on the far side of it is enough to conclude anything. A run that
took four out-of-sample trades and won three of them scored PASS.

WHAT THIS MODULE WILL NOT DO. It will not decide the strategy is good. It
answers a narrower question -- whether the sample can support a conclusion at
all -- and it answers it in a way that can come out NO on evidence that looks
excellent, which is the entire point. A 100% win rate over 6 trades fails here.

THREE MEASUREMENTS, and one of them is a judgment call:

  1. COUNT. Out-of-sample trades against `MIN_TRADES`. Mechanical.

  2. REGIME SPREAD. The document says "3 regimes" and this repository has no
     ONE regime definition -- it has three that disagree, and one of them
     (`*_bucket_full`) is computed with lookahead and is in live use. So the
     bucket here is the CALENDAR QUARTER (ET) of the entry, which is a PROXY
     and is declared as one in the output. It catches the case that actually
     recurs (all the evidence inside one three-month stretch of one kind of
     market) and it will not catch a year of uniformly quiet tape.

     THIS IS A PLACEHOLDER WITH AN OWNER: `docs/strategies/research_backlog/
     13_market_regime_definition.md` (item REG-1) is the research item that
     settles it, lists the seven candidates and the acceptance criteria, and
     names every consumer that switches over when it lands. Do not quietly
     replace the proxy here with a fourth definition.

  3. BOOTSTRAP CI on the mean per-trade P&L. Percentile bootstrap, resampling
     trades independently. That understates the interval when returns are
     serially dependent -- the same objection that applies to the prop-firm
     permutation -- so the interval here is a LOWER bound on the uncertainty,
     and a CI that crosses zero under an assumption favourable to the strategy
     is decisive in a way that one which excludes zero is not.

The breakeven win rate is computed alongside, because section 8's own example is
a bot whose 1:2 geometry needed 66.7% to break even and whose filters could
never have got there. That is geometry, not parameters, and it is cheaper to
read than to tune.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

#: Section 8. Not a statistical derivation -- a floor below which the other two
#: measurements are not worth making.
MIN_TRADES = 120

#: Section 8 again. The proxy is calendar quarters; see the module docstring.
MIN_REGIMES = 3

#: Percentile bootstrap. 10,000 is enough that the interval is stable to the
#: second decimal and cheap enough that nobody skips the check.
N_BOOTSTRAP = 10_000
CI_ALPHA = 0.05

#: Below this many trades the bootstrap is not reported at all. A percentile
#: interval from 8 resampled points is a number, not a measurement, and printing
#: one invites it to be quoted.
MIN_TRADES_FOR_BOOTSTRAP = 30

_PNL_KEYS = ("total_pnl_usd", "pnl", "pnl_usd", "net_pnl")
_TIME_KEYS = ("entry_time", "signal_time", "exit_time")


def _column(df: pd.DataFrame, keys) -> Optional[str]:
    for k in keys:
        if k in df.columns:
            return k
    return None


def bootstrap_mean_ci(pnl: np.ndarray, *, n: int = N_BOOTSTRAP,
                      alpha: float = CI_ALPHA, seed: int = 0) -> Dict[str, Any]:
    """Percentile bootstrap CI for the mean. Independent resampling, stated as such."""
    pnl = np.asarray(pnl, dtype=float)
    pnl = pnl[np.isfinite(pnl)]
    if pnl.size < MIN_TRADES_FOR_BOOTSTRAP:
        return {"ci": None, "reason": (
            "{} usable trades is below the {} needed for a bootstrap interval "
            "to mean anything".format(pnl.size, MIN_TRADES_FOR_BOOTSTRAP))}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, pnl.size, size=(n, pnl.size))
    means = pnl[idx].mean(axis=1)
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {
        "ci": (float(lo), float(hi)),
        "mean": float(pnl.mean()),
        "excludes_zero": bool(lo > 0 or hi < 0),
        "resampling": "independent per trade; understates the interval if "
                      "returns are serially dependent",
        "reason": "{:.0%} CI on mean per-trade P&L: [{:.2f}, {:.2f}]".format(
            1 - alpha, lo, hi),
    }


def breakeven_win_rate(trades: pd.DataFrame) -> Dict[str, Any]:
    """The win rate the GEOMETRY requires, against the one observed.

    Section 8's worked example: a 0.5x-range target against a 2.0x-range stop
    needs >66.7% just to break even, and at a measured 55.6% the profit factor
    cannot reach 1.0 however the filters are tuned.

    Computed from realised wins and losses rather than from declared stop and
    target distances, because the declared target does not reach the sanctioned
    engine at all (it substitutes queen/runner bps) -- so the realised figures
    are the ones describing the trades that actually happened.
    """
    col = _column(trades, _PNL_KEYS)
    if col is None:
        return {"reason": "no P&L column in {}".format(list(trades.columns)[:12])}
    pnl = pd.to_numeric(trades[col], errors="coerce").dropna()
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    if wins.empty or losses.empty:
        return {"reason": "the sample has {} wins and {} losses; a breakeven "
                          "rate needs both".format(len(wins), len(losses))}
    avg_win, avg_loss = float(wins.mean()), float(abs(losses.mean()))
    required = avg_loss / (avg_win + avg_loss)
    observed = float((pnl > 0).mean())
    return {
        "avg_win": avg_win, "avg_loss": avg_loss,
        "required_win_rate": required, "observed_win_rate": observed,
        "margin": observed - required,
        "reason": "geometry needs {:.1%} to break even; observed {:.1%}".format(
            required, observed),
    }


def regime_spread(trades: pd.DataFrame) -> Dict[str, Any]:
    """Calendar quarters spanned by the entries. A PROXY -- see the docstring."""
    col = _column(trades, _TIME_KEYS)
    if col is None:
        return {"n_regimes": None, "buckets": {},
                "reason": "no timestamp column in {}".format(
                    list(trades.columns)[:12])}
    ts = pd.to_datetime(trades[col], errors="coerce", utc=True).dropna()
    if ts.empty:
        return {"n_regimes": 0, "buckets": {},
                "reason": "column '{}' parsed to no usable timestamps".format(col)}
    # ET, NOT UTC (ADR-001). `to_period` drops the zone with a warning, so the
    # conversion is done explicitly first: a trade at 23:00 ET on 31 March is
    # 03:00 UTC on 1 April, and bucketing it in Q2 would put the last evening of
    # a quarter in the next one.
    q = ts.dt.tz_convert("America/New_York").dt.tz_localize(None) \
          .dt.to_period("Q").astype(str)
    counts = q.value_counts().sort_index()
    return {
        "n_regimes": int(counts.size),
        "buckets": {str(k): int(v) for k, v in counts.items()},
        "proxy": "calendar quarter (ET) of {}".format(col),
        "reason": "{} calendar quarter(s) spanned: {}".format(
            counts.size, ", ".join("{} n={}".format(k, v)
                                   for k, v in counts.items())),
    }


def assess(trades: Optional[pd.DataFrame], *, out_of_sample: bool,
           min_trades: int = MIN_TRADES,
           min_regimes: int = MIN_REGIMES) -> Dict[str, Any]:
    """The whole measurement. Returns `sufficient` plus every reason it is not.

    `out_of_sample` is not a threshold, it is a LABEL: in-sample trades cannot
    establish an edge however many of them there are, so a sufficient in-sample
    sample is still insufficient evidence and says so.
    """
    if trades is None or len(trades) == 0:
        return {"sufficient": False, "n_trades": 0, "reasons": [
            "no trades to assess; an empty sample is untested, not passed"]}

    n = int(len(trades))
    reasons = []
    out: Dict[str, Any] = {"n_trades": n, "outOfSample": bool(out_of_sample),
                           "minTrades": int(min_trades),
                           "minRegimes": int(min_regimes)}

    if not out_of_sample:
        reasons.append(
            "the reported trades are IN-SAMPLE; no number of them establishes "
            "an edge. Re-run with --oos-start.")

    if n < min_trades:
        reasons.append(
            "{} trades is below the {} section 8 requires per configuration"
            .format(n, min_trades))

    reg = regime_spread(trades)
    out["regimes"] = reg
    if reg["n_regimes"] is None:
        reasons.append("regime spread could not be measured: " + reg["reason"])
    elif reg["n_regimes"] < min_regimes:
        reasons.append(
            "{} of the {} regimes section 8 requires ({}). All the evidence "
            "comes from one stretch of market.".format(
                reg["n_regimes"], min_regimes, reg["reason"]))

    col = _column(trades, _PNL_KEYS)
    if col is None:
        reasons.append("no P&L column, so no confidence interval could be "
                       "computed on the mean")
    else:
        pnl = pd.to_numeric(trades[col], errors="coerce").to_numpy()
        ci = bootstrap_mean_ci(pnl)
        out["bootstrap"] = ci
        if ci["ci"] is None:
            reasons.append("no confidence interval: " + ci["reason"])
        elif not ci["excludes_zero"]:
            reasons.append(
                "the {} straddles zero, so the mean per-trade P&L is not "
                "distinguishable from no edge -- and that interval is a LOWER "
                "bound, since the resampling assumes independence."
                .format(ci["reason"]))

    out["breakeven"] = breakeven_win_rate(trades)
    out["sufficient"] = not reasons
    out["reasons"] = reasons
    return out


def render(a: Dict[str, Any]) -> str:
    """ASCII only -- the console this prints on is cp1252."""
    L = ["", "STATISTICAL SUFFICIENCY  (STRATEGY_WORKFLOW.md section 8)",
         "-" * 70]
    L.append("  trades              : {} (need {}{})".format(
        a.get("n_trades"), a.get("minTrades"),
        "" if a.get("outOfSample") else ", and these are IN-SAMPLE"))
    reg = a.get("regimes") or {}
    if reg:
        L.append("  regime spread       : {}".format(reg.get("reason")))
        if reg.get("proxy"):
            L.append("    (proxy: {} -- not a volatility regime)".format(reg["proxy"]))
    bs = a.get("bootstrap") or {}
    if bs:
        L.append("  mean per-trade P&L  : {}".format(bs.get("reason")))
        if bs.get("ci"):
            L.append("    excludes zero     : {}".format(bs.get("excludes_zero")))
            L.append("    caveat            : {}".format(bs.get("resampling")))
    be = a.get("breakeven") or {}
    if be:
        L.append("  breakeven geometry  : {}".format(be.get("reason")))
        if be.get("margin") is not None:
            L.append("    margin            : {:+.1%}".format(be["margin"]))
    L.append("-" * 70)
    if a.get("sufficient"):
        L.append("  SUFFICIENT: the sample can support a conclusion. It does not")
        L.append("  say the conclusion is favourable.")
    else:
        L.append("  NOT SUFFICIENT:")
        for r in a.get("reasons", []):
            L.append("    - " + r)
    return "\n".join(L)
