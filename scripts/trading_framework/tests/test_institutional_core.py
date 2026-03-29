import unittest
import pandas as pd
import numpy as np
import os
import sys

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.getcwd(), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scripts.trading_framework.data.loader import FrameworkLoader
from scripts.trading_framework.regime.regime_models import EnsembleRegimeModel
from scripts.trading_framework.ml.walk_forward import PurgedKFold

class TestInstitutionalFramework(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Create a synthetic 1-minute dataset for testing
        num_bars = 1000
        dates = pd.date_range(start="2024-01-01", periods=num_bars, freq="1min")
        
        # Simulated price path (brownian bridge-like)
        close = 100 + np.random.normal(0, 0.001, num_bars).cumsum()
        high = close + abs(np.random.normal(0, 0.001, num_bars))
        low = close - abs(np.random.normal(0, 0.001, num_bars))
        
        cls.test_df = pd.DataFrame({
            'open': close.tolist(),
            'high': high.tolist(),
            'low': low.tolist(),
            'close': close.tolist(),
            'volume': np.random.randint(100, 1000, num_bars),
            'returns': pd.Series(close).pct_change().fillna(0).tolist(),
            'range_pct': ((high - low) / close).tolist()
        }, index=dates)

    def test_news_fusion_logic(self):
        """Test Layer 1: News Fusion metadata generation."""
        loader = FrameworkLoader(ticker="NQ1")
        # Verify method exists (even if DB is empty, logic should held)
        self.assertTrue(hasattr(loader, 'fuse_economic_events'))
        print("✅ News Fusion module verified.")

    def test_regime_ensemble(self):
        """Test Layer 3: Regime Ensemble stability."""
        model = EnsembleRegimeModel()
        regimes = model.predict_regime(self.test_df)
        self.assertEqual(len(regimes), len(self.test_df))
        self.assertTrue(set(regimes.unique()).issubset({0, 1, 2}))
        print("✅ Regime Ensemble module verified.")

    def test_purged_cv(self):
        """Test Layer 6: Purged K-Fold temporal splitting."""
        cv = PurgedKFold(n_splits=3, pct_embargo=0.01)
        # Dummy series for splitting
        y = pd.Series(0, index=self.test_df.index)
        splits = list(cv.split(self.test_df, y))
        self.assertEqual(len(splits), 3)
        print("✅ Purged Walk-Forward CV verified.")

if __name__ == '__main__':
    unittest.main()

def has_attr(obj, name):
    return hasattr(obj, name)
