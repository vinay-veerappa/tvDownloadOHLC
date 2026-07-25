from functools import wraps
import pandas as pd

def validate_ohlc(input_type="ohlc"):
    """
    Decorator to ensure the input DataFrame has the required OHLC columns.
    Standardizes column names to lowercase.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(ohlc_df: pd.DataFrame, *args, **kwargs):
            # Normalize column names (avoid mutation if already lowercase).
            cols = ohlc_df.columns
            lower_cols = cols.str.lower()
            if not lower_cols.equals(cols):
                ohlc_df = ohlc_df.rename(columns=dict(zip(cols, lower_cols)))
            # Ensure required columns exist without re-validating repeatedly.
            required_cols = {
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume"
            }
            missing = [
                required_cols[char]
                for char in input_type
                if required_cols[char] not in cols
            ]
            if missing:
                raise KeyError(f"Missing required columns: {missing}")
            return func(ohlc_df, *args, **kwargs)
        return wrapper
    return decorator
