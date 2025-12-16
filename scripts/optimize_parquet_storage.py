import pandas as pd
from pathlib import Path
import os

def optimize_parquet():
    data_dir = Path("data")
    # Targets that failed
    targets = ["ES1_1m.parquet", "CL1_1m.parquet", "NQ1_1m.parquet"]
    
    for filename in targets:
        path = data_dir / filename
        if not path.exists():
            print(f"Skipping {filename}: Not found")
            continue
            
        old_size = path.stat().st_size / (1024 * 1024)
        print(f"Reading {filename} ({old_size:.2f} MB)...")
        
        try:
            df = pd.read_parquet(path)
            
            # Save with 'brotli' compression (high ratio, slower)
            # Check if pyarrow supports it (standard in modern envs)
            temp_path = path.with_suffix(".temp.parquet")
            
            # Brotli is usually best for static storage. Zstd is good too.
            # trying 'brotli' first.
            df.to_parquet(temp_path, compression='brotli')
            
            new_size = temp_path.stat().st_size / (1024 * 1024)
            reduction = old_size - new_size
            pct = (reduction / old_size) * 100
            
            print(f"  -> Compressed: {new_size:.2f} MB")
            print(f"  -> Reduction: {reduction:.2f} MB ({pct:.1f}%)")
            
            if new_size < 100:
                print("  ✅ Access granted (Under 100MB)")
                
                # Replace original
                path.unlink()
                temp_path.rename(path)
            else:
                print("  ⚠️ Still over 100MB (GitHub Limit)")
                temp_path.unlink() # Discard temp if not useful? 
                # Actually keep it if it's smaller, but warn user.
                # If we keep it, we replace.
                # But let's verify if Brotli actually helps enough.
                # If Brotli doesn't work, we basically must use LFS.
                
        except Exception as e:
            print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    optimize_parquet()
