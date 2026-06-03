import os
import json
import math
import numpy as np

def run_test():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(root_dir, "scratch", "tos_em_calibration.json")
    
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found: {json_path}")
        return
        
    with open(json_path, "r") as f:
        data = json.load(f)
        
    # We will reconstruct the exact bid, ask, mid, mark prices for ATM, ITM, and OTM strikes.
    # From JSON strikes_ladder:
    # strikes are sorted.
    # index idx is the ATM strike.
    # strikes[idx-1] is the OTM Put / ITM Call strike.
    # strikes[idx+1] is the OTM Call / ITM Put strike.
    
    samples = []
    for ticker in data:
        for exp_str in data[ticker]:
            m = data[ticker][exp_str]
            tos_em = m.get("tos_displayed_em")
            if tos_em is None:
                continue
                
            spot = m["spot"]
            dte = m["dte"]
            strikes = [s["strike"] for s in m["strikes_ladder"]]
            atm_strike = m["atm_strike"]
            
            try:
                idx = strikes.index(atm_strike)
            except ValueError:
                # Fallback
                idx = len(strikes) // 2
                
            # Contracts at ATM (idx), ATM-1 (idx-1), ATM+1 (idx+1)
            # Ensure index safety
            if idx - 1 < 0 or idx + 1 >= len(strikes):
                print(f"Warning: Not enough strikes in ladder for {ticker} {exp_str}")
                continue
                
            c_atm = m["strikes_ladder"][idx]["call"]
            p_atm = m["strikes_ladder"][idx]["put"]
            
            c_minus1 = m["strikes_ladder"][idx-1]["call"] # ITM Call
            p_minus1 = m["strikes_ladder"][idx-1]["put"] # OTM Put
            
            c_plus1 = m["strikes_ladder"][idx+1]["call"] # OTM Call
            p_plus1 = m["strikes_ladder"][idx+1]["put"] # ITM Put
            
            # --- Calculations using ASK ---
            straddle_ask = c_atm["ask"] + p_atm["ask"]
            itm_strangle_ask = c_minus1["ask"] + p_plus1["ask"]
            otm_strangle_ask = c_plus1["ask"] + p_minus1["ask"]
            
            pred_itm_ask = (straddle_ask + itm_strangle_ask) / 2.0
            pred_otm_ask = (straddle_ask + otm_strangle_ask) / 2.0
            
            # --- Calculations using MID ---
            straddle_mid = c_atm["mid"] + p_atm["mid"]
            itm_strangle_mid = c_minus1["mid"] + p_plus1["mid"]
            otm_strangle_mid = c_plus1["mid"] + p_minus1["mid"]
            
            pred_itm_mid = (straddle_mid + itm_strangle_mid) / 2.0
            pred_otm_mid = (straddle_mid + otm_strangle_mid) / 2.0
            
            samples.append({
                "ticker": ticker,
                "expiry": exp_str,
                "dte": dte,
                "tos_em": tos_em,
                "pred_itm_ask": pred_itm_ask,
                "pred_otm_ask": pred_otm_ask,
                "pred_itm_mid": pred_itm_mid,
                "pred_otm_mid": pred_otm_mid,
            })
            
    print("=======================================================================")
    print("TESTING FORMULA: (ATM Straddle + 1st ITM/OTM Strangle) / 2")
    print("=======================================================================\n")
    
    # Evaluate MAE / MAPE
    def evaluate_model(name, getter):
        errors = []
        pct_errors = []
        for s in samples:
            pred = getter(s)
            res = abs(s["tos_em"] - pred)
            errors.append(res)
            pct_errors.append(res / s["tos_em"])
        mae = np.mean(errors)
        mape = np.mean(pct_errors) * 100
        return mae, mape
        
    fits = {
        "Formula 1: ITM Strangle using ASK": lambda s: s["pred_itm_ask"],
        "Formula 2: OTM Strangle using ASK": lambda s: s["pred_otm_ask"],
        "Formula 3: ITM Strangle using MID": lambda s: s["pred_itm_mid"],
        "Formula 4: OTM Strangle using MID": lambda s: s["pred_otm_mid"]
    }
    
    for fname, getter in fits.items():
        mae, mape = evaluate_model(fname, getter)
        print(f"{fname}:")
        print(f"  MAE  : {mae:.4f} points")
        print(f"  MAPE : {mape:.3f}%")
        print()
        
    # Print residuals for Formula 3 (ITM Strangle using MID) which we expect is close
    print("=======================================================================")
    print("DETAILED BREAKDOWN: Formula 3 (ITM Strangle using MID)")
    print("=======================================================================")
    print(f"  {'Ticker':<6} | {'DTE':<3} | {'ToS_EM':<8} | {'Pred_Mid':<8} | {'Residual':<9} | {'Pct_Err':<7}")
    print("-" * 65)
    for s in samples:
        pred = s["pred_itm_mid"]
        res = s["tos_em"] - pred
        pct = (res / s["tos_em"]) * 100
        print(f"  {s['ticker']:<6} | {s['dte']:<3} | {s['tos_em']:<8.3f} | {pred:<8.3f} | {res:<+9.3f} | {pct:<+7.2f}%")
    print()
    
    # Print residuals for Formula 4 (OTM Strangle using MID) which is the standard OTM strangle
    print("=======================================================================")
    print("DETAILED BREAKDOWN: Formula 4 (OTM Strangle using MID)")
    print("=======================================================================")
    print(f"  {'Ticker':<6} | {'DTE':<3} | {'ToS_EM':<8} | {'Pred_Mid':<8} | {'Residual':<9} | {'Pct_Err':<7}")
    print("-" * 65)
    for s in sorted(samples, key=lambda x: (x["ticker"], x["dte"])):
        pred = s["pred_otm_mid"]
        res = s["tos_em"] - pred
        pct = (res / s["tos_em"]) * 100
        print(f"  {s['ticker']:<6} | {s['dte']:<3} | {s['tos_em']:<8.3f} | {pred:<8.3f} | {res:<+9.3f} | {pct:<+7.2f}%")
    print()

if __name__ == "__main__":
    run_test()
