"""The prop-firm Monte Carlo had a modelling assumption nothing recorded.

`run_monte_carlo` called `np.random.permutation` on the per-trade P&L array.
That resamples trades INDEPENDENTLY, which destroys serial dependence -- and
clustered losses are the principal trailing-drawdown hazard. Two strategies with
the same trade distribution, one whose losers arrive in runs and one whose
losers are scattered, have IDENTICAL permutation distributions and very
different real pass rates.

Worse than the assumption being wrong is that it was invisible: the scheme
appeared in no artifact, so the 65% threshold in section 9 was being applied to
a number whose meaning nobody had written down.

Nothing here claims `daily_block` is uniformly more pessimistic. Measured on the
first clustered frame both were run against, `iid` gave 0.8% and `daily_block`
23.6% -- the block scheme was HIGHER, because it preserved a structure the
permutation was scattering. The claim is narrower and is what the tests assert:
the scheme materially changes the answer, so it has to be named and chosen
rather than inherited.

ADR-021 froze this as the only prop evaluator, and the review that found this
noted there were no direct behavioural tests of it at all. These are the first.
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

from scripts.trading_framework.ml.prop_firm_simulator import (
    DEFAULT_RESAMPLE, FIRM_PROFILES, PropFirmSimulator, RESAMPLE_SCHEMES)

ACCOUNT = 50_000.0


def _frame(pnl, *, per_day=4, start="2026-01-05"):
    """One frame, `per_day` trades on each successive day."""
    pnl = np.asarray(pnl, dtype=float)
    days = np.repeat(pd.date_range(start, periods=int(np.ceil(len(pnl) / per_day)),
                                   freq="D"), per_day)[:len(pnl)]
    return pd.DataFrame({
        "exit_time": days + pd.to_timedelta(
            np.tile(np.arange(per_day), len(days) // per_day + 1)[:len(pnl)], unit="h"),
        "pnl_pct": pnl / ACCOUNT * 100.0,
    })


@pytest.fixture
def sim():
    return PropFirmSimulator(account_size=ACCOUNT)


@pytest.fixture
def clustered():
    """Losers arrive in RUNS -- the shape a trailing drawdown is exposed to."""
    rng = np.random.default_rng(0)
    blocks = [rng.normal(90, 40, 8) if i % 2 == 0 else rng.normal(-80, 40, 8)
              for i in range(40)]
    return _frame(np.concatenate(blocks), per_day=8)


# --------------------------------------------------------------------------- #
# The scheme changes the answer, and is recorded
# --------------------------------------------------------------------------- #
def test_the_two_schemes_disagree_on_a_frame_with_clustered_losses(sim, clustered):
    """If they agreed there would be nothing to choose and nothing to record."""
    p = FIRM_PROFILES["apex_50k"]
    iid = sim.run_monte_carlo(clustered, p, n_simulations=400, resample="iid")
    blk = sim.run_monte_carlo(clustered, p, n_simulations=400,
                              resample="daily_block")
    assert abs(iid.pass_rate_pct - blk.pass_rate_pct) > 5.0, (
        "the schemes agreed to within 5 points on a deliberately clustered "
        "frame: {} vs {}".format(iid.pass_rate_pct, blk.pass_rate_pct))


def test_the_result_names_the_scheme_it_was_produced_under(sim, clustered):
    for mode in RESAMPLE_SCHEMES:
        mc = sim.run_monte_carlo(clustered, FIRM_PROFILES["apex_50k"],
                                 n_simulations=50, resample=mode)
        assert mc.resampling == mode


def test_the_default_is_the_block_scheme():
    assert DEFAULT_RESAMPLE == "daily_block"


def test_an_unknown_scheme_is_refused_rather_than_falling_back(sim, clustered):
    """A silent fallback would put the old assumption back under a new name."""
    with pytest.raises(ValueError, match="unknown resampling scheme"):
        sim.run_monte_carlo(clustered, FIRM_PROFILES["apex_50k"],
                            n_simulations=10, resample="bootstrap")


def test_a_null_result_still_names_its_scheme(sim):
    """An empty run must not produce the one result with an unlabelled rate."""
    mc = sim.run_monte_carlo(pd.DataFrame({"exit_time": [], "pnl_pct": []}),
                             FIRM_PROFILES["apex_50k"], n_simulations=10,
                             resample="iid")
    assert mc.resampling == "iid"


# --------------------------------------------------------------------------- #
# What the block scheme preserves, and what it does not
# --------------------------------------------------------------------------- #
def test_the_block_scheme_keeps_trades_with_the_day_they_happened_on(sim):
    """A day is the block because every rule that can act -- daily loss limit,
    daily trade cap, consistency -- is evaluated per day. Splitting a day apart
    simulates nothing the rules respond to."""
    pnl = np.arange(12, dtype=float) * 100.0
    df = _frame(pnl, per_day=4)
    day_key = pd.to_datetime(df["exit_time"]).dt.normalize().astype("int64").to_numpy()
    rng = np.random.default_rng(3)
    out = sim._resample(pnl, day_key, rng, "daily_block")
    assert len(out) == len(pnl)
    # every emitted block of 4 must be one of the three original days, in order
    original = {tuple(pnl[i:i + 4]) for i in (0, 4, 8)}
    for i in range(0, len(out), 4):
        assert tuple(out[i:i + 4]) in original, out


def test_the_block_scheme_can_repeat_a_day_and_omit_another(sim):
    """Resampling WITH replacement is the point: a run of bad days recurring is
    the scenario the trailing drawdown exists to survive."""
    pnl = np.arange(12, dtype=float)
    df = _frame(pnl, per_day=4)
    day_key = pd.to_datetime(df["exit_time"]).dt.normalize().astype("int64").to_numpy()
    seen = set()
    for s in range(40):
        out = sim._resample(pnl, day_key, np.random.default_rng(s), "daily_block")
        seen.add(tuple(out))
    assert len(seen) > 1, "the block resample returned the same sequence every time"


def test_a_single_day_of_trades_degrades_to_a_permutation(sim):
    """One block cannot be resampled at day level; say so by behaviour rather
    than raising, since a one-day sample is a legitimate (if useless) input."""
    pnl = np.arange(6, dtype=float)
    day_key = np.zeros(6, dtype="int64")
    out = sim._resample(pnl, day_key, np.random.default_rng(1), "daily_block")
    assert sorted(out) == sorted(pnl)


def test_the_iid_scheme_is_still_available_by_name(sim):
    """Kept so the old number can be reproduced deliberately and compared --
    the objection was that it was the silent default, not that it is useless."""
    pnl = np.arange(20, dtype=float)
    out = sim._resample(pnl, np.zeros(20, dtype="int64"),
                        np.random.default_rng(1), "iid")
    assert sorted(out) == sorted(pnl)


def test_the_monte_carlo_is_reproducible(sim, clustered):
    """A pass rate that moves between two runs of the same inputs cannot be
    compared with a threshold."""
    p = FIRM_PROFILES["apex_50k"]
    a = sim.run_monte_carlo(clustered, p, n_simulations=200, seed=7)
    b = sim.run_monte_carlo(clustered, p, n_simulations=200, seed=7)
    assert a.pass_rate_pct == b.pass_rate_pct


def test_a_different_seed_gives_a_different_draw(sim, clustered):
    """The control: reproducibility must not have been achieved by not sampling."""
    p = FIRM_PROFILES["apex_50k"]
    rates = {sim.run_monte_carlo(clustered, p, n_simulations=120, seed=s)
             .pass_rate_pct for s in range(6)}
    assert len(rates) > 1, rates


# --------------------------------------------------------------------------- #
# The deterministic path, which was computed and read by nobody
# --------------------------------------------------------------------------- #
def test_a_strategy_that_blew_the_account_historically_says_so(sim):
    """This is what `prop_viability` now also requires to be clean."""
    pnl = np.full(200, -60.0)
    det = sim.run_deterministic(_frame(pnl), FIRM_PROFILES["apex_50k"])
    assert det.blown is True and det.passed is False


def test_a_strategy_that_reached_the_target_historically_says_so(sim):
    det = sim.run_deterministic(_frame(np.full(120, 60.0)),
                                FIRM_PROFILES["apex_50k"])
    assert det.passed is True and det.blown is False
