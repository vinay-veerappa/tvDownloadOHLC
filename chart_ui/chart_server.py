from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from indicators import calculate_indicator
import mimetypes

# Ensure JS files are served with correct MIME type
mimetypes.add_type('application/javascript', '.js')

app = FastAPI(title="Futures Data API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory (in parent folder)
DATA_DIR = Path(__file__).parent.parent / "data"

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

@app.get("/demo-plugins")
async def get_demo_plugins():
    """Serve Drawing Tools demo"""
    import os
    demo_path = os.path.join(os.getcwd(), "demo_plugins.html")
    return FileResponse(demo_path)

@app.get("/demo-strategy")
async def get_demo_strategy():
    """Serve Strategy demo"""
    import os
    demo_path = os.path.join(os.getcwd(), "demo_strategy.html")
    return FileResponse(demo_path)

@app.get("/demo-rectangle")
async def get_demo_rectangle():
    """Serve Rectangle demo"""
    import os
    demo_path = os.path.join(os.getcwd(), "demo_rectangle.html")
    return FileResponse(demo_path)

@app.get("/trendline_plugin.js")
async def get_trendline_plugin():
    """Serve TrendLine Plugin"""
    import os
    plugin_path = os.path.join(os.getcwd(), "trendline_plugin.js")
    return FileResponse(plugin_path)

@app.get("/rectangle_plugin.js")
async def get_rectangle_plugin():
    """Serve Rectangle Plugin"""
    import os
    plugin_path = os.path.join(os.getcwd(), "rectangle_plugin.js")
    return FileResponse(plugin_path)

@app.get("/fibonacci_plugin.js")
async def get_fibonacci_plugin():
    """Serve Fibonacci Plugin"""
    import os
    plugin_path = os.path.join(os.getcwd(), "fibonacci_plugin.js")
    return FileResponse(plugin_path)

@app.get("/vertical_line_plugin.js")
async def get_vertical_line_plugin():
    """Serve Vertical Line Plugin"""
    import os
    plugin_path = os.path.join(os.getcwd(), "vertical_line_plugin.js")
    return FileResponse(plugin_path)

@app.get("/anchored_text_plugin.js")
async def get_anchored_text_plugin():
    """Serve Anchored Text Plugin"""
    import os
    plugin_path = os.path.join(os.getcwd(), "anchored_text_plugin.js")
    return FileResponse(plugin_path)

@app.get("/test_plugins.html")
async def get_test_plugins():
    """Serve Plugin Test Page"""
    import os
    test_path = os.path.join(os.getcwd(), "test_plugins.html")
    return FileResponse(test_path)

@app.get("/{filename}.js")
async def get_js_file(filename: str):
    """Serve any JavaScript file from the chart_ui directory"""
    import os
    js_path = os.path.join(os.getcwd(), f"{filename}.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail=f"JavaScript file {filename}.js not found")

@app.get("/api/tickers")
async def get_tickers():
    """Get list of available tickers"""
    tickers = set()
    # Scan for any parquet files
    for file in DATA_DIR.glob("*_*.parquet"):
        # Filename format: TICKER_TIMEFRAME.parquet
        # e.g. ES1_1m.parquet -> ES1
        if "_" in file.stem:
            parts = file.stem.split("_")
            if len(parts) >= 2:
                tickers.add(parts[0])
    
    return {"tickers": sorted(list(tickers))}

@app.get("/api/timeframes")
async def get_timeframes(ticker: str = "ES1"):
    """Get available timeframes"""
    timeframes = []
    # Clean ticker for file matching
    ticker_clean = ticker.upper().replace("!", "").replace(" ", "_")
    
    for file in DATA_DIR.glob(f"{ticker_clean}_*.parquet"):
        tf = file.stem.replace(f"{ticker_clean}_", "")
        timeframes.append(tf)
    return {"timeframes": sorted(timeframes)}

@app.get("/api/range/{timeframe}")
async def get_date_range(timeframe: str, ticker: str = "ES1"):
    """Get the available date range for a timeframe"""
    ticker_clean = ticker.upper().replace("!", "").replace(" ", "_")
    parquet_file = DATA_DIR / f"{ticker_clean}_{timeframe}.parquet"
    
    if not parquet_file.exists():
        raise HTTPException(status_code=404, detail=f"Timeframe {timeframe} not found for {ticker}")
    
    df = pd.read_parquet(parquet_file)
    
    return {
        "ticker": ticker.upper(),
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
    limit: int = 10000,
    ticker: str = "ES1"
):
    """
    Get OHLC data for a specific timeframe and date range
    
    Parameters:
    - timeframe: 1m, 5m, 15m, 1h, 4h, 1D
    - start: ISO datetime string (optional)
    - end: ISO datetime string (optional)
    - limit: Max bars to return
    - ticker: Ticker symbol (default: ES1)
    """
    ticker_clean = ticker.upper().replace("!", "").replace(" ", "_")
    parquet_file = DATA_DIR / f"{ticker_clean}_{timeframe}.parquet"
    
    if not parquet_file.exists():
        raise HTTPException(status_code=404, detail=f"Data not found for {ticker} {timeframe}")
    
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
        item = {
            "time": int(idx.timestamp()),  # Unix timestamp
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close'])
        }
        if 'volume' in row:
            item['value'] = float(row['volume']) # For HistogramSeries
            item['volume'] = float(row['volume']) # For reference
            # Color based on price change
            item['color'] = '#26a69a' if row['close'] >= row['open'] else '#ef5350'
            
        data.append(item)
    
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
    signal: Optional[int] = Query(None),
    ticker: str = "ES1"
):
    """
    Calculate indicator values for a timeframe
    """
    ticker_clean = ticker.upper().replace("!", "").replace(" ", "_")
    parquet_file = DATA_DIR / f"{ticker_clean}_{timeframe}.parquet"
    
    if not parquet_file.exists():
        raise HTTPException(status_code=404, detail=f"Timeframe {timeframe} not found for {ticker}")
    
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
    result_data = []
    # Determine length of result to calculate offset
    if 'values' in indicator_values:
        result_len = len(indicator_values['values'])
    elif 'macd' in indicator_values:
        result_len = len(indicator_values['macd'])
    elif 'upper' in indicator_values: # Bollinger Bands
        result_len = len(indicator_values['upper'])
    else:
        result_len = 0
        
    offset = len(data_list) - result_len
    
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
    print("Starting Futures Chart Server...")
    print("Open http://localhost:8000 in your browser")
    uvicorn.run(app, host="0.0.0.0", port=8000)
