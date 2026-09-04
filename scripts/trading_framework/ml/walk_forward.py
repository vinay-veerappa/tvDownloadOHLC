import pandas as pd
import numpy as np
from typing import Dict, Generator, List, Tuple
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
    
    def __init__(self, n_splits: int = 5, purge_window: int = 60, pct_embargo: float = 0.01):
        """
        Args:
            n_splits: Number of folds.
            purge_window: Number of bars used for the forward label (e.g., target/stop window).
            pct_embargo: Percentage of training set to remove after the test set (ADR-002: usually 1%).
        """
        self.n_splits = n_splits
        self.purge_window = purge_window
        self.pct_embargo = pct_embargo
        
    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits
        
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
    """DEPRECATED -- expanding-window split with NO purge and NO embargo.

    Kept only because callers may still reference it. `train` ends on the bar
    immediately before `test` begins, so any forward-looking label or
    multi-bar-horizon feature computed at the end of train overlaps the start of
    test. Use `sequential_evaluation_folds` for parameter sweeps or `PurgedKFold`
    for fitted models; do not add new callers here.
    """
    folds = []
    chunk_size = len(df) // (n_folds + 1)
    
    for i in range(1, n_folds + 1):
        train = df.iloc[:i * chunk_size]
        test = df.iloc[i * chunk_size : (i + 1) * chunk_size]
        folds.append((train, test))
        
    return folds


# ---------------------------------------------------------------------------
# Sequential evaluation folds -- for PARAMETER sweeps, where nothing is fitted.
#
# PurgedKFold above is the right tool for cross-validating a FITTED model on
# labelled samples: purging removes training rows whose forward-looking label
# overlaps the test block, and the training set legitimately spans both sides of
# it. A parameter sweep fits nothing. There is no training set to purge, so
# k-fold there only buys disjoint evaluation windows -- and it buys them at the
# cost of an unbounded footgun: the caller must re-index signals onto each test
# block itself, and getting that wrong is silent (see
# VectorizedBacktester._align_signals_to_frame and
# tests/test_signal_frame_alignment.py, which record what it cost here).
#
# So this yields explicit, non-overlapping, EQUAL-LENGTH evaluation windows with
# three separate boundaries per fold, because they are three different things:
#
#   gen_end     bars the signal generator may see. Ends at test_end, never past
#               it, so signals inside the window cannot be informed by bars
#               after it.
#   score_start /
#   score_end   the frame the result is measured on. Starts at test_start (so a
#               signal_time inside the window is an EXACT index member, not a
#               snap) and runs `exit_buffer` bars past test_end so a trade
#               opened near the close of the window can still resolve.
#   embargo     bars skipped between consecutive windows, so serial correlation
#               at a boundary is not shared between two folds.
#
# The exit buffer is reserved from the END of the data, not borrowed from it, so
# the final fold is not silently scored with truncated exits. Every window is
# the same length because `VectorizedBacktester` builds its Sharpe from a
# per-BAR series that is zero except at exit bars -- that number scales with
# frame length, so unequal windows are not comparable to each other.
# ---------------------------------------------------------------------------
def sequential_evaluation_folds(n_samples: int, n_splits: int = 3,
                                exit_buffer: int = 1440, embargo: int = 0) -> List[Dict]:
    """Non-overlapping equal-length evaluation windows with a reserved exit buffer.

    Returns a list rather than a generator: callers evaluate the same folds once
    per trial, and a generator silently yields nothing the second time.
    """
    if n_splits < 1:
        raise ValueError("n_splits must be >= 1")
    if exit_buffer < 0 or embargo < 0:
        raise ValueError("exit_buffer and embargo must be >= 0")

    usable = n_samples - exit_buffer - embargo * (n_splits - 1)
    if usable < n_splits:
        raise ValueError(
            "not enough bars for {} folds: {} bars, exit_buffer={}, embargo={} "
            "leaves {} usable. Reduce n_splits/exit_buffer or supply more data."
            .format(n_splits, n_samples, exit_buffer, embargo, usable)
        )

    width = usable // n_splits
    folds = []
    cursor = 0
    for k in range(n_splits):
        test_start = cursor
        test_end = test_start + width
        folds.append({
            "fold": k,
            "test_start": int(test_start),
            "test_end": int(test_end),
            "gen_end": int(test_end),
            "score_start": int(test_start),
            "score_end": int(min(test_end + exit_buffer, n_samples)),
            "n_bars_scored": int(min(test_end + exit_buffer, n_samples) - test_start),
        })
        cursor = test_end + embargo
    return folds
