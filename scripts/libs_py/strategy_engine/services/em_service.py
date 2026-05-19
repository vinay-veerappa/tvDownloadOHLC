import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from prisma import Prisma

logger = logging.getLogger(__name__)


@dataclass
class ExpectedMoveBands:
    """Expected move bands for a ticker on a date. Spec §4.3"""
    ticker: str
    calc_date: date
    expiry_date: Optional[date]
    spot_at_calc: float
    straddle_price: float
    em_365: float
    em_252: float
    adj_em: float                       # 0.85 × straddle (user-adjusted EM)

    upper_boundary_1sd: float           # spot + adj_em
    lower_boundary_1sd: float           # spot - adj_em
    upper_boundary_2sd: float           # spot + 2 * adj_em
    lower_boundary_2sd: float           # spot - 2 * adj_em

    source: str = "ExpectedMove"        # "ExpectedMove" | "RthExpectedMove"


class ExpectedMoveService:
    """
    Wraps ExpectedMove and RthExpectedMove tables.
    Provides the full spec §4.3 interface.
    """

    def __init__(self, db: Prisma):
        self.db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_em_bands(self, ticker: str) -> Optional[ExpectedMoveBands]:
        """Core resolver — tries ExpectedMove then RthExpectedMove."""
        ticker = ticker.upper()

        # 1. Try ExpectedMove (primary)
        try:
            em_rec = await self.db.expectedmove.find_first(
                where={"ticker": ticker},
                order={"calculationDate": "desc"}
            )
            if em_rec:
                straddle = em_rec.straddle or 0.0
                adj_em = em_rec.adjEm if (em_rec.adjEm and em_rec.adjEm > 0) else straddle * 0.85
                em_365 = em_rec.em365 or 0.0
                em_252 = em_rec.em252 or 0.0
                basis = em_rec.price or 0.0

                if adj_em > 0:
                    calc_date = (
                        em_rec.calculationDate.date()
                        if isinstance(em_rec.calculationDate, datetime)
                        else em_rec.calculationDate
                    )
                    expiry_date = None
                    if em_rec.expiryDate:
                        expiry_date = (
                            em_rec.expiryDate.date()
                            if isinstance(em_rec.expiryDate, datetime)
                            else em_rec.expiryDate
                        )
                    return ExpectedMoveBands(
                        ticker=ticker,
                        calc_date=calc_date,
                        expiry_date=expiry_date,
                        spot_at_calc=basis,
                        straddle_price=straddle,
                        em_365=em_365,
                        em_252=em_252,
                        adj_em=adj_em,
                        upper_boundary_1sd=basis + adj_em,
                        lower_boundary_1sd=basis - adj_em,
                        upper_boundary_2sd=basis + 2 * adj_em,
                        lower_boundary_2sd=basis - 2 * adj_em,
                        source="ExpectedMove",
                    )
        except Exception as e:
            logger.warning(f"ExpectedMoveService: Error fetching ExpectedMove for {ticker}: {e}")

        # 2. Fall back to RthExpectedMove
        try:
            rth_rec = await self.db.rthexpectedmove.find_first(
                where={"ticker": ticker},
                order={"date": "desc"}
            )
            if rth_rec:
                adj_em = rth_rec.emStraddle or rth_rec.emIv or rth_rec.emVix or 0.0
                basis = rth_rec.openPrice or 0.0
                if adj_em > 0:
                    calc_date = (
                        rth_rec.date.date()
                        if isinstance(rth_rec.date, datetime)
                        else rth_rec.date
                    )
                    return ExpectedMoveBands(
                        ticker=ticker,
                        calc_date=calc_date,
                        expiry_date=None,
                        spot_at_calc=basis,
                        straddle_price=adj_em,
                        em_365=adj_em,
                        em_252=adj_em,
                        adj_em=adj_em,
                        upper_boundary_1sd=basis + adj_em,
                        lower_boundary_1sd=basis - adj_em,
                        upper_boundary_2sd=basis + 2 * adj_em,
                        lower_boundary_2sd=basis - 2 * adj_em,
                        source="RthExpectedMove",
                    )
        except Exception as e:
            logger.error(f"ExpectedMoveService: Error fetching RthExpectedMove for {ticker}: {e}")

        return None

    # ------------------------------------------------------------------
    # Public spec-compliant API
    # ------------------------------------------------------------------

    # ─── Spec §4.3 interface — temporary thin wrappers ───

    async def get_today_em(self, ticker: str) -> Optional[dict]:
        """Today's expected move bands for ticker.

        TODO(D4): Spec §4.3 calls for a richer ExpectedMoveBands shape with 365-day and
        252-day annualisations plus straddle_price. For now this forwards to
        get_expected_move_bands so callers get the same dict keys
        ('upper_1sd', 'lower_1sd', etc.).
        """
        return await self.get_expected_move_bands(ticker, spot_price=0.0, session_open=None)

    async def get_em_distance_in_sd(
        self,
        ticker: str,
        current_spot: float,
    ) -> Optional[float]:
        """How many SDs is current_spot from the EM basis price?

        Returns (current_spot - basis_price) / em_value. Positive = above basis.

        NOTE: Per spec §4.3 the basis should be the session OPEN. Current impl uses
        whichever basis the EM record provides (typically the snapshot price).
        """
        bands = await self.get_expected_move_bands(ticker, spot_price=current_spot, session_open=None)
        if not bands or bands.get("em_value", 0.0) <= 0.0:
            return None
        return (current_spot - bands["basis_price"]) / bands["em_value"]

    async def get_historical_em_hit_rate(
        self,
        ticker: str,
        lookback_days: int = 60,
    ) -> Optional[dict]:
        """
        How often does spot stay within the EM boundary historically?
        Returns {within_1sd_pct, beyond_upper_pct, beyond_lower_pct} or None.
        Spec §4.3
        """
        ticker = ticker.upper()
        try:
            records = await self.db.expectedmovehistory.find_many(
                where={"ticker": ticker},
                order={"calculationDate": "desc"},
                take=lookback_days
            )
            if not records:
                return None

            total = len(records)
            within = 0
            beyond_upper = 0
            beyond_lower = 0

            for rec in records:
                close = getattr(rec, "actualClose", None) or getattr(rec, "closePrice", None)
                upper = getattr(rec, "upperBoundary", None)
                lower = getattr(rec, "lowerBoundary", None)
                if close is None or upper is None or lower is None:
                    total -= 1
                    continue
                if lower <= close <= upper:
                    within += 1
                elif close > upper:
                    beyond_upper += 1
                else:
                    beyond_lower += 1

            if total == 0:
                return None

            return {
                "within_1sd_pct": round(within / total * 100.0, 2),
                "beyond_upper_pct": round(beyond_upper / total * 100.0, 2),
                "beyond_lower_pct": round(beyond_lower / total * 100.0, 2),
                "sample_size": total,
            }
        except Exception as e:
            logger.error(f"ExpectedMoveService: Error computing historical EM hit rate for {ticker}: {e}")
            return None

    async def get_em_distance_in_sd(
        self,
        ticker: str,
        current_spot: float,
    ) -> Optional[float]:
        """
        How many SDs is current_spot from the session open?
        Returns (current_spot - open) / adj_em. Positive = above open.
        Spec §4.3
        """
        bands = await self._fetch_em_bands(ticker)
        if not bands or bands.adj_em <= 0:
            return None
        return round((current_spot - bands.spot_at_calc) / bands.adj_em, 4)

    # ------------------------------------------------------------------
    # Legacy dict API (backward compat)
    # ------------------------------------------------------------------

    async def get_expected_move_bands(
        self,
        ticker: str,
        spot_price: float,
        session_open: Optional[float] = None,
    ) -> Optional[dict]:
        """Legacy dict-returning method for backward compatibility."""
        bands = await self._fetch_em_bands(ticker)
        if not bands:
            return None

        basis = session_open or bands.spot_at_calc or spot_price
        adj_em = bands.adj_em

        return {
            "calculation_date": bands.calc_date,
            "expiry_date": bands.expiry_date,
            "basis_price": basis,
            "em_value": adj_em,
            "upper_1sd": basis + adj_em,
            "lower_1sd": basis - adj_em,
            "upper_2sd": basis + (adj_em * 2.0),
            "lower_2sd": basis - (adj_em * 2.0),
            "source": bands.source,
        }
