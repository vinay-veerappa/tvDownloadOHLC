"""One row per LEG -- Python adopts NT8's trade-counting convention.

DECIDED 2026-09-04. NT8 reports a 2-contract queen/runner bracket as **two
trades**: an `nt_backtest` of `ICTFVGCISDBot` returned `entries: 6` and
`totalTrades: 12`. Python's engine returns **one** row per entry, carrying
`leg1_points` and `leg2_points` in separate columns and a single aggregate
`total_pnl_usd`.

Left alone, that difference alone puts trade-set recall at ~50% on every bracket
strategy, for a reason that has nothing whatever to do with the strategy logic --
a number that looks exactly like a real parity failure and is not one.

WHY NT8'S CONVENTION AND NOT THE OTHER DIRECTION. Aggregating NT8's two rows into
one would mean the harness TRANSFORMING the authoritative side to fit the model
it is supposed to be testing, which is the precise inversion this work exists to
prevent. It also destroys information: a queen that took profit while the runner
stopped out is a different outcome from both legs stopping, and only the per-leg
view can show the difference. Aggregation can always be done afterwards from
per-leg rows; the reverse is not true.

WHAT THIS MODULE DOES NOT DO. It does not re-simulate. Every value it emits is
either recorded by the engine or derived exactly from recorded values:

    leg1 (queen)   exit price  = entry + leg1_points * sign      [exact]
                   exit time   = `leg1_exit_time`, recorded by the engine
    leg2 (runner)  exit price  = `exit_price`   (the final exit)
                   exit time   = `exit_time`

`leg1_exit_time` had to be ADDED to both the Rust kernel and its Python mirror --
the moment the queen filled was computable but nowhere kept. A queen that never
filled leaves with the runner, so both legs then carry the same exit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

#: Columns a frame must carry before it can be exploded. Named so the refusal can
#: say which one is missing rather than raising KeyError from inside pandas.
REQUIRED = (
    "entry_time", "exit_time", "direction", "entry_price", "exit_price",
    "leg1_points", "leg2_points", "leg1_exit_time", "leg1_exit_price",
)

LEG_QUEEN = 1
LEG_RUNNER = 2


def explode_legs(trades: pd.DataFrame, *, point_value: float | None = None,
                 commission_per_contract_rt: float = 0.0,
                 slippage_ticks: float = 0.0,
                 tick_size: float = 0.25) -> pd.DataFrame:
    """One row per leg, in NT8's convention.

    Each input row becomes exactly two output rows sharing `entry_time`,
    `entry_price` and `direction`, ordered queen-then-runner, with a `leg` column
    (1 = queen, 2 = runner) and a `parent_trade` index back to the source row.

    `point_value` is optional. When given, per-leg `pnl` is money for ONE
    contract per leg, net of that leg's share of commission and slippage; when
    omitted, `pnl` is left as points. It is deliberately not defaulted: a P&L
    figure computed with a guessed multiplier is worse than none, and this repo
    has already shipped an engine that silently used NQ's multiplier for every
    instrument.
    """
    missing = [c for c in REQUIRED if c not in trades.columns]
    if missing:
        raise KeyError(
            "cannot explode to per-leg rows, missing column(s): {}. Present: {}. "
            "A frame from an engine that predates the leg convention will not "
            "carry leg1_exit_time -- re-run the backtest rather than filling it "
            "in.".format(missing, list(trades.columns)))

    if trades.empty:
        return pd.DataFrame(columns=list(trades.columns) + ["leg", "parent_trade", "pnl"])

    n = len(trades)
    src = trades.reset_index(drop=True)
    sign = np.where(src["direction"].astype(str).str.lower().str.startswith("l"), 1.0, -1.0)

    queen = src.copy()
    queen["leg"] = LEG_QUEEN
    queen["exit_time"] = src["leg1_exit_time"].to_numpy()
    queen["exit_price"] = src["leg1_exit_price"].to_numpy(dtype="float64")
    queen["points"] = src["leg1_points"].to_numpy(dtype="float64")
    # `exit_reason` on the source row describes how the POSITION closed, which is
    # the runner's exit. Carried onto the queen row unchanged it reads as a lie:
    # a queen that took its target while the runner later stopped out would be
    # labelled "Stop Loss" -- and exit-reason parity against NT8's `exitName` is
    # one of the checks this whole projection exists to make possible.
    if "queen_hit" in src.columns:
        queen["exit_reason"] = np.where(
            src["queen_hit"].to_numpy(dtype=bool),
            "Profit Target",
            src["exit_reason"].to_numpy())

    runner = src.copy()
    runner["leg"] = LEG_RUNNER
    runner["points"] = src["leg2_points"].to_numpy(dtype="float64")

    for frame in (queen, runner):
        frame["parent_trade"] = np.arange(n)

    out = pd.concat([queen, runner], ignore_index=True)
    out = out.sort_values(["parent_trade", "leg"], kind="mergesort").reset_index(drop=True)

    # The engine's aggregate columns describe the WHOLE trade and would be read
    # as this leg's if they survived. Drop rather than carry a lie.
    out = out.drop(columns=[c for c in ("leg1_points", "leg2_points", "total_points",
                                        "total_pnl_usd", "pnl_pct", "is_win",
                                        "cum_pnl", "equity", "leg1_exit_time",
                                        "leg1_exit_price")
                            if c in out.columns])

    if point_value is None:
        out["pnl"] = out["points"]
    else:
        per_leg_cost = commission_per_contract_rt + slippage_ticks * tick_size * point_value
        out["pnl"] = out["points"] * float(point_value) - per_leg_cost

    _assert_legs_reconstruct(src, out, sign)
    return out


def _assert_legs_reconstruct(src: pd.DataFrame, out: pd.DataFrame,
                             sign: np.ndarray) -> None:
    """The projection must be lossless in points, and it must be checked HERE.

    A silent arithmetic error in a projection surfaces later as a parity
    divergence and gets attributed to the strategy. Two invariants, both cheap:

      * per-leg points sum, per parent, to leg1+leg2 as recorded;
      * each leg's exit price agrees with its own points from the shared entry.

    `total_points` is NOT used as the reference: the engine records it as the
    MEAN of the two legs (`(q + r) / 2`, the per-contract average of a 2-lot
    pack), not their sum, and asserting against it would encode that averaging
    convention into the leg model.
    """
    grouped = out.groupby("parent_trade")["points"].sum().to_numpy(dtype="float64")
    expect = (src["leg1_points"].to_numpy(dtype="float64")
              + src["leg2_points"].to_numpy(dtype="float64"))
    bad = np.flatnonzero(~np.isclose(grouped, expect, atol=1e-9, equal_nan=True))
    if bad.size:
        raise AssertionError(
            "per-leg points do not sum to the recorded legs for {} trade(s); "
            "first at parent_trade={} ({} vs {})".format(
                bad.size, int(bad[0]), grouped[bad[0]], expect[bad[0]]))

    two_sign = np.repeat(sign, 2)
    implied = ((out["exit_price"].to_numpy(dtype="float64")
                - out["entry_price"].to_numpy(dtype="float64")) * two_sign)
    bad = np.flatnonzero(~np.isclose(implied, out["points"].to_numpy(dtype="float64"),
                                     atol=1e-6, equal_nan=True))
    if bad.size:
        raise AssertionError(
            "a leg's exit price disagrees with its own points for {} row(s); "
            "first at row {} (implied {} vs recorded {})".format(
                bad.size, int(bad[0]), implied[bad[0]],
                out["points"].to_numpy()[bad[0]]))
