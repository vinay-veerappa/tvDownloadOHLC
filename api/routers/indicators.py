"""
Indicators API Router
"""

from fastapi import APIRouter, HTTPException
import pandas as pd
from api.models.indicator import (
    IndicatorRequest,
    IndicatorFromFileRequest,
    IndicatorResponse,
    AvailableIndicatorsResponse,
    AvailableIndicator,
    IndicatorRequestWithSettings,
    VWAPSettings,
    VWAPFromFileRequest
)
from api.services.data_loader import load_parquet, get_available_data
from api.services.indicators import calculate_indicators, get_available_indicators
from api.services.vwap import calculate_vwap_with_settings, should_hide_vwap


router = APIRouter()


@router.post("/calculate", response_model=IndicatorResponse)
async def calculate(request: IndicatorRequest):
    """
    Calculate indicators from client-provided OHLCV data.
    Use this for chart indicator overlays to ensure 100% consistency
    with displayed data.
    
    Example request:
    {
        "ohlcv": [
            {"time": 1733184000, "open": 6000, "high": 6010, "low": 5990, "close": 6005, "volume": 1000},
            ...
        ],
        "indicators": ["vwap", "sma_20", "ema_9"]
    }
    """
    if not request.ohlcv:
        raise HTTPException(status_code=400, detail="OHLCV data is required")
    
    # Convert to DataFrame
    df = pd.DataFrame([bar.model_dump() for bar in request.ohlcv])
    
    # Calculate indicators
    indicator_values = calculate_indicators(df, request.indicators)
    
    return IndicatorResponse(
        time=df['time'].tolist(),
        indicators=indicator_values
    )


@router.post("/calculate-v2", response_model=IndicatorResponse)
async def calculate_with_settings(request: IndicatorRequestWithSettings):
    """
    Calculate indicators with custom settings (e.g., VWAP anchor period).
    
    Example request:
    {
        "ohlcv": [...],
        "indicators": ["vwap", "sma_20"],
        "timeframe": "5m",
        "vwap_settings": {
            "anchor": "session",
            "anchor_time": "09:30",
            "anchor_timezone": "America/New_York",
            "bands": [1.0, 2.0],
            "source": "hlc3"
        }
    }
    """
    if not request.ohlcv:
        raise HTTPException(status_code=400, detail="OHLCV data is required")
    
    # Convert to DataFrame
    df = pd.DataFrame([bar.model_dump() for bar in request.ohlcv])
    
    all_indicators = {}
    non_vwap_indicators = []
    
    for ind in request.indicators:
        if ind.lower() == 'vwap':
            # Check if should hide on this timeframe
            if request.timeframe and should_hide_vwap(request.timeframe):
                continue  # Skip VWAP on daily+ timeframes
            
            # Use VWAP settings if provided
            settings = request.vwap_settings or VWAPSettings()
            vwap_result = calculate_vwap_with_settings(
                df,
                anchor=settings.anchor,
                anchor_time=settings.anchor_time,
                anchor_timezone=settings.anchor_timezone,
                bands=settings.bands,
                source=settings.source
            )
            all_indicators.update(vwap_result)
        else:
            non_vwap_indicators.append(ind)
    
    # Calculate non-VWAP indicators
    if non_vwap_indicators:
        other_indicators = calculate_indicators(df, non_vwap_indicators)
        all_indicators.update(other_indicators)
    
    return IndicatorResponse(
        time=df['time'].tolist(),
        indicators=all_indicators
    )


@router.post("/calculate-from-file", response_model=IndicatorResponse)
async def calculate_from_file(request: IndicatorFromFileRequest):
    """
    Calculate indicators from stored data files.
    Use this for backtesting where full historical data is needed.
    
    Example request:
    {
        "ticker": "ES1",
        "timeframe": "5m",
        "indicators": ["vwap", "sma_20"]
    }
    """
    # Load data from file
    df = load_parquet(request.ticker, request.timeframe)
    
    if df is None:
        raise HTTPException(
            status_code=404,
            detail=f"Data not found for {request.ticker} {request.timeframe}"
        )
    
    # Filter by time range if specified
    if request.start_time:
        df = df[df['time'] >= request.start_time]
    if request.end_time:
        df = df[df['time'] <= request.end_time]
    
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail="No data in specified time range"
        )
    
    # Calculate indicators
    indicator_values = calculate_indicators(df, request.indicators)
    
    return IndicatorResponse(
        time=df['time'].tolist(),
        indicators=indicator_values
    )


@router.get("/available", response_model=AvailableIndicatorsResponse)
async def available():
    """List all available indicators"""
    indicators = get_available_indicators()
    return AvailableIndicatorsResponse(
        indicators=[
            AvailableIndicator(**ind) for ind in indicators
        ]
    )


@router.get("/data")
async def list_data():
    """List all available ticker/timeframe combinations"""
    return {"data": get_available_data()}


@router.post("/vwap-from-file", response_model=IndicatorResponse)
async def calculate_vwap_from_file(request: VWAPFromFileRequest):
    """
    Calculate VWAP from backend data files (uses actual volume data).
    
    This is preferred over calculate-v2 when the frontend doesn't have volume
    or uses resampled data. The backend loads the parquet file with full
    volume information.
    
    Example request:
    {
        "ticker": "ES1",
        "timeframe": "1m",
        "vwap_settings": {
            "anchor": "session",
            "anchor_time": "18:00",
            "bands": [1.0, 2.0]
        }
    }
    """
    # Check if should hide on this timeframe
    if should_hide_vwap(request.timeframe):
        return IndicatorResponse(time=[], indicators={})
    
    # Load data from file
    df = load_parquet(request.ticker, request.timeframe)
    
    if df is None:
        raise HTTPException(
            status_code=404,
            detail=f"Data not found for {request.ticker} {request.timeframe}"
        )
    
    # Filter by time range if specified
    if request.start_time:
        df = df[df['time'] >= request.start_time]
    if request.end_time:
        df = df[df['time'] <= request.end_time]
    
    if df.empty:
        return IndicatorResponse(time=[], indicators={})
    
    # Use VWAP settings if provided
    settings = request.vwap_settings or VWAPSettings()
    
    vwap_result = calculate_vwap_with_settings(
        df,
        anchor=settings.anchor,
        anchor_time=settings.anchor_time,
        anchor_timezone=settings.anchor_timezone,
        bands=settings.bands,
        source=settings.source
    )
    
    return IndicatorResponse(
        time=df['time'].tolist(),
        indicators=vwap_result
    )

