import sys
from pathlib import Path

# Add repo root to python path to import scripts
repo_root = Path("c:/Users/vinay/tvDownloadOHLC")
sys.path.append(str(repo_root))

from scripts.streaming.options.options_fetcher import create_client, fetch_option_chain_data
from scripts.streaming.options.config import DTE_TARGETS
from scripts.streaming.options.gex_calculator import _calculate_hypothetical_total_gex

def find_zg_tighter_bounds(calls, puts, spot, delta_adjusted=False):
    # Use tighter bounds (0.9x to 1.1x spot) to avoid boundary zero-gamma noise
    low = spot * 0.9
    high = spot * 1.1
    
    g_low = _calculate_hypothetical_total_gex(calls, puts, low, delta_adjusted)
    g_high = _calculate_hypothetical_total_gex(calls, puts, high, delta_adjusted)
    
    if g_low * g_high > 0:
        return None
        
    for _ in range(30):
        mid = (low + high) / 2.0
        g_mid = _calculate_hypothetical_total_gex(calls, puts, mid, delta_adjusted)
        if abs(g_mid) < 1e-2:
            return round(mid, 2)
        if g_mid < 0:
            low = mid
        else:
            high = mid
            
    return round((low + high) / 2.0, 2)

def main():
    client = create_client()
    for ticker in ['SPY', 'QQQ']:
        print(f"\n=================== {ticker} Intraday Precise Zero Gamma ===================")
        chain = fetch_option_chain_data(client, ticker, DTE_TARGETS)
        spot = chain.spot_price
        
        zg_normal = find_zg_tighter_bounds(chain.calls, chain.puts, spot, delta_adjusted=False)
        zg_delta_adj = find_zg_tighter_bounds(chain.calls, chain.puts, spot, delta_adjusted=True)
        
        print(f"Spot price: {spot}")
        print(f"Precise Zero Gamma (Standard): {zg_normal}")
        print(f"Precise Zero Gamma (Delta-Adjusted): {zg_delta_adj}")

if __name__ == '__main__':
    main()
