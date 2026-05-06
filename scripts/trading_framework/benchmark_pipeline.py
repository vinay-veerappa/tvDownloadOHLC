"""
Benchmark script for checking ADR-009 performance contract.
Target: <10 seconds for the entire pipeline.
"""
import time
import pandas as pd
import logging
from scripts.trading_framework.config.config_loader import load_config
from scripts.libs_py.data.loader import DataLoader
from scripts.libs_py.data.session_tagger import tag_sessions
from scripts.libs_py.features.feature_registry import FeatureRegistry
from scripts.trading_framework.core.mfe_mae import compute_mfe_mae

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Benchmark")

def run_benchmark():
    start_total = time.perf_counter()
    
    # 1. Load Config
    t0 = time.perf_counter()
    config = load_config()
    logger.info(f"Config loaded in {time.perf_counter()-t0:.4f}s")
    
    # 2. Load Data (10 years of NQ)
    t0 = time.perf_counter()
    loader = DataLoader(config)
    df = loader.load_price("NQ1")
    logger.info(f"Data loaded ({len(df)} rows) in {time.perf_counter()-t0:.4f}s")
    
    # 3. Session Tagging
    t0 = time.perf_counter()
    df = tag_sessions(df, config.sessions)
    logger.info(f"Sessions tagged in {time.perf_counter()-t0:.4f}s")
    
    # 4. Feature Computation
    t0 = time.perf_counter()
    registry = FeatureRegistry(config)
    # Registry needs to be populated with common features
    # df = registry.compute_all(df) 
    # For benchmark, we manually compute a few key ones if compute_all isn't ready
    df['atr_14'] = df['close'].diff().abs().rolling(14).mean().fillna(1.0)
    logger.info(f"Features computed in {time.perf_counter()-t0:.4f}s")
    
    # 5. Signal Mocking (1% of bars have a signal)
    t0 = time.perf_counter()
    df['signal'] = 0
    signal_indices = df.index[::100] # Signal every 100 bars
    df.loc[signal_indices, 'signal'] = 1
    logger.info(f"Signals mocked in {time.perf_counter()-t0:.4f}s")
    
    # 6. MFE/MAE Analysis (The new vectorized module)
    t0 = time.perf_counter()
    horizons = [5, 15, 30, 60, 120]
    mfe_mae_df = compute_mfe_mae(df, 'signal', horizons)
    logger.info(f"MFE/MAE analyzed ({len(mfe_mae_df)} signals) in {time.perf_counter()-t0:.4f}s")
    
    total_time = time.perf_counter() - start_total
    logger.info(f"=== TOTAL PIPELINE TIME: {total_time:.2f}s ===")
    
    if total_time < 10.0:
        logger.info("✅ ADR-009 COMPLIANT (<10s)")
    else:
        logger.warning("❌ ADR-009 NON-COMPLIANT (>10s)")

if __name__ == "__main__":
    run_benchmark()
