from datetime import datetime, date
import logging
from typing import List, Dict, Any, Optional
import pytz

from scripts.libs_py.strategy_engine.strategies.base import Strategy, Signal, LegSpec, NearMiss, ManageAction

logger = logging.getLogger(__name__)

class ZeroDtePcsStrategy(Strategy):
    """
    Intraday 0DTE Put Credit Spreads (PCS).
    Sells a Put spread (Short Put + Long Put) on SPY/SPX expiring same day.
    Filters:
    - Time of day: 9:45 AM to 12:00 PM Eastern.
    - Blackout economic calendar.
    - Positive GEX regime (if required).
    - ICT Bullish bias / FVGs / Liquidity sweeps (if required).
    """
    async def scan(self, now: datetime) -> List[Signal]:
        ticker = self.underlying
        short_delta = self.p.get("short_delta", 0.10)
        width = self.p.get("width", 5.0)
        require_positive_gamma = self.p.get("require_positive_gamma", True)
        require_ict = self.p.get("require_ict", False)

        # ─── Time window check ───
        # Convert now to Eastern time
        tz_et = pytz.timezone("America/New_York")
        now_et = now.astimezone(tz_et)
        
        # We only enter between 9:45 AM and 12:00 PM EST
        entry_start = now_et.replace(hour=9, minute=45, second=0, microsecond=0)
        entry_end = now_et.replace(hour=12, minute=0, second=0, microsecond=0)
        
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

        if not (entry_start <= now_et <= entry_end):
            # Not in entry time window, skip without logging near miss
            return []

        # ─── Filter 1: Blackout economic calendar ───
        if await self.s["calendar"].is_blackout_window(now):
            await self._log_near_miss(ticker, spot, "blackout_window_active", None, None, {"now": str(now)})
            return []

        # ─── Filter 2: GEX Regime check ───
        if require_positive_gamma:
            regime_data = await self.s["regime"].get_gex_regime(ticker)
            if not regime_data or regime_data.get("gexRegime") != "POSITIVE":
                gex_label = regime_data.get("gexRegime", "UNKNOWN") if regime_data else "NONE"
                await self._log_near_miss(
                    ticker, spot, "regime_not_positive", 
                    None, None, 
                    {"gexRegime": gex_label}
                )
                return []

        # ─── Filter 3: ICT Bullish Bias check ───
        if require_ict:
            ict_data = await self.s["ict"].get_market_structure(ticker)
            # ict_data contains bias: "BULLISH", "BEARISH", "NEUTRAL"
            bias = ict_data.get("bias", "NEUTRAL").upper()
            if bias != "BULLISH":
                await self._log_near_miss(
                    ticker, spot, "ict_bias_not_bullish", 
                    None, None, 
                    {"ict_bias": bias, "ict_fvg": ict_data.get("fvg_count", 0)}
                )
                return []

        # ─── 0DTE Expiry ───
        expiries = await self.s["broker"].get_expiries(ticker)
        today_str = now_et.strftime("%Y-%m-%d")
        if today_str not in expiries:
            logger.debug(f"{self.name}: Today {today_str} is not a valid expiry in chain for {ticker}")
            return []

        # Fetch option chain for 0 DTE (0 days remaining)
        chain = await self.s["broker"].get_chain(ticker, [0])
        if not chain:
            return []

        # Find Short Put matching target short delta
        short_contract = self.s["broker"].find_strike_by_delta(chain, -short_delta, "PUT")
        if not short_contract:
            logger.warning(f"{self.name}: No short PUT contract found matching delta {-short_delta}")
            return []

        short_strike = short_contract.strike
        long_strike = short_strike - width

        # Find Long Put contract at the correct strike
        long_contract = self.s["broker"].find_strike_nearest(chain, long_strike, "PUT")
        if not long_contract:
            logger.warning(f"{self.name}: No long PUT contract found near strike {long_strike}")
            return []

        short_mid = (short_contract.bid + short_contract.ask) / 2.0 or short_contract.last
        long_mid = (long_contract.bid + long_contract.ask) / 2.0 or long_contract.last
        net_credit = short_mid - long_mid

        if net_credit <= 0.05:
            # Credit too low to enter
            await self._log_near_miss(
                ticker, spot, "credit_below_minimum", 
                net_credit, 0.05, 
                {"short_mid": short_mid, "long_mid": long_mid}
            )
            return []

        # Spreads: Capital required is width * 100. Max risk is (width - net_credit) * 100
        max_capital = width * 100.0
        max_risk = (width - net_credit) * 100.0

        # Calculate position size using 10% max allocation per trade, 2% risk limit
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
            expiry=now.date(),
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
            expiry=now.date(),
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
            "spot": spot,
            "net_credit": net_credit,
            "short_delta": short_contract.delta,
            "long_delta": long_contract.delta,
            "vix": float(chain.vix) if hasattr(chain, "vix") else None,
            "require_positive_gamma": require_positive_gamma,
            "require_ict": require_ict
        }

        signal = Signal(
            research_strategy_id=self.params.research_strategy_id,
            strategy_category="ZERO_DTE_PCS",
            underlying=ticker,
            legs=[short_leg, long_leg],
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            profit_target_pct=0.60,       # 60% profit target standard for intraday credit
            stop_loss_mult=3.0,           # Exit at 3x credit received (loss of 2x credit)
            time_stop_minutes_before_close=30, # Flat by 3:30 PM Eastern
            entry_features=entry_features,
            notes=f"Selling 0DTE Put Credit Spread {short_strike}/{long_strike} for ${net_credit:.2f} credit"
        )
        return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        # ─── Profit Target check ───
        # Standard PCS profit target (default 60% of credit)
        pt_action = await self._check_profit_target(trade, current_mtm, target_pct=0.60)
        if pt_action:
            return pt_action

        # ─── Stop Loss check ───
        # Exit if aggregate cost to close is >= 3x credit received
        sl_action = await self._check_stop_loss(trade, current_mtm, stop_mult=3.0)
        if sl_action:
            return sl_action

        # ─── Time Stop check (EOD flat at 3:30 PM ET) ───
        time_action = await self._check_time_stop(trade, now, flat_by_minutes_before_close=30)
        if time_action:
            logger.info(f"{self.name}: Intraday time stop activated. Closing position before market close.")
            return time_action

        # Expiration Check (At or past 4:00 PM ET)
        leg = trade.legs[0]
        expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
        if (expiry_date - now.date()).days <= 0:
            tz_et = pytz.timezone("America/New_York")
            now_et = now.astimezone(tz_et)
            if now_et.hour >= 16:
                # EOD closing/expiration roll
                logger.info(f"{self.name}: 0DTE trade reached market close. Expiring position.")
                return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)
