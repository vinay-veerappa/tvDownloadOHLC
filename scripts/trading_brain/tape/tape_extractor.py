"""Measured Tape Actuals Extractor & EOD Classification Engine (Milestone 0.7).

Calculates:
1. RTH & Session OHLC (Open @ 09:30 ET, High, Low, RTH Close @ 16:00 ET, Session Close @ 16:15 ET).
2. Canonical Day Type Classification across 5 MECE classes (R1, R2, DNP, DWP, ROTATIONAL_CHOP).
3. HOD / LOD timestamps in UTC and session range in basis points (bps).
4. Bar completeness, tick quality state, and SHA-256 content hashes.
5. Saves versioned, revisable records to session_tape_actuals.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.trading_brain.db.connection import get_db_connection
from scripts.utils.live_storage_resolver import load_session_bars
from scripts.utils.market_calendar import now_iso_utc, to_iso_utc

EASTERN_TZ = ZoneInfo("America/New_York")


@dataclass
class TapeMetrics:
    actual_id: str
    session_date: str
    ticker: str
    revision_seq: int
    contract_id: Optional[str]
    source_system: str
    session_open: float
    session_high: float
    session_low: float
    session_close: float
    rth_close: float
    hod_timestamp_utc: Optional[str]
    lod_timestamp_utc: Optional[str]
    session_range_bps: float
    day_type_classification: str               # 'R1', 'R2', 'DNP', 'DWP', 'ROTATIONAL_CHOP'
    eod_pattern_classification: Optional[str]
    expected_bar_count: int
    actual_bar_count: int
    content_hash: str
    quality_state: str                         # 'CLEAN', 'SUSPECT_TICKS', 'INCOMPLETE_BARS', 'LEGACY_UNVERIFIED'
    supersedes_actual_id: Optional[str] = None


class TapeMetricsExtractor:
    """Extracts ground truth tape actuals from 1m live storage bars and registers them in database."""

    @staticmethod
    def classify_day_type(
        rth_open: float,
        rth_high: float,
        rth_low: float,
        rth_close: float,
        ib_high: float,
        ib_low: float,
        range_bps: float
    ) -> str:
        """Classifies session into canonical 5 MECE day types based on IB penetration and closing location."""
        ib_range = ib_high - ib_low
        if ib_range <= 0 or rth_open <= 0:
            return "ROTATIONAL_CHOP"
            
        up_extension = (rth_high - ib_high) / ib_range
        down_extension = (ib_low - rth_low) / ib_range
        
        # 1. Did Not Penetrate (DNP): inside morning initial balance
        if up_extension < 0.15 and down_extension < 0.15:
            return "DNP"
            
        # 2. Both sides penetrated (R2 Reversal / Outside Day)
        if up_extension >= 0.50 and down_extension >= 0.50:
            return "R2"
            
        # 3. One side penetrated decisively (R1 Trend Expansion)
        if (up_extension >= 1.0 and down_extension < 0.25) or (down_extension >= 1.0 and up_extension < 0.25):
            return "R1"
            
        # 4. Directional drift without explosive extension (DWP)
        if (up_extension >= 0.30 and rth_close > ib_high) or (down_extension >= 0.30 and rth_close < ib_low):
            return "DWP"
            
        # 5. Otherwise Rotational Chop
        return "ROTATIONAL_CHOP"

    @classmethod
    def extract_from_dataframe(
        cls,
        df: pd.DataFrame,
        session_date: str,
        ticker: str,
        contract_id: Optional[str] = None,
        source_system: str = "LIVE_STORAGE_PARQUET",
        supersedes_actual_id: Optional[str] = None,
        revision_seq: int = 1
    ) -> TapeMetrics:
        """Extracts tape metrics from a pandas DataFrame of session bars."""
        if df.empty:
            raise ValueError(f"Cannot extract tape metrics: DataFrame for {ticker} on {session_date} is empty.")
            
        # Normalize column names
        cols = {c.lower(): c for c in df.columns}
        o_col = cols.get("open", "open")
        h_col = cols.get("high", "high")
        l_col = cols.get("low", "low")
        c_col = cols.get("close", "close")
        
        # Filter for RTH (09:30 to 16:00 ET)
        df_rth = df[(df["dt_et"].dt.time >= time(9, 30)) & (df["dt_et"].dt.time <= time(16, 0))].copy()
        
        if df_rth.empty:
            # Fallback to entire available session
            df_rth = df.copy()
            
        session_open = float(df_rth[o_col].iloc[0])
        session_high = float(df_rth[h_col].max())
        session_low = float(df_rth[l_col].min())
        rth_close = float(df_rth[c_col].iloc[-1])
        
        # Session close at 16:15 ET if available, else rth_close
        session_close = float(df[c_col].iloc[-1]) if not df.empty else rth_close
        
        # HOD / LOD timestamps
        hod_idx = df_rth[h_col].idxmax()
        lod_idx = df_rth[l_col].idxmin()
        hod_ts = to_iso_utc(df_rth.loc[hod_idx, "dt"])
        lod_ts = to_iso_utc(df_rth.loc[lod_idx, "dt"])
        
        # Initial Balance (09:30 to 10:30 ET)
        df_ib = df_rth[df_rth["dt_et"].dt.time <= time(10, 30)]
        if not df_ib.empty:
            ib_high = float(df_ib[h_col].max())
            ib_low = float(df_ib[l_col].min())
        else:
            ib_high = session_high
            ib_low = session_low
            
        range_bps = ((session_high - session_low) / session_open) * 10000.0 if session_open > 0 else 0.0
        
        day_type = cls.classify_day_type(
            rth_open=session_open,
            rth_high=session_high,
            rth_low=session_low,
            rth_close=rth_close,
            ib_high=ib_high,
            ib_low=ib_low,
            range_bps=range_bps
        )
        
        expected_bars = 390
        actual_bars = len(df_rth)
        quality = "CLEAN" if actual_bars >= 385 else "INCOMPLETE_BARS"
        
        # Hash computation
        hash_payload = {
            "session_date": session_date,
            "ticker": ticker,
            "open": session_open,
            "high": session_high,
            "low": session_low,
            "close": session_close,
            "rth_close": rth_close,
            "day_type": day_type
        }
        content_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True).encode("utf-8")).hexdigest()
        actual_id = str(uuid.uuid4())
        
        return TapeMetrics(
            actual_id=actual_id,
            session_date=session_date,
            ticker=ticker,
            revision_seq=revision_seq,
            contract_id=contract_id,
            source_system=source_system,
            session_open=session_open,
            session_high=session_high,
            session_low=session_low,
            session_close=session_close,
            rth_close=rth_close,
            hod_timestamp_utc=hod_ts,
            lod_timestamp_utc=lod_ts,
            session_range_bps=range_bps,
            day_type_classification=day_type,
            eod_pattern_classification=f"{day_type}_STANDARD",
            expected_bar_count=expected_bars,
            actual_bar_count=actual_bars,
            content_hash=f"sha256:{content_hash}",
            quality_state=quality,
            supersedes_actual_id=supersedes_actual_id
        )

    @classmethod
    def extract_and_record(
        cls,
        session_date: str,
        ticker: str,
        custom_data_dir: Optional[Union[str, Path]] = None,
        db_path: Optional[Union[str, Path]] = None,
        supersedes_actual_id: Optional[str] = None
    ) -> TapeMetrics:
        """Extracts tape metrics from live storage parquet and records to database."""
        df = load_session_bars(ticker, session_date, custom_dir=custom_data_dir)
        
        with get_db_connection(db_path) as conn:
            # Determine next revision_seq
            cur = conn.execute(
                "SELECT IFNULL(MAX(revision_seq), 0) + 1 AS next_seq FROM session_tape_actuals WHERE session_date = ? AND ticker = ?;",
                (session_date, ticker)
            )
            next_seq = cur.fetchone()["next_seq"]
            
            metrics = cls.extract_from_dataframe(
                df=df,
                session_date=session_date,
                ticker=ticker,
                supersedes_actual_id=supersedes_actual_id,
                revision_seq=next_seq
            )
            
            conn.execute(
                """
                INSERT INTO session_tape_actuals (
                    actual_id, session_date, ticker, revision_seq, contract_id,
                    source_system, session_open, session_high, session_low,
                    session_close, rth_close, hod_timestamp_utc, lod_timestamp_utc,
                    session_range_bps, day_type_classification, eod_pattern_classification,
                    expected_bar_count, actual_bar_count, content_hash, quality_state,
                    supersedes_actual_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    metrics.actual_id, metrics.session_date, metrics.ticker, metrics.revision_seq,
                    metrics.contract_id, metrics.source_system, metrics.session_open,
                    metrics.session_high, metrics.session_low, metrics.session_close,
                    metrics.rth_close, metrics.hod_timestamp_utc, metrics.lod_timestamp_utc,
                    metrics.session_range_bps, metrics.day_type_classification,
                    metrics.eod_pattern_classification, metrics.expected_bar_count,
                    metrics.actual_bar_count, metrics.content_hash, metrics.quality_state,
                    metrics.supersedes_actual_id
                )
            )
            
        return metrics
