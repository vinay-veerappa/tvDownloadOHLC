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

class StockRepairStrategy(Strategy):
    """
    STOCK_REPAIR strategy (Ratio Call Spread for Underwater Positions).
    
    Tears:
    - Target 30 DTE.
    - Confirm the stock is held and is currently underwater (Spot < Cost Basis).
    - Buy 1 ATM Call (Strike A, delta ~0.40).
    - Sell 2 OTM Calls (Strike B, midpoint between spot and cost basis).
    - Ensure Net Credit >= 0.00 (zero cost or credit).
    - Position size: 1 long contract and 2 short contracts per 100 shares held.
    - Achieves accelerated breakeven at Strike B without putting up more capital.
    """
    async def scan(self, now: datetime) -> List[Signal]:
        ticker = self.underlying
        target_dte = self.p.get("dte", 30)
        delta_long = self.p.get("delta_long", 0.40)

        # Check if the ticker's holding is disabled in config.yaml
        config_holdings = self.s.get("config", {}).get("holdings", {})
        ticker_holding_cfg = config_holdings.get(ticker, {})
        if isinstance(ticker_holding_cfg, dict) and not ticker_holding_cfg.get("enabled", True):
            return []

        # Retrieve holding status
        holding = await self.s["holdings"].get_holding(ticker)
        if not holding or holding.get("shares", 0) <= 0:
            return []

        shares = holding["shares"]
        cost_basis = holding["cost_basis"]

        # Fetch Spot Price
        try:
            spot_quote = await self.s["broker"].get_stock_quote(ticker)
            spot = spot_quote["last"]
        except Exception as e:
            logger.error(f"{self.name}: Failed to fetch stock quote: {e}")
            return []

        # Only trigger if the stock is underwater
        if spot >= cost_basis:
            await self._log_near_miss(
                ticker, spot, "stock_not_underwater",
                float(spot), float(cost_basis),
                {"cost_basis": cost_basis}
            )
            return []

        # Retrieve Prisma client and check active trades
        prisma = self.s["prisma"]
        account = await prisma.account.find_first(where={"name": self.name})
        if not account:
            logger.error(f"{self.name}: Silo account not found.")
            return []

        active_trades = await prisma.trade.find_many(
            where={
                "accountId": account.id,
                "status": "OPEN",
                "ticker": ticker
            }
        )
        if active_trades:
            return []

        # ─── Filter 1: Blackout Calendar ───
        if await self.s["calendar"].is_blackout_window(now):
            await self._log_near_miss(ticker, spot, "blackout_window_active", None, None, {"now": str(now)})
            return []

        # ─── Expiry selection ───
        expiries = await self.s["broker"].get_expiries(ticker)
        if not expiries:
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

        # Fetch option chain for expiry
        chain = await self.s["broker"].get_chain(ticker, [target_dte_actual])
        if not chain:
            return []

        # Call A (ATM / delta_long Call)
        contract_a = self.s["broker"].find_strike_by_delta(chain, delta_long, "CALL")
        if not contract_a:
            logger.warning(f"{self.name}: No Long CALL contract found near delta {delta_long}")
            return []

        strike_a = contract_a.strike
        mid_a = _safe_mid(contract_a)

        # Call B (Midpoint of Spot & Cost Basis)
        target_strike_b = (spot + cost_basis) / 2.0
        # Must be above Strike A to form the ratio call spread
        min_strike_b = strike_a + 0.50
        if target_strike_b < min_strike_b:
            target_strike_b = min_strike_b

        contract_b = self.s["broker"].find_strike_nearest(chain, target_strike_b, "CALL")
        if not contract_b or contract_b.strike <= strike_a:
            # Fallback: scan for any call higher than strike_a
            calls_above_a = [c for c in chain.calls if c.strike > strike_a]
            if not calls_above_a:
                logger.warning(f"{self.name}: No Call strikes found above Strike A {strike_a}")
                return []
            contract_b = sorted(calls_above_a, key=lambda c: abs(c.strike - target_strike_b))[0]

        strike_b = contract_b.strike
        mid_b = _safe_mid(contract_b)

        # Net Credit check: (2 * Short Call Premium) - Long Call Premium >= 0.00
        net_credit = (2 * mid_b) - mid_a

        if net_credit < -0.05: # allow a tiny credit threshold / buffer
            await self._log_near_miss(
                ticker, spot, "net_credit_below_zero",
                net_credit, 0.00,
                {
                    "mid_a": mid_a,
                    "mid_b": mid_b,
                    "strike_a": strike_a,
                    "strike_b": strike_b,
                    "target_strike_b": target_strike_b
                }
            )
            return []

        # Sizing rules:
        # Long Call quantity = shares // 100
        qty_long = shares // 100
        qty_short = 2 * qty_long

        if qty_long <= 0:
            logger.warning(f"{self.name}: Shares holding {shares} is less than 100. Skipping.")
            return []

        leg_long = LegSpec(
            option_type="CALL",
            side="LONG",
            strike=strike_a,
            expiry=expiry_date,
            quantity=qty_long,
            symbol=contract_a.symbol,
            mid=mid_a,
            bid=contract_a.bid,
            ask=contract_a.ask,
            iv=contract_a.iv,
            delta=contract_a.delta,
            gamma=contract_a.gamma,
            theta=contract_a.theta,
            vega=contract_a.vega
        )

        leg_short = LegSpec(
            option_type="CALL",
            side="SHORT",
            strike=strike_b,
            expiry=expiry_date,
            quantity=qty_short,
            symbol=contract_b.symbol,
            mid=mid_b,
            bid=contract_b.bid,
            ask=contract_b.ask,
            iv=contract_b.iv,
            delta=contract_b.delta,
            gamma=contract_b.gamma,
            theta=contract_b.theta,
            vega=contract_b.vega
        )

        entry_features = {
            "spot": spot,
            "stock_shares": shares,
            "stock_cost_basis": cost_basis,
            "strike_a": strike_a,
            "strike_b": strike_b,
            "mid_a": mid_a,
            "mid_b": mid_b,
            "net_credit": net_credit,
            "actual_dte": target_dte_actual
        }

        # Sizing calculations for backtesting/silo check
        max_capital = 0.0 # No additional capital required (covered by shares and the ratio spread)
        max_risk = 0.0    # Stock is already owned, no new cash layout

        signal = Signal(
            research_strategy_id=self.params.research_strategy_id,
            strategy_category="STOCK_REPAIR",
            underlying=ticker,
            legs=[leg_long, leg_short],
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            profit_target_pct=self._exit_rules["profit_target_pct"],
            stop_loss_mult=self._exit_rules["stop_loss_mult"],
            roll_at_dte=self._exit_rules["roll_at_dte"],
            entry_features=entry_features,
            notes=f"Stock Repair Ratio Call Spread on {ticker}: Long {qty_long}x {strike_a} Call, Short {qty_short}x {strike_b} Call (Net Credit: ${net_credit:.2f})"
        )
        return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        ex = self._exit_rules
        spot = current_mtm["underlying_px"]

        # 1. Manage at 21 DTE
        roll_dte = ex["roll_at_dte"]
        if roll_dte is not None:
            leg = trade.legs[0]
            expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
            dte = (expiry_date - now.date()).days
            if 0 < dte <= int(roll_dte):
                logger.info(f"{self.name}: Roll triggered at {dte} DTE.")
                return ManageAction(close=True, reason="ROLL")

        # 2. Expiration Day Check (0 DTE)
        leg_long = [l for l in trade.legs if l.side == "LONG"][0]
        leg_short = [l for l in trade.legs if l.side == "SHORT"][0]
        expiry_date = leg_long.expiry.date() if isinstance(leg_long.expiry, datetime) else leg_long.expiry
        dte = (expiry_date - now.date()).days
        if dte <= 0:
            strike_b = leg_short.strike
            if spot >= strike_b:
                logger.info(f"{self.name}: Spot ({spot:.2f}) >= Strike B ({strike_b:.2f}) at expiration. Stock called away (Repair complete!).")
                return ManageAction(close=True, reason="ASSIGNMENT")
            else:
                logger.info(f"{self.name}: Ratio call spread expired below Strike B at expiration. Worthless expiration.")
                return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)
