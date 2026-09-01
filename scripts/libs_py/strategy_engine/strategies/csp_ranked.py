"""
CSP Ranked & Bull Put Spread Strategy for Options Strategy Engine
Implements Ben (@PatternProfits)'s quantitative 100-pt methodology with multi-quarter trajectory review.
Supports two synchronized execution silos:
1. BEN_CSP: 100% Cash-Secured Put (collateral = strike * 100).
2. BEN_SPREAD: Defined-Risk Bull Put Spread (short strike at Tier-1, long strike 5-10 pts OTM).
"""

from datetime import datetime, date
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from scripts.libs_py.strategy_engine.strategies.base import Strategy, Signal, LegSpec, NearMiss, ManageAction
from scripts.csp_ranking.live_scanner import scan_live_market
from scripts.csp_ranking.scoring_engine import ScoredCandidate, rank_csp_candidates
from scripts.csp_ranking.trajectory_analyzer import run_autonomous_deep_review
from scripts.csp_ranking.finviz_client import FinvizClient
from scripts.csp_ranking.technicals import TechnicalAnalyzer
from scripts.utils.universe_manager import get_universe

logger = logging.getLogger(__name__)


def _safe_mid(contract) -> float:
    """Calculates safe mid-price or falls back to last."""
    if hasattr(contract, "bid") and contract.bid and contract.bid > 0 and hasattr(contract, "ask") and contract.ask and contract.ask > 0:
        return (contract.bid + contract.ask) / 2.0
    return getattr(contract, "last", 0.0) or getattr(contract, "bid", 0.0) or getattr(contract, "ask", 0.0) or 0.0


class CspRankedStrategy(Strategy):
    """
    Ben (@PatternProfits) Quantitative CSP & Spread Strategy.
    Evaluates top Tier-1 candidates and executes in either CSP or SPREAD silo.
    """

    async def scan(self, now: datetime) -> List[Signal]:
        ticker = self.underlying
        mode = self.p.get("mode", "CSP") # "CSP" or "SPREAD"
        spread_width = float(self.p.get("spread_width", 10.0))
        min_score = float(self.p.get("min_score", 90.0)) # Tier 1 Green Light floor

        prisma = self.s["prisma"]

        # 1. Look up silo Account
        account = await prisma.account.find_first(where={"name": self.name})
        if not account:
            logger.error(f"{self.name}: Silo account not found.")
            return []

        # 2. Check if we already have an open trade for this ticker in this silo
        active_trades = await prisma.trade.find_many(
            where={
                "accountId": account.id,
                "status": "OPEN",
                "ticker": ticker
            },
            include={"legs": True}
        )
        if active_trades:
            return [] # Already active in trade

        # 3. Pull market quote
        try:
            spot_quote = await self.s["broker"].get_stock_quote(ticker)
            spot = spot_quote["last"]
        except Exception as e:
            logger.warning(f"{self.name}: Failed to fetch spot quote for {ticker}: {e}")
            return []

        # 4. Filter: Blackout Calendar check
        if await self.s["calendar"].is_blackout_window(now):
            await self._log_near_miss(ticker, spot, "blackout_window_active", None, None, {"now": str(now)})
            return []

        # 5. Filter: Earnings before expiration
        target_dte = self.p.get("dte", 30)
        earnings_days = await self.s["earnings"].days_to_earnings(ticker)
        if earnings_days is not None and earnings_days <= target_dte:
            await self._log_near_miss(
                ticker, spot, "earnings_within_dte", 
                float(earnings_days), float(target_dte), 
                {"earnings_days": earnings_days}
            )
            return []

        # 6. Fetch option chain for target expiration
        expiries = await self.s["broker"].get_expiries(ticker)
        if not expiries:
            return []

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

        chain = await self.s["broker"].get_chain(ticker, [target_dte_actual])
        if not chain:
            return []

        # Short delta target: -0.20 to -0.25 (OTM cushion)
        short_delta_target = float(self.p.get("short_delta", 0.20))
        short_contract = self.s["broker"].find_strike_by_delta(chain, -short_delta_target, "PUT")
        if not short_contract:
            return []

        short_strike = short_contract.strike
        short_mid = _safe_mid(short_contract)
        if short_mid <= 0.20:
            return []

        # 7. Generate Signal based on Mode (CSP vs SPREAD)
        if mode == "CSP":
            # ─── SILO 1: Cash-Secured Put (100% Collateral) ───
            max_capital = short_strike * 100.0
            max_risk = short_strike * 100.0

            qty = await self.s["sizing"].calculate_size(
                account.id,
                max_risk_per_contract=max_risk,
                max_capital_per_contract=max_capital,
                max_risk_pct=0.95,
                max_allocation_pct=0.95
            )
            if qty <= 0:
                return []

            leg = LegSpec(
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

            signal = Signal(
                research_strategy_id=self.params.research_strategy_id,
                strategy_category="BEN_CSP",
                underlying=ticker,
                legs=[leg],
                max_risk_per_contract=max_risk,
                max_capital_per_contract=max_capital,
                profit_target_pct=0.50, # 50% Profit Rule
                stop_loss_mult=self._exit_rules["stop_loss_mult"],
                roll_at_dte=self._exit_rules.get("roll_at_dte"),
                entry_features={
                    "spot": spot,
                    "short_strike": short_strike,
                    "delta": short_contract.delta,
                    "mid_premium": short_mid,
                    "yield_pct": (short_mid / short_strike) * 100.0,
                    "dte": target_dte_actual
                },
                notes=f"Ben CSP {ticker} ${short_strike:.1f} Put @ ${short_mid:.2f} ({target_dte_actual} DTE)"
            )
            return [signal]

        else:
            # ─── SILO 2: Bull Put Spread (Defined-Risk Credit Spread) ───
            # Adjust spread width if stock is cheap
            actual_width = min(spread_width, short_strike * 0.10) if short_strike < 50 else spread_width
            long_strike_target = short_strike - actual_width
            long_contract = self.s["broker"].find_strike_nearest(chain, long_strike_target, "PUT")

            if not long_contract or long_contract.strike >= short_strike:
                return []

            long_mid = _safe_mid(long_contract)
            net_credit = short_mid - long_mid
            if net_credit <= 0.10:
                return []

            actual_spread_width = short_strike - long_contract.strike
            max_risk = (actual_spread_width * 100.0) - (net_credit * 100.0)
            max_capital = actual_spread_width * 100.0

            qty = await self.s["sizing"].calculate_size(
                account.id,
                max_risk_per_contract=max_risk,
                max_capital_per_contract=max_capital,
                max_risk_pct=0.25,
                max_allocation_pct=0.50
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
                strike=long_contract.strike,
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

            signal = Signal(
                research_strategy_id=self.params.research_strategy_id,
                strategy_category="BEN_SPREAD",
                underlying=ticker,
                legs=[short_leg, long_leg],
                max_risk_per_contract=max_risk,
                max_capital_per_contract=max_capital,
                profit_target_pct=0.50, # 50% Profit Rule
                stop_loss_mult=2.0,     # 2x credit stop
                roll_at_dte=self._exit_rules.get("roll_at_dte"),
                entry_features={
                    "spot": spot,
                    "short_strike": short_strike,
                    "long_strike": long_contract.strike,
                    "net_credit": net_credit,
                    "max_risk": max_risk,
                    "roc_pct": (net_credit * 100.0 / max_risk) * 100.0 if max_risk > 0 else 0,
                    "dte": target_dte_actual
                },
                notes=f"Ben Bull Put Spread {ticker} ${short_strike:.1f}/${long_contract.strike:.1f} P @ ${net_credit:.2f} credit"
            )
            return [signal]

    async def manage(self, trade: Any, current_mtm: Any, now: datetime) -> ManageAction:
        ex = self._exit_rules
        ticker = trade.ticker.upper()
        spot = current_mtm["underlying_px"]

        # 1. 50% Max Profit Exit Rule
        pt_action = await self._check_profit_target(trade, current_mtm, target_pct=0.50)
        if pt_action:
            logger.info(f"{self.name}: 50% profit target reached on {ticker}. Closing trade.")
            return pt_action

        # 2. Stop Loss Check (for spreads)
        if trade.strategyCategory == "BEN_SPREAD":
            stop_action = await self._check_stop_loss_credit(trade, current_mtm, stop_mult=ex.get("stop_loss_mult", 2.0))
            if stop_action:
                return stop_action

        # 3. DTE Roll Check (e.g. at 14 DTE if challenged)
        roll_dte = ex.get("roll_at_dte", 14)
        if roll_dte is not None and trade.legs:
            leg = trade.legs[0]
            expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
            dte = (expiry_date - now.date()).days
            if 0 < dte <= int(roll_dte):
                # If spot is within 3% of strike, roll down and out
                if spot <= leg.strike * 1.03:
                    return ManageAction(close=True, reason="ROLL")

        # 4. Expiration Check (0 DTE)
        if trade.legs:
            leg = trade.legs[0]
            expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
            dte = (expiry_date - now.date()).days
            if dte <= 0:
                if spot <= leg.strike:
                    if trade.strategyCategory == "BEN_CSP":
                        logger.info(f"{self.name}: CSP at {leg.strike} assigned on {ticker} (Spot {spot:.2f}). Transitioning to Wheel holding.")
                        return ManageAction(close=True, reason="ASSIGNMENT")
                    else:
                        logger.info(f"{self.name}: Spread expired ITM on {ticker}.")
                        return ManageAction(close=True, reason="STOP")
                else:
                    logger.info(f"{self.name}: Option expired worthless OTM. Full profit captured.")
                    return ManageAction(close=True, reason="EOD")

        return ManageAction(close=False)
