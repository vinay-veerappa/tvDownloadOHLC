"""
Pydantic models for indicator API requests and responses
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class OHLCVBar(BaseModel):
    """Single OHLCV bar"""
    time: int  # Unix timestamp
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0


class IndicatorRequest(BaseModel):
    """Request to calculate indicators from client-provided OHLCV data"""
    ohlcv: List[OHLCVBar]  # OHLCV data from frontend
    indicators: List[str]  # e.g., ["vwap", "sma_20", "ema_9", "atr_14"]


class IndicatorFromFileRequest(BaseModel):
    """Request to calculate indicators from stored data (for backtesting)"""
    ticker: str
    timeframe: str
    indicators: List[str]
    start_time: Optional[int] = None
    end_time: Optional[int] = None


class IndicatorResponse(BaseModel):
    """Response with calculated indicator values"""
    time: List[int]  # Unix timestamps
    indicators: Dict[str, List[Optional[float]]]  # {"vwap": [...], "sma_20": [...]}


class AvailableIndicator(BaseModel):
    """Info about an available indicator"""
    name: str
    description: str
    parameters: Dict[str, Any]


class AvailableIndicatorsResponse(BaseModel):
    """List of all available indicators"""
    indicators: List[AvailableIndicator]


class VWAPSettings(BaseModel):
    """Settings for VWAP calculation"""
    anchor: str = "session"  # session, week, month
    anchor_time: str = "09:30"  # Time to reset (HH:MM)
    anchor_timezone: str = "America/New_York"
    bands: List[float] = [1.0]  # Std dev multipliers [1.0, 2.0, 3.0]
    source: str = "hlc3"  # hlc3, close, ohlc4


class IndicatorRequestWithSettings(BaseModel):
    """Request with indicator-specific settings"""
    ohlcv: List[OHLCVBar]
    indicators: List[str]
    vwap_settings: Optional[VWAPSettings] = None
    timeframe: Optional[str] = None  # For auto-hiding VWAP on daily+


class VWAPFromFileRequest(BaseModel):
    """Request VWAP calculation from backend data files"""
    ticker: str
    timeframe: str
    vwap_settings: Optional[VWAPSettings] = None
    start_time: Optional[int] = None  # Unix timestamp filter
    end_time: Optional[int] = None    # Unix timestamp filter
