from fastapi import APIRouter, Response
import pandas as pd
import numpy as np
from api.features.shared.data_loader import load_parquet

router = APIRouter()

@router.get("/{ticker}/{timeframe}")
async def get_ohlc_slice(
    ticker: str,
    timeframe: str,
    t_start: float,
    t_end: float,
    limit: int = 120000,
    format: str = "binary",
    direction: str = "left" # "left" or "right"
):
    df = load_parquet(ticker, timeframe, t_end=t_end)
    
    if df is None or df.empty:
        return Response(status_code=404)
        
    # Open-Boundary Slicing (Half-open interval)
    mask = (df['time'] >= t_start) & (df['time'] < t_end)
    
    if direction == "right":
        slice_df = df[mask].head(limit)
    else:
        slice_df = df[mask].tail(limit)
    
    if format == "binary":
        # Float64 Alignment (Prevents 10-digit Unix truncation)
        arr = slice_df[["time", "open", "high", "low", "close"]].values.astype(np.float64)
        return Response(content=arr.tobytes(), media_type="application/octet-stream")
    
    from fastapi.responses import ORJSONResponse
    return ORJSONResponse(slice_df[["time", "open", "high", "low", "close"]].to_dict(orient="records"))
