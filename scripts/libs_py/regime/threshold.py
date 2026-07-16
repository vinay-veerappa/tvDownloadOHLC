import pandas as pd

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
