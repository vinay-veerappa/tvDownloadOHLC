import asyncio
import schwab
import json
import os
import sys
import time
import sqlite3
import pandas as pd
from datetime import datetime, timezone, timedelta, time as dt_time
from zoneinfo import ZoneInfo
import httpx
import websockets
from aiohttp import web
try:
    import yfinance as yf
except ImportError:
    yf = None

# Timezone Configuration (Market uses UTC for storage)
ET_TZ = ZoneInfo("America/New_York")
FUTURES_HTF_SOURCE = os.getenv("FUTURES_HTF_SOURCE", "yfinance").strip().lower()
FUTURES_YFINANCE_MAP = {
    "/ES": "ES=F",
    "/NQ": "NQ=F",
    "/YM": "YM=F",
    "/RTY": "RTY=F",
    "/CL": "CL=F",
    "/GC": "GC=F",
}

def get_now_iso():
    """Returns current time in UTC as ISO string for storage."""
    return datetime.now(timezone.utc).isoformat()

def atomic_write_json(data, filepath):
    """Writes JSON data to a file atomically using a temporary file and os.replace."""
    dir_name = os.path.dirname(filepath)
    base_name = os.path.basename(filepath)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    tmp_path = os.path.join(dir_name, f".{base_name}.tmp")
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, filepath)
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass
        raise e

def resolve_futures_htf_source():
    if FUTURES_HTF_SOURCE in {"yfinance", "schwab"}:
        return FUTURES_HTF_SOURCE
    return "yfinance"

# Configuration
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web", "prisma", "dev.db")

from scripts.streaming.options.config import HUB_URL, HUB_WS_ENDPOINT as HUB_WS

async def hub_request(method, params):
    """Send a REST request through the Hub's proxy."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=30.0)
            if resp.status_code == 200:
                result = resp.json()
                # Ensure result has status/data structure if not present
                if isinstance(result, dict) and "status" not in result:
                    return {"status": "success", "data": result}
                return result
            else:
                return {"status": "error", "message": f"Hub Error [{resp.status_code}]: {resp.text}"}
        except Exception as e:
            return {"status": "error", "message": f"Hub Connection Error: {str(e)}"}

# Global State
charts = {} # Key: Symbol -> { data: {}, data_15s: {}, data_30s: {}, file_json: str, file_15s: str, file_30s: str, ... }
active_subscriptions = {"futures": [], "equities": []}
# Global State for WebSocket active connections: symbol -> client_id -> (ws, timeframe)
active_connections = {}

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
    defaults = ["/NQ", "/ES", "/RTY", "/YM", "/CL", "/GC", "QQQ", "SPY", "SPX", "GOOGL", "AAPL", "MSFT", "AMZN", "TSLA", "META", "NFLX", "NVDA", "VVIX", "VIX"]
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
    Optimized for large lists: avoids full sort if already sorted.
    """
    if not candles: return []
    if len(candles) < 2: return candles
    
    unique = {}
    is_sorted = True
    last_time = -1
    
    for c in candles:
        t = c['time']
        if t not in unique:
            unique[t] = c
            if t < last_time:
                is_sorted = False
            last_time = t
            
    if is_sorted and len(unique) == len(candles):
        return candles # Already unique and sorted
        
    vals = list(unique.values())
    if is_sorted:
        return vals # Unique and already in correct order
        
    return sorted(vals, key=lambda x: x['time'])

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

async def bridge_gaps(symbol, gaps):
    """
    Fetch missing data for each gap from Schwab Hub.
    Returns combined list of candles for all gaps.
    """
    all_bridged = []
    max_age_days = 45
    now = datetime.now()
    
    for gap_start_ms, gap_end_ms in gaps:
        start_dt = datetime.fromtimestamp(gap_start_ms / 1000)
        end_dt = datetime.fromtimestamp(gap_end_ms / 1000)
        
        if (now - end_dt).days > max_age_days:
            print(f"⚠️ [{symbol}] Gap too old to bridge via API: {start_dt} -> {end_dt}")
            continue
        
        print(f"🔧 [{symbol}] Bridging gap: {start_dt} -> {end_dt}")
        
        try:
            # When providing start_datetime and end_datetime, Schwab API prefers NO period/periodType
            resp = await hub_request("get_price_history", {
                "symbol": symbol,
                "frequency_type": "minute",
                "frequency": 1,
                "start_datetime": int(gap_start_ms),
                "end_datetime": int(gap_end_ms),
                "need_extended_hours_data": True
            })
            
            if resp.get("status") == "success":
                data = resp.get("data", {})
                candles = data.get('candles', [])
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
                print(f"  ❌ Hub Request Failed for {symbol} gap: {resp.get('message')}")
        except Exception as e:
            print(f"  ❌ Bridge error: {e}")
            
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
                # Only keep last 15,000 candles in memory to save RAM
                df = df.tail(15000)
                data["candles"] = deduplicate_candles(df.to_dict(orient="records"))
                data["last_update"] = get_now_iso()
                print(f"✅ [{symbol}] Restored {len(data['candles'])} bars (1m) to memory.")
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

# HUB_URL and HUB_WS imported at top

# Consolidated hub_request defined at top

async def fetch_bootstrap_data(symbol):
    print(f"🚀 [{symbol}] Bootstrapping via Hub...")
    try:
        params = {
            "symbol": symbol,
            "period_type": "day",
            "period": 3, # period enum value or string matches Schwab
            "frequency_type": "minute",
            "frequency": 1,
            "need_extended_hours_data": True
        }
        result = await hub_request("get_price_history", params)
        
        if result.get("status") != "success":
            print(f"❌ [{symbol}] Hub bootstrap failed: {result.get('message')}")
            return []

        data = result.get("data", {})
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
        print(f"❌ [{symbol}] Hub bootstrap exception: {e}")
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

def get_symbol_schedule(symbol):
    futures_schedule = {
        "/ES": dt_time(16, 15),
        "/NQ": dt_time(16, 15),
        "/YM": dt_time(16, 15),
        "/RTY": dt_time(16, 15),
        "/CL": dt_time(14, 30),
        "/GC": dt_time(13, 30),
    }
    if symbol.startswith("/"):
        return {
            "session_open": dt_time(18, 0),
            "settlement": futures_schedule.get(symbol, dt_time(16, 15)),
            "is_futures": True,
        }
    return {
        "session_open": dt_time(0, 0),
        "settlement": dt_time(16, 0),
        "is_futures": False,
    }

def previous_business_day(day_value):
    current = day_value - timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current

def get_trade_date_for_timestamp(ts_utc, symbol):
    schedule = get_symbol_schedule(symbol)
    ts_et = ts_utc.astimezone(ET_TZ)
    if schedule["is_futures"] and ts_et.timetz().replace(tzinfo=None) >= schedule["session_open"]:
        return ts_et.date() + timedelta(days=1)
    return ts_et.date()

def get_current_trade_date(now_et, symbol):
    schedule = get_symbol_schedule(symbol)
    if not schedule["is_futures"]:
        return now_et.date()

    current_time = now_et.timetz().replace(tzinfo=None)
    if now_et.weekday() == 6 and current_time >= schedule["session_open"]:
        return now_et.date() + timedelta(days=1)
    if now_et.weekday() < 4 and current_time >= schedule["session_open"]:
        return now_et.date() + timedelta(days=1)
    return now_et.date()

def get_settlement_datetime(trade_date, symbol):
    settlement_time = get_symbol_schedule(symbol)["settlement"]
    return datetime.combine(trade_date, settlement_time, ET_TZ)

def get_latest_closed_trade_date(now_et, symbol, grace_minutes=10):
    current_trade_date = get_current_trade_date(now_et, symbol)
    settlement_dt = get_settlement_datetime(current_trade_date, symbol) + timedelta(minutes=grace_minutes)
    if now_et >= settlement_dt:
        return current_trade_date
    return previous_business_day(current_trade_date)

def normalize_htf_dataframe(df):
    normalized = df.copy()
    if normalized.empty:
        return normalized

    if 'datetime' in normalized.columns:
        normalized['datetime'] = pd.to_datetime(normalized['datetime'], utc=True, errors='coerce')
        normalized = normalized.dropna(subset=['datetime'])
        normalized.set_index('datetime', inplace=True)
    elif 'time' in normalized.columns:
        time_series = normalized['time']
        if pd.api.types.is_numeric_dtype(time_series):
            unit = 'ms' if time_series.max() > 10**11 else 's'
            normalized['datetime'] = pd.to_datetime(time_series, unit=unit, utc=True, errors='coerce')
        else:
            normalized['datetime'] = pd.to_datetime(time_series, utc=True, errors='coerce')
        normalized = normalized.dropna(subset=['datetime'])
        normalized.set_index('datetime', inplace=True)
    elif not isinstance(normalized.index, pd.DatetimeIndex):
        normalized.index = pd.to_datetime(normalized.index, utc=True, errors='coerce')
        normalized = normalized[~normalized.index.isna()]

    if normalized.index.tz is None:
        normalized.index = normalized.index.tz_localize(timezone.utc)
    else:
        normalized.index = normalized.index.tz_convert(timezone.utc)

    keep_cols = [col for col in ['open', 'high', 'low', 'close', 'volume'] if col in normalized.columns]
    normalized = normalized[keep_cols].sort_index()
    return normalized[~normalized.index.duplicated(keep='last')]

def get_daily_anchor_for_trade_date(trade_date, symbol):
    schedule = get_symbol_schedule(symbol)
    if schedule['is_futures']:
        anchor_date = trade_date - timedelta(days=1)
        return datetime.combine(anchor_date, schedule['session_open'], ET_TZ).astimezone(timezone.utc)
    return datetime.combine(trade_date, schedule['settlement'], ET_TZ).astimezone(timezone.utc)

def canonicalize_daily_bars(df, symbol):
    normalized = normalize_htf_dataframe(df)
    if normalized.empty:
        return normalized

    working = normalized.copy()
    working['_trade_date'] = [get_trade_date_for_timestamp(ts, symbol) for ts in working.index]
    working = working.sort_index()

    canonical = working.groupby('_trade_date').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'max',
    }).sort_index()
    canonical.index = pd.DatetimeIndex([get_daily_anchor_for_trade_date(day_value, symbol) for day_value in canonical.index], tz=timezone.utc)
    canonical.index.name = 'datetime'
    return canonical

def filter_finalized_daily_rows(df, symbol, now_utc):
    if df.empty:
        return df
    now_et = now_utc.astimezone(ET_TZ)
    latest_closed_trade_date = get_latest_closed_trade_date(now_et, symbol)
    keep_mask = [get_trade_date_for_timestamp(ts, symbol) <= latest_closed_trade_date for ts in df.index]
    filtered = df.loc[keep_mask].copy()
    return filtered.sort_index()

async def get_quote_settlement_info(symbol):
    """Retrieves settlement-ready quote info via Hub."""
    candidates = [symbol]
    stripped = symbol.lstrip('/')
    if stripped not in candidates:
        candidates.append(stripped)

    for candidate in candidates:
        try:
            result = await hub_request("get_quotes", {"symbols": [candidate]})
            if result.get("status") == "success":
                response = result.get("data", {})
                if not isinstance(response, dict) or 'errors' in response:
                    continue

                for payload in response.values():
                    if not isinstance(payload, dict): continue
                    
                    reference = payload.get('reference', {})
                    quote = payload.get('quote', {})
                    payload_symbol = payload.get('symbol', '')
                    product = reference.get('product', '')

                    symbol_matches = (
                        payload_symbol == symbol or
                        payload_symbol == candidate or
                        product == symbol or
                        product == f'/{stripped}' or
                        product == candidate
                    )
                    if not symbol_matches: continue

                    settlement_price = reference.get('futureSettlementPrice')
                    if settlement_price is None:
                        settlement_price = quote.get('closePrice')

                    if settlement_price is not None:
                        try:
                            settle_time = quote.get('settleTime')
                            settle_dt = None
                            if settle_time is not None:
                                settle_dt = pd.to_datetime(settle_time, unit='ms', utc=True).to_pydatetime()
                            return {
                                'price': float(settlement_price),
                                'settle_datetime': settle_dt,
                            }
                        except (TypeError, ValueError):
                            continue
        except Exception as e:
            print(f"⚠️ Failed to get quote for {candidate}: {e}")
            continue

    return None

async def get_quote_close_price(symbol):
    info = await get_quote_settlement_info(symbol)
    return info['price'] if info else None

async def apply_daily_settlement_override(df, symbol, now_utc):
    if df.empty: return df
    settlement_info = await get_quote_settlement_info(symbol)
    if settlement_info is None: return df

    settlement_close = settlement_info['price']
    now_et = now_utc.astimezone(ET_TZ)
    latest_closed_trade_date = get_latest_closed_trade_date(now_et, symbol)

    matching_rows = [ts for ts in df.index if get_trade_date_for_timestamp(ts, symbol) == latest_closed_trade_date]
    if not matching_rows: return df

    latest_idx = max(matching_rows)
    df.loc[latest_idx, 'close'] = settlement_close
    return df

def fetch_yfinance_daily_history(symbol, start_dt, end_dt, now_utc):
    yf_symbol = FUTURES_YFINANCE_MAP.get(symbol)
    if yf_symbol is None:
        raise ValueError(f"No yfinance mapping configured for {symbol}")
    if yf is None:
        raise RuntimeError("yfinance is not installed")

    history = yf.Ticker(yf_symbol).history(
        start=(start_dt - timedelta(days=3)).date(),
        end=(end_dt + timedelta(days=3)).date(),
        interval="1d",
        auto_adjust=False,
        actions=False,
    )
    if history.empty:
        return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

    date_col = 'Date' if 'Date' in history.reset_index().columns else history.reset_index().columns[0]
    history = history.reset_index()
    raw_dates = pd.to_datetime(history[date_col], errors='coerce')
    if raw_dates.dt.tz is None:
        raw_dates = raw_dates.dt.tz_localize(ET_TZ)
    else:
        raw_dates = raw_dates.dt.tz_convert(ET_TZ)

    trade_dates = raw_dates.dt.tz_localize(None).dt.normalize() - pd.Timedelta(days=1)
    daily_df = pd.DataFrame({
        'datetime': [get_daily_anchor_for_trade_date(day_value.date(), symbol) for day_value in trade_dates],
        'open': history['Open'].astype(float),
        'high': history['High'].astype(float),
        'low': history['Low'].astype(float),
        'close': history['Close'].astype(float),
        'volume': history['Volume'].fillna(0).astype(float),
    }).set_index('datetime').sort_index()

    return filter_finalized_daily_rows(daily_df, symbol, now_utc)

async def fetch_schwab_daily_history(symbol, start_dt, end_dt, now_utc):
    """Fetches daily history via Hub's REST proxy."""
    resp = await hub_request("get_price_history", {
        "symbol": symbol,
        "period_type": "year",
        "period": 1,
        "frequency_type": "daily",
        "frequency": 1,
        "need_extended_hours_data": True
    })
    
    if resp.get("status") != "success":
        print(f"  ❌ Failed to fetch daily history for {symbol}: {resp.get('message')}")
        return pd.DataFrame()
        
    data = resp.get("data", {})
    candles = data.get('candles', [])
    if not candles: return pd.DataFrame()
    
    df = pd.DataFrame(candles)
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms', utc=True)
    df.set_index('datetime', inplace=True)
    return df

def get_week_start_for_trade_date(trade_date, symbol):
    schedule = get_symbol_schedule(symbol)
    week_monday = trade_date - timedelta(days=trade_date.weekday())
    if schedule['is_futures']:
        week_start_date = week_monday - timedelta(days=1)
        return datetime.combine(week_start_date, schedule['session_open'], ET_TZ).astimezone(timezone.utc)
    return datetime.combine(week_monday, dt_time(0, 0), ET_TZ).astimezone(timezone.utc)

def build_weekly_from_daily(daily_df, symbol, now_utc):
    if daily_df.empty:
        return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

    grouped = daily_df.copy()
    grouped['_trade_date'] = [get_trade_date_for_timestamp(ts, symbol) for ts in grouped.index]
    grouped['_week_start'] = [get_week_start_for_trade_date(day_value, symbol) for day_value in grouped['_trade_date']]
    grouped = grouped.sort_index()

    weekly = grouped.groupby('_week_start').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
    }).sort_index()

    now_et = now_utc.astimezone(ET_TZ)
    current_trade_date = get_current_trade_date(now_et, symbol)
    current_week_start = get_week_start_for_trade_date(current_trade_date, symbol)
    week_is_final = now_et >= (get_settlement_datetime(current_trade_date, symbol) + timedelta(minutes=10)) and current_trade_date.weekday() == 4
    if not week_is_final and current_week_start in weekly.index:
        weekly = weekly.drop(index=current_week_start)
        
    return weekly

async def update_historical_files(symbol):
    """
    Updates Daily (1d) with finalized bars only and rebuilds Weekly (1W) from Daily.
    Futures default to yfinance for HTF data, with Schwab available via FUTURES_HTF_SOURCE=schwab.
    """
    symbol_map = {
        "/ES": "ES1", "/NQ": "NQ1", "/YM": "YM1", "/RTY": "RTY1",
        "/CL": "CL1", "/GC": "GC1","VVIX":"VVIX","VIX":"VIX","SPX":"SPX",
        "SPY":"SPY","QQQ":"QQQ","TSLA":"TSLA","NVDA":"NVDA","MSFT":"MSFT","AAPL":"AAPL","AMZN":"AMZN","META":"META"
    }
    ticker = symbol_map.get(symbol)
    if not ticker: return # Only update mapped futures/indices for now

    print(f"📅 [{symbol}] Checking historical data for {ticker}...")

    daily_path = os.path.join(DATA_DIR, f"{ticker}_1d.parquet")
    weekly_path = os.path.join(DATA_DIR, f"{ticker}_1W.parquet")
    now_utc = datetime.now(timezone.utc)
    htf_source = resolve_futures_htf_source() if symbol.startswith("/") else "schwab"

    existing_daily = pd.DataFrame()
    if os.path.exists(daily_path):
        try:
            existing_daily = pd.read_parquet(daily_path)
            if not existing_daily.empty:
                existing_daily = canonicalize_daily_bars(existing_daily, symbol)
        except Exception as e:
            print(f"  ⚠️ Error reading 1d: {e}")

    if htf_source == "yfinance" and symbol.startswith("/") and not existing_daily.empty:
        start_dt = (existing_daily.index.min() - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
    elif not existing_daily.empty:
        start_dt = (existing_daily.index.max() - timedelta(days=14)).astimezone(timezone.utc).replace(tzinfo=None)
    else:
        start_dt = (now_utc - timedelta(days=730)).replace(tzinfo=None)

    end_dt = now_utc.replace(tzinfo=None)
    if start_dt >= end_dt:
        start_dt = end_dt - timedelta(days=14)

    print(f"  ⬇️ Updating 1d from {start_dt.date()} via {htf_source}...")

    try:
        if htf_source == "yfinance" and symbol.startswith("/"):
            source_daily = fetch_yfinance_daily_history(symbol, start_dt, end_dt, now_utc)
            combined_daily = canonicalize_daily_bars(source_daily, symbol)
            combined_daily.to_parquet(daily_path)
            print(f"   ✅ Rebuilt 1d from yfinance: {len(combined_daily)} rows")
        else:
            new_df = await fetch_schwab_daily_history(symbol, start_dt, end_dt, now_utc)

            if not new_df.empty:
                if not existing_daily.empty:
                    combined_daily = pd.concat([existing_daily, new_df])
                else:
                    combined_daily = new_df.sort_index()

                combined_daily = canonicalize_daily_bars(combined_daily, symbol)
                combined_daily = await apply_daily_settlement_override(combined_daily, symbol, now_utc)
                combined_daily.to_parquet(daily_path)
                print(f"   ✅ Updated 1d: {len(combined_daily)} rows (Fetched {len(new_df)})")
            else:
                combined_daily = existing_daily
                print("   No new finalized daily data.")

        if combined_daily.empty:
            return

        weekly_df = build_weekly_from_daily(combined_daily, symbol, now_utc)
        weekly_df.to_parquet(weekly_path)
        print(f"   ✅ Rebuilt 1W from 1d: {len(weekly_df)} rows")

        # --- EXPORT TO JSON FOR FRONTEND LIVE CHARTS ---
        safe_sym = get_safe_symbol(symbol)
        live_dir = os.path.join(DATA_DIR, "live")
        
        def write_df_to_live_json(df, tf_suffix):
            if df.empty: return
            candles = []
            for ts, row in df.iterrows():
                candles.append({
                    "time": int(ts.timestamp() * 1000),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row.get("volume", 0))
                })
            out_path = os.path.join(live_dir, f"live_chart_{safe_sym}_{tf_suffix}.json")
            with open(out_path, "w") as f:
                json.dump({
                    "symbol": symbol,
                    "last_update": get_now_iso(),
                    "live_price": float(df.iloc[-1]["close"]),
                    "candles": candles
                }, f)
                
        # Daily/Weekly JSON exports decommissioned - frontend now queries Spoke/Parquet API directly.
        pass

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"   ⚠️ Historical update failed: {e}")

def normalize_client_symbol(symbol):
    if not symbol:
        return ""
    clean = symbol.replace("1!", "").replace("-", "/").upper()
    if not clean.startswith("/") and clean in ["NQ", "ES", "YM", "RTY", "CL", "GC"]:
        clean = "/" + clean
    return clean

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    symbol_raw = request.query.get("symbol")
    timeframe = request.query.get("timeframe", "1m")
    
    symbol = normalize_client_symbol(symbol_raw)
    if not symbol:
        await ws.close(code=4000, message=b"Missing symbol")
        return ws
        
    client_id = id(ws)
    active_connections.setdefault(symbol, {})[client_id] = (ws, timeframe)
    print(f"🔌 WebSocket client connected for {symbol} (tf: {timeframe})")
    
    # 1. Send initial snapshot from memory
    try:
        if symbol in charts:
            chart_ctx = charts[symbol]
            if timeframe == "15s":
                candles_to_send = chart_ctx["data_15s"]["candles"][-100:]
                live_p = chart_ctx["data_15s"]["live_price"]
            elif timeframe == "30s":
                candles_to_send = chart_ctx["data_30s"]["candles"][-100:]
                live_p = chart_ctx["data_30s"]["live_price"]
            else:
                candles_to_send = chart_ctx["data"]["candles"][-100:]
                live_p = chart_ctx["data"]["live_price"]
                
            await ws.send_json({
                "type": "snapshot",
                "symbol": symbol,
                "timeframe": timeframe,
                "live_price": live_p,
                "candles": candles_to_send
            })
        else:
            print(f"⚠️ WebSocket symbol {symbol} not in active charts watchlist")
            await ws.send_json({
                "type": "snapshot",
                "symbol": symbol,
                "timeframe": timeframe,
                "live_price": 0.0,
                "candles": []
            })
    except Exception as e:
        print(f"❌ Error sending initial snapshot to WS client: {e}")
        
    # 2. Keep connection open
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                if msg.data == "ping":
                    await ws.send_str("pong")
            elif msg.type == web.WSMsgType.ERROR:
                print(f"ws connection closed with exception {ws.exception()}")
    finally:
        # Clean up client
        if symbol in active_connections and client_id in active_connections[symbol]:
            del active_connections[symbol][client_id]
            if not active_connections[symbol]:
                del active_connections[symbol]
        print(f"🔌 WebSocket client disconnected for {symbol}")
        
    return ws

async def broadcast_quote(symbol, price, iso_time):
    if symbol not in active_connections:
        return
    message = json.dumps({
        "type": "quote",
        "symbol": symbol,
        "price": price,
        "time": iso_time
    })
    tasks = []
    for client_id, (ws, _) in list(active_connections[symbol].items()):
        try:
            tasks.append(ws.send_str(message))
        except Exception as e:
            pass
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def broadcast_candle(symbol, candle, timeframe="1m"):
    if symbol not in active_connections:
        return
    message = json.dumps({
        "type": "candle",
        "symbol": symbol,
        "timeframe": timeframe,
        "candle": candle
    })
    tasks = []
    for client_id, (ws, client_tf) in list(active_connections[symbol].items()):
        c_tf = "1m" if client_tf in ["1", "1m"] else client_tf
        s_tf = "1m" if timeframe in ["1", "1m"] else timeframe
        if c_tf == s_tf:
            try:
                tasks.append(ws.send_str(message))
            except Exception as e:
                pass
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def level_one_handler(msg):
    # msg is the data portion of the broadcast
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
                    
                    # Write Fast Quote (Decommissioned - frontend uses Spoke /quote API)
                    pass

                    # --- Sub-Minute Aggregation ---
                    curr_time = time.time()
                    update_sub_candle(chart_ctx["data_15s"], last_price, curr_time, 15)
                    update_sub_candle(chart_ctx["data_30s"], last_price, curr_time, 30)
                    
                    # Broadcast quote and sub-minute candles
                    await broadcast_quote(key, last_price, cdata["last_update"])
                    if chart_ctx["data_15s"]["candles"]:
                        await broadcast_candle(key, chart_ctx["data_15s"]["candles"][-1], "15s")
                    if chart_ctx["data_30s"]["candles"]:
                        await broadcast_candle(key, chart_ctx["data_30s"]["candles"][-1], "30s")

        # Batch write sub-minute JSONs (Decommissioned - sub-minute state kept in memory)
        pass

def save_candles_to_parquet(symbol, candles, parquet_path):
    """Saves a list of candles to the live storage parquet, ensuring no duplicates."""
    if not candles: return
    try:
        new_df = pd.DataFrame(candles)
        # Ensure timestamp column for consistency (though we primarily use 'time' ms)
        if 'time' in new_df.columns:
            new_df['timestamp'] = pd.to_datetime(new_df['time'], unit='ms')
            
        if not os.path.exists(parquet_path):
            new_df.to_parquet(parquet_path, index=False)
        else:
            existing_df = pd.read_parquet(parquet_path)
            # Combine, deduplicate on 'time', and save
            pd.concat([existing_df, new_df]).drop_duplicates(subset=['time']).sort_values('time').to_parquet(parquet_path, index=False)
        # print(f"📁 [{symbol}] Archived {len(candles)} bars to {os.path.basename(parquet_path)}")
    except Exception as e:
        print(f"❌ Error saving parquet for {symbol}: {e}")

async def chart_handler(msg):
    if 'content' not in msg: return
    
    impacted_symbols = set()
    
    for c in msg['content']:
        key = c.get('key')
        if key in charts:
            cdata = charts[key]["data"]
            files = charts[key]["files"]
            impacted_symbols.add(key)
            
            # Parse fields that are present (supports both named and numbered keys)
            candle_time = c.get("CHART_TIME_MILLIS") or c.get("1") or c.get(1)
            if not candle_time:
                continue
            candle_time = int(candle_time)

            # Helper to get float or None safely
            def get_val(keys):
                for k in keys:
                    v = c.get(k)
                    if v is not None:
                        try:
                            return float(v)
                        except (TypeError, ValueError):
                            pass
                return None

            open_val = get_val(["OPEN_PRICE", "2", 2])
            high_val = get_val(["HIGH_PRICE", "3", 3])
            low_val = get_val(["LOW_PRICE", "4", 4])
            close_val = get_val(["CLOSE_PRICE", "5", 5])
            volume_val = get_val(["VOLUME", "6", 6])
            
            # Update Buffer
            if cdata["candles"] and cdata["candles"][-1]["time"] == candle_time:
                # Merge delta into existing candle
                prev = cdata["candles"][-1]
                if open_val is not None: prev["open"] = open_val
                if high_val is not None: prev["high"] = high_val
                if low_val is not None: prev["low"] = low_val
                if close_val is not None: prev["close"] = close_val
                if volume_val is not None: prev["volume"] = int(volume_val)
            else:
                # Save previous finalized candle to live parquet storage
                if cdata["candles"]:
                    finalized_candle = cdata["candles"][-1]
                    save_candles_to_parquet(key, [finalized_candle], files["parquet"])

                # New candle
                prev = cdata["candles"][-1] if cdata["candles"] else None
                new_candle = {
                    "time": candle_time,
                    "open": open_val if open_val is not None else (prev["close"] if prev else 0.0),
                    "high": high_val if high_val is not None else (prev["close"] if prev else 0.0),
                    "low": low_val if low_val is not None else (prev["close"] if prev else 0.0),
                    "close": close_val if close_val is not None else (prev["close"] if prev else 0.0),
                    "volume": int(volume_val) if volume_val is not None else 0
                }
                cdata["candles"].append(new_candle)
                # Soft prune if too large
                if len(cdata["candles"]) > 20000:
                    cdata["candles"] = cdata["candles"][-15000:]
            
            cdata["last_update"] = get_now_iso()
            # Note: We don't overwrite live_price here, it's handled by level_one_handler.

    # Perform expensive operations (dedup, sort, write) ONCE per symbol per message
    for key in impacted_symbols:
        chart_ctx = charts[key]
        cdata = chart_ctx["data"]
        files = chart_ctx["files"]
        
        # Deduplicate ONCE per batch
        cdata["candles"] = deduplicate_candles(cdata["candles"])
        
        # Broadcast 1m candle update
        if cdata["candles"]:
            await broadcast_candle(key, cdata["candles"][-1], "1m")
            
        # Snapshot writing decommissioned - frontend fetches history and streams via WebSockets/Parquet.
        pass

async def handle_history(request):
    symbol = request.query.get("symbol")
    limit_str = request.query.get("limit", "180000")
    try:
        limit = int(limit_str)
    except:
        limit = 180000
        
    if not symbol:
        return web.json_response({"error": "Missing symbol"}, status=400)
        
    files = get_live_files(symbol)
    parquet_path = files["parquet"]
    
    try:
        if not os.path.exists(parquet_path):
            return web.json_response({"error": f"No parquet data for {symbol}"}, status=404)
            
        df = pd.read_parquet(parquet_path)
        df = df.tail(limit)
        
        candles = df.to_dict(orient="records")
        formatted = []
        for c in candles:
            formatted.append({
                "time": int(c["time"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": int(c.get("volume", 0))
            })
            
        return web.json_response({
            "symbol": symbol,
            "candles": formatted,
            "hasMore": len(df) >= limit
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_quote(request):
    symbol = request.query.get("symbol")
    if not symbol:
        return web.json_response({"error": "Missing symbol"}, status=400)
    
    # Normalize ticker (e.g. NQ1! -> /NQ, -NQ -> /NQ)
    clean = symbol.replace("1!", "").replace("-", "/").upper()
    if not clean.startswith("/") and clean in ["NQ", "ES", "YM", "RTY", "CL", "GC"]:
        clean = "/" + clean

    if clean in charts:
        cdata = charts[clean]["data"]
        return web.json_response({
            "symbol": clean,
            "price": cdata.get("live_price", 0.0),
            "time": cdata.get("last_update", "")
        })
    else:
        return web.json_response({"error": f"Symbol {clean} not in active charts"}, status=404)

async def start_api_server():
    app = web.Application()
    
    # Configure CORS
    import aiohttp_cors
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    
    resource = cors.add(app.router.add_resource("/history"))
    cors.add(resource.add_route("GET", handle_history))
    
    resource_quote = cors.add(app.router.add_resource("/quote"))
    cors.add(resource_quote.add_route("GET", handle_quote))
    
    # Add WebSocket endpoint
    app.router.add_get('/stream', websocket_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8001)
    await site.start()
    print("🌐 API Server started on http://0.0.0.0:8001")

async def main():
    print("🚀 [StreamChart] Starting as Spoke...")
    os.makedirs(os.path.join(DATA_DIR, "live"), exist_ok=True)

    # 1. Initialize Symbols
    symbols = get_watchlist_symbols()
    print(f"📋 Watching {len(symbols)} tickers: {symbols}")

    for sym in symbols:
        charts[sym] = init_chart_data(sym)
        # 1.1 Fetch Bootstrap
        boot = await fetch_bootstrap_data(sym)
        if boot:
            boot = validate_bootstrap_data(sym, boot)
            cdata = charts[sym]["data"]
            existing_times = {c["time"] for c in cdata["candles"]}
            cdata["candles"] = deduplicate_candles(cdata["candles"] + [c for c in boot if c["time"] not in existing_times])
            
            # 1.2 Detect and bridge gaps between restored data and bootstrap
            gaps = detect_gaps(cdata["candles"], sym)
            if gaps:
                print(f"🔧 [{sym}] Attempting to bridge {len(gaps)} gaps...")
                bridged = await bridge_gaps(sym, gaps)
                if bridged:
                    print(f"✅ [{sym}] Bridged {len(bridged)} missing bars.")
                    cdata["candles"] = deduplicate_candles(cdata["candles"] + bridged)
            
            if len(cdata["candles"]) > 20000:
                cdata["candles"] = cdata["candles"][-15000:]
            cdata["last_update"] = get_now_iso()
            
            # Commit bootstrap/bridged data to live storage parquet
            save_candles_to_parquet(sym, cdata["candles"], charts[sym]["files"]["parquet"])
            
            # No longer writing snapshot or checkpoint JSON files on boot.
            pass

    # 1.5 Start API Server
    await start_api_server()

    # 2. Historical Data Update (Daily/Weekly)
    print("\n📅 Updating Historical Files (Daily/Weekly)...")
    for sym in symbols:
        await update_historical_files(sym)

    # 3. Main Loop
    while True:
        try:
            async with websockets.connect(HUB_WS) as ws:
                print(f"✅ Connected to Hub at {HUB_WS}")
                while True:
                    msg_raw = await ws.recv()
                    msg = json.loads(msg_raw)
                    event_data = msg.get("data", {})
                    
                    service = event_data.get("service")
                    if service == "LEVELONE_FUTURES":
                        await level_one_handler(event_data)
                    elif service in ["CHART_FUTURES", "CHART_EQUITY"]:
                        await chart_handler(event_data)
                    
        except websockets.ConnectionClosed:
            print("❌ Hub connection closed. Retrying in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"⚠️ Spoke Error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping...")

