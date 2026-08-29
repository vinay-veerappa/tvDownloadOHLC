"""Measured Tape Actuals Extractor & EOD Classification Engine (Milestone 0.7).

Calculates:
1. RTH & Session OHLC (Open @ 09:30 ET, High, Low, RTH Close @ 16:00 ET, Session Close @ 16:15 ET).
2. Canonical Day Type Classification across 5 MECE classes (R1, R2, DNP, DWP, ROTATIONAL_CHOP)
   mirroring canonical scripts/derived/precompute_daily_classification.py & daily_classification_v2.pine.
3. HOD / LOD timestamps in UTC and session range in basis points (bps).
4. Bar completeness, scheduled short session handling, and SHA-256 content hashes.
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
    quality_state: str                         # 'CLEAN', 'SUSPECT_TICKS', 'INCOMPLETE_BARS', 'SCHEDULED_SHORT_SESSION', 'LEGACY_UNVERIFIED'
    supersedes_actual_id: Optional[str] = None


class TapeMetricsExtractor:
    """Extracts ground truth tape actuals from 1m live storage bars and registers them in database."""

    @staticmethod
    def get_session_boxes(df_rth: pd.DataFrame) -> List[Dict[str, Any]]:
        """Constructs canonical hourly session boxes mirroring PineScript v2 / precompute_daily_classification.py:
        Box 0: 09:30 - 09:59
        Box 1: 10:00 - 10:59
        Box 2: 11:00 - 11:59
        Box 3: 12:00 - 12:59
        Box 4: 13:00 - 13:59
        Box 5: 14:00 - 14:59
        Box 6: 15:00 - 15:59
        """
        cols = {c.lower(): c for c in df_rth.columns}
        h_col = cols.get("high", "high")
        l_col = cols.get("low", "low")
        
        boxes = []
        # Box 0: 09:30 to 09:59
        b0 = df_rth[(df_rth["dt_et"].dt.time >= time(9, 30)) & (df_rth["dt_et"].dt.time <= time(9, 59))]
        if not b0.empty:
            boxes.append({"h": float(b0[h_col].max()), "l": float(b0[l_col].min()), "t": time(9, 30)})
            
        # Boxes 1-5: 10:00 to 14:59
        for h in range(10, 15):
            bh = df_rth[(df_rth["dt_et"].dt.time >= time(h, 0)) & (df_rth["dt_et"].dt.time <= time(h, 59))]
            if not bh.empty:
                boxes.append({"h": float(bh[h_col].max()), "l": float(bh[l_col].min()), "t": time(h, 0)})
                
        # Box 6: 15:00 to 15:59
        b6 = df_rth[(df_rth["dt_et"].dt.time >= time(15, 0)) & (df_rth["dt_et"].dt.time <= time(15, 59))]
        if not b6.empty:
            boxes.append({"h": float(b6[h_col].max()), "l": float(b6[l_col].min()), "t": time(15, 0)})
            
        return boxes

    @classmethod
    def classify_day_type(
        cls,
        df_rth: pd.DataFrame,
        ticker: str = "NQ1"
    ) -> str:
        """Canonical Day Type Classification mirroring scripts/derived/precompute_daily_classification.py.
        
        Evaluates Opening Range (09:30 1m bar), Breaks, Touches, Returns (for R2), and Pullbacks (for DWP/DNP).
        """
        if df_rth.empty:
            return "ROTATIONAL_CHOP"
            
        cols = {c.lower(): c for c in df_rth.columns}
        h_col = cols.get("high", "high")
        l_col = cols.get("low", "low")
        
        # 1. Opening Range (09:30 1m bar)
        or_candle = df_rth[df_rth["dt_et"].dt.time == time(9, 30)]
        if or_candle.empty:
            or_candle = df_rth.iloc[[0]]
        or_h = float(or_candle[h_col].iloc[0])
        or_l = float(or_candle[l_col].iloc[0])
        
        # 2. Reconstruct Boxes
        boxes = cls.get_session_boxes(df_rth)
        if not boxes:
            return "ROTATIONAL_CHOP"
            
        # Tick tolerance
        tick_size = 0.01 if "CL" in ticker else (0.1 if ("GC" in ticker or "RTY" in ticker) else (1.0 if "YM" in ticker else 0.25))
        tolerance = 2.0 * tick_size
        min_touches_r1 = 4
        min_sep_r2 = 1
        r2_window_start_idx = 2  # 11:00 AM NY
        
        highs = [b["h"] for b in boxes]
        lows = [b["l"] for b in boxes]
        size = len(boxes)
        
        def touch_check(h, l): return h >= (or_l - tolerance) and l <= (or_h + tolerance)
        def break_check(h, l): return l > (or_h + tolerance) or h < (or_l - tolerance)
        
        broke_or = False
        broke_or_idx = -1
        broke_up = False
        touch_count = 0
        returned = False
        ret_idx = -1
        
        # Analysis Phase 1: Breaks & Touches
        for i in range(size):
            if break_check(highs[i], lows[i]):
                if not broke_or:
                    broke_or = True
                    broke_or_idx = i
                    broke_up = lows[i] > (or_h + tolerance)
            else:
                if touch_check(highs[i], lows[i]):
                    touch_count += 1
                    
        # Analysis Phase 2: Returns (for R2)
        if broke_or and broke_or_idx < size - 1:
            for i in range(broke_or_idx + 1, size):
                if touch_check(highs[i], lows[i]):
                    returned = True
                    ret_idx = i
                    touch_count += 1
                    break
                    
        # Analysis Phase 3: Pullbacks (for DWP/DNP)
        has_pb = False
        if broke_or and not returned:
            pb_end = size - 2
            if pb_end > broke_or_idx:
                if broke_up:
                    highest_low = lows[broke_or_idx]
                    for i in range(broke_or_idx + 1, pb_end + 1):
                        if lows[i] < highest_low:
                            has_pb = True
                            break
                        highest_low = max(highest_low, lows[i])
                else:
                    lowest_high = highs[broke_or_idx]
                    for i in range(broke_or_idx + 1, pb_end + 1):
                        if highs[i] > lowest_high:
                            has_pb = True
                            break
                        lowest_high = min(lowest_high, highs[i])
                        
        # Final Priority: R2 > R1 > DWP/DNP > ROTATIONAL_CHOP
        is_r2 = broke_or and returned and ret_idx >= r2_window_start_idx and (ret_idx - broke_or_idx) >= min_sep_r2
        is_r1 = touch_count >= min_touches_r1
        
        if is_r2:
            return "R2"
        elif is_r1:
            return "R1"
        elif broke_or:
            return "DWP" if has_pb else "DNP"
        else:
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
            
        cols = {c.lower(): c for c in df.columns}
        o_col = cols.get("open", "open")
        h_col = cols.get("high", "high")
        l_col = cols.get("low", "low")
        c_col = cols.get("close", "close")
        
        # Filter for RTH (09:30 to 16:00 ET)
        df_rth = df[(df["dt_et"].dt.time >= time(9, 30)) & (df["dt_et"].dt.time <= time(16, 0))].copy()
        if df_rth.empty:
            df_rth = df.copy()
            
        session_open = float(df_rth[o_col].iloc[0])
        session_high = float(df_rth[h_col].max())
        session_low = float(df_rth[l_col].min())
        rth_close = float(df_rth[c_col].iloc[-1])
        session_close = float(df[c_col].iloc[-1]) if not df.empty else rth_close
        
        hod_idx = df_rth[h_col].idxmax()
        lod_idx = df_rth[l_col].idxmin()
        hod_ts = to_iso_utc(df_rth.loc[hod_idx, "dt"])
        lod_ts = to_iso_utc(df_rth.loc[lod_idx, "dt"])
        
        range_bps = ((session_high - session_low) / session_open) * 10000.0 if session_open > 0 else 0.0
        
        day_type = cls.classify_day_type(df_rth, ticker=ticker)
        
        actual_bars = len(df_rth)
        # Scheduled half-day handling (e.g. 210 bars 09:30 to 13:00)
        if actual_bars >= 385:
            quality = "CLEAN"
            expected_bars = 390
        elif 205 <= actual_bars <= 215:
            quality = "SCHEDULED_SHORT_SESSION"
            expected_bars = 210
        else:
            quality = "INCOMPLETE_BARS"
            expected_bars = 390
            
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
            eod_pattern_classification=f"{day_type}_CANONICAL",
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
