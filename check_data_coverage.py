import pandas as pd
import os
import glob

DATA_DIR = "data"

def check_coverage():
    output_file = "DATA_COVERAGE_REPORT.md"
    with open(output_file, "w") as out:
        out.write("# Data Coverage Report\n\n")
        out.write("| Ticker | Timeframe | OHLC Start | OHLC End | Volume Start | Volume End | Bars |\n")
        out.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        files = sorted(glob.glob(os.path.join(DATA_DIR, "*.parquet")))
        
        for f in files:
            basename = os.path.basename(f)
            name_parts = os.path.splitext(basename)[0].split('_')
            if len(name_parts) < 2: continue
            
            ticker = name_parts[0]
            timeframe = name_parts[1]
            
            try:
                df = pd.read_parquet(f, columns=['close', 'volume'])
            except:
                continue
                
            if df.empty:
                continue
                
            ohlc_start = df.index.min().strftime('%Y-%m-%d')
            ohlc_end = df.index.max().strftime('%Y-%m-%d')
            count = len(df)
            
            # Volume Range
            if 'volume' in df.columns:
                vol_df = df[df['volume'] > 0]
                if not vol_df.empty:
                    vol_start = vol_df.index.min().strftime('%Y-%m-%d')
                    vol_end = vol_df.index.max().strftime('%Y-%m-%d')
                else:
                    vol_start = "None"
                    vol_end = "None"
            else:
                vol_start = "None"
                vol_end = "None"
                
            out.write(f"| {ticker} | {timeframe} | {ohlc_start} | {ohlc_end} | {vol_start} | {vol_end} | {count} |\n")
            
    print(f"Report written to {output_file}")

if __name__ == "__main__":
    check_coverage()
