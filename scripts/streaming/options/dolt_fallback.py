"""
dolt_fallback.py
================
Robust EOD option chain and spot price retrieval from the local Dolt options database.
Provides a high-quality, high-precision fallback for weekend/macro sweeps and trade settlement.
"""

import os
import sys
import json
import logging
import subprocess
from datetime import date, datetime, timedelta
from typing import Optional, Any


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

from scripts.streaming.options.options_fetcher import OptionChainData, OptionContract

log = logging.getLogger(__name__)

# Base Paths
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
DOLT_DIR = os.path.join(WORKSPACE_DIR, "data", "options", "options")
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")

def get_dolt_dir() -> str:
    """Returns verified path to Dolt options repository."""
    return DOLT_DIR

def fetch_historical_spot_local(ticker: str, target_date: date) -> Optional[float]:
    """Retrieve historical spot EOD close price from local daily parquet if available."""
    try:
        import pandas as pd
        parquet_path = os.path.join(DATA_DIR, f"{ticker.upper()}_1d.parquet")
        if os.path.exists(parquet_path):
            df = pd.read_parquet(parquet_path)
            # Standardize index to date objects
            if hasattr(df.index, 'date'):
                df.index = df.index.date
            
            if target_date in df.index:
                close_val = float(df.loc[target_date, "close"])
                log.info("[SPOT] Found precise spot price in local Parquet for %s on %s: %s", ticker, target_date, close_val)
                return close_val
    except Exception as e:
        log.warning("[SPOT] Local Parquet lookup failed for %s on %s: %s", ticker, target_date, e)
    return None

def fetch_historical_spot_yfinance(ticker: str, target_date: date) -> Optional[float]:
    """Retrieve historical spot EOD close price from yfinance as secondary fallback."""
    try:
        import yfinance as yf
        ticker_yf = f"^{ticker}" if ticker in ("SPX", "NDX", "DJX", "RUT", "VIX") else ticker
        t = yf.Ticker(ticker_yf)
        start_str = target_date.strftime("%Y-%m-%d")
        
        # Pull a small 4-day window to catch weekend expiries or holiday EOD data safely
        end_date = target_date + timedelta(days=4)
        end_str = end_date.strftime("%Y-%m-%d")
        
        df = t.history(start=start_str, end=end_str)
        if not df.empty:
            # Match exact date first
            for dt, row in df.iterrows():
                if dt.date() == target_date:
                    close_val = float(row["Close"])
                    log.info("[SPOT] Fetched precise spot price from yfinance for %s on %s: %s", ticker, target_date, close_val)
                    return close_val
            
            # If not exact, grab the first available row in the target direction
            close_val = float(df["Close"].iloc[0])
            log.info("[SPOT] Fetched nearest spot price from yfinance for %s close to %s: %s", ticker, target_date, close_val)
            return close_val
    except Exception as e:
        log.warning("[SPOT] yfinance spot lookup failed for %s on %s: %s", ticker, target_date, e)
    return None

def estimate_spot_via_parity(contracts: list[OptionContract]) -> float:
    """Fallback method: Estimate EOD spot price from options using Put-Call Parity (S = C - P + K)."""
    # Group contracts by (expiry, strike)
    expiry_groups = {}
    for c in contracts:
        key = (c.expiry, c.strike)
        if key not in expiry_groups:
            expiry_groups[key] = {}
        expiry_groups[key][c.contract_type] = c
    
    estimates = []
    for (exp, strike), types in expiry_groups.items():
        if "CALL" in types and "PUT" in types:
            call = types["CALL"]
            put = types["PUT"]
            # Estimate: S = C - P + K
            call_mid = (call.bid + call.ask) / 2.0 if call.bid and call.ask else call.last
            put_mid = (put.bid + put.ask) / 2.0 if put.bid and put.ask else put.last
            
            # Only use options with liquid bids/asks
            if call.bid > 0 and put.bid > 0:
                s_est = call_mid - put_mid + strike
                estimates.append(s_est)
                
    if estimates:
        estimates.sort()
        # Return median estimate to filter out outliers
        est_val = estimates[len(estimates) // 2]
        log.info("[SPOT] Estimated spot price via Put-Call parity median: %.2f (from %d liquid strikes)", est_val, len(estimates))
        return est_val
    return 0.0

def fetch_from_dolt(ticker: str, target_date_str: str = None) -> Optional[OptionChainData]:
    """
    Queries Dolt options EOD database for the target_date (or latest date available if target_date is None).
    Reconstructs OptionChainData using the tiered spot price hierarchy.
    """
    if not os.path.exists(DOLT_DIR):
        log.warning("[DOLT] Database directory not found at: %s", DOLT_DIR)
        return None
        
    log.info("[DOLT] Resolving latest available options date in Dolt for %s...", ticker)
    
    # Standardize ticker formatting for Dolt (root ticker)
    ticker_clean = ticker.upper().replace('/', '')
    
    # 1. Query volatility_history for max(date) — extremely fast
    cmd_max_date = [
        "dolt", "sql", 
        "-q", f"select max(date) as max_date from volatility_history where act_symbol = '{ticker_clean}'",
        "-r", "json"
    ]
    try:
        res = subprocess.run(cmd_max_date, cwd=DOLT_DIR, capture_output=True, text=True)
        if res.returncode != 0:
            log.warning("[DOLT] Max date query failed: %s", res.stderr.strip())
            return None
        
        data = json.loads(res.stdout)
        rows = data.get("rows", [])
        if not rows or not rows[0].get("max_date"):
            log.warning("[DOLT] No historical volatility dates found for %s", ticker_clean)
            return None
            
        latest_date_str = rows[0]["max_date"]
        log.info("[DOLT] Latest available EOD date for %s in Dolt is: %s", ticker_clean, latest_date_str)
        
        # Decide target query date
        query_date_str = target_date_str if target_date_str else latest_date_str
        query_date = datetime.strptime(query_date_str, "%Y-%m-%d").date()
        
        # 2. Query option_chain for the target date
        log.info("[DOLT] Querying options chain for %s on %s...", ticker_clean, query_date_str)
        cmd_chain = [
            "dolt", "sql",
            "-q", f"select * from option_chain where date = '{query_date_str}' and act_symbol = '{ticker_clean}'",
            "-r", "json"
        ]
        
        res_chain = subprocess.run(cmd_chain, cwd=DOLT_DIR, capture_output=True, text=True)
        if res_chain.returncode != 0:
            log.warning("[DOLT] Options chain query failed: %s", res_chain.stderr.strip())
            return None
            
        chain_data = json.loads(res_chain.stdout)
        db_rows = chain_data.get("rows", [])
        if not db_rows:
            log.warning("[DOLT] No options chain rows returned for %s on %s", ticker_clean, query_date_str)
            return None
            
        log.info("[DOLT] Successfully loaded %d option contracts from Dolt DB.", len(db_rows))
        
        contracts = []
        for row in db_rows:
            strike_val = float(row["strike"])
            call_put = row["call_put"].upper()
            expiry_str = row["expiration"]
            exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            dte_days = (exp_date - query_date).days
            
            # Extract nullable/empty fields safely
            bid_val = float(row["bid"]) if row.get("bid") is not None else 0.0
            ask_val = float(row["ask"]) if row.get("ask") is not None else 0.0
            vol_iv = float(row["vol"]) if row.get("vol") is not None else 0.0
            delta_val = float(row["delta"]) if row.get("delta") is not None else 0.0
            gamma_val = float(row["gamma"]) if row.get("gamma") is not None else 0.0
            theta_val = float(row["theta"]) if row.get("theta") is not None else 0.0
            vega_val = float(row["vega"]) if row.get("vega") is not None else 0.0
            rho_val = float(row["rho"]) if row.get("rho") is not None else 0.0
            
            # Canonical standard format contract symbol: TickerYYMMDD[C/P]Strike (strike * 1000 padded to 8 digits)
            strike_padded = f"{int(strike_val * 1000):08d}"
            exp_formatted = exp_date.strftime("%y%m%d")
            symbol_canonical = f"{ticker_clean}{exp_formatted}{call_put[0]}{strike_padded}"
            
            contract = OptionContract(
                symbol=symbol_canonical,
                strike=strike_val,
                type=call_put,
                contract_type=call_put,
                expiry=exp_date,
                bid=bid_val,
                ask=ask_val,
                last=(bid_val + ask_val) / 2.0,
                mark=(bid_val + ask_val) / 2.0,
                iv=vol_iv,
                delta=delta_val,
                gamma=gamma_val,
                theta=theta_val,
                vega=vega_val,
                rho=rho_val,
                dte=dte_days
            )
            contracts.append(contract)
            
        # Reconstruct underlying spot price using the tiered fallback hierarchy
        spot_val = fetch_historical_spot_local(ticker_clean, query_date)
        if spot_val is None:
            spot_val = fetch_historical_spot_yfinance(ticker_clean, query_date)
        if spot_val is None or spot_val <= 0:
            spot_val = estimate_spot_via_parity(contracts)
            
        return OptionChainData(
            ticker=ticker_clean,
            spot=spot_val,
            spot_open=spot_val,
            timestamp=datetime.combine(query_date, datetime.min.time()),
            contracts=contracts,
            underlying_symbol=ticker_clean,
            spot_price=spot_val
        )
        
    except Exception as e:
        log.error("[DOLT] Error fetching options chain from Dolt for %s on %s: %s", ticker, target_date_str, e, exc_info=True)
        
    return None
