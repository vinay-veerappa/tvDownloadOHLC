from datetime import datetime, date, timedelta
import logging
from typing import List, Dict, Any, Optional
import pytz


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.strategy_engine.strategies.base import Strategy, Signal, LegSpec, NearMiss, ManageAction

logger = logging.getLogger(__name__)


def _safe_mid(contract) -> float:
    """Reliable mid-price; fall back to last when only one side is quoted (D7)."""
    if contract.bid and contract.bid > 0 and contract.ask and contract.ask > 0:
        return (contract.bid + contract.ask) / 2.0
    return contract.last or contract.bid or contract.ask or 0.0


class IncomeCcStrategy(Strategy):
    """
    Systematic covered calls written on long stock holdings based on statistical tier boundaries.
    Tiers:
    - Never write calls below the stock's cost basis.
    - If IV Rank >= 50: Sell 0.15 Delta Call (rich premium, high safety).
    - If 30 <= IV Rank < 50: Sell 0.20 Delta Call.
    - If IV Rank < 30: Sell 0.30 Delta Call (aggressive premium capture).
    - Target 30 DTE.
    - Special staging rule for RIVN: must be held >= 4 weeks before call writing begins.
    """
    async def scan(self, now: datetime) -> List[Signal]:
        ticker = self.underlying
        target_dte = 30

        # Check if the ticker's holding is disabled in config.yaml (M10)
        config_holdings = self.s.get("config", {}).get("holdings", {})
        ticker_holding_cfg = config_holdings.get(ticker, {})
        if isinstance(ticker_holding_cfg, dict) and not ticker_holding_cfg.get("enabled", True):
            # Suppress execution scans and near-miss logs completely for disabled staged tickers (M10)
            return []

        # Retrieve Prisma database client
        prisma = self.s["prisma"]
        account = await prisma.account.find_first(where={"name": self.name})
        if not account:
            logger.error(f"{self.name}: Silo account not found.")
            return []

        # Check if we have active trades in this account
        active_trades = await prisma.trade.find_many(
            where={
                "accountId": account.id,
                "status": "OPEN",
                "ticker": ticker
            }
        )
        if active_trades:
            return []

        # ─── Check stock holding ───
        holding = await self.s["holdings"].get_holding(ticker)
        if not holding or holding["shares"] < 100:
            # No shares or less than 100 shares, cannot write covered call
            return []

        # ─── Special staging check for RIVN ───
        if ticker == "RIVN":
            acquired_at = holding["acquired_at"]  # D1: dict access
            if isinstance(acquired_at, str):
                acquired_at = datetime.fromisoformat(acquired_at.replace("Z", "+00:00"))

            # Check if held for >= 4 weeks (28 days)
            days_held = (now.replace(tzinfo=pytz.utc) - acquired_at.replace(tzinfo=pytz.utc)).days
            if days_held < 28:
                await self._log_near_miss(
                    ticker, holding["cost_basis"], "rivn_staging_active",
                    float(days_held), 28.0,
                    {"days_held": days_held, "acquiredAt": str(acquired_at)}
                )
                return []

        # Fetch Spot Price
        try:
            spot_quote = await self.s["broker"].get_stock_quote(ticker)
            spot = spot_quote["last"]
        except Exception as e:
            logger.error(f"{self.name}: Failed to fetch stock quote: {e}")
            return []

        # ─── Filter 1: Blackout economic calendar ───
        if await self.s["calendar"].is_blackout_window(now):
            await self._log_near_miss(ticker, spot, "blackout_window_active", None, None, {"now": str(now)})
            return []

        # ─── Filter 2: Earnings Check (avoid writing within 14 days of earnings) ───
        earnings_days = await self.s["earnings"].days_to_earnings(ticker)
        if earnings_days is not None and earnings_days <= 14:
            await self._log_near_miss(
                ticker, spot, "earnings_within_14_days", 
                float(earnings_days), 14.0, 
                {"earnings_days": earnings_days}
            )
            return []

        # ─── Determine Strike Delta Tier using IV Rank ───
        iv_data = await self.s["iv"].get_volatility_metrics(ticker)
        iv_rank = iv_data.get("iv_rank", 0.0)

        if iv_rank >= 50.0:
            target_delta = 0.15
        elif iv_rank >= 30.0:
            target_delta = 0.20
        else:
            target_delta = 0.30

        # ─── Expiry selection ───
        expiries = await self.s["broker"].get_expiries(ticker)
        if not expiries:
            return []

        best_expiry_str = None
        best_dte_diff = 9999
        for exp_str in expiries:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            dte = (exp_date - now.date()).days
            diff = abs(dte - target_dte)
            if diff < best_dte_diff:
                best_dte_diff = diff
                best_expiry_str = exp_str

        if not best_expiry_str:
            return []

        expiry_date = datetime.strptime(best_expiry_str, "%Y-%m-%d").date()
        target_dte_actual = (expiry_date - now.date()).days

        chain = await self.s["broker"].get_chain(ticker, [target_dte_actual])
        if not chain:
            return []

        # Find Call closest to target delta
        contract = self.s["broker"].find_strike_by_delta(chain, target_delta, "CALL")
        if not contract:
            return []

        strike = contract.strike

        # Enforce strike >= stock cost basis to prevent selling at a capital loss
        if strike < holding["cost_basis"]:  # D1: dict access
            logger.info(f"{self.name}: Best delta strike {strike} is below cost basis {holding['cost_basis']}. Adjusting to nearest strike >= cost basis.")
            # Search for the next available strike >= cost basis
            contracts = chain.calls
            valid_contracts = [c for c in contracts if c.strike >= holding["cost_basis"]]
            if valid_contracts:
                # Find the one closest to the cost basis
                contract = min(valid_contracts, key=lambda c: c.strike)
                strike = contract.strike
            else:
                # No strike available above cost basis, skip
                await self._log_near_miss(
                    ticker, spot, "no_strike_above_cost_basis",
                    strike, holding["cost_basis"],
                    {"cost_basis": holding["cost_basis"]}
                )
                return []

        mid_premium = _safe_mid(contract)  # D7
        qty = holding["shares"] // 100  # D1: dict access

        leg = LegSpec(
            option_type="CALL",
            side="SHORT",
            strike=strike,
            expiry=expiry_date,
            quantity=qty,
            symbol=contract.symbol,
            mid=mid_premium,
            bid=contract.bid,
            ask=contract.ask,
            iv=contract.iv,
            delta=contract.delta,
            gamma=contract.gamma,
            theta=contract.theta,
            vega=contract.vega
        )

        entry_features = {
            "spot": spot,
            "stock_cost_basis": holding["cost_basis"],  # D1: dict access
            "target_delta": target_delta,
            "actual_delta": contract.delta,
            "iv_rank": iv_rank,
            "mid_premium": mid_premium,
            "actual_dte": target_dte_actual
        }

        signal = Signal(
            research_strategy_id=self.params.research_strategy_id,
            strategy_category="INCOME_CC",
            underlying=ticker,
            legs=[leg],
            max_risk_per_contract=spot * 100.0,
            max_capital_per_contract=0.0,  # Stock is already held
            profit_target_pct=self._exit_rules["profit_target_pct"],  # M7
            stop_loss_mult=self._exit_rules["stop_loss_mult"],         # M7
            roll_at_dte=self._exit_rules["roll_at_dte"],               # M7
            entry_features=entry_features,
            notes=f"Selling covered Call {ticker} at {strike} (DTE {target_dte_actual}) against {holding['shares']} shares"  # D1
        )
        return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        ex = self._exit_rules  # M7: config-driven exit params
        ticker = trade.ticker.upper()
        spot = current_mtm["underlying_px"]

        # 1. Profit Target Check
        pt_action = await self._check_profit_target(trade, current_mtm, target_pct=ex["profit_target_pct"])
        if pt_action:
            return pt_action

        # 2. Tastytrade 21-DTE roll check (C9: explicit reason; D13: caller controls reason)
        roll_dte = ex["roll_at_dte"]
        if roll_dte is not None:
            dte_action = await self._check_dte_time_stop(trade, now, close_at_dte=int(roll_dte), reason="ROLL")
            if dte_action:
                logger.info(f"{self.name}: Covered Call at {roll_dte} DTE. Rolling position.")
                return dte_action

        # Expiration Check (0 DTE)
        leg = trade.legs[0]
        expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
        if (expiry_date - now.date()).days <= 0:
            strike = leg.strike
            if spot >= strike:
                # ITM: Assignment! Stock is called away.
                logger.info(f"{self.name}: Call at strike {strike} is ITM at expiration. Stock called away at cost basis.")
                return ManageAction(close=True, reason="ASSIGNMENT")
            else:
                # OTM: Expired worthless
                logger.info(f"{self.name}: Call at strike {strike} expired OTM. Retaining stock and premium.")
                return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)
