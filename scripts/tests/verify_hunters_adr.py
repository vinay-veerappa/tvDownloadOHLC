import pandas as pd
import numpy as np
from pathlib import Path
from scripts.strategies.initial_balance.core.initial_balance_pullback import IBPullbackStrategy
from scripts.strategies.reversal.core.box_reversion import BoxReversionStrategy
from scripts.strategies.reversal.core.mean_reversion import MeanReversionStrategy
from scripts.strategies.reversal.core.six_am_reversal import SixAMReversalStrategy
from scripts.strategies.ema_pullback.core.ema_pullback import EMAPullbackStrategy
from scripts.strategies.vwap_reclaim.core.vwap_reclaim import VWAPReclaimStrategy
from scripts.strategies.failed_auction.core.failed_auction import FailedAuctionStrategy

def verify_strategy(name, strategy_class, data):
    print(f"\n--- Verifying {name} ---")
    try:
        strat = strategy_class()
        
        # 1. Check get_param_grid
        grid = strat.get_param_grid()
        print(f"[OK] get_param_grid() returned {len(grid)} parameters")
        
        # 2. Run hunt()
        signals = strat.hunt(data)
        print(f"[OK] hunt() returned {len(signals)} signals")
        
        if not signals.empty:
            # 3. Verify Schema
            required_cols = ['signal_time', 'direction', 'entry_price', 'stop_price', 'target1_price']
            missing = [c for c in required_cols if c not in signals.columns]
            if not missing:
                print(f"[OK] Schema validation passed")
                print(f"Sample signal:\n{signals.iloc[0]}")
            else:
                print(f"[FAIL] Missing columns: {missing}")
        else:
            print("[WARN] No signals generated for the test period")
            
    except Exception as e:
        print(f"[ERROR] Strategy {name} failed verification: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Load recent NQ data for testing
    data_path = Path("data/NQ1_1m.parquet")
    if not data_path.exists():
        print(f"Error: {data_path} not found")
        exit()
        
    print(f"Loading sample data from {data_path}...")
    full_data = pd.read_parquet(data_path)
    
    # Filter to last 10 days for speed
    last_date = full_data.index.max()
    test_data = full_data[full_data.index > (last_date - pd.Timedelta(days=10))].copy()
    print(f"Testing on {len(test_data)} bars from {test_data.index.min()} to {test_data.index.max()}")
    
    # Run Verifications
    verify_strategy("IB Pullback", IBPullbackStrategy, test_data)
    verify_strategy("Box Reversion", BoxReversionStrategy, test_data)
    verify_strategy("Mean Reversion", MeanReversionStrategy, test_data)
    verify_strategy("EMA Pullback", EMAPullbackStrategy, test_data)
    verify_strategy("VWAP Reclaim", VWAPReclaimStrategy, test_data)
    verify_strategy("Failed Auction", FailedAuctionStrategy, test_data)
    verify_strategy("6 AM Reversal", SixAMReversalStrategy, test_data)
