"""Section 8's thresholds, which nothing had ever measured.

"At least 120 trades per configuration across at least 3 regimes" and "for a
marginal PF, bootstrap a confidence interval; if it crosses zero there is no
edge" have been in STRATEGY_WORKFLOW.md section 8 since it was written. The
`out_of_sample` criterion checked that `--oos-start` was PASSED -- that a split
EXISTS, not that what landed on the far side of it can support a conclusion.

The test this file is really for is the first one: a sample that looks
excellent and is not enough.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.trading_framework.reporting import sufficiency as S


def _trades(n, *, pnl=None, start="2026-01-05", freq="6h", seed=1):
    rng = np.random.default_rng(seed)
    if pnl is None:
        pnl = rng.normal(40, 300, n)
    return pd.DataFrame({
        "entry_time": pd.date_range(start, periods=n, freq=freq, tz="UTC"),
        "total_pnl_usd": np.asarray(pnl, dtype=float),
    })


# --------------------------------------------------------------------------- #
# The case this exists for
# --------------------------------------------------------------------------- #
def test_six_trades_all_winners_is_not_sufficient():
    """100% win rate, every trade profitable, and it proves nothing."""
    a = S.assess(_trades(6, pnl=[300, 250, 410, 180, 520, 260]),
                 out_of_sample=True)
    assert a["sufficient"] is False
    joined = " ".join(a["reasons"])
    assert "below the 120" in joined
    assert "regimes" in joined
    assert "confidence interval" in joined


def test_an_empty_trade_list_is_untested_not_passed():
    a = S.assess(pd.DataFrame(), out_of_sample=True)
    assert a["sufficient"] is False
    assert "untested, not passed" in a["reasons"][0]


def test_in_sample_trades_are_insufficient_however_many_there_are():
    a = S.assess(_trades(400, pnl=np.full(400, 250.0)), out_of_sample=False)
    assert a["sufficient"] is False
    assert any("IN-SAMPLE" in r for r in a["reasons"])


def test_a_year_of_trades_in_one_quarter_fails_on_regime_spread():
    """The case that recurs: plenty of evidence, all from one stretch of tape."""
    a = S.assess(_trades(300, freq="15min", start="2026-01-05"),
                 out_of_sample=True)
    assert (a["regimes"]["n_regimes"]) == 1
    assert any("one stretch of market" in r for r in a["reasons"])


def test_a_ci_that_straddles_zero_fails_and_says_the_interval_is_a_lower_bound():
    rng = np.random.default_rng(3)
    a = S.assess(_trades(200, pnl=rng.normal(0.0, 500, 200), freq="18h"),
                 out_of_sample=True)
    assert a["bootstrap"]["excludes_zero"] is False
    assert any("straddles zero" in r and "LOWER" in r for r in a["reasons"])


# --------------------------------------------------------------------------- #
# The negative control -- a gate that only says no proves nothing
# --------------------------------------------------------------------------- #
def test_a_sample_that_really_is_sufficient_passes():
    rng = np.random.default_rng(11)
    pnl = rng.normal(120, 200, 400)          # a real, large mean relative to sd
    a = S.assess(_trades(400, pnl=pnl, freq="18h"), out_of_sample=True)
    assert a["regimes"]["n_regimes"] >= S.MIN_REGIMES, a["regimes"]["reason"]
    assert a["bootstrap"]["excludes_zero"] is True
    assert a["sufficient"] is True, a["reasons"]


def test_sufficient_does_not_mean_good():
    """A large, clearly LOSING sample is statistically sufficient. The wording
    of the render must not imply otherwise -- that is how a measurement gets
    quoted as a verdict."""
    rng = np.random.default_rng(12)
    a = S.assess(_trades(400, pnl=rng.normal(-150, 200, 400), freq="18h"),
                 out_of_sample=True)
    assert a["sufficient"] is True
    assert "does not" in S.render(a)


# --------------------------------------------------------------------------- #
# The pieces
# --------------------------------------------------------------------------- #
def test_the_bootstrap_refuses_a_sample_too_small_to_bootstrap():
    r = S.bootstrap_mean_ci(np.arange(8, dtype=float))
    assert r["ci"] is None and "below the 30" in r["reason"]


def test_the_bootstrap_is_deterministic():
    x = np.random.default_rng(5).normal(50, 300, 200)
    assert S.bootstrap_mean_ci(x)["ci"] == S.bootstrap_mean_ci(x)["ci"]


def test_the_bootstrap_names_its_independence_assumption():
    """The interval understates uncertainty under serial dependence, and a
    consumer who is not told that will read it as tighter than it is."""
    r = S.bootstrap_mean_ci(np.random.default_rng(6).normal(50, 300, 200))
    assert "serially dependent" in r["resampling"]


def test_breakeven_win_rate_reproduces_section_8s_worked_example():
    """A 1:2 risk-reward needs >66.7% to break even -- section 8, IBBreakoutBot."""
    pnl = [100.0] * 6 + [-200.0] * 4           # avg win 100, avg loss 200
    be = S.breakeven_win_rate(pd.DataFrame({"total_pnl_usd": pnl}))
    assert abs(be["required_win_rate"] - 2 / 3) < 1e-9
    assert abs(be["observed_win_rate"] - 0.6) < 1e-9
    assert be["margin"] < 0


def test_breakeven_refuses_a_one_sided_sample():
    be = S.breakeven_win_rate(pd.DataFrame({"total_pnl_usd": [1.0, 2.0]}))
    assert "needs both" in be["reason"]


def test_the_regime_bucket_declares_that_it_is_a_proxy():
    """This is the reviewable judgment call in the module; it must not read as
    a volatility regime to anyone skimming the output."""
    reg = S.regime_spread(_trades(50, freq="10D"))
    assert "calendar quarter" in reg["proxy"]
    assert "not a volatility regime" in S.render(
        S.assess(_trades(50, freq="10D"), out_of_sample=True))


def test_quarters_are_bucketed_in_et_not_utc():
    """ADR-001. 23:00 ET on 31 March is 03:00 UTC on 1 April; bucketing on UTC
    puts the last evening of a quarter in the next one."""
    df = pd.DataFrame({
        "entry_time": pd.to_datetime(
            ["2026-03-31 23:00", "2026-03-31 22:00"]).tz_localize(
                "America/New_York").tz_convert("UTC"),
        "total_pnl_usd": [1.0, -1.0],
    })
    reg = S.regime_spread(df)
    assert reg["n_regimes"] == 1, reg["buckets"]
    assert list(reg["buckets"]) == ["2026Q1"], reg["buckets"]


def test_a_frame_with_no_timestamp_column_says_so_rather_than_scoring_zero():
    reg = S.regime_spread(pd.DataFrame({"total_pnl_usd": [1.0]}))
    assert reg["n_regimes"] is None and "no timestamp column" in reg["reason"]


def test_the_render_is_ascii():
    """The console here is cp1252; an em-dash raises UnicodeEncodeError."""
    text = S.render(S.assess(_trades(200, freq="18h"), out_of_sample=True))
    text.encode("cp1252")


# --------------------------------------------------------------------------- #
# Wiring
# --------------------------------------------------------------------------- #
def test_the_criterion_is_on_the_checklist():
    from scripts.trading_framework.workflow import CRITERIA, Checklist
    assert any(k == "statistically_sufficient" for k, _ in CRITERIA)
    # and it starts NOT EVALUATED, so it cannot be a pass by omission
    assert Checklist().items["statistically_sufficient"].status == "NOT EVALUATED"


def test_validated_is_unreachable_while_the_new_criterion_is_unevaluated():
    from scripts.trading_framework.workflow import Checklist, PASS
    c = Checklist()
    for k in list(c.items):
        if k != "statistically_sufficient":
            c.set(k, PASS, "")
    assert c.validated is False
    c.set("statistically_sufficient", PASS, "")
    assert c.validated is True
