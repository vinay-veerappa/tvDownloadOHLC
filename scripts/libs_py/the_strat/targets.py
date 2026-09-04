"""Strat measured-move target engine (Pillar 1 — pure, vectorizable).

WHY THIS EXISTS
---------------
combos.py sets magnitude_1_target = prior-bar high/low (h[i-2] / l[i-2]).
For a 2U-1-2U the entry (inside_high + tick) sits just BELOW that prior high,
so reward is 1-2 pts against 5-15 pts of risk (RR ~0.2). 2-2 reversals are
worse: target == trigger-bar extreme gives reward == 0. Every min_rr filter
then either passes nothing or forces min_rr=0 (zero-expectancy scalps).

CANONICAL RULE (used by Python signals.py AND NT8 StratCore.cs — keep in sync):
    inside_range = inside_high - inside_low            (the coil being broken)
    prior_leg    = |trigger_close - origin_open|       (energy into the setup;
                     origin = bar[i-2] open for 2-1-2/3-1-2, bar[i-1] open for 2-2)
    target_dist  = max(inside_range, 0.5 * prior_leg, min_target_points)
    target1      = entry +/- target_dist
    target2      = entry +/- 2 * target_dist  (runner; strategies may substitute
                     a structural swing — 1h/3h extreme — when further than target2)

The structural stop (inside-bar opposite extreme +/- tick) is NEVER widened,
only capped at max_risk_points — and capping is flagged so strategies can
skip instead of trading a fake invalidation level.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MeasuredTargets:
    target1: float
    target2: float
    target_dist: float
    risk_points: float
    reward_points: float
    rr_ratio: float
    stop_capped: bool


def measured_targets(
    direction: int,
    entry: float,
    structural_stop: float,
    inside_high: float,
    inside_low: float,
    prior_leg_points: float,
    min_target_points: float,
    max_risk_points: float,
    tick_size: float = 0.25,
) -> MeasuredTargets:
    """Compute tradable targets + capped risk for one setup.

    direction: +1 LONG, -1 SHORT. Returns RR of target1 vs (possibly capped) risk.
    """
    inside_range = max(inside_high - inside_low, tick_size)
    leg = max(prior_leg_points, 0.0)
    target_dist = max(inside_range, 0.5 * leg, min_target_points)

    struct_risk = abs(entry - structural_stop)
    if struct_risk < tick_size:
        struct_risk = tick_size
    stop_capped = struct_risk > max_risk_points
    risk = min(struct_risk, max_risk_points)
    if risk < tick_size:
        risk = tick_size
    capped_stop = entry - risk if direction == 1 else entry + risk

    _ = capped_stop  # caller keeps structural stop unless it opts into the cap
    target1 = entry + target_dist if direction == 1 else entry - target_dist
    target2 = entry + 2.0 * target_dist if direction == 1 else entry - 2.0 * target_dist
    rr = target_dist / risk if risk > 0 else 0.0
    return MeasuredTargets(
        target1=target1,
        target2=target2,
        target_dist=target_dist,
        risk_points=risk,
        reward_points=target_dist,
        rr_ratio=rr,
        stop_capped=stop_capped,
    )
