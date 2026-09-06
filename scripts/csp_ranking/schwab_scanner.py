"""
Schwab Trader API Scanner for Cash-Secured Puts (Routes via Central Options Hub)
Queries the central Schwab Options Hub (FastAPI/REST proxy) to request live option chains,
official Greeks, implied volatility, volume, and open interest across the scan universe.
"""

import requests
import json
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from pathlib import Path

from scripts.csp_ranking.tos_parser import TOSOptionContract
from scripts.csp_ranking.finviz_client import FinvizClient
from scripts.streaming.options.config import HUB_URL
from scripts.utils.universe_manager import get_universe, get_dynamic_csp_universe


def query_hub_rest(method: str, params: dict, timeout: int = 15) -> dict:
    """
    Sends a prioritized REST request to the central Schwab Unified Hub proxy.
    """
    url = f"{HUB_URL}/request"
    payload = {
        "method": method,
        "params": params,
        "priority": 2  # Options chain priority
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise ConnectionError(f"Hub returned status {resp.status_code}: {resp.text}")
    return resp.json()


def scan_schwab_options(
    tickers: Optional[List[str]] = None,
    min_iv_pct: float = 60.0,
    min_dte: int = 25,
    max_dte: int = 45,
    min_delta: float = -0.30,
    max_delta: float = -0.10,
    min_open_interest: int = 100,
    min_ror_pct: float = 2.0,
    max_ror_pct: float = 8.0,
) -> List[TOSOptionContract]:
    """
    Queries the central Schwab Options Hub to discover and filter CSP candidates matching Ben's exact 9 criteria.
    """
    target_tickers = tickers or get_dynamic_csp_universe()
    today = date.today()
    discovered_contracts: List[TOSOptionContract] = []
    finviz_client = FinvizClient()

    print(f"\n📡 Querying Central Schwab Options Hub ({HUB_URL}) across {len(target_tickers)} liquid tickers...")

    for ticker in target_tickers:
        print(f"   -> Querying Hub for {ticker}...", end="\r")
        try:
            # 1. Fundamental profitability check
            prof = finviz_client.get_ticker_profile(ticker)
            if prof and prof.pe and prof.pe <= 0:
                continue # Disqualify unprofitable tickers

            # 2. Query Schwab Option Chains via Hub Proxy
            resp = query_hub_rest("get_option_chain", {
                "symbol": ticker,
                "contractType": "PUT",
                "includeUnderlyingQuote": True,
                "strategy": "SINGLE",
            })

            if not isinstance(resp, dict):
                continue

            underlying_price = resp.get("underlyingPrice", 0.0)
            if underlying_price < 8.0:
                continue

            put_map = resp.get("putExpDateMap", {})
            if not put_map:
                continue

            # 3. Iterate Expirations in DTE Window
            for exp_key, strikes_map in put_map.items():
                parts = exp_key.split(":")
                exp_date_str = parts[0]
                dte = int(parts[1]) if len(parts) > 1 else (datetime.strptime(exp_date_str, "%Y-%m-%d").date() - today).days

                if not (min_dte <= dte <= max_dte):
                    continue

                exp_d = datetime.strptime(exp_date_str, "%Y-%m-%d").date()

                # 4. Iterate Put Strikes
                for strike_str, opt_list in strikes_map.items():
                    if not opt_list:
                        continue
                    opt = opt_list[0]

                    strike = float(opt.get("strikePrice", 0.0))
                    bid = float(opt.get("bid", 0.0))
                    ask = float(opt.get("ask", 0.0))
                    last_p = float(opt.get("last", 0.0))
                    vol = int(opt.get("totalVolume", 0))
                    oi = int(opt.get("openInterest", 0))
                    delta = float(opt.get("delta", 0.0))
                    gamma = float(opt.get("gamma", 0.0))
                    theta = float(opt.get("theta", 0.0))
                    vega = float(opt.get("vega", 0.0))
                    iv = float(opt.get("volatility", 0.0))

                    if strike <= 0 or bid <= 0.05:
                        continue

                    # Filter Delta (-0.30 to -0.10)
                    if not (min_delta <= delta <= max_delta):
                        continue

                    # Filter Open Interest (>= 100)
                    if oi < min_open_interest:
                        continue

                    # Filter IV (>= 60%)
                    if iv > 0 and iv < min_iv_pct:
                        continue

                    # Filter ROR (2.0% - 5.0%+)
                    trade_ror = (bid / strike) * 100.0
                    if not (min_ror_pct <= trade_ror <= max_ror_pct):
                        continue

                    exp_code = exp_d.strftime("%y%m%d")
                    strike_code = str(int(strike)) if strike.is_integer() else str(strike)
                    tos_sym = f".{ticker}{exp_code}P{strike_code}"
                    desc = f"{ticker} 100 (Weeklys) {exp_d.strftime('%d %b %y').upper()} {strike_code} PUT"

                    raw_dict = {
                        "Symbol": tos_sym,
                        "Description": desc,
                        "Last": last_p,
                        "Net Chng": 0.0,
                        "%Change": "0.0%",
                        "Volume": vol,
                        "Bid": bid,
                        "Ask": ask,
                        "High": last_p,
                        "Low": last_p,
                        "Delta": f"{delta:.2f}",
                        "Gamma": f"{gamma:.2f}",
                        "Theta": f"{theta:.2f}",
                        "Vega": f"{vega:.2f}",
                    }

                    contract = TOSOptionContract(raw_dict, scan_date=today)
                    discovered_contracts.append(contract)

        except Exception:
            continue

    print(f"✅ Options Hub scan complete: Discovered {len(discovered_contracts)} qualifying contracts.          ")
    return discovered_contracts
