import asyncio
import time
import logging
from datetime import datetime
from typing import Any, Optional, Dict, List

from scripts.streaming.options.options_fetcher import (
    fetch_futures_quote,
    fetch_option_chain_data,
    OptionChainData,
    OptionContract,
    _hub_request,
    _safe_float
)
from scripts.streaming.options.config import SCHWAB_INDEX_PREFIX

logger = logging.getLogger(__name__)

class BrokerService:
    """
    Unified, cached, stateless Broker Service wrapping Schwab API feeds.
    Provides non-blocking async execution using asyncio.to_thread for underlying blocking REST requests.
    """
    def __init__(self, stock_ttl: float = 5.0, option_ttl: float = 10.0, chain_ttl: float = 30.0):
        self.stock_ttl = stock_ttl
        self.option_ttl = option_ttl
        self.chain_ttl = chain_ttl
        
        self._stock_quotes_cache: Dict[str, tuple] = {}
        self._option_quotes_cache: Dict[str, tuple] = {}
        self._option_chains_cache: Dict[tuple, tuple] = {}
        self._expiries_cache: Dict[str, tuple] = {}

    def clear_caches(self):
        """Clears all in-memory quote and option chain caches."""
        self._stock_quotes_cache.clear()
        self._option_quotes_cache.clear()
        self._option_chains_cache.clear()
        self._expiries_cache.clear()

    async def get_stock_quote(self, ticker: str) -> dict:
        """
        Gets the latest quote for a stock or future index.
        Returns:
            dict: {symbol, last, bid, ask, open, timestamp}
        """
        ticker = ticker.upper()
        now = time.time()
        
        # Check cache
        if ticker in self._stock_quotes_cache:
            quote, ts = self._stock_quotes_cache[ticker]
            if now - ts < self.stock_ttl:
                return quote

        # Handle futures quotes
        if ticker.startswith("/"):
            try:
                futures_quote = await asyncio.to_thread(fetch_futures_quote, ticker)
                if futures_quote and futures_quote.price is not None:
                    quote = {
                        "symbol": ticker,
                        "last": futures_quote.price,
                        "bid": futures_quote.price,
                        "ask": futures_quote.price,
                        "open": futures_quote.open_price or futures_quote.price,
                        "timestamp": now
                    }
                    self._stock_quotes_cache[ticker] = (quote, now)
                    return quote
            except Exception as e:
                logger.error(f"Error fetching futures quote for {ticker}: {e}")
                
        # Handle index or equity quotes
        api_sym = SCHWAB_INDEX_PREFIX.get(ticker, ticker)
        try:
            params = {"symbols": [api_sym]}
            # Make request via hub request in thread
            res = await asyncio.to_thread(_hub_request, "get_quotes", params)
            
            data = res.get(api_sym, {}) or res.get("data", {}).get(api_sym, {})
            q = data.get("quote", {})
            
            if q:
                last = _safe_float(q.get("lastPrice") or q.get("mark"))
                bid = _safe_float(q.get("bidPrice"))
                ask = _safe_float(q.get("askPrice"))
                open_p = _safe_float(q.get("openPrice") or q.get("sessionOpen") or last)
                
                quote = {
                    "symbol": ticker,
                    "last": last,
                    "bid": bid or last,
                    "ask": ask or last,
                    "open": open_p,
                    "timestamp": now
                }
                self._stock_quotes_cache[ticker] = (quote, now)
                return quote
            else:
                raise ValueError(f"No quote data returned for {api_sym}")
        except Exception as e:
            logger.error(f"Error fetching stock quote for {ticker} (api: {api_sym}): {e}")
            # Try fallback to last known cache if available, even if stale
            if ticker in self._stock_quotes_cache:
                return self._stock_quotes_cache[ticker][0]
            raise

    async def get_option_quote(self, symbol: str) -> dict:
        """
        Gets the latest quote for an option contract.
        Returns:
            dict: {symbol, last, bid, ask, mark, iv, delta, gamma, theta, vega, timestamp}
        """
        symbol = symbol.upper()
        now = time.time()
        
        # Check cache
        if symbol in self._option_quotes_cache:
            quote, ts = self._option_quotes_cache[symbol]
            if now - ts < self.option_ttl:
                return quote
                
        try:
            params = {"symbols": [symbol]}
            res = await asyncio.to_thread(_hub_request, "get_quotes", params)
            
            data = res.get(symbol, {}) or res.get("data", {}).get(symbol, {})
            q = data.get("quote", {})
            
            if q:
                last = _safe_float(q.get("lastPrice") or q.get("mark"))
                bid = _safe_float(q.get("bidPrice"))
                ask = _safe_float(q.get("askPrice"))
                mark = _safe_float(q.get("mark") or (bid + ask) / 2.0 or last)
                
                quote = {
                    "symbol": symbol,
                    "last": last,
                    "bid": bid or last,
                    "ask": ask or last,
                    "mark": mark,
                    "iv": _safe_float(q.get("volatility", 0.0)) / 100.0,
                    "delta": _safe_float(q.get("delta")),
                    "gamma": _safe_float(q.get("gamma")),
                    "theta": _safe_float(q.get("theta")),
                    "vega": _safe_float(q.get("vega")),
                    "timestamp": now
                }
                self._option_quotes_cache[symbol] = (quote, now)
                return quote
            else:
                raise ValueError(f"No option quote data returned for {symbol}")
        except Exception as e:
            logger.error(f"Error fetching option quote for {symbol}: {e}")
            if symbol in self._option_quotes_cache:
                return self._option_quotes_cache[symbol][0]
            raise

    async def get_chain(self, ticker: str, dte_targets: list[int]) -> OptionChainData:
        """
        Gets the option chain for a ticker matching target DTEs.
        Returns:
            OptionChainData
        """
        ticker = ticker.upper()
        now = time.time()
        
        # Cache key based on ticker and sorted dte_targets
        cache_key = (ticker, tuple(sorted(dte_targets)))
        
        if cache_key in self._option_chains_cache:
            chain, ts = self._option_chains_cache[cache_key]
            if now - ts < self.chain_ttl:
                return chain
                
        try:
            # fetch_option_chain_data handles paging, date chunks, and underlying quote extraction
            chain = await asyncio.to_thread(fetch_option_chain_data, None, ticker, dte_targets)
            
            # If spot price in returned chain is 0, we fall back to our stock quote
            if chain.spot == 0.0 or chain.spot_price == 0.0:
                try:
                    sq = await self.get_stock_quote(ticker)
                    chain.spot = sq["last"]
                    chain.spot_price = sq["last"]
                    if chain.spot_open == 0.0:
                        chain.spot_open = sq["open"]
                except Exception as sq_err:
                    logger.warning(f"Could not fill zero spot price for {ticker}: {sq_err}")
            
            self._option_chains_cache[cache_key] = (chain, now)
            return chain
        except Exception as e:
            logger.error(f"Error fetching option chain for {ticker} (DTE {dte_targets}): {e}")
            if cache_key in self._option_chains_cache:
                return self._option_chains_cache[cache_key][0]
            raise

    async def get_expiries(self, ticker: str) -> list[str]:
        """
        Gets all available expiration dates for a ticker.
        Returns:
            list[str]: Expirations in "YYYY-MM-DD" format
        """
        ticker = ticker.upper()
        now = time.time()
        
        if ticker in self._expiries_cache:
            expiries, ts = self._expiries_cache[ticker]
            if now - ts < 300.0: # Expiries change very slowly, 5 mins TTL is extremely safe
                return expiries
                
        try:
            api_sym = SCHWAB_INDEX_PREFIX.get(ticker, ticker)
            params = {
                "symbol": api_sym,
                "strikeCount": 1
            }
            payload = await asyncio.to_thread(_hub_request, "get_option_chain", params)
            call_map = payload.get("callExpDateMap", {}) or {}
            put_map = payload.get("putExpDateMap", {}) or {}
            
            all_exp_keys = sorted(set(call_map.keys()) | set(put_map.keys()))
            expiries = []
            for k in all_exp_keys:
                parts = k.split(":")
                if parts:
                    expiries.append(parts[0])
                    
            self._expiries_cache[ticker] = (expiries, now)
            return expiries
        except Exception as e:
            logger.error(f"Error fetching expiries for {ticker}: {e}")
            if ticker in self._expiries_cache:
                return self._expiries_cache[ticker][0]
            raise

    def find_strike_by_delta(self, chain: OptionChainData, target_delta: float, contract_type: str = "CALL") -> OptionContract | None:
        """
        Finds the contract in the chain closest to the target delta.
        Handles negative PUT deltas transparently.
        """
        contracts = chain.calls if contract_type.upper() == "CALL" else chain.puts
        if not contracts:
            return None
        
        target_abs = abs(target_delta)
        best_c = min(contracts, key=lambda c: abs(abs(c.delta) - target_abs))
        return best_c

    def find_strike_nearest(self, chain: OptionChainData, target_strike: float, contract_type: str = "CALL") -> OptionContract | None:
        """
        Finds the contract in the chain closest to the target strike price.
        """
        contracts = chain.calls if contract_type.upper() == "CALL" else chain.puts
        if not contracts:
            return None
            
        best_c = min(contracts, key=lambda c: abs(c.strike - target_strike))
        return best_c
