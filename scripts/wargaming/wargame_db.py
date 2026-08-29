"""Isolated 3-Bank SQLite Database Engine with Canonical Trading Second Brain Cutover (Milestone 0.3b).

Authoritative master: data/wargaming/db/trading_brain.sqlite
Legacy shadow projections:
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
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timezone

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.migrations.outbox_projector import OutboxProjector

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
    """Create schemas across canonical database and all 3 legacy SQLite databases."""
    # 0. Canonical Database
    init_trading_brain_db(verbose=False)

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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mickey_date_ticker ON mickey_wargames(session_date, ticker);")
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_system_date_ticker ON system_wargames(session_date, ticker);")
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

    log.info(f"Initialized canonical database and all 3 legacy databases in {DB_DIR}")


def save_mickey_ground_truth(data: Dict[str, Any], db_path: Optional[Path] = None) -> str:
    """Authoritatively inserts ground-truth transcript into canonical DB and projects to legacy."""
    session_id = data.get("session_id")
    if not session_id:
        s_date = data.get("session_date", datetime.now().strftime("%Y-%m-%d"))
        ticker = data.get("ticker", "NQ1")
        stype = data.get("stream_type", "wargaming")
        session_id = f"{s_date}_{ticker}_{stype}"

    legacy_payload = {
        "session_id": session_id,
        "session_date": data.get("session_date"),
        "ticker": data.get("ticker", "NQ1"),
        "stream_type": data.get("stream_type", "wargaming"),
        "title": data.get("title"),
        "notebook_source_id": data.get("notebook_source_id"),
        "gdrive_file_id": data.get("gdrive_file_id"),
        "raw_transcript": data.get("raw_transcript"),
        "char_count": data.get("char_count", len(data.get("raw_transcript", "") or "")),
        "p12_bias": data.get("p12_bias"),
        "primary_scenario": data.get("primary_scenario"),
        "key_levels_json": json.dumps(data.get("key_levels", {})) if isinstance(data.get("key_levels"), (dict, list)) else data.get("key_levels"),
        "overnight_assessment": data.get("overnight_assessment"),
        "invalidation_notes": data.get("invalidation_notes")
    }

    # 1. Authoritative insert into trading_brain.sqlite + outbox enqueue
    info_id = f"info-mickey-{session_id}"
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO information_items (
                information_id, evidence_class, time_orientation, source_type,
                title, verbatim_text, available_at_utc, structured_payload_json
            ) VALUES (?, 'DOCTRINE', 'EX_ANTE', 'TRANSCRIPT', ?, ?, ?, ?);
            """,
            (
                info_id,
                f"Mickey Ground Truth: {data.get('title') or session_id}",
                data.get("raw_transcript") or data.get("overnight_assessment") or "",
                f"{data.get('session_date')}T08:45:00Z",
                json.dumps(legacy_payload)
            )
        )
        OutboxProjector.enqueue_outbox_item(
            conn=conn,
            destination_db="mickey_ground_truth",
            canonical_table="information_items",
            canonical_id=info_id,
            payload=legacy_payload
        )

    # 2. Project outbox
    projector = OutboxProjector(canonical_db_path=db_path, mickey_ground_truth_path=MICKEY_DB_PATH)
    projector.project_pending()

    return session_id


def save_system_wargame(data: Dict[str, Any], markdown_report: str = "", gdrive_file_id: Optional[str] = None, db_path: Optional[Path] = None) -> str:
    """Authoritatively inserts AI system prediction into canonical DB and projects to legacy."""
    s_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    ticker = data.get("ticker", "NQ1")
    cutoff = data.get("cutoff_time", "08:45")
    pred_id = f"pred_{s_date}_{cutoff.replace(':', '')}_{ticker}"

    p12 = data.get("p12", {})
    sess = data.get("sessions", {})
    anchors = data.get("anchors", {})
    cs = data.get("candle_science", {})
    pack = data.get("pack_trading", {})

    legacy_payload = {
        "prediction_id": pred_id,
        "session_date": s_date,
        "ticker": ticker,
        "cutoff_time": cutoff,
        "spot_price": float(data.get("spot_price", 0.0)),
        "p12_high": p12.get("high"),
        "p12_low": p12.get("low"),
        "p12_mid": p12.get("mid"),
        "p12_bias": p12.get("bias", "NEUTRAL"),
        "p12_diff_pts": p12.get("diff_pts", 0.0),
        "p12_diff_bps": p12.get("diff_bps", 0.0),
        "asia_status": sess.get("asia_status"),
        "asia_broken": 1 if sess.get("asia_broken") else 0,
        "london_status": sess.get("london_status"),
        "london_broken": 1 if sess.get("london_broken") else 0,
        "session_alignment": sess.get("alignment"),
        "anchors_json": json.dumps(anchors),
        "candle_science_json": json.dumps(cs),
        "pack_brackets_json": json.dumps(pack),
        "markdown_report": markdown_report,
        "gdrive_file_id": gdrive_file_id
    }

    # 1. Authoritative insert into trading_brain.sqlite + outbox enqueue
    fc_id = f"fc-{pred_id}"
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO forecast_snapshots (
                forecast_id, session_date, ticker, model_version_id, forecast_mode,
                effective_cutoff_utc, predicted_bias, p12_vector_direction, p12_equilibrium_level,
                candle_science_target_high, candle_science_target_low, git_hash, config_hash
            ) VALUES (?, ?, ?, 'MOD_WARGAME_V1', 'REPLAY_AUDIT', ?, ?, ?, ?, ?, ?, 'main', 'config');
            """,
            (
                fc_id,
                s_date,
                ticker,
                f"{s_date}T{cutoff}:00Z",
                p12.get("bias", "NEUTRAL"),
                p12.get("bias", "NEUTRAL"),
                p12.get("mid"),
                cs.get("high"),
                cs.get("low")
            )
        )
        OutboxProjector.enqueue_outbox_item(
            conn=conn,
            destination_db="system_wargames",
            canonical_table="forecast_snapshots",
            canonical_id=fc_id,
            payload=legacy_payload
        )

    # 2. Project outbox
    projector = OutboxProjector(canonical_db_path=db_path, system_wargames_path=SYSTEM_DB_PATH)
    projector.project_pending()

    return pred_id


def save_market_actuals(data: Dict[str, Any], db_path: Optional[Path] = None) -> str:
    """Authoritatively inserts mechanical EOD realized tape facts into canonical DB and projects to legacy."""
    session_id = data.get("session_id")
    if not session_id:
        s_date = data.get("session_date", datetime.now().strftime("%Y-%m-%d"))
        ticker = data.get("ticker", "NQ1")
        session_id = f"{s_date}_{ticker}"

    rth_open = float(data.get("rth_open", 0.0) or 0.0)
    rth_high = float(data.get("rth_high", 0.0) or 0.0)
    rth_low = float(data.get("rth_low", 0.0) or 0.0)
    rth_close = float(data.get("rth_close", 0.0) or 0.0)
    range_bps = ((rth_high - rth_low) / rth_open) * 10000.0 if rth_open > 0 else 0.0

    legacy_payload = {
        "session_id": session_id,
        "session_date": data.get("session_date"),
        "ticker": data.get("ticker", "NQ1"),
        "rth_open": rth_open,
        "rth_high": rth_high,
        "rth_low": rth_low,
        "rth_close": rth_close,
        "actual_hod_time": data.get("actual_hod_time"),
        "actual_lod_time": data.get("actual_lod_time"),
        "step1_met": 1 if data.get("step1_met") else 0,
        "step2_met": 1 if data.get("step2_met") else 0,
        "step3_met": 1 if data.get("step3_met") else 0,
        "step4_met": 1 if data.get("step4_met") else 0,
        "four_step_score": data.get("four_step_score", 0),
        "three_hour_block_type": data.get("three_hour_block_type"),
        "realized_day_type": data.get("realized_day_type"),
        "winning_scenario": data.get("winning_scenario"),
        "queen_hit_time": data.get("queen_hit_time"),
        "stop_hit_time": data.get("stop_hit_time")
    }

    # 1. Authoritative insert into trading_brain.sqlite + outbox enqueue
    actual_id = f"act-{session_id}"
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO session_tape_actuals (
                actual_id, session_date, ticker, contract_id, source_system,
                session_open, session_high, session_low, session_close, rth_close,
                hod_timestamp_utc, lod_timestamp_utc, session_range_bps,
                day_type_classification, expected_bar_count, actual_bar_count,
                content_hash, quality_state
            ) VALUES (?, ?, ?, 'NQU6', 'WARGAME_ACTUALS', ?, ?, ?, ?, ?, ?, ?, ?, ?, 390, 390, 'hash', 'CLEAN');
            """,
            (
                actual_id,
                data.get("session_date"),
                data.get("ticker", "NQ1"),
                rth_open,
                rth_high,
                rth_low,
                rth_close,
                rth_close,
                f"{data.get('session_date')}T{data.get('actual_hod_time') or '16:00'}:00Z",
                f"{data.get('session_date')}T{data.get('actual_lod_time') or '09:30'}:00Z",
                range_bps,
                data.get("realized_day_type", "ROTATIONAL_CHOP")
            )
        )
        OutboxProjector.enqueue_outbox_item(
            conn=conn,
            destination_db="market_actuals",
            canonical_table="session_tape_actuals",
            canonical_id=actual_id,
            payload=legacy_payload
        )

    # 2. Project outbox
    projector = OutboxProjector(canonical_db_path=db_path, market_actuals_path=ACTUALS_DB_PATH)
    projector.project_pending()

    return session_id


def query_session_triad(session_date: str, ticker: str = "NQ1", db_path: Optional[Path] = None) -> Dict[str, Any]:
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
    print(f"Successfully initialized canonical and legacy databases at: {DB_DIR}")
