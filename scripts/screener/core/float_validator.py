"""
float_validator.py
==================
Cross-references Finviz reported float shares against yfinance sharesOutstanding / floatShares.
Flags discrepancies > 15% to prevent false low-float momentum signals on outdated data.
"""
from typing import Dict, Any, Optional

def validate_float(finviz_float: Optional[float], yf_float: Optional[float]) -> Dict[str, Any]:
    """
    Cross-validates Finviz reported float against yfinance float.
    Returns validation report dictionary.
    """
    f_val = float(finviz_float or 0.0)
    y_val = float(yf_float or 0.0)

    if f_val <= 0.0 or y_val <= 0.0:
        eff = max(f_val, y_val)
        return {
            "is_valid": True,
            "discrepancy_pct": 0.0,
            "effective_float": eff,
            "flagged": False
        }

    discrepancy_pct = abs(f_val - y_val) / y_val * 100.0
    is_valid = discrepancy_pct <= 15.0

    return {
        "is_valid": is_valid,
        "discrepancy_pct": round(discrepancy_pct, 2),
        "effective_float": max(f_val, y_val), # Conservative higher float
        "flagged": not is_valid
    }
