"""
Indicator calculation service using pandas-ta
"""

import pandas as pd
import pandas_ta as ta
from typing import Dict, List, Optional, Any


# Available indicators with their descriptions and parameters
AVAILABLE_INDICATORS = {
    "vwap": {
        "description": "Volume Weighted Average Price",
        "parameters": {}
    },
    "sma": {
        "description": "Simple Moving Average",
        "parameters": {"period": "int, default 20"}
    },
    "ema": {
        "description": "Exponential Moving Average", 
        "parameters": {"period": "int, default 21"}
    },
    "atr": {
        "description": "Average True Range",
        "parameters": {"period": "int, default 14"}
    },
    "rsi": {
        "description": "Relative Strength Index",
        "parameters": {"period": "int, default 14"}
    },
    "bbands": {
        "description": "Bollinger Bands (upper, middle, lower)",
        "parameters": {"period": "int, default 20", "std": "float, default 2.0"}
    },
    "macd": {
        "description": "MACD (line, signal, histogram)",
        "parameters": {"fast": "int, default 12", "slow": "int, default 26", "signal": "int, default 9"}
    },
}


def parse_indicator_name(indicator: str) -> tuple:
    """
    Parse indicator name with optional period
    e.g., "sma_20" -> ("sma", {"period": 20})
          "ema_9" -> ("ema", {"period": 9})
          "vwap" -> ("vwap", {})
    """
    parts = indicator.lower().split("_")
    name = parts[0]
    params = {}
    
    if len(parts) > 1:
        try:
            params["period"] = int(parts[1])
        except ValueError:
            pass
    
    return name, params


def calculate_indicator(df: pd.DataFrame, indicator: str) -> Dict[str, List[Optional[float]]]:
    """
    Calculate a single indicator and return as dict of lists
    
    Returns dict because some indicators return multiple series (e.g., bbands, macd)
    """
    name, params = parse_indicator_name(indicator)
    period = params.get("period")
    
    result = {}
    
    if name == "vwap":
        values = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
        result[indicator] = values.tolist()
    
    elif name == "sma":
        p = period or 20
        values = ta.sma(df['close'], length=p)
        result[f"sma_{p}"] = values.tolist()
    
    elif name == "ema":
        p = period or 21
        values = ta.ema(df['close'], length=p)
        result[f"ema_{p}"] = values.tolist()
    
    elif name == "atr":
        p = period or 14
        values = ta.atr(df['high'], df['low'], df['close'], length=p)
        result[f"atr_{p}"] = values.tolist()
    
    elif name == "rsi":
        p = period or 14
        values = ta.rsi(df['close'], length=p)
        result[f"rsi_{p}"] = values.tolist()
    
    elif name == "bbands":
        p = period or 20
        bb = ta.bbands(df['close'], length=p, std=2.0)
        if bb is not None:
            result[f"bbands_upper_{p}"] = bb.iloc[:, 0].tolist()  # BBU
            result[f"bbands_mid_{p}"] = bb.iloc[:, 1].tolist()    # BBM
            result[f"bbands_lower_{p}"] = bb.iloc[:, 2].tolist()  # BBL
    
    elif name == "macd":
        macd_df = ta.macd(df['close'])
        if macd_df is not None:
            result["macd_line"] = macd_df.iloc[:, 0].tolist()
            result["macd_signal"] = macd_df.iloc[:, 1].tolist()
            result["macd_histogram"] = macd_df.iloc[:, 2].tolist()
    
    # Convert NaN to None for JSON serialization
    for key in result:
        result[key] = [None if pd.isna(v) else v for v in result[key]]
    
    return result


def calculate_indicators(df: pd.DataFrame, indicators: List[str]) -> Dict[str, List[Optional[float]]]:
    """Calculate multiple indicators and return combined result"""
    all_results = {}
    
    for indicator in indicators:
        try:
            result = calculate_indicator(df, indicator)
            all_results.update(result)
        except Exception as e:
            print(f"Error calculating {indicator}: {e}")
    
    return all_results


def get_available_indicators() -> List[Dict[str, Any]]:
    """Return list of available indicators with their info"""
    return [
        {
            "name": name,
            "description": info["description"],
            "parameters": info["parameters"]
        }
        for name, info in AVAILABLE_INDICATORS.items()
    ]
