import pandas as pd
import numpy as np
import sys
from pathlib import Path

def main():
    base_dir = Path("data/derived_baseline")
    opt_dir = Path("data/derived")
    
    files = [
        "ib_facts.parquet",
        "ib_ext_detail.parquet",
        "ib_play_detail.parquet",
        "ib_level_touch_detail.parquet",
        "ib_fvg_detail.parquet"
    ]
    
    # Define sort keys for stable comparison
    sort_keys = {
        "ib_facts.parquet": ["symbol", "trading_day", "session_slot", "time_basis"],
        "ib_ext_detail.parquet": ["symbol", "trading_day", "session_slot", "time_basis", "side", "level"],
        "ib_play_detail.parquet": ["symbol", "trading_day", "session_slot", "time_basis", "play"],
        "ib_level_touch_detail.parquet": ["symbol", "trading_day", "session_slot", "time_basis", "level_pct", "phase"],
        "ib_fvg_detail.parquet": ["symbol", "session_slot", "time_basis", "trading_day", "fvg_id", "touch_n"]
    }
    
    print("=== Verification of Parquet Parity ===")
    all_pass = True
    
    for f in files:
        bp = base_dir / f
        op = opt_dir / f
        
        if not bp.exists():
            print(f"[!] Baseline file missing: {bp}")
            all_pass = False
            continue
        if not op.exists():
            print(f"[!] Optimized file missing: {op}")
            all_pass = False
            continue
            
        print(f"\nComparing {f}...")
        df_base = pd.read_parquet(bp)
        df_opt = pd.read_parquet(op)
        
        # Sort values cleanly
        keys = sort_keys[f]
        df_base = df_base.sort_values(by=keys).reset_index(drop=True)
        df_opt = df_opt.sort_values(by=keys).reset_index(drop=True)
        
        # Align columns
        cols = df_base.columns.tolist()
        df_opt = df_opt[cols]
        
        # Check shapes
        if df_base.shape != df_opt.shape:
            print(f"  [X] Shape mismatch! Baseline: {df_base.shape}, Optimized: {df_opt.shape}")
            all_pass = False
            continue
            
        try:
            # Re-cast float types for parity
            for col in df_base.columns:
                if df_base[col].dtype == object:
                    # Fill NaNs/Nones to avoid assert_frame_equal mismatch on object types
                    df_base[col] = df_base[col].fillna("None").astype(str)
                    df_opt[col] = df_opt[col].fillna("None").astype(str)
                elif pd.api.types.is_float_dtype(df_base[col]):
                    # Check matching NaNs
                    df_base[col] = df_base[col].replace({np.nan: None})
                    df_opt[col] = df_opt[col].replace({np.nan: None})
            
            # Using check_exact=False to allow for minor float serialization variances
            pd.testing.assert_frame_equal(df_base, df_opt, check_dtype=False, check_exact=False, atol=1e-5)
            print(f"  [OK] 100% value parity verified for {f} (rows: {len(df_base)}).")
        except AssertionError as e:
            print(f"  [X] Value mismatch in {f}!")
            print(e)
            all_pass = False
            
    if all_pass:
        print("\n[PASSED] All tables match 100% with baseline outputs!")
        sys.exit(0)
    else:
        print("\n[FAILED] Value mismatch or differences detected.")
        sys.exit(1)

if __name__ == "__main__":
    main()
