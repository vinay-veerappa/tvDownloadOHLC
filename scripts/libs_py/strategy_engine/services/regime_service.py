import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from prisma import Prisma

logger = logging.getLogger(__name__)

class RegimeService:
    """
    Service for querying GEX and Macro regime boundaries and states from SQLite.
    Includes built-in staleness protection for index tickers.
    """
    def __init__(self, db: Prisma):
        self.db = db

    async def get_gex_regime(self, ticker: str) -> Optional[dict]:
        """
        Retrieves the latest GexSnapshot for a given ticker.
        Applies a 5-minute staleness check for indices (SPX, SPY, QQQ, IWM).
        Returns:
            dict: {
                "gexRegime": str,
                "regimeLabel": str,
                "totalGex": float,
                "spotPrice": float,
                "gammaMagnet": float,
                "pinStrike": float,
                "timestamp": datetime,
                "is_stale": bool,
                "age_seconds": float
            } or None
        """
        ticker = ticker.upper()
        try:
            snapshot = await self.db.gexsnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            
            if not snapshot:
                return None
                
            # Check staleness (5 minutes / 300 seconds) for key index trackers
            is_stale = False
            now = datetime.now(timezone.utc)
            ts = snapshot.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            
            age_seconds = (now - ts).total_seconds()
            if ticker in ["SPX", "SPY", "QQQ", "IWM"] and age_seconds > 300.0:
                is_stale = True
                
            return {
                "gexRegime": snapshot.gexRegime,
                "regimeLabel": snapshot.regimeLabel or "",
                "totalGex": snapshot.totalGex,
                "spotPrice": snapshot.spotPrice,
                "gammaMagnet": snapshot.gammaMagnet or 0.0,
                "pinStrike": snapshot.pinStrike or 0.0,
                "timestamp": snapshot.timestamp,
                "is_stale": is_stale,
                "age_seconds": age_seconds
            }
        except Exception as e:
            logger.error(f"Error fetching GEX regime for {ticker}: {e}")
            return None

    async def get_macro_regime(self, ticker: str) -> Optional[dict]:
        """
        Retrieves the latest MacroSnapshot for a given ticker.
        Returns:
            dict: {
                "spotPrice": float,
                "macroCallWall": float,
                "macroPutWall": float,
                "zeroGamma": float,
                "timestamp": datetime
            } or None
        """
        ticker = ticker.upper()
        try:
            snapshot = await self.db.macrosnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            
            if not snapshot:
                return None
                
            return {
                "spotPrice": snapshot.spotPrice,
                "macroCallWall": snapshot.macroCallWall or 0.0,
                "macroPutWall": snapshot.macroPutWall or 0.0,
                "zeroGamma": snapshot.zeroGamma or 0.0,
                "timestamp": snapshot.timestamp
            }
        except Exception as e:
            logger.error(f"Error fetching macro regime for {ticker}: {e}")
            return None
