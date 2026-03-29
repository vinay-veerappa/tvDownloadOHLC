import pandas as pd
import numpy as np
from typing import List, Tuple, Generator
from sklearn.model_selection import KFold

# Layer 6: ML Optimization — Purged Walk-Forward Cross-Validation.
# Institutional Standard for Time-Series: Prevents Data Leakage/Overfitting.
# Based on Lopez de Prado's "Advances in Financial Machine Learning".

class PurgedKFold:
    """
    K-Fold Cross-Validator for Time-Series that implements Purging and Embargo.
    
    1. Purging: Removes training observations that overlap with the test set
       due to forward-looking labels (success of signal N bars ahead).
    2. Embargo: Removes training observations immediately following the test set
       to avoid serial correlation leakage.
    """
    
    def __init__(self, n_splits: int = 5, purge_window: int = 60, pct_embargo: float = 0.05):
        """
        Args:
            n_splits: Number of folds.
            purge_window: Number of bars used for the forward label (e.g., target/stop window).
            pct_embargo: Percentage of training set to remove after the test set.
        """
        self.n_splits = n_splits
        self.purge_window = purge_window
        self.pct_embargo = pct_embargo
        
    def split(self, X: pd.DataFrame, y: pd.Series = None, groups=None) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Produce purged and embargoed train/test indices.
        """
        n_samples = len(X)
        indices = np.arange(n_samples)
        
        # We start with a standard KFold to get initial split positions
        # But we will purge the training set relative to test boundaries
        kf = KFold(n_splits=self.n_splits, shuffle=False)
        
        for train_indices, test_indices in kf.split(indices):
            # 1. Identify Test Set Boundaries
            test_start = test_indices[0]
            test_end = test_indices[-1]
            
            # 2. PURGING: Training observations that overlap with test forward window
            # If a training observation at t has a label based on [t, t + purge_window],
            # it will leak information if t + purge_window >= test_start.
            # So purge all train_indices where t + purge_window >= test_start AND t < test_start.
            purged = []
            for t in train_indices:
                if t < test_start:
                    if t + self.purge_window < test_start:
                        purged.append(t)
                elif t > test_end:
                    # 3. EMBARGO: Observations following the test set
                    embargo_size = int(n_samples * self.pct_embargo)
                    if t > test_end + embargo_size:
                        purged.append(t)
                else:
                    # Inside test set - skip
                    pass
            
            yield np.array(purged), test_indices

def walk_forward_split(df: pd.DataFrame, n_folds: int = 5) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Simple Walk-Forward Split (Non-purged) for initial validation.
    """
    folds = []
    chunk_size = len(df) // (n_folds + 1)
    
    for i in range(1, n_folds + 1):
        train = df.iloc[:i * chunk_size]
        test = df.iloc[i * chunk_size : (i + 1) * chunk_size]
        folds.append((train, test))
        
    return folds
