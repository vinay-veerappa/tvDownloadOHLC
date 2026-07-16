import pandas as pd
from hmmlearn import hmm

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.regime.base import RegimeModel

class HMMRegimeModel(RegimeModel):
    """
    Gaussian Hidden Markov Model for market regime detection.
    Layer 3: Classifies volatility and momentum states using temporal dynamics.
    """
    
    def __init__(self, n_regimes: int = 3, covariance_type: str = "diag", n_iter: int = 100):
        super().__init__(name=f"hmm_{n_regimes}")
        self.n_regimes = n_regimes
        self.model = hmm.GaussianHMM(n_components=n_regimes, covariance_type=covariance_type, n_iter=n_iter)
        
    def predict_regime(self, data: pd.DataFrame) -> pd.Series:
        """
        Fits and predicts regimes based on returns and volatility.
        """
        # Feature vector for HMM
        # We use returns and range (volatility) as the primary state indicators
        X = data[['returns', 'range_pct']].values
        
        # Train HMM (In-sample for this simple case, should be walk-forward for production)
        self.model.fit(X)
        regimes = self.model.predict(X)
        
        return pd.Series(regimes, index=data.index)
