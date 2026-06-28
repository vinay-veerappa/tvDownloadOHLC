import os
import sys
import argparse
import subprocess
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import io

# Force standard output and error to use utf-8 on Windows to prevent emoji encoding crashes
if sys.platform == 'win32' and not hasattr(sys.stdout, '_wrapped_utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    sys.stdout._wrapped_utf8 = True
if sys.platform == 'win32' and not hasattr(sys.stderr, '_wrapped_utf8'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)
    sys.stderr._wrapped_utf8 = True

# Ensure repository root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.append(root_dir)

DATA_DIR = os.path.join(root_dir, "data")
DERIVED_DIR = os.path.join(DATA_DIR, "derived")
Path(DERIVED_DIR).mkdir(parents=True, exist_ok=True)

def sync_vix_vvix_if_needed():
    """
    Checks if VIX/VVIX daily parquets are up-to-date.
    If not, calls update_via_schwab.py to sync them.
    """
    today = datetime.now().date()
    
    for symbol in ["VIX", "VVIX"]:
        filepath = os.path.join(DATA_DIR, f"{symbol}_1d.parquet")
        need_update = True
        
        if os.path.exists(filepath):
            try:
                df = pd.read_parquet(filepath)
                if not df.empty:
                    last_date = df.index.max().date()
                    # If the data includes today, it's fully up to date
                    if last_date >= today:
                        need_update = False
                    # On weekends (Saturday/Sunday), if last_date is Friday, it's up to date
                    elif today.weekday() in [5, 6] and last_date.weekday() == 4 and (today - last_date).days <= 2:
                        need_update = False
            except Exception as e:
                print(f"Error checking {symbol} date: {e}")
                
        if need_update:
            print(f"🔄 VIX/VVIX daily data is outdated or missing. Triggering Schwab sync for {symbol}...")
            try:
                script_path = os.path.join(root_dir, "scripts", "market_data", "update_via_schwab.py")
                subprocess.run(
                    [sys.executable, script_path, symbol, "--tf", "1d"],
                    check=True
                )
            except Exception as e:
                print(f"Warning: Failed to update {symbol} via Schwab API: {e}", file=sys.stderr)

def generate_friction_matrix(ticker):
    """
    Computes 21 EMA / 200 SMA distances for ticker and joins VIX/VVIX closes.
    """
    ticker = ticker.upper()
    
    # 1. Load VIX and VVIX daily closes
    vix_path = os.path.join(DATA_DIR, "VIX_1d.parquet")
    vvix_path = os.path.join(DATA_DIR, "VVIX_1d.parquet")
    
    if not os.path.exists(vix_path) or not os.path.exists(vvix_path):
        print("Error: VIX or VVIX daily parquet files not found. Cannot compile friction matrix.")
        return None
        
    vix_df = pd.read_parquet(vix_path)[['close']].rename(columns={'close': 'vix_close'})
    vvix_df = pd.read_parquet(vvix_path)[['close']].rename(columns={'close': 'vvix_close'})
    
    # 2. Load Ticker daily history
    ticker_path = os.path.join(DATA_DIR, f"{ticker}_1d.parquet")
    if not os.path.exists(ticker_path):
        print(f"Error: Daily price parquet not found for {ticker} at {ticker_path}")
        return None
        
    df = pd.read_parquet(ticker_path)
    if df.empty or 'close' not in df.columns:
        print(f"Error: Empty or invalid data for {ticker}")
        return None
        
    df = df.sort_index()
    
    # 3. Calculate rolling averages
    ema21 = df['close'].ewm(span=21, adjust=False).mean()
    sma200 = df['close'].rolling(window=200).mean()
    
    df['dist_21_ema_pct'] = (df['close'] - ema21) / ema21
    df['dist_200_sma_pct'] = (df['close'] - sma200) / sma200
    
    # 4. Normalize DatetimeIndex timezones and dates before joining to prevent hourly mismatches
    eastern = ZoneInfo("America/New_York")
    
    for frame in [df, vix_df, vvix_df]:
        # Localize naive DatetimeIndex to UTC first, then convert to US/Eastern
        if frame.index.tz is None:
            frame.index = frame.index.tz_localize(timezone.utc)
        
        # Convert index to US/Eastern string dates
        frame['date_str'] = frame.index.tz_convert(eastern).strftime('%Y-%m-%d')
        
    # Join on normalized date_str index
    df_clean = df[['dist_21_ema_pct', 'dist_200_sma_pct', 'date_str']].set_index('date_str')
    vix_clean = vix_df[['vix_close', 'date_str']].set_index('date_str')
    vvix_clean = vvix_df[['vvix_close', 'date_str']].set_index('date_str')
    
    # Left join VIX and VVIX onto the primary ticker series
    merged = df_clean.join(vix_clean, how='left')
    merged = merged.join(vvix_clean, how='left')
    
    # Drop rows where we have absolutely no EMA/SMA metrics (unmapped dates)
    merged = merged.dropna(subset=['dist_21_ema_pct', 'dist_200_sma_pct'], how='all')
    
    # Add ticker column and date_key
    merged['ticker'] = ticker
    merged['date_key'] = merged.index
    
    # Reorder columns
    result = merged[['date_key', 'ticker', 'dist_21_ema_pct', 'dist_200_sma_pct', 'vix_close', 'vvix_close']]
    return result

def update_centralized_friction_matrix(ticker):
    """
    Compiles metrics and appends them to data/derived/market_friction_matrix.parquet.
    """
    # First, make sure VIX and VVIX are up to date
    sync_vix_vvix_if_needed()
    
    # Generate new friction metrics
    new_metrics = generate_friction_matrix(ticker)
    if new_metrics is None or new_metrics.empty:
        return False
        
    matrix_path = os.path.join(DERIVED_DIR, "market_friction_matrix.parquet")
    
    if os.path.exists(matrix_path):
        try:
            existing_matrix = pd.read_parquet(matrix_path)
            # Ensure date_key is string type for clean deduplication
            existing_matrix['date_key'] = existing_matrix['date_key'].astype(str)
            combined = pd.concat([existing_matrix, new_metrics], ignore_index=True)
            print(f"Merged with existing friction matrix ({len(existing_matrix)} rows).")
        except Exception as e:
            print(f"Warning: Failed to load existing friction matrix: {e}. Rewriting file.")
            combined = new_metrics
    else:
        combined = new_metrics
        
    # Deduplicate and sort
    combined = combined.drop_duplicates(subset=['date_key', 'ticker'], keep='last')
    combined = combined.sort_values(by=['ticker', 'date_key']).reset_index(drop=True)
    
    # Save back
    try:
        combined.to_parquet(matrix_path, index=False)
        print(f"✅ Successfully updated centralized friction matrix at {matrix_path} ({len(combined)} total rows).")
        return True
    except Exception as e:
        print(f"❌ Failed to save friction matrix: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate and update market friction matrix parquet")
    parser.add_argument("--ticker", required=True, help="Ticker symbol (e.g. SPY, QQQ)")
    args = parser.parse_args()
    
    update_centralized_friction_matrix(args.ticker)

if __name__ == "__main__":
    main()
