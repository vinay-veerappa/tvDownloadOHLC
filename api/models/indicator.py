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
