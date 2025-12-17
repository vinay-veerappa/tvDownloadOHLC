
import argparse
import subprocess
import os
import sys

# Mapping Logic
CONCEPTS = {
    "sweep": "bias_liquidity_sweep.py",
    "displacement": "bias_displacement.py",
    "fvg": "bias_fvg_rejection.py",
    "mechanical": "bias_mechanical.py",
    "nysession": "bias_ny_session.py",
    "magnet": "bias_magnet_trend.py",
    "asiavol": "bias_asia_volatility.py",
    "p12": "bias_p12_levels.py",
    "matrix": "bias_probability_matrix.py"
}

def run_test(concept, ticker):
    if concept not in CONCEPTS:
        print(f"Error: Unknown concept '{concept}'. Available: {list(CONCEPTS.keys())}")
        return
    
    script_name = CONCEPTS[concept]
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    
    if not os.path.exists(script_path):
        print(f"Error: Script {script_name} not found in {os.path.dirname(script_path)}")
        return
        
    print(f"Running {concept} analysis for {ticker}...")
    print("-" * 50)
    
    try:
        # Run subprocess
        result = subprocess.run(
            [sys.executable, script_path, ticker],
            capture_output=False, # Stream to stdout
            text=True
        )
        if result.returncode != 0:
            print(f"\nError running script. Exit code: {result.returncode}")
    except Exception as e:
        print(f"Execution failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ICT Bias Backtests")
    parser.add_argument("concept", help=f"Concept to test: {list(CONCEPTS.keys())}")
    parser.add_argument("ticker", nargs="?", default="NQ1", help="Ticker symbol (default: NQ1)")
    
    args = parser.parse_args()
    run_test(args.concept, args.ticker)
