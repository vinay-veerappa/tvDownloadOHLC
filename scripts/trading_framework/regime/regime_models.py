import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from hmmlearn import hmm
from scripts.trading_framework.core.base import RegimeModel

class HMMRegimeModel(RegimeModel):
    """
    Gaussian Hidden Markov Model for market regime detection.
    Layer 3: Classifies volatility and momentum states.
    """
    
    def __init__(self, n_regimes: int = 3, covariance_type: str = "full", n_iter: int = 100):
        self.n_regimes = n_regimes
        self.model = hmm.GaussianHMM(n_components=n_regimes, covariance_type=covariance_type, n_iter=n_iter)
        
    def predict_regime(self, data: pd.DataFrame) -> pd.Series:
        """
        Fits and predicts regimes based on daily returns and returns volatility.
        Inputs: returns, range_pct (from Layer 1 loader).
        """
        # Resample for regime stability
        daily = data.resample('D').agg({
            'returns': 'sum',
            'range_pct': 'mean'
        }).dropna()
        
        # Train HMM
        X = daily[['returns', 'range_pct']].values
        self.model.fit(X)
        regimes = self.model.predict(X)
        
        # Map back to 1m timeline
        regime_series = pd.Series(regimes, index=daily.index)
        return regime_series.reindex(data.index, method='ffill').fillna(0)

class ThresholdRegimeModel(RegimeModel):
    """
    Simpler threshold-based regime detection (ATR-normalized).
    Categorizes the market as: Low-Vol, Normal-Vol, High-Vol.
    """
    
    def __init__(self, high_vol_threshold: float = 0.02, low_vol_threshold: float = 0.005):
        self.hv_threshold = high_vol_threshold
        self.lv_threshold = low_vol_threshold
        
    def predict_regime(self, data: pd.DataFrame) -> pd.Series:
        # ATR-normalized range (from Layer 1 loader)
        vol = data['range_pct'].rolling(window=1440).mean() # 1 day avg vol
        
        regimes = pd.Series(1, index=data.index) # Normal-Vol
        regimes[vol > self.hv_threshold] = 2    # High-Vol
        regimes[vol < self.lv_threshold] = 0    # Low-Vol
        
        return regimes
