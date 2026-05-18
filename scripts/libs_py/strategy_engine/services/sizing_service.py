import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SizingService:
    """
    Evaluates capital availability and risk policy rules to compute safe trade sizing.
    Enforces maximum capital allocation (default 10% per trade) and maximum risk (default 2% per trade).
    """
    def __init__(self, prisma_client):
        self.prisma = prisma_client

    async def calculate_size(
        self,
        account_id: str,
        max_risk_per_contract: float,       # Max loss of the position per contract/spread unit
        max_capital_per_contract: float,    # Cash or margin buying power required per unit
        max_risk_pct: float = 0.02,         # Max risk % of total account equity per trade (default 2%)
        max_allocation_pct: float = 0.10,   # Max capital % of total account equity per trade (default 10%)
    ) -> int:
        """
        Calculates the maximum safe contract/shares count to open.
        Returns 0 if account balance is insufficient or risk rules are breached.
        """
        try:
            account = await self.prisma.account.find_unique(where={"id": account_id})
            if not account:
                logger.error(f"SizingService: Account {account_id} not found in database.")
                return 0

            balance = account.currentBalance
            if balance <= 0:
                logger.warning(f"SizingService: Account {account.name} has zero or negative balance: ${balance:,.2f}")
                return 0

            # 1. Capital-based limit
            max_capital_allowed = balance * max_allocation_pct
            size_by_capital = 999999
            if max_capital_per_contract > 0:
                size_by_capital = int(math.floor(max_capital_allowed / max_capital_per_contract))

            # 2. Risk-based limit
            max_risk_allowed = balance * max_risk_pct
            size_by_risk = 999999
            if max_risk_per_contract > 0:
                size_by_risk = int(math.floor(max_risk_allowed / max_risk_per_contract))

            # Selected size is the minimum of both bounds
            size = min(size_by_capital, size_by_risk)

            if size < 0:
                return 0

            logger.info(
                f"SizingService for {account.name} (Balance: ${balance:,.2f}): "
                f"Capital Cap ({max_allocation_pct*100}% of bal = ${max_capital_allowed:,.2f}, req={max_capital_per_contract}) -> {size_by_capital} units. "
                f"Risk Cap ({max_risk_pct*100}% of bal = ${max_risk_allowed:,.2f}, req={max_risk_per_contract}) -> {size_by_risk} units. "
                f"Final Size: {size}"
            )
            return size

        except Exception as e:
            logger.error(f"SizingService: Error calculating size: {e}")
            return 0
