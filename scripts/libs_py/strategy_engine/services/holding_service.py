from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Optional, TypedDict
import pytz

# Setup logger
logger = logging.getLogger(__name__)


class HoldingRecord(TypedDict):
    """An active equity or option holding in the account."""
    ticker: str
    shares: int
    cost_basis: float
    acquired_at: datetime


class HoldingService:
    """Read/Write wrapper over Prisma `Holding` table.

    Tracks external portfolio state (e.g. underlying shares held) to check
    hedging/covered status or rule out duplicate entries.
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

    async def get_holding(self, ticker: str) -> Optional[HoldingRecord]:
        """Get holding for a specific ticker, or None if not held."""
        try:
            holding = await self.db.holding.find_unique(
                where={
                    "ticker": ticker
                }
            )
        except Exception as e:
            logger.error(f"Failed to query holding for ticker {ticker}: {e}")
            return None

        if holding:
            acq_at = holding.acquiredAt
            if acq_at.tzinfo is None:
                acq_at = pytz.utc.localize(acq_at)
            return HoldingRecord(
                ticker=holding.ticker,
                shares=holding.shares,
                cost_basis=holding.costBasis,
                acquired_at=acq_at
            )
        return None

    async def add_holding(
        self,
        ticker: str,
        shares: int,
        cost_basis: float,
        acquired_at: Optional[datetime] = None,
    ) -> HoldingRecord:
        """Add/increment a position. Weighted averages cost basis if already exists."""
        utc_acq = self._normalize_dt(acquired_at)
        existing = await self.get_holding(ticker)

        if existing:
            # Average cost basis calculation
            total_shares = existing["shares"] + shares
            if total_shares <= 0:
                # Liquidated or invalid state, delete it
                try:
                    await self.db.holding.delete(where={"ticker": ticker})
                except Exception as e:
                    logger.error(f"Failed to delete holding on zero shares for {ticker}: {e}")
                return HoldingRecord(ticker=ticker, shares=0, cost_basis=0.0, acquired_at=utc_acq)

            weighted_cost = (
                (existing["shares"] * existing["cost_basis"]) + (shares * cost_basis)
            ) / total_shares

            try:
                updated = await self.db.holding.update(
                    where={"ticker": ticker},
                    data={
                        "shares": total_shares,
                        "costBasis": weighted_cost,
                        "updatedAt": datetime.now(pytz.utc)
                    }
                )
            except Exception as e:
                logger.error(f"Failed to update existing holding for {ticker}: {e}")
                raise e

            acq_at = updated.acquiredAt
            if acq_at.tzinfo is None:
                acq_at = pytz.utc.localize(acq_at)
            return HoldingRecord(
                ticker=updated.ticker,
                shares=updated.shares,
                cost_basis=updated.costBasis,
                acquired_at=acq_at
            )
        else:
            # Create new holding
            try:
                created = await self.db.holding.create(
                    data={
                        "ticker": ticker,
                        "shares": shares,
                        "costBasis": cost_basis,
                        "acquiredAt": utc_acq
                    }
                )
            except Exception as e:
                logger.error(f"Failed to create new holding for {ticker}: {e}")
                raise e

            acq_at = created.acquiredAt
            if acq_at.tzinfo is None:
                acq_at = pytz.utc.localize(acq_at)
            return HoldingRecord(
                ticker=created.ticker,
                shares=created.shares,
                cost_basis=created.costBasis,
                acquired_at=acq_at
            )

    async def remove_holding(self, ticker: str, shares: int) -> Optional[HoldingRecord]:
        """Reduce a position. If shares drop to <= 0, deletes holding from DB and returns None."""
        existing = await self.get_holding(ticker)
        if not existing:
            logger.warning(f"Attempted to remove holding for ticker {ticker} but none exists.")
            return None

        remaining_shares = existing["shares"] - shares
        if remaining_shares <= 0:
            try:
                await self.db.holding.delete(
                    where={
                        "ticker": ticker
                    }
                )
                logger.info(f"Position in {ticker} fully closed. Removed from database.")
            except Exception as e:
                logger.error(f"Failed to delete holding for {ticker}: {e}")
            return None
        else:
            try:
                updated = await self.db.holding.update(
                    where={
                        "ticker": ticker
                    },
                    data={
                        "shares": remaining_shares,
                        "updatedAt": datetime.now(pytz.utc)
                    }
                )
            except Exception as e:
                logger.error(f"Failed to reduce holding for {ticker}: {e}")
                raise e

            acq_at = updated.acquiredAt
            if acq_at.tzinfo is None:
                acq_at = pytz.utc.localize(acq_at)
            return HoldingRecord(
                ticker=updated.ticker,
                shares=updated.shares,
                cost_basis=updated.costBasis,
                acquired_at=acq_at
            )

    async def add_shares(self, ticker: str, shares: int, cost_basis: float, acquired_at: Optional[datetime] = None) -> HoldingRecord:
        """Alias for add_holding, used by paper executor during assignments."""
        return await self.add_holding(ticker, shares, cost_basis, acquired_at)

    async def remove_shares(self, ticker: str, shares: int, removed_at: Optional[datetime] = None) -> Optional[HoldingRecord]:
        """Alias for remove_holding, used by paper executor during call aways."""
        return await self.remove_holding(ticker, shares)
