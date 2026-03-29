import pandas as pd
import numpy as np
import os
import joblib
from typing import Dict, Any, List, Optional
try:
    import lightgbm as lgb
except ImportError:
    # Fallback to a simpler model or raise if strictly required by architecture
    from sklearn.ensemble import RandomForestClassifier as lgb

# Layer 8: Machine Learning Optimization — Signal Classifier.
# This sits on top of Layer 4 (Strategy Logic) and Layer 5 (Backtest Engine).
# It uses the Feature Registry (Layer 2) to predict trade success.

class SignalClassifier:
    """
    Institutional Signal Classification Layer (Phase 4).
    Primary Role: Filter False Positives from mechanical strategies.
    
    A trade passes if: Predicted Probability > 0.55
    """
    
    def __init__(self, model_path: str = "models/signal_classifier.joblib"):
        self.model_path = model_path
        self.model = None
        self.feature_cols = []
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
    def train(self, X: pd.DataFrame, y: pd.Series):
        """
        Trains the classifier on historical 'Trade Success' (hit target vs hit stop).
        
        Args:
            X: Standardized Feature Matrix at signal time (from Layer 2 Registry).
            y: Binary target [0: fail, 1: success].
        """
        self.feature_cols = list(X.columns)
        
        # Use LightGBM for its efficiency and support for categorical data (Regimes)
        params = {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'seed': 42
        }
        
        # Convert categoricals if present
        for col in X.select_dtypes(include=['object', 'category']).columns:
            X[col] = X[col].astype('category').cat.codes
            
        train_data = lgb.Dataset(X, label=y)
        self.model = lgb.train(params, train_data, num_boost_round=100)
        
        # Persist model
        joblib.dump({"model": self.model, "feature_cols": self.feature_cols}, self.model_path)
        print(f"✅ Signal Classifier trained on {len(X)} samples and saved to {self.model_path}")
        
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Inference: Predict probability of success for upcoming signals.
        """
        if self.model is None and os.path.exists(self.model_path):
            data = joblib.load(self.model_path)
            self.model = data["model"]
            self.feature_cols = data["feature_cols"]
            
        if self.model is None:
            # If no model, return neutral probability
            return np.full(len(X), 0.5)

        # Ensure feature alignment
        X = X[self.feature_cols].copy()
        for col in X.select_dtypes(include=['object', 'category']).columns:
            X[col] = X[col].astype('category').cat.codes

        return self.model.predict(X)

    def filter_signals(self, signals: pd.DataFrame, features: pd.DataFrame, threshold: float = 0.55) -> pd.DataFrame:
        """
        The critical Layer 4 -> Layer 8 interface.
        Filters mechanical signals based on predicted probability.
        """
        if signals.empty: return signals
        
        # 1. Snap features at signal times
        # Assumes signals['signal_time'] exists and aligns with features.index
        valid_features = features.reindex(signals['signal_time']).dropna(axis=1, how='all').fillna(0)
        
        # 2. Score
        probs = self.predict_proba(valid_features)
        signals['ml_prob'] = probs
        
        # 3. Filter
        filtered = signals[signals['ml_prob'] >= threshold].copy()
        print(f"📉 ML Filter: {len(signals)} mechanical -> {len(filtered)} filtered ({len(signals)-len(filtered)} rejected)")
        
        return filtered
