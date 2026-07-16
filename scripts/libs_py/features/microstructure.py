import pandas as pd
import numpy as np

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.features.indicators import compute_atr

# Layer 2: Feature Engineering — Market Microstructure Features.
# Focuses on arrival velocity, momentum, and internal price action.

def compute_arrival_velocity(df: pd.DataFrame, lookback: int = 10) -> pd.Series:
    """
    Normalized speed of price movement (ATR-relative).
    (Close - Close[lookback]) / ATR
    Indicates how fast we are approaching the mean/band.
    """
    atr = compute_atr(df, period=lookback*2)
    velocity = (df['close'] - df['close'].shift(lookback)) / atr
    return velocity.fillna(0)

def compute_momentum_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Price action dynamics beyond indicator bands.
    1. bar_range_atr: Relative expansion of the current bar.
    2. close_position_in_bar: % position of close relative to high/low.
    3. consecutive_direction: Number of bars moving in one direction.
    """
    atr = compute_atr(df, period=14)
    bar_range = (df['high'] - df['low'])
    bar_range_atr = bar_range / atr
    
    close_pos = (df['close'] - df['low']) / bar_range.replace(0, 0.0001)
    
    # Consecutive direction
    up = (df['close'] > df['close'].shift(1)).astype(int)
    down = (df['close'] < df['close'].shift(1)).astype(int)
    
    # Calculate streaks
    up_streaks = up.groupby(up.ne(up.shift()).cumsum()).cumsum()
    up_streaks = up_streaks.where(up == 1, 0)
    
    down_streaks = down.groupby(down.ne(down.shift()).cumsum()).cumsum()
    down_streaks = down_streaks.where(down == 1, 0)
    
    consecutive_dir = up_streaks - down_streaks
    
    return pd.DataFrame({
        'bar_range_atr': bar_range_atr,
        'close_position_in_bar': close_pos,
        'consecutive_direction': consecutive_dir
    }, index=df.index)
