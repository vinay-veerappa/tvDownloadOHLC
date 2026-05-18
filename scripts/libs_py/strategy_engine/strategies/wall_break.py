from datetime import datetime, date
import logging
from typing import List, Dict, Any, Optional
import pytz

from scripts.libs_py.strategy_engine.strategies.base import Strategy, Signal, LegSpec, NearMiss, ManageAction

logger = logging.getLogger(__name__)

class WallBreakStrategy(Strategy):
    """
    GEX Wall Breakout Debit Spread Strategy.
    Buys breakout debit spreads (Bull Call or Bear Put) when spot breaches dominant GEX walls.
    Dominant GEX levels are obtained from GexSnapshot:
    - Call Wall = pinStrike (if spot is below) or gammaMagnet (if spot is below).
    - Put Wall = pinStrike (if spot is above) or gammaMagnet (if spot is above).
    Filters:
    - Time of day: 10:00 AM to 3:00 PM Eastern.
    - Max VIX (e.g. 22).
    - Spot breaches or is within wall_proximity_pct of a dominant wall.
    """
    async def scan(self, now: datetime) -> List[Signal]:
        ticker = self.underlying
        entry_window = self.p.get("entry_window", ["10:00", "15:00"])
        max_vix = self.p.get("max_vix", 22)
        proximity_pct = self.p.get("wall_proximity_pct", 0.003)
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

        # Fetch Spot Price
        try:
            spot_quote = await self.s["broker"].get_stock_quote(ticker)
            spot = spot_quote["last"]
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
        try:
            vix_quote = await self.s["broker"].get_stock_quote("VIX")
            vix = vix_quote["last"]
        except Exception:
            vix = 15.0 # fallback

        if vix > max_vix:
            await self._log_near_miss(
                ticker, spot, "vix_above_threshold", 
                float(vix), float(max_vix), 
                {"vix": vix}
            )
            return []

        # ─── Filter 3: GEX Wall Extraction ───
        regime_data = await self.s["regime"].get_gex_regime(ticker)
        if not regime_data:
            logger.warning(f"{self.name}: No GEX regime data available for breakout tracking.")
            return []

        # Extract walls from snapshot
        gamma_magnet = regime_data.get("gammaMagnet") or spot
        pin_strike = regime_data.get("pinStrike") or spot

        # Identify Call Wall (nearest dominant level above spot) and Put Wall (nearest dominant level below spot)
        call_wall = max(gamma_magnet, pin_strike)
        put_wall = min(gamma_magnet, pin_strike)

        if call_wall <= spot:
            call_wall = spot * 1.01  # fallback
        if put_wall >= spot:
            put_wall = spot * 0.99  # fallback

        # Determine proximity or breach
        is_bullish_breakout = spot >= call_wall * (1.0 - proximity_pct)
        is_bearish_breakout = spot <= put_wall * (1.0 + proximity_pct)

        if not (is_bullish_breakout or is_bearish_breakout):
            # No breakout, log near miss
            dist_to_call = call_wall - spot
            dist_to_put = spot - put_wall
            min_dist = min(dist_to_call, dist_to_put)
            await self._log_near_miss(
                ticker, spot, "no_gex_wall_breakout", 
                float(spot), None, 
                {"call_wall": call_wall, "put_wall": put_wall, "distance_to_nearest": min_dist}
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

        # Buy Bull Call Spread or Bear Put Spread based on breakout direction
        if is_bullish_breakout:
            # ─── Bull Call Spread (Debit) ───
            # Long strike is at Call Wall
            long_contract = self.s["broker"].find_strike_nearest(chain, call_wall, "CALL")
            if not long_contract:
                return []

            long_strike = long_contract.strike
            short_strike = long_strike + width

            short_contract = self.s["broker"].find_strike_nearest(chain, short_strike, "CALL")
            if not short_contract:
                return []

            long_mid = (long_contract.bid + long_contract.ask) / 2.0 or long_contract.last
            short_mid = (short_contract.bid + short_contract.ask) / 2.0 or short_contract.last
            net_debit = long_mid - short_mid

            option_type = "CALL"
            legs_spec = [long_contract, short_contract]

        else:
            # ─── Bear Put Spread (Debit) ───
            # Long strike is at Put Wall
            long_contract = self.s["broker"].find_strike_nearest(chain, put_wall, "PUT")
            if not long_contract:
                return []

            long_strike = long_contract.strike
            short_strike = long_strike - width

            short_contract = self.s["broker"].find_strike_nearest(chain, short_strike, "PUT")
            if not short_contract:
                return []

            long_mid = (long_contract.bid + long_contract.ask) / 2.0 or long_contract.last
            short_mid = (short_contract.bid + short_contract.ask) / 2.0 or short_contract.last
            net_debit = long_mid - short_mid

            option_type = "PUT"
            legs_spec = [long_contract, short_contract]

        if net_debit <= 0.05 or net_debit >= width:
            await self._log_near_miss(
                ticker, spot, "invalid_debit_price", 
                net_debit, None, 
                {"long_mid": long_mid, "short_mid": short_mid}
            )
            return []

        # Risk and Capital for Debit Spread = net_debit * 100
        max_capital = net_debit * 100.0
        max_risk = net_debit * 100.0

        # Calculate position size using 10% capital allocation
        qty = await self.s["sizing"].calculate_size(
            account.id,
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            max_risk_pct=0.02,
            max_allocation_pct=0.10
        )

        if qty <= 0:
            return []

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

        entry_features = {
            "spot": spot,
            "call_wall": call_wall,
            "put_wall": put_wall,
            "is_bullish_breakout": is_bullish_breakout,
            "is_bearish_breakout": is_bearish_breakout,
            "net_debit": net_debit,
            "vix": vix
        }

        signal = Signal(
            research_strategy_id=self.params.research_strategy_id,
            strategy_category="WALL_BREAK",
            underlying=ticker,
            legs=[long_leg, short_leg],
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            profit_target_pct=0.50,       # 50% profit target
            stop_loss_mult=0.50,          # Treated as stop_pct = 50% in helper
            time_stop_minutes_before_close=30, # Flat by 3:30 PM Eastern
            entry_features=entry_features,
            notes=f"GEX Wall Breakout Debit Spread {long_strike}/{short_strike} for ${net_debit:.2f} debit"
        )
        return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        # 1. Profit Target check: exit at 50% profit of debit paid
        pt_action = await self._check_profit_target(trade, current_mtm, target_pct=0.50)
        if pt_action:
            return pt_action

        # 2. Stop Loss check: exit if value decreases by 50%
        sl_action = await self._check_stop_loss(trade, current_mtm, stop_pct=0.50)
        if sl_action:
            return sl_action

        # 3. Time Stop check (EOD flat at 3:30 PM ET)
        time_action = await self._check_time_stop(trade, now, flat_by_minutes_before_close=30)
        if time_action:
            logger.info(f"{self.name}: Intraday time stop activated. Closing GEX wall breakout spread.")
            return time_action

        # Expiration Check
        leg = trade.legs[0]
        expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
        if (expiry_date - now.date()).days <= 0:
            tz_et = pytz.timezone("America/New_York")
            now_et = now.astimezone(tz_et)
            if now_et.hour >= 16:
                logger.info(f"{self.name}: Spread reached expiration at close.")
                return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)
