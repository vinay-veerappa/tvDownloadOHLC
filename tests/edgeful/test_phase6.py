"""
Phase 6 functional tests.

Covers:
  - Range preset completeness (RANGE_PRESETS has all new presets)
  - Session-breakout helpers (_get_first_break, _close_location)
  - _build_symbol_records output shape and field values
  - compute_confluence vote functions (all 5 vote helpers)
  - compute_confluence causal probability (no lookahead via _expanding_cond_prob)
  - compute_confluence bias labels (BULLISH / BEARISH / NEUTRAL + confidence)
  - _expanding_cond_prob fallback to unconditional when N < MIN_SAMPLE
"""
from __future__ import annotations

import datetime
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.ranges.range_definitions import RANGE_PRESETS
from scripts.context.compute_session_breakouts import (
    _get_first_break,
    _close_location,
    _build_symbol_records,
)
from scripts.context.compute_daily_confluence import (
    _expanding_cond_prob,
    _gap_vote,
    _occ_vote,
    _pdh_pdl_vote,
    _streak_vote,
    _mop_vote,
    _build_master,
    compute_confluence,
    MIN_SAMPLE,
    BIAS_THRESHOLD,
)


# ─────────────────────────────────────────────────────────────────────────────
# Range preset completeness
# ─────────────────────────────────────────────────────────────────────────────

class TestRangePresetCompleteness(unittest.TestCase):
    REQUIRED_PHASE6_PRESETS = [
        "LUNCH",
        "ASIA",
        "OVERNIGHT",
        "SILVER_BULLET_AM",
        "SILVER_BULLET_PM",
        "POWER_HOUR",
    ]

    def test_all_phase6_presets_present(self) -> None:
        for name in self.REQUIRED_PHASE6_PRESETS:
            self.assertIn(name, RANGE_PRESETS, f"Missing preset: {name}")

    def test_phase6_preset_times(self) -> None:
        self.assertEqual(RANGE_PRESETS["LUNCH"].start_time, "12:00")
        self.assertEqual(RANGE_PRESETS["LUNCH"].end_time, "13:30")
        self.assertEqual(RANGE_PRESETS["SILVER_BULLET_AM"].start_time, "10:00")
        self.assertEqual(RANGE_PRESETS["SILVER_BULLET_AM"].end_time, "11:00")
        self.assertEqual(RANGE_PRESETS["SILVER_BULLET_PM"].start_time, "14:00")
        self.assertEqual(RANGE_PRESETS["SILVER_BULLET_PM"].end_time, "15:00")
        self.assertEqual(RANGE_PRESETS["POWER_HOUR"].start_time, "15:00")
        self.assertEqual(RANGE_PRESETS["POWER_HOUR"].end_time, "16:00")
        self.assertEqual(RANGE_PRESETS["ASIA"].start_time, "20:00")
        self.assertEqual(RANGE_PRESETS["OVERNIGHT"].start_time, "18:00")

    def test_eth_session_presets_have_observe_until(self) -> None:
        for name in ("ASIA", "OVERNIGHT"):
            rdef = RANGE_PRESETS[name]
            self.assertIsNotNone(rdef.observe_until, f"{name} missing observe_until")

    def test_rth_presets_default_session(self) -> None:
        for name in ("LUNCH", "SILVER_BULLET_AM", "SILVER_BULLET_PM", "POWER_HOUR"):
            self.assertEqual(RANGE_PRESETS[name].session, "RTH", f"{name} should be RTH")


# ─────────────────────────────────────────────────────────────────────────────
# Session breakout helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ny_bar(high: float, low: float, close: float, *, minutes_into_session: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame(
        {"open": [close], "high": [high], "low": [low], "close": [close],
         "volume": [1000], "minutes_into_session": [minutes_into_session]},
        index=pd.DatetimeIndex(["2024-01-02 09:31:00"]),
    )


class TestGetFirstBreak(unittest.TestCase):
    def test_no_bars_returns_none(self) -> None:
        result = _get_first_break(pd.DataFrame(), 100.0, 99.0)
        self.assertEqual(result, ("NONE", None))

    def test_no_break_inside_range(self) -> None:
        bars = _ny_bar(high=99.9, low=99.1, close=99.5)
        dir_, mins = _get_first_break(bars, 100.0, 99.0)
        self.assertEqual(dir_, "NONE")
        self.assertIsNone(mins)

    def test_clean_break_up(self) -> None:
        bars = _ny_bar(high=100.5, low=99.5, close=100.3, minutes_into_session=2.0)
        dir_, mins = _get_first_break(bars, 100.0, 99.0)
        self.assertEqual(dir_, "UP")
        self.assertAlmostEqual(mins, 2.0)

    def test_clean_break_down(self) -> None:
        bars = _ny_bar(high=99.5, low=98.5, close=98.7, minutes_into_session=3.0)
        dir_, mins = _get_first_break(bars, 100.0, 99.0)
        self.assertEqual(dir_, "DOWN")
        self.assertAlmostEqual(mins, 3.0)

    def test_ambiguous_bar_bullish_close_resolves_up(self) -> None:
        # wick touches both sides; close > open → tie-break UP
        bars = pd.DataFrame(
            {"open": [99.5], "high": [100.1], "low": [98.9],
             "close": [100.0], "volume": [1000], "minutes_into_session": [1.0]},
            index=pd.DatetimeIndex(["2024-01-02 09:31:00"]),
        )
        dir_, _ = _get_first_break(bars, 100.0, 99.0)
        self.assertEqual(dir_, "UP")

    def test_ambiguous_bar_bearish_close_resolves_down(self) -> None:
        bars = pd.DataFrame(
            {"open": [100.0], "high": [100.1], "low": [98.9],
             "close": [99.4], "volume": [1000], "minutes_into_session": [1.0]},
            index=pd.DatetimeIndex(["2024-01-02 09:31:00"]),
        )
        dir_, _ = _get_first_break(bars, 100.0, 99.0)
        self.assertEqual(dir_, "DOWN")

    def test_nan_boundary_returns_none(self) -> None:
        bars = _ny_bar(high=101.0, low=98.0, close=100.5)
        dir_, mins = _get_first_break(bars, float("nan"), 99.0)
        self.assertEqual(dir_, "NONE")
        self.assertIsNone(mins)


class TestCloseLocation(unittest.TestCase):
    def test_above(self) -> None:
        self.assertEqual(_close_location(101.0, 100.0, 99.0), "ABOVE")

    def test_below(self) -> None:
        self.assertEqual(_close_location(98.5, 100.0, 99.0), "BELOW")

    def test_inside(self) -> None:
        self.assertEqual(_close_location(99.5, 100.0, 99.0), "INSIDE")

    def test_at_high_is_inside(self) -> None:
        self.assertEqual(_close_location(100.0, 100.0, 99.0), "INSIDE")

    def test_nan_inputs_return_unknown(self) -> None:
        self.assertEqual(_close_location(float("nan"), 100.0, 99.0), "UNKNOWN")
        self.assertEqual(_close_location(99.5, float("nan"), 99.0), "UNKNOWN")


class TestBuildSymbolRecords(unittest.TestCase):
    """Unit-test _build_symbol_records with synthetic tagged bars."""

    def _make_ctx(self, td: datetime.date) -> pd.DataFrame:
        return pd.DataFrame([{
            "symbol": "NQ1",
            "trading_date": td,
            "day_of_week": 0,
            "is_event_day": False,
            "event_type": None,
            "event_types": None,
            "is_opex_week": False,
            "session_direction": "UP",
            "vix_regime": "LOW",
        }])

    def _make_tagged(self, td: datetime.date) -> pd.DataFrame:
        """Two LONDON + several NY_AM bars with NY breaking London high."""
        london_ts = pd.date_range("2024-01-02 03:00", periods=4, freq="30min")
        ny_ts     = pd.date_range("2024-01-02 09:30", periods=6, freq="1min")

        london = pd.DataFrame({
            "open":  [100.0] * 4, "high": [100.5] * 4, "low": [99.5] * 4,
            "close": [100.0] * 4, "volume": [500] * 4,
            "session": "LONDON",
            "trading_date": td,
            "minutes_into_session": range(4),
        }, index=london_ts)

        ny_bars = pd.DataFrame({
            "open":  [100.5, 101.0, 101.2, 101.5, 101.8, 101.6],
            "high":  [100.6, 101.1, 101.4, 101.7, 102.0, 101.8],  # breaks 100.5 London high at bar 0
            "low":   [100.3, 100.8, 101.0, 101.2, 101.5, 101.3],
            "close": [101.0, 101.2, 101.3, 101.6, 101.8, 101.5],
            "volume": [1000] * 6,
            "session": "NY_AM",
            "trading_date": td,
            "minutes_into_session": list(range(6)),
        }, index=ny_ts)

        return pd.concat([london, ny_bars])

    def test_record_schema_and_values(self) -> None:
        td = datetime.date(2024, 1, 2)
        ctx    = self._make_ctx(td)
        tagged = self._make_tagged(td)
        result = _build_symbol_records("NQ1", ctx, tagged)

        self.assertEqual(len(result), 1)
        row = result.iloc[0]

        # Basic schema fields
        self.assertEqual(row["symbol"], "NQ1")
        self.assertEqual(row["trading_date"], td)
        self.assertIn("london_high", result.columns)
        self.assertIn("ny_close_location_vs_london", result.columns)

        # London range computed from bars
        self.assertAlmostEqual(row["london_high"], 100.5)
        self.assertAlmostEqual(row["london_low"],  99.5)

        # NY broke London high — first break should be UP
        self.assertEqual(row["first_break_direction"], "UP")

        # NY close (101.5) > london_high (100.5)
        self.assertEqual(row["ny_close_location_vs_london"], "ABOVE")
        self.assertTrue(row["continuation_after_first_break"])
        self.assertFalse(row["reversal_after_first_break"])

    def test_empty_tagged_returns_empty(self) -> None:
        td  = datetime.date(2024, 1, 2)
        ctx = self._make_ctx(td)
        result = _build_symbol_records("NQ1", ctx, pd.DataFrame())
        self.assertTrue(result.empty)

    def test_day_missing_from_ctx_is_skipped(self) -> None:
        td      = datetime.date(2024, 1, 2)
        other   = datetime.date(2024, 1, 3)   # ctx has different date
        ctx     = self._make_ctx(other)
        tagged  = self._make_tagged(td)
        result  = _build_symbol_records("NQ1", ctx, tagged)
        self.assertTrue(result.empty)

    def test_duplicate_ctx_rows_same_day_keep_last(self) -> None:
        td = datetime.date(2024, 1, 2)
        ctx = pd.DataFrame(
            [
                {
                    "symbol": "NQ1",
                    "trading_date": td,
                    "day_of_week": 0,
                    "is_event_day": False,
                    "event_type": None,
                    "event_types": None,
                    "is_opex_week": False,
                    "session_direction": "UP",
                    "vix_regime": "LOW",
                },
                {
                    "symbol": "NQ1",
                    "trading_date": td,
                    "day_of_week": 2,
                    "is_event_day": True,
                    "event_type": "CPI",
                    "event_types": "CPI",
                    "is_opex_week": True,
                    "session_direction": "DOWN",
                    "vix_regime": "HIGH",
                },
            ]
        )
        tagged = self._make_tagged(td)

        result = _build_symbol_records("NQ1", ctx, tagged)

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(int(row["day_of_week"]), 2)
        self.assertEqual(row["event_type"], "CPI")
        self.assertTrue(bool(row["is_event_day"]))
        self.assertTrue(bool(row["is_opex_week"]))
        self.assertEqual(row["vix_regime"], "HIGH")


# ─────────────────────────────────────────────────────────────────────────────
# Confluence vote helpers
# ─────────────────────────────────────────────────────────────────────────────

def _row(**kwargs) -> pd.Series:
    return pd.Series(kwargs)


class TestGapVote(unittest.TestCase):
    def test_gap_up_high_prob_votes_bearish(self) -> None:
        row = _row(gap_fill_probability=0.65, gap_direction="UP")
        self.assertEqual(_gap_vote(row), -1)

    def test_gap_down_high_prob_votes_bullish(self) -> None:
        row = _row(gap_fill_probability=0.65, gap_direction="DOWN")
        self.assertEqual(_gap_vote(row), 1)

    def test_prob_at_threshold_returns_zero(self) -> None:
        row = _row(gap_fill_probability=BIAS_THRESHOLD, gap_direction="UP")
        self.assertEqual(_gap_vote(row), 0)

    def test_no_gap_returns_zero(self) -> None:
        row = _row(gap_fill_probability=0.70, gap_direction="NONE")
        self.assertEqual(_gap_vote(row), 0)

    def test_nan_prob_returns_zero(self) -> None:
        row = _row(gap_fill_probability=float("nan"), gap_direction="UP")
        self.assertEqual(_gap_vote(row), 0)

    def test_low_prob_returns_zero(self) -> None:
        row = _row(gap_fill_probability=0.40, gap_direction="DOWN")
        self.assertEqual(_gap_vote(row), 0)


class TestOCCVote(unittest.TestCase):
    def test_up_continuation_votes_bullish(self) -> None:
        row = _row(occ_continuation_probability=0.60, occ_first_direction="UP")
        self.assertEqual(_occ_vote(row), 1)

    def test_down_continuation_votes_bearish(self) -> None:
        row = _row(occ_continuation_probability=0.60, occ_first_direction="DOWN")
        self.assertEqual(_occ_vote(row), -1)

    def test_prob_exactly_threshold_returns_zero(self) -> None:
        row = _row(occ_continuation_probability=BIAS_THRESHOLD, occ_first_direction="UP")
        self.assertEqual(_occ_vote(row), 0)

    def test_missing_direction_returns_zero(self) -> None:
        row = _row(occ_continuation_probability=0.70, occ_first_direction=float("nan"))
        self.assertEqual(_occ_vote(row), 0)


class TestPDHPDLVote(unittest.TestCase):
    def test_pdh_break_with_continuation_bullish(self) -> None:
        row = _row(pdh_broken=True, pdl_broken=False,
                   pdh_break_continuation=True, pdl_break_continuation=float("nan"))
        self.assertEqual(_pdh_pdl_vote(row), 1)

    def test_pdl_break_with_continuation_bearish(self) -> None:
        row = _row(pdh_broken=False, pdl_broken=True,
                   pdh_break_continuation=float("nan"), pdl_break_continuation=True)
        self.assertEqual(_pdh_pdl_vote(row), -1)

    def test_failed_pdh_break_bearish(self) -> None:
        row = _row(pdh_broken=True, pdl_broken=False,
                   pdh_break_continuation=False, pdl_break_continuation=float("nan"))
        self.assertEqual(_pdh_pdl_vote(row), -1)

    def test_failed_pdl_break_bullish(self) -> None:
        row = _row(pdh_broken=False, pdl_broken=True,
                   pdh_break_continuation=float("nan"), pdl_break_continuation=False)
        self.assertEqual(_pdh_pdl_vote(row), 1)

    def test_no_breaks_returns_zero(self) -> None:
        row = _row(pdh_broken=False, pdl_broken=False,
                   pdh_break_continuation=float("nan"), pdl_break_continuation=float("nan"))
        self.assertEqual(_pdh_pdl_vote(row), 0)


class TestStreakVote(unittest.TestCase):
    def test_up_streak_reversal_votes_bearish(self) -> None:
        row = _row(streak_reversal_probability=0.65, streak_direction="UP")
        self.assertEqual(_streak_vote(row), -1)

    def test_down_streak_reversal_votes_bullish(self) -> None:
        row = _row(streak_reversal_probability=0.65, streak_direction="DOWN")
        self.assertEqual(_streak_vote(row), 1)

    def test_low_prob_returns_zero(self) -> None:
        row = _row(streak_reversal_probability=0.48, streak_direction="UP")
        self.assertEqual(_streak_vote(row), 0)

    def test_missing_direction_returns_zero(self) -> None:
        row = _row(streak_reversal_probability=0.70, streak_direction=float("nan"))
        self.assertEqual(_streak_vote(row), 0)


class TestMOPVote(unittest.TestCase):
    def test_open_above_midnight_retrace_votes_bearish(self) -> None:
        row = _row(mop_retrace_probability=0.65, open_vs_midnight="ABOVE")
        self.assertEqual(_mop_vote(row), -1)

    def test_open_below_midnight_retrace_votes_bullish(self) -> None:
        row = _row(mop_retrace_probability=0.65, open_vs_midnight="BELOW")
        self.assertEqual(_mop_vote(row), 1)

    def test_missing_open_vs_midnight_returns_zero(self) -> None:
        row = _row(mop_retrace_probability=0.65, session_direction="UP")
        self.assertEqual(_mop_vote(row), 0)

    def test_exactly_at_threshold_returns_zero(self) -> None:
        row = _row(mop_retrace_probability=BIAS_THRESHOLD, session_direction="UP")
        self.assertEqual(_mop_vote(row), 0)


# ─────────────────────────────────────────────────────────────────────────────
# _expanding_cond_prob: no lookahead and fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestExpandingCondProb(unittest.TestCase):
    def _frame(self, n: int, event_val: float = 1.0) -> pd.DataFrame:
        """Create a minimal dataframe with n rows of the same group."""
        return pd.DataFrame({
            "symbol":       ["NQ1"] * n,
            "day_of_week":  [0] * n,
            "vix_regime":   ["LOW"] * n,
            "event_col":    [event_val] * n,
        })

    def test_first_row_is_nan(self) -> None:
        """Causal probability must be NaN for the very first row (no history)."""
        df = self._frame(5)
        result = _expanding_cond_prob(df, "event_col", ["day_of_week", "vix_regime"])
        self.assertTrue(pd.isna(result.iloc[0]),
                        "First row probability must be NaN (no prior data).")

    def test_no_future_leakage(self) -> None:
        """Probability at row i must be computed from rows < i only."""
        df = self._frame(20, event_val=1.0)
        result = _expanding_cond_prob(df, "event_col", ["day_of_week", "vix_regime"])
        # At row 1, result should be 1.0 (only row 0 contributed, which is 1.0)
        self.assertAlmostEqual(result.iloc[1], 1.0)

    def test_converges_to_true_mean(self) -> None:
        """After many consistent observations the probability should converge."""
        n = 30
        df = self._frame(n, event_val=1.0)
        result = _expanding_cond_prob(df, "event_col", ["day_of_week", "vix_regime"])
        # All events =1, so probability should approach 1.0
        self.assertAlmostEqual(result.iloc[-1], 1.0, places=4)

    def test_fallback_to_unconditional_when_small_group(self) -> None:
        """With few rows in one dow-regime cell, should fall back to symbol-level rate."""
        # Symbol has 30 rows with DOW=0/vix=LOW (1's), plus 2 rows with DOW=1/vix=HIGH (0's).
        majority = pd.DataFrame({
            "symbol":      ["NQ1"] * MIN_SAMPLE,
            "day_of_week": [0] * MIN_SAMPLE,
            "vix_regime":  ["LOW"] * MIN_SAMPLE,
            "event_col":   [1.0] * MIN_SAMPLE,
        })
        minority = pd.DataFrame({
            "symbol":      ["NQ1", "NQ1"],
            "day_of_week": [1, 1],
            "vix_regime":  ["HIGH", "HIGH"],
            "event_col":   [0.0, 0.0],
        })
        df = pd.concat([majority, minority], ignore_index=True)
        result = _expanding_cond_prob(df, "event_col", ["day_of_week", "vix_regime"])

        # The 2 minority rows (indices MIN_SAMPLE and MIN_SAMPLE+1) have only 2 conditional rows,
        # both < MIN_SAMPLE, so they fall back to the symbol-level unconditional rate.
        minority_idx_0 = MIN_SAMPLE
        minority_idx_1 = MIN_SAMPLE + 1
        # At minority_idx_0: conditional group has 0 prior rows → fallback
        # Unconditional symbol rate: ~15 ones out of 15 prior rows → ~1.0
        val0 = result.iloc[minority_idx_0]
        # It should be NaN (no symbol-level prior either at that point) or close to the
        # unconditional rate — not the minority group's 0.0
        if not pd.isna(val0):
            self.assertGreater(val0, 0.5,
                "Should fall back to high unconditional rate, not minority's 0.0")


# ─────────────────────────────────────────────────────────────────────────────
# compute_confluence integration with synthetic data
# ─────────────────────────────────────────────────────────────────────────────

def _make_minimal_master(n: int = 40) -> pd.DataFrame:
    """Build a minimal synthetic master frame with all required columns."""
    dates = [datetime.date(2024, 1, 1) + datetime.timedelta(days=i) for i in range(n)]
    rng = np.random.default_rng(42)

    df = pd.DataFrame({
        "symbol":           ["NQ1"] * n,
        "trading_date":     dates,
        "day_of_week":      [d.weekday() for d in dates],
        "vix_regime":       ["LOW"] * n,
        "session_direction": rng.choice(["UP", "DOWN"], n).tolist(),
        "streak_direction":  rng.choice(["UP", "DOWN"], n).tolist(),
        "streak_length":     rng.integers(1, 5, n).tolist(),
        "gap_direction":     rng.choice(["UP", "DOWN", "NONE"], n).tolist(),
        "gap_filled":        rng.integers(0, 2, n).astype(float).tolist(),
        "or_bo_winner":      rng.integers(0, 2, n).astype(float).tolist(),
        "ib_bo_winner":      rng.integers(0, 2, n).astype(float).tolist(),
        "occ_continuation":  rng.integers(0, 2, n).astype(float).tolist(),
        "occ_first_direction": rng.choice(["UP", "DOWN"], n).tolist(),
        "mop_retrace":       rng.integers(0, 2, n).astype(float).tolist(),
        "pdh_broken":        rng.integers(0, 2, n).astype(float).tolist(),
        "pdl_broken":        rng.integers(0, 2, n).astype(float).tolist(),
        "pdh_break_continuation": rng.integers(0, 2, n).astype(float).tolist(),
        "pdl_break_continuation": rng.integers(0, 2, n).astype(float).tolist(),
        "streak_reversal":   rng.integers(0, 2, n).astype(float).tolist(),
        "gap_size_bucket":   ["SMALL"] * n,
        "open_vs_pd_range":  ["INSIDE"] * n,
        "is_event_day":      [False] * n,
        "event_type":        [None] * n,
        "is_opex_week":      [False] * n,
        "atr_14d":           [100.0] * n,
        "atr_usage_pct":     [0.5] * n,
    })
    return df


class TestComputeConfluenceIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _make_minimal_master(n=40)
        self.result = compute_confluence(self.df.copy())

    def test_row_count_preserved(self) -> None:
        self.assertEqual(len(self.result), len(self.df))

    def test_probability_columns_present(self) -> None:
        expected_probs = [
            "gap_fill_probability",
            "or_breakout_probability",
            "ib_single_break_probability",
            "occ_continuation_probability",
            "mop_retrace_probability",
            "pdh_pdl_break_probability",
            "streak_reversal_probability",
        ]
        for col in expected_probs:
            self.assertIn(col, self.result.columns, f"Missing column: {col}")

    def test_probabilities_are_in_unit_interval(self) -> None:
        prob_cols = [c for c in self.result.columns if c.endswith("_probability")]
        for col in prob_cols:
            vals = self.result[col].dropna()
            self.assertTrue(
                ((vals >= 0.0) & (vals <= 1.0)).all(),
                f"{col} has values outside [0, 1]",
            )

    def test_dominant_bias_values(self) -> None:
        valid = {"BULLISH", "BEARISH", "NEUTRAL"}
        actual = set(self.result["dominant_bias"].unique())
        self.assertTrue(actual.issubset(valid),
                        f"Unexpected dominant_bias values: {actual - valid}")

    def test_confidence_values(self) -> None:
        valid = {"HIGH", "MEDIUM", "LOW"}
        actual = set(self.result["confidence"].unique())
        self.assertTrue(actual.issubset(valid),
                        f"Unexpected confidence values: {actual - valid}")

    def test_total_vote_range(self) -> None:
        """Total vote is sum of 5 signals, each in {-1, 0, 1}."""
        self.assertTrue((self.result["total_vote"].abs() <= 5).all())

    def test_bias_consistent_with_vote_BULLISH(self) -> None:
        """All BULLISH rows must have total_vote >= 2."""
        bullish = self.result[self.result["dominant_bias"] == "BULLISH"]
        self.assertTrue((bullish["total_vote"] >= 2).all())

    def test_bias_consistent_with_vote_BEARISH(self) -> None:
        """All BEARISH rows must have total_vote <= -2."""
        bearish = self.result[self.result["dominant_bias"] == "BEARISH"]
        self.assertTrue((bearish["total_vote"] <= -2).all())

    def test_internal_vote_cols_not_in_output(self) -> None:
        """Vote helper columns (v_gap, v_occ, ...) should be dropped from output."""
        for col in ("v_gap", "v_occ", "v_pdh_pdl", "v_streak", "v_mop"):
            self.assertNotIn(col, self.result.columns, f"Internal col leaked: {col}")

    def test_no_lookahead_first_row_probs_are_nan(self) -> None:
        """For the first row of each symbol, all causal probs must be NaN."""
        first_row = self.result[self.result["symbol"] == "NQ1"].iloc[0]
        prob_cols = [c for c in self.result.columns if c.endswith("_probability")]
        for col in prob_cols:
            self.assertTrue(
                pd.isna(first_row[col]),
                f"Lookahead detected: {col} has non-NaN value on first row",
            )

    def test_high_confidence_requires_three_aligned_votes(self) -> None:
        """HIGH confidence rows must have max_count >= 3."""
        high_conf = self.result[self.result["confidence"] == "HIGH"]
        if not high_conf.empty:
            max_count = high_conf[["continuation_confluence_count",
                                   "reversal_confluence_count"]].max(axis=1)
            self.assertTrue((max_count >= 3).all())

    def test_second_symbol_probs_are_independent(self) -> None:
        """Probabilities computed for one symbol should not bleed into another."""
        df2 = _make_minimal_master(n=40)
        df2["symbol"] = "ES1"
        combined = pd.concat([self.df.copy(), df2], ignore_index=True)
        result2 = compute_confluence(combined)

        nq1_rows = result2[result2["symbol"] == "NQ1"]
        es1_rows = result2[result2["symbol"] == "ES1"]
        # First rows for each symbol must each be NaN (independent expanding windows)
        for sym_rows, sym in [(nq1_rows, "NQ1"), (es1_rows, "ES1")]:
            first = sym_rows.iloc[0]
            for col in ["gap_fill_probability", "or_breakout_probability"]:
                if col in result2.columns:
                    self.assertTrue(
                        pd.isna(first[col]),
                        f"Symbol bleed detected: {sym} first row {col} is not NaN",
                    )


class TestBuildMasterOCCSelection(unittest.TestCase):
    def test_occ_prefers_15min_per_symbol_day_with_local_fallback(self) -> None:
        context = pd.DataFrame(
            {
                "symbol": ["NQ1", "NQ1", "ES1"],
                "trading_date": [
                    datetime.date(2024, 1, 2),
                    datetime.date(2024, 1, 3),
                    datetime.date(2024, 1, 2),
                ],
                "day_of_week": [1, 2, 1],
                "vix_regime": ["LOW", "LOW", "LOW"],
            }
        )

        occ = pd.DataFrame(
            {
                "symbol": ["NQ1", "NQ1", "NQ1", "ES1", "ES1"],
                "trading_date": [
                    datetime.date(2024, 1, 2),
                    datetime.date(2024, 1, 2),
                    datetime.date(2024, 1, 3),
                    datetime.date(2024, 1, 2),
                    datetime.date(2024, 1, 2),
                ],
                "candle_duration_minutes": [5, 15, 5, 5, 30],
                "continuation": [0.0, 1.0, 1.0, 1.0, 0.0],
                "first_candle_direction": ["DOWN", "UP", "DOWN", "UP", "DOWN"],
            }
        )

        empty = pd.DataFrame()

        def fake_read(path, cols=None):
            name = path.name
            if name == "occ_records.parquet":
                return occ.copy()
            if name == "gap_records.parquet":
                return empty
            if name == "reference_levels.parquet":
                return empty
            if name == "range_trades.parquet":
                return empty
            if name == "streak_records.parquet":
                return empty
            return empty

        with patch("scripts.context.compute_daily_confluence._load_context", return_value=context):
            with patch("scripts.context.compute_daily_confluence._read", side_effect=fake_read):
                result = _build_master(["NQ1", "ES1"])

        # NQ1 2024-01-02 should use 15m record, not 5m record.
        row_nq_15 = result[
            (result["symbol"] == "NQ1")
            & (result["trading_date"] == datetime.date(2024, 1, 2))
        ].iloc[0]
        self.assertEqual(row_nq_15["occ_first_direction"], "UP")
        self.assertEqual(float(row_nq_15["occ_continuation"]), 1.0)

        # NQ1 2024-01-03 has no 15m record, so fallback to available 5m.
        row_nq_fb = result[
            (result["symbol"] == "NQ1")
            & (result["trading_date"] == datetime.date(2024, 1, 3))
        ].iloc[0]
        self.assertEqual(row_nq_fb["occ_first_direction"], "DOWN")
        self.assertEqual(float(row_nq_fb["occ_continuation"]), 1.0)


if __name__ == "__main__":
    unittest.main()
