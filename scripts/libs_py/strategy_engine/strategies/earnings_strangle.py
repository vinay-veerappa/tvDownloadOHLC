from datetime import datetime, date, timedelta
import logging
from typing import List, Dict, Any, Optional
import pytz

from scripts.libs_py.strategy_engine.strategies.base import Strategy, Signal, LegSpec, NearMiss, ManageAction

logger = logging.getLogger(__name__)


def _safe_mid(contract) -> float:
    """Reliable mid-price; fall back to last when only one side is quoted (D7)."""
    if contract.bid and contract.bid > 0 and contract.ask and contract.ask > 0:
        return (contract.bid + contract.ask) / 2.0
    return contract.last or contract.bid or contract.ask or 0.0


class EarningsStrangleStrategy(Strategy):
    """
    Systematic Earnings Short Strangle Strategy.
    Sells Call and Put options 1 to 5 days before an earnings announcement to capture the post-earnings IV crush.
    Tastytrade Rules:
    - Sell ~0.10 Delta Put and Call.
    - Expiry: First weekly expiration covering the earnings date.
    - IV Rank >= 30.
    - Management: Close immediately the morning after the earnings announcement (IV crush capture) or at 30% profit.
    """
    async def scan(self, now: datetime) -> List[Signal]:
        ticker = self.underlying
        min_iv_rank = self.p.get("min_iv_rank", 30)
        short_delta = self.p.get("short_delta", self.p.get("target_delta", 0.10))

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

        # ─── Filter 1: Earnings Date Check (Must be within 1 to 5 days) ───
        earnings_days = await self.s["earnings"].days_to_earnings(ticker)
        if earnings_days is None or earnings_days < 1 or earnings_days > 5:
            await self._log_near_miss(
                ticker, 0.0, "earnings_not_in_range", 
                float(earnings_days) if earnings_days is not None else -1.0, 5.0, 
                {"earnings_days": earnings_days}
            )
            return []

        # Fetch Spot Price
        try:
            spot_quote = await self.s["broker"].get_stock_quote(ticker)
            spot = spot_quote["last"]
        except Exception as e:
            logger.error(f"{self.name}: Failed to fetch stock quote: {e}")
            return []

        # ─── Filter 2: Blackout economic calendar ───
        if await self.s["calendar"].is_blackout_window(now):
            await self._log_near_miss(ticker, spot, "blackout_window_active", None, None, {"now": str(now)})
            return []

        # ─── Filter 3: IV Rank Check ───
        iv_data = await self.s["iv"].get_volatility_metrics(ticker)
        iv_rank = iv_data.get("iv_rank", 0.0)
        if iv_rank < min_iv_rank:
            await self._log_near_miss(
                ticker, spot, "iv_rank_below_threshold", 
                float(iv_rank), float(min_iv_rank), 
                {"iv_rank": iv_rank}
            )
            return []

        # ─── Expiry Selection (First expiry strictly >= earnings date) ───
        expiries = await self.s["broker"].get_expiries(ticker)
        if not expiries:
            return []

        earnings_date = now.date() + timedelta(days=int(earnings_days))
        best_expiry_str = None
        best_dte = 9999

        for exp_str in expiries:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            if exp_date >= earnings_date:
                dte = (exp_date - now.date()).days
                if dte < best_dte:
                    best_dte = dte
                    best_expiry_str = exp_str

        if not best_expiry_str:
            logger.warning(f"{self.name}: No suitable expiry found covering earnings date {earnings_date}")
            return []

        expiry_date = datetime.strptime(best_expiry_str, "%Y-%m-%d").date()
        target_dte_actual = (expiry_date - now.date()).days

        chain = await self.s["broker"].get_chain(ticker, [target_dte_actual])
        if not chain:
            return []

        # Find Short Put (matching -0.10 delta)
        short_put = self.s["broker"].find_strike_by_delta(chain, -short_delta, "PUT")
        if not short_put:
            logger.warning(f"{self.name}: Short PUT contract not found matching delta {-short_delta}")
            return []

        # Find Short Call (matching 0.10 delta)
        short_call = self.s["broker"].find_strike_by_delta(chain, short_delta, "CALL")
        if not short_call:
            logger.warning(f"{self.name}: Short CALL contract not found matching delta {short_delta}")
            return []

        # ─── D7: use _safe_mid ───
        put_mid = _safe_mid(short_put)
        call_mid = _safe_mid(short_call)
        net_credit = put_mid + call_mid

        if net_credit <= 0.10:
            await self._log_near_miss(
                ticker, spot, "credit_below_minimum",
                net_credit, 0.10,
                {"put_mid": put_mid, "call_mid": call_mid}
            )
            return []

        # C14: Reject if net_credit < max_debit_pct * spot (strangle should generate meaningful premium)
        # Spec §9.3: net credit must exceed 2% of the underlying spot price
        max_debit_pct = self.p.get("max_debit_pct", 0.02)
        min_credit_required = spot * max_debit_pct
        if net_credit < min_credit_required:
            await self._log_near_miss(
                ticker, spot, "credit_below_pct_threshold",
                net_credit, min_credit_required,
                {"net_credit": net_credit, "min_credit_required": min_credit_required, "max_debit_pct": max_debit_pct}
            )
            return []

        # Strangle Margin/Capital Sizing:
        # Standard margin for short strangle is roughly 10% of underlying strikes.
        max_capital = (short_put.strike + short_call.strike) * 100.0 * 0.10
        max_risk = spot * 100.0 * 0.20 # assume 20% move risk cap

        qty = await self.s["sizing"].calculate_size(
            account.id,
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            max_risk_pct=0.02,
            max_allocation_pct=0.10
        )

        if qty <= 0:
            return []

        put_leg = LegSpec(
            option_type="PUT",
            side="SHORT",
            strike=short_put.strike,
            expiry=expiry_date,
            quantity=qty,
            symbol=short_put.symbol,
            mid=put_mid,
            bid=short_put.bid,
            ask=short_put.ask,
            iv=short_put.iv,
            delta=short_put.delta,
            gamma=short_put.gamma,
            theta=short_put.theta,
            vega=short_put.vega
        )

        call_leg = LegSpec(
            option_type="CALL",
            side="SHORT",
            strike=short_call.strike,
            expiry=expiry_date,
            quantity=qty,
            symbol=short_call.symbol,
            mid=call_mid,
            bid=short_call.bid,
            ask=short_call.ask,
            iv=short_call.iv,
            delta=short_call.delta,
            gamma=short_call.gamma,
            theta=short_call.theta,
            vega=short_call.vega
        )

        entry_features = {
            "spot": spot,
            "days_to_earnings": earnings_days,
            "earnings_date": str(earnings_date),
            "iv_rank": iv_rank,
            "put_strike": short_put.strike,
            "call_strike": short_call.strike,
            "net_credit": net_credit,
            "actual_dte": target_dte_actual
        }

        signal = Signal(
            research_strategy_id=self.params.research_strategy_id,
            strategy_category="EARNINGS_STRANGLE",
            underlying=ticker,
            legs=[put_leg, call_leg],
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            profit_target_pct=self._exit_rules["profit_target_pct"],  # C15+M7: spec says 50%
            stop_loss_mult=self._exit_rules["stop_loss_mult"],         # M7
            entry_features=entry_features,
            notes=f"Selling pre-earnings strangle {short_put.strike}/{short_call.strike} for ${net_credit:.2f} credit"
        )
        return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        ex = self._exit_rules  # M7
        ticker = trade.ticker.upper()

        # 1. Profit Target check (C15: 50% per spec)
        pt_action = await self._check_profit_target(trade, current_mtm, target_pct=ex["profit_target_pct"])
        if pt_action:
            return pt_action

        # 2. Stop Loss check
        sl_action = await self._check_stop_loss(trade, current_mtm, stop_mult=ex["stop_loss_mult"])
        if sl_action:
            return sl_action

        # 3. Post-Earnings crush check:
        # Check if the earnings event has passed. If so, close immediately to capture the crush.
        earnings_days = await self.s["earnings"].days_to_earnings(ticker)
        if earnings_days is not None and earnings_days <= 0:
            tz_et = pytz.timezone("America/New_York")
            now_et = now.astimezone(tz_et)
            # Ensure market is open (post 9:30 AM ET)
            if now_et.hour > 9 or (now_et.hour == 9 and now_et.minute >= 30):
                logger.info(f"{self.name}: Earnings announcement has passed. Closing position to lock in IV crush.")
                return ManageAction(close=True, reason="EARNINGS_CRUSH_CAPTURE")

        # Expiration check
        leg = trade.legs[0]
        expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
        if (expiry_date - now.date()).days <= 0:
            logger.info(f"{self.name}: Strangle reached expiration date. Flatting position.")
            return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)
