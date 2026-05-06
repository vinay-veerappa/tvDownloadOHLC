import unittest
import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.libs_py.data.loader import DataLoader
from scripts.libs_py.regime.ensemble import EnsembleRegimeModel
from scripts.trading_framework.ml.walk_forward import PurgedKFold
from scripts.trading_framework.config.config_loader import SessionConfig, AppConfig, load_config

class TestInstitutionalFramework(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Create a synthetic 1-minute dataset for testing
        num_bars = 100
        dates = pd.date_range(start="2024-01-01", periods=num_bars, freq="1min")
        
        cls.test_df = pd.DataFrame({
            'open': np.linspace(100, 105, num_bars),
            'high': np.linspace(100.5, 105.5, num_bars),
            'low': np.linspace(99.5, 104.5, num_bars),
            'close': np.linspace(100.2, 105.2, num_bars),
            'volume': np.random.randint(100, 1000, num_bars),
            'range_pct': np.random.uniform(0.0001, 0.002, num_bars),
            'returns': np.random.normal(0, 0.001, num_bars)
        }, index=dates)

        # Mock session configuration aligned with institutional window definitions
        cls.mock_session = SessionConfig(
            rth_start="09:30", rth_end="16:00", ib_end="10:30",
            ny_am_end="12:00", lunch_start="12:00", lunch_end="13:30",
            ny_pm_start="14:00", last_entry="15:45", flatten_by="16:00"
        )
        
    def test_dataloader_structure(self):
        """Test Layer 1: DataLoader structural integrity."""
        # Check that essential pricing and internals loading methods are accessible
        assert hasattr(DataLoader, 'load_price')
        assert hasattr(DataLoader, 'load_internals')

    def test_regime_ensemble(self):
        """Test Layer 3: Regime Ensemble stability."""
        model = EnsembleRegimeModel()
        regimes = model.predict_regime(self.test_df)
        assert len(regimes) == len(self.test_df)
        # Ensure it returns integers [0, 1, 2]
        assert pd.api.types.is_integer_dtype(regimes)

    def test_purged_cv(self):
        """Test Layer 6: Purged K-Fold temporal splitting."""
        cv = PurgedKFold(n_splits=3, pct_embargo=0.01)
        # Dummy series for splitting
        y = pd.Series(0, index=self.test_df.index)
        splits = list(cv.split(self.test_df, y))
        assert len(splits) == 3
        
        # Verify train/test indices don't overlap to prevent leakage
        for train_idx, test_idx in splits:
            overlap = set(train_idx).intersection(set(test_idx))
            assert len(overlap) == 0

if __name__ == '__main__':
    unittest.main()
