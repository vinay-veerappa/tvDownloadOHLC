import pandas as pd
from sklearn.mixture import GaussianMixture
from scripts.libs.regime.base import RegimeModel

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
