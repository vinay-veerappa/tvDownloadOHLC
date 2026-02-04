
import pandas as pd
import matplotlib.pyplot as plt
import os

# Configuration
CSV_PATH = r"c:\Users\vinay\tvDownloadOHLC\scripts\profiler\monte_carlo\output\mc_stats_NQ_NY1.csv"
OUTPUT_IMG = r"c:\Users\vinay\tvDownloadOHLC\scripts\profiler\monte_carlo\output\verification_plot.png"
BASE_PRICE = 20000.0
PM_SCALE = 10.0

def verify_calculations():
    print(f"Loading data from {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    
    # Filter for BULL p95 and BEAR p95 (as examples)
    bull_data = df[df['type'] == 'BULL'].sort_values('bar')
    bear_data = df[df['type'] == 'BEAR'].sort_values('bar')
    
    # Lists to store plotted points
    bull_prices = []
    bear_prices = []
    
    # We need to simulate the "Smooth" and "Re-anchor" logic if possible, 
    # but for raw verification, we'll just take the raw CSV values as "Model Output".
    # In Pine, user uses 'pm_scale' to scale these values.
    
    # Logic:
    # val_h = model_val * pm_scale
    # p_h = base_p * (1.0 + val_h / 100.0)
    
    print("\n--- Verification Sample (BULL p95) ---")
    print(f"Base Price: {BASE_PRICE}")
    print(f"PM Scale: {PM_SCALE}")
    print(f"{'Bar':<5} | {'Raw (p95)':<12} | {'Scaled (%)':<12} | {'Final Price':<12}")
    
    for _, row in bull_data.iterrows():
        bar_idx = int(row['bar'])
        raw_val = row['p95'] # distinct column
        
        # NOTE: The CSV values are Likelihoods or similar? 
        # Looking at CSV: "0.00118" for p95 at bar 0.
        # This is 0.118%.
        
        # Interpretation 1: The model assumes these ARE percentages (0.01 = 1%).
        # If csv has 0.00118, that is 0.118%. 
        # So in Pine: val_h = 0.00118 * 10 = 0.0118 (1.18%).
        # p_h = 20000 * (1 + 0.0118/100) = 20000 * 1.000118 = 20002.36.
        # Wait, that's very small for a "High" projection.
        
        # Interpretation 2: The CSV values are decimal returns (0.01 = 1%).
        # Then we should convert to percent multiply by 100?
        # Pine script usually expects 1.0 to be 1%.
        
        # In the existing Pine logic:
        # float val_h = array.get(h_smooth, i) 
        # val_h := val_h * pm_scale
        # float p_h = base_p * (1.0 + val_h / 100.0)
        
        # If the array in Pine contains these raw CSV values (e.g. 0.00118),
        # And we perform: 0.00118 * 10 / 100 = 0.000118.
        # Then price moves from 20000 to 20002.
        
        # If the array in Pine *already* multiplied them by 100 to be "Percent"
        # (e.g. 0.118), then:
        # 0.118 * 10 / 100 = 0.0118.
        # Price moves from 20000 to 20236. This feels more correct for a volatile asset like NQ.
        
        # IMPORTANT: We need to know if the Pine Script *Data array* is 
        # decimals (0.001) or percents (0.1).
        
        # Assuming Data is Raw Decimal from CSV:
        # To get meaningful moves, we might need to treat them as Percent?
        # Or maybe pm_scale needs to be really big?
        
        # Let's Calculate
        val_scaled = raw_val * PM_SCALE # 0.00118 * 10 = 0.0118
        final_price = BASE_PRICE * (1.0 + val_scaled / 100.0)
        
        bull_prices.append(final_price)
        
        if bar_idx % 15 == 0:
            print(f"{bar_idx:<5} | {raw_val:<12.6f} | {val_scaled:<12.6f} | {final_price:<12.2f}")

    # Plot
    plt.figure(figsize=(10, 6))
    plt.plot(bull_prices, label='Bull p95 Projection', color='blue')
    # plt.plot(bear_prices, label='Bear p95 Projection', color='red') # Add bear logic similarly
    
    plt.title(f"Simulated Price Model (Scale={PM_SCALE})")
    plt.xlabel("Bar Index")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(True)
    plt.savefig(OUTPUT_IMG)
    print(f"\nPlot saved to {OUTPUT_IMG}")

if __name__ == "__main__":
    verify_calculations()
