"""
Data Loading Module
===================
Handles ingestion of:
1. TradingView Strategy Exports (.xlsx)
2. Economic News (Prisma SQLite)
3. Profiler Session Data (JSON)
4. Opening Range Stats (JSON)
5. VWAP Data (Parquet)
"""

import pandas as pd
import sqlite3
import json
import os
from datetime import datetime

# Default Paths (Relative to Project Root)
PRISMA_DB = r"web\prisma\dev.db"
PROFILER_JSON = r"data\NQ1_profiler.json"
OPENING_RANGE_JSON = r"data\NQ1_opening_range.json"
VWAP_PARQUET = r"data\indicators\NQ1_1m_vwap.parquet"

def load_strategy_data(filepath, name=None):
    """
    Load and process strategy data from TradingView Excel export.
    Merges Entry and Exit rows to create a single-row-per-trade DataFrame.
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return None

    if name is None:
        name = os.path.basename(filepath)

    try:
        xl = pd.ExcelFile(filepath)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None
    
    # Locate "List of trades"
    sheet = next((s for s in xl.sheet_names if s.lower() == "list of trades"), "List of trades")
    try:
        trade_list = pd.read_excel(xl, sheet_name=sheet)
    except Exception as e:
        print(f"Error reading sheet '{sheet}': {e}")
        return None

    # Helper: Clean duplicate headers if TV export is messy
    trade_list.columns = [c.strip() for c in trade_list.columns]
    
    if 'Date and time' not in trade_list.columns:
        print(f"Error: 'Date and time' column missing in {filepath}")
        return None

    trade_list['Date and time'] = pd.to_datetime(trade_list['Date and time'])
    
    # Entries
    entries = trade_list[trade_list['Type'].str.contains('Entry', case=False, na=False)].copy()
    # Normalize Entry Cols
    # We need: Trade #, Date/Time, Signal, Price
    # Signal col might be 'Signal'
    entries = entries[['Trade #', 'Date and time', 'Signal', 'Price USD']].copy()
    entries.columns = ['Trade #', 'Entry Time', 'Entry Signal', 'Entry Price']
    
    # Exits
    exits = trade_list[trade_list['Type'].str.contains('Exit', case=False, na=False)].copy()
    
    # Cols to keep from Exits (P&L, MFE, MAE)
    wanted_cols = ['Trade #', 'Date and time', 'Type', 'Signal', 'Price USD', 
                   'Net P&L USD', 'Net P&L %', 'MFE USD', 'MFE %', 'MAE USD', 'MAE %', 
                   'Contracts', 'Position size (qty)'] # Added Contracts/Qty
    
    # Robust column selection
    cols_to_use = [c for c in wanted_cols if c in exits.columns]
    exits = exits[cols_to_use].copy()
    
    # Rename
    rename_map = { 'Date and time': 'Exit Time', 'Price USD': 'Exit Price', 'Signal': 'Exit Signal' }
    exits = exits.rename(columns=rename_map, inplace=False)
    
    # Merge
    merged = pd.merge(exits, entries, on='Trade #', how='left')
    merged['Strategy'] = name
    
    # Additional Context
    merged['Entry Time'] = pd.to_datetime(merged['Entry Time'])
    merged['DateStr'] = merged['Entry Time'].dt.strftime('%Y-%m-%d')
    merged['Hour'] = merged['Entry Time'].dt.hour
    merged['Minute'] = merged['Entry Time'].dt.minute
    merged['DayOfWeek'] = merged['Entry Time'].dt.day_name()
    
    # Helper: Quantity/Contracts normalization
    # Some exports have 'Contracts', some 'Position size (qty)'
    if 'Contracts' in merged.columns:
        merged['Qty'] = merged['Contracts']
    elif 'Position size (qty)' in merged.columns:
        merged['Qty'] = merged['Position size (qty)']
    else:
        merged['Qty'] = 1 # Default if missing
        
    return merged

def load_news_events(db_path=PRISMA_DB):
    """Load HIGH IMPACT news from Prisma SQLite."""
    if not os.path.exists(db_path):
        print(f"Warning: News DB not found at {db_path}")
        return pd.DataFrame()
        
    try:
        conn = sqlite3.connect(db_path)
        query = "SELECT datetime, name, impact FROM EconomicEvent WHERE impact='HIGH'"
        news_df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Normalize Timestamps (Handle ms vs s vs string)
        # Try-catch ladder for auto-detection
        try:
            # Try numeric
             news_df['datetime'] = pd.to_numeric(news_df['datetime'])
             # If huge, likely MS
             if news_df['datetime'].mean() > 4e10: # > year 2000 in seconds
                 news_df['datetime'] = pd.to_datetime(news_df['datetime'], unit='ms')
             else:
                 news_df['datetime'] = pd.to_datetime(news_df['datetime'], unit='s')
        except:
             # Fallback to string parse
             news_df['datetime'] = pd.to_datetime(news_df['datetime'])
             
        return news_df
    except Exception as e:
        print(f"Error loading News: {e}")
        return pd.DataFrame()

def load_profiler(json_path=PROFILER_JSON):
    """Load Profiler Session Status."""
    if not os.path.exists(json_path):
        print(f"Warning: Profiler Data not found at {json_path}")
        return pd.DataFrame()
        
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        # Filter for key sessions
        df = df[df['session'].isin(['NY1', 'NY2'])]
        return df
    except Exception as e:
        print(f"Error loading Profiler: {e}")
        return pd.DataFrame()

def load_or_data(json_path=OPENING_RANGE_JSON):
    """Load Opening Range Stats."""
    if not os.path.exists(json_path):
        print(f"Warning: OR Data not found at {json_path}")
        return pd.DataFrame()
        
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        df['DateStr'] = df['date'] # Normalize key
        return df
    except Exception as e:
        print(f"Error loading OR Data: {e}")
        return pd.DataFrame()

def load_vwap(parquet_path=VWAP_PARQUET):
    """Load VWAP Parquet Data."""
    if not os.path.exists(parquet_path):
        print(f"Warning: VWAP Data not found at {parquet_path}")
        return pd.DataFrame()
        
    try:
        df = pd.read_parquet(parquet_path)
        # Ensure 'time' is datetime (parquet often loads as int/ns)
        # Usually internal parquet is 'time' (int32/64) or datetime
        if not pd.api.types.is_datetime64_any_dtype(df['time']):
             df['time'] = pd.to_datetime(df['time'], unit='s')
             
        return df
    except Exception as e:
        print(f"Error loading VWAP: {e}")
        return pd.DataFrame()