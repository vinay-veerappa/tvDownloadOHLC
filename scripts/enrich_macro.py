import pandas as pd
import sqlite3
import os
import glob
from datetime import datetime
import pytz

# Paths
BASE_DIR = r"c:\Users\vinay\tvDownloadOHLC"
MACRO_FILE = os.path.join(BASE_DIR, "processed", "macro_records.parquet")
VIX_FILE = os.path.join(BASE_DIR, "data", "VIX_1m.parquet")
VVIX_FILE = os.path.join(BASE_DIR, "data", "VVIX_1m.parquet")
DB_FILE = os.path.join(BASE_DIR, "web", "prisma", "dev.db")
ENHANCED_CSV_DIR = os.path.join(BASE_DIR, "docs", "research", "ict", "data")
OUTPUT_FILE = os.path.join(BASE_DIR, "processed", "macro_enriched.parquet")

def get_vix_open(vix_df, dates):
    """Get VIX price at 9:30 ET for each date."""
    # Ensure index is datetime and localized to UTC if it's not
    if vix_df.index.tz is None:
        vix_df.index = vix_df.index.tz_localize('UTC')
    
    # Convert to US/Eastern
    vix_et = vix_df.index.tz_convert('US/Eastern')
    vix_df['et_datetime'] = vix_et
    vix_df['date'] = vix_et.date
    vix_df['time'] = vix_et.time
    
    results = {}
    for d in dates:
        # Search for 09:30:00 on this date
        day_data = vix_df[vix_df['date'] == d]
        if day_data.empty:
            results[d] = None
            continue
            
        # Try to find exactly 09:30
        open_bar = day_data[day_data['time'] >= datetime.strptime("09:30:00", "%H:%M:%S").time()].head(1)
        if not open_bar.empty:
            results[d] = open_bar['close'].iloc[0]
        else:
            results[d] = None
            
    return results

def get_economic_events(db_path, dates):
    """Get high/med impact event counts per day."""
    if not os.path.exists(db_path):
        print(f"Warning: DB not found at {db_path}")
        return {}
        
    conn = sqlite3.connect(db_path)
    
    # Dates in Prisma are usually ISO strings or UTC timestamps
    # SQLite DATE() function can help
    query = """
    SELECT DATE(datetime) as date, impact, COUNT(*) as count 
    FROM EconomicEvent 
    GROUP BY DATE(datetime), impact
    """
    df_events = pd.read_sql_query(query, conn)
    conn.close()
    
    results = {}
    for d in dates:
        d_str = d.strftime("%Y-%m-%d")
        day_events = df_events[df_events['date'] == d_str]
        
        high = day_events[day_events['impact'] == 'HIGH']['count'].sum()
        med = day_events[day_events['impact'] == 'MEDIUM']['count'].sum()
        
        results[d] = {
            'high_impact_news': int(high) if not pd.isna(high) else 0,
            'med_impact_news': int(med) if not pd.isna(med) else 0
        }
    return results

def get_ict_scenarios(csv_dir, ticker, dates):
    """Load enhanced CSV and join scenario fields."""
    pattern = f"trading_days_enhanced_{ticker}.csv"
    csv_path = os.path.join(csv_dir, pattern)
    
    if not os.path.exists(csv_path):
        print(f"Warning: Enhanced CSV not found for {ticker} at {csv_path}")
        return pd.DataFrame()
        
    df_csv = pd.read_csv(csv_path)
    # The csv has a 'date' column in YYYY-MM-DD
    df_csv['trading_date'] = pd.to_datetime(df_csv['date']).dt.date
    
    # Keep relevant columns
    cols = ['trading_date', 'pattern', 'manipulation', 'ny_position']
    return df_csv[cols]

def main():
    if not os.path.exists(MACRO_FILE):
        print("Error: No macro records found. Run download logic first.")
        return

    print("Loading macro records...")
    df_macro = pd.read_parquet(MACRO_FILE)
    df_macro['trading_date'] = pd.to_datetime(df_macro['trading_date']).dt.date
    unique_dates = df_macro['trading_date'].unique()
    
    # 1. VIX/VVIX Enrichment
    print("Enriching with VIX/VVIX data...")
    if os.path.exists(VIX_FILE):
        vix_df = pd.read_parquet(VIX_FILE)
        vix_opens = get_vix_open(vix_df, unique_dates)
        df_macro['vix_open'] = df_macro['trading_date'].map(vix_opens)
    
    if os.path.exists(VVIX_FILE):
        vvix_df = pd.read_parquet(VVIX_FILE)
        vvix_opens = get_vix_open(vvix_df, unique_dates)
        df_macro['vvix_open'] = df_macro['trading_date'].map(vvix_opens)

    # 2. Economic Events Enrichment
    print("Enriching with Economic Events...")
    events_data = get_economic_events(DB_FILE, unique_dates)
    df_macro['high_impact_news'] = df_macro['trading_date'].apply(lambda d: events_data.get(d, {}).get('high_impact_news', 0))
    df_macro['med_impact_news'] = df_macro['trading_date'].apply(lambda d: events_data.get(d, {}).get('med_impact_news', 0))

    # 3. ICT Scenario Enrichment (Ticker-specific)
    print("Enriching with ICT scenarios...")
    enriched_dfs = []
    for ticker, group in df_macro.groupby('ticker'):
        df_inst = get_ict_scenarios(ENHANCED_CSV_DIR, ticker, unique_dates)
        if not df_inst.empty:
            group = group.merge(df_inst, on='trading_date', how='left')
        else:
            group['pattern'] = None
            group['manipulation'] = None
            group['ny_position'] = None
        enriched_dfs.append(group)
    
    df_final = pd.concat(enriched_dfs)
    
    # Final cleanup
    print(f"Saving enriched records to {OUTPUT_FILE}...")
    df_final.to_parquet(OUTPUT_FILE, index=False)
    print("Done!")
    print(df_final[['trading_date', 'ticker', 'vix_open', 'high_impact_news', 'pattern']].head())

if __name__ == "__main__":
    main()
