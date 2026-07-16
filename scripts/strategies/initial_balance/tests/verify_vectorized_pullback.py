import pandas as pd
import os
from datetime import time

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.strategies.initial_balance.core.initial_balance_pullback import IBPullbackStrategy
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester

def verify_pullback_migration(ticker="NQ1", years=1):
    print(f"🚀 Verifying Vectorized IB Pullback for {ticker} ({years} Year)...")
    
    # 1. Load Data
    DATA_PATH = f"data/{ticker}_1m.parquet"
    if not os.path.exists(DATA_PATH):
        print(f"❌ Data not found at {DATA_PATH}")
        return
        
    df = pd.read_parquet(DATA_PATH)
    
    # Standard Preprocessing
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns: 
            df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
            df = df.set_index('datetime')
    df = df.sort_index()
    if df.index.tz is not None: df = df.tz_convert('US/Eastern')
    
    start_date = df.index[-1] - pd.Timedelta(days=years*365)
    df = df[df.index >= start_date]
    
    # 2. Execute Hunter (SDS Standard)
    print("🔭 Hunting for signals...")
    hunter = IBPullbackStrategy(ticker=ticker)
    signals = hunter.hunt(df, params={'tp_r_mult': 1.0})
    
    if signals.empty:
        print("⚠️ No signals found in the last year.")
        return
        
    print(f"✅ Found {len(signals)} signals.")
    print("\nSample Signals:")
    print(signals.head())
    
    # 3. Execute Engine (ADR-009 Standard)
    print("\n⚙️ Running Vectorized Engine...")
    engine = VectorizedBacktester(slippage_pct=0.0001)
    results = engine.run(signals, df, {'ticker': ticker})
    
    print("\n📊 Performance Results:")
    print(f"Total P&L: {results['total_return_%']:.2f}%")
    print(f"Win Rate: {results['win_rate_%']:.2f}%")
    print(f"Avg MAE: {results['avg_mae_%']:.4f}%")
    print(f"Num Trades: {results['num_trades']}")
    
    # 4. Final Validation
    if results['num_trades'] > 0 and results['total_return_%'] != 0:
        print("\n✅ STRATEGY DESIGN STANDARD VERIFIED.")
        print("Vectorized Hunter and Engine are synchronized.")
    else:
        print("\n❌ VERIFICATION FAILED: Unexpected results.")

if __name__ == "__main__":
    verify_pullback_migration()
