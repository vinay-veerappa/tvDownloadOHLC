"""The Edge System metrics -- ONE implementation of the spec.

SPEC: docs/architecture/STRATEGY_WORKFLOW.md section 7.2.
      Subsumed 2026-09-04 from "The Edge System: Risk Profile Master Guide"
      (user-provided source text) and its lossy derivative REPORTING_METRICS.md,
      both deleted. The guide's TEN WORKED SYSTEMS live in
      tests/test_institutional_metrics.py, which is a stronger home than prose:
      they now fail a build.

There used to be TWO implementations of these formulas -- `tearsheet.py::
compute_institutional_metrics` and `risk_profiler.py::RiskProfiler` -- with the
same metric names and, for `ror`, DIFFERENT UNITS: one stored a fraction, the
other stored fraction*100. A third consumer, `optimization_summary.py`, reads
`ror` and badges it green below 1, i.e. it expects the percentage. Cross-wire
those and a 50% risk of ruin renders as "0.50%" and grades green. Both now
delegate here, so the units have one owner.

Two corrections to what those implementations did, both decided 2026-09-04 after
measuring against the spec's own ten worked systems (section 13):

1. COMBINED EDGE IS SCALE-FREE. The spec is internally inconsistent: section 5
   states `CE = EV_R x PF` (normalised), while its worked example P5 quotes
   CombinedEdge 357 for EV $146 / PF 2.44 -- which is EV_DOLLARS x PF (356.2).
   The grading scale (A>150 ... D>20) belongs to the dollar version. The code
   took the FORMULA from one and the GRADES from the other, so every one of the
   spec's ten systems graded F, including its A+ exemplar.

   Resolved in favour of the normalised form, because the dollar form grades the
   ACCOUNT rather than the STRATEGY: one strategy at EV_R 0.10 / PF 1.15, held
   constant with a 1% risk policy throughout, scores 28.7 (D) on $25k and 287.5
   (A) on $250k. `EV_R` and `PF` are both invariant to position size, which is
   what a grade needs. Thresholds are the spec's, converted by dividing by the
   spec's own worked risk-per-trade of $225 -- the factor the two readings differ
   by. A round /100 was tried first and graded the spec's P4 (stated Grade A) a C.

2. RUIN IS THE DRAWDOWN LIMIT, NOT THE ACCOUNT. Section 6 defines RoR as the
   probability of hitting "zero OR BLOWOUT THRESHOLD"; the old code read only the
   first half and used `account_size / risk_per_trade` as the exponent. On a prop
   account the blowout threshold is the TRAILING DRAWDOWN -- $2,500 on an Apex
   50K, i.e. 5% of the account, not 100%. That is a ~20-40x error in an exponent.

   The consequence was a metric with two reachable values. Across the spec's ten
   systems the distinct outputs were exactly {0.0, 1.0}: 100% if EV <= 0, and
   0.00% otherwise, because any base < 1 raised to ~200-400 underflows. The
   spec's four bands (<1% / 1-5% / 5-20% / >20%) could NEVER be reached. With the
   drawdown exponent the same systems spread across all four.

   Note the account size cancels either way under a fixed-fractional policy --
   both the ruin distance and the risk per trade are percentages of it. What
   drives RoR is the RATIO, which is why it is expressed that way here.

The closed form is kept. With the corrected exponent it agrees with simulation
(20.08% closed-form vs 20.03% over 40k paths for a 55% system at 8 units), so
independence was not what was breaking it. `PropFirmSimulator` remains the
authority on prop viability and is the right cross-check.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import numpy as np

#: Ruin distance when no prop profile is supplied. Deliberately NOT the account
#: size: a self-funded account still stops trading long before zero, and using
#: the full account is the defect this module was written to fix. Stated as a
#: fraction of the account so it cannot drift with account size.
DEFAULT_RUIN_FRACTION = 0.20


# --------------------------------------------------------------------------- #
# Grades. Thresholds are the spec's; only Combined Edge is rescaled, and §12
# ("position sizing by grade") is what makes these load-bearing rather than
# decorative -- an F means do not trade.
# --------------------------------------------------------------------------- #
def grade_ev(ev_dollars: float) -> str:
    if ev_dollars > 100: return "A"
    if ev_dollars >= 50: return "B"
    if ev_dollars >= 10: return "C"
    if ev_dollars > 0: return "D"
    return "F"


def grade_pf(pf: float) -> str:
    """Spec section 4: >2.0 A, 1.4-2.0 B, 1.1-1.4 C, <1.0 F."""
    if pf >= 2.0: return "A"
    if pf >= 1.4: return "B"
    if pf >= 1.1: return "C"
    if pf >= 1.0: return "D"
    return "F"


def grade_sqn(sqn: float) -> str:
    """Spec section 10: >3.0 A, 2.0-3.0 B, 1.6-2.0 C, <1.6 D/F."""
    if sqn >= 3.0: return "A"
    if sqn >= 2.0: return "B"
    if sqn >= 1.6: return "C"
    if sqn >= 1.0: return "D"
    return "F"


def grade_drr(drr: float) -> str:
    """Spec section 8: <4 A, 4-7 B/C, 7-10 D, >10 F."""
    if drr < 4: return "A"
    if drr <= 7: return "B"
    if drr <= 10: return "D"
    return "F"


#: The spec's Combined Edge thresholds (A>150, B>100, C>50, D>20) are stated on
#: the DOLLAR reading, which is `EV_R x PF x Risk$`. They are therefore implicitly
#: denominated in the spec's own worked risk-per-trade (section 2: "Risk per trade
#: ($R) = $225"). Normalising the metric means dividing the thresholds by that
#: same number -- it is a units conversion, not a re-opinion.
#:
#: A round /100 was tried first and is WRONG: it graded the spec's P4 (EV $90,
#: PF 2.00, stated Grade A) as a C. /225 reproduces A for both P4 and P5.
SPEC_WORKED_RISK = 225.0
CE_THRESHOLDS = {g: d / SPEC_WORKED_RISK for g, d in
                 (("A", 150.0), ("B", 100.0), ("C", 50.0), ("D", 20.0))}


def grade_ce(ce: float) -> str:
    """Spec section 5 thresholds, converted to the normalised (scale-free) reading."""
    if ce > CE_THRESHOLDS["A"]: return "A"
    if ce >= CE_THRESHOLDS["B"]: return "B"
    if ce >= CE_THRESHOLDS["C"]: return "C"
    if ce >= CE_THRESHOLDS["D"]: return "D"
    return "F"


def grade_ror(ror_fraction: float) -> str:
    """Spec section 6 bands, which the drawdown exponent finally makes reachable."""
    if ror_fraction < 0.01: return "Professional"
    if ror_fraction <= 0.05: return "Acceptable"
    if ror_fraction <= 0.20: return "Dangerous"
    return "Lethal"


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RuinBasis:
    """WHAT the strategy is assumed to be ruined BY. Recorded, never guessed.

    `ror` is meaningless without this: the same trades give 0.00% against a
    100%-of-account threshold and 20% against a prop trailing drawdown. Every
    report that prints a risk of ruin must print the basis beside it.
    """
    ruin_distance: float          # dollars from peak to liquidation
    risk_per_trade: float         # dollars at risk on one trade
    source: str                   # e.g. "prop profile: Apex 50K (trailing DD)"

    @property
    def units(self) -> float:
        if self.risk_per_trade <= 0:
            raise ValueError(
                "risk_per_trade must be > 0 to express a ruin distance in units; "
                "got {!r}. Every metric in the spec depends on risk being defined "
                "first (section 2).".format(self.risk_per_trade))
        return self.ruin_distance / self.risk_per_trade


def ruin_basis_from_profile(profile: Any, risk_per_trade: float) -> RuinBasis:
    """Take the ruin distance from a PropFirmProfile's TRAILING DRAWDOWN.

    Decided 2026-09-04: the trailing drawdown is the real liquidation point, so
    it is the honest survival number. A self-imposed "stop trading" threshold
    would be a different (larger) number and is deliberately not used.
    """
    dd = float(getattr(profile, "max_trailing_drawdown", 0.0) or 0.0)
    if dd <= 0:
        raise ValueError(
            "prop profile {!r} declares no max_trailing_drawdown, so there is no "
            "ruin distance to compute against. Pass an explicit RuinBasis rather "
            "than falling back to the account size -- that fallback is the defect "
            "this module exists to remove.".format(getattr(profile, "name", profile)))
    return RuinBasis(
        ruin_distance=dd,
        risk_per_trade=float(risk_per_trade),
        source="prop profile: {} (trailing drawdown ${:,.0f})".format(
            getattr(profile, "name", "?"), dd),
    )


def default_ruin_basis(account_size: float, risk_per_trade: float) -> RuinBasis:
    return RuinBasis(
        ruin_distance=DEFAULT_RUIN_FRACTION * float(account_size),
        risk_per_trade=float(risk_per_trade),
        source="no prop profile supplied; default {:.0%} of ${:,.0f}".format(
            DEFAULT_RUIN_FRACTION, account_size),
    )


# --------------------------------------------------------------------------- #
def risk_of_ruin(combined_edge: float, basis: RuinBasis) -> float:
    """Spec section 6: ((1 - edge) / (1 + edge)) ^ units. Returns a FRACTION.

    Returns a fraction, always -- the `ror` unit collision that motivated this
    module came from one caller storing a percentage under the same key. Callers
    that want a percentage multiply at the point of RENDERING.
    """
    edge = max(0.0, min(float(combined_edge), 0.99))
    if edge <= 0.0:
        return 1.0                     # no edge: ruin is certain, given enough trades
    return ((1.0 - edge) / (1.0 + edge)) ** basis.units


def max_consecutive_losses(n_trades: int, loss_rate: float) -> float:
    """Spec section 7: ln(N) / ln(1 / LossRate). The expected worst streak."""
    if n_trades <= 1 or not (0.0 < loss_rate < 1.0):
        return 0.0
    return math.log(n_trades) / math.log(1.0 / loss_rate)


def compute(pnl_dollars: Sequence[float], *, risk_per_trade: float,
            account_size: float, max_drawdown_pct: float,
            ruin_basis: Optional[RuinBasis] = None) -> Dict[str, Any]:
    """Every Edge System metric, from per-trade dollar P&L.

    `max_drawdown_pct` is a POSITIVE percentage (12.5 means a 12.5% drawdown).
    `ror` is a fraction. `ruin_basis` is echoed so a reader can see what the
    risk of ruin was measured against.
    """
    pnl = np.asarray(list(pnl_dollars), dtype="float64")
    if pnl.size == 0:
        return {"error": "no trades", "n_trades": 0}
    if risk_per_trade <= 0:
        raise ValueError("risk_per_trade must be > 0 (spec section 2: define risk first)")

    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    n = int(pnl.size)
    win_rate = wins.size / n
    avg_win = float(wins.mean()) if wins.size else 0.0
    avg_loss = float(abs(losses.mean())) if losses.size else 0.0

    ev = win_rate * avg_win - (1.0 - win_rate) * avg_loss        # section 3
    gross_win, gross_loss = float(wins.sum()), float(abs(losses.sum()))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")  # section 4

    ev_r = ev / risk_per_trade
    # Section 5, normalised reading. NOT EV$ x PF -- see the module docstring.
    combined_edge = ev_r * (pf if math.isfinite(pf) else 0.0)

    r_multiples = pnl / risk_per_trade                            # section 10
    sd = float(r_multiples.std(ddof=1)) if n > 1 else 0.0
    mean_r = float(r_multiples.mean())
    # `sd > 0` is NOT a sufficient guard. numpy's two-pass std over twenty
    # BITWISE-IDENTICAL values returns 5.7e-17 rather than 0.0, so a strategy
    # with literally zero variance divided by noise and scored SQN 3.49e16 --
    # grade A, "Holy Grail". Compare against the scale of the data instead.
    scale = max(abs(mean_r), float(np.abs(r_multiples).max()), 1e-12)
    sqn = (mean_r / sd) * math.sqrt(n) if sd > scale * 1e-9 else 0.0

    risk_pct = (risk_per_trade / account_size) * 100.0            # section 8
    drr = abs(max_drawdown_pct) / risk_pct if risk_pct > 0 else float("inf")

    basis = ruin_basis or default_ruin_basis(account_size, risk_per_trade)
    ror = risk_of_ruin(combined_edge, basis)

    return {
        "n_trades": n,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "ev": ev, "ev_r": ev_r, "ev_grade": grade_ev(ev),
        "pf": pf, "pf_grade": grade_pf(pf),
        "combined_edge": combined_edge, "ce_grade": grade_ce(combined_edge),
        "sqn": sqn, "sqn_grade": grade_sqn(sqn),
        "drr": drr, "drr_grade": grade_drr(drr),
        # A FRACTION. Render as ror * 100.
        "ror": ror, "ror_grade": grade_ror(ror),
        "ruin_units": basis.units,
        "ruin_basis": basis.source,
        "max_streak": int(math.ceil(max_consecutive_losses(n, 1.0 - win_rate))),
        "risk_per_trade": float(risk_per_trade),
        "account_size": float(account_size),
    }
