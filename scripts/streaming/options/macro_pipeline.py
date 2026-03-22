"""
macro_pipeline.py
=================
Weekend macro pipeline for institutional HTF analysis.
Implements Task 1: "Cache & Cascade" strategy.
"""
from __future__ import annotations

import json
import logging
import os
import requests
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import yfinance as yf
except ImportError:
    yf = None

from .options_fetcher import (
    OptionChainData, 
    OptionContract, 
    fetch_option_chain_data, 
    create_client,
    _today_ny,
    _safe_float,
    fetch_futures_quote
)
from .config import DATA_DIR, MACRO_DTE_TARGETS, MACRO_LEVELS_TXT, INDEX_TO_FUTURES, USE_OPENING_BASIS
from .formatting import futures_tag
from .whale_detector import detect_volume_anomalies
from .macro_charting import generate_macro_chart_bytes
from .discord_notifier import send_macro_update
from .interval_writer import write_macro_snapshot
from .file_writer import write_macro_levels, write_quant_json
from .gex_calculator import calculate_dealer_levels, extract_dominant_oi_nodes

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caching / Serialisation logic
# ---------------------------------------------------------------------------

def _serialize_chain(chain: OptionChainData) -> dict[str, Any]:
    """Convert OptionChainData dataclass to a JSON-serializable dict."""
    return {
        "underlying_symbol": chain.underlying_symbol,
        "spot_price": chain.spot_price,
        "spot_open": chain.spot_open,
        "chain_volatility": chain.chain_volatility,
        "calls": [vars(c) for c in chain.calls],
        "puts": [vars(p) for p in chain.puts]
    }

def _deserialize_chain(data: dict[str, Any]) -> OptionChainData:
    """Convert a dict back into an OptionChainData dataclass."""
    # Convert string dates back to date objects if they were strings
    for call in data["calls"]:
        if isinstance(call["expiry"], str):
            call["expiry"] = date.fromisoformat(call["expiry"])
    for put in data["puts"]:
        if isinstance(put["expiry"], str):
            put["expiry"] = date.fromisoformat(put["expiry"])

    return OptionChainData(
        underlying_symbol=data["underlying_symbol"],
        spot_price=data["spot_price"],
        spot_open=data["spot_open"],
        chain_volatility=data.get("chain_volatility", 0.0),
        calls=[OptionContract(**c) for c in data["calls"]],
        puts=[OptionContract(**p) for p in data["puts"]]
    )

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

# ---------------------------------------------------------------------------
# yfinance Fallback Implementation
# ---------------------------------------------------------------------------

def _fetch_from_yfinance(ticker: str) -> OptionChainData | None:
    """Pull the full option chain via yfinance as a fallback."""
    if yf is None:
        log.warning("yfinance not installed — fallback unavailable.")
        return None

    log.info("Attempting yfinance fallback for %s...", ticker)
    try:
        yf_ticker = f"^{ticker}" if ticker in ("SPX", "NDX", "DJX", "RUT", "VIX") else ticker
        yft = yf.Ticker(yf_ticker)
        # yf.Ticker.options returns a list of expiration dates
        expiries = yft.options
        if not expiries:
            log.warning("yfinance returned no options for %s", ticker)
            return None

        spot = yft.fast_info.get("lastPrice", 0.0)
        spot_open = yft.fast_info.get("openPrice", 0.0)
        
        calls: list[OptionContract] = []
        puts: list[OptionContract] = []
        today = _today_ny()

        for exp in expiries:
            chain = yft.option_chain(exp)
            exp_date = date.fromisoformat(exp)
            dte = (exp_date - today).days
            
            # Map yfinance DataFrame to OptionContract
            for _, row in chain.calls.iterrows():
                calls.append(_parse_yf_contract(row, exp_date, dte, "CALL"))
            for _, row in chain.puts.iterrows():
                puts.append(_parse_yf_contract(row, exp_date, dte, "PUT"))

        return OptionChainData(
            underlying_symbol=ticker,
            spot_price=spot,
            spot_open=spot_open,
            calls=calls,
            puts=puts
        )
    except Exception as e:
        log.error("yfinance fetch failed: %s", e)
        return None

def _parse_yf_contract(row: Any, expiry: date, dte: int, contract_type: str) -> OptionContract:
    # yfinance greeks are often missing or in 'impliedVolatility'
    # Fallback to 0.0 for higher order greeks if not present
    
    def _safe_int(val: Any) -> int:
        try:
            if val is None or (isinstance(val, float) and (val != val or val == float('inf'))):
                return 0
            return int(val)
        except (ValueError, TypeError):
            return 0

    return OptionContract(
        symbol=str(row.get("contractSymbol", "")),
        strike=float(row.get("strike", 0.0)),
        expiry=expiry,
        contract_type=contract_type,
        open_interest=_safe_int(row.get("openInterest")),
        volume=_safe_int(row.get("volume")),
        mark=(float(row.get("bid", 0.0)) + float(row.get("ask", 0.0))) / 2.0,
        bid=float(row.get("bid", 0.0)),
        ask=float(row.get("ask", 0.0)),
        iv=float(row.get("impliedVolatility", 0.0)),
        delta=0.0, # yfinance doesn't provide these directly in the chain DF reliably
        gamma=0.0,
        theta=0.0,
        vega=0.0,
        rho=0.0,
        dte=dte
    )

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_macro_data(ticker: str, force_refresh: bool = False) -> OptionChainData | None:
    """
    Implements Task 1: Cache & Cascade.
    1. Check Local Cache
    2. Primary Fetch (Schwab)
    3. Fallback (yfinance)
    """
    cache_file = DATA_DIR / f"macro_cache_{ticker.upper()}_{date.today().isoformat()}.json"
    
    # 1. Local Cache First
    if cache_file.exists() and not force_refresh:
        log.info("Loading %s from local cache...", ticker)
        try:
            return _deserialize_chain(json.loads(cache_file.read_text()))
        except Exception as e:
            log.warning("Failed to load cache: %s", e)

    # 2. Primary Fetch (Schwab)
    log.info("Starting primary fetch for %s (Schwab)...", ticker)
    try:
        client = create_client()
        # For macro HTF, we use the targets defined in config
        chain = fetch_option_chain_data(client, ticker, MACRO_DTE_TARGETS)
        
        # Save to cache
        cache_file.write_text(json.dumps(_serialize_chain(chain), cls=DateEncoder, indent=2))
        return chain
    except Exception as e:
        log.warning("Schwab fetch failed/limited: %s", e)

    # 3. Fallback (yfinance)
    chain = _fetch_from_yfinance(ticker)
    if chain:
        # Save to cache if fallback succeeded
        cache_file.write_text(json.dumps(_serialize_chain(chain), cls=DateEncoder, indent=2))
        return chain

    return None

def run_macro_pipeline(tickers: list[str], force_refresh: bool = False) -> None:
    """
    Main entry point for the Weekly Macro HTF Module.
    Runs everything from data fetch to UI push.
    """
    log.info("Starting Weekly Macro HTF Pipeline for %s", tickers)
    path: Path = MACRO_LEVELS_TXT
    if path.exists(): 
        path.unlink()
    
    for ticker in tickers:
        try:
            # 1. Fetch Data (Cache & Cascade)
            chain = fetch_macro_data(ticker, force_refresh=force_refresh)
            if not chain:
                log.error("No data for %s, skipping.", ticker)
                continue
            
            # 2. Institutional Macro Calculations
            # We use the existing GEX calculator but on the HTF chain
            log.info("Calculating Macro HTF levels for %s...", ticker)
            dl = calculate_dealer_levels(chain, ticker)
            
            macro_levels = {
                "macro_call_wall": dl.call_wall,
                "macro_put_wall": dl.put_wall,
                "zero_gamma": dl.zero_gamma,
                "put_25d_iv": dl.put_25d_iv,
                "call_25d_iv": dl.call_25d_iv,
                "volatility_skew_premium": dl.volatility_skew_premium,
                "strikes_oi": [
                    {"strike": sg.strike, "call_oi": sg.call_oi, "put_oi": sg.put_oi}
                    for sg in dl.strike_gex
                ]
            }

            # 3. Pillar 1: Whale Detection
            anomalies = detect_volume_anomalies(chain, ticker)
            total_anomalies = len(anomalies.get("structural", [])) + len(anomalies.get("tactical", []))
            log.info("Detected %d whale anomalies for %s", total_anomalies, ticker)

            # NEW: Structural Nodes (The Map)
            dominant_nodes = extract_dominant_oi_nodes(chain)

            # --- TRANSLATE TO FUTURES SPACE ---
            futures_sym = INDEX_TO_FUTURES.get(ticker)
            output_ticker = ticker
            
            if futures_sym:
                fut = fetch_futures_quote(futures_sym)
                if fut:
                    base_open = chain.spot_open
                    anchor_basis = 0.0
                    anchor_ratio = 1.0
                    
                    if USE_OPENING_BASIS and fut.open_price > 0 and base_open > 0:
                        anchor_basis = round(fut.open_price - base_open, 2)
                        anchor_ratio = round(fut.open_price / base_open, 4)
                        
                    mode = "additive"
                    if fut.price > 0 and chain.spot_price > 0:
                        if (fut.price / chain.spot_price) > 2.0:
                            mode = "multiplicative"

                    log.info("Translating %s macro levels to %s (mode: %s, basis: %.2f, ratio: %.4f)", ticker, futures_sym, mode, anchor_basis, anchor_ratio)
                    
                    import copy
                    fut_macro_levels = copy.deepcopy(macro_levels)
                    fut_anomalies = copy.deepcopy(anomalies)
                    fut_dominant_nodes = copy.deepcopy(dominant_nodes) # Explicit Copy
                    
                    if mode == "multiplicative" and anchor_ratio > 0:
                        for k, v in fut_macro_levels.items():
                            if k in ["macro_call_wall", "macro_put_wall", "zero_gamma"] and v is not None:
                                fut_macro_levels[k] = round(v * anchor_ratio, 2)
                        for sg in fut_macro_levels.get("strikes_oi", []):
                            sg["strike"] = round(sg["strike"] * anchor_ratio, 2)
                        for node in fut_dominant_nodes: # Explicit Scaling
                            node["strike"] = round(node["strike"] * anchor_ratio, 2)
                        # Update BOTH buckets in the anomalies dict
                        for bucket in ["structural", "tactical"]:
                            for w in fut_anomalies.get(bucket, []):
                                w["strike"] = round(w["strike"] * anchor_ratio, 2)
                                
                    elif mode == "additive" and anchor_basis != 0:
                        for k, v in fut_macro_levels.items():
                            if k in ["macro_call_wall", "macro_put_wall", "zero_gamma"] and v is not None:
                                fut_macro_levels[k] = round(v + anchor_basis, 2)
                        for sg in fut_macro_levels.get("strikes_oi", []):
                            sg["strike"] = round(sg["strike"] + anchor_basis, 2)
                        for node in fut_dominant_nodes: # Explicit Scaling
                            node["strike"] = round(node["strike"] + anchor_basis, 2)
                        # Update BOTH buckets in the anomalies dict
                        for bucket in ["structural", "tactical"]:
                            for w in fut_anomalies.get(bucket, []):
                                w["strike"] = round(w["strike"] + anchor_basis, 2)
                            
                    output_ticker = futures_tag(futures_sym)
                    
                    # Pass all 5 arguments cleanly for Futures!
                    write_macro_levels(output_ticker, fut_macro_levels, fut_anomalies, fut_dominant_nodes)
                    write_quant_json(output_ticker, fut.price, fut_macro_levels, fut_anomalies, fut_dominant_nodes)
                    write_macro_snapshot(output_ticker, fut.price, fut_macro_levels, fut_anomalies, fut_dominant_nodes)

            # 4. Pillar 3: Charting
            chart_buf = generate_macro_chart_bytes(ticker, float(chain.spot_price), macro_levels, anomalies["structural"])
            
            # 5. Delivery Pillar 2: Discord Update
            if chart_buf.getbuffer().nbytes > 0:
                # Explicitly pass spot price and dominant_nodes
                send_macro_update(ticker, float(chain.spot_price), chart_buf, macro_levels, anomalies["structural"], dominant_nodes)
                chart_buf.seek(0)
            
            # 6. Delivery Pillar 4: Next.js UI Push
            write_macro_snapshot(ticker, float(chain.spot_price), macro_levels, anomalies, dominant_nodes)

            # 7. Delivery Pillar 5: Pine Script Text Append
            write_macro_levels(ticker, macro_levels, anomalies, dominant_nodes)
            
            # 8. Delivery Pillar 6: Quant JSON Output
            write_quant_json(ticker, float(chain.spot_price), macro_levels, anomalies, dominant_nodes)
            
            log.info("Macro HTF Pipeline completed for %s", ticker)

        except Exception as e:
            log.exception("Error in Macro Pipeline for %s: %s", ticker, e)