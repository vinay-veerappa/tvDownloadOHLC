import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from hmmlearn import hmm
from sklearn.mixture import GaussianMixture
from scripts.trading_framework.core.base import RegimeModel

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

class ThresholdRegimeModel(RegimeModel):
    """
    Rule-based regime detection (ATR-normalized).
    Categorizes the market as: 0 (Low-Vol), 1 (Normal-Vol), 2 (High-Vol).
    """
    
    def __init__(self, high_vol_threshold: float = 0.002, low_vol_threshold: float = 0.0005):
        super().__init__(name="threshold")
        self.hv_threshold = high_vol_threshold
        self.lv_threshold = low_vol_threshold
        
    def predict_regime(self, data: pd.DataFrame) -> pd.Series:
        # Use simple returns absolute magnitude for thresholding
        vol = data['range_pct'].rolling(window=20).mean() # short-term vol
        
        regimes = pd.Series(1, index=data.index) # Normal
        regimes[vol > self.hv_threshold] = 2    # High
        regimes[vol < self.lv_threshold] = 0    # Low
        
        return regimes

class EnsembleRegimeModel(RegimeModel):
    """
    Consensus-based regime model.
    Combines Threshold, HMM, and GMM models to find stable market states.
    """
    
    def __init__(self, models: List[RegimeModel] = None):
        self.models = models or [
            ThresholdRegimeModel(),
            HMMRegimeModel(),
            GMMRegimeModel()
        ]
        
    def predict_regime(self, data: pd.DataFrame) -> pd.Series:
        # 1. Collect predictions from all models
        all_preds = []
        for i, model in enumerate(self.models):
            preds = model.predict_regime(data)
            all_preds.append(preds.rename(f"m{i}"))
            
        df_preds = pd.concat(all_preds, axis=1)
        
        # 2. Find Mode (Majority Vote)
        # Note: Mapping might be needed if state labels 0,1,2 don't align across models
        # For simplicity, we assume they align by luck or by pre-sorting states by variance
        consensus = df_preds.mode(axis=1)[0]
        
        return consensus.fillna(1).astype(int)
