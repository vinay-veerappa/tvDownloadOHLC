from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from indicators import calculate_indicator

app = FastAPI(title="ES Futures Data API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory
DATA_DIR = Path("data")

@app.get("/")
async def root():
    """Serve the chart UI"""
    import os
    html_path = os.path.join(os.getcwd(), "chart_ui.html")
    return FileResponse(html_path)

@app.get("/indicator_manager.js")
async def get_indicator_manager():
    """Serve the indicator manager JS file"""
    import os
    js_path = os.path.join(os.getcwd(), "indicator_manager.js")
    return FileResponse(js_path, media_type="application/javascript")

@app.get("/demo")
async def get_demo():
    """Serve KLineChart demo"""
    import os
    demo_path = os.path.join(os.getcwd(), "demo_klinechart.html")
    return FileResponse(demo_path)

@app.get("/api/timeframes")
async def get_timeframes():
    """Get available timeframes"""
    timeframes = []
    for file in DATA_DIR.glob("ES_*.parquet"):
        tf = file.stem.replace("ES_", "")
        timeframes.append(tf)
    return {"timeframes": sorted(timeframes)}

@app.get("/api/range/{timeframe}")
async def get_date_range(timeframe: str):
    """Get the available date range for a timeframe"""
    parquet_file = DATA_DIR / f"ES_{timeframe}.parquet"
    
    if not parquet_file.exists():
        raise HTTPException(status_code=404, detail=f"Timeframe {timeframe} not found")
    
    df = pd.read_parquet(parquet_file)
    
    return {
        "timeframe": timeframe,
        "start": df.index.min().isoformat(),
        "end": df.index.max().isoformat(),
        "bars": len(df)
    }

@app.get("/api/ohlc/{timeframe}")
async def get_ohlc(
    timeframe: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 10000
):
    """
    Get OHLC data for a specific timeframe and date range
    
    Parameters:
    - timeframe: 1m, 5m, 15m, 1h, 4h, 1D
    - start: ISO datetime string (optional)
    - end: ISO datetime string (optional)
    - limit: Maximum number of bars to return (default: 10000)
    """
    parquet_file = DATA_DIR / f"ES_{timeframe}.parquet"
    
    if not parquet_file.exists():
        raise HTTPException(status_code=404, detail=f"Timeframe {timeframe} not found")
    
    # Load data
    df = pd.read_parquet(parquet_file)
    
    # Filter by date range
    if start:
        start_dt = pd.to_datetime(start)
        df = df[df.index >= start_dt]
    
    if end:
        end_dt = pd.to_datetime(end)
        df = df[df.index <= end_dt]
    
    # Limit number of bars (take most recent if exceeds limit)
    if len(df) > limit:
        df = df.tail(limit)
    
    # Convert to format for lightweight-charts
    data = []
    for idx, row in df.iterrows():
        data.append({
            "time": int(idx.timestamp()),  # Unix timestamp
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close'])
        })
    
    return {
        "timeframe": timeframe,
        "bars": len(data),
        "data": data
    }

@app.get("/api/indicator/{timeframe}/{indicator_name}")
async def get_indicator(
    timeframe: str,
    indicator_name: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 10000,
    period: Optional[int] = Query(None),
    std_dev: Optional[float] = Query(None),
    fast: Optional[int] = Query(None),
    slow: Optional[int] = Query(None),
    signal: Optional[int] = Query(None)
):
    """
    Calculate indicator values for a timeframe
    
    Available indicators:
    - sma: Simple Moving Average (period)
    - ema: Exponential Moving Average (period)
    - bb: Bollinger Bands (period, std_dev)
    - rsi: Relative Strength Index (period)
    - macd: MACD (fast, slow, signal)
    - vwap: Volume Weighted Average Price
    - atr: Average True Range (period)
    """
    parquet_file = DATA_DIR / f"ES_{timeframe}.parquet"
    
    if not parquet_file.exists():
        raise HTTPException(status_code=404, detail=f"Timeframe {timeframe} not found")
    
    # Load data
    df = pd.read_parquet(parquet_file)
    
    # Filter by date range
    if start:
        start_dt = pd.to_datetime(start)
        df = df[df.index >= start_dt]
    
    if end:
        end_dt = pd.to_datetime(end)
        df = df[df.index <= end_dt]
    
    # Limit number of bars
    if len(df) > limit:
        df = df.tail(limit)
    
    # Convert to list of dicts for indicator calculation
    data_list = []
    for idx, row in df.iterrows():
        data_list.append({
            "time": int(idx.timestamp()),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close'])
        })
    
    # Build parameters
    params = {}
    if period is not None:
        params['period'] = period
    if std_dev is not None:
        params['std_dev'] = std_dev
    if fast is not None:
        params['fast'] = fast
    if slow is not None:
        params['slow'] = slow
    if signal is not None:
        params['signal'] = signal
    
    # Calculate indicator
    try:
        indicator_values = calculate_indicator(indicator_name, data_list, **params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Match indicator values with timestamps
    # Note: some indicators have warm-up period, so values array is shorter
    result_data = []
    offset = len(data_list) - len(indicator_values.get('values', indicator_values.get('macd', [])))
    
    if 'values' in indicator_values:
        # Single line indicator (SMA, EMA, RSI, VWAP, ATR)
        for i, value in enumerate(indicator_values['values']):
            result_data.append({
                "time": data_list[offset + i]['time'],
                "value": float(value)
            })
    else:
        # Multi-line indicator (BB, MACD)
        keys = list(indicator_values.keys())
        for i in range(len(indicator_values[keys[0]])):
            point = {"time": data_list[offset + i]['time']}
            for key in keys:
                point[key] = float(indicator_values[key][i])
            result_data.append(point)
    
    return {
        "indicator": indicator_name,
        "timeframe": timeframe,
        "params": params,
        "data": result_data
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting ES Futures Chart Server...")
    print("Open http://localhost:8000 in your browser")
    uvicorn.run(app, host="0.0.0.0", port=8000)
