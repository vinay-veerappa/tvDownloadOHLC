"""
Indicator calculation service using pandas-ta
"""

import pandas as pd
from typing import Dict, List, Optional, Any

# Optional talib import - not all environments have it installed
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    talib = None
    TALIB_AVAILABLE = False
    print("[Indicators] Warning: talib not installed. SMA, EMA, ATR, RSI, BBANDS, MACD indicators will not be available.")



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
        # Custom Anchored VWAP Implementation
        try:
            df_copy = df.copy()
            # Ensure time is datetime in UTC first (assuming input is unix seconds)
            df_copy['dt'] = pd.to_datetime(df_copy['time'], unit='s', utc=True)
            
            # Default to Eastern for session anchoring if not specified
            tz = params.get('timezone', 'America/New_York')
            df_copy['dt_tz'] = df_copy['dt'].dt.tz_convert(tz)
            
            # Parse anchor time (e.g., "18:00" or default "09:30" or "00:00")
            anchor_time_str = params.get('anchor_time', '00:00')
            h, m = map(int, anchor_time_str.split(':'))
            
            # Identify session changes
            # A new session starts if time >= anchor_time AND previous time < anchor_time (crossing)
            # OR if the date changes and we are past anchor time
            # Simplest approach: Shift time by roughly (24 - anchor_hour) to align "start" to 00:00 local "virtual" time
            # then group by date of this shifted time.
            
            # Offset logic: 
            # If anchor is 18:00, we want 18:01 today to be same session as 17:59 tomorrow? No.
            # 18:00 today starts the session for tomorrow.
            # So 18:00 T -> 17:59 T+1 is one session.
            # If we subtract 18 hours, 18:00 becomes 00:00. 
            # 17:59 (next day) becomes 23:59 (prev day "session").
            # So just subtracting the offset and taking the .date() works for grouping.
            
            offset = pd.Timedelta(hours=h, minutes=m)
            df_copy['session_group'] = (df_copy['dt_tz'] - offset).dt.date
            
            # Helper for PV and P2V (Price * Price * Volume) for Variance
            df_copy['pv'] = df_copy['close'] * df_copy['volume']
            df_copy['p2v'] = df_copy['close'] * df_copy['close'] * df_copy['volume']
            
            # Calculate cumulative sums per session
            df_copy['cum_pv'] = df_copy.groupby('session_group')['pv'].cumsum()
            df_copy['cum_vol'] = df_copy.groupby('session_group')['volume'].cumsum()
            df_copy['cum_p2v'] = df_copy.groupby('session_group')['p2v'].cumsum()
            
            # Calculate VWAP
            vwap_values = df_copy['cum_pv'] / df_copy['cum_vol']
            result[indicator] = vwap_values.tolist()
            
            # Calculate Bands if requested
            bands = params.get('bands', []) # List of multipliers e.g. [1.0, 2.0]
            if bands:
                # Variance = (CumP2V / CumVol) - (VWAP^2)
                # Standard Deviation = sqrt(Variance)
                variance = (df_copy['cum_p2v'] / df_copy['cum_vol']) - (vwap_values * vwap_values)
                # Ensure variance is non-negative (floating point errors)
                variance = variance.clip(lower=0)
                std_dev = variance ** 0.5
                
                for mult in bands:
                    if mult <= 0: continue
                    # Format key to match frontend expectation (e.g. 1.0 -> 1_0)
                    mult_str = f"{mult:.1f}".replace('.', '_')
                    upper_key = f"{indicator}_upper_{mult_str}"
                    lower_key = f"{indicator}_lower_{mult_str}"
                    
                    result[upper_key] = (vwap_values + (std_dev * mult)).tolist()
                    result[lower_key] = (vwap_values - (std_dev * mult)).tolist()
            
        except Exception as e:
            print(f"Error calculating Custom VWAP: {e}")
            result[indicator] = [None] * len(df)
    
    elif name == "sma":
        if not TALIB_AVAILABLE:
            result[f"sma_{period or 20}"] = [None] * len(df)
        else:
            p = period or 20
            values = talib.SMA(df['close'], timeperiod=p)
            result[f"sma_{p}"] = values.tolist()
    
    elif name == "ema":
        if not TALIB_AVAILABLE:
            result[f"ema_{period or 21}"] = [None] * len(df)
        else:
            p = period or 21
            values = talib.EMA(df['close'], timeperiod=p)
            result[f"ema_{p}"] = values.tolist()
    
    elif name == "atr":
        if not TALIB_AVAILABLE:
            result[f"atr_{period or 14}"] = [None] * len(df)
        else:
            p = period or 14
            values = talib.ATR(df['high'], df['low'], df['close'], timeperiod=p)
            result[f"atr_{p}"] = values.tolist()
    
    elif name == "rsi":
        if not TALIB_AVAILABLE:
            result[f"rsi_{period or 14}"] = [None] * len(df)
        else:
            p = period or 14
            values = talib.RSI(df['close'], timeperiod=p)
            result[f"rsi_{p}"] = values.tolist()
    
    elif name == "bbands":
        if not TALIB_AVAILABLE:
            p = period or 20
            result[f"bbands_upper_{p}"] = [None] * len(df)
            result[f"bbands_mid_{p}"] = [None] * len(df)
            result[f"bbands_lower_{p}"] = [None] * len(df)
        else:
            p = period or 20
            upper, middle, lower = talib.BBANDS(df['close'], timeperiod=p, nbdevup=2.0, nbdevdn=2.0, matype=0)
            result[f"bbands_upper_{p}"] = upper.tolist()
            result[f"bbands_mid_{p}"] = middle.tolist()
            result[f"bbands_lower_{p}"] = lower.tolist()
    
    elif name == "macd":
        if not TALIB_AVAILABLE:
            result["macd_line"] = [None] * len(df)
            result["macd_signal"] = [None] * len(df)
            result["macd_histogram"] = [None] * len(df)
        else:
            # MACD default: fast=12, slow=26, signal=9
            fast = params.get("fast", 12)
            slow = params.get("slow", 26)
            signal = params.get("signal", 9)
            macd, macdsignal, macdhist = talib.MACD(df['close'], fastperiod=fast, slowperiod=slow, signalperiod=signal)
            result["macd_line"] = macd.tolist()
            result["macd_signal"] = macdsignal.tolist()
            result["macd_histogram"] = macdhist.tolist()
    
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
