import asyncio
import schwab
import json
import os
import sys
import time
import sqlite3
import pandas as pd
from datetime import datetime, timezone, timedelta
from schwab.auth import easy_client
from schwab.client import Client
from schwab.streaming import StreamClient
from schwab_token_sync import sync_token_to_db, restore_token_from_db

# Timezone Configuration (Market uses UTC for storage)
def get_now_iso():
    """Returns current time in UTC as ISO string for storage."""
    return datetime.now(timezone.utc).isoformat()

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
    live_dir = os.path.join(DATA_DIR, "live")
    return {
        "json": os.path.join(live_dir, f"live_chart_{safe}.json"),
        "json_15s": os.path.join(live_dir, f"live_chart_{safe}_15s.json"),
        "json_30s": os.path.join(live_dir, f"live_chart_{safe}_30s.json"),
        "parquet": os.path.join(live_dir, f"live_storage_{safe}.parquet")
    }

def get_watchlist_symbols():
    defaults = ["/NQ", "/ES", "/RTY", "/YM","/CL", "/GC","QQQ", "SPY", "GOOGL", "AAPL", "MSFT", "AMZN", "TSLA", "META", "NFLX", "NVDA"]
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
    """
    Ensures candles are unique by 'time' and sorted.
    IMPORTANT: Preserves FIRST occurrence to prevent new data from overwriting existing.
    """
    if not candles: return []
    unique = {}
    for c in candles:
        # Only add if time not already present (preserve first occurrence)
        if c['time'] not in unique:
            unique[c['time']] = c
    return sorted(unique.values(), key=lambda x: x['time'])

def validate_bootstrap_data(symbol, bootstrap_candles):
    """
    Validate bootstrap data against historical parquet.
    ONLY accepts bootstrap candles for timestamps that DON'T exist in historical data.
    Never overwrites existing historical data.
    Logs any conflicts to a report file for investigation.
    """
    # Map streaming symbol to historical file
    symbol_map = {
        "/ES": "ES1",
        "/NQ": "NQ1",
        "/YM": "YM1",
        "/RTY": "RTY1",
        "/CL": "CL1",
        "/GC": "GC1"
    }
    
    ticker = symbol_map.get(symbol)
    if not ticker:
        return bootstrap_candles  # No historical file to validate against
    
    hist_path = os.path.join(DATA_DIR, f"{ticker}_1m.parquet")
    if not os.path.exists(hist_path):
        return bootstrap_candles
    
    try:
        print(f"📊 [{symbol}] Validating bootstrap against historical data...")
        hist = pd.read_parquet(hist_path)
        
        # Filter to last 45 days (matches Schwab API max fetch)
        cutoff = datetime.now().timestamp() - (45 * 24 * 60 * 60)
        hist = hist[hist['time'] >= cutoff]
        
        # Create set of historical timestamps (in milliseconds)
        hist['time_ms'] = (hist['time'] * 1000).astype('int64')
        hist_times = set(hist['time_ms'].values)
        
        # Also create lookup for conflict detection
        hist_lookup = hist.set_index('time_ms')[['open', 'high', 'low', 'close']].to_dict('index')
        
        validated = []
        skipped = 0
        conflicts = []
        
        for candle in bootstrap_candles:
            time_ms = int(candle['time'])
            
            if time_ms in hist_times:
                # Historical data exists - SKIP this bootstrap candle (never overwrite)
                skipped += 1
                
                # Check if there's a conflict for logging
                hist_row = hist_lookup.get(time_ms)
                if hist_row:
                    boot_open = candle['open']
                    hist_open = hist_row['open']
                    if abs(boot_open - hist_open) > 0.01:  # Any meaningful difference
                        conflicts.append({
                            "time_ms": time_ms,
                            "time_str": datetime.fromtimestamp(time_ms / 1000).isoformat(),
                            "historical_open": hist_open,
                            "historical_close": hist_row['close'],
                            "bootstrap_open": boot_open,
                            "bootstrap_close": candle['close'],
                            "diff_pct": round((boot_open - hist_open) / hist_open * 100, 2)
                        })
            else:
                # No historical data - accept bootstrap candle
                validated.append(candle)
        
        print(f"✅ [{symbol}] Validated: {len(validated)} new, {skipped} skipped (already in history)")
        
        # Log conflicts to report file for investigation
        if conflicts:
            safe_symbol = symbol.replace("/", "-")
            report_path = os.path.join(DATA_DIR, "live", f"bootstrap_conflicts_{safe_symbol}.json")
            with open(report_path, 'w') as f:
                json.dump({
                    "symbol": symbol,
                    "generated": datetime.now().isoformat(),
                    "conflict_count": len(conflicts),
                    "conflicts": conflicts
                }, f, indent=2)
            print(f"⚠️ [{symbol}] {len(conflicts)} conflicts logged to {report_path}")
        
        return validated
        
    except Exception as e:
        print(f"⚠️ [{symbol}] Bootstrap validation failed: {e}")
        return bootstrap_candles

def detect_gaps(candles, symbol, threshold_minutes=5):
    """
    Detect gaps in 1-minute data larger than threshold.
    Returns list of (gap_start_ms, gap_end_ms) tuples.
    Excludes expected weekend gaps (Friday close -> Sunday open).
    Now also checks for gap between last candle and current time.
    """
    if not candles:
        return []
        
    gaps = []
    threshold_ms = threshold_minutes * 60 * 1000  # 5 minutes = 300,000 ms
    now_ms = int(time.time() * 1000)
    
    # 1. Check for gaps between existing candles
    if len(candles) >= 2:
        for i in range(1, len(candles)):
            prev_time = candles[i-1]['time']
            curr_time = candles[i]['time']
            diff = curr_time - prev_time
            
            # Skip expected gaps (normal is 1 min = 60,000 ms)
            if diff > threshold_ms:
                # Use UTC for weekday checks
                prev_dt = datetime.fromtimestamp(prev_time / 1000, tz=timezone.utc)
                curr_dt = datetime.fromtimestamp(curr_time / 1000, tz=timezone.utc)
                
                # Skip weekend gaps (Friday close -> Sunday open)
                if prev_dt.weekday() == 4 and curr_dt.weekday() in [6, 0]:
                    continue
                # Skip Saturday -> Sunday/Monday
                if prev_dt.weekday() in [5, 6] and curr_dt.weekday() in [6, 0]:
                    continue
                    
                gaps.append((prev_time, curr_time))
    
    # 2. Check for gap between last candle and NOW
    last_time = candles[-1]['time']
    diff_to_now = now_ms - last_time
    
    if diff_to_now > threshold_ms:
        # Use UTC for weekday checks
        last_dt = datetime.fromtimestamp(last_time / 1000, tz=timezone.utc)
        now_dt = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)
        
        # Weekend check for current gap
        is_weekend = False
        if last_dt.weekday() == 4 and now_dt.weekday() in [5, 6]:
             is_weekend = True
        elif last_dt.weekday() in [5, 6]:
             is_weekend = True
             
        if not is_weekend:
            print(f"🔍 [{symbol}] Gap detected since last data point (UTC): {last_dt} -> {now_dt}")
            gaps.append((last_time, now_ms))
    
    return gaps

def bridge_gaps(client, symbol, gaps):
    """
    Fetch missing data for each gap from Schwab API.
    Returns combined list of candles for all gaps.
    Note: Schwab API only allows ~45 days of historical data.
    """
    all_bridged = []
    max_age_days = 45
    now = datetime.now()
    
    for gap_start_ms, gap_end_ms in gaps:
        start_dt = datetime.fromtimestamp(gap_start_ms / 1000)
        end_dt = datetime.fromtimestamp(gap_end_ms / 1000)
        
        # Skip if gap is too old for Schwab API
        if (now - end_dt).days > max_age_days:
            print(f"⚠️ [{symbol}] Gap too old to bridge via API: {start_dt} -> {end_dt}")
            continue
        
        print(f"🔧 [{symbol}] Bridging gap: {start_dt} -> {end_dt}")
        
        try:
            resp = client.get_price_history(
                symbol,
                period_type=Client.PriceHistory.PeriodType.DAY,
                frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                frequency=Client.PriceHistory.Frequency.EVERY_MINUTE,
                start_datetime=start_dt,
                end_datetime=end_dt,
                need_extended_hours_data=True
            )
            
            if resp.status_code == 200:
                candles = resp.json().get('candles', [])
                for c in candles:
                    all_bridged.append({
                        "time": c.get("datetime", 0),
                        "open": c.get("open", 0),
                        "high": c.get("high", 0),
                        "low": c.get("low", 0),
                        "close": c.get("close", 0),
                        "volume": c.get("volume", 0)
                    })
                print(f"   ✅ Fetched {len(candles)} bars")
            else:
                print(f"   ❌ API returned {resp.status_code}")
        except Exception as e:
            print(f"⚠️ [{symbol}] Bridge failed: {e}")
    
    return all_bridged

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
                data["last_update"] = get_now_iso()
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
            token_path='token.json',
            enforce_enums=False)
    except Exception as e:
        print(f"Auth failed: {e}")
        return None

def fetch_bootstrap_data(client, symbol):
    print(f"🚀 [{symbol}] Bootstrapping...")
    try:
        resp = client.get_price_history(symbol, 
                                        period_type=Client.PriceHistory.PeriodType.DAY,
                                        period=Client.PriceHistory.Period.THREE_MONTHS,
                                        frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                                        frequency=Client.PriceHistory.Frequency.EVERY_MINUTE,
                                        need_extended_hours_data=True)
        
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
    container["last_update"] = get_now_iso()

def update_historical_files(client, symbol):
    """
    Checks and updates Daily (1d) and Weekly (1W) parquet files for the symbol.
    Fetches missing history from Schwab if files are stale.
    """
    symbol_map = {
        "/ES": "ES1", "/NQ": "NQ1", "/YM": "YM1", "/RTY": "RTY1",
        "/CL": "CL1", "/GC": "GC1"
    }
    ticker = symbol_map.get(symbol)
    if not ticker: return # Only update mapped futures/indices for now

    print(f"📅 [{symbol}] Checking historical data for {ticker}...")

    # Define tasks: (Parquet Suffix, Schwab PeriodType, Schwab FrequencyType, Schwab Frequency)
    # Note: Schwab 'weekly' frequency might not be directly available for all assets or might need 'daily' aggregation.
    # Safe bet: Update Daily (1d). Weekly can be derived or updated if API supports it.
    # Schwab Client.PriceHistory.FrequencyType.WEEKLY exists.
    
    tasks = [
        ("1d", "year", "daily", 1),
        ("1W", "year", "weekly", 1)
    ]

    for suffix, p_type, f_type, freq in tasks:
        file_path = os.path.join(DATA_DIR, f"{ticker}_{suffix}.parquet")
        
        last_date = None
        existing_df = pd.DataFrame()

        if os.path.exists(file_path):
            try:
                existing_df = pd.read_parquet(file_path)
                if not existing_df.empty:
                    # Check last timestamp
                    # Assuming 'datetime' index or column
                    if 'datetime' in existing_df.columns:
                        existing_df['datetime'] = pd.to_datetime(existing_df['datetime'])
                        existing_df.set_index('datetime', inplace=True)
                    elif isinstance(existing_df.index, pd.DatetimeIndex):
                        pass
                    elif 'time' in existing_df.columns:
                         existing_df['datetime'] = pd.to_datetime(existing_df['time'], unit='s', utc=True)
                         existing_df.set_index('datetime', inplace=True)

                    # Normalize to UTC Aware
                    if existing_df.index.tz is None:
                        # Assume it's US/Eastern or just local? 
                        # Actually if we want to concat with UTC new data, we must localize and converting.
                        # Safest: Localize to UTC if naive (assuming it was stored as UTC)
                        existing_df.index = existing_df.index.tz_localize(timezone.utc)
                    else:
                        existing_df.index = existing_df.index.tz_convert(timezone.utc)

                    existing_df.sort_index(inplace=True)
                    last_date = existing_df.index[-1]
            except Exception as e:
                print(f"  ⚠️ Error reading {suffix}: {e}")

        if last_date:
            # last_date is likely pandas Timestamp
            # Convert to python datetime first to be safe
            if hasattr(last_date, 'to_pydatetime'):
                last_date = last_date.to_pydatetime()
            
            # Ensure naive
            if last_date.tzinfo:
                last_date = last_date.replace(tzinfo=None)
            
            if (datetime.now() - last_date).days < 1:
                continue
            
            start_dt = last_date + timedelta(days=1)
        else:
            start_dt = datetime.now() - timedelta(days=730)

        # Final check
        # Paranoid reconstruction to ensure pure python naive datetime
        now = datetime.now()
        if start_dt.tzinfo or hasattr(start_dt, 'tz'):
             start_dt = datetime(start_dt.year, start_dt.month, start_dt.day, start_dt.hour, start_dt.minute)
        
        if start_dt >= now: continue

        print(f"  ⬇️ Updating {suffix} from {start_dt.date()}...")

        try:
            resp = client.get_price_history(
                symbol,
                period_type=p_type,
                frequency_type=f_type,
                frequency=freq,
                start_datetime=start_dt,
                end_datetime=now,
                need_extended_hours_data=False 
            )
            
            if resp.status_code == 200:
                data = resp.json()
                candles = data.get('candles', [])
                if not candles:
                    print(f"   No new data for {suffix}.")
                    continue
                
                new_data = []
                for c in candles:
                    new_data.append({
                        "datetime": pd.to_datetime(c.get("datetime", 0), unit='ms', utc=True),
                        "open": c.get("open", 0),
                        "high": c.get("high", 0),
                        "low": c.get("low", 0),
                        "close": c.get("close", 0),
                        "volume": c.get("volume", 0)
                    })
                
                new_df = pd.DataFrame(new_data)
                new_df.set_index('datetime', inplace=True)
                
                # Merge
                if not existing_df.empty:
                    combined = pd.concat([existing_df, new_df])
                    combined = combined[~combined.index.duplicated(keep='last')]
                    combined.sort_index(inplace=True)
                else:
                    combined = new_df
                
                # Save
                # Ensure columns
                # Parquet usually stores index if to_parquet is used on DF with index
                # But our standard seems to be preserving 'time' or 'datetime' column?
                # Let's reset index to keep 'datetime' column for compatibility if needed
                # Actually previous files had specific schemas. 
                # 'NQ1_1d.parquet' usually has: open, high, low, close, volume (index is datetime)
                
                # IMPORTANT: Reset index to column for saving if that's the convention?
                # debug showed: NQ1_1d has DatetimeIndex. So direct save is fine.
                
                combined.to_parquet(file_path)
                print(f"   ✅ Updated {suffix}: {len(combined)} rows (Added {len(new_df)})")
                
            else:
                print(f"   ❌ API Error: {resp.status_code}")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"   ⚠️ Fetch failed: {e}")

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
            # Validate bootstrap data against historical parquet to prevent corrupt data
            boot = validate_bootstrap_data(sym, boot)
            
            cdata = charts[sym]["data"]
            existing_times = {c["time"] for c in cdata["candles"]}
            cdata["candles"] = deduplicate_candles(cdata["candles"] + [c for c in boot if c["time"] not in existing_times])
            if len(cdata["candles"]) > 500000:
                cdata["candles"] = cdata["candles"][-500000:]
            cdata["last_update"] = get_now_iso()
            
            with open(charts[sym]["files"]["json"], "w") as f:
                json.dump(cdata, f, indent=2)

    # 2.5. Gap Detection & Bridging (after all data is loaded)
    print("\n🔍 Checking for data gaps...")
    for sym in symbols:
        cdata = charts[sym]["data"]
        files = charts[sym]["files"]
        
        # Detect gaps in the merged data
        gaps = detect_gaps(cdata["candles"], sym, threshold_minutes=5)
        
        if gaps:
            print(f"⚠️ [{sym}] Found {len(gaps)} data gap(s)")
            
            # Bridge gaps via Schwab API
            bridged = bridge_gaps(client, sym, gaps)
            if bridged:
                # Validate bridged data against historical parquet
                bridged = validate_bootstrap_data(sym, bridged)
                
                cdata["candles"] = deduplicate_candles(cdata["candles"] + bridged)
                cdata["last_update"] = get_now_iso()
                print(f"✅ [{sym}] Merged {len(bridged)} bridged bars")
                
                # Save updated data back to parquet
                try:
                    df = pd.DataFrame(cdata["candles"])
                    df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
                    df.to_parquet(files["parquet"], index=False)
                    print(f"📁 [{sym}] Updated parquet storage")
                except Exception as e:
                    print(f"⚠️ [{sym}] Failed to save parquet: {e}")
                
                # Also update JSON
                with open(files["json"], "w") as f:
                    json.dump(cdata, f, indent=2)
        else:
            print(f"✅ [{sym}] No gaps detected")

    # 2.6. Historical Data Update (Daily/Weekly)
    print("\n📅 updating Historical Files (Daily/Weekly)...")
    for sym in symbols:
        # Run this for mapped futures/indices
        update_historical_files(client, sym)

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
                        cdata["last_update"] = get_now_iso()
                        
                        # Write Fast Quote
                        safe_symbol = get_safe_symbol(key)
                        quote_file = os.path.join(DATA_DIR, "live", f"latest_quote_{safe_symbol}.json")
                        try:
                            # Use try-block for atomic-ish write (rename would be better but this is Windows)
                            with open(quote_file, "w") as f:
                                json.dump({
                                    "symbol": key,
                                    "price": last_price,
                                    "time": cdata["last_update"]
                                }, f)
                        except: pass

                        # NOTE: We do NOT write the full JSON here anymore
                        # The chart_handler writes both snapshot and full with proper throttling
                        # This keeps level_one updates fast (just the tiny quote file)

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
                        # Keep full history (up to ~1 year ~ 360k bars)
                        if len(cdata["candles"]) > 500000:
                            cdata["candles"].pop(0)
                        
                    cdata["last_update"] = get_now_iso()
                    cdata["candles"] = deduplicate_candles(cdata["candles"])
                    
                    if cdata["live_price"] == 0:
                        cdata["live_price"] = candle["close"]
                    
                    try:
                        # 1. Write Snapshot (Fast, Frequent)
                        # Contains metadata + last 50 candles
                        # Update: Throttled to max 4 times/sec (250ms) to prevent excessive IO/Watcher triggers
                        now = time.time()
                        last_snap = cdata.get("_last_snap_ts", 0)
                        
                        if now - last_snap > 0.25:
                            snapshot = {
                                "symbol": cdata["symbol"],
                                "last_update": cdata["last_update"],
                                "live_price": cdata["live_price"],
                                "candles": cdata["candles"][-50:] if cdata["candles"] else []
                            }
                            snap_file = files["json"].replace(".json", "_snapshot.json")
                            with open(snap_file, "w") as f:
                                json.dump(snapshot, f)
                            cdata["_last_snap_ts"] = now

                        # 2. Write Full History (Heavy, Throttled)
                        # Only write every 60 seconds OR if it's the first time
                        last_write = cdata.get("_last_write_ts", 0)
                        
                        if now - last_write > 60:
                            with open(files["json"], "w") as f:
                                json.dump(cdata, f) # Minified (no indent) to save space
                            cdata["_last_write_ts"] = now
                            print(f"pw Checkpoint saved for {key}")

                        # Only print log occasionally to reduce noise
                        # print(f"📈 [{key}] {candle['time']} C:{candle['close']}") 
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
