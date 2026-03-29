import os
import pandas as pd
import numpy as np
from typing import Optional
import sys

# Ensure project root is in path to import from scripts.utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from scripts.utils.fused_data_loader import load_fused_data as legacy_load, TICKER_MAP, LIVE_DIR, DATA_DIR

# Layer 1: Data Loader with ADR-002 (%-Normalization) and ADR-007 (News Fusion)

class FrameworkLoader:
    """
    Standardized Data Loader for the Statistical Trading Framework.
    Wraps legacy fused_data_loader but enforces framework-specific normalization.
    """
    
    def __init__(self, ticker: str = "NQ1"):
        self.ticker = ticker
        self.raw_data: Optional[pd.DataFrame] = None
        
    def load(self, timeframe: str = "1m", include_historical: bool = True) -> pd.DataFrame:
        """
        Load fused OHLCV data and apply ADR-002 synchronization with robust fusion.
        """
        # 1. Paths
        live_ticker = TICKER_MAP.get(self.ticker, self.ticker)
        live_path = os.path.join(LIVE_DIR, f"live_storage_{live_ticker}.parquet")
        hist_path = os.path.join(DATA_DIR, f"{self.ticker}_{timeframe}.parquet")
        
        dfs = []
        
        # 2. Load and Normalize Individually (Avoid truncation)
        if os.path.exists(live_path):
            df_l = pd.read_parquet(live_path)
            if not df_l.empty:
                df_l['datetime'] = pd.to_datetime(df_l['time'], unit='ms')
                df_l = df_l.set_index('datetime')
                dfs.append(df_l)
        
        if include_historical and os.path.exists(hist_path):
            df_h = pd.read_parquet(hist_path)
            if not df_h.empty:
                df_h.index = pd.to_datetime(df_h.index)
                dfs.append(df_h)

        if not dfs: return pd.DataFrame()
        
        # 3. Fuse and Deduplicate
        df = pd.concat(dfs)
        df = df[~df.index.duplicated(keep='last')]
        df = df.sort_index()

        # 4. Institutional Timezone Normalization (Institutional Standard)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert('US/Eastern').tz_localize(None)

        # 5. ADR-002: Statistical Normalization
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        df['range_pct'] = (df['high'] - df['low']) / df['close'].shift(1)
        df['gap_pct'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        # 6. Clean up schema and remove feature-NaNs
        core_cols = ['open', 'high', 'low', 'close', 'volume', 'returns', 'log_returns', 'range_pct', 'gap_pct']
        df = df[core_cols].dropna()
        
        # 7. Layer 1 Extension: News Fusion
        df = self.fuse_economic_events(df)
        
        self.raw_data = df
        return self.raw_data

    def fuse_economic_events(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        [ADR-007] Inject institutional news context from Prisma DB.
        Connects DB EconomicEvent table to the 1m timeline as distance-to-news features.
        """
        import sqlite3
        
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../web/prisma/dev.db"))
        if not os.path.exists(db_path):
            print(f"Warning: Prisma DB not found at {db_path}. Skipping news fusion.")
            return df
            
        try:
            conn = sqlite3.connect(db_path)
            # Query only HIGH impact events for core filtering
            query = "SELECT datetime, impact FROM EconomicEvent WHERE impact = 'HIGH'"
            events_df = pd.read_sql_query(query, conn)
            conn.close()
            
            if events_df.empty:
                df['is_high_impact_news'] = False
                df['sec_to_news'] = 999999
                return df
                
            # Convert to datetime and sort
            events_df['datetime'] = pd.to_datetime(events_df['datetime'])
            # Ensure timezone parity (Framework uses US/Eastern)
            # Prisma stores as UTC typically or ISO strings. 
            # We assume stored as ISO UTC. Match framework conversion.
            if events_df['datetime'].dt.tz is None:
                events_df['datetime'] = events_df['datetime'].dt.tz_localize('UTC')
            events_df['datetime'] = events_df['datetime'].dt.tz_convert('US/Eastern').dt.tz_localize(None)
            
            event_times = sorted(events_df['datetime'].tolist())
            
            # Efficient Vectorized Mapping for 1m bars
            # 1. Flag exact news bars (or +/- 1 min wrap)
            df['is_high_impact_news'] = df.index.isin(event_times)
            
            # 2. Distance to/from news (Causal Timing)
            # We use searchsorted to find the nearest upcoming/past news
            bar_times = df.index.values
            event_times_np = np.array([t.to_datetime64() for t in event_times])
            
            # Find index of the next event for each bar
            idx = np.searchsorted(event_times_np, bar_times)
            
            # Distance to NEXT news (seconds)
            to_news = np.full(len(df), 999999.0)
            valid_next = idx < len(event_times_np)
            to_news[valid_next] = (event_times_np[idx[valid_next]] - bar_times[valid_next]) / np.timedelta64(1, 's')
            df['sec_to_news'] = to_news
            
            # Distance since PAST news (seconds)
            since_news = np.full(len(df), 999999.0)
            valid_past = idx > 0
            since_news[valid_past] = (bar_times[valid_past] - event_times_np[idx[valid_past]-1]) / np.timedelta64(1, 's')
            df['sec_since_news'] = since_news
            
            print(f"Successfully fused {len(event_times)} institutional news events into timeline.")
            
        except Exception as e:
            print(f"Error during news fusion: {e}")
            df['is_high_impact_news'] = False
            df['sec_to_news'] = 999999
            
        return df
