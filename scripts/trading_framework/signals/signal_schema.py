import pandas as pd
from typing import List, Dict

# Centralized Signal Schema Mapping — Layer 4 architecture contract.
# Every Strategy Logic (BoxReversion, BB Reversion, etc) must output this format.
# Every Engine (Vectorized, Event-driven) must consume this format.

SIGNAL_SCHEMA = {
    # Identity
    "signal_id":            str,      # unique random ID or timestamp-based
    "signal_time":          pd.Timestamp, # precise bar when signal fired
    "symbol":               str,       # e.g., "NQ1"

    # Direction and type
    "direction":            str,       # "long" or "short"
    "signal_type":          str,       # e.g., "band_touch", "false_breakout"
    "band_type":            str,       # "bollinger", "keltner", "box"

    # Entry reference (execution logic happens at entry_time + 1 bar usually)
    "entry_price":          float,     # Reference price at signal time

    # Targets and stops (pre-computed by strategy logic)
    "target1_price":        float,     # primary target (Midline)
    "target2_price":        float,     # secondary target (Opposite Band)
    "stop_price":           float,     # invalidation level

    # Contextual Snapshots (captured at signal time for ML layer consumption)
    "entry_regime":         str,       # current market regime
    "entry_regime_confidence": float,  # model consensus confidence
    "entry_session":        str,       # Asia, London, NY_AM, NY_PM
    "entry_vix_pctile":     float,     # VIX relative level
    "entry_is_macro_window": bool      # True if fired during ICT macro
}

def validate_signals(df: pd.DataFrame) -> List[str]:
    """
    Validates that a signal dataframe conforms to the Layer 4 schema.
    Returns list of validation errors.
    """
    errors = []
    missing_cols = [col for col in SIGNAL_SCHEMA.keys() if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing columns: {missing_cols}")
    
    # Optional: type checking (vectorized)
    # for col, dtype in SIGNAL_SCHEMA.items():
    #     if col in df.columns and not pd.api.types.is_dtype_equal(df[col].dtype, dtype):
    #         errors.append(f"Invalid dtype for {col}: Expected {dtype}, got {df[col].dtype}")
            
    return errors
