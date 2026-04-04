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
        resp = requests.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        
        # If it's a wrapped response from our special handlers (like 'resolve')
        if isinstance(result, dict) and "status" in result:
            if result.get("status") != "success":
                raise RuntimeError(f"Hub proxy error: {result.get('message')}")
            return result.get("data", {})
        
        # Otherwise, assume it's direct data from the Schwab API
        return result
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
        
        log.info(f"Fetching chain chunk for {symbol}: DTE {from_dte}-{to_dte}...")
        try:
            payload = _hub_request("get_option_chain", params)
        except RuntimeError as e:
            if "TooBigBody" in str(e) and strike_count > 20:
                log.warning(f"Body too big for {symbol} at strikeCount={strike_count}. Reducing and retrying...")
                params["strikeCount"] = 25
                payload = _hub_request("get_option_chain", params)
            else:
                raise

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

        current_dte = to_dte + 1
        if current_dte > max_dte:
            break

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
    try:
        res = _hub_request("resolve", {"symbols": [symbol]})
        # _hub_request already returns either the direct dict or result.get("data")
        # If it returned result.get("data"), then mapping is res.get(symbol)
        # If it returned direct, it might be nested
        
        mapping = res.get(symbol) or res.get("data", {}).get(symbol, {})
        active = mapping.get("active", symbol)
        
        log.info(f"Resolved {symbol} to {active} for quoting.")
        
        qres = _hub_request("get_quotes", {"symbols": [active]})
        data = qres.get(active, {})
        q = data.get("quote", {})
        
        last = _safe_float(q.get("mark") or q.get("lastPrice"))
        open_p = _safe_float(q.get("openPrice") or q.get("sessionOpen"))
        
        log.info(f"Quote for {active}: last={last}, open={open_p}")
        
        return FuturesQuote(symbol=symbol, price=last, open_price=open_p)
    except Exception as e:
        log.error("Failed to fetch futures quote for %s from Hub: %s", symbol, e)
        last, open_p = _fetch_futures_from_yfinance(symbol)
        if last is None:
            log.error(f"Total failure to quote {symbol} (Hub and yfinance both failed).")
        return FuturesQuote(symbol=symbol, price=last, open_price=open_p)


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
    log.info(f"Using active contract {active_contract} (clean: {root_clean}) for option resolution.")
    
    spot_info = fetch_futures_quote(symbol)
    if not spot_info or spot_info.price is None:
        raise RuntimeError(f"Could not get spot price for {symbol} to generate strikes.")
    
    spot = spot_info.price
    
    increment = 100 if "NQ" in symbol else 5
    base_strike = round(spot / increment) * increment
    strikes = [base_strike + (i * increment) for i in range(-50, 51)]
    
    log.info(f"Generating symbols for {symbol} (root: {root_clean}) centered at {base_strike}...")
    symbols = []
    for s in strikes:
        symbols.append(f"./{root_clean}C{s}")
        symbols.append(f"./{root_clean}P{s}")
    
    log.info(f"Generated {len(symbols)} symbols. Sample: {symbols[:4]}")
        
    all_quotes = {}
    for i in range(0, len(symbols), 400):
        batch = symbols[i:i+400]
        resp = _hub_request("get_quotes", {"symbols": batch})
        if isinstance(resp, dict):
            # If the Hub returns direct Schwab format, it's { "symbol": { "quote": ... } }
            results_in_batch = len(resp)
            log.info(f"Batch {i//400} (size {len(batch)}) returned {results_in_batch} results.")
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
        spot_open=spot_info.open,
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
        log.info(f'yfinance fallback for {symbol} ({yf_symbol}): last={last}, open={open_p}')
        return last, open_p
    except Exception as e: 
        log.error(f'yfinance fetch failed for {yf_symbol}: {e}')
        return None, None

