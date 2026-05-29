from datetime import datetime, date
import logging
from typing import List, Dict, Any, Optional

from scripts.libs_py.strategy_engine.strategies.base import Strategy, Signal, LegSpec, NearMiss, ManageAction

logger = logging.getLogger(__name__)

def _safe_mid(contract) -> float:
    """Reliable mid-price; fall back to last when only one side is quoted (D7)."""
    if contract.bid and contract.bid > 0 and contract.ask and contract.ask > 0:
        return (contract.bid + contract.ask) / 2.0
    return contract.last or contract.bid or contract.ask or 0.0

class CollarStrategy(Strategy):
    """
    COLLAR strategy (Short OTM Call + Long OTM Put Collar for Equity Hedging/Premium).
    
    Tears:
    - Target 30 DTE.
    - Confirm the stock is held.
    - Sell 1 OTM Call (Strike A, delta ~0.20) for premium collection.
    - Buy 1 OTM Put (Strike B, delta ~0.15) for downside hedge.
    - Ensure Net Credit >= 0.00 (premium collected from call pays for the protective put).
    - Position size: 1 long contract and 1 short contract per 100 shares held.
    """
    async def scan(self, now: datetime) -> List[Signal]:
        ticker = self.underlying
        target_dte = self.p.get("dte", 30)
        short_call_delta = self.p.get("short_call_delta", 0.20)
        long_put_delta = self.p.get("long_put_delta", 0.15)

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

        # OTM Short Call (delta_call ~ 0.20)
        contract_call = self.s["broker"].find_strike_by_delta(chain, short_call_delta, "CALL")
        if not contract_call:
            logger.warning(f"{self.name}: No Short CALL contract found near delta {short_call_delta}")
            return []

        strike_call = contract_call.strike
        mid_call = _safe_mid(contract_call)

        # OTM Long Put (delta_put ~ -0.15)
        # Note: put delta is negative
        contract_put = self.s["broker"].find_strike_by_delta(chain, -long_put_delta, "PUT")
        if not contract_put:
            logger.warning(f"{self.name}: No Long PUT contract found near delta {-long_put_delta}")
            return []

        strike_put = contract_put.strike
        mid_put = _safe_mid(contract_put)

        # Net Credit check: Call sold mid - Put bought mid >= 0.00 (Credit or zero-cost)
        net_credit = mid_call - mid_put

        if net_credit < -0.05: # allow a tiny credit threshold / buffer
            await self._log_near_miss(
                ticker, spot, "net_credit_below_zero",
                net_credit, 0.00,
                {
                    "mid_call": mid_call,
                    "mid_put": mid_put,
                    "strike_call": strike_call,
                    "strike_put": strike_put
                }
            )
            return []

        # Sizing rules:
        # Contract quantity = shares // 100
        qty = shares // 100

        if qty <= 0:
            logger.warning(f"{self.name}: Shares holding {shares} is less than 100. Skipping.")
            return []

        leg_call = LegSpec(
            option_type="CALL",
            side="SHORT",
            strike=strike_call,
            expiry=expiry_date,
            quantity=qty,
            symbol=contract_call.symbol,
            mid=mid_call,
            bid=contract_call.bid,
            ask=contract_call.ask,
            iv=contract_call.iv,
            delta=contract_call.delta,
            gamma=contract_call.gamma,
            theta=contract_call.theta,
            vega=contract_call.vega
        )

        leg_put = LegSpec(
            option_type="PUT",
            side="LONG",
            strike=strike_put,
            expiry=expiry_date,
            quantity=qty,
            symbol=contract_put.symbol,
            mid=mid_put,
            bid=contract_put.bid,
            ask=contract_put.ask,
            iv=contract_put.iv,
            delta=contract_put.delta,
            gamma=contract_put.gamma,
            theta=contract_put.theta,
            vega=contract_put.vega
        )

        entry_features = {
            "spot": spot,
            "stock_shares": shares,
            "stock_cost_basis": cost_basis,
            "strike_call": strike_call,
            "strike_put": strike_put,
            "mid_call": mid_call,
            "mid_put": mid_put,
            "net_credit": net_credit,
            "actual_dte": target_dte_actual
        }

        # Sizing calculations for backtesting/silo check
        max_capital = 0.0 # No additional capital required (covered by shares)
        max_risk = (spot - strike_put) * 100.0 * qty # Limited risk to the downside put floor

        signal = Signal(
            research_strategy_id=self.params.research_strategy_id,
            strategy_category="COLLAR",
            underlying=ticker,
            legs=[leg_call, leg_put],
            max_risk_per_contract=max_risk / qty,
            max_capital_per_contract=max_capital,
            profit_target_pct=self._exit_rules["profit_target_pct"],
            stop_loss_mult=self._exit_rules["stop_loss_mult"],
            roll_at_dte=self._exit_rules["roll_at_dte"],
            entry_features=entry_features,
            notes=f"Collar Hedge on {ticker}: Short {qty}x {strike_call} Call, Long {qty}x {strike_put} Put (Net Credit: ${net_credit:.2f})"
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
        leg_call = [l for l in trade.legs if l.optionType == "CALL"][0]
        leg_put = [l for l in trade.legs if l.optionType == "PUT"][0]
        expiry_date = leg_call.expiry.date() if isinstance(leg_call.expiry, datetime) else leg_call.expiry
        dte = (expiry_date - now.date()).days
        if dte <= 0:
            strike_call = leg_call.strike
            strike_put = leg_put.strike
            if spot >= strike_call:
                logger.info(f"{self.name}: Spot ({spot:.2f}) >= Strike Call ({strike_call:.2f}) at expiration. Stock called away.")
                return ManageAction(close=True, reason="ASSIGNMENT")
            elif spot <= strike_put:
                logger.info(f"{self.name}: Spot ({spot:.2f}) <= Strike Put ({strike_put:.2f}) at expiration. Protective Put protection triggered.")
                return ManageAction(close=True, reason="ASSIGNMENT")
            else:
                logger.info(f"{self.name}: Collar options expired worthless. Stock retained.")
                return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)
