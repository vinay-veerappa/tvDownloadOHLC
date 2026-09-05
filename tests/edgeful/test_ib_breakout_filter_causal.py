"""REG-1 regression: the IB breakout filter must key its walk-forward
calibration on the CAUSAL range bucket.

The shipped version keyed calibration cells on ``range_bucket_full`` — a label
computed from whole-sample quantiles, i.e. a day was labelled using data from
days after it (lookahead). This test pins three things:

1. Calibration keys on ``range_bucket_trailing`` when present.
2. The confluence score reads the causal bucket (it previously matched a
   vocabulary — "normal"/"compressed"/"wide" — that never occurs in the
   pipeline output, so the branch scored 0 for every row).
3. A row whose full-sample label differs from its trailing label lands in a
   different calibration cell than it would under the lookahead key.
"""

import unittest

import numpy as np
import pandas as pd

from scripts.edgeful.ib_breakout_filter import (
    _compute_confluence_score,
    _walk_forward_calibration,
)


def _make_frame(n_days: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    days = pd.date_range("2024-01-01", periods=n_days, freq="D").strftime("%Y-%m-%d")
    rows = []
    for i, d in enumerate(days):
        for slot in ("Globex IB", "London IB"):
            range_pct = float(rng.uniform(0.1, 1.0))
            rows.append(
                {
                    "symbol": "NQ1",
                    "session_slot": slot,
                    "time_basis": "et",
                    "trading_day": d,
                    "range_pct": range_pct,
                    # Deliberately disagree on a known subset of rows: this is
                    # the lookahead signature, exaggerated so the test cannot
                    # pass by chance.
                    "range_bucket_full": "Medium",
                    "range_bucket_trailing": "Small" if i % 2 == 0 else "Large",
                    "first_break_dir": 1,
                    "trend_aligned_with_break": 1,
                    "avwap_aligned": 1,
                    "break_dir_matches_avwap0930": 1,
                    "fail_setup_score": 0,
                    "play3_result": float(rng.normal(0.0, 0.01)),
                    "play3_mfe": float(abs(rng.normal(0.01, 0.005))),
                }
            )
    return pd.DataFrame(rows)


class TestCausalCalibrationKey(unittest.TestCase):
    def test_calibration_uses_trailing_bucket(self) -> None:
        """Small-cell rows always win and Large-cell rows always lose; after
        the calibration has enough observations the two cells must separate,
        even though every row shares the SAME full-sample label."""
        df = _make_frame(n_days=120)
        # Deterministic outcomes keyed on the trailing label only.
        is_small = df["range_bucket_trailing"] == "Small"
        df["play3_result"] = np.where(is_small, 0.01, -0.01)
        cal = _walk_forward_calibration(df)

        wr = cal["empirical_win_rate_strict"]
        # The calibration lags outcomes by one trading day via groupby(day)
        # .shift(1), so each day's FIRST session slot row never contributes an
        # observation to its cell (first-in-day -> NaN). Only the second slot
        # ("London IB") accumulates; assert there.
        accumulates = df["session_slot"] == "London IB"
        late = df["trading_day"] > "2024-04-01"
        late_small = wr[is_small & accumulates & late]
        late_large = wr[~is_small & accumulates & late]
        self.assertGreater(late_small.dropna().mean(), 0.9)
        self.assertLess(late_large.dropna().mean(), 0.1)

    def test_calibration_changes_when_full_disagrees(self) -> None:
        """Flipping ONLY the trailing label of a large block of rows must move
        their calibration; flipping ONLY the full label must not."""
        df = _make_frame(n_days=120)
        base = _walk_forward_calibration(df)

        # Flip the trailing label on a whole block: cell membership changes for
        # enough observations to escape the shrinkage fallback (min_obs=20).
        df_flip_trailing = df.copy()
        flip = df.index[df["range_bucket_trailing"] == "Small"][:40]
        df_flip_trailing.loc[flip, "range_bucket_trailing"] = "Large"
        flipped_trailing = _walk_forward_calibration(df_flip_trailing)
        changed_trailing = (
            base["empirical_win_rate_strict"].fillna(-1)
            != flipped_trailing["empirical_win_rate_strict"].fillna(-1)
        )
        self.assertTrue(changed_trailing.any())

        # Flip the full label everywhere: calibration must NOT move, because
        # the full label is no longer a key. This is the negative control for
        # the fix itself.
        df_flip_full = df.copy()
        df_flip_full["range_bucket_full"] = "Large"
        flipped_full = _walk_forward_calibration(df_flip_full)
        changed_full = (
            base["empirical_win_rate_strict"].fillna(-1)
            != flipped_full["empirical_win_rate_strict"].fillna(-1)
        )
        self.assertFalse(changed_full.any())

    def test_confluence_score_uses_pipeline_vocabulary(self) -> None:
        """The score must read Small/Medium/Large — the vocabulary the pipeline
        actually emits. The pre-fix code matched "normal"/"compressed"/"wide",
        which never occur, so the bucket term was always 0."""
        df = pd.DataFrame(
            {
                "trend_aligned_with_break": [1.0, 1.0, 1.0, 1.0],
                "avwap_aligned": [1.0, 1.0, 1.0, 1.0],
                "break_dir_matches_avwap0930": [1.0, 1.0, 1.0, 1.0],
                "fail_setup_score": [0.0, 0.0, 0.0, 0.0],
                "range_bucket_trailing": ["Small", "Medium", "Large", "Medium"],
                "range_bucket_full": ["Medium", "Medium", "Medium", "Medium"],
            }
        )
        out = _compute_confluence_score(df)
        self.assertEqual(len(out), 4)
        # trend(3) + avwap(2) + match(2) = 7 for every row; the bucket term
        # is +0.5 for Medium and -0.5 for Small/Large (trailing preferred).
        expected = np.array([7.0 - 0.5, 7.0 + 0.5, 7.0 - 0.5, 7.0 + 0.5])
        np.testing.assert_allclose(out["confluence_score"].values, expected)

    def test_confluence_score_falls_back_to_full_when_trailing_missing(self) -> None:
        """Legacy tables without the trailing column still score, off the
        lookahead label — better than silently scoring 0."""
        df = pd.DataFrame(
            {
                "trend_aligned_with_break": [1.0],
                "avwap_aligned": [1.0],
                "break_dir_matches_avwap0930": [1.0],
                "fail_setup_score": [0.0],
                "range_bucket_full": ["Medium"],
            }
        )
        out = _compute_confluence_score(df)
        self.assertAlmostEqual(out["confluence_score"].iloc[0], 7.5)


if __name__ == "__main__":
    unittest.main()