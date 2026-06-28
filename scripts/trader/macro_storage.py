import os
import sys
import sqlite3
import argparse
import numpy as np
import pandas as pd
import pytz
from datetime import datetime, timezone
from pathlib import Path
import io

# Force standard output and error to use utf-8 on Windows to prevent emoji encoding crashes
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)

# Ensure repository root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.append(root_dir)

DB_PATH = os.path.join(root_dir, "web", "prisma", "dev.db")
DATA_DIR = os.path.join(root_dir, "data")
EASTERN = pytz.timezone("US/Eastern")

def get_et_date_str(timestamp_ms):
    dt_utc = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
    dt_et = dt_utc.astimezone(EASTERN)
    return dt_et.strftime("%Y-%m-%d")

def calculate_volatility_features(ticker):
    """
    Loads daily prices, computes 20-day annualized realized volatility,
    and returns a DataFrame indexed by YYYY-MM-DD date string.
    """
    parquet_path = os.path.join(DATA_DIR, f"{ticker}_1d.parquet")
    if not os.path.exists(parquet_path):
        print(f"Error: Parquet file not found at {parquet_path}")
        return None

    df = pd.read_parquet(parquet_path)
    if df.empty or 'close' not in df.columns:
        print(f"Error: Empty or invalid data in {parquet_path}")
        return None

    # Sort index to ensure chronological order
    df = df.sort_index()

    # Compute daily log returns
    df['log_ret'] = np.log(df['close'] / df['close'].shift(1))

    # Compute 20-day annualized historical realized volatility (standard deviation * sqrt(252))
    df['hv_20d'] = df['log_ret'].rolling(20).std() * np.sqrt(252)

    # Map DatetimeIndex to US/Eastern date string YYYY-MM-DD
    # Schwab/yfinance dates are usually daily closes, which might be stored with various timezone formats.
    # Convert index to US/Eastern timezone to be absolutely safe
    if df.index.tz is None:
        df.index = df.index.tz_localize(timezone.utc)
    
    df['date_key'] = df.index.tz_convert(EASTERN).strftime("%Y-%m-%d")
    
    return df.set_index('date_key')[['close', 'hv_20d']]

def process_volatility_storage(ticker, target_date_str=None, backfill=False):
    """
    Calculates 20d HV and VRP and writes back to MacroSnapshot table in SQLite.
    """
    print(f"⚡ Running Volatility & VRP storage engine for {ticker}...")
    
    # Calculate historical vol series
    vol_df = calculate_volatility_features(ticker)
    if vol_df is None or vol_df.empty:
        return False

    if not os.path.exists(DB_PATH):
        print(f"Error: Prisma database not found at {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Fetch all snapshots for the ticker to do localized timezone comparison in python
        cursor.execute(
            "SELECT id, tradingDate, put25dIv, call25dIv FROM MacroSnapshot WHERE ticker = ?",
            (ticker,)
        )
        rows = cursor.fetchall()
        if not rows:
            print(f"No MacroSnapshot rows found for ticker {ticker} in DB.")
            conn.close()
            return False

        updated_count = 0
        for row in rows:
            row_id, trading_date_ms, put_iv, call_iv = row
            row_date_str = get_et_date_str(trading_date_ms)
            
            # Filter condition
            if not backfill:
                if target_date_str and row_date_str != target_date_str:
                    continue
                elif not target_date_str:
                    # Default to latest row in DB if not specifying target_date and not backfilling
                    latest_db_ms = max(r[1] for r in rows)
                    if trading_date_ms != latest_db_ms:
                        continue
            
            # Check if we have volatility data for this date
            if row_date_str not in vol_df.index:
                print(f"  [Skip] No daily price data available for {row_date_str}")
                continue

            hv_val = vol_df.loc[row_date_str, 'hv_20d']
            if pd.isna(hv_val):
                print(f"  [Skip] HV is NaN for {row_date_str} (likely insufficient rolling window)")
                continue

            # Resolve ATM IV (average of call & put 25d IV, or fallback if one is missing)
            atm_iv = None
            if put_iv is not None and call_iv is not None:
                atm_iv = (put_iv + call_iv) / 2.0
            elif put_iv is not None:
                atm_iv = put_iv
            elif call_iv is not None:
                atm_iv = call_iv
            
            if atm_iv is None:
                print(f"  [Warning] Missing both call25dIv and put25dIv for {row_date_str}. VRP cannot be computed.")
                vrp_val = None
            else:
                # Compute VRP = ATM IV - HV
                vrp_val = atm_iv - float(hv_val)

            # Perform SQLite UPDATE
            cursor.execute(
                """
                UPDATE MacroSnapshot 
                SET historical_vol_20d = ?, volatility_risk_premium = ? 
                WHERE id = ?
                """,
                (float(hv_val), vrp_val, row_id)
            )
            updated_count += 1
            print(f"  [Update] {row_date_str} -> HV: {hv_val*100:.2f}%, VRP: {f'{vrp_val*100:.2f}%' if vrp_val is not None else 'N/A'}")

        conn.commit()
        conn.close()
        print(f"✅ Successfully updated {updated_count} MacroSnapshot rows in Prisma DB.")
        return True

    except Exception as e:
        print(f"❌ Database error: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="End-of-Session Daily Options Volatility & VRP Caching")
    parser.add_argument("--ticker", required=True, help="Ticker symbol (e.g. SPY, QQQ)")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format (defaults to latest)")
    parser.add_argument("--backfill", action="store_true", help="Calculate and backfill all historical snapshots in DB")
    args = parser.parse_args()

    # Normalise ticker to upper case
    ticker = args.ticker.upper()
    
    process_volatility_storage(ticker, target_date_str=args.date, backfill=args.backfill)

if __name__ == "__main__":
    main()
