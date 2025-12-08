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
    AvailableIndicator
)
from api.services.data_loader import load_parquet, get_available_data
from api.services.indicators import calculate_indicators, get_available_indicators


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
