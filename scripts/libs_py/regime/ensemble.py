import pandas as pd
from typing import List

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
from scripts.libs_py.regime.threshold import ThresholdRegimeModel
from scripts.libs_py.regime.hmm import HMMRegimeModel
from scripts.libs_py.regime.clustering import GMMRegimeModel

class EnsembleRegimeModel(RegimeModel):
    """
    Consensus-based regime model.
    Combines Threshold, HMM, and GMM models to find stable market states.
    """
    
    def __init__(self, models: List[RegimeModel] = None):
        super().__init__(name="ensemble")
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
        consensus = df_preds.mode(axis=1)[0]
        
        return consensus.fillna(1).astype(int)
