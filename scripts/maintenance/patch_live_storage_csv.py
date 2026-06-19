import pandas as pd
from pathlib import Path
import glob

source_dir = Path("data/TV_OHLC")
live_dir = Path("data/live")

ticker_map = {
    "CME_MINI_ES1!": "-ES",
    "CME_MINI_NQ1!": "-NQ",
    "CME_MINI_RTY1!": "-RTY",
    "CBOT_MINI_YM1!": "-YM",
    "COMEX_GC1!": "-GC",
    "NYMEX_CL1!": "-CL",
}

def patch_live_storage():
    csv_files = glob.glob(str(source_dir / "*.csv"))
    
    for f in csv_files:
        filename = Path(f).stem
        if ", " not in filename:
            continue
            
        parts = filename.split(", ")
        tv_ticker = parts[0]
        
        if tv_ticker in ticker_map:
            live_symbol = ticker_map[tv_ticker]
        else:
            # Handle standard TV exports like "NASDAQ_AAPL" or "NYSE_SPY"
            if "_" in tv_ticker:
                live_symbol = tv_ticker.split("_")[-1]
            else:
                live_symbol = tv_ticker
                
        live_path = live_dir / f"live_storage_{live_symbol}.parquet"
        
        if not live_path.exists():
            print(f"Live storage not found for {live_symbol}, skipping to prevent creating unlinked files.")
            continue
            
        print(f"\n[SAFE MERGE MODE] Processing {tv_ticker} -> {live_symbol}...")
        
        # Read CSV
        df_csv = pd.read_csv(f)
        
        # Standardize CSV columns
        cols = [c.lower() for c in df_csv.columns]
        df_csv.columns = cols
        
        if "volume" not in df_csv.columns:
            df_csv["volume"] = 0
            
        df_csv = df_csv[["time", "open", "high", "low", "close", "volume"]].copy()
        
        # Format for live_storage
        df_csv["timestamp"] = pd.to_datetime(df_csv["time"], unit="s")
        df_csv["time"] = df_csv["time"] * 1000.0  # ms float64
        
        df_csv["open"] = df_csv["open"].astype(float)
        df_csv["high"] = df_csv["high"].astype(float)
        df_csv["low"] = df_csv["low"].astype(float)
        df_csv["close"] = df_csv["close"].astype(float)
        df_csv["volume"] = df_csv["volume"].astype(int)
        
        # Read live storage
        df_live = pd.read_parquet(live_path)
        
        original_len = len(df_live)
        
        # Merge
        combined = pd.concat([df_live, df_csv], ignore_index=True)
        combined = combined.drop_duplicates(subset=["time"], keep="last")
        combined = combined.sort_values("time")
        
        # Reorder columns to match original
        expected_cols = ["time", "open", "high", "low", "close", "volume", "timestamp"]
        combined = combined[expected_cols]
        
        combined.to_parquet(live_path, index=False)
        print(f"  Merged {len(df_csv)} rows. Total size: {original_len} -> {len(combined)}")

if __name__ == "__main__":
    patch_live_storage()
    print("Done patching live storage!")
