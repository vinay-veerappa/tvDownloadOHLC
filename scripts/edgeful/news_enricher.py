import pandas as pd
import numpy as np
import sqlite3
import os
from .config import PRISMA_DB_PATH


EVENT_TIMEZONE = 'America/New_York'

def enrich_news(macro_df: pd.DataFrame, prisma_db_path: str = None) -> pd.DataFrame:
    """
    Enriches macro records with economic news context from the Prisma database.
    
    Metrics:
    - news_within_60m: Boolean flag
    - nearest_news_name: Name of the event
    - nearest_news_impact: High, Med, Low
    - nearest_news_dist_m: Time difference in minutes
    """
    if macro_df.empty:
        return macro_df

    # 1. Load Events from Prisma (SQLite)
    db_path = prisma_db_path or str(PRISMA_DB_PATH)
    if not os.path.exists(db_path):
        # Fallback if DB missing
        macro_df['news_within_60m'] = False
        return macro_df

    try:
        conn = sqlite3.connect(db_path)
        # Prisma datetime is big int (ms epoch)
        query = "SELECT datetime, name, impact FROM EconomicEvent"
        events_df = pd.read_sql_query(query, conn)
        conn.close()
        
        events_df['datetime'] = pd.to_datetime(events_df['datetime'], unit='ms', utc=True)
        # Convert event timestamps into Eastern wall-clock time to match macro_start.
        events_df['event_dt'] = (
            events_df['datetime']
            .dt.tz_convert(EVENT_TIMEZONE)
            .dt.tz_localize(None)
            .astype('datetime64[ns]')
        )
    except Exception as e:
        print(f"!! News Enrichment Error (Prisma): {e}")
        return macro_df

    if events_df.empty:
        macro_df['news_within_60m'] = False
        return macro_df

    # 2. Vectorized Proximity Search (merge_asof)
    res_df = macro_df.copy()
    
    # Sort for merge_asof
    res_df['macro_start_temp'] = res_df['macro_start'].dt.tz_localize(None).astype('datetime64[ns]')

    macro_min = res_df['macro_start_temp'].min()
    macro_max = res_df['macro_start_temp'].max()
    event_min = events_df['event_dt'].min()
    event_max = events_df['event_dt'].max()

    if event_max < macro_min or event_min > macro_max:
        print(
            "!! News Enrichment Warning: EconomicEvent coverage does not overlap macro dataset "
            f"(events {event_min} -> {event_max}, macros {macro_min} -> {macro_max})."
        )

    res_df = res_df.sort_values('macro_start_temp')
    events_df = events_df.sort_values('event_dt')
    
    # Nearest News BACKWARD
    res_df = pd.merge_asof(
        res_df,
        events_df[['event_dt', 'name', 'impact']].rename(columns={
            'event_dt': 'prev_news_dt',
            'name': 'prev_news_name',
            'impact': 'prev_news_impact'
        }),
        left_on='macro_start_temp',
        right_on='prev_news_dt',
        direction='backward'
    )
    
    # Nearest News FORWARD
    res_df = pd.merge_asof(
        res_df,
        events_df[['event_dt', 'name', 'impact']].rename(columns={
            'event_dt': 'next_news_dt',
            'name': 'next_news_name',
            'impact': 'next_news_impact'
        }),
        left_on='macro_start_temp',
        right_on='next_news_dt',
        direction='forward'
    )
    
    # Calc distances
    res_df['prev_dist_m'] = (res_df['macro_start_temp'] - res_df['prev_news_dt']).dt.total_seconds() / 60
    res_df['next_dist_m'] = (res_df['next_news_dt'] - res_df['macro_start_temp']).dt.total_seconds() / 60
    
    # Determine Nearest
    mask_next_closer = (res_df['next_dist_m'] < res_df['prev_dist_m'].fillna(999999)) | res_df['prev_dist_m'].isna()
    
    res_df['nearest_news_name'] = np.where(mask_next_closer, res_df['next_news_name'], res_df['prev_news_name'])
    res_df['nearest_news_impact'] = np.where(mask_next_closer, res_df['next_news_impact'], res_df['prev_news_impact'])
    res_df['nearest_news_dist_m'] = np.where(mask_next_closer, res_df['next_dist_m'], res_df['prev_dist_m']).astype(float)
    
    res_df['news_within_60m'] = res_df['nearest_news_dist_m'] <= 60
    
    # Cleanup temps
    cols_to_drop = [
        'macro_start_temp', 'prev_news_dt', 'prev_news_name', 'prev_news_impact',
        'next_news_dt', 'next_news_name', 'next_news_impact', 'prev_dist_m', 'next_dist_m'
    ]
    res_df = res_df.drop(columns=cols_to_drop)
    
    return res_df
