from __future__ import annotations

import logging
import requests
import json
from pathlib import Path
from datetime import date, timedelta, datetime, time
from typing import Any, Optional
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import schwab
try:
    import yfinance as yf
except ImportError:
    yf = None


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.streaming.options.config import (
    SCHWAB_INDEX_PREFIX, 
    SECRETS_PATH, 
    TOKEN_PATH,
    NY_SESSION_ROLLOVER_TIME,
    OPTION_CHAIN_WIDE_WINDOW,
    FUTURES_YF_MAP,
    HUB_URL,
    LARGE_INDICES
)

log = logging.getLogger(__name__)

def _hub_request(method: str, params: dict) -> dict:
    """Send a REST request through the Hub's proxy."""
    try:
        if method == "resolve":
            resp = requests.post(f"{HUB_URL}/resolve", json=params, timeout=30)
        else:
            resp = requests.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        
        # If it's a wrapped response from our special handlers (like 'resolve')
        if isinstance(result, dict) and "status" in result:
            if result.get("status") != "success":
                raise RuntimeError(f"Hub proxy error: {result.get('message')}")
            return result.get("data") or {}
        
        # Otherwise, assume it's direct data from the Schwab API
        return result or {}
    except Exception as e:
        log.error(f"Failed to reach Hub proxy: {e}")
        raise RuntimeError(f"Hub proxy unreachable: {e}")


@dataclass
class OptionContract:
    symbol: str
    strike: float
    type: str = "" # Legancy support
    contract_type: str = "" # Canonical naming
    expiry: Any = "" # Can be str, int, or date
    last: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    mark: float = 0.0
    volume: int = 0
    open_interest: int = 0
    iv: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    dte: int = 0

    def __post_init__(self):
        # Ensure expiry is a date object
        orig = self.expiry
        if isinstance(self.expiry, (int, float)):
            # Assume timestamp in ms
            self.expiry = datetime.fromtimestamp(self.expiry / 1000.0, tz=ZoneInfo("UTC")).date()
        elif isinstance(self.expiry, str) and self.expiry:
            try:
                # Try ISO format (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
                self.expiry = datetime.fromisoformat(self.expiry.split(" ")[0]).date()
            except ValueError:
                pass
        
        if not isinstance(self.expiry, date):
            log.warning(f"Failed to convert expiry '{orig}' (type {type(orig)}) to date object for {self.symbol}")

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0 if self.bid and self.ask else self.last


@dataclass
class OptionChainData:
    ticker: str
    spot: float
    spot_open: float
    timestamp: datetime
    contracts: list[OptionContract] = field(default_factory=list)
    underlying_symbol: str = ""
    spot_price: float = 0.0
    is_futures: bool = False  # True for RTD-native futures chains → use Black-76 pricing

    def __post_init__(self):
        if not self.underlying_symbol:
            self.underlying_symbol = self.ticker
        if not self.spot_price:
            self.spot_price = self.spot

    @property
    def calls(self) -> list[OptionContract]:
        return [c for c in self.contracts if c.contract_type == "CALL"]

    @property
    def puts(self) -> list[OptionContract]:
        return [c for c in self.contracts if c.contract_type == "PUT"]

    @property
    def chain_volatility(self) -> float:
        """Calculate average IV across all contracts."""
        if not self.contracts:
            return 0.0
        return sum(c.iv for c in self.contracts) / len(self.contracts)


@dataclass
class FuturesQuote:
    symbol: str
    price: float | None
    open_price: float | None


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def create_client(secrets_path: Path = SECRETS_PATH, token_path: Path = TOKEN_PATH) -> schwab.Client:
    """
    Dummy/Legacy client creator. 
    In the Hub-based architecture, we proxy most calls.
    """
    return None


def fetch_option_chain_data(client: Any, symbol: str, dte_targets: list[int]) -> OptionChainData:
    """
    Fetch raw options data from Schwab, filter by DTE, and return flattened contracts.
    """
    if not dte_targets:
        raise ValueError("dte_targets must not be empty.")

    if symbol.startswith("/"):
        return fetch_futures_option_chain_data(symbol, dte_targets)

    api_sym = SCHWAB_INDEX_PREFIX.get(symbol, symbol)
    
    today = _today_ny(rollover_time=NY_SESSION_ROLLOVER_TIME)
    max_dte = max(dte_targets) + OPTION_CHAIN_WIDE_WINDOW
    
    is_large = symbol in LARGE_INDICES or api_sym in LARGE_INDICES
    # Total strikes across whole YEAR for SPX etc. needs to be tighter
    # than current 100 to avoid overflow even with chunking.
    strike_count = 60 if is_large and max_dte > 30 else 100

    # Date partitioning (for Hub proxy stability)
    # If the range is > 45 days, fetch in chunks.
    partition_size = 45 if is_large else 366
    
    all_contracts: list[OptionContract] = []
    spot: float = 0.0
    spot_open: float = 0.0
    
    # Generate chunks
    chunks = []
    current_dte = 0
    while current_dte <= max_dte:
        from_dte = current_dte
        to_dte = min(current_dte + partition_size, max_dte)
        
        from_date = today + timedelta(days=from_dte)
        to_date = today + timedelta(days=to_dte)
        
        params = {
            "symbol": api_sym,
            "fromDate": from_date.isoformat(),
            "toDate": to_date.isoformat(),
            "strikeCount": strike_count
        }
        chunks.append((from_dte, to_dte, params))
        
        current_dte = to_dte + 1
        if current_dte > max_dte:
            break

    # Fetch chunks concurrently
    from concurrent.futures import ThreadPoolExecutor
    
    def fetch_chunk(chunk_info):
        from_dte, to_dte, params = chunk_info
        log.debug(f"Fetching chain chunk for {symbol}: DTE {from_dte}-{to_dte}...")
        try:
            payload = _hub_request("get_option_chain", params)
            return payload
        except RuntimeError as e:
            if "TooBigBody" in str(e) and params["strikeCount"] > 20:
                log.debug(f"Body too big for {symbol} at strikeCount={params['strikeCount']}. Reducing and retrying...")
                params_copy = params.copy()
                params_copy["strikeCount"] = 25
                try:
                    payload = _hub_request("get_option_chain", params_copy)
                    return payload
                except Exception as retry_err:
                    log.error(f"Retry chunk failed for {symbol}: {retry_err}")
                    return None
            else:
                log.error(f"Chunk fetch failed for {symbol}: {e}")
                return None
        except Exception as e:
            log.error(f"Chunk fetch failed for {symbol}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=min(len(chunks), 10)) as executor:
        payloads = list(executor.map(fetch_chunk, chunks))

    for payload in payloads:
        if not payload:
            continue

        # Extract underlying metrics from the first successful chunk
        if spot == 0:
            underlying = payload.get("underlying") or {}
            raw_spot = (
                underlying.get("mark")
                if underlying.get("mark") is not None
                else underlying.get("last")
                if underlying.get("last") is not None
                else payload.get("underlyingPrice")
            )
            spot = _safe_float(raw_spot)
            spot_open = _safe_float(
                underlying.get("openPrice") 
                or underlying.get("sessionOpen") 
                or underlying.get("open") 
            )
            if spot_open == 0.0:
                try:
                    qres = _hub_request("get_quotes", {"symbols": [api_sym]})
                    qdata = qres.get(api_sym, {})
                    q_val = qdata.get("quote", {})
                    fetched_open = _safe_float(q_val.get("openPrice") or q_val.get("sessionOpen"))
                    if fetched_open:
                        spot_open = fetched_open
                        log.debug("Fetched spot open price for %s via get_quotes fallback: %.2f", symbol, spot_open)
                except Exception as e:
                    log.debug("Could not fetch spot open price for %s via get_quotes fallback: %s", symbol, e)

        call_map = payload.get("callExpDateMap", {})
        put_map = payload.get("putExpDateMap", {})

        # Process this chunk's expirations
        all_exp_keys = sorted(set(call_map.keys()) | set(put_map.keys()))
        selected_exp_keys = _select_expiration_keys({k: {} for k in all_exp_keys}, dte_targets)
        
        # Only add contracts that match our target DTE list AND were found in this batch
        for exp_key in selected_exp_keys:
            # Check if this exp_key was returned in THIS chunk
            # If so, process its contracts.
            if exp_key in call_map:
                for strike_str, strike_list in call_map[exp_key].items():
                    for c in strike_list:
                        all_contracts.append(_map_contract(c, "CALL"))
            if exp_key in put_map:
                for strike_str, strike_list in put_map[exp_key].items():
                    for c in strike_list:
                        all_contracts.append(_map_contract(c, "PUT"))

    if spot == 0:
        log.warning("Spot price is zero for %s — levels may be inaccurate.", symbol)

    # Deduplicate in case expiries overlap chunks (shouldn't happen with +1 but safe)
    # Using a simple dict-based dedup on contract symbol
    unique_contracts = {c.symbol: c for c in all_contracts}
    
    return OptionChainData(
        ticker=symbol,
        spot=spot,
        spot_open=spot_open,
        timestamp=datetime.now(ZoneInfo("UTC")),
        contracts=list(unique_contracts.values())
    )


def fetch_futures_quote(symbol: str) -> FuturesQuote:
    """
    Fetch the latest price for a futures ticker via the Hub's resolve/quotes path.
    """
    if not symbol:
        return FuturesQuote(symbol=None, price=None, open_price=None)

    try:
        res = _hub_request("resolve", {"symbols": [symbol]})
        # _hub_request already returns either the direct dict or result.get("data")
        # If it returned result.get("data"), then mapping is res.get(symbol)
        # If it returned direct, it might be nested
        
        mapping = res.get(symbol) or res.get("data", {}).get(symbol, {})
        active = mapping.get("active", symbol)
        
        log.debug(f"Resolved {symbol} to {active} for quoting.")
        
        qres = _hub_request("get_quotes", {"symbols": [active]})
        data = qres.get(active, {})
        q = data.get("quote", {})
        
        last = _safe_float(q.get("mark") or q.get("lastPrice"))
        open_p = _safe_float(q.get("sessionOpen") or q.get("openPrice"))

        log.debug(f"Quote for {active}: last={last}, open={open_p}")

        return FuturesQuote(symbol=symbol, price=last, open_price=open_p)
    except Exception as e:
        log.error("Failed to fetch futures quote for %s from Hub: %s", symbol, e)
        last, open_p = _fetch_futures_from_yfinance(symbol)
        if last is None:
            log.error(f"Total failure to quote {symbol} (Hub and yfinance both failed).")
        return FuturesQuote(symbol=symbol, price=last, open_price=open_p)


def fetch_batched_futures_quotes(symbols: list[str]) -> dict[str, FuturesQuote]:
    """
    Fetch latest futures quotes for multiple symbols in a single batched Hub REST call.
    Reduces N resolve + N quote calls down to 1 resolve + 1 quote call.
    """
    clean_syms = [s for s in set(symbols) if s]
    if not clean_syms:
        return {}

    try:
        res = _hub_request("resolve", {"symbols": clean_syms})
        active_map: dict[str, str] = {}
        for sym in clean_syms:
            mapping = res.get(sym) or res.get("data", {}).get(sym, {})
            active_map[sym] = mapping.get("active", sym)

        active_symbols = list(set(active_map.values()))
        qres = _hub_request("get_quotes", {"symbols": active_symbols})
        
        results: dict[str, FuturesQuote] = {}
        for orig_sym, active_sym in active_map.items():
            data = qres.get(active_sym, {})
            q = data.get("quote", {})
            last = _safe_float(q.get("mark") or q.get("lastPrice"))
            open_p = _safe_float(q.get("sessionOpen") or q.get("openPrice"))
            if last is not None:
                results[orig_sym] = FuturesQuote(symbol=orig_sym, price=last, open_price=open_p)
            else:
                results[orig_sym] = fetch_futures_quote(orig_sym)
        return results
    except Exception as e:
        log.error("Failed batched futures quotes fetch: %s — falling back to single fetch.", e)
        return {s: fetch_futures_quote(s) for s in clean_syms}


# ---------------------------------------------------------------------------
# Futures symbol → live_storage filename stem
# ---------------------------------------------------------------------------
_FUTURES_LIVE_STORAGE_MAP: dict[str, str] = {
    "/ES":  "-ES",
    "/NQ":  "-NQ",
    "/RTY": "-RTY",
    "/YM":  "-YM",
    "/GC":  "-GC",
    "/CL":  "-CL",
}


def get_eod_close_price(symbol: str, target_dt_utc: datetime) -> float | None:
    """
    Return the close price of the 1-minute bar whose open timestamp matches
    *target_dt_utc* (UTC-naive datetime, second-precision).

    Two source paths are supported:

    Futures (``/ES``, ``/NQ``, ``/RTY``, ``/YM`` …)
        Reads ``data/live/live_storage_{stem}.parquet``.
        Schema: ``timestamp`` column, UTC-naive datetime64[ns], minute bars.
        A bar labelled ``2026-06-25 19:59:00`` is the 15:59 ET candle.

    SPX cash spot (``"SPX"``)
        Reads ``data/SPX_1m.parquet``.
        Schema: DatetimeIndex named ``datetime``, US/Eastern timezone-aware.
        A bar labelled ``2026-06-25 16:04:00-04:00`` is the 16:04 ET candle.

    Returns ``None`` if the file is missing, the bar is not found, or any
    read error occurs.
    """
    try:
        import pandas as pd
        from scripts.streaming.options.config import LIVE_STORAGE_DIR, OHLCV_DATA_DIR

        if symbol == "SPX":
            path = LIVE_STORAGE_DIR / "live_storage_SPX.parquet"
            close_val = None
            target_ts = pd.Timestamp(target_dt_utc)

            # 1. Try reading from live_storage_SPX.parquet
            if path.exists():
                try:
                    df = pd.read_parquet(path, columns=["timestamp", "close"])
                    row = df[df["timestamp"] == target_ts]
                    if not row.empty:
                        close_val = float(row.iloc[0]["close"])
                        log.debug("get_eod_close_price SPX: found %.2f at %s UTC (parquet)", close_val, target_ts)
                        return close_val
                    else:
                        # Fallback to the last available candle on target day in parquet
                        df_today = df[df["timestamp"].dt.date == target_ts.date()]
                        if not df_today.empty:
                            last_row = df_today.sort_values("timestamp").iloc[-1]
                            close_val = float(last_row["close"])
                            log.debug(
                                "get_eod_close_price SPX: target %s UTC not found in parquet. Falling back to last bar of the day: %.2f at %s UTC",
                                target_ts, close_val, last_row["timestamp"]
                            )
                            return close_val
                except Exception as e:
                    log.debug("get_eod_close_price SPX: error reading parquet %s: %s", path, e)

            # 2. Fallback: fetch from Hub REST API
            log.debug("get_eod_close_price SPX: %s not found in parquet, querying Hub REST API...", target_ts)
            try:
                resp = _hub_request("get_price_history", {
                    "symbol": "$SPX",
                    "period_type": "day",
                    "period": 1,
                    "frequency_type": "minute",
                    "frequency": 1,
                    "need_extended_hours_data": True
                })
                candles = resp.get("candles", [])
                if candles:
                    new_candles = []
                    for c in candles:
                        c_time = float(c.get("datetime", 0))
                        new_candles.append({
                            "time": c_time,
                            "open": float(c.get("open", 0)),
                            "high": float(c.get("high", 0)),
                            "low": float(c.get("low", 0)),
                            "close": float(c.get("close", 0)),
                            "volume": int(c.get("volume", 0))
                        })
                    
                    new_df = pd.DataFrame(new_candles)
                    new_df["timestamp"] = pd.to_datetime(new_df["time"], unit="ms")
                    
                    # Find target candle
                    target_row = new_df[new_df["timestamp"] == target_ts]
                    if not target_row.empty:
                        close_val = float(target_row.iloc[0]["close"])
                        log.debug("get_eod_close_price SPX: found %.2f at %s UTC (Hub REST)", close_val, target_ts)
                    else:
                        # Fallback to the last available candle on target day from API response
                        df_today = new_df[new_df["timestamp"].dt.date == target_ts.date()]
                        if not df_today.empty:
                            last_row = df_today.sort_values("timestamp").iloc[-1]
                            close_val = float(last_row["close"])
                            log.debug(
                                "get_eod_close_price SPX: target %s UTC not found. Falling back to last bar of the day: %.2f at %s UTC",
                                target_ts, close_val, last_row["timestamp"]
                            )

                    # Cache/save to parquet
                    if not path.exists():
                        new_df.to_parquet(path, index=False)
                    else:
                        existing_df = pd.read_parquet(path)
                        pd.concat([existing_df, new_df]).drop_duplicates(subset=["time"], keep="last").sort_values("time").to_parquet(path, index=False)
                    log.debug("get_eod_close_price SPX: Cached %d candles to %s", len(new_df), path)

                    if close_val is not None:
                        return close_val
            except Exception as e:
                log.error("get_eod_close_price SPX: Hub REST fallback failed: %s", e)

            # 3. Graceful fallback: return None (the caller will retain underlying.mark)
            log.warning("get_eod_close_price SPX: could not fetch/find close at %s UTC", target_ts)
            return None


        # --- Futures path ---
        stem = _FUTURES_LIVE_STORAGE_MAP.get(symbol)
        if stem is None:
            log.warning("get_eod_close_price: no live_storage mapping for %s", symbol)
            return None
        path = LIVE_STORAGE_DIR / f"live_storage_{stem}.parquet"
        if not path.exists():
            log.warning("get_eod_close_price: %s not found", path)
            return None

        df = pd.read_parquet(path, columns=["timestamp", "close"])
        # timestamp is UTC-naive datetime64[ns] — match exactly.
        target_ts = pd.Timestamp(target_dt_utc)
        row = df[df["timestamp"] == target_ts]
        if row.empty:
            log.warning("get_eod_close_price %s: bar %s UTC not found", symbol, target_ts)
            return None
        close = float(row.iloc[0]["close"])
        log.debug("get_eod_close_price %s: found %.2f at %s UTC", symbol, close, target_ts)
        return close

    except Exception as exc:
        log.error("get_eod_close_price(%s, %s) failed: %s", symbol, target_dt_utc, exc)
        return None


def fetch_futures_option_chain_data(symbol: str, dte_targets: list[int]) -> OptionChainData:
    """

    Directly fetch futures options data using REST 'quotes' for generated symbols.
    format: ./ROOT{month}{year}{C/P}{strike}
    """
    res = _hub_request("resolve", {"symbols": [symbol]})
    # res is now either the direct dict or result.get("data")
    mapping = res.get(symbol) or res.get("data", {}).get(symbol, {})
    active_contract = mapping.get("active", symbol)
    
    root_clean = active_contract.replace("/", "")
    log.debug(f"Using active contract {active_contract} (clean: {root_clean}) for option resolution.")

    spot_info = fetch_futures_quote(symbol)
    if not spot_info or spot_info.price is None:
        raise RuntimeError(f"Could not get spot price for {symbol} to generate strikes.")

    spot = spot_info.price

    increment = 100 if "NQ" in symbol else 5
    base_strike = round(spot / increment) * increment
    strikes = [base_strike + (i * increment) for i in range(-50, 51)]

    log.debug(f"Generating symbols for {symbol} (root: {root_clean}) centered at {base_strike}...")
    symbols = []
    for s in strikes:
        symbols.append(f"./{root_clean}C{s}")
        symbols.append(f"./{root_clean}P{s}")

    log.debug(f"Generated {len(symbols)} symbols. Sample: {symbols[:4]}")

    all_quotes = {}
    for i in range(0, len(symbols), 400):
        batch = symbols[i:i+400]
        resp = _hub_request("get_quotes", {"symbols": batch})
        if isinstance(resp, dict):
            # If the Hub returns direct Schwab format, it's { "symbol": { "quote": ... } }
            results_in_batch = len(resp)
            log.debug(f"Batch {i//400} (size {len(batch)}) returned {results_in_batch} results.")
            all_quotes.update(resp)
        else:
            log.warning(f"Batch {i//400} returned non-dict response: {type(resp)}")
            
    contracts: list[OptionContract] = []
    for sym, q in all_quotes.items():
        ref = q.get("reference", {})
        quote = q.get("quote", {})
        strike = ref.get("strikePrice")
        if strike is None: continue
        
        bid = _safe_float(quote.get("bidPrice"))
        ask = _safe_float(quote.get("askPrice"))
        last = _safe_float(quote.get("lastPrice") or quote.get("mark"))
        mid = (bid + ask) / 2.0 if (bid and ask) else last
        
        contracts.append(OptionContract(
            symbol=sym,
            strike=float(strike),
            contract_type="CALL" if ref.get("contractType") == "C" else "PUT",
            expiry=ref.get("expiryDate") or ref.get("expirationDate") or "",
            last=last,
            bid=bid,
            ask=ask,
            mark=_safe_float(quote.get("mark")) or mid,
            volume=int(quote.get("totalVolume") or 0),
            open_interest=int(quote.get("openInterest") or 0),
            iv=_safe_float(quote.get("volatility", 0.0)) / 100.0,
            delta=_safe_float(quote.get("delta")),
            gamma=_safe_float(quote.get("gamma")),
            theta=_safe_float(quote.get("theta")),
            vega=_safe_float(quote.get("vega")),
            rho=_safe_float(quote.get("rho")),
            dte=int(ref.get("daysToExpiration") or 0)
        ))
        
    if not contracts:
        raise RuntimeError(f"No futures options contracts found for {symbol}")

    return OptionChainData(
        ticker=symbol,
        spot=spot,
        spot_open=spot_info.open_price,
        timestamp=datetime.now(ZoneInfo("UTC")),
        contracts=contracts
    )


def _map_contract(c: dict, ctype: str) -> OptionContract:
    bid = _safe_float(c.get("bid"))
    ask = _safe_float(c.get("ask"))
    last = _safe_float(c.get("last"))
    return OptionContract(
        symbol=c.get("symbol", ""),
        strike=float(c.get("strikePrice", 0)),
        contract_type=ctype,
        expiry=str(c.get("expirationDate", "")),
        last=last,
        bid=bid,
        ask=ask,
        mark=(bid + ask) / 2.0 if (bid and ask) else last,
        volume=int(c.get("totalVolume", 0)),
        open_interest=int(c.get("openInterest", 0)),
        iv=_safe_float(c.get("volatility", 0.0)) / 100.0,
        delta=_safe_float(c.get("delta", 0.0)),
        gamma=_safe_float(c.get("gamma", 0.0)),
        theta=_safe_float(c.get("theta", 0.0)),
        vega=_safe_float(c.get("vega", 0.0))
    )


def _select_expiration_keys(exp_map: dict, dte_targets: list[int]) -> list[str]:
    if not exp_map: return []
    all_keys = sorted(exp_map.keys())
    results = []
    for target in dte_targets:
        best_key = None
        min_diff = 999
        for k in all_keys:
            try:
                days = int(k.split(":")[1])
                diff = abs(days - target)
                if diff < min_diff:
                    min_diff = diff
                    best_key = k
            except: continue
        if best_key and best_key not in results:
            results.append(best_key)
    return results


def _today_ny(rollover_time: Optional[time] = None) -> date:
    tz = ZoneInfo("America/New_York")
    now = datetime.now(tz)
    
    # If a rollover time is provided (e.g. 4 PM ET), treat time 
    # at/after that as the "next" day for option chain fetching.
    if rollover_time and now.time() >= rollover_time:
        return (now + timedelta(days=1)).date()
        
    return now.date()


def _safe_float(val: Any) -> float:
    try: return float(val) if val is not None else 0.0
    except: return 0.0



def _fetch_futures_from_yfinance(symbol: str) -> tuple[float | None, float | None]:
    if yf is None: 
        log.warning('yfinance not installed, cannot fetch fallback quote.')
        return None, None
    yf_symbol = FUTURES_YF_MAP.get(symbol)
    if not yf_symbol: 
        log.warning(f'No yfinance mapping for {symbol}')
        return None, None
    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period='1d')
        if hist.empty: 
            log.warning(f'yfinance returned empty history for {yf_symbol}')
            return None, None
        last = float(hist['Close'].iloc[-1])
        open_p = float(hist['Open'].iloc[0])
        log.debug(f'yfinance fallback for {symbol} ({yf_symbol}): last={last}, open={open_p}')
        return last, open_p
    except Exception as e: 
        log.error(f'yfinance fetch failed for {yf_symbol}: {e}')
        return None, None

