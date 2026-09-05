"""The Edge System metrics, checked against the SPEC'S OWN worked examples.

Spec: docs/strategies/9_30_breakout/0930_AllDay/analysis/RISK_PROFILE_DEFINITIONS.md
Its section 13 lists ten systems with stated win rate, EV, PF and grade. That is
a ready-made corpus, and it is the only way to check a grader that would
otherwise be checked against itself.

Running the old implementation against it is what found the defects: all ten
systems graded F on Combined Edge, including the spec's A+ exemplar, and Risk of
Ruin had exactly two reachable values across the whole corpus, {0.0, 1.0}.
"""
import math

import numpy as np
import pytest

from scripts.trading_framework.reporting import institutional_metrics as im

RISK = 225.0            # spec section 2's worked risk-per-trade
ACCOUNT = 50_000.0

# (name, win_rate, EV$, PF, spec's overall grade) -- spec section 13.
SPEC_SYSTEMS = [
    ("N1 horrible", 0.30, -127.0, 0.19, "F"),
    ("N2 losing flip", 0.40, -55.0, 0.59, "F"),
    ("N3 slight edge", 0.35, -93.0, 0.36, "F"),
    ("N4 almost breakeven", 0.45, -33.0, 0.73, "D/F"),
    ("N5 breakeven", 0.50, -12.0, 0.89, "D"),
    ("P1 small real edge", 0.55, 36.0, 1.36, "B"),
    ("P2 trend following", 0.45, 33.0, 1.27, "B"),
    ("P3 big R multiple", 0.30, 82.0, 1.52, "A-"),
    ("P4 high PF", 0.60, 90.0, 2.00, "A"),
    ("P5 excellent balanced", 0.55, 146.0, 2.44, "A+"),
]

POSITIVE = [s for s in SPEC_SYSTEMS if s[2] > 0]
NEGATIVE = [s for s in SPEC_SYSTEMS if s[2] <= 0]


def _basis(units):
    """A ruin basis with a chosen number of units, stated explicitly."""
    return im.RuinBasis(ruin_distance=units * RISK, risk_per_trade=RISK,
                        source="test: {} units".format(units))


# --------------------------------------------------------------------------- #
# Combined Edge -- the reading, and the account-independence that decided it
# --------------------------------------------------------------------------- #
def test_p5_confirms_the_spec_quotes_the_DOLLAR_reading():
    """The datum that resolved the spec's internal contradiction.

    Section 5 says `CE = EV_R x PF`; section 13's P5 states CombinedEdge 357 for
    EV $146 / PF 2.44. Only EV$ x PF reproduces 357. This test does not endorse
    that reading -- it pins the observation that forced the choice, so nobody
    re-opens the question from the formula alone.
    """
    _, _, ev, pf, _ = SPEC_SYSTEMS[-1]
    assert ev * pf == pytest.approx(357, abs=1.0)
    assert (ev / RISK) * pf == pytest.approx(1.583, abs=0.01)


@pytest.mark.parametrize("account", [25_000.0, 50_000.0, 150_000.0, 250_000.0])
def test_combined_edge_is_invariant_to_account_size(account):
    """The property that made the normalised reading the right one.

    One strategy, one risk POLICY (1% of account), four account sizes. The
    dollar reading graded this D at $25k and A at $250k. A grade that moves when
    you resize the account is grading the account.
    """
    risk = 0.01 * account
    rng = np.random.default_rng(4)
    r = np.where(rng.random(400) < 0.55, 1.0, -0.8)     # fixed R-multiples
    pnl = r * risk

    m = im.compute(pnl, risk_per_trade=risk, account_size=account,
                   max_drawdown_pct=10.0, ruin_basis=_basis(8))
    assert m["combined_edge"] == pytest.approx(_expected_ce(r), rel=1e-9)


def _expected_ce(r):
    wins, losses = r[r > 0], r[r <= 0]
    ev_r = r.mean()
    pf = wins.sum() / abs(losses.sum())
    return ev_r * pf


def test_the_spec_grading_scale_no_longer_fails_every_system():
    """The regression that motivated all of this.

    The old grader returned F for all ten spec systems -- including P5, which the
    spec calls A+. Asserted as a property of the CORPUS, not of one system: if a
    future rescale flattens the grades again, this fails.
    """
    grades = {name: im.grade_ce((ev / RISK) * pf)
              for name, _, ev, pf, _ in SPEC_SYSTEMS}
    assert grades["P5 excellent balanced"] == "A", grades
    assert grades["P4 high PF"] == "A", grades      # spec states Grade A
    assert len({g for g in grades.values()}) >= 3, (
        "the whole corpus collapsed onto {} grade(s) -- a scale that cannot "
        "separate the spec's own worst system from its best is not grading: {}"
        .format(len(set(grades.values())), grades))


def test_every_negative_expectancy_system_grades_F():
    """The negative control. Without it, a scale that grades everything A passes."""
    for name, _wr, ev, pf, _ in NEGATIVE:
        assert im.grade_ce((ev / RISK) * pf) == "F", name


# --------------------------------------------------------------------------- #
# Risk of ruin -- the bands must be REACHABLE
# --------------------------------------------------------------------------- #
def test_ror_bands_are_reachable_across_the_spec_corpus():
    """The defect, stated as a property.

    Against a 100%-of-account exponent (~222 units at $225 risk on $50k) the
    distinct RoR values across all ten spec systems were exactly {0.0, 1.0}: the
    spec's four bands could never be produced by any input. Against the prop
    trailing-drawdown exponent they spread.
    """
    account_units = ACCOUNT / RISK                       # ~222: the old behaviour
    old = {round(im.risk_of_ruin((ev / RISK) * pf, _basis(account_units)), 6)
           for _, _, ev, pf, _ in SPEC_SYSTEMS}
    assert old == {0.0, 1.0}, (
        "the old exponent is supposed to be degenerate; if this changed, the "
        "premise of this test needs re-deriving: %s" % old)

    # Apex 50K trailing drawdown $2,500 at $225 risk = 11.1 units.
    dd_units = 2_500.0 / RISK
    new = [im.risk_of_ruin((ev / RISK) * pf, _basis(dd_units))
           for _, _, ev, pf, _ in SPEC_SYSTEMS]
    bands = {im.grade_ror(r) for r in new}
    assert len(bands) >= 3, (
        "the drawdown exponent must separate the corpus into several bands, "
        "otherwise it is the same degenerate metric with a different constant: "
        "%s" % sorted(bands))


def test_ror_is_monotonic_in_edge():
    """More edge must never mean more ruin."""
    b = _basis(11.1)
    rors = [im.risk_of_ruin(ce, b) for ce in (0.05, 0.1, 0.2, 0.4, 0.8)]
    assert rors == sorted(rors, reverse=True), rors


def test_ror_is_monotonic_in_units():
    """A deeper drawdown allowance must never mean more ruin."""
    rors = [im.risk_of_ruin(0.2, _basis(u)) for u in (2, 4, 8, 16, 32)]
    assert rors == sorted(rors, reverse=True), rors


def test_no_edge_is_certain_ruin():
    for ce in (0.0, -0.5):
        assert im.risk_of_ruin(ce, _basis(11.1)) == 1.0


def test_ror_is_returned_as_a_fraction_never_a_percentage():
    """The unit collision that made this module necessary.

    `tearsheet.py` stored a fraction and `risk_profiler.py` stored fraction*100
    under the same key `ror`, while `optimization_summary.py` badges green below
    1 -- so a 50% risk of ruin could render as "0.50%" and pass.
    """
    r = im.risk_of_ruin(0.2, _basis(11.1))
    assert 0.0 <= r <= 1.0
    m = im.compute([100.0, -50.0] * 30, risk_per_trade=RISK,
                   account_size=ACCOUNT, max_drawdown_pct=5.0)
    assert 0.0 <= m["ror"] <= 1.0


def test_the_closed_form_agrees_with_simulation():
    """Independence was NOT what was breaking the metric -- the exponent was.

    If these ever diverge materially, the closed form has stopped being an
    adequate model and the simulator should take over.
    """
    p, units, n_paths, n_trades = 0.55, 8.0, 20_000, 400
    rng = np.random.default_rng(11)
    steps = np.where(rng.random((n_paths, n_trades)) < p, 1.0, -1.0)
    simulated = float((( units + steps.cumsum(axis=1)).min(axis=1) <= 0).mean())

    A = 2 * p - 1                       # even-money advantage, matching the sim
    closed = ((1 - A) / (1 + A)) ** units
    assert closed == pytest.approx(simulated, abs=0.02), (closed, simulated)


# --------------------------------------------------------------------------- #
# The ruin basis must be declared, and must be visible in the output
# --------------------------------------------------------------------------- #
def test_a_profile_without_a_drawdown_is_refused_not_defaulted():
    """Falling back to the account size is the defect; it must not be reachable."""
    class _NoDD:
        name = "Broken Profile"
        max_trailing_drawdown = 0.0

    with pytest.raises(ValueError) as exc:
        im.ruin_basis_from_profile(_NoDD(), risk_per_trade=RISK)
    assert "account size" in str(exc.value)


def test_the_basis_travels_with_the_number():
    """`ror` is meaningless without what it was measured against."""
    from scripts.trading_framework.ml.prop_firm_simulator import FIRM_PROFILES
    prof = FIRM_PROFILES["apex_50k"]
    basis = im.ruin_basis_from_profile(prof, risk_per_trade=RISK)
    assert basis.units == pytest.approx(2_500.0 / RISK)
    assert "Apex 50K" in basis.source and "trailing" in basis.source

    m = im.compute([100.0, -50.0] * 30, risk_per_trade=RISK, account_size=ACCOUNT,
                   max_drawdown_pct=5.0, ruin_basis=basis)
    assert m["ruin_basis"] == basis.source
    assert m["ruin_units"] == pytest.approx(basis.units)


def test_zero_risk_per_trade_is_refused():
    """Spec section 2: no metric matters until risk is defined."""
    with pytest.raises(ValueError):
        im.RuinBasis(1000.0, 0.0, "x").units
    with pytest.raises(ValueError):
        im.compute([1.0], risk_per_trade=0.0, account_size=ACCOUNT,
                   max_drawdown_pct=1.0)


# --------------------------------------------------------------------------- #
# The remaining spec formulas
# --------------------------------------------------------------------------- #
def test_consecutive_loss_formula_matches_the_spec_worked_example():
    """Spec section 7: N=200, loss rate 55% -> about 9 in a row."""
    assert im.max_consecutive_losses(200, 0.55) == pytest.approx(8.8, abs=0.2)


def test_ev_and_pf_reproduce_from_constructed_trades():
    """Ties the formulas to real per-trade input rather than to themselves."""
    pnl = [225.0] * 55 + [-225.0] * 45          # 55% at 1R
    m = im.compute(pnl, risk_per_trade=RISK, account_size=ACCOUNT,
                   max_drawdown_pct=10.0, ruin_basis=_basis(11.1))
    assert m["win_rate"] == pytest.approx(0.55)
    assert m["ev"] == pytest.approx(0.55 * 225 - 0.45 * 225)
    assert m["pf"] == pytest.approx((55 * 225) / (45 * 225))
    assert m["ev_r"] == pytest.approx(m["ev"] / RISK)
    assert m["combined_edge"] == pytest.approx(m["ev_r"] * m["pf"])


def test_drr_is_drawdown_over_risk_percent():
    """Spec section 8: DRR = MaxDD% / RiskPerTrade%."""
    m = im.compute([225.0, -225.0] * 50, risk_per_trade=500.0,
                   account_size=50_000.0, max_drawdown_pct=8.0,
                   ruin_basis=_basis(4))
    assert m["drr"] == pytest.approx(8.0 / 1.0)      # risk is 1% of the account
    # Spec section 8 bands: <4 A, 4-7 B/C, 7-10 D, >10 F. 8.0 is D, not F --
    # this asserted F by restating the rule from memory instead of reading it.
    assert m["drr_grade"] == "D"
    assert im.grade_drr(3.0) == "A" and im.grade_drr(12.0) == "F"


def test_sqn_is_zero_rather_than_nan_when_every_trade_is_identical():
    m = im.compute([100.0] * 20, risk_per_trade=RISK, account_size=ACCOUNT,
                   max_drawdown_pct=1.0, ruin_basis=_basis(11.1))
    assert m["sqn"] == 0.0 and math.isfinite(m["sqn"])


def test_no_trades_reports_an_error_rather_than_a_zeroed_result():
    """A null result is not a measurement."""
    m = im.compute([], risk_per_trade=RISK, account_size=ACCOUNT,
                   max_drawdown_pct=0.0)
    assert m.get("error") and m["n_trades"] == 0
    assert "ror" not in m, "an empty corpus must not produce a risk of ruin"


def test_ror_saturates_above_the_clamp_and_that_is_a_KNOWN_LIMIT():
    """Pinned, not hidden: the metric cannot rank strong systems against each other.

    The spec's formula puts CombinedEdge in the slot where the classical
    gambler's-ruin formula expects a PROBABILITY advantage (2p-1, in (0,1)).
    CombinedEdge is not a probability and routinely exceeds 1 on the normalised
    reading -- the spec's own P5 scores 1.583. The implementation clamps at 0.99,
    so every system at or above that clamp reports the SAME risk of ruin.

    That is acceptable because it saturates towards SAFE for systems that are
    already strong on CE and SQN, and the bands stay discriminating exactly where
    the decision is hard (marginal systems: measured 0.73% / 1.52% / 100% across
    the spec's P1, P2 and N5). It is NOT acceptable to rank strong systems by
    RoR. Use `PropFirmSimulator` when that is the question.

    Asserted as a property so that if someone replaces the closed form with
    something that CAN separate strong systems, this test fails and the comment
    above gets revisited rather than silently rotting.
    """
    b = _basis(11.1)
    assert im.risk_of_ruin(0.99, b) == im.risk_of_ruin(5.0, b)
    assert im.risk_of_ruin(0.99, b) == im.risk_of_ruin(1.583, b)   # the spec's P5

    # ... while remaining discriminating in the region that decides anything.
    marginal = [im.risk_of_ruin(ce, b) for ce in (0.10, 0.15, 0.22, 0.30)]
    assert len(set(round(x, 6) for x in marginal)) == 4, marginal
    assert marginal == sorted(marginal, reverse=True)
