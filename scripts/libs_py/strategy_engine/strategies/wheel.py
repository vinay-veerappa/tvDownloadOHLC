from datetime import datetime, date
import logging
from typing import List, Dict, Any, Optional


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


class WheelStrategy(Strategy):
    """
    systematic Option Wheel Strategy.
    1. Sell Cash-Secured Puts (CSPs) at target short delta (e.g. 0.30) & DTE (e.g. 45).
    2. If assigned, acquire the stock holding.
    3. Sell Covered Calls (CCs) against the stock holding.
    4. If CC is called away, remove stock holding and return to CSP writing.
    """
    async def scan(self, now: datetime) -> List[Signal]:

        ticker = self.underlying
        short_delta = self.p.get("short_delta", 0.30)
        target_dte = self.p.get("dte", 45)
        # Determine dynamic min_iv_rank using Tastytrade Playbook routing
        min_iv_rank = self.get_min_iv_rank_for_ticker(ticker, self.p.get("min_iv_rank", 30))

        # Retrieve Prisma database client
        prisma = self.s["prisma"]
        
        # Look up the silo Account
        account = await prisma.account.find_first(where={"name": self.name})
        if not account:
            logger.error(f"{self.name}: Silo account not found.")
            return []
        
        # Check if we have active trades in this account/strategy
        active_trades = await prisma.trade.find_many(
            where={
                "accountId": account.id,
                "status": "OPEN",
                "ticker": ticker
            },
            include={"legs": True}
        )
        if active_trades:
            # Already active in a trade, skip scanning
            return []

        # Check if we hold shares of this stock
        holding = await self.s["holdings"].get_holding(ticker)
        has_stock = holding is not None and holding["shares"] > 0

        # Fetch Spot Price
        try:
            spot_quote = await self.s["broker"].get_stock_quote(ticker)
            spot = spot_quote["last"]
        except Exception as e:
            logger.error(f"{self.name}: Failed to fetch stock quote: {e}")
            return []

        # ─── Filter 1: Blackout Calendar check ───
        if await self.s["calendar"].is_blackout_window(now):
            await self._log_near_miss(ticker, spot, "blackout_window_active", None, None, {"now": str(now)})
            return []

        # ─── Filter 2: Earnings calendar check (do not enter if earnings within target DTE) ───
        earnings_days = await self.s["earnings"].days_to_earnings(ticker)
        if earnings_days is not None and earnings_days <= target_dte:
            await self._log_near_miss(
                ticker, spot, "earnings_within_dte", 
                float(earnings_days), float(target_dte), 
                {"earnings_days": earnings_days}
            )
            return []

        # ─── Filter 3: Implied Volatility Rank check ───
        iv_data = await self.s["iv"].get_volatility_metrics(ticker)
        iv_rank = iv_data.get("iv_rank", 0.0)
        if iv_rank < min_iv_rank:
            await self._log_near_miss(
                ticker, spot, "iv_rank_below_threshold", 
                float(iv_rank), float(min_iv_rank), 
                {"iv_rank": iv_rank}
            )
            return []

        # ─── Expiry selection ───
        expiries = await self.s["broker"].get_expiries(ticker)
        if not expiries:
            logger.warning(f"{self.name}: No expiries returned for {ticker}")
            return []

        # Find expiry date closest to target DTE
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

        # Fetch options chain for that specific expiry
        chain = await self.s["broker"].get_chain(ticker, [target_dte_actual])
        if not chain:
            return []

        # Decide whether to sell a CSP (no stock held) or sell a CC (stock held)
        if not has_stock:
            # ─── PHASE 1: Write Cash-Secured Put (CSP) ───
            contract = self.s["broker"].find_strike_by_delta(chain, -short_delta, "PUT")
            if not contract:
                logger.warning(f"{self.name}: No PUT contract found matching delta {-short_delta}")
                return []

            strike = contract.strike
            mid_premium = _safe_mid(contract)  # D7

            # Capital secured = strike * 100
            max_capital = strike * 100.0
            max_risk = strike * 100.0

            # Calculate size (use up to 90% allocation for Cash-Secured Puts silo)
            qty = await self.s["sizing"].calculate_size(
                account.id, 
                max_risk_per_contract=max_risk,
                max_capital_per_contract=max_capital,
                max_risk_pct=0.95, 
                max_allocation_pct=0.95
            )

            if qty <= 0:
                logger.info(f"{self.name}: Size calculated is 0.")
                return []

            leg = LegSpec(
                option_type="PUT",
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

            signal = Signal(
                research_strategy_id=self.params.research_strategy_id,
                strategy_category="WHEEL",
                underlying=ticker,
                legs=[leg],
                max_risk_per_contract=max_risk,
                max_capital_per_contract=max_capital,
                profit_target_pct=self._exit_rules["profit_target_pct"],
                stop_loss_mult=self._exit_rules["stop_loss_mult"],
                time_stop_dte=self._exit_rules.get("time_stop_dte"),
                roll_at_dte=self._exit_rules["roll_at_dte"] if target_dte >= 40 else None,
                entry_features={
                    "iv_rank": iv_rank,
                    "spot": spot,
                    "target_delta": -short_delta,
                    "actual_delta": contract.delta,
                    "mid_premium": mid_premium
                },
                notes=f"Selling CSP {ticker} Put at {strike} (DTE {target_dte_actual})"
            )
            return [signal]

        else:
            # ─── PHASE 2: Write Covered Call (CC) ───
            # Stock is already held. We write calls matching the number of shares we own (1 contract per 100 shares)
            owned_shares = holding["shares"]  # D1: dict access
            qty = owned_shares // 100
            if qty <= 0:
                logger.warning(f"{self.name}: Owns {owned_shares} shares of {ticker}, which is less than 100 shares.")
                return []

            contract = self.s["broker"].find_strike_by_delta(chain, short_delta, "CALL")
            if not contract:
                logger.warning(f"{self.name}: No CALL contract found matching delta {short_delta}")
                return []

            # ─── D11: Cost-basis guard ───
            # Never write a CC below the stock's cost basis — that locks in a capital loss if assigned.
            # Spec §8.1: "If no call strike both above breakeven AND at ≥0.15 delta is available,
            # log STUCK_WAITING. No CC is sold. State remains LONG_STOCK."
            cost_basis = holding["cost_basis"]

            if contract.strike < cost_basis:
                # Try to find the nearest strike >= cost_basis
                logger.info(
                    f"{self.name}: Best delta strike {contract.strike} is below cost basis {cost_basis}. "
                    f"Searching for strike >= cost basis."
                )
                # We need to scan the chain for calls above cost_basis
                # Use find_strike_nearest as a proxy starting from cost_basis
                above_cb_contract = self.s["broker"].find_strike_nearest(chain, cost_basis, "CALL")
                if above_cb_contract and above_cb_contract.strike >= cost_basis:
                    contract = above_cb_contract
                    strike = contract.strike
                else:
                    # No valid strike — log STUCK_WAITING and skip (spec §8.1)
                    await self._log_near_miss(
                        ticker, spot, "STUCK_WAITING",
                        contract.strike, cost_basis,
                        {
                            "reason": "No call strike >= cost_basis available at current delta",
                            "cost_basis": cost_basis,
                            "best_strike": contract.strike,
                            "target_delta": short_delta
                        }
                    )
                    return []
            else:
                strike = contract.strike

            mid_premium = _safe_mid(contract)  # D7

            # Capital per contract is 0 since we already hold the stock!
            max_capital = 0.0
            max_risk = spot * 100.0 # Stock risk

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

            signal = Signal(
                research_strategy_id=self.params.research_strategy_id,
                strategy_category="WHEEL",
                underlying=ticker,
                legs=[leg],
                max_risk_per_contract=max_risk,
                max_capital_per_contract=max_capital,
                profit_target_pct=self._exit_rules["profit_target_pct"],  # M7
                stop_loss_mult=self._exit_rules["stop_loss_mult"],         # M7
                roll_at_dte=self._exit_rules["roll_at_dte"],               # M7 (None if 7DTE variant)
                entry_features={
                    "iv_rank": iv_rank,
                    "spot": spot,
                    "target_delta": short_delta,
                    "actual_delta": contract.delta,
                    "mid_premium": mid_premium,
                    "stock_cost_basis": holding["cost_basis"]  # D1: dict access
                },
                notes=f"Selling Covered Call {ticker} at {strike} (DTE {target_dte_actual})"
            )
            return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        ex = self._exit_rules  # M7: config-driven exit params
        ticker = trade.ticker.upper()
        spot = current_mtm["underlying_px"]

        # Standard profit target exit
        pt_action = await self._check_profit_target(trade, current_mtm, target_pct=ex["profit_target_pct"])
        if pt_action:
            return pt_action

        # DTE roll check: use config roll_at_dte; only applies when set (e.g. 21 for 45DTE variants)
        roll_dte = ex["roll_at_dte"]
        if roll_dte is not None:
            leg = trade.legs[0]
            expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
            dte = (expiry_date - now.date()).days
            if 0 < dte <= int(roll_dte):
                return ManageAction(close=True, reason="ROLL")  # D13: documented close-then-rescan

        # Expiration Check (0 DTE)
        leg = trade.legs[0]
        expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
        dte = (expiry_date - now.date()).days
        if dte <= 0:
            # Check if assigned
            strike = leg.strike
            if leg.optionType == "PUT" and spot <= strike:
                logger.info(f"{self.name}: PUT at strike {strike} is ITM at expiration (Spot: {spot:.2f}). Triggering Assignment.")
                return ManageAction(close=True, reason="ASSIGNMENT")
            elif leg.optionType == "CALL" and spot >= strike:
                logger.info(f"{self.name}: CALL at strike {strike} is ITM at expiration (Spot: {spot:.2f}). Stock called away.")
                return ManageAction(close=True, reason="ASSIGNMENT")
            # Expired worthless
            logger.info(f"{self.name}: Option at strike {strike} expired OTM (Spot: {spot:.2f}). Worthless expiration.")
            return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)
