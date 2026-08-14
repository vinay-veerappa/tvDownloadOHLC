"""
Extract Expected Moves & Option Quotes from ThinkorSwim (TOS) Desktop via RTD COM & Schwab/TOS EM Model.
"""

import asyncio
import json
import math
import sys
import os
import time
from datetime import datetime, date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.streaming.options.tos_rtd.adapter import TOSRTDAdapter, RTDConfig
from scripts.streaming.options.gex_calculator import calculate_tos_expected_move
from scripts.market_data.schwab_options_utils import normalize_option_chain_symbol

SYMBOLS_MAP = {
    "ES": "/ES",
    "NQ": "/NQ",
    "SPX": "$SPX",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "DIA": "DIA",
    "IWM": "IWM"
}

def get_next_friday(d: date) -> date:
    days_ahead = 4 - d.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)

def test_tos_rtd_extraction():
    print(f"=== Starting TOS RTD & Expected Move Extraction at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')} ===")
    
    target_expiry = get_next_friday(date.today())
    print(f"Target Expiry Friday: {target_expiry}")
    
    config = RTDConfig(strike_range=15, strike_spacing=1.0)
    adapter = TOSRTDAdapter(config)
    
    futures_symbols = ["/ES", "/NQ"]
    
    try:
        adapter.start(symbols=futures_symbols, expiry=target_expiry)
        time.sleep(3)
        
        snapshot = adapter.get_snapshot()
        print(f"TOS RTD Snapshot received: {len(snapshot)} keys")
        
        results = {}
        for label, rtd_sym in SYMBOLS_MAP.items():
            price = adapter.get_futures_price(rtd_sym) if rtd_sym.startswith("/") else None
            results[label] = {
                "rtd_symbol": rtd_sym,
                "price": price
            }
            
        print("\nDirect TOS RTD Prices:")
        for k, v in results.items():
            print(f"  {k} ({v['rtd_symbol']}): {v['price']}")
            
        adapter.stop()
        return results
    except Exception as e:
        print(f"TOS RTD Error: {e}")
        try:
            adapter.stop()
        except Exception:
            pass
        return {}

if __name__ == "__main__":
    test_tos_rtd_extraction()
