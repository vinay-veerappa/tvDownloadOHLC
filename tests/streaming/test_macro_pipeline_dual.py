import logging
import sys
import os

# Add the scripts directory to path to allow absolute imports within the package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.streaming.options.macro_pipeline import run_macro_pipeline

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    # Get tickers from command line if provided, otherwise default
    if len(sys.argv) > 1:
        # Check if first arg is --tickers and use next arg, or just use all args
        if sys.argv[1] == "--tickers" and len(sys.argv) > 2:
            tickers = sys.argv[2].split(",")
        else:
            tickers = sys.argv[1].split(",")
    else:
        tickers = ["SPX"]
        
    print(f"Running macro pipeline for: {tickers}")
    try:
        run_macro_pipeline(tickers, force_refresh=True)
        print("Pipeline run complete.")
    except Exception as e:
        print(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
