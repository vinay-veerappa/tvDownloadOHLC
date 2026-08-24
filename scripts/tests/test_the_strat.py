"""Pytest suite for The Strat Python package."""

from datetime import datetime, time
import numpy as np
import pandas as pd
import pytest

from scripts.libs_py.the_strat.taxonomy import (
    ActionableWickType,
    StratBarInfo,
    StratType,
    classify_bar,
    classify_bars_df,
)
from scripts.libs_py.the_strat.ftfc import (
    Direction,
    FTFCEngine,
    FTFCResult,
)
from scripts.libs_py.the_strat.combos import (
    ComboType,
    StratComboDetector,
    StratSetup,
    TradeDirection,
)
from scripts.libs_py.the_strat.strategy import (
    StratBacktester,
    StratBacktestSummary,
)


class TestStratTaxonomy:
    """Test Strat candle taxonomy (1, 2U, 2D, 3) and wick logic."""

    def test_inside_bar_1(self):
        res = classify_bar(high=105.0, low=95.0, prev_high=110.0, prev_low=90.0)
        assert res.strat_type == StratType.INSIDE
        assert res.is_inside is True
        assert res.is_directional_up is False
        assert res.is_directional_down is False
        assert res.is_outside is False
        assert res.strat_type.display_name == "1"

    def test_two_up_bar_2u(self):
        res = classify_bar(high=115.0, low=95.0, prev_high=110.0, prev_low=90.0)
        assert res.strat_type == StratType.TWO_UP
        assert res.is_directional_up is True
        assert res.strat_type.display_name == "2U"

    def test_two_down_bar_2d(self):
        res = classify_bar(high=108.0, low=85.0, prev_high=110.0, prev_low=90.0)
        assert res.strat_type == StratType.TWO_DOWN
        assert res.is_directional_down is True
        assert res.strat_type.display_name == "2D"

    def test_outside_bar_3(self):
        res = classify_bar(high=115.0, low=85.0, prev_high=110.0, prev_low=90.0)
        assert res.strat_type == StratType.OUTSIDE
        assert res.is_outside is True
        assert res.strat_type.display_name == "3"

    def test_hammer_wick_actionable(self):
        # Open=108, Close=110, High=110, Low=90 -> Lower wick=18/20 = 90%
        res = classify_bar(
            high=110.0, low=90.0, prev_high=110.0, prev_low=90.0,
            open_price=108.0, close_price=110.0, wick_threshold=0.65
        )
        assert res.wick_type == ActionableWickType.HAMMER

    def test_shooter_wick_actionable(self):
        # Open=92, Close=90, High=110, Low=90 -> Upper wick=18/20 = 90%
        res = classify_bar(
            high=110.0, low=90.0, prev_high=110.0, prev_low=90.0,
            open_price=92.0, close_price=90.0, wick_threshold=0.65
        )
        assert res.wick_type == ActionableWickType.SHOOTER

    def test_vectorized_dataframe_classification(self):
        data = {
            "open": [100, 102, 104, 101, 108],
            "high": [105, 106, 105, 103, 115],
            "low":  [95,  96,  97,  90,  88],
            "close":[102, 104, 101, 91,  112],
        }
        df = pd.DataFrame(data)
        df_strat = classify_bars_df(df)

        assert "strat_type" in df_strat.columns
        assert "strat_label" in df_strat.columns
        # Bar 1 vs Bar 0: H=106 > 105, L=96 >= 95 -> 2U
        assert df_strat["strat_type"].iloc[1] == StratType.TWO_UP
        # Bar 2 vs Bar 1: H=105 <= 106, L=97 >= 96 -> 1
        assert df_strat["strat_type"].iloc[2] == StratType.INSIDE
        # Bar 3 vs Bar 2: H=103 <= 105, L=90 < 97 -> 2D
        assert df_strat["strat_type"].iloc[3] == StratType.TWO_DOWN
        # Bar 4 vs Bar 3: H=115 > 103, L=88 < 90 -> 3
        assert df_strat["strat_type"].iloc[4] == StratType.OUTSIDE


class TestStratFTFC:
    """Test Full Time Frame Continuity engine."""

    def test_ftfc_full_bullish(self):
        opens = {"5m": 100.0, "15m": 99.0, "1h": 98.0, "4h": 95.0, "D": 90.0, "W": 85.0}
        curr_price = 105.0
        result = FTFCEngine.compute_from_candles(curr_price, opens)

        assert result.bullish_count == 6
        assert result.bearish_count == 0
        assert result.is_full_continuity is True
        assert result.full_continuity == Direction.BULLISH
        assert result.dominant_bias == Direction.BULLISH
        assert result.score == 6

    def test_ftfc_full_bearish(self):
        opens = {"5m": 100.0, "15m": 102.0, "1h": 105.0, "4h": 110.0, "D": 115.0}
        curr_price = 98.0
        result = FTFCEngine.compute_from_candles(curr_price, opens)

        assert result.bullish_count == 0
        assert result.bearish_count == 5
        assert result.is_full_continuity is True
        assert result.full_continuity == Direction.BEARISH
        assert result.dominant_bias == Direction.BEARISH
        assert result.score == -5

    def test_ftfc_conflict_mixed(self):
        opens = {"5m": 102.0, "15m": 101.0, "1h": 98.0, "D": 95.0}
        curr_price = 100.0
        result = FTFCEngine.compute_from_candles(curr_price, opens)

        assert result.bullish_count == 2
        assert result.bearish_count == 2
        assert result.is_full_continuity is False
        assert result.score == 0
        assert result.dominant_bias == Direction.NEUTRAL


class TestStratCombosAndBacktest:
    """Test Strat Combos and Strategy execution."""

    def test_212_bullish_continuation_detection(self):
        data = {
            "open":  [100.0, 102.0, 105.0, 106.0],
            "high":  [105.0, 110.0, 108.0, 112.0],  # Bar 1: 2U (110>105), Bar 2: 1 (108<=110, 103>=101), Bar 3: 2U (112>108)
            "low":   [95.0,  101.0, 103.0, 104.0],
            "close": [102.0, 109.0, 106.0, 111.0],
        }
        df = pd.DataFrame(data)
        detector = StratComboDetector(tick_size=0.25)
        setups = detector.scan_dataframe(df, min_rr_ratio=0.0)

        assert len(setups) >= 1
        s = setups[0]
        assert s.combo_type == ComboType.BULLISH_212_CONT
        assert s.direction == TradeDirection.LONG
        assert s.entry_trigger_price == 108.25  # Inside bar high (108) + 0.25
        assert s.stop_loss_price == 102.75      # Inside bar low (103) - 0.25
        assert s.magnitude_1_target == 110.0    # Prior 2U high

    def test_22_bullish_reversal_detection(self):
        data = {
            "open":  [100.0, 98.0,  92.0],
            "high":  [105.0, 100.0, 102.0],  # Bar 1: 2D (90<95, 100<=105), Bar 2: 2U (102>100, 91>=90)
            "low":   [95.0,  90.0,  91.0],
            "close": [98.0,  92.0,  101.0],
        }
        df = pd.DataFrame(data)
        detector = StratComboDetector(tick_size=0.25)
        setups = detector.scan_dataframe(df, min_rr_ratio=0.0)

        assert len(setups) >= 1
        s = setups[0]
        assert s.combo_type == ComboType.BULLISH_22_REV
        assert s.direction == TradeDirection.LONG
        assert s.entry_trigger_price == 100.25  # Bar 1 high (100) + 0.25
        assert s.stop_loss_price == 89.75       # Bar 1 low (90) - 0.25

    def test_backtester_execution(self):
        bars = [
            {"open": 100, "high": 105, "low": 95, "close": 102},
            {"open": 102, "high": 110, "low": 101, "close": 109}, # 2U
            {"open": 109, "high": 108, "low": 103, "close": 106}, # 1 (inside)
            {"open": 106, "high": 112, "low": 104, "close": 111}, # 2U -> Triggers Long at 108.25, hits 110 target
            {"open": 111, "high": 113, "low": 108, "close": 112},
        ]
        df = pd.DataFrame(bars)
        bt = StratBacktester(point_value=20.0, slippage_ticks=0, commission_per_contract=0.0)
        summary = bt.run_backtest(df, min_rr_ratio=0.0, start_time_et=time(0, 0), end_time_et=time(23, 59))

        assert summary.total_trades >= 1
        assert summary.winning_trades >= 1
        assert summary.win_rate > 0.0
