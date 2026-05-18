import os
import subprocess
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from prisma import Prisma

logger = logging.getLogger(__name__)

# Default Dolt directory config
DOLT_DIR = "data/options/options"

# Proxy mappings for index underlyings to their EOD historical proxy
PROXY_MAPPINGS = {
    "SPX": "SPY",
    "QQQ": "SPY",
    "IWM": "SPY"
}

class IvService:
    """
    Volatility service. Resolves:
    1. Trailing EOD Historical Volatility (HV) from Dolt volatility_history.
    2. Current or EOD Implied Volatility (IV) from Prisma GexSnapshots and Dolt.
    Includes SPY proxy resolution for indices SPX, QQQ, and IWM.
    """
    def __init__(self, db: Prisma, dolt_dir: str = DOLT_DIR):
        self.db = db
        self.dolt_dir = dolt_dir

    def _query_dolt_volatility(self, ticker: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Executes a Dolt CLI query to extract the latest EOD hv_current and iv_current for a given ticker.
        Returns:
            Tuple[Optional[float], Optional[float]]: (hv_current, iv_current)
        """
        try:
            sql = f"SELECT hv_current, iv_current FROM volatility_history WHERE act_symbol = '{ticker}' ORDER BY date DESC LIMIT 1"
            cmd = ["dolt", "sql", "-q", sql, "-r", "csv"]
            
            cwd = os.path.abspath(self.dolt_dir)
            if not os.path.exists(cwd):
                logger.warning(f"Dolt directory not found: {cwd}. Volatility queries will bypass Dolt.")
                return None, None
                
            res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
            
            # Parse CSV response
            reader = csv.DictReader(io.StringIO(res.stdout.strip()))
            for row in reader:
                hv = float(row["hv_current"]) if row.get("hv_current") and row["hv_current"] != "NULL" else None
                iv = float(row["iv_current"]) if row.get("iv_current") and row["iv_current"] != "NULL" else None
                return hv, iv
        except Exception as e:
            logger.error(f"Error querying Dolt volatility for {ticker}: {e}")
        return None, None

    async def get_historical_volatility(self, ticker: str) -> Optional[float]:
        """
        Resolves trailing EOD historical volatility data from Dolt.
        Applies proxy mapping for indices if direct data is missing.
        Returns:
            float: EOD historical volatility as decimal (e.g. 0.1293) or None
        """
        ticker = ticker.upper()
        
        # 1. Try direct query
        hv, _ = self._query_dolt_volatility(ticker)
        if hv is not None:
            return hv
            
        # 2. Try proxy query if direct query fails or returns None
        proxy_ticker = PROXY_MAPPINGS.get(ticker)
        if proxy_ticker:
            logger.info(f"Direct Dolt HV for {ticker} unavailable. Falling back to proxy {proxy_ticker}.")
            hv, _ = self._query_dolt_volatility(proxy_ticker)
            if hv is not None:
                return hv
                
        # 3. Fallback to SQLite HistoricalVolatility table if populated
        try:
            db_rec = await self.db.historicalvolatility.find_first(
                where={"ticker": ticker},
                order={"date": "desc"}
            )
            if db_rec and db_rec.hv is not None:
                return db_rec.hv
        except Exception as e:
            logger.warning(f"Error fetching HV from Prisma fallback for {ticker}: {e}")
            
        return None

    async def get_current_iv(self, ticker: str, broker_service: Optional[Any] = None) -> Optional[float]:
        """
        Resolves current ATM implied volatility.
        Tries:
        1. ATM IV calculated from Schwab options chain via BrokerService (highest real-time accuracy).
        2. put25d/call25d IV averaged from the latest Prisma GexSnapshot.
        3. EOD iv_current from Dolt.
        Returns:
            float: Implied volatility as decimal (e.g. 0.1511) or None
        """
        ticker = ticker.upper()

        # 1. Real-time ATM IV calculation from Schwab chain via BrokerService if provided
        if broker_service:
            try:
                # Retrieve standard 1-30 DTE chain
                chain = await broker_service.get_chain(ticker, [0, 1, 2, 3, 4, 5, 6, 7])
                if chain and chain.spot > 0:
                    # Find near-the-money options
                    c_atm = broker_service.find_strike_nearest(chain, chain.spot, "CALL")
                    p_atm = broker_service.find_strike_nearest(chain, chain.spot, "PUT")
                    ivs = []
                    if c_atm and c_atm.iv > 0:
                        ivs.append(c_atm.iv)
                    if p_atm and p_atm.iv > 0:
                        ivs.append(p_atm.iv)
                    if ivs:
                        return sum(ivs) / len(ivs)
            except Exception as e:
                logger.warning(f"Error computing live ATM IV from broker chain for {ticker}: {e}")

        # 2. Latest GexSnapshot from Prisma
        try:
            snapshot = await self.db.gexsnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            if snapshot and (snapshot.put25dIv is not None or snapshot.call25dIv is not None):
                p25 = snapshot.put25dIv or 0.0
                c25 = snapshot.call25dIv or 0.0
                raw_iv = (p25 + c25) / 2.0 if p25 > 0 and c25 > 0 else (p25 or c25)
                if raw_iv > 0.0:
                    return raw_iv / 100.0 if raw_iv > 1.0 else raw_iv
        except Exception as e:
            logger.warning(f"Error fetching IV from GexSnapshot for {ticker}: {e}")

        # 3. EOD iv_current from Dolt
        _, iv = self._query_dolt_volatility(ticker)
        if iv is not None:
            return iv
            
        # Try proxy if still None
        proxy_ticker = PROXY_MAPPINGS.get(ticker)
        if proxy_ticker:
            _, iv = self._query_dolt_volatility(proxy_ticker)
            if iv is not None:
                return iv

        return None
