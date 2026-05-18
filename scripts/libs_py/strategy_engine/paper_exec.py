import logging
import json
from datetime import datetime, date
from typing import Any, Optional, List

from scripts.libs_py.strategy_engine.strategies.base import Signal, LegSpec, ManageAction

logger = logging.getLogger(__name__)

class PaperExecutor:
    """
    Paper Order Execution Engine.
    Handles trade entries, exits, option assignments, stock holdings updates, 
    and account balance maintenance in the SQLite Prisma database.
    """
    def __init__(self, prisma, broker, holdings):
        """
        Args:
            prisma: Prisma SQLite client
            broker: BrokerService instance
            holdings: HoldingService instance
        """
        self.db = prisma
        self.broker = broker
        self.holdings = holdings

    async def execute_signal(self, strategy_name: str, signal: Signal, now: datetime) -> Optional[Any]:
        """
        Opens a new paper trade by creating Trade and TradeLeg records, 
        and updates the corresponding silo Account balance.
        """
        try:
            # 1. Locate Account silo linked to the variant combination name
            account = await self.db.account.find_first(where={"name": strategy_name})
            if not account:
                logger.error(f"PaperExecutor: Account not found for variant name '{strategy_name}'")
                return None

            # 2. Locate Strategy parent category record
            parent_strategy = await self.db.strategy.find_first(where={"name": signal.strategy_category})
            if not parent_strategy:
                logger.error(f"PaperExecutor: Parent Strategy not found for category '{signal.strategy_category}'")
                return None

            # 3. Locate standard playbook record
            playbook = await self.db.playbook.find_first(where={"name": "Strategy Engine Playbook"})
            playbook_id = playbook.id if playbook else None

            # 4. Calculate entry price based on legs
            # Net price is sum of leg premiums: negative for LONG, positive for SHORT
            net_premium = 0.0
            for leg in signal.legs:
                premium = leg.mid
                if leg.side == "SHORT":
                    net_premium += premium
                else:
                    net_premium -= premium

            # For credit trades, net_premium is positive credit received.
            # For debit trades, net_premium is negative (cost paid). We'll store it as positive debit in entryPrice.
            is_credit = net_premium >= 0.0
            entry_price = abs(net_premium)

            # Sizing validation
            qty = signal.legs[0].quantity
            if qty <= 0:
                logger.warning(f"PaperExecutor: Invalid trade quantity {qty} for signal {signal.notes}")
                return None

            # 5. Create Trade record
            trade = await self.db.trade.create(
                data={
                    "ticker": signal.underlying,
                    "entryDate": now,
                    "entryPrice": entry_price,
                    "quantity": float(qty),
                    "direction": "CREDIT" if is_credit else "DEBIT",
                    "status": "OPEN",
                    "accountId": account.id,
                    "strategyId": parent_strategy.id,
                    "playbookId": playbook_id,
                    "originalSource": "strategy_engine",
                    "takeProfit": signal.profit_target_pct,
                    "stopLoss": signal.stop_loss_mult,
                    "notes": signal.notes,
                    "metadata": json.dumps(signal.entry_features),
                    "risk": signal.max_risk_per_contract * qty
                }
            )

            # 6. Create TradeLeg records
            for idx, leg in enumerate(signal.legs):
                # Ensure expiry is a datetime if it's a date
                expiry_dt = None
                if leg.expiry:
                    if isinstance(leg.expiry, date):
                        expiry_dt = datetime.combine(leg.expiry, datetime.min.time())
                    else:
                        expiry_dt = leg.expiry

                await self.db.tradeleg.create(
                    data={
                        "tradeId": trade.id,
                        "symbol": leg.symbol,
                        "legIndex": idx,
                        "optionType": leg.option_type,
                        "side": leg.side,
                        "strike": float(leg.strike) if leg.strike else None,
                        "expiry": expiry_dt,
                        "quantity": int(leg.quantity),
                        "openPrice": float(leg.mid),
                        "openBid": float(leg.bid) if leg.bid else None,
                        "openAsk": float(leg.ask) if leg.ask else None,
                        "openIv": float(leg.iv) if leg.iv else None,
                        "openDelta": float(leg.delta) if leg.delta else None,
                        "openGamma": float(leg.gamma) if leg.gamma else None,
                        "openTheta": float(leg.theta) if leg.theta else None,
                        "openVega": float(leg.vega) if leg.vega else None
                    }
                )

            # 7. Update Account balance
            # Credit adds premium to balance; Debit subtracts cost from balance
            cash_effect = net_premium * qty * 100.0
            new_balance = account.currentBalance + cash_effect
            await self.db.account.update(
                where={"id": account.id},
                data={"currentBalance": new_balance}
            )

            logger.info(f"PaperExecutor: Successfully executed trade entry {trade.id} for {strategy_name}. Cash impact: ${cash_effect:+,.2f}. New Balance: ${new_balance:,.2f}")
            return trade

        except Exception as e:
            logger.error(f"PaperExecutor: Failed to execute entry signal: {e}", exc_info=True)
            return None

    async def close_trade(self, trade: Any, action: ManageAction, cost_to_close: float, now: datetime) -> bool:
        """
        Exits an open paper trade, updates closing TradeLeg details, realizes P&L, 
        and updates the corresponding silo Account balance. Handles options assignment transitions.
        """
        try:
            # 1. Fetch trade with legs and account
            trade_full = await self.db.trade.find_unique(
                where={"id": trade.id},
                include={"legs": True, "account": True}
            )
            if not trade_full:
                logger.error(f"PaperExecutor: Trade {trade.id} not found for closing.")
                return False

            account = trade_full.account
            qty = trade_full.quantity
            is_credit = trade_full.direction == "CREDIT"
            entry_price = trade_full.entryPrice

            # 2. Calculate P&L of the options legs
            # For Credit trades, realized PnL = (entryPrice - cost_to_close) * qty * 100
            # For Debit trades, realized PnL = (cost_to_close - entryPrice) * qty * 100
            if is_credit:
                trade_pnl = (entry_price - cost_to_close) * qty * 100.0
            else:
                trade_pnl = (cost_to_close - entry_price) * qty * 100.0

            # 3. Handle Assignment Cash Transitions and Equity holdings updates
            is_assignment = "ASSIGN" in (action.reason or "").upper()
            total_cash_returned = 0.0

            if is_assignment:
                for leg in trade_full.legs:
                    if leg.optionType == "PUT" and leg.side == "SHORT":
                        # CSP Short Put Assignment: buy 100 shares at strike
                        strike = leg.strike
                        shares_to_buy = int(qty * 100)
                        logger.info(f"PaperExecutor: CSP assignment triggered. Buying {shares_to_buy} shares of {trade.ticker} at ${strike:.2f}")
                        
                        # Add shares to Holdings
                        await self.holdings.add_shares(trade.ticker, shares_to_buy, strike, now)
                        
                        # Subtract cash for stock purchase
                        total_cash_returned -= strike * shares_to_buy

                    elif leg.optionType == "CALL" and leg.side == "SHORT":
                        # CC Short Call Assignment: stock is called away at strike
                        strike = leg.strike
                        shares_to_sell = int(qty * 100)
                        logger.info(f"PaperExecutor: CC assignment triggered. Selling {shares_to_sell} shares of {trade.ticker} at ${strike:.2f}")
                        
                        # Get stock cost basis before removal to compute equity P&L
                        holding = await self.holdings.get_holding(trade.ticker)
                        stock_cost_basis = holding.costBasis if holding else strike
                        
                        # Remove shares from Holdings
                        await self.holdings.remove_shares(trade.ticker, shares_to_sell, now)
                        
                        # Add cash for stock sale
                        total_cash_returned += strike * shares_to_sell
                        
                        # Add stock realized gains to overall trade realized P&L!
                        stock_gain = (strike - stock_cost_basis) * shares_to_sell
                        trade_pnl += stock_gain
                        logger.info(f"PaperExecutor: Realized stock gain from CC call away: ${stock_gain:+,.2f} (Cost Basis: ${stock_cost_basis:.2f})")

            # 4. Closing Cash impact to Silo account
            # Credit: we pay cost_to_close to exit
            # Debit: we receive cost_to_close to exit
            if not is_assignment:
                if is_credit:
                    cash_effect = -cost_to_close * qty * 100.0
                else:
                    cash_effect = cost_to_close * qty * 100.0
            else:
                # If assigned, the short option expired worthless or ITM (pnl is full credit received, which is already in balance).
                # The cash impact is only the assignment purchase/sale itself!
                cash_effect = total_cash_returned

            # 5. Update Tradelegs to CLOSED
            for leg in trade_full.legs:
                # Try fetching closing market prices from Schwab API, if available
                close_bid = None
                close_ask = None
                close_mid = None
                try:
                    opt_quote = await self.broker.get_option_quote(leg.symbol)
                    close_bid = opt_quote.bid
                    close_ask = opt_quote.ask
                    close_mid = opt_quote.mid
                except Exception:
                    pass

                # Calculate leg-level PnL
                leg_pnl = 0.0
                if leg.side == "SHORT":
                    leg_pnl = (leg.openPrice - (close_mid or 0.0)) * leg.quantity * 100.0
                else:
                    leg_pnl = ((close_mid or 0.0) - leg.openPrice) * leg.quantity * 100.0

                await self.db.tradeleg.update(
                    where={"id": leg.id},
                    data={
                        "closePrice": close_mid or cost_to_close,
                        "closeBid": close_bid,
                        "closeAsk": close_ask,
                        "legPnl": leg_pnl,
                        "assigned": is_assignment,
                        "expiredOtm": not is_assignment and (cost_to_close <= 0.0)
                    }
                )

            # 6. Update Trade to CLOSED
            status_label = "ASSIGNED" if is_assignment else "CLOSED"
            await self.db.trade.update(
                where={"id": trade.id},
                data={
                    "exitDate": now,
                    "exitPrice": cost_to_close,
                    "pnl": trade_pnl,
                    "status": status_label,
                    "notes": (trade_full.notes or "") + f" | Closed: {action.reason}"
                }
            )

            # 7. Update Account currentBalance
            new_balance = account.currentBalance + cash_effect
            await self.db.account.update(
                where={"id": account.id},
                data={"currentBalance": new_balance}
            )

            logger.info(f"PaperExecutor: Successfully closed trade {trade.id} ({status_label}). Realized P&L: ${trade_pnl:+,.2f}. Cash impact: ${cash_effect:+,.2f}. New Balance: ${new_balance:,.2f}")
            return True

        except Exception as e:
            logger.error(f"PaperExecutor: Failed to close trade {trade.id}: {e}", exc_info=True)
            return False
