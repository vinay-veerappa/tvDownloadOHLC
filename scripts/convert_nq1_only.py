
from pathlib import Path
from convert_to_chunked_json import convert_parquet_to_chunked_json

def main():
    data_dir = Path("data")
    output_dir = Path("public/data") # Adjusted to match where scripts expecting it (root relative? No, profile-backtest expects public/data in cwd)
    
    # Check if we are running from root or scripts
    # My cwd is c:\Users\vinay\tvDownloadOHLC
    # public/data is correct.
    
    parquet_path = data_dir / "NQ1_1m.parquet"
    if not parquet_path.exists():
        print(f"Error: {parquet_path} not found")
        return

    print(f"Converting specific file: {parquet_path}")
    convert_parquet_to_chunked_json(parquet_path, output_dir)

if __name__ == "__main__":
    main()
