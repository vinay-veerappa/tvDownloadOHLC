"""
options_fetcher.py
==================
All Charles Schwab API I/O lives here.

Public surface
--------------
create_client()          — Authenticated schwab.Client from secrets/token files.
fetch_option_chain_data()— Full option chain for a ticker, filtered to DTE targets.
fetch_futures_quote()    — Current price for a front-month futures symbol.

Domain objects
--------------
OptionContract  — Single option contract with greeks and market data.
OptionChainData — All calls/puts for one underlying, one DTE window.
FuturesQuote    — A single futures price snapshot.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from datetime import date, timedelta, datetime, time
from zoneinfo import ZoneInfo

import requests
import schwab

try:
    import yfinance as yf
except ImportError:
    yf = None

from .config import (
    SCHWAB_INDEX_PREFIX, 
    SECRETS_PATH, 
    TOKEN_PATH,
    NY_SESSION_ROLLOVER_TIME,
    OPTION_CHAIN_WIDE_WINDOW,
    FUTURES_YF_MAP
)

log = logging.getLogger(__name__)

HUB_URL = "http://127.0.0.1:8000"

def _hub_request(method: str, params: dict) -> dict:
    """Send a REST request through the Hub's proxy."""
    try:
        resp = requests.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get("status") != "success":
            raise RuntimeError(f"Hub proxy error: {result.get('message')}")
        return result.get("data", {})
    except Exception as e:
        log.error(f"Failed to reach Hub proxy: {e}")
        raise RuntimeError(f"Hub proxy unreachable: {e}")


# ---------------------------------------------------------------------------
# Domain objects
# ---------------------------------------------------------------------------

@dataclass
class OptionContract:
    symbol: str
    strike: float
    expiry: date
    contract_type: str       # "CALL" or "PUT"
    open_interest: int
    volume: int
    mark: float
    bid: float
    ask: float
    iv: float                # decimal, e.g. 0.20 for 20%
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    dte: int


@dataclass
class OptionChainData:
    underlying_symbol: str   # normalised Schwab API symbol
    spot_price: float
    spot_open: float = 0.0
    chain_volatility: float = 0.0
    calls: list[OptionContract] = field(default_factory=list)
    puts:  list[OptionContract] = field(default_factory=list)


@dataclass
class FuturesQuote:
    symbol: str
    price: float
    open_price: float = 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _today_ny() -> date:
    """
    Return the logical trading date in Eastern Time.
    Before 4:00 PM EST, the target date is today.
    After 4:00 PM EST, the target date officially rolls over to tomorrow.
    """
    ny_time = datetime.now(ZoneInfo("America/New_York"))
    
    # If the current time is past the rollover time (e.g. 16:00 EST), roll forward 1 day
    if ny_time.time() >= NY_SESSION_ROLLOVER_TIME:
        return (ny_time + timedelta(days=1)).date()
        
    return ny_time.date()


def _schwab_symbol(symbol: str) -> str:
    """Return the Schwab API symbol for *symbol*, applying the $ prefix where needed."""
    return SCHWAB_INDEX_PREFIX.get(symbol.upper(), symbol)


def _best_mark(opt: dict[str, Any]) -> float:
    if opt.get("mark") is not None:
        return float(opt["mark"])
    return (float(opt.get("bid", 0)) + float(opt.get("ask", 0))) / 2.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value) if value is not None else default
        # Treat NaN/Inf as missing — callers should not receive poisoned floats.
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _parse_contract(raw: dict[str, Any], contract_type: str) -> OptionContract | None:
    """Parse a single raw Schwab option dict into an OptionContract."""
    try:
        exp_str = raw.get("expirationDate", "")
        exp_date = date.fromisoformat(exp_str[:10]) if exp_str else _today_ny()

        # Schwab sends volatility as a percentage (e.g. 20.0 → 0.20).
        # It can also be NaN for illiquid contracts — _safe_float handles both.
        iv_raw = raw.get("volatility")
        iv_pct = _safe_float(iv_raw)
        iv = iv_pct / 100.0 if iv_pct != 0.0 else 0.0

        return OptionContract(
            symbol=raw.get("symbol", ""),
            strike=_safe_float(raw.get("strikePrice")),
            expiry=exp_date,
            contract_type=contract_type,
            open_interest=int(raw.get("openInterest") or 0),
            volume=int(raw.get("totalVolume") or 0),
            mark=_best_mark(raw),
            bid=_safe_float(raw.get("bid")),
            ask=_safe_float(raw.get("ask")),
            iv=iv,
            delta=_safe_float(raw.get("delta")),
            gamma=_safe_float(raw.get("gamma")),
            theta=_safe_float(raw.get("theta")),
            vega=_safe_float(raw.get("vega")),
            rho=_safe_float(raw.get("rho")),
            dte=int(raw.get("daysToExpiration") or 0),
        )
    except Exception as exc:
        # Log at WARNING so systematic parse failures (e.g. API field renames)
        # are visible rather than silently swallowed at DEBUG level.
        log.warning("Contract parse error (%s): %s", raw.get("symbol", "?"), exc)
        return None


def _parse_exp_key(exp_key: str) -> tuple[date, int]:
    """
    Parse Schwab expiration key format: "YYYY-MM-DD:DTE".
    We completely ignore Schwab's DTE integer because it goes stale overnight,
    and calculate it strictly against NY time.
    """
    date_part, _, _ = exp_key.partition(":")
    exp_date = date.fromisoformat(date_part)
    
    # Calculate the true DTE using our timezone-aware helper
    true_dte = (exp_date - _today_ny()).days
    
    return exp_date, true_dte


def _select_expiration_keys(
    option_map: dict[str, dict[str, list[dict]]],
    dte_targets: list[int],
) -> set[str]:
    """
    Select nearest available expiration keys for each target DTE.
    Filters out expired chains that Schwab caches overnight.
    """
    if not option_map:
        return set()

    parsed: list[tuple[str, date, int]] = []
    current_ny_date = _today_ny()
    
    for exp_key in option_map.keys():
        try:
            exp_date, dte = _parse_exp_key(exp_key)
            
            # ROBUSTNESS CHECK: Instantly drop expired chains
            if exp_date < current_ny_date:
                log.debug(f"Dropping expired chain from Schwab payload: {exp_key}")
                continue
                
            parsed.append((exp_key, exp_date, dte))
        except ValueError:
            log.debug("Could not parse expiry key: %s", exp_key)

    if not parsed:
        return set()

    selected: set[str] = set()
    for target in dte_targets:
        # Prefer nearest non-negative DTE first; fallback to absolute nearest.
        non_negative = [p for p in parsed if p[2] >= 0]
        pool = non_negative if non_negative else parsed
        # Use a default argument to bind `target` at loop time, avoiding
        # late-binding closure issues if this lambda is ever stored/deferred.
        best = min(pool, key=lambda p, t=target: (abs(p[2] - t), p[2], p[1]))
        selected.add(best[0])

    # Ensure at least one expiry exists even if targets are empty.
    if not selected:
        best = min(parsed, key=lambda p: (abs(p[2]), p[1]))
        selected.add(best[0])

    return selected


def _extract_contracts(
    option_map: dict[str, dict[str, list[dict]]],
    contract_type: str,
    selected_exp_keys: set[str],
) -> list[OptionContract]:
    """Flatten callExpDateMap/putExpDateMap for the selected expirations."""
    contracts: list[OptionContract] = []
    for exp_key, strikes in option_map.items():
        if exp_key not in selected_exp_keys:
            continue
        for _strike_key, contr_list in strikes.items():
            for raw in contr_list:
                parsed = _parse_contract(raw, contract_type)
                if parsed is not None:
                    contracts.append(parsed)
    return contracts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_client(
    secrets_path: Path = SECRETS_PATH,
    token_path: Path = TOKEN_PATH,
) -> Any:
    """
    NOTE: In the Hub-and-Spoke model, the Spoke does NOT need a full Client.
    It uses the Hub's REST proxy. This function now returns a 'Dummy' or 
    Proxy-aware object, or is bypassed by callers.
    """
    return None


def fetch_option_chain_data(
    client: Any,
    symbol: str,
    dte_targets: list[int],
) -> OptionChainData:
    """
    Pull the full option chain for *symbol*, retaining only expirations in
    *dte_targets* (e.g. [0, 1] for 0DTE and 1DTE).

    Parameters
    ----------
    client      : Authenticated Schwab client (from create_client()).
    symbol      : Human-readable ticker, e.g. "SPX", "NDX", "SPY", "QQQ".
    dte_targets : List of target DTE values (calendar days from today).

    Raises
    ------
    ValueError    : If dte_targets is empty.
    RuntimeError  : On HTTP error, rate-limit, or non-SUCCESS API response.
    """
    if not dte_targets:
        raise ValueError("dte_targets must not be empty.")

    api_sym = _schwab_symbol(symbol)
    
    today = _today_ny()
    # Query a wide enough window so weekend/overnight runs still return expiries.
    max_dte = max(dte_targets) + OPTION_CHAIN_WIDE_WINDOW

    params = {
        "symbol": api_sym,
        "from_date": today.isoformat(),
        "to_date": (today + timedelta(days=max_dte)).isoformat(),
        "include_underlying_quote": True,
    }
    
    payload = _hub_request("get_option_chain", params)
    status = payload.get("status")
    if status and status != "SUCCESS":
        raise RuntimeError(
            f"Option chain status='{status}' for {symbol} ({api_sym})"
        )

    # Extract spot price from nested underlying quote.
    # Use explicit None checks rather than truthiness so a genuine 0.0 value
    # (unlikely for equities/indices, but possible) isn't silently skipped.
    underlying = payload.get("underlying") or {}
    raw_spot = (
        underlying.get("mark")
        if underlying.get("mark") is not None
        else underlying.get("last")
        if underlying.get("last") is not None
        else payload.get("underlyingPrice")
    )
    spot: float = _safe_float(raw_spot)

    # Extract opening price for anchored basis translation
    spot_open = _safe_float(
        underlying.get("openPrice") 
        or underlying.get("sessionOpen") 
        or underlying.get("open") 
    )

    if spot == 0:
        log.warning("Spot price is zero for %s — levels may be inaccurate.", symbol)

    call_map_raw = payload.get("callExpDateMap", {})
    put_map_raw = payload.get("putExpDateMap", {})

    def _scrub_expired(raw_map: dict) -> dict:
        """Purge any options chain that is older than our logical trading day."""
        clean = {}
        logical_today = _today_ny()
        
        for exp_key, strikes in raw_map.items():
            try:
                date_str = exp_key.split(":")[0]
                exp_date = date.fromisoformat(date_str)
                
                # Only keep chains that expire ON or AFTER our logical trading day
                if exp_date >= logical_today:
                    clean[exp_key] = strikes
                else:
                    log.debug(f"Purging dead expired chain: {exp_key}")
            except Exception:
                clean[exp_key] = strikes 
        return clean
        
    # Sanitize the maps before the rest of the script sees them
    call_map = _scrub_expired(call_map_raw)
    put_map = _scrub_expired(put_map_raw)

    # Pick nearest available expirations from the cleaned maps
    exp_source_map = call_map if call_map else put_map
    selected_exp_keys = _select_expiration_keys(exp_source_map, dte_targets)

    # ---> NEW CODE TO EXTRACT TOS BLENDED VOLATILITY <---
    chain_vol = 0.0
    if selected_exp_keys:
        # Grab the nearest DTE key (the primary one we care about for the daily expected move)
        front_exp_key = sorted(list(selected_exp_keys))[0]
        
        # Schwab usually stores the blended IV in the first strike's array or right inside the date map.
        # It's an array of strike arrays, so we peek at the first strike available.
        if front_exp_key in exp_source_map:
            first_strike_data = next(iter(exp_source_map[front_exp_key].values()), [])
            if first_strike_data:
                # Extract the 'volatility' field (Schwab returns it as a percentage e.g. 29.5)
                chain_vol = _safe_float(first_strike_data[0].get("volatility", 0.0))
    # ---> END NEW CODE <---

    calls = _extract_contracts(call_map, "CALL", selected_exp_keys)
    puts  = _extract_contracts(put_map,  "PUT",  selected_exp_keys)

    log.info(
        "Option chain %s (%s): spot=%.2f  calls=%d  puts=%d  dte_targets=%s  selected_exp=%s",
        symbol, api_sym, spot, len(calls), len(puts), dte_targets, sorted(selected_exp_keys),
    )
    return OptionChainData(
        underlying_symbol=api_sym,
        spot_price=spot,
        spot_open=spot_open,
        chain_volatility=chain_vol,
        calls=calls,
        puts=puts,
    )


def fetch_futures_quote(
    symbol: str,
    token_path: Path = TOKEN_PATH,
) -> FuturesQuote | None:
    # 1. Fetch real-time price and globex open from Schwab Quotes API (fastest)
    price_sc, open_sc = _fetch_futures_from_schwab(symbol, token_path)

    # 2. Fetch un-delayed RTH open from Schwab Price History API
    #    (This avoids yfinance's 15min delay and Globex-vs-RTH mismatch)
    open_rth = _fetch_rth_open_from_schwab(symbol, token_path)
    
    # 3. Fallback to yfinance only if both Schwab calls fail
    if price_sc is None and open_rth is None:
        price_yf, open_yf = _fetch_futures_from_yfinance(symbol)
        final_price = price_yf
        final_open  = open_yf
        source_lbl = "yfinance"
    else:
        final_price = price_sc
        final_open  = open_rth if open_rth is not None else open_sc
        source_lbl = "schwab"

    if final_price is not None:
        log.info(
            "Futures quote %s: price=%.2f  open=%.2f  (source=%s)",
            symbol,
            final_price,
            final_open or 0.0,
            source_lbl
        )
        return FuturesQuote(symbol=symbol, price=final_price, open_price=final_open or 0.0)

    log.warning("Futures quote unavailable for %s from all sources.", symbol)
    return None


def _fetch_futures_from_schwab(symbol: str, token_path: Path) -> tuple[float | None, float | None]:
    """
    Hit the Hub Proxy for a futures quote.
    """
    try:
        data = _hub_request("get_quotes", {"symbols": [symbol]})
        key = next(iter(data.keys()), None)
        if key is None:
            return None, None

        quote = data[key].get("quote", {})
        price = _safe_float(
            quote.get("lastPrice")
            or quote.get("last")
            or quote.get("mark")
        )
        open_p = _safe_float(
            quote.get("openPrice")
            or quote.get("open")
        )
        return (price, open_p) if price > 0 else (None, None)
    except Exception as e:
        log.warning(f"Hub futures fetch failed for {symbol}: {e}")
        return None, None


def _fetch_rth_open_from_schwab(symbol: str, token_path: Path) -> float | None:
    """
    Fetch the 9:30 AM ET bar from Schwab Price History API via Hub.
    """
    try:
        params = {
            "symbol": symbol,
            "period_type": "day",
            "period": 1,
            "frequency_type": "minute",
            "frequency": 1,
            "need_extended_hours_data": True
        }
        data = _hub_request("get_price_history", params)
        candles = data.get("candles", [])
        if not candles:
            return None

        # RTH Open is the bar at 09:30 AM ET.
        ny_tz = ZoneInfo("America/New_York")
        now_ny = datetime.now(ny_tz)
        target_time = time(9, 30)
        
        for c in candles:
            dt = datetime.fromtimestamp(c["datetime"] / 1000, tz=ZoneInfo("UTC")).astimezone(ny_tz)
            if dt.time() == target_time and dt.date() == now_ny.date():
                return float(c["open"])
        
        return float(candles[0]["open"])

    except Exception as exc:
        log.debug("Hub price history fetch failed for %s: %s", symbol, exc)
        return None


def _fetch_futures_from_yfinance(symbol: str) -> tuple[float | None, float | None]:
    """
    Fetch a futures price and RTH open (9:30 AM) via yfinance.
    """
    if yf is None:
        return None, None

    yf_symbol = FUTURES_YF_MAP.get(symbol)
    if not yf_symbol:
        log.debug("No yfinance mapping for futures symbol %s", symbol)
        return None, None

    try:
        ticker = yf.Ticker(yf_symbol)
        # Fetch 1-day 1-min data to extract the precise RTH open bar
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            # Fall back to info 
            info = ticker.fast_info if hasattr(ticker, "fast_info") else {}
            last = info.get("lastPrice")
            open_p = info.get("openPrice")
            return (float(last) if last else None, float(open_p) if open_p else None)

        last = float(hist["Close"].iloc[-1])

        # Attempt to find the 9:30 AM ET bar to match SPX RTH open
        # (SPX does not have Globex, so anchored basis must use RTH open for both)
        try:
            hist.index = hist.index.tz_convert("America/New_York")
            rth_bars = hist.between_time("09:30", "09:30")
            if not rth_bars.empty:
                open_p = float(rth_bars["Open"].iloc[0])
                log.debug("Found RTH Open for %s at 09:30 NY: %.2f", symbol, open_p)
            else:
                # If 9:30 bar doesn't exist yet (pre-market), use session start (Globex)
                open_p = float(hist["Open"].iloc[0])
        except Exception:
            open_p = float(hist["Open"].iloc[0])

        return last, open_p
    except Exception as exc:
        log.warning("yfinance fallback failed for %s (%s): %s", symbol, yf_symbol, exc)
        return None, None