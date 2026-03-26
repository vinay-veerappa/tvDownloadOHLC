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
            # Normalize column names
            ohlc_df.columns = [c.lower() for c in ohlc_df.columns]
            
            required_cols = {
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume"
            }
            
            for char in input_type:
                col_name = required_cols.get(char)
                if col_name not in ohlc_df.columns:
                    raise KeyError(f"Missing required column: {col_name}")
            
            return func(ohlc_df, *args, **kwargs)
        return wrapper
    return decorator
