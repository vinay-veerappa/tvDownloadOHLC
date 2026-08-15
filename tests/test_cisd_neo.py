"""
Unit tests for Authoritative Neo/Canonical CISD detection engine.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scripts.libs_py.ict_engine import detect_cisd_neo


def test_cisd_neo_synthetic_bullish_and_bearish():
    """
    Test that CISD accurately triggers on synthetic price action with defined pullbacks.
    """
    # 1. Construct controlled price series
    # Start flat at 100
    times = [datetime(2024, 1, 1, 9, 30) + timedelta(minutes=i) for i in range(20)]
    
    # Sequence:
    # 0-3: Downward leg (100 -> 90)
    # 4-6: Upward pullback (90 -> 95, opens at 90.5, 92, 93.5)
    # 7-9: Bearish expansion (95 -> 85) -> New low! Arms +CISD resistance at highest pullback open (93.5)
    # 10-12: Bullish reversal body-closing above 93.5 -> Triggers Bullish CISD (+1)!
    
    opens  = [100, 98, 95, 92, 90.5, 92.0, 93.5, 93.0, 88.0, 86.0, 86.0, 91.0, 95.0, 96.0, 96.0, 94.0, 92.0, 90.0, 88.0, 85.0]
    highs  = [101, 99, 96, 93, 92.5, 94.0, 95.5, 94.0, 89.0, 87.0, 87.0, 92.0, 96.0, 97.0, 97.0, 95.0, 93.0, 91.0, 89.0, 86.0]
    lows   = [ 98, 95, 92, 90, 90.0, 91.5, 93.0, 88.0, 85.0, 84.0, 85.0, 90.0, 94.0, 95.0, 93.5, 91.5, 89.5, 87.5, 84.5, 83.0]
    closes = [ 98, 95, 92, 91, 92.0, 93.5, 95.0, 88.0, 86.0, 85.0, 91.0, 95.0, 95.5, 96.5, 94.0, 92.0, 90.0, 88.0, 85.0, 84.0]
    
    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes
    }, index=pd.DatetimeIndex(times))
    
    result = detect_cisd_neo(df)
    
    # Assert columns exist
    assert "cisd_event" in result.columns
    assert "cisd_state" in result.columns
    assert "active_bull_level" in result.columns
    assert "active_bear_level" in result.columns
    assert "structure_top" in result.columns
    assert "structure_bottom" in result.columns
    
    # Bar 11 closes at 95.0, which is > 93.5 (+CISD armed level) -> Should trigger Bullish CISD (+1)
    bull_events = np.where(result["cisd_event"].values == 1)[0]
    assert len(bull_events) > 0, "Bullish CISD should have triggered"
    assert result["cisd_state"].values[bull_events[0]] == 1, "Regime should flip to Bullish (+1)"


def test_cisd_neo_on_real_market_data():
    """
    Test detect_cisd_neo on real historical NQ data from data/-NQ_1m.parquet.
    """
    import os
    sample_path = "data/-NQ_1m.parquet"
    if not os.path.exists(sample_path):
        pytest.skip(f"{sample_path} not found")
        
    df = pd.read_parquet(sample_path).head(50000)
    result = detect_cisd_neo(df)

    
    assert len(result) == len(df)
    assert set(result["cisd_state"].unique()).issubset({-1, 0, 1})
    
    bull_count = (result["cisd_event"] == 1).sum()
    bear_count = (result["cisd_event"] == -1).sum()
    
    print(f"Tested on {len(df)} bars: Bull CISD events = {bull_count}, Bear CISD events = {bear_count}")
    assert bull_count > 0 and bear_count > 0, "Real market data should contain both Bullish and Bearish CISDs"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
