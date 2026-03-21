"""
whale_detector.py
=================
Detects volume anomalies, calculates dynamic liquidity thresholds via yfinance, 
and aggregates by strike to classify Structural vs. Tactical Whales.
"""
from __future__ import annotations

import logging
from typing import Any
import yfinance as yf

from .options_fetcher import OptionChainData

log = logging.getLogger(__name__)

# Simple cache so we don't spam yfinance for the same ticker's ADV
_LIQUIDITY_CACHE: dict[str, float] = {}

def _get_dynamic_threshold(ticker: str, spot: float) -> float:
    """
    Calculates the minimum notional premium for a 'Whale'.
    Thresholds lowered to cast a wider, more realistic net for institutional flow.
    """
    yf_ticker = "^SPX" if ticker == "SPX" else "^NDX" if ticker == "NDX" else ticker

    if yf_ticker not in _LIQUIDITY_CACHE:
        try:
            ticker_obj = yf.Ticker(yf_ticker)
            avg_vol = ticker_obj.fast_info.get("tenDayAverageVolume") or 10_000_000
            addv = avg_vol * spot
            
            # Adjusted Tiering based on daily dollar flow
            if addv > 20_000_000_000:     # > $20B/day (The Black Holes: SPY, QQQ, NVDA)
                threshold = 2_500_000.0   # Lowered from $5M to $2.5M
            elif addv > 5_000_000_000:    # > $5B/day (Heavyweights: TSLA, AAPL, AMZN)
                threshold = 1_000_000.0   # Lowered from $2M to $1M
            elif addv > 1_000_000_000:    # > $1B/day (Standard liquid equities)
                threshold = 500_000.0     # Lowered from $1M to $500k
            else:                         # Smaller tickers / ETFs
                threshold = 250_000.0     # Lowered from $500k to $250k
                
            _LIQUIDITY_CACHE[yf_ticker] = threshold
            log.info("Dynamic Whale Threshold for %s: $%s (ADDV: $%s)", ticker, f"{threshold:,.0f}", f"{addv:,.0f}")
        except Exception as e:
            log.warning("Could not fetch yfinance ADV for %s, defaulting to $500k. Error: %s", ticker, e)
            _LIQUIDITY_CACHE[yf_ticker] = 500_000.0

    return _LIQUIDITY_CACHE[yf_ticker]


def detect_volume_anomalies(
    chain: OptionChainData, 
    ticker: str,
    min_vol_oi_ratio: float = 0.5, 
    min_volume: int = 200
) -> dict[str, list[dict[str, Any]]]:
    """
    Returns a dictionary separating anomalies into 'structural' (confluence >= 2)
    and 'tactical' (confluence == 1).
    """
    spot = float(chain.spot_price)
    dynamic_min_notional = _get_dynamic_threshold(ticker, spot)
    
    agg_map: dict[tuple[float, str], dict[str, Any]] = {}

    for c in chain.calls + chain.puts:
        oi = max(c.open_interest, 1)
        vol = int(c.volume)
        ratio = vol / oi
        notional = vol * float(c.mark) * 100.0

        if ratio < min_vol_oi_ratio or vol < min_volume:
            continue

        # Moneyness check
        if c.contract_type == "CALL" and c.strike < spot: continue
        if c.contract_type == "PUT" and c.strike > spot: continue

        key = (float(c.strike), c.contract_type)
        if key not in agg_map:
            agg_map[key] = {
                "strike": float(c.strike),
                "type": c.contract_type,
                "dtes": set(),
                "total_notional": 0.0,
                "total_volume": 0,
                "ratios": [],
                "has_golden_sweep": False  # Add the new flag here
            }
        
       # --- THE GOLDEN SWEEP TEST (STRICT) ---
        # 1. Extreme Fresh Capital: Volume must be at least 2.5x the resting OI.
        # 2. Urgency: DTE <= 35, but strictly > 0 (0DTE ruins Vol/OI math).
        # 3. Conviction: Premium must meet the DYNAMIC threshold, not a flat $1M.
        notional_val = vol * float(c.mark) * 100.0
        
        if (ratio >= 2.5) and (0 < c.dte <= 35) and (notional_val >= dynamic_min_notional):
            agg_map[key]["has_golden_sweep"] = True

        agg_map[key]["dtes"].add(int(c.dte))
        agg_map[key]["total_notional"] += notional
        agg_map[key]["total_volume"] += vol
        agg_map[key]["ratios"].append(ratio)

    structural_whales = []
    tactical_whales = []
    
    for data in agg_map.values():
        if data["total_notional"] < dynamic_min_notional:
            continue
            
        dtes = sorted(list(data["dtes"]))
        confluence_count = len(dtes)
        avg_ratio = sum(data["ratios"]) / len(data["ratios"])
        
        nearest_dte = dtes[0]
        tier = 1 if nearest_dte <= 30 else 2 if nearest_dte <= 90 else 3 if nearest_dte <= 180 else 4
        dte_str = f"{dtes[0]}-{dtes[-1]}d" if confluence_count > 1 else f"{dtes[0]}d"

        anomaly = {
            "strike": data["strike"],
            "type": data["type"],
            "dte_str": dte_str,
            "confluence": confluence_count,
            "avg_vol_oi_ratio": round(avg_ratio, 2),
            "notional": round(data["total_notional"], 2),
            "tier": tier,
            "volume": data["total_volume"],
            "is_golden_sweep": data["has_golden_sweep"] # Passed to UI
        }

        # Route to the proper bucket
        if confluence_count >= 2:
            structural_whales.append(anomaly)
        else:
            tactical_whales.append(anomaly)

    return {
        "structural": sorted(structural_whales, key=lambda x: x["notional"], reverse=True),
        "tactical": sorted(tactical_whales, key=lambda x: x["notional"], reverse=True)
    }