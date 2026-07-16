import pandas as pd
import numpy as np
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List

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

from scripts.trading_framework.core.base import SignalGenerator

class ModularSignalGenerator(SignalGenerator, ABC):
    """
    Standardized Vectorized Strategy Interface (ADR-017).
    Decomposes strategy logic into Triggers, Filters, and Risk.
    
    Attributes:
        strategy_name: Global identifier for the Research Hub DB.
    """
    
    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.filters = []

    def add_filter(self, filter_func):
        """Add a reusable filter component (e.g. KillZone, News)."""
        self.filters.append(filter_func)

    @abstractmethod
    def get_raw_trigger(self, data: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
        """
        Layer 4a: Core logic triggering (1 for Long, -1 for Short, 0 for None).
        Must be vectorized.
        """
        pass

    @abstractmethod
    def calculate_risk_levels(self, data: pd.DataFrame, signals: pd.Series, config: Dict[str, Any]) -> pd.DataFrame:
        """
        Layer 4c: Assign stop and target prices to each signal index.
        Returns a DataFrame with [entry_price, stop_price, target1_price].
        """
        pass

    def generate_signals(self, data: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """
        The standardized entry point for the Research Lifecycle.
        Orchestrates Trigger -> Filters -> Risk.
        """
        # 1. Generate Raw Triggers (Layer 4a)
        raw_signals = self.get_raw_trigger(data, config)
        
        # 2. Apply Modular Filters (Layer 4b)
        valid_mask = pd.Series(True, index=data.index)
        for filter_comp in self.filters:
            valid_mask &= filter_comp(data, config)
            
        filtered_signals = raw_signals.where(valid_mask, 0)
        
        # 3. Identify Entry Indices
        entry_indices = filtered_signals[filtered_signals != 0].index
        if entry_indices.empty:
            return pd.DataFrame()

        # 4. Apply Risk Management (Layer 4c)
        risk_df = self.calculate_risk_levels(data, filtered_signals, config)
        
        # 5. Build Standardized Metadata-rich Signal DataFrame
        signal_list = []
        for idx in entry_indices:
            direction = "long" if filtered_signals.loc[idx] == 1 else "short"
            risk_row = risk_df.loc[idx]
            
            signal_list.append({
                'signal_id': str(uuid.uuid4()),
                'signal_time': idx,
                'direction': direction,
                'entry_price': risk_row['entry_price'],
                'stop_price': risk_row['stop_price'],
                'target1_price': risk_row['target1_price'],
                'status': 'active'
            })
            
        return pd.DataFrame(signal_list)

    @abstractmethod
    def get_param_grid(self) -> Dict[str, Any]:
        """Expose hyperparameter search space for Optuna (Layer 5)."""
        pass
