from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Optional, List
import pytz
import yfinance as yf
import pandas as pd
import numpy as np

# Setup logger
logger = logging.getLogger(__name__)


@dataclass
class EarningsAnnouncement:
    """A scheduled earnings announcement."""
    ticker: str
    earnings_date: datetime
    before_market: bool
    confirmed: bool


class EarningsService:
    """Manages earnings calendar via yfinance + EarningsCalendar table.

    Populated by a weekly cron job (`fetch_upcoming_all`).
    """

    def __init__(self, prisma_client):
        """
        Args:
            prisma_client: Prisma client instance
        """
        self.db = prisma_client

    def _normalize_dt(self, dt: Optional[datetime]) -> datetime:
        """Normalize datetime to timezone-aware UTC datetime."""
        if dt is None:
            return datetime.now(pytz.utc)
        if dt.tzinfo is None:
            return pytz.utc.localize(dt)
        return dt.astimezone(pytz.utc)

    async def get_next_earnings(self, ticker: str) -> Optional[EarningsAnnouncement]:
        """Next upcoming earnings announcement for ticker, or None if not scheduled."""
        now_utc = datetime.now(pytz.utc)
        
        try:
            event = await self.db.earningscalendar.find_first(
                where={
                    "ticker": ticker,
                    "earningsDate": {
                        "gte": now_utc
                    }
                },
                order={
                    "earningsDate": "asc"
                }
            )
        except Exception as e:
            logger.error(f"Failed to query next earnings for ticker {ticker}: {e}")
            return None

        if event:
            # Ensure database datetime is UTC timezone-aware
            evt_date = event.earningsDate
            if evt_date.tzinfo is None:
                evt_date = pytz.utc.localize(evt_date)
            return EarningsAnnouncement(
                ticker=event.ticker,
                earnings_date=evt_date,
                before_market=event.beforeMarket,
                confirmed=event.confirmed
            )
        return None

    async def is_earnings_within(self, ticker: str, days: int) -> bool:
        """True if ticker has earnings within `days` of now."""
        next_earn = await self.get_next_earnings(ticker)
        if not next_earn:
            return False
            
        now_utc = datetime.now(pytz.utc)
        limit = now_utc + timedelta(days=days)
        return next_earn.earnings_date <= limit

    async def days_to_earnings(self, ticker: str) -> Optional[int]:
        """Calendar days from today to next earnings. None if not scheduled."""
        next_earn = await self.get_next_earnings(ticker)
        if not next_earn:
            return None
            
        now_utc = datetime.now(pytz.utc)
        # Convert both to date in US/Eastern to handle local calendar days accurately
        tz = pytz.timezone("US/Eastern")
        today_local = now_utc.astimezone(tz).date()
        earn_local = next_earn.earnings_date.astimezone(tz).date()
        
        return (earn_local - today_local).days

    async def fetch_upcoming_all(self, tickers: List[str]) -> int:
        """Pull upcoming earnings from yfinance for each ticker, upsert into EarningsCalendar.

        Returns count of rows upserted. Called weekly by a cron job.
        Robust to yfinance flakiness — partial failures are logged but don't raise.
        """
        upserted_count = 0
        now_utc = datetime.now(pytz.utc)
        tz_et = pytz.timezone("US/Eastern")

        for ticker in tickers:
            logger.info(f"Fetching earnings calendar for {ticker} via yfinance...")
            try:
                # Clean ticker for yfinance lookup (e.g. QQQ -> QQQ, SPY -> SPY)
                clean_ticker = ticker.replace("!", "")
                if clean_ticker == "SPX":
                    # SPX index doesn't have earnings; skip
                    continue

                t_obj = yf.Ticker(clean_ticker)
                calendar = t_obj.calendar

                if calendar is None or (isinstance(calendar, dict) and not calendar):
                    logger.warning(f"No calendar found for {ticker}")
                    continue

                dates = []
                # Handle different yfinance versions and formats
                if isinstance(calendar, dict):
                    dates = calendar.get("Earnings Date", [])
                elif isinstance(calendar, pd.DataFrame):
                    # Check if 'Earnings Date' is index
                    if "Earnings Date" in calendar.index:
                        dates_val = calendar.loc["Earnings Date"].values[0]
                        if isinstance(dates_val, (list, np.ndarray, pd.Series)):
                            dates = list(dates_val)
                        else:
                            dates = [dates_val]
                    # Check if 'Earnings Date' is column
                    elif "Earnings Date" in calendar.columns:
                        dates = calendar["Earnings Date"].tolist()

                # Process found dates
                for d in dates:
                    if pd.isna(d):
                        continue
                    
                    # Convert to datetime if it's pandas timestamp or date
                    if isinstance(d, (pd.Timestamp, date, datetime)):
                        if isinstance(d, date) and not isinstance(d, datetime):
                            d_dt = datetime.combine(d, datetime.min.time())
                        else:
                            d_dt = d.to_pydatetime() if hasattr(d, "to_pydatetime") else d
                    else:
                        try:
                            # Try parsing string
                            d_dt = pd.to_datetime(d).to_pydatetime()
                        except Exception as e:
                            logger.error(f"Failed to parse earnings date '{d}': {e}")
                            continue

                    # Localize to UTC
                    if d_dt.tzinfo is None:
                        # yfinance usually returns exchange local times, which is Eastern for standard US equities
                        # Let's assume Eastern if naive and convert to UTC
                        d_dt = tz_et.localize(d_dt).astimezone(pytz.utc)
                    else:
                        d_dt = d_dt.astimezone(pytz.utc)

                    # Determine if BMO (Before Market Open) or AMC (After Market Close)
                    # Convert to Eastern Time to check hours
                    d_dt_et = d_dt.astimezone(tz_et)
                    # BMO standard: if time is before 12:00 PM ET
                    before_market = d_dt_et.hour < 12

                    # Upsert into DB with fallback protection
                    try:
                        await self.db.earningscalendar.upsert(
                            where={"ticker_earningsDate": {"ticker": ticker, "earningsDate": d_dt}},
                            data={
                                "create": {
                                    "ticker": ticker,
                                    "earningsDate": d_dt,
                                    "beforeMarket": before_market,
                                    "confirmed": True,
                                    "source": "yfinance",
                                    "fetchedAt": now_utc
                                },
                                "update": {
                                    "beforeMarket": before_market,
                                    "confirmed": True,
                                    "fetchedAt": now_utc
                                }
                            }
                        )
                    except Exception as ex:
                        logger.debug(f"Prisma composite upsert failed, executing manual fallback: {ex}")
                        existing = await self.db.earningscalendar.find_first(
                            where={
                                "ticker": ticker,
                                "earningsDate": d_dt
                            }
                        )
                        if existing:
                            await self.db.earningscalendar.update(
                                where={"id": existing.id},
                                data={
                                    "beforeMarket": before_market,
                                    "confirmed": True,
                                    "fetchedAt": now_utc
                                }
                            )
                        else:
                            await self.db.earningscalendar.create(
                                data={
                                    "ticker": ticker,
                                    "earningsDate": d_dt,
                                    "beforeMarket": before_market,
                                    "confirmed": True,
                                    "source": "yfinance",
                                    "fetchedAt": now_utc
                                }
                            )

                    upserted_count += 1
                    logger.info(f"Upserted earnings for {ticker} on {d_dt_et} (before_market={before_market})")

            except Exception as e:
                logger.error(f"Error fetching/processing earnings for ticker {ticker}: {e}", exc_info=True)

        return upserted_count
