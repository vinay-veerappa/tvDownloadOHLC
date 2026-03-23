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

from scripts.streaming.options.options_fetcher import (
    OptionChainData, 
    OptionContract, 
    fetch_option_chain_data, 
    fetch_futures_option_chain_data, # NEW
    create_client,
    _today_ny,
    _safe_float,
    fetch_futures_quote
)
from scripts.streaming.options.config import DATA_DIR, MACRO_DTE_TARGETS, MACRO_LEVELS_TXT, INDEX_TO_FUTURES, USE_OPENING_BASIS, FUTURES_YF_MAP
from scripts.streaming.options.formatting import futures_tag
from scripts.streaming.options.whale_detector import detect_volume_anomalies
from scripts.streaming.options.macro_charting import generate_macro_chart_bytes
from scripts.streaming.options.discord_notifier import send_macro_update
from scripts.streaming.options.interval_writer import write_macro_snapshot
from scripts.streaming.options.file_writer import write_macro_levels, write_quant_json
from scripts.streaming.options.gex_calculator import calculate_dealer_levels, extract_dominant_oi_nodes

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
        if ticker.startswith('/'):
            yf_ticker = FUTURES_YF_MAP.get(ticker, ticker)
        else:
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
            try:
                chain = yft.option_chain(exp)
                exp_date = date.fromisoformat(exp)
                dte = (exp_date - today).days
                
                # Map yfinance DataFrame to OptionContract
                for _, row in chain.calls.iterrows():
                    calls.append(_parse_yf_contract(row, exp_date, dte, "CALL"))
                for _, row in chain.puts.iterrows():
                    puts.append(_parse_yf_contract(row, exp_date, dte, "PUT"))
            except Exception as e:
                log.warning("Failed to fetch expiry %s for %s: %s", exp, ticker, e)
                continue

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

def fetch_macro_data(ticker: str, force_refresh: bool = False, resolved_sym: str = None) -> OptionChainData | None:
    """
    Implements Task 1: Cache & Cascade.
    1. Check Local Cache (using root ticker)
    2. Primary Fetch (Schwab) using resolved_sym
    3. Fallback (yfinance) using root ticker
    """
    cache_ticker = ticker # Use root for cache name consistency
    today_str = date.today().isoformat()
    # Check for existing cache files for today (can be multiple if different suffixes)
    cache_file = DATA_DIR / f"macro_cache_{cache_ticker.upper().replace('/', '')}_{today_str}.json"
    
    # 1. Local Cache First
    if cache_file.exists() and not force_refresh:
        log.info("Loading %s from local cache...", cache_ticker)
        try:
            return _deserialize_chain(json.loads(cache_file.read_text()))
        except Exception as e:
            log.warning("Failed to load cache: %s", e)

    # 2. Primary Fetch (Schwab)
    fetch_sym = resolved_sym or ticker
    log.info("Starting primary fetch for %s (resolved: %s) (Schwab)...", ticker, fetch_sym)
    try:
        # Check if this is a futures symbol for Direct [D] mode
        if ticker.startswith('/'):
            log.info("Detected futures symbol. Using specialized direct fetcher for %s", ticker)
            chain = fetch_futures_option_chain_data(ticker, MACRO_DTE_TARGETS)
        else:
            client = create_client()
            chain = fetch_option_chain_data(client, fetch_sym, MACRO_DTE_TARGETS)
        
        # Save to cache
        cache_file.write_text(json.dumps(_serialize_chain(chain), cls=DateEncoder, indent=2))
        return chain
    except Exception as e:
        log.warning("Schwab fetch failed/limited for %s: %s", fetch_sym, e)
        
    # 3. Fallback (yfinance) using the root ticker
    chain = _fetch_from_yfinance(ticker)
    if chain:
        # Save to cache if fallback succeeded
        cache_file.write_text(json.dumps(_serialize_chain(chain), cls=DateEncoder, indent=2))
    return chain

def run_macro_pipeline(tickers: list[str], force_refresh: bool = False) -> None:
    """
    Main entry point for the Weekly Macro HTF Module.
    Runs everything from data fetch to UI push.
    """
    log.info("Starting Weekly Macro HTF Pipeline for %s", tickers)
    path: Path = MACRO_LEVELS_TXT
    if path.exists(): 
        path.unlink()
        
    # Resolve all tickers via hub to get dual mapping metadata
    try:
        hub_url = "http://127.0.0.1:8080/resolve"
        resp = requests.post(hub_url, json={"symbols": tickers})
        if resp.status_code == 200:
            resolution_data = resp.json().get("data", {})
        else:
            log.warning("Hub resolution failed, using defaults.")
            resolution_data = {}
    except Exception as e:
        log.warning(f"Could not connect to Hub for resolution: {e}")
        resolution_data = {}
    
    for ticker in tickers:
        try:
            res_info = resolution_data.get(ticker, {
                "direct": ticker, 
                "mapped": INDEX_TO_FUTURES.get(ticker, ticker),
                "active": ticker
            })

            # 1. Primary Variant Processing
            # ----------------------------
            chain = None
            resolved_info = res_info.get("active", ticker)
            # Handle cases where res_info might be the nested dict instead of the resolved string
            resolved_sym = resolved_info if isinstance(resolved_info, str) else resolved_info.get("active", ticker)
            
            log.info("Processing primary variant for %s (resolved: %s)...", ticker, resolved_sym)
            chain = fetch_macro_data(ticker, force_refresh=force_refresh, resolved_sym=resolved_sym)
            
            if chain:
                # Institutional Macro Calculations
                chain.underlying_symbol = ticker
                dl = calculate_dealer_levels(chain, ticker)
                
                macro_levels = {
                    "macro_call_wall": dl.call_wall,
                    "macro_put_wall": dl.put_wall,
                    "zero_gamma": dl.zero_gamma,
                    "put_25d_iv": dl.put_25d_iv,
                    "call_25d_iv": dl.call_25d_iv,
                    "volatility_skew_premium": dl.volatility_skew_premium,
                    "strikes_oi": [{"strike": sg.strike, "call_oi": sg.call_oi, "put_oi": sg.put_oi} for sg in dl.strike_gex]
                }
                anomalies = detect_volume_anomalies(chain, ticker)
                dominant_nodes = extract_dominant_oi_nodes(chain)

                output_tag = f"{ticker}[D]" if ticker.startswith('/') else ticker
                log.info("Saving primary results for %s as %s", ticker, output_tag)
                write_macro_levels(output_tag, macro_levels, anomalies, dominant_nodes)
                write_quant_json(output_tag, float(chain.spot_price), macro_levels, anomalies, dominant_nodes)
                write_macro_snapshot(output_tag, float(chain.spot_price), macro_levels, anomalies, dominant_nodes)

                # Charting & Discord (Primary only)
                chart_buf = generate_macro_chart_bytes(ticker, float(chain.spot_price), macro_levels, anomalies["structural"])
                if chart_buf.getbuffer().nbytes > 0:
                    send_macro_update(ticker, float(chain.spot_price), chart_buf, macro_levels, anomalies["structural"], dominant_nodes)
                    chart_buf.seek(0)
            else:
                log.warning("No primary data fetched for %s, skipping primary processing.", ticker)

            # 2. Mapped Variant Processing (Comparison)
            # ----------------------------------------
            mapped_ticker = None
            target_tag = None
            fetch_sym = None
            
            if ticker.startswith('/'):
                # Future -> Index (Reverse)
                mapped_ticker = res_info.get("mapped")
                target_tag = f"{ticker}[M]"
                fetch_sym = mapped_ticker
            else:
                # Index -> Future (Forward)
                mapped_ticker = INDEX_TO_FUTURES.get(ticker)
                target_tag = f"{mapped_ticker}[M]"
                fetch_sym = ticker # Reuse current chain if possible

            if mapped_ticker and target_tag:
                log.info("Processing mapped variant for %s -> %s (fetch: %s)...", ticker, target_tag, fetch_sym)
                m_chain = chain if (fetch_sym == ticker and chain) else fetch_macro_data(fetch_sym, force_refresh=force_refresh)
                
                if m_chain:
                    fut_root = mapped_ticker if mapped_ticker.startswith('/') else INDEX_TO_FUTURES.get(mapped_ticker, ticker)
                    fut = fetch_futures_quote(fut_root)
                    
                    if fut:
                        m_dl = calculate_dealer_levels(m_chain, fetch_sym)
                        m_levels = {
                            "macro_call_wall": m_dl.call_wall,
                            "macro_put_wall": m_dl.put_wall,
                            "zero_gamma": m_dl.zero_gamma,
                            "put_25d_iv": m_dl.put_25d_iv,
                            "call_25d_iv": m_dl.call_25d_iv,
                            "volatility_skew_premium": m_dl.volatility_skew_premium,
                            "strikes_oi": [{"strike": sg.strike, "call_oi": sg.call_oi, "put_oi": sg.put_oi} for sg in m_dl.strike_gex]
                        }
                        m_anomalies = detect_volume_anomalies(m_chain, fetch_sym)
                        m_nodes = extract_dominant_oi_nodes(m_chain)

                        # Basis Translation
                        spot_ratio = round(fut.price / m_chain.spot_price, 4) if m_chain.spot_price > 0 else 1.0
                        spot_basis = round(fut.price - m_chain.spot_price, 2)
                        
                        # Decide on translation mode
                        mode = "multiplicative" if spot_ratio > 2.0 or spot_ratio < 0.5 else "additive"
                        
                        # Preferred basis (Opening if available and configured)
                        anchor_basis = round(fut.open_price - m_chain.spot_open, 2) if (USE_OPENING_BASIS and fut.open_price > 0 and m_chain.spot_open > 0) else spot_basis
                        anchor_ratio = round(fut.open_price / m_chain.spot_open, 4) if (USE_OPENING_BASIS and fut.open_price > 0 and m_chain.spot_open > 0) else spot_ratio

                        log.info("Translation for %s: mode=%s, ratio=%.4f, basis=%.2f", target_tag, mode, anchor_ratio, anchor_basis)

                        import copy
                        f_l, f_a, f_n = copy.deepcopy(m_levels), copy.deepcopy(m_anomalies), copy.deepcopy(m_nodes)

                        if mode == "multiplicative":
                            for k in ["macro_call_wall", "macro_put_wall", "zero_gamma"]:
                                if f_l.get(k): f_l[k] = round(f_l[k] * anchor_ratio, 2)
                            for sg in f_l.get("strikes_oi", []): 
                                sg["strike"] = round(sg["strike"] * anchor_ratio, 2)
                            for node in f_n: 
                                node["strike"] = round(node["strike"] * anchor_ratio, 2)
                            for bucket in ["structural", "tactical"]:
                                for w in f_a.get(bucket, []): 
                                    w["strike"] = round(w["strike"] * anchor_ratio, 2)
                        else:
                            for k in ["macro_call_wall", "macro_put_wall", "zero_gamma"]:
                                if f_l.get(k): f_l[k] = round(f_l[k] + anchor_basis, 2)
                            for sg in f_l.get("strikes_oi", []): 
                                sg["strike"] = round(sg["strike"] + anchor_basis, 2)
                            for node in f_n: 
                                node["strike"] = round(node["strike"] + anchor_basis, 2)
                            for bucket in ["structural", "tactical"]:
                                for w in f_a.get(bucket, []): 
                                    w["strike"] = round(w["strike"] + anchor_basis, 2)

                        write_macro_levels(target_tag, f_l, f_a, f_n)
                        write_quant_json(target_tag, fut.price, f_l, f_a, f_n)
                        write_macro_snapshot(target_tag, fut.price, f_l, f_a, f_n)

            log.info("Macro HTF Pipeline completed for %s", ticker)

        except Exception as e:
            log.exception("Error in Macro Pipeline for %s: %s", ticker, e)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Macro HTF Options Pipeline")
    parser.add_argument("tickers", nargs="*", default=["SPX", "QQQ"], help="Tickers to process")
    parser.add_argument("--force-refresh", action="store_true", help="Force a fresh data fetch")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    run_macro_pipeline(args.tickers, force_refresh=args.force_refresh)
