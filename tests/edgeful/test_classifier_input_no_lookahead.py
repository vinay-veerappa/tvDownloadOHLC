"""REG-1 consumer fix: the classifier's feature matrix must not carry the
whole-sample (`_full`) regime labels.

`range_bucket_full` / `vix_bucket_full` are whole-sample quantile labels --
a 2010 row's bucket is computed from data through 2026. Training on them
leaks the future distribution into every split; the causal `_trailing`
variants carry the same information as expanding quantiles knowable on the
day. The fix is at the feature LIST, so the leakage is gone at the join.
"""

import unittest

import pandas as pd

from scripts.edgeful.universal_signal_classifier_input import (
    CONFLUENCE_CAT_FEATURES,
    CONFLUENCE_FEATURES,
    _attach_confluence_features,
)

KEY_COLS = ["symbol", "session_slot", "time_basis", "trading_day"]


class TestNoLookaheadBucketFeatures(unittest.TestCase):
    def test_full_buckets_are_not_in_the_feature_lists(self):
        for lst, name in ((CONFLUENCE_FEATURES, "CONFLUENCE_FEATURES"),
                          (CONFLUENCE_CAT_FEATURES, "CONFLUENCE_CAT_FEATURES")):
            self.assertNotIn("range_bucket_full", lst, name)
            self.assertNotIn("vix_bucket_full", lst, name)

    def test_causal_trailing_buckets_are(self):
        """Negative control: the causal variants must survive the cull, or the
        fix removed the signal instead of the lookahead."""
        self.assertIn("range_bucket_trailing", CONFLUENCE_FEATURES)
        self.assertIn("vix_bucket_trailing", CONFLUENCE_FEATURES)
        self.assertIn("range_bucket_trailing", CONFLUENCE_CAT_FEATURES)

    def test_the_join_drops_full_buckets_even_if_the_source_has_them(self):
        """The confluence table still CARRIES the _full columns; the join must
        not emit them just because they exist upstream."""
        confluence = pd.DataFrame({
            "symbol": ["NQ1"],
            "session_slot": ["London IB"],
            "time_basis": ["et"],
            "trading_day": ["2024-01-02"],
            "range_bucket_full": ["Small"],
            "range_bucket_trailing": ["Large"],
            "vix_bucket_full": ["Low"],
            "vix_bucket_trailing": ["High"],
            "vix_close": [15.0],
        })
        rows = pd.DataFrame({k: confluence[k].values for k in KEY_COLS})
        joined = _attach_confluence_features(rows, confluence)
        self.assertIn("range_bucket_trailing", joined.columns)
        self.assertNotIn("range_bucket_full", joined.columns)
        self.assertNotIn("vix_bucket_full", joined.columns)
        self.assertEqual(joined["range_bucket_trailing"].iloc[0], "Large")


if __name__ == "__main__":
    unittest.main()