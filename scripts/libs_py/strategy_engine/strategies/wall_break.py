from datetime import datetime, date
import logging
from typing import List, Dict, Any, Optional
import pytz

from scripts.libs_py.strategy_engine.strategies.base import Strategy, Signal, LegSpec, NearMiss, ManageAction

logger = logging.getLogger(__name__)

def _safe_mid(contract) -> float:
    """Return reliable mid-price; fall back to last if only one side is quoted."""
    if contract.bid and contract.bid > 0 and contract.ask and contract.ask > 0:
        return (contract.bid + contract.ask) / 2.0
    return contract.last or contract.bid or contract.ask or 0.0


class WallBreakStrategy(Strategy):
    """
    GEX Wall Breakout Debit Spread Strategy.
    Buys breakout debit spreads (Bull Call or Bear Put) when spot breaches dominant GEX walls.
    Dominant GEX levels come from RegimeService.get_nearest_walls() which reads
    MacroSnapshot.dominantNodes — real top-strike GEX concentrations (D9).
    Filters:
    - Time of day: 10:00 AM to 3:00 PM Eastern.
    - Max VIX (e.g. 22) — fetched via $VIX.X Schwab ticker (D8).
    - Spot breaches or is within wall_proximity_pct of a dominant wall.
    Note: DEX confirmation + volume filter (C13) deferred to v1.1.
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

        # ─── Filter 2: VIX Check — use $VIX.X Schwab ticker (D8) ───
        try:
            vix_quote = await self.s["broker"].get_stock_quote("$VIX.X")
            vix = vix_quote["last"]
        except Exception:
            # Fallback: read VIX from the latest MacroSnapshot.vix field if available
            try:
                regime = await self.s["regime"].get_current_regime(ticker)
                vix = getattr(regime, "vix", None) or 15.0
            except Exception:
                vix = 15.0  # hard fallback — log so we know it's firing
            logger.warning(f"{self.name}: VIX fetch failed; using fallback {vix}")

        if vix > max_vix:
            await self._log_near_miss(
                ticker, spot, "vix_above_threshold",
                float(vix), float(max_vix),
                {"vix": vix}
            )
            return []

        # ─── Filter 3: Real GEX Wall Extraction via RegimeService (D9) ───
        # get_nearest_walls() reads MacroSnapshot.dominantNodes — actual GEX concentration strikes.
        # This replaces the synthetic gammaMagnet/pinStrike proxy that fired every day.
        call_walls = await self.s["regime"].get_nearest_walls(ticker, above_spot=True, n=3)
        put_walls  = await self.s["regime"].get_nearest_walls(ticker, above_spot=False, n=3)

        if not call_walls and not put_walls:
            await self._log_near_miss(
                ticker, spot, "no_gex_walls_available",
                None, None,
                {"reason": "MacroSnapshot has no dominantNodes data"}
            )
            return []

        # Primary wall = closest level in each direction
        call_wall = call_walls[0] if call_walls else None
        put_wall  = put_walls[0]  if put_walls  else None

        is_bullish_breakout = (
            call_wall is not None
            and spot >= call_wall * (1.0 - proximity_pct)
        )
        is_bearish_breakout = (
            put_wall is not None
            and spot <= put_wall * (1.0 + proximity_pct)
        )

        if not (is_bullish_breakout or is_bearish_breakout):
            dist_to_call = (call_wall - spot) if call_wall else None
            dist_to_put  = (spot - put_wall)  if put_wall  else None
            await self._log_near_miss(
                ticker, spot, "no_gex_wall_breakout",
                float(spot), None,
                {
                    "call_wall": call_wall,
                    "put_wall": put_wall,
                    "dist_to_call": dist_to_call,
                    "dist_to_put": dist_to_put
                }
            )
            return []

        # ─── DEX Confirmation (C13) ───
        try:
            em_bands = await self.s["em"].get_today_em(ticker)
        except Exception as e:
            logger.error(f"{self.name}: ExpectedMoveService error: {e}")
            em_bands = None

        if em_bands:
            upper_1sd = em_bands["upper_1sd"]
            lower_1sd = em_bands["lower_1sd"]
            if is_bullish_breakout and spot > upper_1sd:
                await self._log_near_miss(
                    ticker, spot, "dex_overextended_bullish",
                    float(spot), float(upper_1sd),
                    {"upper_1sd": upper_1sd}
                )
                return []
            elif is_bearish_breakout and spot < lower_1sd:
                await self._log_near_miss(
                    ticker, spot, "dex_overextended_bearish",
                    float(spot), float(lower_1sd),
                    {"lower_1sd": lower_1sd}
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

            # Volume Filter (C13)
            calls = chain.calls
            avg_call_volume = sum(c.volume for c in calls) / len(calls) if calls else 0
            volume_multiple = self.p.get("volume_multiple", 1.5)
            if avg_call_volume > 0 and long_contract.volume < volume_multiple * avg_call_volume:
                await self._log_near_miss(
                    ticker, spot, "volume_below_threshold",
                    float(long_contract.volume), float(volume_multiple * avg_call_volume),
                    {"contract_volume": long_contract.volume, "avg_call_volume": avg_call_volume, "volume_multiple": volume_multiple}
                )
                return []

            long_strike = long_contract.strike
            short_strike = long_strike + width

            short_contract = self.s["broker"].find_strike_nearest(chain, short_strike, "CALL")
            if not short_contract:
                return []

            long_mid = _safe_mid(long_contract)   # D7
            short_mid = _safe_mid(short_contract)  # D7
            net_debit = long_mid - short_mid

            option_type = "CALL"
            legs_spec = [long_contract, short_contract]

        else:
            # ─── Bear Put Spread (Debit) ───
            # Long strike is at Put Wall
            long_contract = self.s["broker"].find_strike_nearest(chain, put_wall, "PUT")
            if not long_contract:
                return []

            # Volume Filter (C13)
            puts = chain.puts
            avg_put_volume = sum(p.volume for p in puts) / len(puts) if puts else 0
            volume_multiple = self.p.get("volume_multiple", 1.5)
            if avg_put_volume > 0 and long_contract.volume < volume_multiple * avg_put_volume:
                await self._log_near_miss(
                    ticker, spot, "volume_below_threshold",
                    float(long_contract.volume), float(volume_multiple * avg_put_volume),
                    {"contract_volume": long_contract.volume, "avg_put_volume": avg_put_volume, "volume_multiple": volume_multiple}
                )
                return []

            long_strike = long_contract.strike
            short_strike = long_strike - width

            short_contract = self.s["broker"].find_strike_nearest(chain, short_strike, "PUT")
            if not short_contract:
                return []

            long_mid = _safe_mid(long_contract)   # D7
            short_mid = _safe_mid(short_contract)  # D7
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
            "all_call_walls": call_walls,
            "all_put_walls": put_walls,
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
            profit_target_pct=self._exit_rules["profit_target_pct"],            # M7
            stop_loss_mult=self._exit_rules["stop_loss_mult"],                   # M7 (interpreted as stop_pct for DEBIT)
            time_stop_minutes_before_close=self._exit_rules["flat_before_close_minutes"],  # M7
            entry_features=entry_features,
            notes=f"GEX Wall Breakout Debit Spread {long_strike}/{short_strike} for ${net_debit:.2f} debit"
        )
        return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        ex = self._exit_rules  # M7
        # 1. Profit Target check
        pt_action = await self._check_profit_target(trade, current_mtm, target_pct=ex["profit_target_pct"])
        if pt_action:
            return pt_action

        # 2. Stop Loss: for DEBIT spread stop_pct = stop_loss_mult interpreted as fraction
        sl_action = await self._check_stop_loss_debit(trade, current_mtm, stop_pct=ex["stop_loss_pct"])
        if sl_action:
            return sl_action

        # 3. Time Stop (EOD flat)
        time_action = await self._check_time_stop(trade, now, flat_by_minutes_before_close=ex["flat_before_close_minutes"])
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
