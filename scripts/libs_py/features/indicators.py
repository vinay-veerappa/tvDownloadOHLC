import pandas as pd
import numpy as np

# Layer 2: Feature Engineering — Core Technical Indicator Implementations.
# These functions should be strictly causal (no look-ahead).

def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Computes Average True Range (Wilder's or EMA).
    Universal volatility normalizer for signals and risk.
    """
    tr = pd.concat([
        (df['high'] - df['low']),
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    
    return tr.rolling(window=period).mean() # Simplified Wilder's

def compute_bollinger_bands(df: pd.DataFrame, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """
    Bollinger Bands (Volatility-based Mean Reversion Bands).
    Returns basic bands + derived position features (bandwidth, %b, zscore).
    """
    mid = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    
    # Bandwidth: measure of volatility relative to its mean
    bandwidth = (upper - lower) / mid
    
    # Pct_B: relative price position in the channel (0-1)
    # Price beyond bands = >1.0 / <0.0
    pct_b = (df['close'] - lower) / (upper - lower)
    
    # Z-Score: ATR-normalized distance from Mid
    zscore = (df['close'] - mid) / std
    
    return pd.DataFrame({
        'bb_mid': mid,
        'bb_upper': upper,
        'bb_lower': lower,
        'bb_bandwidth': bandwidth,
        'bb_pct_b': pct_b,
        'bb_zscore': zscore
    }, index=df.index)

def compute_keltner_channels(df: pd.DataFrame, period: int = 20, atr_period: int = 14, atr_mult: float = 2.0) -> pd.DataFrame:
    """
    Keltner Channels (Trend-based Mean Reversion Bands).
    EMA mid + ATR outer boundaries.
    """
    mid = df['close'].ewm(span=period).mean()
    atr = compute_atr(df, period=atr_period)
    upper = mid + atr_mult * atr
    lower = mid - atr_mult * atr
    
    # %K: relative position within the Keltner channel
    pct_k = (df['close'] - lower) / (upper - lower)
    
    return pd.DataFrame({
        'kc_mid': mid,
        'kc_upper': upper,
        'kc_lower': lower,
        'kc_pct_k': pct_k
    }, index=df.index)

def compute_squeeze(df: pd.DataFrame, bb: pd.DataFrame, kc: pd.DataFrame) -> pd.DataFrame:
    """
    TTMSqueeze-style detection: Bollinger Bands inside Keltner Channels.
    Indicates potential breakout regimes.
    """
    is_squeeze = (bb['bb_upper'] < kc['kc_upper']) & (bb['bb_lower'] > kc['kc_lower'])
    
    # Squeeze duration (number of consecutive bars in squeeze)
    squeeze_duration = is_squeeze.astype(int).groupby(is_squeeze.ne(is_squeeze.shift()).cumsum()).cumsum()
    squeeze_duration = squeeze_duration.where(is_squeeze, 0)
    
    return pd.DataFrame({
        'is_squeeze': is_squeeze,
        'squeeze_duration': squeeze_duration
    }, index=df.index)
