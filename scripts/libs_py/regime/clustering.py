import pandas as pd
from sklearn.mixture import GaussianMixture

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

class GMMRegimeModel(RegimeModel):
    """
    Gaussian Mixture Model (Clustering) for regime detection.
    Unlike HMM, treats each bar as independent (no temporal smoothing).
    """
    
    def __init__(self, n_clusters: int = 3, n_init: int = 5):
        super().__init__(name=f"gmm_{n_clusters}")
        self.n_clusters = n_clusters
        self.model = GaussianMixture(n_components=n_clusters, n_init=n_init, reg_covar=1e-6)
        
    def predict_regime(self, data: pd.DataFrame) -> pd.Series:
        X = data[['returns', 'range_pct']].values
        self.model.fit(X)
        regimes = self.model.predict(X)
        return pd.Series(regimes, index=data.index)
