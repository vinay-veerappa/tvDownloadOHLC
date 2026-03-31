import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from sklearn.feature_selection import SelectFromModel, SequentialFeatureSelector
from sklearn.ensemble import RandomForestClassifier

# Layer 8: Feature Selection — Pruning Strategy Noise.
# Reduces dimensionality to prevent model overfitting in the Signal Classifier.

class FeatureSelector:
    """
    Automated Feature Selection Layer.
    Uses model-based importance and recursive selection to find robust feature sets.
    """
    
    def __init__(self, n_features: int = 5):
        self.n_features = n_features
        self.selected_columns = []
        
    def select_boruta_style(self, X: pd.DataFrame, y: pd.Series) -> List[str]:
        """
        Identify top features using Random Forest Importance.
        """
        # 1. Base model for ranking
        base_model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        
        # 2. Sequential / Model-based selection
        selector = SelectFromModel(base_model, threshold='median', max_features=self.n_features)
        
        # 3. Fit
        # Encode categoricals for sklearn
        X_encoded = X.copy()
        for col in X_encoded.select_dtypes(include=['object', 'category']).columns:
            X_encoded[col] = X_encoded[col].astype('category').cat.codes
            
        selector.fit(X_encoded, y)
        
        self.selected_columns = list(X.columns[selector.get_support()])
        
        print(f"🎯 Feature Selection: {len(X.columns)} features -> {len(self.selected_columns)} selected")
        print(f"Selected: {self.selected_columns}")
        
        return self.selected_columns

    def rank_importance(self, X: pd.DataFrame, y: pd.Series) -> pd.Series:
        """
        Simple feature importance ranking.
        """
        base_model = RandomForestClassifier(n_estimators=100, random_state=42)
        X_encoded = X.copy()
        for col in X_encoded.select_dtypes(include=['object', 'category']).columns:
            X_encoded[col] = X_encoded[col].astype('category').cat.codes
            
        base_model.fit(X_encoded, y)
        
        importance = pd.Series(base_model.feature_importances_, index=X.columns).sort_values(ascending=False)
        return importance
