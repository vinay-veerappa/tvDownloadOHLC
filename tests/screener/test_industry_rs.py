import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from scripts.screener.core.industry_rs import calculate_industry_rs

@patch('scripts.screener.core.industry_rs.Performance')
def test_calculate_industry_rs_rankings(mock_performance_cls):
    """Verify Industry Group RS ranking parses finviz strings and computes percentiles."""
    
    # Mock Finviz returned dataframe
    mock_perf = MagicMock()
    mock_performance_cls.return_value = mock_perf
    
    # Create 4 fake industries to test percentiles
    mock_df = pd.DataFrame({
        "Name": ["Tech", "Energy", "Utility", "Finance"],
        "Perf Half": ["20.0%", "-5.0%", "5.0%", "10.0%"]
    })
    mock_perf.screener_view.return_value = mock_df
    
    rankings = calculate_industry_rs()
    
    assert isinstance(rankings, dict)
    assert len(rankings) == 4
    
    # Verify rankings map correctly
    # Tech (20%) is best -> rank 1.0 (100)
    # Energy (-5%) is worst -> rank 0.25 (25.0)
    # Utility (5%) is 2nd worst -> rank 0.5 (50.0)
    # Finance (10%) is 2nd best -> rank 0.75 (75.0)
    
    assert rankings["Tech"] == 100.0
    assert rankings["Energy"] == 25.0
    assert rankings["Utility"] == 50.0
    assert rankings["Finance"] == 75.0
