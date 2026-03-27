"""
Simple utility script to get current NQStats for a ticker.
Usage: python scripts/nqstats/get_current_nqstats.py --ticker NQ1
"""

import sys
import os
from datetime import datetime

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from scripts.utils.fused_data_loader import load_fused_data
from scripts.libs.nqstats.engine import NQStatsEngine

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Get current NQStats")
    parser.add_argument("--ticker", default="NQ1", help="Ticker (NQ1, ES1, etc.)")
    args = parser.parse_args()
    
    ticker = args.ticker
    
    print(f"[*] Fetching {ticker} data for NQStats analysis...")
    df = load_fused_data(ticker, timeframe="1m")
    
    if df.empty:
        print(f"[!] Error: No data found for {ticker}")
        return
        
    engine = NQStatsEngine(df, ticker=ticker)
    print(f"[*] Processing Unified Bias Algorithm...")
    engine.process()
    
    print("\n" + "="*45)
    print(engine.get_report())
    print("="*45)
    
    # Also output raw key for potential automation
    latest = engine.get_latest_status()
    print(f"\nCombo Key: {latest['aln']} | {latest['broken']} | {latest.get('status', 'N/A')}")

if __name__ == "__main__":
    main()
