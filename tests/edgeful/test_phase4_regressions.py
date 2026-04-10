import unittest

import pandas as pd

from scripts.edgeful.lib.session_tagger import tag_session
from scripts.edgeful.lib.trade_simulator import SimulationPolicy, STRATEGY_PRESETS, simulate_strategy
from scripts.ranges.compute_ranges import _build_range_record
from scripts.ranges.range_definitions import RANGE_PRESETS


class TestPhase4Regressions(unittest.TestCase):
    def test_session_tagger_day_of_week_uses_trading_date_rollover(self) -> None:
        idx = pd.DatetimeIndex(["2026-04-10 19:00:00"])
        df = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.1],
                "low": [0.9],
                "close": [1.0],
                "volume": [100],
            },
            index=idx,
        )

        out = tag_session(df.copy())
        self.assertEqual(str(out.iloc[0]["trading_date"]), "2026-04-13")
        self.assertEqual(int(out.iloc[0]["day_of_week"]), 0)

    def test_simulate_strategy_ambiguous_bar_default_split(self) -> None:
        rr = {
            "symbol": "NQ1",
            "range_name": "OR_5",
            "trading_date": "2024-01-02",
            "range_high": 100.0,
            "range_low": 99.0,
            "range_mid": 99.5,
            "range_width": 1.0,
        }

        post_bars = pd.DataFrame(
            {
                "open": [100.0],
                "high": [101.5],
                "low": [98.5],
                "close": [100.2],
                "volume": [1000],
            },
            index=pd.DatetimeIndex(["2024-01-02 09:31:00"]),
        )

        trade = simulate_strategy(
            post_bars,
            rr,
            STRATEGY_PRESETS["BO_1X"],
            pd.Timestamp("2024-01-02 09:30:00"),
        )

        self.assertIsNotNone(trade)
        self.assertEqual(trade.exit_reason, "AMBIGUOUS_SPLIT")
        self.assertEqual(trade.exit_bar_check_order, "AMBIGUOUS_BOTH")
        self.assertTrue(trade.ambiguous_bar)
        self.assertEqual(trade.exit_price, 100.0)

    def test_simulate_strategy_ambiguous_bar_stop_first_policy(self) -> None:
        rr = {
            "symbol": "NQ1",
            "range_name": "OR_5",
            "trading_date": "2024-01-02",
            "range_high": 100.0,
            "range_low": 99.0,
            "range_mid": 99.5,
            "range_width": 1.0,
        }

        post_bars = pd.DataFrame(
            {
                "open": [100.0],
                "high": [101.5],
                "low": [98.5],
                "close": [100.2],
                "volume": [1000],
            },
            index=pd.DatetimeIndex(["2024-01-02 09:31:00"]),
        )

        trade = simulate_strategy(
            post_bars,
            rr,
            STRATEGY_PRESETS["BO_1X"],
            pd.Timestamp("2024-01-02 09:30:00"),
            policy=SimulationPolicy(ambiguous_bar_resolution="STOP_FIRST"),
        )

        self.assertIsNotNone(trade)
        self.assertEqual(trade.exit_reason, "AMBIGUOUS_STOP_FIRST")
        self.assertEqual(trade.exit_price, 99.0)

    def test_build_range_record_includes_intrinsic_day_of_week(self) -> None:
        rdef = RANGE_PRESETS["OR_5"]
        rng_row = pd.Series(
            {
                "range_high": 100.0,
                "range_low": 99.0,
                "range_mid": 99.5,
                "range_width": 1.0,
                "range_width_pct": 1.0,
                "range_open": 99.2,
                "range_close": 99.8,
                "bar_count": 5,
            }
        )
        day_bars = pd.DataFrame(
            {
                "open": [99.5, 99.8, 100.2],
                "high": [99.9, 100.3, 100.5],
                "low": [99.4, 99.7, 99.9],
                "close": [99.8, 100.2, 100.4],
                "volume": [100, 120, 130],
            },
            index=pd.DatetimeIndex(["2024-01-05 09:35:00", "2024-01-05 09:36:00", "2024-01-05 09:37:00"]),
        )

        rec = _build_range_record("NQ1", rdef, "2024-01-05", rng_row, day_bars)
        self.assertIn("day_of_week", rec)
        self.assertEqual(rec["day_of_week"], 4)


if __name__ == "__main__":
    unittest.main()
