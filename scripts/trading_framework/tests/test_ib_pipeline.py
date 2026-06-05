import pandas as pd
import numpy as np
import pytest
from datetime import time
from scripts.libs_py.nqstats.ib import calculate_ib_statistics_v5

def test_ib_pipeline_shape_alignment_with_missing_ib_bars():
    # Day 1: Full day of 1-minute bars
    t1 = pd.date_range("2026-06-01 00:00:00", "2026-06-01 16:00:00", freq="1min", tz="US/Eastern")
    # Day 2: Only afternoon bars, NO bars in NY AM IB (09:30 - 10:30)
    t2 = pd.date_range("2026-06-02 13:00:00", "2026-06-02 16:00:00", freq="1min", tz="US/Eastern")
    
    t = t1.append(t2)
    
    df = pd.DataFrame(index=t)
    df['open'] = 100.0
    df['high'] = 101.0
    df['low'] = 99.0
    df['close'] = 100.0
    df['volume'] = 100
    
    # Run calculate_ib_statistics_v5 for NY AM IB
    facts, touches, fvgs = calculate_ib_statistics_v5(
        df_1m=df,
        symbol="NQ1",
        session_choice="NY AM IB",
        time_basis="ET_fixed",
        use_fvg=True
    )
    
    # It should run successfully without ValueError!
    assert not facts.empty
    
    # Day 1 should have IB stats computed
    day1_facts = facts[facts['trading_day'] == pd.Timestamp("2026-06-01").date()]
    assert not day1_facts.empty
    
    # Day 2 has no IB bars, so it should not be in the final facts
    day2_facts = facts[facts['trading_day'] == pd.Timestamp("2026-06-02").date()]
    assert day2_facts.empty
