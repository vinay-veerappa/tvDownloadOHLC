import pandas as pd
from abc import ABC, abstractmethod

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
