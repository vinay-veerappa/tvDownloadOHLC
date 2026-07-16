import pandas as pd
import numpy as np
import zoneinfo
import duckdb
from pathlib import Path
from .config import STANDARD_MACROS, HYDRA_MACROS, get_1m_path

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.nqstats.sessions import get_trading_date  # noqa: F401 – re-exported for callers

ET_TZ = zoneinfo.ZoneInfo("US/Eastern")


def load_bars_duckdb(instrument: str, start_date=None, end_date=None) -> pd.DataFrame:
    """
    Loads 1m bars from Parquet using DuckDB for high-performance preprocessing.
    Sets 'trading_date' based on institutional 18:00 ET cutoff.
    """
    path = get_1m_path(instrument)
    if not path.exists():
        print(f"  [{instrument}] DataLoader: Path does not exist: {path}")
        return pd.DataFrame()

    print(f"  [{instrument}] DataLoader: Loading from {path}...")
    con = duckdb.connect(database=':memory:')
    con.execute("SET TimeZone='US/Eastern'")
    
    con.execute(f"""
    CREATE OR REPLACE VIEW bars_enriched AS
    WITH standardized AS (
        SELECT 
            CASE 
                WHEN typeof(time) IN ('BIGINT', 'DOUBLE') THEN 
                    CASE WHEN time > 1000000000000 THEN to_timestamp(time::BIGINT / 1000) ELSE to_timestamp(time::BIGINT) END
                ELSE time::TIMESTAMP
            END as dt_utc,
            open, high, low, close, volume
        FROM read_parquet('{str(path).replace('\\', '/')}')
    ),
    localized AS (
        SELECT 
            timezone('US/Eastern', dt_utc AT TIME ZONE 'UTC') as dt_et,
            EXTRACT(HOUR FROM timezone('US/Eastern', dt_utc AT TIME ZONE 'UTC')) as hour_et,
            EXTRACT(MINUTE FROM timezone('US/Eastern', dt_utc AT TIME ZONE 'UTC')) as minute_et,
            isodow(timezone('US/Eastern', dt_utc AT TIME ZONE 'UTC')) as isodow_et,
            open, high, low, close, volume
        FROM standardized
    )
    SELECT 
        dt_et,
        hour_et,
        minute_et,
        CASE 
            WHEN hour_et >= 18 THEN 
                CASE 
                    WHEN isodow_et = 5 THEN (dt_et + INTERVAL 3 DAY)::DATE
                    WHEN isodow_et = 6 THEN (dt_et + INTERVAL 2 DAY)::DATE
                    WHEN isodow_et = 7 THEN (dt_et + INTERVAL 1 DAY)::DATE
                    ELSE (dt_et + INTERVAL 1 DAY)::DATE
                END
            WHEN isodow_et = 6 THEN (dt_et + INTERVAL 2 DAY)::DATE
            WHEN isodow_et = 7 THEN (dt_et + INTERVAL 1 DAY)::DATE
            ELSE dt_et::DATE
        END as trading_date,
        open, high, low, close, volume
    FROM localized
    """)
    
    query = "SELECT * FROM bars_enriched"
    if start_date or end_date:
        filters = []
        if start_date: filters.append(f"trading_date >= '{start_date}'")
        if end_date: filters.append(f"trading_date <= '{end_date}'")
        query += " WHERE " + " AND ".join(filters)
    
    df = con.execute(query).df()
    
    if df.empty:
        return df
        
    df['dt_et'] = pd.to_datetime(df['dt_et'])
    if df['dt_et'].dt.tz is None:
        df['dt_et'] = df['dt_et'].dt.tz_localize('US/Eastern', ambiguous='NaT', nonexistent='shift_forward')
    else:
        df['dt_et'] = df['dt_et'].dt.tz_convert(ET_TZ)
        
    df = df.set_index('dt_et', inplace=False)
    return df

def get_session_bars(df: pd.DataFrame, trading_day) -> pd.DataFrame:
    target_date = pd.to_datetime(trading_day).date()
    return df[df['trading_date'] == target_date]