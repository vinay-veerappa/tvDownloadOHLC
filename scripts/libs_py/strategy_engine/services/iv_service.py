import csv
import io
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional, Tuple

from prisma import Prisma

logger = logging.getLogger(__name__)

DOLT_DIR = "data/options/options"

PROXY_MAPPINGS = {
    "SPX": "SPY",
    "QQQ": "SPY",
    "IWM": "SPY",
}

DOLT_NATIVE = {"SPY", "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "AMD"}
DOLT_PROXIED = {"SPX", "QQQ", "IWM"}
DOLT_UNAVAILABLE = {"RIVN"}


@dataclass
class IvSnapshot:
    """IV state for a ticker on a date. Spec §4.4"""
    ticker: str
    on_date: date
    iv: float                        # current IV as decimal (e.g. 0.25)
    hv: Optional[float]              # historical realized vol, decimal
    iv_rank: Optional[float]         # 0-100
    iv_percentile: Optional[float]   # 0-100 (% of last 252d below current)
    iv_year_high: Optional[float]    # decimal
    iv_year_low: Optional[float]     # decimal
    iv_hv_ratio: Optional[float]     # iv / hv
    source: str                      # "dolt" | "prisma_gex" | "unknown"


class IvService:
    """
    Centralized IV access. Routes between Dolt (historical) and Prisma sources.
    All IV values are stored and returned as decimals (e.g. 0.25 = 25%).
    Spec §4.4
    """

    def __init__(self, db: Prisma, dolt_dir: str = DOLT_DIR):
        self.db = db
        self.dolt_dir = dolt_dir

    # ------------------------------------------------------------------
    # Internal: Dolt
    # ------------------------------------------------------------------

    def _dolt_available(self) -> bool:
        return os.path.exists(os.path.abspath(self.dolt_dir))

    def _query_dolt(self, sql: str) -> list[dict]:
        """Run a Dolt SQL query and return rows as list of dicts."""
        try:
            cwd = os.path.abspath(self.dolt_dir)
            res = subprocess.run(
                ["dolt", "sql", "-q", sql, "-r", "csv"],
                cwd=cwd, capture_output=True, text=True, check=True, timeout=10
            )
            reader = csv.DictReader(io.StringIO(res.stdout.strip()))
            return list(reader)
        except Exception as e:
            logger.warning(f"IvService: Dolt query failed: {e}")
            return []

    def _to_decimal(self, raw: Optional[float]) -> Optional[float]:
        """Normalise a value that may be percent-scaled (>1) to decimal."""
        if raw is None:
            return None
        return raw / 100.0 if raw > 1.0 else raw

    def _query_dolt_vol_row(self, ticker: str) -> dict:
        """Returns the latest volatility_history row for ticker, or {}."""
        if not self._dolt_available():
            return {}
        sql = (
            f"SELECT hv_current, iv_current, iv_year_high, iv_year_low "
            f"FROM volatility_history WHERE act_symbol = '{ticker}' "
            f"ORDER BY date DESC LIMIT 1"
        )
        rows = self._query_dolt(sql)
        return rows[0] if rows else {}

    def _query_dolt_iv_percentile(self, ticker: str, current_iv_decimal: float) -> Optional[float]:
        """Compute IV percentile: % of last 252 days where iv_current < current."""
        if not self._dolt_available():
            return None
        current_scaled = current_iv_decimal * 100 if current_iv_decimal <= 1.0 else current_iv_decimal
        sql = (
            f"SELECT COUNT(*) as total, "
            f"SUM(CASE WHEN iv_current < {current_scaled:.4f} THEN 1 ELSE 0 END) as below_count "
            f"FROM volatility_history WHERE act_symbol = '{ticker}' "
            f"ORDER BY date DESC LIMIT 252"
        )
        rows = self._query_dolt(sql)
        if not rows:
            return None
        try:
            total = int(rows[0].get("total", 0))
            below = int(rows[0].get("below_count", 0))
            if total > 0:
                return round(below / total * 100.0, 2)
        except (ValueError, ZeroDivisionError):
            pass
        return None

    def _resolve_dolt_ticker(self, ticker: str) -> Tuple[str, bool]:
        """Returns (query_ticker, is_proxy)."""
        if ticker in DOLT_NATIVE:
            return ticker, False
        if ticker in DOLT_PROXIED:
            return PROXY_MAPPINGS[ticker], True
        return ticker, False

    # ------------------------------------------------------------------
    # Core snapshot builder
    # ------------------------------------------------------------------

    async def get_iv_snapshot(self, ticker: str, on_date: Optional[date] = None) -> Optional[IvSnapshot]:
        """
        Best available IV snapshot for ticker on date.
        Resolution order: Dolt native → Dolt proxy → Prisma GexSnapshot → None.
        Returns None for DOLT_UNAVAILABLE tickers.
        Spec §4.4
        """
        ticker = ticker.upper()
        if ticker in DOLT_UNAVAILABLE:
            logger.info(f"IvService: {ticker} has no IV history available. Returning None.")
            return None

        target_date = on_date or date.today()
        dolt_ticker, is_proxy = self._resolve_dolt_ticker(ticker)

        # 1. Try Dolt
        row = self._query_dolt_vol_row(dolt_ticker)
        if row:
            hv_raw = row.get("hv_current")
            iv_raw = row.get("iv_current")
            iv_high_raw = row.get("iv_year_high")
            iv_low_raw = row.get("iv_year_low")

            hv = self._to_decimal(float(hv_raw)) if hv_raw and hv_raw != "NULL" else None
            iv = self._to_decimal(float(iv_raw)) if iv_raw and iv_raw != "NULL" else None
            iv_high = self._to_decimal(float(iv_high_raw)) if iv_high_raw and iv_high_raw != "NULL" else None
            iv_low = self._to_decimal(float(iv_low_raw)) if iv_low_raw and iv_low_raw != "NULL" else None

            iv_rank = None
            if iv is not None and iv_high is not None and iv_low is not None and iv_high != iv_low:
                iv_rank = round(100.0 * (iv - iv_low) / (iv_high - iv_low), 2)
                iv_rank = max(0.0, min(100.0, iv_rank))

            iv_percentile = None
            if iv is not None:
                iv_percentile = self._query_dolt_iv_percentile(dolt_ticker, iv)

            iv_hv_ratio = None
            if iv is not None and hv and hv > 0:
                iv_hv_ratio = round(iv / hv, 3)

            return IvSnapshot(
                ticker=ticker,
                on_date=target_date,
                iv=iv or 0.0,
                hv=hv,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                iv_year_high=iv_high,
                iv_year_low=iv_low,
                iv_hv_ratio=iv_hv_ratio,
                source="dolt",
            )

        # 2. Fall back to Prisma GexSnapshot for intraday IV
        try:
            snapshot = await self.db.gexsnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            if snapshot:
                p25 = getattr(snapshot, "put25dIv", None) or 0.0
                c25 = getattr(snapshot, "call25dIv", None) or 0.0
                raw_iv = (p25 + c25) / 2.0 if p25 > 0 and c25 > 0 else (p25 or c25)
                iv = self._to_decimal(raw_iv) if raw_iv > 0 else None

                if iv:
                    return IvSnapshot(
                        ticker=ticker,
                        on_date=target_date,
                        iv=iv,
                        hv=None,
                        iv_rank=None,
                        iv_percentile=None,
                        iv_year_high=None,
                        iv_year_low=None,
                        iv_hv_ratio=None,
                        source="prisma_gex",
                    )
        except Exception as e:
            logger.warning(f"IvService: Error fetching GexSnapshot IV for {ticker}: {e}")

        return None

    # ------------------------------------------------------------------
    # Convenience methods — spec §4.4
    # ------------------------------------------------------------------

    async def get_iv_rank(self, ticker: str, on_date: Optional[date] = None) -> Optional[float]:
        """IV rank 0-100. None if unavailable."""
        snap = await self.get_iv_snapshot(ticker, on_date)
        return snap.iv_rank if snap else None

    async def get_iv_percentile(self, ticker: str, on_date: Optional[date] = None) -> Optional[float]:
        """IV percentile 0-100. None if unavailable."""
        snap = await self.get_iv_snapshot(ticker, on_date)
        return snap.iv_percentile if snap else None

    async def get_iv_hv_ratio(self, ticker: str, on_date: Optional[date] = None) -> Optional[float]:
        """Vol risk premium: IV / HV. None if HV unavailable."""
        snap = await self.get_iv_snapshot(ticker, on_date)
        return snap.iv_hv_ratio if snap else None

    async def get_current_intraday_iv(self, ticker: str) -> Optional[float]:
        """
        Latest ATM IV from GexSnapshot (intraday, fresh within last 60s).
        Falls back to None if no fresh snapshot.
        Spec §4.4
        """
        ticker = ticker.upper()
        try:
            snapshot = await self.db.gexsnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            if not snapshot:
                return None

            # Check freshness (60s)
            ts = snapshot.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age > 60.0:
                return None

            p25 = getattr(snapshot, "put25dIv", None) or 0.0
            c25 = getattr(snapshot, "call25dIv", None) or 0.0
            raw = (p25 + c25) / 2.0 if p25 > 0 and c25 > 0 else (p25 or c25)
            return self._to_decimal(raw) if raw > 0 else None
        except Exception as e:
            logger.warning(f"IvService: Error fetching intraday IV for {ticker}: {e}")
            return None

    async def get_current_skew(self, ticker: str) -> Optional[float]:
        """
        volatilitySkewPremium from latest GexSnapshot.
        Higher = put-side IV richer than call-side.
        Spec §4.4
        """
        ticker = ticker.upper()
        try:
            snapshot = await self.db.gexsnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            if snapshot:
                return getattr(snapshot, "volatilitySkewPremium", None)
        except Exception as e:
            logger.warning(f"IvService: Error fetching skew for {ticker}: {e}")
        return None

    # ------------------------------------------------------------------
    # Legacy dict API (backward compat — keeps old callers working)
    # ------------------------------------------------------------------

    async def get_historical_volatility(self, ticker: str) -> Optional[float]:
        snap = await self.get_iv_snapshot(ticker)
        return snap.hv if snap else None

    async def get_current_iv(self, ticker: str, broker_service=None) -> Optional[float]:
        snap = await self.get_iv_snapshot(ticker)
        return snap.iv if snap else None

    async def get_volatility_metrics(self, ticker: str) -> dict:
        snap = await self.get_iv_snapshot(ticker)
        if snap:
            return {"iv": snap.iv, "hv": snap.hv or 0.0, "iv_rank": snap.iv_rank or 0.0}
        return {"iv": 0.0, "hv": 0.0, "iv_rank": 0.0}
