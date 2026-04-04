import os
import pandas as pd
import numpy as np
import sys
import argparse
from datetime import datetime

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from scripts.utils.fused_data_loader import DERIVED_DIR, REGIME_DIR, TICKER_MAP
from scripts.libs.data.loader import FrameworkLoader
from scripts.trading_framework.library.adapters.nqstats_adapter import NQStatsAdapter
from scripts.libs.regime.regime_models import HMMRegimeModel, GMMRegimeModel, ThresholdRegimeModel

def sync_features(ticker: str = "NQ1", force: bool = False):
    """
    Regenerates and persists all stationary features for a ticker.
    Fulfills ADR-008: Calculate Once, Persist Everywhere.
    """
    print(f"\n--- Starting Feature Sync for {ticker} ---")
    
    try:
        # 1. Load Base Data (OHLCV + News)
        loader = FrameworkLoader(ticker=ticker)
        df = loader.load(include_historical=True)
        if df.empty:
            print(f"Error: No data found for {ticker}")
            return

        feature_dfs = []

        # 2. Extract NQStats Features (Session Boxes, ALN, Mids)
        print(f"[{ticker}] Extracting NQStats features...")
        nq_features = NQStatsAdapter.get_box_features(df, ticker=ticker)
        feature_dfs.append(nq_features)

        # 3. Compute Regime Features (Modular)
        regime_models = [
            HMMRegimeModel(n_regimes=3),
            HMMRegimeModel(n_regimes=4),
            GMMRegimeModel(n_clusters=3),
            ThresholdRegimeModel()
        ]

        for model in regime_models:
            feat_name = model.get_feature_name()
            print(f"[{ticker}] Computing regime: {feat_name}...")
            regimes = model.predict_regime(df)
            feature_dfs.append(pd.DataFrame({feat_name: regimes}, index=df.index))

        # 4. Merge all features
        all_features = pd.concat(feature_dfs, axis=1)
        
        # 5. Save to Centralized Store
        if not os.path.exists(DERIVED_DIR):
            os.makedirs(DERIVED_DIR)
            
        output_path = os.path.join(DERIVED_DIR, f"{ticker}_features_1m.parquet")
        
        # Overwrite the stationary "truth".
        all_features.to_parquet(output_path, compression='snappy')
        
        print(f"[{ticker}] Successfully persisted {len(all_features.columns)} features to {output_path}")
    except Exception as e:
        print(f"[{ticker}] Sync FAILED: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync Derived Features")
    parser.add_argument("--ticker", type=str, default="ALL", help="Ticker to sync or 'ALL'")
    parser.add_argument("--force", action="store_true", help="Force overwrite")
    args = parser.parse_args()
    
    if args.ticker == "ALL":
        target_tickers = ["ES1", "NQ1", "RTY1", "YM1", "CL1", "GC1"]
        print(f"Bulk syncing all futures: {target_tickers}")
        for t in target_tickers:
            sync_features(ticker=t, force=args.force)
    else:
        sync_features(ticker=args.ticker, force=args.force)
