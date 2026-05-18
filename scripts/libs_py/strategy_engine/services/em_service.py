import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from prisma import Prisma

logger = logging.getLogger(__name__)

class ExpectedMoveService:
    """
    Service for resolving daily expected moves from database records.
    Computes standard deviation bands from session opens or spot prices.
    """
    def __init__(self, db: Prisma):
        self.db = db

    async def get_expected_move_bands(self, ticker: str, spot_price: float, session_open: Optional[float] = None) -> Optional[dict]:
        """
        Retrieves the latest ExpectedMove or RthExpectedMove for a ticker,
        and computes the upper/lower 1SD and 2SD bands based on the session open (or spot_price if open is not available).
        Returns:
            dict: {
                "calculation_date": datetime,
                "expiry_date": datetime or None,
                "basis_price": float,
                "em_value": float,
                "upper_1sd": float,
                "lower_1sd": float,
                "upper_2sd": float,
                "lower_2sd": float,
                "source": "ExpectedMove" | "RthExpectedMove"
            } or None
        """
        ticker = ticker.upper()
        
        # 1. Try ExpectedMove
        try:
            em_rec = await self.db.expectedmove.find_first(
                where={"ticker": ticker},
                order={"calculationDate": "desc"}
            )
            if em_rec:
                em_val = em_rec.adjEm or em_rec.price * (em_rec.em252 or em_rec.em365 or 0.0)
                # Fallback to straddle if adjEm is 0
                if em_val == 0.0:
                    em_val = em_rec.straddle
                    
                if em_val > 0.0:
                    basis = session_open or em_rec.price or spot_price
                    return {
                        "calculation_date": em_rec.calculationDate,
                        "expiry_date": em_rec.expiryDate,
                        "basis_price": basis,
                        "em_value": em_val,
                        "upper_1sd": basis + em_val,
                        "lower_1sd": basis - em_val,
                        "upper_2sd": basis + (em_val * 2.0),
                        "lower_2sd": basis - (em_val * 2.0),
                        "source": "ExpectedMove"
                    }
        except Exception as e:
            logger.warning(f"Error fetching ExpectedMove for {ticker}: {e}")

        # 2. Fall back to RthExpectedMove
        try:
            rth_rec = await self.db.rthexpectedmove.find_first(
                where={"ticker": ticker},
                order={"date": "desc"}
            )
            if rth_rec:
                em_val = rth_rec.emStraddle or rth_rec.emIv or rth_rec.emVix or 0.0
                if em_val > 0.0:
                    basis = session_open or rth_rec.openPrice or spot_price
                    return {
                        "calculation_date": rth_rec.date,
                        "expiry_date": None,
                        "basis_price": basis,
                        "em_value": em_val,
                        "upper_1sd": basis + em_val,
                        "lower_1sd": basis - em_val,
                        "upper_2sd": basis + (em_val * 2.0),
                        "lower_2sd": basis - (em_val * 2.0),
                        "source": "RthExpectedMove"
                    }
        except Exception as e:
            logger.error(f"Error fetching RthExpectedMove fallback for {ticker}: {e}")
            
        return None
