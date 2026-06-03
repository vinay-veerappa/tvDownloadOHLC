import os
import json
import numpy as np

def run_fitting():
    # 1. Path setup
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(root_dir, "scratch", "tos_em_calibration.json")
    
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found: {json_path}")
        return
        
    with open(json_path, "r") as f:
        data = json.load(f)
        
    # 2. Update ToS displayed EM values from user
    tos_updates = {
        "SPX": {
            "2026-06-03": 31.523,
            "2026-06-04": 52.19,
            "2026-06-05": 70.066
        },
        "SPY": {
            "2026-06-03": 3.793,
            "2026-06-04": 5.467,
            "2026-06-05": 7.133
        }
    }
    
    for ticker, exp_updates in tos_updates.items():
        if ticker in data:
            for exp_str, val in exp_updates.items():
                if exp_str in data[ticker]:
                    data[ticker][exp_str]["tos_displayed_em"] = val
                    
    # Save the updated JSON back to file
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Updated and saved ToS values to {json_path}\n")
    
    # 3. Extract datasets for regression
    # We will fit using 'mid' price measures.
    samples = []
    
    for ticker in ["SPX", "SPY"]:
        if ticker not in data:
            continue
        for exp_str, val in tos_updates[ticker].items():
            if exp_str not in data[ticker]:
                continue
                
            metrics = data[ticker][exp_str]
            samples.append({
                "ticker": ticker,
                "expiry": exp_str,
                "dte": metrics["dte"],
                "tos_em": val,
                "straddle": metrics["atm_straddle_mid"],
                "strangle_05": metrics["strangle_05pct_mid"],
                "strangle_10": metrics["strangle_10pct_mid"],
                "strangle_15": metrics["strangle_15pct_mid"]
            })
            
    print(f"Extracted {len(samples)} samples for fitting:")
    for s in samples:
        print(f"  {s['ticker']} {s['expiry']} ({s['dte']}DTE): ToS={s['tos_em']:.3f} | Straddle={s['straddle']:.2f} | Strangle(0.5%)={s['strangle_05']:.2f} | Strangle(1%)={s['strangle_10']:.2f}")
    print()
    
    # Prep matrices for regression: EM = w0 * straddle + w1 * strangle_05 + w2 * strangle_10
    # No-intercept linear regression: Y = X * W
    Y = np.array([s["tos_em"] for s in samples])
    
    # Model A: Multi-term model (straddle, strangle 0.5%, strangle 1.0%)
    X_multi = np.array([[s["straddle"], s["strangle_05"], s["strangle_10"]] for s in samples])
    W_multi, residuals_multi_sum, _, _ = np.linalg.lstsq(X_multi, Y, rcond=None)
    
    # Model B: Simple model (k * straddle)
    X_simple = np.array([[s["straddle"]] for s in samples])
    W_simple, residuals_simple_sum, _, _ = np.linalg.lstsq(X_simple, Y, rcond=None)
    
    # Model C: Multi-term with intercept
    X_multi_int = np.array([[1.0, s["straddle"], s["strangle_05"], s["strangle_10"]] for s in samples])
    W_multi_int, _, _, _ = np.linalg.lstsq(X_multi_int, Y, rcond=None)
    
    # 4. Report Model A (Multi-term, No Intercept)
    print("=======================================================================")
    print("MODEL A: EM = w0 * Straddle + w1 * Strangle(0.5%) + w2 * Strangle(1.0%)  (No Intercept)")
    print("=======================================================================")
    print(f"Weights:")
    print(f"  w0 (Straddle)     : {W_multi[0]:.6f}")
    print(f"  w1 (Strangle 0.5%): {W_multi[1]:.6f}")
    print(f"  w2 (Strangle 1.0%): {W_multi[2]:.6f}")
    print()
    
    residuals_multi = Y - X_multi.dot(W_multi)
    mae_multi = np.mean(np.abs(residuals_multi))
    mape_multi = np.mean(np.abs(residuals_multi) / Y) * 100
    
    print("Residuals per sample:")
    for idx, s in enumerate(samples):
        pred = X_multi[idx].dot(W_multi)
        res = residuals_multi[idx]
        pct_res = (res / s["tos_em"]) * 100
        print(f"  {s['ticker']} {s['expiry']}: Actual={s['tos_em']:7.3f} | Pred={pred:7.3f} | Residual={res:+6.3f} ({pct_res:+5.2f}%)")
    print(f"\nMean Absolute Error (MAE) : {mae_multi:.4f} points")
    print(f"Mean Absolute Pct Error   : {mape_multi:.3f}%")
    print()
    
    # 5. Report Model B (Simple Straddle Multiple, No Intercept)
    print("=======================================================================")
    print("MODEL B: EM = k * Straddle  (No Intercept)")
    print("=======================================================================")
    print(f"Straddle Multiple (k): {W_simple[0]:.6f}")
    print()
    
    residuals_simple = Y - X_simple.dot(W_simple)
    mae_simple = np.mean(np.abs(residuals_simple))
    mape_simple = np.mean(np.abs(residuals_simple) / Y) * 100
    
    print("Residuals per sample:")
    for idx, s in enumerate(samples):
        pred = X_simple[idx].dot(W_simple)
        res = residuals_simple[idx]
        pct_res = (res / s["tos_em"]) * 100
        print(f"  {s['ticker']} {s['expiry']}: Actual={s['tos_em']:7.3f} | Pred={pred:7.3f} | Residual={res:+6.3f} ({pct_res:+5.2f}%)")
    print(f"\nMean Absolute Error (MAE) : {mae_simple:.4f} points")
    print(f"Mean Absolute Pct Error   : {mape_simple:.3f}%")
    print()
    
    # 6. Report Model C (Multi-term with Intercept)
    print("=======================================================================")
    print("MODEL C: EM = intercept + w0 * Straddle + w1 * Strangle(0.5%) + w2 * Strangle(1.0%)")
    print("=======================================================================")
    print(f"Intercept         : {W_multi_int[0]:.6f}")
    print(f"w0 (Straddle)     : {W_multi_int[1]:.6f}")
    print(f"w1 (Strangle 0.5%): {W_multi_int[2]:.6f}")
    print(f"w2 (Strangle 1.0%): {W_multi_int[3]:.6f}")
    print()
    
    residuals_multi_int = Y - X_multi_int.dot(W_multi_int)
    mae_multi_int = np.mean(np.abs(residuals_multi_int))
    mape_multi_int = np.mean(np.abs(residuals_multi_int) / Y) * 100
    
    print("Residuals per sample:")
    for idx, s in enumerate(samples):
        pred = X_multi_int[idx].dot(W_multi_int)
        res = residuals_multi_int[idx]
        pct_res = (res / s["tos_em"]) * 100
        print(f"  {s['ticker']} {s['expiry']}: Actual={s['tos_em']:7.3f} | Pred={pred:7.3f} | Residual={res:+6.3f} ({pct_res:+5.2f}%)")
    print(f"\nMean Absolute Error (MAE) : {mae_multi_int:.4f} points")
    print(f"Mean Absolute Pct Error   : {mape_multi_int:.3f}%")
    print()
    
    # 7. Comparison Summary
    print("=======================================================================")
    print("COMPARISON AND RECOMMENDATION")
    print("=======================================================================")
    print(f"Model A (Multi-term, No Int) MAE: {mae_multi:.4f} points (MAPE: {mape_multi:.2f}%)")
    print(f"Model B (Simple Straddle, No Int) MAE: {mae_simple:.4f} points (MAPE: {mape_simple:.2f}%)")
    print(f"Model C (Multi-term, With Int) MAE: {mae_multi_int:.4f} points (MAPE: {mape_multi_int:.2f}%)")
    print()
    
    diff = mae_simple - mae_multi
    if diff < 0.05 or (mae_simple / mae_multi < 1.05):
        print("RECOMMENDATION: The simple model (EM = k * Straddle) fits nearly as well as the multi-term model.")
        print(f"We should favor the simpler model to prevent overfitting. Suggested Straddle Multiple: k = {W_simple[0]:.4f}")
    else:
        print("RECOMMENDATION: The multi-term model (Model A) provides a significantly better fit.")
        print(f"Fitted weights: EM = {W_multi[0]:.4f}*Straddle + {W_multi[1]:.4f}*Strangle(0.5%) + {W_multi[2]:.4f}*Strangle(1.0%)")

if __name__ == "__main__":
    run_fitting()
