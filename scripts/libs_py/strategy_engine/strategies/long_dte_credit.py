from datetime import datetime, date
import logging
from typing import List, Dict, Any, Optional

from scripts.libs_py.strategy_engine.strategies.base import Strategy, Signal, LegSpec, NearMiss, ManageAction

logger = logging.getLogger(__name__)

class LongDteCreditStrategy(Strategy):
    """
    Tastytrade 45-DTE systematic Credit Spreads (PCS).
    Sells a 45-DTE Put Credit Spread (PCS) during elevated IV Rank.
    Tastytrade Rules:
    - Target 45 DTE.
    - IV Rank >= 35.
    - Exit/Roll at 50% profit target.
    - Exit/Roll strictly at 21 DTE to eliminate gamma risk.
    """
    async def scan(self, now: datetime) -> List[Signal]:
        ticker = self.underlying
        short_delta = self.p.get("short_delta", 0.16)
        width_pct = self.p.get("width_pct", 0.02)
        target_dte = self.p.get("dte", 45)
        min_iv_rank = self.p.get("min_iv_rank", 35)

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

        # ─── Filter 2: Earnings calendar check ───
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
            return []

        # Find expiry date closest to target DTE (45)
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

        # Fetch option chain for that expiry
        chain = await self.s["broker"].get_chain(ticker, [target_dte_actual])
        if not chain:
            return []

        # Find Short Put matching target short delta
        short_contract = self.s["broker"].find_strike_by_delta(chain, -short_delta, "PUT")
        if not short_contract:
            logger.warning(f"{self.name}: No short PUT contract found matching delta {-short_delta}")
            return []

        short_strike = short_contract.strike
        width = spot * width_pct
        long_strike = short_strike - width

        # Find Long Put contract near strike
        long_contract = self.s["broker"].find_strike_nearest(chain, long_strike, "PUT")
        if not long_contract:
            logger.warning(f"{self.name}: No long PUT contract found near strike {long_strike}")
            return []

        short_mid = (short_contract.bid + short_contract.ask) / 2.0 or short_contract.last
        long_mid = (long_contract.bid + long_contract.ask) / 2.0 or long_contract.last
        net_credit = short_mid - long_mid

        if net_credit <= 0.05:
            await self._log_near_miss(
                ticker, spot, "credit_below_minimum", 
                net_credit, 0.05, 
                {"short_mid": short_mid, "long_mid": long_mid}
            )
            return []

        # Calculate Risk and Sizing
        max_capital = width * 100.0
        max_risk = (width - net_credit) * 100.0

        qty = await self.s["sizing"].calculate_size(
            account.id,
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            max_risk_pct=0.02,
            max_allocation_pct=0.10
        )

        if qty <= 0:
            return []

        short_leg = LegSpec(
            option_type="PUT",
            side="SHORT",
            strike=short_strike,
            expiry=expiry_date,
            quantity=qty,
            symbol=short_contract.symbol,
            mid=short_mid,
            bid=short_contract.bid,
            ask=short_contract.ask,
            iv=short_contract.iv,
            delta=short_contract.delta,
            gamma=short_contract.gamma,
            theta=short_contract.theta,
            vega=short_contract.vega
        )

        long_leg = LegSpec(
            option_type="PUT",
            side="LONG",
            strike=long_strike,
            expiry=expiry_date,
            quantity=qty,
            symbol=long_contract.symbol,
            mid=long_mid,
            bid=long_contract.bid,
            ask=long_contract.ask,
            iv=long_contract.iv,
            delta=long_contract.delta,
            gamma=long_contract.gamma,
            theta=long_contract.theta,
            vega=long_contract.vega
        )

        entry_features = {
            "iv_rank": iv_rank,
            "spot": spot,
            "net_credit": net_credit,
            "short_delta": short_contract.delta,
            "long_delta": long_contract.delta,
            "vix": float(chain.vix) if hasattr(chain, "vix") else None,
            "actual_dte": target_dte_actual
        }

        signal = Signal(
            research_strategy_id=self.params.research_strategy_id,
            strategy_category="LONG_DTE_CREDIT",
            underlying=ticker,
            legs=[short_leg, long_leg],
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            profit_target_pct=0.50,       # 50% Tastytrade exit target
            stop_loss_mult=2.0,           # Exit at 2.0x credit (1.0x loss)
            roll_at_dte=21,               # Roll/Exit strictly at 21 DTE
            entry_features=entry_features,
            notes=f"Selling 45DTE Put Credit Spread {short_strike}/{long_strike} for ${net_credit:.2f} credit"
        )
        return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        # 1. Profit Target Check: exit at 50% profit
        pt_action = await self._check_profit_target(trade, current_mtm, target_pct=0.50)
        if pt_action:
            return pt_action

        # 2. Stop Loss Check: exit at 2x credit (1.0x loss)
        sl_action = await self._check_stop_loss(trade, current_mtm, stop_mult=2.0)
        if sl_action:
            return sl_action

        # 3. Tastytrade 21-DTE time exit/roll rule
        dte_action = await self._check_dte_time_stop(trade, now, close_at_dte=21)
        if dte_action:
            logger.info(f"{self.name}: Tastytrade 21-DTE rule triggered. Rolling/Closing position.")
            return dte_action

        # Expiration Check (0 DTE)
        leg = trade.legs[0]
        expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
        if (expiry_date - now.date()).days <= 0:
            logger.info(f"{self.name}: Spread reached expiration day. Expiring position.")
            return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)
