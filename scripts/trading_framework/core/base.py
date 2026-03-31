from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, Optional

class SignalGenerator(ABC):
    """
    Abstract Base Class for all signal generation logic.
    Layer 4 of the Statistical Trading Framework.
    """
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
        """
        Produce a series of binary signals (-1, 0, 1).
        
        Args:
            data: OHLCV DataFrame with features populated.
            config: Strategy-specific parameters.
            
        Returns:
            pd.Series: -1 for Short, 1 for Long, 0 for Neutral.
        """
        pass

class RegimeModel(ABC):
    """
    Abstract Base Class for market regime detection models.
    Layer 3 of the Statistical Trading Framework.
    """
    
    def __init__(self, name: str = "base"):
        self.name = name

    @abstractmethod
    def predict_regime(self, data: pd.DataFrame) -> pd.Series:
        """
        Assign a regime state to every bar in the dataset.
        
        Returns:
            pd.Series: Integer-encoded regime states.
        """
        pass

    def get_feature_name(self) -> str:
        """Standardized naming for the derived feature store."""
        return f"feat_regime_{self.name}"

class BaseBacktester(ABC):
    """
    Interface for the backtesting engine (Vectorized or Event-driven).
    Layer 5 of the Statistical Trading Framework.
    """
    
    @abstractmethod
    def run(self, signals: pd.Series, data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute trades based on signals and return performance metrics.
        """
        pass
