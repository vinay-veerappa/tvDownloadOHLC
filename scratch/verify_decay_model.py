import json
import os
import math

def generate_verification_table():
    json_path = r"c:\Users\vinay\tvDownloadOHLC\data\options\macro_levels.json"
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)

    headers = ["Ticker", "Expiry", "DTE", "Formula(1.0)", "Skew(0.85)", "Decay(0.15)", "Decay(0.25)", "Target"]
    print(" | ".join(f"{h:<12}" for h in headers))
    print("-" * 110)

    assets = data.get('market_structure', [])
    targets = {
        "SPY": {
            "2026-05-12": 6.809,
            "2026-05-13": 8.286
        }
    }
    
    for asset_data in assets:
        asset = asset_data.get('asset', 'Unknown')
        cash = asset_data.get('cash_ticker', 'Unknown')
        label = f"{asset}/{cash}"
        
        ems = asset_data.get('expected_moves', [])
        for em in ems[:6]:
            dte = em.get('dte', 0)
            if dte == 0: continue
            
            expiry = em.get('expiry', 'N/A')
            base_em = em.get('em_value', 0.0)
            
            # Models
            skew_085 = round(base_em * 0.85, 2)
            decay_015 = round(base_em * (0.85 + 0.15 / dte), 2)
            decay_025 = round(base_em * (0.85 + 0.25 / dte), 2)
            
            target = targets.get(cash, {}).get(expiry, "-")
            
            row = [label, expiry, str(dte), str(base_em), str(skew_085), str(decay_015), str(decay_025), str(target)]
            print(" | ".join(f"{str(val):<12}" for val in row))

if __name__ == "__main__":
    generate_verification_table()
