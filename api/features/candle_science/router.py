from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, Optional
from api.features.candle_science.service import CandleScienceService
from api.features.shared.data_loader import get_available_data

router = APIRouter()

@router.get("/metadata")
async def get_metadata():
    """Get available tickers and timeframes."""
    data = get_available_data()
    return {"available_data": data}

@router.get("/filters")
async def get_filters(ticker: str, timeframe: str):
    """Get available filter values for a specific ticker/timeframe."""
    options = CandleScienceService.get_filter_options(ticker, timeframe)
    if not options:
        raise HTTPException(status_code=404, detail="Data not found")
    return options

@router.post("/calculate")
async def calculate_stats(
    ticker: str = Body(...),
    timeframe: str = Body(...),
    filters: Optional[Dict[str, Any]] = Body(None)
):
    """Execute statistical analysis."""
    stats = CandleScienceService.calculate_stats(ticker, timeframe, filters)
    if "error" in stats:
        raise HTTPException(status_code=400, detail=stats["error"])
    return stats
