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


class EarningsStrangleStrategy(Strategy):
    """
    Long Earnings Strangle Strategy (spec §8.7).
    BUYS Call + Put strangles 5 days before earnings to capture the pre-earnings IV ramp.
    Closes the day BEFORE earnings to avoid event/gap risk entirely.

    Rules:
    - Enter 5 days before earnings announcement (configurable via days_before).
    - Find call at +0.30 delta and put at -0.30 delta on the first expiry covering earnings.
    - IV percentile must be LOW (<=50): we want room for IV to expand, not contract.
    - Total debit <= max_debit AND debit <= 2% of underlying spot.
    - Exit: 30 min before close on the day BEFORE earnings (HARD RULE — never hold through).
    - Profit target: +50% of debit. Stop: -30% of debit.
    """
   
    async def scan(self, now: datetime) -> List[Signal]:
        ticker = self.underlying
        days_before = self.p.get("days_before", 5)
        target_delta = self.p.get("target_delta", 0.30)
        max_debit_abs = self.p.get("max_debit", 5.0)            # absolute cap, dollars per contract
        max_debit_pct = self.p.get("max_debit_pct_of_spot", 0.02)  # 2% of spot
        max_iv_percentile = self.p.get("max_iv_percentile", 50.0)

        prisma = self.s["prisma"]
        account = await prisma.account.find_first(where={"name": self.name})
        if not account:
            logger.error(f"{self.name}: Silo account not found.")
            return []

        # One-at-a-time policy
        active_trades = await prisma.trade.find_many(
            where={"accountId": account.id, "status": "OPEN", "ticker": ticker}
        )
        if active_trades:
            return []

        # ─── Filter 1: Earnings exactly `days_before` days away (1 to days_before window) ───
        earnings_days = await self.s["earnings"].days_to_earnings(ticker)
        if earnings_days is None or earnings_days < 1 or earnings_days > days_before:
            await self._log_near_miss(
                ticker, 0.0, "earnings_not_in_entry_window",
                float(earnings_days) if earnings_days is not None else -1.0, float(days_before),
                {"earnings_days": earnings_days, "window": [1, days_before]}
            )
            return []

        # Spot
        try:
            spot_quote = await self.s["broker"].get_stock_quote(ticker)
            spot = spot_quote["last"]
        except Exception as e:
            logger.error(f"{self.name}: Failed to fetch stock quote: {e}")
            return []

        # ─── Filter 2: Blackout ───
        if await self.s["calendar"].is_blackout_window(now):
            await self._log_near_miss(ticker, spot, "blackout_window_active", None, None, {"now": str(now)})
            return []

        # ─── Filter 3: IV percentile must be LOW (we're BUYING — want room for IV to expand) ───
        iv_data = await self.s["iv"].get_volatility_metrics(ticker)
        # NOTE: get_volatility_metrics currently returns iv_rank not iv_percentile. Using iv_rank as proxy.
        # TODO(D3): use real iv_percentile once IvService exposes it.
        iv_proxy = iv_data.get("iv_rank", 0.0)
        if iv_proxy > max_iv_percentile:
            await self._log_near_miss(
                ticker, spot, "iv_too_high_for_long_strangle",
                float(iv_proxy), float(max_iv_percentile),
                {"iv_rank_proxy": iv_proxy, "rationale": "buying IV requires LOW iv_percentile"}
            )
            return []

        # ─── Expiry: first expiry strictly AFTER earnings ───
        expiries = await self.s["broker"].get_expiries(ticker)
        if not expiries:
            return []

        earnings_date = now.date() + timedelta(days=int(earnings_days))
        best_expiry_str = None
        best_dte = 9999
        for exp_str in expiries:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            if exp_date > earnings_date:    # strictly after — expiry must survive the event
                dte = (exp_date - now.date()).days
                if dte < best_dte:
                    best_dte = dte
                    best_expiry_str = exp_str

        if not best_expiry_str:
            logger.warning(f"{self.name}: No expiry found AFTER earnings date {earnings_date}")
            return []

        expiry_date = datetime.strptime(best_expiry_str, "%Y-%m-%d").date()
        target_dte_actual = (expiry_date - now.date()).days

        chain = await self.s["broker"].get_chain(ticker, [target_dte_actual])
        if not chain:
            return []

        # Strike selection — same as before
        long_put = self.s["broker"].find_strike_by_delta(chain, -target_delta, "PUT")
        long_call = self.s["broker"].find_strike_by_delta(chain, target_delta, "CALL")
        if not long_put or not long_call:
            logger.warning(f"{self.name}: Could not find strikes near ±{target_delta} delta")
            return []

        put_mid = _safe_mid(long_put)
        call_mid = _safe_mid(long_call)
        net_debit = put_mid + call_mid

        # ─── Filter 4: debit <= absolute cap ───
        if net_debit > max_debit_abs:
            await self._log_near_miss(
                ticker, spot, "debit_above_absolute_cap",
                net_debit, max_debit_abs,
                {"put_mid": put_mid, "call_mid": call_mid}
            )
            return []

        # ─── Filter 5: debit <= 2% of spot (spec §8.7 #8) ───
        debit_pct_of_spot = net_debit / spot if spot > 0 else 999.0
        if debit_pct_of_spot > max_debit_pct:
            await self._log_near_miss(
                ticker, spot, "debit_above_pct_of_spot",
                float(debit_pct_of_spot), float(max_debit_pct),
                {"net_debit": net_debit, "spot": spot}
            )
            return []

        # Sizing: max loss = full debit
        max_risk = net_debit * 100.0
        max_capital = net_debit * 100.0

        qty = await self.s["sizing"].calculate_size(
            account.id,
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            max_risk_pct=0.02,
            max_allocation_pct=0.10,
        )
        if qty <= 0:
            return []

        put_leg = LegSpec(
            option_type="PUT", side="LONG",       # BUYING
            strike=long_put.strike, expiry=expiry_date, quantity=qty,
            symbol=long_put.symbol, mid=put_mid,
            bid=long_put.bid, ask=long_put.ask, iv=long_put.iv,
            delta=long_put.delta, gamma=long_put.gamma, theta=long_put.theta, vega=long_put.vega,
        )
        call_leg = LegSpec(
            option_type="CALL", side="LONG",      # BUYING
            strike=long_call.strike, expiry=expiry_date, quantity=qty,
            symbol=long_call.symbol, mid=call_mid,
            bid=long_call.bid, ask=long_call.ask, iv=long_call.iv,
            delta=long_call.delta, gamma=long_call.gamma, theta=long_call.theta, vega=long_call.vega,
        )

        entry_features = {
            "spot": spot,
            "days_to_earnings": earnings_days,
            "earnings_date": str(earnings_date),
            "iv_rank_at_entry": iv_proxy,
            "put_strike": long_put.strike,
            "call_strike": long_call.strike,
            "put_iv_at_entry": long_put.iv,
            "call_iv_at_entry": long_call.iv,
            "net_debit": net_debit,
            "debit_pct_of_spot": debit_pct_of_spot,
            "actual_dte": target_dte_actual,
        }

        signal = Signal(
            research_strategy_id=self.params.research_strategy_id,
            strategy_category="EARNINGS_STRANGLE",
            underlying=ticker,
            legs=[put_leg, call_leg],
            max_risk_per_contract=max_risk,
            max_capital_per_contract=max_capital,
            profit_target_pct=self._exit_rules["profit_target_pct"],   # default 0.50 = +50% of debit
            stop_loss_mult=self._exit_rules["stop_loss_mult"],          # unused for DEBIT (manage uses stop_loss_pct)
            entry_features=entry_features,
            notes=f"BUYING pre-earnings strangle {long_put.strike}P/{long_call.strike}C for ${net_debit:.2f} debit",
        )
        return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        """
        Exit priority:
        1. HARD RULE: day before earnings + 30 min before close → FORCE CLOSE (never hold through event).
        2. Profit target: +50% of debit paid (long position appreciated).
        3. Stop loss: -30% of debit (theta + IV stagnation eroding position).
        4. Expiration fallback.
        """
        ex = self._exit_rules
        ticker = trade.ticker.upper()

        # ─── 1. HARD pre-earnings exit ───
        earnings_days = await self.s["earnings"].days_to_earnings(ticker)
        if earnings_days is not None and earnings_days <= 1:
            tz_et = pytz.timezone("America/New_York")
            now_et = now.astimezone(tz_et)
            # Within 30 minutes of market close on the day BEFORE earnings
            minutes_to_close = (16 - now_et.hour) * 60 - now_et.minute
            if earnings_days == 1 and minutes_to_close <= 30:
                logger.info(f"{self.name}: Day before earnings, <=30 min to close. FORCE CLOSE to avoid event risk.")
                return ManageAction(close=True, reason="PRE_EARNINGS")
            # If earnings_days is 0 (rare — earnings today), close immediately at any time
            if earnings_days <= 0:
                logger.warning(f"{self.name}: Earnings already today/passed and we're still in — closing now.")
                return ManageAction(close=True, reason="PRE_EARNINGS_LATE")

        # ─── 2. Profit target (use DEBIT helper) ───
        pt_action = await self._check_profit_target(trade, current_mtm, target_pct=ex["profit_target_pct"])
        if pt_action:
            return pt_action

        # ─── 3. Stop loss (DEBIT — uses stop_loss_pct, default 0.30 per spec §8.7) ───
        stop_pct = float(self.p.get("stop_loss_pct", 0.30))
        sl_action = await self._check_stop_loss_debit(trade, current_mtm, stop_pct=stop_pct)
        if sl_action:
            return sl_action

        # ─── 4. Expiration ───
        leg = trade.legs[0]
        expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
        if (expiry_date - now.date()).days <= 0:
            logger.info(f"{self.name}: Strangle reached expiration. Closing.")
            return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)