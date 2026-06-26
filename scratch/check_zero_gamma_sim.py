import json
import math

def _bsm_d1d2(S, K, t, iv, r, q):
    if S <= 0 or K <= 0 or t <= 0 or iv <= 0:
        return None, None, None
    d1 = (math.log(S / K) + (r - q + 0.5 * iv ** 2) * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)
    norm_d1 = math.exp(-0.5 * d1 ** 2) / math.sqrt(2.0 * math.pi)
    return d1, d2, norm_d1

def calculate_gex_at_spot(strikes_data, S_hypo, t=1/365.0, r=0.02, q=0.0):
    total = 0.0
    contract_size = 100
    for row in strikes_data:
        strike = row['strike']
        
        # Call GEX
        call_oi = row['call_oi']
        call_iv = max(row['call_iv'], 1e-4)
        if call_oi > 0:
            d1, d2, norm_d1 = _bsm_d1d2(S_hypo, strike, t, call_iv, r, q)
            if d1 is not None:
                gamma = math.exp(-q * t) * norm_d1 / (S_hypo * call_iv * math.sqrt(t))
                gex = gamma * call_oi * contract_size * S_hypo
                total += gex
                
        # Put GEX
        put_oi = row['put_oi']
        put_iv = max(row['put_iv'], 1e-4)
        if put_oi > 0:
            d1, d2, norm_d1 = _bsm_d1d2(S_hypo, strike, t, put_iv, r, q)
            if d1 is not None:
                gamma = math.exp(-q * t) * norm_d1 / (S_hypo * put_iv * math.sqrt(t))
                gex = gamma * put_oi * contract_size * S_hypo
                total -= gex
                
    return total

with open('data/options/gex_profiles_versioned.json') as f:
    gex_data = json.load(f)

profiles = gex_data['profiles']

for ticker, spot in [('SPY', 728.25), ('QQQ', 706.12)]:
    print(f"\n--- {ticker} (Spot: {spot}) ---")
    strikes_data = profiles[ticker]
    
    # Calculate at boundaries: spot * 0.5 and spot * 1.5
    low = spot * 0.5
    high = spot * 1.5
    g_low = calculate_gex_at_spot(strikes_data, low)
    g_high = calculate_gex_at_spot(strikes_data, high)
    print(f"At low ({low:.2f}): GEX = {g_low:.6e}")
    print(f"At high ({high:.2f}): GEX = {g_high:.6e}")
    
    # Calculate GEX in a grid from low to high to see the profile
    print("GEX Profile Grid:")
    for pct in [0.5, 0.7, 0.9, 0.95, 0.98, 1.0, 1.02, 1.05, 1.1, 1.3, 1.5]:
        grid_spot = spot * pct
        gex_val = calculate_gex_at_spot(strikes_data, grid_spot)
        print(f"  Spot {pct:4.2f}x ({grid_spot:6.2f}): GEX = {gex_val:+13.2f}")
