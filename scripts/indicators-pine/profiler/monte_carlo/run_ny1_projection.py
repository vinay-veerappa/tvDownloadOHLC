import sys
import os

# Add the directory containing monte_carlo_engine to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monte_carlo_engine import MonteCarloProjection

def main():
    print("Starting Monte Carlo Projection for NY1 Session...")
    
    # Configuration for NY1 (07:30 - 08:30) projecting to 16:00
    config = {
        "ticker": "NQ",
        "range_name": "NY1",
        "timezone": "America/New_York",
        "range_start": "07:30",
        "range_end": "08:30",
        "projection_end": "16:00",
        # "reference_type": "Range Mid", # Using Mid as per typical Profiler bias logic
        "reference_type": "Range Mid",
        "simulations": 10000,
        "timeframe": "5min",
        "percentiles": [5, 10, 25, 50, 75, 90, 95],
        # "start_date": "2024-01-01" # Optional: Limit history
    }
    
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, "../../../data/NQ1_1m.parquet")
    output_dir = os.path.join(base_dir, "output")
    
    pine_path = os.path.join(output_dir, "mc_bands_NQ_NY1.pine")
    img_path = os.path.join(output_dir, "mc_diagnostics_NQ_NY1.png")
    
    # Execute
    try:
        mc = MonteCarloProjection(data_path, config)
        mc.extract_ranges()
        mc.run_simulation()
        
        # Generate Outputs
        mc.generate_pinescript(pine_path)
        mc.plot_diagnostics(img_path)
        mc.export_stats(os.path.join(output_dir, "mc_stats_NQ_NY1.csv"))
        mc.generate_report(os.path.join(output_dir, "mc_report_NQ_NY1.md"))
        
        print("\nSUCCESS!")
        print(f"Chart: {img_path}")
        print(f"Pine Script: {pine_path}")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
