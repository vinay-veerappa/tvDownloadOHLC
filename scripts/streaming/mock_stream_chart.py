#!/usr/bin/env python3
"""
mock_stream_chart.py
===================
Offline mock streaming chart server that runs on port 8001.
Acts as a drop-in replacement for stream_chart.py when the market is closed or offline.
Loads historical 1m parquets, aligns dates to "now", and streams mock updates.
"""

import os
import sys
import json
import time
import asyncio
import random
from datetime import datetime, timedelta, timezone
import pandas as pd
from aiohttp import web
import aiohttp_cors

# Setup repo paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(REPO_ROOT, "data")

# Ticker mapping to 1m parquets
TICKER_MAP = {
    "/NQ": "NQ1_1m.parquet",
    "NQ1!": "NQ1_1m.parquet",
    "NQ": "NQ1_1m.parquet",
    "/ES": "ES1_1m.parquet",
    "ES1!": "ES1_1m.parquet",
    "ES": "ES1_1m.parquet",
    "/CL": "CL1_1m.parquet",
    "/GC": "GC1_1m.parquet",
    "/YM": "YM1_1m.parquet",
    "/RTY": "RTY1_1m.parquet",
}

# Cache for loaded and shifted data: symbol -> list of dict candles (time in ms)
db_candles = {}
db_live_candle = {}  # The current active "unclosed" candle
active_connections = {}  # symbol -> client_id -> (ws, timeframe)

def get_parquet_path(symbol):
    fname = TICKER_MAP.get(symbol)
    if not fname:
        # Try finding anything matching
        clean = symbol.replace("/", "").replace("1!", "")
        for k, v in TICKER_MAP.items():
            if clean in k or k in clean:
                fname = v
                break
    if not fname:
        fname = "NQ1_1m.parquet"  # Default fallback
    
    return os.path.join(DATA_DIR, fname)

def load_and_shift_candles(symbol):
    """Loads historical 1m candles and shifts timestamps so they end at current time."""
    p_path = get_parquet_path(symbol)
    print(f"📂 [{symbol}] Loading base data from {p_path}...")
    
    if not os.path.exists(p_path):
        print(f"⚠️ Parquet file not found: {p_path}. Generating dummy data.")
        return generate_dummy_candles()

    try:
        # To avoid loading 120MB+ into memory, read the tail of the parquet
        # We can read using pandas with a filter, or read the whole file and tail it since it's fast enough in Python.
        # But tailing a parquet is fast.
        df = pd.read_parquet(p_path)
        if df.empty:
            return generate_dummy_candles()
        
        # Take the last 10,000 candles
        df = df.tail(10000).copy()
        
        # Sort by timestamp/time
        if 'datetime' in df.columns:
            df['time_sec'] = pd.to_datetime(df['datetime'], utc=True).astype('int64') // 10**9
        elif 'time' in df.columns:
            # Check if time is in ms or seconds
            max_t = df['time'].max()
            if max_t > 10**11:
                df['time_sec'] = df['time'] // 1000
            else:
                df['time_sec'] = df['time']
        else:
            # Use index
            df['time_sec'] = pd.to_datetime(df.index, utc=True).astype('int64') // 10**9

        df = df.sort_values('time_sec')
        candles = df.to_dict(orient="records")
        
        # Shift timestamps so the last candle is at the current minute
        now_sec = int(time.time())
        current_minute_sec = (now_sec // 60) * 60
        
        last_candle_sec = candles[-1]['time_sec']
        delta_sec = current_minute_sec - last_candle_sec
        
        shifted = []
        for c in candles:
            shifted.append({
                "time": int((c['time_sec'] + delta_sec) * 1000), # in milliseconds
                "open": float(c['open']),
                "high": float(c['high']),
                "low": float(c['low']),
                "close": float(c['close']),
                "volume": int(c.get('volume', 0))
            })
            
        print(f"✅ [{symbol}] Loaded & shifted {len(shifted)} candles. Last candle: {datetime.fromtimestamp((shifted[-1]['time'])/1000, tz=timezone.utc).isoformat()}")
        return shifted
    except Exception as e:
        print(f"❌ Error loading parquet for {symbol}: {e}")
        return generate_dummy_candles()

def generate_dummy_candles():
    """Fallback generator for dummy candles."""
    now_sec = int(time.time())
    current_minute_sec = (now_sec // 60) * 60
    
    candles = []
    price = 18500.0
    for i in range(1000):
        t_sec = current_minute_sec - (1000 - i) * 60
        o = price + random.uniform(-10, 10)
        c = o + random.uniform(-15, 15)
        h = max(o, c) + random.uniform(0, 5)
        l = min(o, c) - random.uniform(0, 5)
        candles.append({
            "time": int(t_sec * 1000),
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": random.randint(10, 100)
        })
        price = c
    return candles

def get_or_create_candles(symbol):
    # Normalize client symbol
    norm_sym = symbol.replace("1!", "").replace("-", "/").upper()
    if not norm_sym.startswith("/") and norm_sym in ["NQ", "ES", "YM", "RTY", "CL", "GC"]:
        norm_sym = "/" + norm_sym
        
    if norm_sym not in db_candles:
        db_candles[norm_sym] = load_and_shift_candles(norm_sym)
        # Initialize the live unclosed candle as the last loaded candle
        last_c = db_candles[norm_sym][-1]
        db_live_candle[norm_sym] = dict(last_c)
        
    return norm_sym, db_candles[norm_sym]

# --- REST HANDLERS ---

async def handle_history(request):
    symbol_raw = request.query.get("symbol")
    limit_str = request.query.get("limit", "180000")
    try:
        limit = int(limit_str)
    except:
        limit = 180000
        
    if not symbol_raw:
        return web.json_response({"error": "Missing symbol"}, status=400)
        
    norm_sym, candles = get_or_create_candles(symbol_raw)
    
    # Return requested count
    result_candles = candles[-limit:]
    
    # Include current active live candle at the very end
    if norm_sym in db_live_candle:
        # Check if the live candle's timestamp matches the last candle in history
        if result_candles and result_candles[-1]['time'] == db_live_candle[norm_sym]['time']:
            result_candles[-1] = db_live_candle[norm_sym]
        else:
            result_candles.append(db_live_candle[norm_sym])
            
    print(f"📊 [GET /history] {norm_sym} limit={limit} returning {len(result_candles)} candles")
    return web.json_response({
        "symbol": norm_sym,
        "candles": result_candles,
        "hasMore": len(candles) >= limit
    })

# --- WEBSOCKET HANDLER ---

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    symbol_raw = request.query.get("symbol")
    timeframe = request.query.get("timeframe", "1m")
    
    if not symbol_raw:
        await ws.close(code=4000, message=b"Missing symbol")
        return ws
        
    norm_sym, candles = get_or_create_candles(symbol_raw)
    
    client_id = id(ws)
    active_connections.setdefault(norm_sym, {})[client_id] = (ws, timeframe)
    print(f"🔌 [WS] Client connected for {norm_sym} ({timeframe})")
    
    # Send snapshot (last 200 candles)
    snapshot_candles = list(candles[-200:])
    if snapshot_candles and snapshot_candles[-1]['time'] == db_live_candle[norm_sym]['time']:
        snapshot_candles[-1] = db_live_candle[norm_sym]
        
    try:
        await ws.send_json({
            "type": "snapshot",
            "symbol": norm_sym,
            "timeframe": timeframe,
            "live_price": db_live_candle[norm_sym]["close"],
            "candles": snapshot_candles
        })
    except Exception as e:
        print(f"❌ Error sending WS snapshot: {e}")
        
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                if msg.data == "ping":
                    await ws.send_str("pong")
    finally:
        if norm_sym in active_connections and client_id in active_connections[norm_sym]:
            del active_connections[norm_sym][client_id]
        print(f"🔌 [WS] Client disconnected for {norm_sym}")
        
    return ws

# --- STREAM SIMULATION LOOP ---

async def broadcast_tick(symbol, candle):
    if symbol not in active_connections:
        return
    message = json.dumps({
        "type": "candle",
        "symbol": symbol,
        "timeframe": "1m",
        "candle": candle
    })
    
    tasks = []
    for client_id, (ws, client_tf) in list(active_connections[symbol].items()):
        if client_tf in ["1", "1m"]:
            try:
                tasks.append(ws.send_str(message))
            except:
                pass
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def simulation_loop():
    """Main loop simulating live ticks and new candle formations."""
    print("🔄 Starting simulated tick generator...")
    while True:
        await asyncio.sleep(1.0) # Tick every 1 second
        
        now_ms = int(time.time() * 1000)
        now_minute_ms = (now_ms // 60000) * 60000
        
        for symbol in list(db_candles.keys()):
            live_c = db_live_candle[symbol]
            candles = db_candles[symbol]
            
            # Check if we crossed into a new minute
            if now_minute_ms > live_c["time"]:
                # 1. Finalize current live candle by appending to history
                candles.append(dict(live_c))
                if len(candles) > 15000:
                    db_candles[symbol] = candles[-10000:]
                
                # 2. Start a new live candle
                prev_close = live_c["close"]
                live_c = {
                    "time": now_minute_ms,
                    "open": prev_close,
                    "high": prev_close,
                    "low": prev_close,
                    "close": prev_close,
                    "volume": 0
                }
                db_live_candle[symbol] = live_c
                print(f"⏰ [{symbol}] New 1m candle created: {datetime.fromtimestamp(now_minute_ms/1000, tz=timezone.utc).strftime('%H:%M:%S')}")
            
            # Update the active candle (tick update)
            tick_size = random.uniform(-3.5, 3.5)
            # Add a slight bias to make ES/NQ drift upwards/downwards nicely
            tick_bias = random.choice([0.1, -0.08])
            price_change = tick_size + tick_bias
            
            live_c["close"] = round(live_c["close"] + price_change, 2)
            live_c["high"] = round(max(live_c["high"], live_c["close"]), 2)
            live_c["low"] = round(min(live_c["low"], live_c["close"]), 2)
            live_c["volume"] += random.randint(1, 10)
            
            # Broadcast the updated candle
            await broadcast_tick(symbol, live_c)

async def main():
    app = web.Application()
    
    # Configure CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    
    resource = cors.add(app.router.add_resource("/history"))
    cors.add(resource.add_route("GET", handle_history))
    app.router.add_get('/stream', websocket_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8001)
    await site.start()
    print("🌐 Mock API Server running on http://127.0.0.1:8001")
    
    # Bootstrap NQ1 as default watchlist item to populate cache immediately
    get_or_create_candles("/NQ")
    get_or_create_candles("/ES")
    
    # Run the tick generator as a background task
    asyncio.create_task(simulation_loop())
    
    # Keep the server running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping Mock Server...")
