"""Python must count trades the way NT8 counts them: one row per LEG.

NT8 reported `entries: 6, totalTrades: 12` for a 2-contract queen/runner bot.
Python returned one row per entry. Compared as-is, trade-set recall reads ~50%
on every bracket strategy for a reason that has nothing to do with the strategy.

These tests hold the projection to being LOSSLESS and HONEST, not merely to
producing two rows. The interesting failures are the quiet ones: a queen exit
inherited from the previous trade, an aggregate column surviving onto a leg row
and being read as that leg's, or an exit reason describing the position rather
than the leg.
"""
import numpy as np
import pandas as pd
import pytest

from scripts.parity.legs import explode_legs, LEG_QUEEN, LEG_RUNNER


def _trade(direction="Long", entry=100.0, leg1=2.0, leg2=5.0,
           entry_t="2026-03-02 10:00", queen_t="2026-03-02 10:05",
           exit_t="2026-03-02 10:30", reason="Profit Target", queen_hit=True):
    sign = 1.0 if direction == "Long" else -1.0
    return {
        "entry_time": pd.Timestamp(entry_t),
        "exit_time": pd.Timestamp(exit_t),
        "direction": direction,
        "entry_price": entry,
        "exit_price": entry + leg2 * sign,
        "leg1_points": leg1,
        "leg2_points": leg2,
        "total_points": (leg1 + leg2) / 2.0,
        "total_pnl_usd": 999.0,
        "exit_reason": reason,
        "queen_hit": queen_hit,
        "runner_hit": True,
        "leg1_exit_time": pd.Timestamp(queen_t),
        "leg1_exit_price": entry + leg1 * sign,
    }


def _frame(*rows):
    return pd.DataFrame(list(rows))


def test_one_trade_becomes_two_rows():
    out = explode_legs(_frame(_trade()))
    assert len(out) == 2
    assert list(out["leg"]) == [LEG_QUEEN, LEG_RUNNER]
    assert out["parent_trade"].tolist() == [0, 0]


def test_legs_share_the_entry_and_differ_in_the_exit():
    out = explode_legs(_frame(_trade()))
    assert out["entry_time"].nunique() == 1
    assert out["entry_price"].nunique() == 1
    assert out["direction"].nunique() == 1
    assert out.loc[0, "exit_time"] < out.loc[1, "exit_time"]
    assert out.loc[0, "exit_price"] != out.loc[1, "exit_price"]


@pytest.mark.parametrize("direction,leg1,leg2", [
    ("Long", 2.0, 5.0),
    ("Long", -3.0, -3.0),
    ("Short", 2.0, 5.0),
    ("Short", -3.0, -3.0),
    ("Short", 4.0, -1.0),      # queen took profit, runner gave it back
])
def test_each_leg_price_agrees_with_its_own_points(direction, leg1, leg2):
    """The invariant that makes the projection safe in BOTH directions.

    Signed points travelled must reconstruct from the leg's own entry and exit --
    the same quantity trade-set parity judges on. A sign error here would show up
    later as a geometry divergence and be blamed on the strategy.
    """
    out = explode_legs(_frame(_trade(direction=direction, leg1=leg1, leg2=leg2)))
    sign = 1.0 if direction == "Long" else -1.0
    implied = (out["exit_price"] - out["entry_price"]) * sign
    assert np.allclose(implied.to_numpy(), out["points"].to_numpy())
    assert out["points"].sum() == pytest.approx(leg1 + leg2)


def test_a_queen_that_never_filled_leaves_with_the_runner():
    """Both legs stopped together: same exit time, and no earlier phantom exit."""
    t = _trade(leg1=-3.0, leg2=-3.0, queen_t="2026-03-02 10:30",
               exit_t="2026-03-02 10:30", reason="Stop Loss", queen_hit=False)
    out = explode_legs(_frame(t))
    assert out.loc[0, "exit_time"] == out.loc[1, "exit_time"]
    assert set(out["exit_reason"]) == {"Stop Loss"}


def test_the_queens_exit_reason_is_its_own_not_the_positions():
    """A queen that took profit while the runner stopped out is not a Stop Loss.

    The source row's `exit_reason` describes how the POSITION closed. Carried
    onto the queen row it mislabels the leg, and exit-reason parity against NT8's
    `exitName` is one of the checks this projection exists to enable.
    """
    t = _trade(leg1=4.0, leg2=-2.0, reason="Stop Loss", queen_hit=True)
    out = explode_legs(_frame(t))
    assert out.loc[0, "exit_reason"] == "Profit Target"
    assert out.loc[1, "exit_reason"] == "Stop Loss"


def test_aggregate_columns_do_not_survive_onto_a_leg_row():
    """`total_pnl_usd` on a leg row would be silently read as that leg's money."""
    out = explode_legs(_frame(_trade()))
    for col in ("total_pnl_usd", "total_points", "leg1_points", "leg2_points",
                "leg1_exit_time", "leg1_exit_price"):
        assert col not in out.columns, col


def test_pnl_is_points_until_a_point_value_is_supplied():
    """No guessed multiplier. An engine here once used NQ's for every instrument."""
    out = explode_legs(_frame(_trade()))
    assert np.allclose(out["pnl"].to_numpy(), out["points"].to_numpy())

    priced = explode_legs(_frame(_trade()), point_value=20.0,
                          commission_per_contract_rt=1.40)
    assert np.allclose(priced["pnl"].to_numpy(),
                       priced["points"].to_numpy() * 20.0 - 1.40)


def test_a_frame_without_a_queen_exit_is_refused_by_name():
    """An engine predating the convention must not be silently filled in."""
    df = _frame(_trade()).drop(columns=["leg1_exit_time"])
    with pytest.raises(KeyError) as exc:
        explode_legs(df)
    assert "leg1_exit_time" in str(exc.value)


def test_an_inconsistent_leg_is_caught_here_not_in_the_parity_report():
    """A projection error must fail at the projection, not surface as divergence."""
    df = _frame(_trade())
    df.loc[0, "leg1_exit_price"] = 12345.0        # disagrees with leg1_points
    with pytest.raises(AssertionError) as exc:
        explode_legs(df)
    assert "exit price disagrees" in str(exc.value)


def test_many_trades_keep_their_own_queen_exits():
    """The reset bug this guards: a trade whose queen never fills must not
    inherit the PREVIOUS trade's queen exit time."""
    rows = [
        _trade(entry_t="2026-03-02 10:00", queen_t="2026-03-02 10:05",
               exit_t="2026-03-02 10:30", queen_hit=True),
        _trade(entry_t="2026-03-02 11:00", queen_t="2026-03-02 11:20",
               exit_t="2026-03-02 11:20", leg1=-3.0, leg2=-3.0,
               reason="Stop Loss", queen_hit=False),
    ]
    out = explode_legs(_frame(*rows))
    assert len(out) == 4
    second = out[out["parent_trade"] == 1]
    assert (second["exit_time"] == pd.Timestamp("2026-03-02 11:20")).all()
    assert (second["exit_time"] > rows[0]["exit_time"]).all()


def test_empty_in_empty_out_with_the_leg_columns_present():
    """A column-less empty frame is unreadable, not empty."""
    empty = _frame(_trade()).iloc[0:0]
    out = explode_legs(empty)
    assert out.empty
    assert "leg" in out.columns and "parent_trade" in out.columns


def test_the_engine_actually_emits_a_queen_exit_time():
    """Ties the projection to the real engine.

    Every test above uses hand-built rows, so all of them would still pass if the
    engine never recorded `leg1_exit_time` at all. This one runs the compiled
    kernel and asserts the field arrives, is populated, and is never later than
    the position's exit.
    """
    pytest.importorskip("nt8_parity_core")
    from scripts.execution.nt8_parity_engine import NT8ParityEngine

    rng = np.random.default_rng(7)
    n = 3000
    idx = pd.date_range("2026-03-02 09:30", periods=n, freq="1min",
                        tz="America/New_York")
    px = 20000 + np.cumsum(rng.normal(0, 3.0, n))
    df = pd.DataFrame({"open": px, "high": px + rng.uniform(0.5, 6, n),
                       "low": px - rng.uniform(0.5, 6, n),
                       "close": px + rng.normal(0, 1, n), "volume": 100.0},
                      index=idx)
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    sig = pd.Series(0, index=idx)
    sig.iloc[::137] = np.where(rng.random(len(sig.iloc[::137])) > 0.5, 1, -1)
    sl = df["close"] * (1 - 0.0025 * np.where(sig.to_numpy() >= 0, 1, -1))

    trades = NT8ParityEngine(point_value=20.0, contracts=2).simulate(
        df, sig, df["close"], sl)
    assert not trades.empty, "fixture produced no trades; the assertions below would be vacuous"
    assert "leg1_exit_time" in trades.columns
    assert trades["leg1_exit_time"].notna().all()
    assert (trades["leg1_exit_time"] <= trades["exit_time"]).all()

    legs = explode_legs(trades, point_value=20.0)
    assert len(legs) == 2 * len(trades)
