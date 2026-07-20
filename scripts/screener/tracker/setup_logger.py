"""
setup_logger.py
===============
DuckDB setup logger engine.
Persists screened candidates to DuckDB (data/screener_setups.duckdb) with strategy versioning,
config hashes, and survivorship bias flags for forward performance tracking.
"""
import os
import uuid
from datetime import datetime, timezone
import logging
import pandas as pd
from pathlib import Path

try:
    import duckdb
except ImportError:
    duckdb = None

log = logging.getLogger("screener_tracker")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DUCKDB_PATH = REPO_ROOT / "data" / "screener_setups.duckdb"


def init_duckdb_schema(con):
    """Initializes screener_setups table schema in DuckDB."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS screener_setups (
            setup_id VARCHAR PRIMARY KEY,
            timestamp_utc TIMESTAMP NOT NULL,
            ticker VARCHAR NOT NULL,
            strategy_id VARCHAR NOT NULL,
            strategy_version VARCHAR NOT NULL,
            config_hash VARCHAR NOT NULL,
            market_regime VARCHAR,
            entry_close_price DOUBLE NOT NULL,
            adr_20_pct DOUBLE,
            dist_10ema_pct DOUBLE,
            rvol_20 DOUBLE,
            survivorship_bias_flag BOOLEAN NOT NULL,
            forward_return_5d DOUBLE,
            forward_return_10d DOUBLE,
            forward_return_20d DOUBLE
        );
    """)


def log_setups_to_duckdb(matches: pd.DataFrame, db_path: str = None) -> int:
    """
    Persists matched setup rows into DuckDB.
    Returns count of logged rows.
    """
    if matches is None or matches.empty or duckdb is None:
        return 0

    target_path = str(db_path or DEFAULT_DUCKDB_PATH)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    try:
        con = duckdb.connect(target_path)
        init_duckdb_schema(con)
        
        now_utc = datetime.now(timezone.utc)
        logged_count = 0

        for _, row in matches.iterrows():
            setup_id = uuid.uuid4().hex
            ticker = str(row.get("ticker", "UNKNOWN"))
            strat_id = str(row.get("strategy_id", "custom"))
            strat_ver = str(row.get("strategy_version", "1.0.0"))
            cfg_hash = str(row.get("config_hash", "00000000"))
            regime = str(row.get("market_regime", "BULL_EXPLOSIVE"))
            close_price = float(row.get("close", 0.0) or row.get("Close", 0.0) or row.get("price", 0.0))
            adr_pct = float(row.get("adr_20_pct", 0.0) or 0.0)
            dist_10ema = float(row.get("dist_10ema_pct", 0.0) or 0.0)
            rvol = float(row.get("rvol_20", 1.0) or 1.0)
            survivorship_flag = True # Default True when screening static current constituent universe

            con.execute("""
                INSERT INTO screener_setups (
                    setup_id, timestamp_utc, ticker, strategy_id, strategy_version,
                    config_hash, market_regime, entry_close_price, adr_20_pct,
                    dist_10ema_pct, rvol_20, survivorship_bias_flag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, [
                setup_id, now_utc, ticker, strat_id, strat_ver,
                cfg_hash, regime, close_price, adr_pct,
                dist_10ema, rvol, survivorship_flag
            ])
            logged_count += 1

        con.close()
        log.info(f"Successfully logged {logged_count} setups to DuckDB at {target_path}")
        return logged_count
    except Exception as e:
        log.error(f"Failed to log setups to DuckDB: {e}")
        return 0
