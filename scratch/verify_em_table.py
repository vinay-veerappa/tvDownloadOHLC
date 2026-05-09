
import json
import math
import os
from datetime import datetime, date, timedelta

def get_trading_days(start_date, end_date):
    """Count trading days between two dates (excluding weekends)."""
    days = 0
    curr = start_date
    while curr < end_date:
        if curr.weekday() < 5:
            days += 1
        curr += timedelta(days=1)
    return max(1, days)

def main():
    # Load the macro levels JSON
    file_path = 'data/options/macro_levels.json'
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
        
    with open(file_path, 'r') as f:
        macro_data = json.load(f)
    
    # Reference Date for Saturday morning snapshot
    # generated_at: 2026-05-09
    today = date(2026, 5, 9)
    
    # Targets from user (ToS Expected Move values)
    # Targets from user (ToS Expected Move values)
    # Calibrated on Saturday morning snapshot (2026-05-09)
    targets = {
        "SPY": {
            "2026-05-11": 4.736,
            "2026-05-12": 6.809, # User provided 6.809
            "2026-05-13": 8.286, # User provided 8.286
            "2026-05-14": 9.817,
            "2026-05-15": 11.303
        },
        "SPX": {
            "2026-05-11": 45.679,
            "2026-05-12": 66.463,
            "2026-05-13": 80.489,
            "2026-05-14": 95.716,
            "2026-05-15": 110.938
        },
        "AAPL": {
            "2026-05-11": 4.16,
            "2026-05-13": 6.74,
            "2026-05-15": 8.616,
            "2026-05-18": 9.367,
            "2026-05-20": 10.662
        },
        "NVDA": {
            "2026-05-11": 4.582,
            "2026-05-13": 7.689,
            "2026-05-15": 9.687,
            "2026-05-18": 11.09,
            "2026-05-22": 19.297
        }
    }
    
    print(f"# Expected Move Model Verification")
    print(f"Snapshot Date: {today}")
    print(f"Formula: Price * IV * sqrt((0.637 * DTE + intercept) / 365)")
    print(f"Intercepts: Equity=0.24, Futures=0.69")
    print("")
    print("| Ticker | Expiry | DTE | IV % | ToS Target | Engine EM | Inst (0.85) | Delta % |")
    print("|--------|--------|-----|------|------------|-----------|-------------|---------|")

    # Filter for interesting tickers
    target_tickers = ["ES", "NQ", "SPY", "AAPL", "NVDA"]

    for asset_data in macro_data['market_structure']:
        asset = asset_data['asset']
        if asset not in target_tickers:
            continue
            
        lookup_ticker = asset
        if asset == "ES": lookup_ticker = "SPX"
        elif asset == "NQ": lookup_ticker = "NDX" # Fallback or keep NQ targets if available
            
        asset_targets = targets.get(lookup_ticker, {})
            
        for em in asset_data['expected_moves'][:8]: # Show first 8 expiries
            expiry_str = em['expiry']
            cal_dte = em['dte'] 
            
            spot = (em['em_upper'] + em['em_lower']) / 2.0
            engine_em = em['em_value']
            
            # Constants from handoff doc
            is_futures = asset in ["ES", "NQ", "CL", "GC", "RTY", "YM"]
            intercept = 0.69 if is_futures else 0.24
            slope = 0.637
            
            # Calibrated T_eff
            t_eff_calibrated = (slope * cal_dte + intercept) / 365.0
            
            if t_eff_calibrated > 0:
                # Back out IV used by engine
                series_iv = engine_em / (spot * math.sqrt(t_eff_calibrated))
                iv_pct = series_iv * 100
                val_inst = engine_em * 0.85
            else:
                iv_pct = 0
                val_inst = 0
            
            target = asset_targets.get(expiry_str, 0)
            diff_pct = (engine_em - target) / target * 100 if target > 0 else 0
            
            def fmt_val(val, tgt):
                if tgt == 0: return f"{val:.2f}"
                # Bold if within 0.1% of target
                return f"**{val:.2f}**" if abs(val - tgt) / tgt < 0.001 else f"{val:.2f}"

            target_str = f"{target:.2f}" if target > 0 else "N/A"
            diff_str = f"{diff_pct:+.2f}%" if target > 0 else "N/A"
            
            print(f"| {asset:4} | {expiry_str} | {cal_dte:3} | {iv_pct:5.2f}% | {target_str:10} | {fmt_val(engine_em, target):9} | {val_inst:11.2f} | {diff_str:7} |")


if __name__ == "__main__":
    main()
