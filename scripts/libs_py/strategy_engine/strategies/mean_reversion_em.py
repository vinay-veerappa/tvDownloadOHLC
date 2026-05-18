from datetime import datetime, date
import logging
from typing import List, Dict, Any, Optional
import pytz

from scripts.libs_py.strategy_engine.strategies.base import Strategy, Signal, LegSpec, NearMiss, ManageAction

logger = logging.getLogger(__name__)

class MeanReversionEmStrategy(Strategy):
    """
    Expected Move Mean Reversion Strategy.
    Fades 1-Standard Deviation Expected Move (EM) boundary touches by writing credit spreads.
    Filters:
    - Time of day: 10:30 AM to 2:30 PM Eastern.
    - Max VIX threshold (e.g. 20).
    - Positive GEX regime (if required).
    - Spot touches or breaches daily 1SD upper/lower EM boundary.
    """
    async def scan(self, now: datetime) -> List[Signal]:
        ticker = self.underlying
        entry_window = self.p.get("entry_window", ["10:30", "14:30"])
        max_vix = self.p.get("max_vix", 20)
        require_positive_gamma = self.p.get("require_positive_gamma", True)
        width = 5.0

        # Convert now to Eastern time
        tz_et = pytz.timezone("America/New_York")
        now_et = now.astimezone(tz_et)

        # Check time window
        start_h, start_m = map(int, entry_window[0].split(":"))
        end_h, end_m = map(int, entry_window[1].split(":"))
        entry_start = now_et.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        entry_end = now_et.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

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

        # Fetch Spot Price and Open Price
        try:
            spot_quote = await self.s["broker"].get_stock_quote(ticker)
            spot = spot_quote["last"]
            session_open = spot_quote["open"]
        except Exception as e:
            logger.error(f"{self.name}: Failed to fetch stock quote: {e}")
            return []

        if not (entry_start <= now_et <= entry_end):
            return []

        # ─── Filter 1: Blackout economic calendar ───
        if await self.s["calendar"].is_blackout_window(now):
            await self._log_near_miss(ticker, spot, "blackout_window_active", None, None, {"now": str(now)})
            return []

        # ─── Filter 2: VIX Check ───
        # Fetch current VIX using spot quote of VIX
        try:
            vix_quote = await self.s["broker"].get_stock_quote("VIX")
            vix = vix_quote["last"]
        except Exception:
            vix = 15.0 # default fallback

        if vix > max_vix:
            await self._log_near_miss(
                ticker, spot, "vix_above_threshold", 
                float(vix), float(max_vix), 
                {"vix": vix}
            )
            return []

        # ─── Filter 3: GEX Regime check ───
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

        # ─── Filter 4: Expected Move Boundary Touch ───
        em_data = await self.s["em"].get_expected_move_bands(ticker, spot, session_open)
        if not em_data:
            logger.warning(f"{self.name}: Failed to calculate Expected Move bands for {ticker}")
            return []

        upper_1sd = em_data["upper_1sd"]
        lower_1sd = em_data["lower_1sd"]
        em_value = em_data["em_value"]

        # Check for touches
        is_upside_touch = spot >= upper_1sd
        is_downside_touch = spot <= lower_1sd

        if not (is_upside_touch or is_downside_touch):
            # No touch, log near miss with how far away it is
            dist_to_upper = upper_1sd - spot
            dist_to_lower = spot - lower_1sd
            min_dist = min(dist_to_upper, dist_to_lower)
            await self._log_near_miss(
                ticker, spot, "no_em_boundary_touch", 
                float(spot), None, 
                {"upper_1sd": upper_1sd, "lower_1sd": lower_1sd, "distance_to_nearest": min_dist}
            )
            return []

        # ─── 0DTE Expiry selection ───
        expiries = await self.s["broker"].get_expiries(ticker)
        today_str = now_et.strftime("%Y-%m-%d")
        if today_str not in expiries:
            return []

        chain = await self.s["broker"].get_chain(ticker, [0])
        if not chain:
            return []

        # Construct Call spread (fading rally) or Put spread (fading selloff)
        if is_downside_touch:
            # ─── Bullish Fade: Sell Put Spread ───
            # Short Put closest to lower_1sd
            short_contract = self.s["broker"].find_strike_nearest(chain, lower_1sd, "PUT")
            if not short_contract:
                return []

            short_strike = short_contract.strike
            long_strike = short_strike - width

            long_contract = self.s["broker"].find_strike_nearest(chain, long_strike, "PUT")
            if not long_contract:
                return []

            short_mid = (short_contract.bid + short_contract.ask) / 2.0 or short_contract.last
            long_mid = (long_contract.bid + long_contract.ask) / 2.0 or long_contract.last
            net_credit = short_mid - long_mid

            option_type = "PUT"
            legs_spec = [short_contract, long_contract]

        else:
            # ─── Bearish Fade: Sell Call Spread ───
            # Short Call closest to upper_1sd
            short_contract = self.s["broker"].find_strike_nearest(chain, upper_1sd, "CALL")
            if not short_contract:
                return []

            short_strike = short_contract.strike
            long_strike = short_strike + width

            long_contract = self.s["broker"].find_strike_nearest(chain, long_strike, "CALL")
            if not long_contract:
                return []

            short_mid = (short_contract.bid + short_contract.ask) / 2.0 or short_contract.last
            long_mid = (long_contract.bid + long_contract.ask) / 2.0 or long_contract.last
            net_credit = short_mid - long_mid

            option_type = "CALL"
            legs_spec = [short_contract, long_contract]

        if net_credit <= 0.05:
            await self._log_near_miss(
                ticker, spot, "credit_below_minimum", 
                net_credit, 0.05, 
                {"short_mid": short_mid, "long_mid": long_mid}
            )
            return []

        # Risk and Capital calculations
        max_capital = width * 100.0
        max_risk = (width - net_credit) * 100.0

        # Calculate position size
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
            option_type=option_type,
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
            option_type=option_type,
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

        direction = "CREDIT"
        trade_direction = "CREDIT"

        entry_features = {
            "spot": spot,
            "session_open": session_open,
            "upper_1sd": upper_1sd,
            "lower_1sd": lower_1sd,
            "em_value": em_value,
            "is_upside_touch": is_upside_touch,
            "is_downside_touch": is_downside_touch,
            "net_credit": net_credit,
            "vix": vix
        }

        signal = Signal(
            research_strategy_id=self.params.research_strategy_id,
            strategy_category="MEAN_REVERSION_EM",
            underlying=ticker,
            legs=[short_leg, long_leg],
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            profit_target_pct=0.50,       # 50% target
            stop_loss_mult=3.0,           # Exit at 3x credit
            time_stop_minutes_before_close=30, # Flat by 3:30 PM Eastern
            entry_features=entry_features,
            notes=f"Mean Reversion EM touch spread {short_strike}/{long_strike} for ${net_credit:.2f} credit"
        )
        return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        # 1. Profit Target: exit at 50% profit
        pt_action = await self._check_profit_target(trade, current_mtm, target_pct=0.50)
        if pt_action:
            return pt_action

        # 2. Stop Loss: exit at 3x credit (loss of 2x credit)
        sl_action = await self._check_stop_loss(trade, current_mtm, stop_mult=3.0)
        if sl_action:
            return sl_action

        # 3. Time Stop: close at 3:30 PM Eastern
        time_action = await self._check_time_stop(trade, now, flat_by_minutes_before_close=30)
        if time_action:
            logger.info(f"{self.name}: Intraday time stop activated. Closing mean reversion spread.")
            return time_action

        # Expiration Check
        leg = trade.legs[0]
        expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
        if (expiry_date - now.date()).days <= 0:
            tz_et = pytz.timezone("America/New_York")
            now_et = now.astimezone(tz_et)
            if now_et.hour >= 16:
                logger.info(f"{self.name}: 0DTE trade expired at close.")
                return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)
