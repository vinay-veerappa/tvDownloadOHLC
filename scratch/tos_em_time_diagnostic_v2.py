import os
import json
import math
import numpy as np

def run_diagnostic():
    # 1. Path setup
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(root_dir, "scratch", "tos_em_calibration.json")
    
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found: {json_path}")
        return
        
    with open(json_path, "r") as f:
        data = json.load(f)
        
    # User actuals
    tos_updates = {
        "SPX": {
            "2026-06-03": 32.228,
            "2026-06-04": 52.624,
            "2026-06-05": 70.382
        },
        "SPY": {
            "2026-06-03": 3.793,
            "2026-06-04": 5.468,
            "2026-06-05": 7.134
        },
        "QQQ": {
            "2026-06-03": 6.568,
            "2026-06-04": 9.472,
            "2026-06-05": 11.998
        },
        "IWM": {
            "2026-06-03": 2.523,
            "2026-06-04": 3.629,
            "2026-06-05": 4.874
        },
        "AAPL": {
            "2026-06-03": 3.628,
            "2026-06-05": 6.471
        },
        "MSFT": {
            "2026-06-03": 8.431,
            "2026-06-05": 14.357
        },
        "NVDA": {
            "2026-06-03": 4.520,
            "2026-06-05": 8.197
        },
        "TSLA": {
            "2026-06-03": 9.209,
            "2026-06-05": 16.604
        }
    }
    
    # Update and save JSON
    for ticker, exp_updates in tos_updates.items():
        if ticker in data:
            for exp_str, val in exp_updates.items():
                if exp_str in data[ticker]:
                    data[ticker][exp_str]["tos_displayed_em"] = val
                    
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Successfully saved all 20 ToS captures to {json_path}\n")
    
    # Extract samples
    samples = []
    for ticker, exp_updates in tos_updates.items():
        for exp_str, val in exp_updates.items():
            if ticker in data and exp_str in data[ticker]:
                m = data[ticker][exp_str]
                samples.append({
                    "ticker": ticker,
                    "expiry": exp_str,
                    "dte": m["dte"],
                    "straddle": m["atm_straddle_mid"],
                    "tos_em": val,
                    "ratio": val / m["atm_straddle_mid"]
                })
                
    # Sort samples for readable output
    samples = sorted(samples, key=lambda x: (x["ticker"], x["dte"]))
    
    # Group samples
    subsets = {
        "Pooled (All 20 Samples)": samples,
        "ETFs & Indices Only (SPX, SPY, QQQ, IWM - 12 Samples)": [s for s in samples if s["ticker"] in ["SPX", "SPY", "QQQ", "IWM"]],
        "Individual Stocks Only (AAPL, MSFT, NVDA, TSLA - 8 Samples)": [s for s in samples if s["ticker"] not in ["SPX", "SPY", "QQQ", "IWM"]]
    }
    
    for name, subset in subsets.items():
        print("=" * 80)
        print(f"SUBSET: {name}")
        print("=" * 80)
        
        DTE_arr = np.array([s["dte"] for s in subset])
        Ratio_arr = np.array([s["ratio"] for s in subset])
        
        # --- Fit Model 1: Flat (ratio = k) ---
        k_opt = np.mean(Ratio_arr)
        
        # --- Fit Model 2: Slope/Intercept (ratio = a * sqrt(0.637 * DTE + b)) ---
        best_b = 0.0
        best_a = 0.0
        min_sse_multi = float("inf")
        for b in np.linspace(0.01, 15.0, 15000):
            z = np.sqrt(0.637 * DTE_arr + b)
            a = np.sum(Ratio_arr * z) / np.sum(z * z)
            sse = np.sum((Ratio_arr - a * z) ** 2)
            if sse < min_sse_multi:
                min_sse_multi = sse
                best_b = b
                best_a = a
                
        # --- Fit Model 3: Plain Calendar (ratio = a * sqrt(DTE + offset)) ---
        best_offset = 0.0
        best_a_cal = 0.0
        min_sse_cal = float("inf")
        for offset in np.linspace(0.01, 15.0, 15000):
            z = np.sqrt(DTE_arr + offset)
            a = np.sum(Ratio_arr * z) / np.sum(z * z)
            sse = np.sum((Ratio_arr - a * z) ** 2)
            if sse < min_sse_cal:
                min_sse_cal = sse
                best_offset = offset
                best_a_cal = a
                
        # Evaluate function
        def evaluate(ratio_pred_fn):
            errors = []
            pct_errors = []
            residuals = []
            for s in subset:
                pred = ratio_pred_fn(s["dte"]) * s["straddle"]
                res = s["tos_em"] - pred
                residuals.append(res)
                errors.append(abs(res))
                pct_errors.append(abs(res) / s["tos_em"])
            return np.mean(errors), np.mean(pct_errors) * 100, residuals
            
        mae_1, mape_1, res_1 = evaluate(lambda d: k_opt)
        mae_2, mape_2, res_2 = evaluate(lambda d: best_a * math.sqrt(0.637 * d + best_b))
        mae_3, mape_3, res_3 = evaluate(lambda d: best_a_cal * math.sqrt(d + best_offset))
        
        # Report fits
        print(f"Model 1 (Flat): ratio = {k_opt:.6f}")
        print(f"  MAE  : {mae_1:.4f} points | MAPE : {mape_1:.3f}%")
        print(f"Model 2 (Slope/Intercept): ratio = {best_a:.6f} * sqrt(0.637 * DTE + {best_b:.4f})")
        print(f"  MAE  : {mae_2:.4f} points | MAPE : {mape_2:.3f}%")
        print(f"Model 3 (Plain Calendar): ratio = {best_a_cal:.6f} * sqrt(DTE + {best_offset:.4f})")
        print(f"  MAE  : {mae_3:.4f} points | MAPE : {mape_3:.3f}%")
        print()
        
        # Residuals Table for Model 1 (Flat)
        print("Residuals breakdown for Model 1 (Flat):")
        print(f"  {'Ticker':<6} | {'DTE':<3} | {'Straddle':<8} | {'ToS_EM':<8} | {'Pred':<8} | {'Residual':<9} | {'Pct_Err':<7}")
        print("-" * 65)
        for idx, s in enumerate(subset):
            pred = k_opt * s["straddle"]
            res = res_1[idx]
            pct = (res / s["tos_em"]) * 100
            print(f"  {s['ticker']:<6} | {s['dte']:<3} | {s['straddle']:<8.2f} | {s['tos_em']:<8.3f} | {pred:<8.3f} | {res:<+9.3f} | {pct:<+7.2f}%")
        print()
        
        # Decision Comparison
        print("DECISION SUMMARY:")
        print(f"  Flat MAE: {mae_1:.4f} | Slope/Int MAE: {mae_2:.4f} | Plain Cal MAE: {mae_3:.4f}")
        diff = mae_1 - mae_2
        if abs(diff) < 0.05 or (mae_1 / mae_2 < 1.05):
            print(f"  -> Winner: FLAT MODEL (simplest, fits within {abs(diff):.4f} points of sloped, MAPE: {mape_1:.2f}%)")
            print(f"  -> Recommended Straddle Multiple: k = {k_opt:.4f}")
        elif mae_2 < mae_1:
            print(f"  -> Winner: SLOPE/INTERCEPT MODEL (fits better, ratio = {best_a:.4f}*sqrt(0.637*DTE + {best_b:.4f}))")
        else:
            print(f"  -> Winner: PLAIN CALENDAR MODEL (ratio = {best_a_cal:.4f}*sqrt(DTE + {best_offset:.4f}))")
        print("\n")

if __name__ == "__main__":
    run_diagnostic()
