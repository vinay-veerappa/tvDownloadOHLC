"""Isolated 3-Bank SQLite Database Engine for Mickey & Austin Wargaming

Manages three decoupled, isolated SQLite databases under `data/wargaming/db/`:
1. `mickey_ground_truth.sqlite`: Master expert intelligence mined from NotebookLM / YouTube.
2. `system_wargames.sqlite`: Automated pre-market AI predictions with zero look-ahead data.
3. `market_actuals.sqlite`: 100% mechanical EOD tape facts captured at 16:15 EST.

Usage:
    from scripts.wargaming.wargame_db import (
        init_all_databases,
        save_mickey_ground_truth,
        save_system_wargame,
        save_market_actuals,
        query_session_triad,
    )
"""
from __future__ import annotations

import sys
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, date

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DB_DIR = REPO_ROOT / "data" / "wargaming" / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)

MICKEY_DB_PATH = DB_DIR / "mickey_ground_truth.sqlite"
SYSTEM_DB_PATH = DB_DIR / "system_wargames.sqlite"
ACTUALS_DB_PATH = DB_DIR / "market_actuals.sqlite"

log = logging.getLogger(__name__)


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Return a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_all_databases():
    """Create schemas across all 3 isolated SQLite databases."""
    # 1. Mickey Ground Truth DB
    with get_connection(MICKEY_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mickey_wargames (
                session_id TEXT PRIMARY KEY,
                session_date DATE NOT NULL,
                ticker TEXT NOT NULL,
                stream_type TEXT NOT NULL,
                title TEXT,
                notebook_source_id TEXT,
                gdrive_file_id TEXT,
                raw_transcript TEXT,
                char_count INTEGER,
                p12_bias TEXT,
                primary_scenario TEXT,
                key_levels_json TEXT,
                overnight_assessment TEXT,
                invalidation_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

    # 2. System Wargames DB
    with get_connection(SYSTEM_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_wargames (
                prediction_id TEXT PRIMARY KEY,
                session_date DATE NOT NULL,
                ticker TEXT NOT NULL,
                cutoff_time TEXT NOT NULL,
                spot_price REAL NOT NULL,
                p12_high REAL,
                p12_low REAL,
                p12_mid REAL,
                p12_bias TEXT NOT NULL,
                p12_diff_pts REAL,
                p12_diff_bps REAL,
                asia_status TEXT,
                asia_broken BOOLEAN,
                london_status TEXT,
                london_broken BOOLEAN,
                session_alignment TEXT,
                anchors_json TEXT,
                false_scenario_json TEXT,
                true_scenario_json TEXT,
                candle_science_json TEXT,
                pack_brackets_json TEXT,
                markdown_report TEXT,
                gdrive_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

    # 3. Market Actuals DB
    with get_connection(ACTUALS_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_actuals (
                session_id TEXT PRIMARY KEY,
                session_date DATE NOT NULL,
                ticker TEXT NOT NULL,
                rth_open REAL,
                rth_high REAL,
                rth_low REAL,
                rth_close REAL,
                actual_hod_time TEXT,
                actual_lod_time TEXT,
                step1_met BOOLEAN,
                step2_met BOOLEAN,
                step3_met BOOLEAN,
                step4_met BOOLEAN,
                four_step_score INTEGER,
                three_hour_block_type TEXT,
                realized_day_type TEXT,
                winning_scenario TEXT,
                queen_hit_time TEXT,
                stop_hit_time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_actuals_date_ticker ON market_actuals(session_date, ticker);")
        conn.commit()

    with get_connection(MICKEY_DB_PATH) as conn:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mickey_date_ticker ON mickey_wargames(session_date, ticker);")
        conn.commit()

    with get_connection(SYSTEM_DB_PATH) as conn:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_system_date_ticker ON system_wargames(session_date, ticker);")
        conn.commit()

    log.info(f"Initialized all 3 databases and composite indexes in {DB_DIR}")




def save_mickey_ground_truth(data: Dict[str, Any]) -> str:
    """Insert or update a ground-truth transcript record."""
    session_id = data.get("session_id")
    if not session_id:
        s_date = data.get("session_date", datetime.now().strftime("%Y-%m-%d"))
        ticker = data.get("ticker", "NQ1")
        stype = data.get("stream_type", "wargaming")
        session_id = f"{s_date}_{ticker}_{stype}"

    with get_connection(MICKEY_DB_PATH) as conn:
        conn.execute("""
            INSERT INTO mickey_wargames (
                session_id, session_date, ticker, stream_type, title,
                notebook_source_id, gdrive_file_id, raw_transcript, char_count,
                p12_bias, primary_scenario, key_levels_json, overnight_assessment, invalidation_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                title=excluded.title,
                gdrive_file_id=COALESCE(excluded.gdrive_file_id, mickey_wargames.gdrive_file_id),
                raw_transcript=excluded.raw_transcript,
                char_count=excluded.char_count,
                p12_bias=excluded.p12_bias,
                primary_scenario=excluded.primary_scenario,
                key_levels_json=excluded.key_levels_json,
                overnight_assessment=excluded.overnight_assessment,
                invalidation_notes=excluded.invalidation_notes;
        """, (
            session_id,
            data.get("session_date"),
            data.get("ticker", "NQ1"),
            data.get("stream_type", "wargaming"),
            data.get("title"),
            data.get("notebook_source_id"),
            data.get("gdrive_file_id"),
            data.get("raw_transcript"),
            data.get("char_count", len(data.get("raw_transcript", "") or "")),
            data.get("p12_bias"),
            data.get("primary_scenario"),
            json.dumps(data.get("key_levels", {})) if isinstance(data.get("key_levels"), (dict, list)) else data.get("key_levels"),
            data.get("overnight_assessment"),
            data.get("invalidation_notes"),
        ))
        conn.commit()

    return session_id


def save_system_wargame(data: Dict[str, Any], markdown_report: str = "", gdrive_file_id: Optional[str] = None) -> str:
    """Insert or update an AI system pre-market prediction."""
    s_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    ticker = data.get("ticker", "NQ1")
    cutoff = data.get("cutoff_time", "06:00")
    pred_id = f"pred_{s_date}_{cutoff.replace(':', '')}_{ticker}"

    p12 = data.get("p12", {})
    sess = data.get("sessions", {})
    anchors = data.get("anchors", {})
    cs = data.get("candle_science", {})
    pack = data.get("pack_trading", {})

    with get_connection(SYSTEM_DB_PATH) as conn:
        conn.execute("""
            INSERT INTO system_wargames (
                prediction_id, session_date, ticker, cutoff_time, spot_price,
                p12_high, p12_low, p12_mid, p12_bias, p12_diff_pts, p12_diff_bps,
                asia_status, asia_broken, london_status, london_broken, session_alignment,
                anchors_json, candle_science_json, pack_brackets_json, markdown_report, gdrive_file_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(prediction_id) DO UPDATE SET
                spot_price=excluded.spot_price,
                p12_high=excluded.p12_high,
                p12_low=excluded.p12_low,
                p12_mid=excluded.p12_mid,
                p12_bias=excluded.p12_bias,
                p12_diff_pts=excluded.p12_diff_pts,
                p12_diff_bps=excluded.p12_diff_bps,
                asia_status=excluded.asia_status,
                asia_broken=excluded.asia_broken,
                london_status=excluded.london_status,
                london_broken=excluded.london_broken,
                session_alignment=excluded.session_alignment,
                anchors_json=excluded.anchors_json,
                candle_science_json=excluded.candle_science_json,
                pack_brackets_json=excluded.pack_brackets_json,
                markdown_report=excluded.markdown_report,
                gdrive_file_id=COALESCE(excluded.gdrive_file_id, system_wargames.gdrive_file_id);
        """, (
            pred_id,
            s_date,
            ticker,
            cutoff,
            data.get("spot_price", 0.0),
            p12.get("high"),
            p12.get("low"),
            p12.get("mid"),
            p12.get("bias", "NEUTRAL"),
            p12.get("diff_pts", 0.0),
            p12.get("diff_bps", 0.0),
            sess.get("asia_status"),
            sess.get("asia_broken", False),
            sess.get("london_status"),
            sess.get("london_broken", False),
            sess.get("alignment"),
            json.dumps(anchors),
            json.dumps(cs),
            json.dumps(pack),
            markdown_report,
            gdrive_file_id,
        ))
        conn.commit()

    return pred_id


def save_market_actuals(data: Dict[str, Any]) -> str:
    """Insert or update mechanical EOD realized tape facts."""
    session_id = data.get("session_id")
    if not session_id:
        s_date = data.get("session_date", datetime.now().strftime("%Y-%m-%d"))
        ticker = data.get("ticker", "NQ1")
        session_id = f"{s_date}_{ticker}"

    with get_connection(ACTUALS_DB_PATH) as conn:
        conn.execute("""
            INSERT INTO market_actuals (
                session_id, session_date, ticker, rth_open, rth_high, rth_low, rth_close,
                actual_hod_time, actual_lod_time, step1_met, step2_met, step3_met, step4_met,
                four_step_score, three_hour_block_type, realized_day_type, winning_scenario,
                queen_hit_time, stop_hit_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                rth_open=excluded.rth_open,
                rth_high=excluded.rth_high,
                rth_low=excluded.rth_low,
                rth_close=excluded.rth_close,
                actual_hod_time=excluded.actual_hod_time,
                actual_lod_time=excluded.actual_lod_time,
                step1_met=excluded.step1_met,
                step2_met=excluded.step2_met,
                step3_met=excluded.step3_met,
                step4_met=excluded.step4_met,
                four_step_score=excluded.four_step_score,
                three_hour_block_type=excluded.three_hour_block_type,
                realized_day_type=excluded.realized_day_type,
                winning_scenario=excluded.winning_scenario,
                queen_hit_time=excluded.queen_hit_time,
                stop_hit_time=excluded.stop_hit_time;
        """, (
            session_id,
            data.get("session_date"),
            data.get("ticker", "NQ1"),
            data.get("rth_open"),
            data.get("rth_high"),
            data.get("rth_low"),
            data.get("rth_close"),
            data.get("actual_hod_time"),
            data.get("actual_lod_time"),
            data.get("step1_met", False),
            data.get("step2_met", False),
            data.get("step3_met", False),
            data.get("step4_met", False),
            data.get("four_step_score", 0),
            data.get("three_hour_block_type"),
            data.get("realized_day_type"),
            data.get("winning_scenario"),
            data.get("queen_hit_time"),
            data.get("stop_hit_time"),
        ))
        conn.commit()

    return session_id


def query_session_triad(session_date: str, ticker: str = "NQ1") -> Dict[str, Any]:
    """Retrieve the unified 3-bank triad (AI Prediction, Mickey Truth, Realized Actuals) for reconciliation."""
    triad = {"date": session_date, "ticker": ticker, "system_prediction": None, "mickey_truth": None, "market_actuals": None}

    # 1. System Wargames
    with get_connection(SYSTEM_DB_PATH) as conn:
        cur = conn.execute("SELECT * FROM system_wargames WHERE session_date = ? AND ticker = ? ORDER BY cutoff_time DESC LIMIT 1", (session_date, ticker))
        row = cur.fetchone()
        if row:
            triad["system_prediction"] = dict(row)

    # 2. Mickey Truth
    with get_connection(MICKEY_DB_PATH) as conn:
        cur = conn.execute("SELECT * FROM mickey_wargames WHERE session_date = ? AND ticker = ? LIMIT 1", (session_date, ticker))
        row = cur.fetchone()
        if row:
            triad["mickey_truth"] = dict(row)

    # 3. Market Actuals
    with get_connection(ACTUALS_DB_PATH) as conn:
        cur = conn.execute("SELECT * FROM market_actuals WHERE session_date = ? AND ticker = ? LIMIT 1", (session_date, ticker))
        row = cur.fetchone()
        if row:
            triad["market_actuals"] = dict(row)

    return triad


if __name__ == "__main__":
    init_all_databases()
    print(f"Successfully initialized isolated 3-bank databases at: {DB_DIR}")
