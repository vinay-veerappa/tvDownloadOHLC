import os
import json
import math
import numpy as np

def run_comparison():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(root_dir, "scratch", "tos_em_calibration.json")
    
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found: {json_path}")
        return
        
    with open(json_path, "r") as f:
        data = json.load(f)
        
    # Today's actual ToS expected moves (provided by user for June 4th and June 5th)
    tos_updates = {
        "SPX": {
            "2026-06-04": 42.06,
            "2026-06-05": 62.09
        },
        "SPY": {
            "2026-06-04": 4.42,
            "2026-06-05": 6.311
        },
        "QQQ": {
            "2026-06-04": 6.887,
            "2026-06-05": 9.892
        },
        "AAPL": {
            "2026-06-05": 5.313
        },
        "TSLA": {
            "2026-06-05": 13.749
        }
    }
    
    # We will compile all valid records
    records = []
    for ticker, exp_updates in tos_updates.items():
        for exp_str, tos_val in exp_updates.items():
            if ticker in data and exp_str in data[ticker]:
                m = data[ticker][exp_str]
                records.append({
                    "ticker": ticker,
                    "expiry": exp_str,
                    "dte": m["dte"],
                    "spot": m["spot"],
                    "iv": m["atm_iv_front"],
                    "straddle": m["atm_straddle_mid"],
                    "tos_em": tos_val
                })
                
    records = sorted(records, key=lambda x: (x["ticker"], x["dte"]))
    
    print(f"Loaded {len(records)} records for June 3, 2026 verification.\n")
    
    # Define models
    def model_config_flat(r):
        # Current production config model
        # SPX has 1.05 multiplier override, others default to 1.10
        k = 1.05 if r["ticker"] in ["SPX", "/ES", "ES"] else 1.10
        return k * r["straddle"]
        
    def model_handoff_sloped(r):
        # Handoff document: a + b / DTE
        is_etf = r["ticker"] in ["SPX", "SPY", "QQQ", "IWM"]
        a = 1.106 if is_etf else 1.074
        b = 0.135 if is_etf else 0.145
        mult = a + b / max(0.5, r["dte"])
        return r["straddle"] * mult
        
    def model_teff_iv(r):
        # T_eff formula from handoff: Price * IV * sqrt((0.637 * DTE + 0.24) / 365)
        # Note: all these are equities/ETFs so intercept is 0.24
        t_eff_yr = (0.637 * r["dte"] + 0.24) / 365.0
        return r["spot"] * r["iv"] * math.sqrt(t_eff_yr)
        
    # Fit flat multipliers on today's actuals
    # ETFs: mean(ToS_EM / Straddle)
    # Stocks: mean(ToS_EM / Straddle)
    etf_ratios = [r["tos_em"] / r["straddle"] for r in records if r["ticker"] in ["SPX", "SPY", "QQQ"]]
    stock_ratios = [r["tos_em"] / r["straddle"] for r in records if r["ticker"] not in ["SPX", "SPY", "QQQ"]]
    
    k_etf = np.mean(etf_ratios) if etf_ratios else 1.10
    k_stock = np.mean(stock_ratios) if stock_ratios else 1.10
    
    print(f"Empirically fitted flat multipliers on today's actuals:")
    print(f"  ETFs/Indices k = {k_etf:.4f}")
    print(f"  Stocks k       = {k_stock:.4f}\n")
    
    def model_fitted_flat(r):
        is_etf = r["ticker"] in ["SPX", "SPY", "QQQ"]
        k = k_etf if is_etf else k_stock
        return k * r["straddle"]

    models = {
        "Config Flat (k=1.05/1.10)": model_config_flat,
        "Handoff Sloped (a+b/DTE)": model_handoff_sloped,
        "TOS T_eff (IV-based)": model_teff_iv,
        "Fitted Flat (k={:.2f}/{:.2f})".format(k_etf, k_stock): model_fitted_flat
    }
    
    # Print comparison table
    print("### Expected Move Model Comparison Table (June 3, 2026)")
    print(f"| {'Ticker':<6} | {'DTE':<3} | {'ToS EM':<8} | {'Straddle':<8} | {'Config Flat':<11} | {'Handoff Sloped':<14} | {'T_eff IV':<10} | {'Fitted Flat':<11} |")
    print("|--------|-----|--------|----------|-------------|----------------|----------|-------------|")
    
    results = {name: {"errors": [], "pct_errors": []} for name in models}
    
    for r in records:
        row_str = f"| {r['ticker']:<6} | {r['dte']:<3} | {r['tos_em']:<8.3f} | {r['straddle']:<8.2f} |"
        for name, fn in models.items():
            pred = fn(r)
            err = pred - r["tos_em"]
            pct_err = (err / r["tos_em"]) * 100
            results[name]["errors"].append(abs(err))
            results[name]["pct_errors"].append(abs(pct_err))
            row_str += f" {pred:<11.2f} ({pct_err:+5.1f}%) |"
        print(row_str)
        
    print("\n### Model Performance Summary (Mean Absolute Error & Pct Error)")
    print(f"| {'Model':<30} | {'Mean Absolute Error (MAE)':<25} | {'Mean Absolute Pct Error (MAPE)':<30} |")
    print("|--------------------------------|---------------------------|--------------------------------|")
    for name in models:
        mae = np.mean(results[name]["errors"])
        mape = np.mean(results[name]["pct_errors"])
        print(f"| {name:<30} | {mae:<25.4f} points | {mape:<30.2f}% |")

if __name__ == "__main__":
    run_comparison()
