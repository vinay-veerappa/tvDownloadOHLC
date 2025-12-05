import pandas as pd
import numpy as np

class Indicators:
    """Modular indicator calculation library"""
    
    @staticmethod
    def sma(data, period=20):
        """Simple Moving Average"""
        df = pd.DataFrame(data)
        df['sma'] = df['close'].rolling(window=period).mean()
        return df['sma'].dropna().tolist()
    
    @staticmethod
    def ema(data, period=20):
        """Exponential Moving Average"""
        df = pd.DataFrame(data)
        df['ema'] = df['close'].ewm(span=period, adjust=False).mean()
        return df['ema'].dropna().tolist()
    
    @staticmethod
    def bollinger_bands(data, period=20, std_dev=2):
        """Bollinger Bands - returns (upper, middle, lower)"""
        df = pd.DataFrame(data)
        df['sma'] = df['close'].rolling(window=period).mean()
        df['std'] = df['close'].rolling(window=period).std()
        df['upper'] = df['sma'] + (df['std'] * std_dev)
        df['lower'] = df['sma'] - (df['std'] * std_dev)
        
        result = df[['upper', 'sma', 'lower']].dropna()
        return {
            'upper': result['upper'].tolist(),
            'middle': result['sma'].tolist(),
            'lower': result['lower'].tolist()
        }
    
    @staticmethod
    def rsi(data, period=14):
        """Relative Strength Index"""
        df = pd.DataFrame(data)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.dropna().tolist()
    
    @staticmethod
    def macd(data, fast=12, slow=26, signal=9):
        """MACD - returns (macd, signal, histogram)"""
        df = pd.DataFrame(data)
        df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
        df['macd'] = df['ema_fast'] - df['ema_slow']
        df['signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
        df['histogram'] = df['macd'] - df['signal']
        
        result = df[['macd', 'signal', 'histogram']].dropna()
        return {
            'macd': result['macd'].tolist(),
            'signal': result['signal'].tolist(),
            'histogram': result['histogram'].tolist()
        }
    
    @staticmethod
    def vwap(data):
        """Volume Weighted Average Price"""
        df = pd.DataFrame(data)
        # For VWAP we need volume, but our data doesn't have it
        # So we'll use typical price * 1 (assuming equal volume)
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['cumulative_tp'] = df['typical_price'].cumsum()
        df['cumulative_volume'] = range(1, len(df) + 1)
        df['vwap'] = df['cumulative_tp'] / df['cumulative_volume']
        return df['vwap'].tolist()
    
    @staticmethod
    def atr(data, period=14):
        """Average True Range"""
        df = pd.DataFrame(data)
        df['h-l'] = df['high'] - df['low']
        df['h-pc'] = abs(df['high'] - df['close'].shift(1))
        df['l-pc'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=period).mean()
        return df['atr'].dropna().tolist()

def calculate_indicator(indicator_name, data, **params):
    """
    Central function to calculate any indicator
    
    Args:
        indicator_name: str - name of indicator (sma, ema, bb, rsi, macd, vwap, atr)
        data: list of OHLC dicts
        **params: indicator-specific parameters
    
    Returns:
        dict with indicator values
    """
    indicators = Indicators()
    
    if indicator_name == 'sma':
        period = params.get('period', 20)
        return {'values': indicators.sma(data, period)}
    
    elif indicator_name == 'ema':
        period = params.get('period', 20)
        return {'values': indicators.ema(data, period)}
    
    elif indicator_name == 'bb':
        period = params.get('period', 20)
        std_dev = params.get('std_dev', 2)
        return indicators.bollinger_bands(data, period, std_dev)
    
    elif indicator_name == 'rsi':
        period = params.get('period', 14)
        return {'values': indicators.rsi(data, period)}
    
    elif indicator_name == 'macd':
        fast = params.get('fast', 12)
        slow = params.get('slow', 26)
        signal = params.get('signal', 9)
        return indicators.macd(data, fast, slow, signal)
    
    elif indicator_name == 'vwap':
        return {'values': indicators.vwap(data)}
    
    elif indicator_name == 'atr':
        period = params.get('period', 14)
        return {'values': indicators.atr(data, period)}
    
    else:
        raise ValueError(f"Unknown indicator: {indicator_name}")
