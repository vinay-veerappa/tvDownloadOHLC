import asyncio
import schwab
import json
import os
import sys
import time
import sqlite3
import pandas as pd
from datetime import datetime
from schwab.auth import easy_client
from schwab.client import Client
from schwab.streaming import StreamClient
from schwab_token_sync import sync_token_to_db, restore_token_from_db

# Configuration
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web", "prisma", "dev.db")

# ... existing imports ...

# Global State
charts = {} # Key: Symbol -> { data: {}, data_15s: {}, data_30s: {}, file_json: str, file_15s: str, file_30s: str, ... }
active_subscriptions = {"futures": [], "equities": []}

def get_safe_symbol(symbol):
    return symbol.replace("/", "-")

def get_live_files(symbol):
    safe = get_safe_symbol(symbol)
    return {
        "json": os.path.join(DATA_DIR, f"live_chart_{safe}.json"),
        "json_15s": os.path.join(DATA_DIR, f"live_chart_{safe}_15s.json"),
        "json_30s": os.path.join(DATA_DIR, f"live_chart_{safe}_30s.json"),
        "parquet": os.path.join(DATA_DIR, f"live_storage_{safe}.parquet")
    }

def get_watchlist_symbols():
    defaults = ["/NQ", "/ES", "QQQ", "SPY", "NVDA"]
    try:
        if not os.path.exists(DB_PATH):
            return defaults
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT symbol FROM Watchlist ORDER BY createdAt DESC")
        rows = cursor.fetchall()
        conn.close()
        symbols = [r[0] for r in rows]
        return symbols if symbols else defaults
    except Exception as e:
        print(f"⚠️ Failed to read watchlist: {e}")
        return defaults

def deduplicate_candles(candles):
    """Ensures candles are unique by 'time' and sorted."""
    if not candles: return []
    unique = {}
    for c in candles:
        unique[c['time']] = c
    return sorted(unique.values(), key=lambda x: x['time'])

def init_chart_data(symbol):
    files = get_live_files(symbol)
    
    def create_container():
        return {
            "symbol": symbol,
            "last_update": "",
            "live_price": 0.0,
            "candles": []
        }

    data = create_container()
    data_15s = create_container()
    data_30s = create_container()
    
    # Restore main 1m data from Parquet
    if os.path.exists(files["parquet"]):
        try:
            df = pd.read_parquet(files["parquet"])
            if not df.empty:
                if 'timestamp' in df.columns:
                    df = df.drop(columns=['timestamp'])
                data["candles"] = deduplicate_candles(df.to_dict(orient="records"))
                data["last_update"] = datetime.now().isoformat()
                print(f"✅ [{symbol}] Restored {len(data['candles'])} bars (1m).")
        except Exception as e:
            print(f"⚠️ [{symbol}] Restore failed: {e}")
            
    # Sub-minute persistence not strictly required across restarts for now 
    # (unless we add parquet for them too), but we can load from JSON if exists
    for (key, container) in [("json_15s", data_15s), ("json_30s", data_30s)]:
        if os.path.exists(files[key]):
            try:
                with open(files[key], "r") as f:
                    loaded = json.load(f)
                    container["candles"] = loaded.get("candles", [])
                    container["live_price"] = loaded.get("live_price", 0.0)
            except: pass

    return { 
        "data": data, 
        "data_15s": data_15s, 
        "data_30s": data_30s,
        "files": files 
    }

def get_client():
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Missing credentials")
        return None

    with open("secrets.json", "r") as f:
        secrets = json.load(f)
        
    try:
        return easy_client(
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            callback_url='https://127.0.0.1:8182',
            token_path='token.json')
    except Exception as e:
        print(f"Auth failed: {e}")
        return None

def fetch_bootstrap_data(client, symbol):
    print(f"🚀 [{symbol}] Bootstrapping...")
    try:
        resp = client.get_price_history(symbol, 
                                        period_type=Client.PriceHistory.PeriodType.DAY,
                                        period=Client.PriceHistory.Period.TWO_DAYS,
                                        frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                                        frequency=Client.PriceHistory.Frequency.EVERY_MINUTE)
        
        if resp.status_code != 200:
            print(f"❌ [{symbol}] Bootstrap failed: {resp.status_code}")
            return []

        data = resp.json()
        candles = data.get('candles', [])
        
        formatted = []
        for c in candles:
            formatted.append({
                "time": c.get("datetime", 0),
                "open": c.get("open", 0),
                "high": c.get("high", 0),
                "low": c.get("low", 0),
                "close": c.get("close", 0),
                "volume": c.get("volume", 0)
            })
        
        return formatted
        
    except Exception as e:
        print(f"❌ [{symbol}] Bootstrap exception: {e}")
        return []

def update_sub_candle(container, price, time_curr, interval_sec):
    # time_curr is current unix timestamp (seconds)
    # Calculate bucket start
    bucket = (int(time_curr) // interval_sec) * interval_sec
    
    candles = container["candles"]
    
    if not candles or candles[-1]["time"] != bucket:
        # Close previous? We rely on dedup/sort. Just append new.
        candles.append({
            "time": bucket,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 0 
        })
        # Keep buffer small for sub-minute (~2 hours)
        # 2 hours * 4 bars/min = 480 bars
        if len(candles) > 1000: 
            candles.pop(0)
    else:
        # Update current
        current = candles[-1]
        current["high"] = max(current["high"], price)
        current["low"] = min(current["low"], price)
        current["close"] = price
        # Volume could be incremented if we had trade size, but level one usually just gives price
    
    container["live_price"] = price
    container["last_update"] = datetime.now().isoformat()

async def main():
    # ... Setup ...
    os.makedirs(DATA_DIR, exist_ok=True)
    restore_token_from_db()

    client = get_client()
    if not client: return

    try:
        print("Verifying session...")
        client.get_account_numbers()
        sync_token_to_db()
        print("Session verified.")
    except Exception as e:
        print(f"[CRITICAL] Session failed: {e}")
        return

    # 2. Initialize Symbols
    symbols = get_watchlist_symbols()
    print(f"📋 Watching {len(symbols)} tickers: {symbols}")

    for sym in symbols:
        charts[sym] = init_chart_data(sym)
        # Bootstrap valid only for 1m (Schwab restrictions)
        boot = fetch_bootstrap_data(client, sym)
        if boot:
            cdata = charts[sym]["data"]
            existing_times = {c["time"] for c in cdata["candles"]}
            cdata["candles"] = deduplicate_candles(cdata["candles"] + [c for c in boot if c["time"] not in existing_times])
            if len(cdata["candles"]) > 5000:
                cdata["candles"] = cdata["candles"][-5000:]
            cdata["last_update"] = datetime.now().isoformat()
            
            with open(charts[sym]["files"]["json"], "w") as f:
                json.dump(cdata, f, indent=2)

    # 3. Stream Setup
    stream_client = StreamClient(client, account_id='BB4E515511E76B8B035DC72194CA615919766D183922871CF062DB9ACA6E0EBD') 

    async def level_one_handler(msg):
        if 'content' in msg:
            for c in msg['content']:
                key = c.get('key')
                if key in charts:
                    last_price = c.get("3") or c.get("LAST_PRICE")
                    if last_price:
                        chart_ctx = charts[key]
                        cdata = chart_ctx["data"]
                        cdata["live_price"] = last_price
                        cdata["last_update"] = datetime.now().isoformat()
                        
                        # Write Fast Quote
                        safe_symbol = get_safe_symbol(key)
                        quote_file = os.path.join(DATA_DIR, f"latest_quote_{safe_symbol}.json")
                        try:
                            # Use try-block for atomic-ish write (rename would be better but this is Windows)
                            with open(quote_file, "w") as f:
                                json.dump({
                                    "symbol": key,
                                    "price": last_price,
                                    "time": cdata["last_update"]
                                }, f)
                        except: pass

                        # Update Main 1m File (Preserve state)
                        with open(chart_ctx["files"]["json"], "w") as f:
                            json.dump(cdata, f, indent=2)

                        # --- Sub-Minute Aggregation ---
                        curr_time = time.time()
                        
                        # Update 15s
                        update_sub_candle(chart_ctx["data_15s"], last_price, curr_time, 15)
                        with open(chart_ctx["files"]["json_15s"], "w") as f:
                            json.dump(chart_ctx["data_15s"], f)
                            
                        # Update 30s
                        update_sub_candle(chart_ctx["data_30s"], last_price, curr_time, 30)
                        with open(chart_ctx["files"]["json_30s"], "w") as f:
                            json.dump(chart_ctx["data_30s"], f)

    async def chart_handler(msg):
        # Keeps 1m bars in sync and archived
        if 'content' in msg:
            for c in msg['content']:
                key = c.get('key')
                if key in charts:
                    cdata = charts[key]["data"]
                    files = charts[key]["files"]
                    
                    candle = {
                        "time": c.get("CHART_TIME_MILLIS", 0),
                        "open": c.get("OPEN_PRICE", 0),
                        "high": c.get("HIGH_PRICE", 0),
                        "low": c.get("LOW_PRICE", 0),
                        "close": c.get("CLOSE_PRICE", 0),
                        "volume": c.get("VOLUME", 0)
                    }
                    
                    # Archive Logic
                    if cdata["candles"] and cdata["candles"][-1]["time"] != candle["time"]:
                        completed_candle = cdata["candles"][-1]
                        try:
                            df = pd.DataFrame([completed_candle])
                            df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
                            
                            if not os.path.exists(files["parquet"]):
                                df.to_parquet(files["parquet"], index=False)
                            else:
                                existing_df = pd.read_parquet(files["parquet"])
                                pd.concat([existing_df, df]).drop_duplicates(subset=['time']).to_parquet(files["parquet"], index=False)
                            print(f"📁 [{key}] Archived {completed_candle['time']}")
                        except Exception as e:
                            print(f"Error saving parquet for {key}: {e}")

                    # Update Buffer
                    if cdata["candles"] and cdata["candles"][-1]["time"] == candle["time"]:
                        cdata["candles"][-1] = candle
                    else:
                        cdata["candles"].append(candle)
                        if len(cdata["candles"]) > 5000:
                            cdata["candles"].pop(0)
                        
                    cdata["last_update"] = datetime.now().isoformat()
                    cdata["candles"] = deduplicate_candles(cdata["candles"])
                    
                    if cdata["live_price"] == 0:
                        cdata["live_price"] = candle["close"]
                    
                    try:
                        with open(files["json"], "w") as f:
                            json.dump(cdata, f, indent=2)
                        print(f"📈 [{key}] {candle['time']} C:{candle['close']}")
                    except Exception as e:
                        print(f"Write error {key}: {e}")

    # Login & Subs
    # ... (Rest is similar, just ensuring new handlers are attached)
    await stream_client.login()
    
    futures = [s for s in symbols if s.startswith("/") or s.endswith("!")]
    equities = [s for s in symbols if s not in futures]
    
    if futures:
        stream_client.add_chart_futures_handler(chart_handler)
        stream_client.add_level_one_futures_handler(level_one_handler)
        await stream_client.chart_futures_subs(futures)
        await stream_client.level_one_futures_subs(futures)
        active_subscriptions["futures"] = futures
        
    if equities:
        stream_client.add_chart_equity_handler(chart_handler)
        stream_client.add_level_one_equity_handler(level_one_handler)
        await stream_client.chart_equity_subs(equities)
        await stream_client.level_one_equity_subs(equities)
        active_subscriptions["equities"] = equities

    print(f"Streaming initialized for {len(symbols)} symbols.")
    
    last_sync = time.time()
    while True:
        try:
            await stream_client.handle_message()
            
            if time.time() - last_sync > 1800:
                print("⏳ Token Sync...")
                sync_token_to_db()
                last_sync = time.time()
                
        except Exception as e:
            print(f"⚠️ Error: {e}. Retry in 5s...")
            await asyncio.sleep(5)
            # ... Reconnect logic ...


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping...")
