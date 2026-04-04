"""
Unit tests for MFE/MAE vectorized logic.
"""
import pytest
import pandas as pd
import numpy as np
from scripts.trading_framework.core.mfe_mae import compute_mfe_mae
from scripts.trading_framework.config.config_loader import MfeMaeConfig

def test_mfe_mae_vectorized_windows():
    """
    Test that MFE/MAE correctly identifies max/min excursions.
    """
    # Create simple 1m data
    # Prices: 100, 105 (MFE=5), 90 (MAE=10), 110 (MFE=10)
    data = {
        'close': [100.0, 105.0, 90.0, 110.0, 100.0],
        'high': [100.0, 106.0, 95.0, 112.0, 105.0],
        'low': [99.0, 101.0, 88.0, 89.0, 98.0],
        'atr': [2.0, 2.0, 2.0, 2.0, 2.0]
    }
    df = pd.DataFrame(data, index=pd.date_range("2023-01-01", periods=5, freq="1min"))
    
    # 1 signal at T=0 (Buy)
    df['signal'] = 0
    df.loc[df.index[0], 'signal'] = 1 
    
    # Horizons in bars
    horizons = [2, 4]
    
    result = compute_mfe_mae(df, 'signal', horizons, atr_col='atr')
    
    # Result only contains signal bars
    match = result.iloc[0]
    
    # Check T=2 horizon (bars 1, 2)
    # Highs: 106, 95 -> Max High = 106. Entry = 100. MFE = 6.0
    # Lows: 101, 88 -> Min Low = 88. Entry = 100. MAE = 12.0
    # ATR = 2.0
    # MFE_ATR = 6/2 = 3.0
    # MAE_ATR = 12/2 = 6.0
    
    assert match['mfe_2'] == pytest.approx(3.0)
    assert match['mae_2'] == pytest.approx(-0.5) # (99 - 100) / 2 = -0.5 (includes entry bar low)

def test_mfe_mae_empty_signals():
    """
    Ensure no crash on empty signals.
    """
    df = pd.DataFrame({'close': [100]*10, 'high': [100]*10, 'low': [100]*10, 'atr': [1]*10, 'signal': [0]*10}, 
                      index=pd.date_range("2023-01-01", periods=10, freq="1min"))
    horizons = [5]
    result = compute_mfe_mae(df, 'signal', horizons, atr_col='atr')
    assert result.empty

if __name__ == "__main__":
    import sys
    pytest.main(sys.argv)
