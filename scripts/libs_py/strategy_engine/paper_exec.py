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

    def _notify_discord(self, message: str, files: List[str] = None):
        """Helper to send non-blocking Discord notifications using the discord_notify utility."""
        try:
            import os
            import yaml
            # Load config to check if Discord is enabled
            discord_cfg = {}
            config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                    discord_cfg = config.get("discord", {})
            
            if not discord_cfg.get("enabled", False):
                return
            
            channel = discord_cfg.get("channel", "test_channel")
            events = discord_cfg.get("events", {})
            
            # Identify which event this is to see if we should skip
            is_entry = "NEW POSITION OPENED" in message
            is_exit = "POSITION CLOSED" in message or "POSITION ASSIGNED" in message
            
            if is_entry and not events.get("trade_entry", True):
                return
            if is_exit and not events.get("trade_exit", True):
                return
            
            from scripts.utils.discord_notify import get_webhook_url, send_message
            webhook_url = get_webhook_url(channel)
            if not webhook_url:
                logger.warning(f"Discord: Webhook URL not found for channel '{channel}'")
                return
            
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, send_message, webhook_url, message, files)
                logger.info(f"Discord: Notification queued asynchronously for channel '{channel}'")
            except RuntimeError:
                # No running event loop (e.g. outside async context)
                send_message(webhook_url, message, files)
        except Exception as e:
            logger.warning(f"Discord: Failed to send notification: {e}")


    async def list_open_trades(self) -> List[Any]:
        """
        Lists all currently OPEN paper trades with their legs and accounts (C2).
        """
        return await self.db.trade.find_many(
            where={"status": "OPEN"},
            include={"legs": True, "account": True}
        )

    def _get_slippage(self, ticker: str) -> float:
        """Returns standard per-share slippage from the Playbook (M9)."""
        if ticker in ["SPY", "SPX", "QQQ", "IWM"]:
            return 0.02
        else:
            return 0.05

    async def execute_signal(self, strategy_name: str, signal: Signal, now: datetime, slippage_pct: float = 0.02) -> Optional[Any]:
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

            # 4. Calculate entry price based on legs (adjusted for dynamic slippage per Task C)
            net_premium = 0.0
            leg_slippages = []
            for leg in signal.legs:
                premium = leg.mid
                if premium is None:
                    if leg.bid is not None and leg.ask is not None:
                        premium = (leg.bid + leg.ask) / 2.0
                    else:
                        premium = 0.0

                # Dynamic slippage calculation
                if leg.bid is not None and leg.ask is not None and leg.ask > leg.bid:
                    leg_slippage = slippage_pct * (leg.ask - leg.bid)
                else:
                    leg_slippage = self._get_slippage(signal.underlying)
                
                leg_slippages.append(leg_slippage)

                if leg.side == "SHORT":
                    net_premium += (premium - leg_slippage)
                else:
                    net_premium -= (premium + leg_slippage)

            # For credit trades, net_premium is positive credit received.
            # For debit trades, net_premium is negative (cost paid). We'll store it as positive debit in entryPrice.
            is_credit = net_premium >= 0.0
            entry_price = abs(net_premium)

            # Sizing validation
            qty = signal.legs[0].quantity
            if qty <= 0:
                logger.warning(f"PaperExecutor: Invalid trade quantity {qty} for signal {signal.notes}")
                return None

            # 5. Create Trade record (writing fill_assumption to metadata)
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
                    "metadata": json.dumps({
                        **signal.entry_features,
                        "research_strategy_id": signal.research_strategy_id,
                        "fill_assumption": "mid_with_slippage",
                        "applied_slippages": leg_slippages
                    }),
                    "risk": signal.max_risk_per_contract * qty
                }
            )

            # 6. Create TradeLeg records
            for idx, leg in enumerate(signal.legs):
                effective_mid = leg.mid if leg.mid is not None else (
                    (leg.bid + leg.ask) / 2.0 if (leg.bid and leg.ask) else 0.0
                )
                leg_slippage = leg_slippages[idx]
                opening_price = (effective_mid - leg_slippage) if leg.side == "SHORT" else (effective_mid + leg_slippage)


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
                        "openPrice": opening_price,
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
            # NO-OP: We only book realized PnL at close. Cash acts as Net Equity.
            cash_effect = 0.0
            new_balance = account.currentBalance

            logger.info(f"PaperExecutor: Successfully executed trade entry {trade.id} for {strategy_name}. Balance remains: ${new_balance:,.2f}")

            # Discord Trade Entry Notification
            try:
                trade_direction = "CREDIT" if is_credit else "DEBIT"
                legs_str = ""
                for leg in signal.legs:
                    strike_str = f" ${leg.strike}" if leg.strike else ""
                    expiry_str = f" expiring {leg.expiry}" if leg.expiry else ""
                    legs_str += f"• **{leg.side}** {leg.option_type}{strike_str}{expiry_str} (Qty: {leg.quantity})\n"
                
                pt_str = f"{signal.profit_target_pct:.0%}" if signal.profit_target_pct is not None else "N/A"
                sl_str = f"{signal.stop_loss_mult:.1f}x" if signal.stop_loss_mult is not None else "N/A"
                
                entry_msg = (
                    f"📥 **STRATEGY ENGINE: NEW POSITION OPENED**\n\n"
                    f"* **Silo:** `{strategy_name}`\n"
                    f"* **Underlying:** `{signal.underlying}`\n"
                    f"* **Action:** Opened {trade_direction} position\n"
                    f"* **Entry Price:** `${entry_price:.2f}`\n"
                    f"* **Max Risk:** `${signal.max_risk_per_contract * qty:.2f}`\n"
                    f"* **Legs:**\n{legs_str}"
                    f"* **Exit Rules:** Target profit {pt_str} | Stop loss {sl_str}\n"
                    f"* **Notes:** {signal.notes}"
                )
                self._notify_discord(entry_msg)
            except Exception as de:
                logger.warning(f"PaperExecutor: Failed to queue Discord entry notification: {de}")

            return trade

        except Exception as e:
            logger.error(f"PaperExecutor: Failed to execute entry signal: {e}", exc_info=True)
            return None

    async def close_trade(self, trade: Any, action: ManageAction, cost_to_close: float, now: datetime, slippage_pct: float = 0.02) -> bool:
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

            is_assignment = False
            if "ASSIGN" in (action.reason or "").upper():
                has_short_option = False
                is_itm = False
                
                # Fetch current spot price for ITM verification
                spot_price = None
                try:
                    quote = await self.broker.get_stock_quote(trade_full.ticker)
                    spot_price = quote.get("last")
                except Exception as e:
                    logger.warning(f"PaperExecutor: Could not fetch spot price for ITM verification on assignment: {e}")
                
                for leg in trade_full.legs:
                    if leg.optionType in ["PUT", "CALL"] and leg.side == "SHORT":
                        has_short_option = True
                        if leg.expiry:
                            expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
                            days_to_expiry = (expiry_date - now.date()).days
                            
                            # Strict DTE check: only assign if at or past expiry (DTE <= 0)
                            if days_to_expiry <= 0:
                                if spot_price is not None and leg.strike is not None:
                                    if leg.optionType == "PUT" and spot_price <= leg.strike:
                                        is_itm = True
                                    elif leg.optionType == "CALL" and spot_price >= leg.strike:
                                        is_itm = True
                                else:
                                    # Fallback if quote is unavailable: assume assignment was intended
                                    is_itm = True
                                    logger.warning(f"PaperExecutor: Missing spot or strike for ITM verification on trade {trade.id}, defaulting to True.")
                
                if has_short_option and is_itm:
                    is_assignment = True
                else:
                    reason_msg = ""
                    if not has_short_option:
                        reason_msg = "no short option leg found"
                    elif not is_itm:
                        reason_msg = f"short option is out-of-the-money (Spot: {spot_price}, Strike: {trade_full.legs[0].strike})"
                    else:
                        reason_msg = "DTE is greater than 0"
                    logger.warning(f"PaperExecutor: Assignment requested for trade {trade.id} but {reason_msg}. Defaulting to normal close.")

            # 2. Calculate Realized P&L (incorporating dynamic slippage per Task C)
            num_legs = len(trade_full.legs)
            
            trade_pnl = 0.0
            stock_gain = 0.0

            # Handle stock transitions for option assignment
            if is_assignment:
                for leg in trade_full.legs:
                    if leg.optionType == "PUT" and leg.side == "SHORT":
                        # CSP Assignment: Buy stock at strike
                        strike = leg.strike
                        shares_to_buy = int(qty * 100)
                        logger.info(f"PaperExecutor: CSP assignment triggered. Buying {shares_to_buy} shares of {trade.ticker} at ${strike:.2f}")
                        await self.holdings.add_shares(trade.ticker, shares_to_buy, strike, now)
                        
                    elif leg.optionType == "CALL" and leg.side == "SHORT":
                        # CC Assignment: Sell stock at strike
                        strike = leg.strike
                        shares_to_sell = int(qty * 100)
                        logger.info(f"PaperExecutor: CC assignment triggered. Selling {shares_to_sell} shares of {trade.ticker} at ${strike:.2f}")
                        
                        holding = await self.holdings.get_holding(trade.ticker)
                        stock_cost_basis = holding["cost_basis"] if holding else strike
                        await self.holdings.remove_shares(trade.ticker, shares_to_sell, now)
                        
                        stock_gain = (strike - stock_cost_basis) * shares_to_sell
                        logger.info(f"PaperExecutor: Realized stock gain from CC call away: ${stock_gain:+,.2f} (Cost Basis: ${stock_cost_basis:.2f})")

            total_close_slippage = 0.0
            leg_exit_slippages = []
            
            num_short_legs = sum(1 for l in trade_full.legs if l.side == "SHORT" and l.optionType in ["PUT", "CALL"])
            num_long_legs = sum(1 for l in trade_full.legs if l.side == "LONG" and l.optionType in ["PUT", "CALL"])

            # 5. Process each leg to update Tradelegs and sum aggregate trade_pnl
            for leg in trade_full.legs:
                # Try fetching closing market prices from Schwab API, if available
                close_bid = None
                close_ask = None
                close_mid = None
                try:
                    if leg.optionType in ["PUT", "CALL"]:
                        opt_quote = await self.broker.get_option_quote(leg.symbol)
                    else:
                        opt_quote = await self.broker.get_stock_quote(leg.symbol)
                    close_bid = opt_quote.get("bid")
                    close_ask = opt_quote.get("ask")
                    mark = opt_quote.get("mark")
                    close_mid = mark if mark is not None else (((close_bid + close_ask) / 2.0) if (close_bid is not None and close_ask is not None) else opt_quote.get("last"))
                except Exception:
                    pass

                # Dynamic close slippage calculation
                if not is_assignment:
                    if close_bid is not None and close_ask is not None and close_ask > close_bid:
                        leg_slippage = slippage_pct * (close_ask - close_bid)
                    else:
                        leg_slippage = self._get_slippage(trade_full.ticker)
                else:
                    leg_slippage = 0.0

                total_close_slippage += leg_slippage
                leg_exit_slippages.append(leg_slippage)

                # Fallback to leg-level cost basis if Schwab quote not found
                # D5: use 100.0 multiplier only for options, 1.0 for stock
                multiplier = 100.0 if leg.optionType in ["PUT", "CALL"] else 1.0
                
                if close_mid is not None:
                    close_val = close_mid
                else:
                    if leg.optionType not in ["PUT", "CALL"]:
                        close_val = spot_price if spot_price is not None else leg.openPrice
                    elif cost_to_close > 0:
                        # Net liability: assign cost to short legs
                        if leg.side == "SHORT" and num_short_legs > 0:
                            close_val = cost_to_close / num_short_legs
                        else:
                            close_val = 0.0
                    elif cost_to_close < 0:
                        # Net asset: assign value to long legs
                        if leg.side == "LONG" and num_long_legs > 0:
                            close_val = abs(cost_to_close) / num_long_legs
                        else:
                            close_val = 0.0
                    else:
                        close_val = 0.0
                
                # Apply close slippage per leg
                if not is_assignment:
                    if leg.side == "SHORT":
                        close_val_adjusted = close_val + leg_slippage
                    else:
                        close_val_adjusted = max(0.0, close_val - leg_slippage)
                else:
                    if leg.optionType in ["PUT", "CALL"]:
                        close_val_adjusted = 0.0
                    else:
                        close_val_adjusted = close_val

                leg_pnl = 0.0
                if leg.side == "SHORT":
                    leg_pnl = (leg.openPrice - close_val_adjusted) * leg.quantity * multiplier
                else:
                    leg_pnl = (close_val_adjusted - leg.openPrice) * leg.quantity * multiplier

                trade_pnl += leg_pnl

                await self.db.tradeleg.update(
                    where={"id": leg.id},
                    data={
                        "closePrice": close_val_adjusted,
                        "closeBid": close_bid,
                        "closeAsk": close_ask,
                        "legPnl": leg_pnl,
                        "assigned": is_assignment,
                        "expiredOtm": not is_assignment and (close_val_adjusted <= 0.0)
                    }
                )

            # Include assignment stock gain/loss in the trade PnL
            trade_pnl += stock_gain
            cash_effect = trade_pnl

            # 6. Update Trade to CLOSED
            status_label = "ASSIGNED" if is_assignment else "CLOSED"
            
            # Normal exit price is the adjusted cost to close, assignment exit price is strike-based or 0
            if is_assignment:
                exit_price_adjusted = 0.0
            else:
                if is_credit:
                    exit_price_adjusted = cost_to_close + total_close_slippage
                else:
                    exit_price_adjusted = max(0.0, abs(cost_to_close) - total_close_slippage)

            # Update metadata to include exit slippages
            try:
                meta = json.loads(trade_full.metadata) if trade_full.metadata else {}
            except Exception:
                meta = {}
            meta["exit_slippages"] = leg_exit_slippages

            await self.db.trade.update(
                where={"id": trade.id},
                data={
                    "exitDate": now,
                    "exitPrice": exit_price_adjusted,
                    "pnl": trade_pnl,
                    "status": status_label,
                    "notes": (trade_full.notes or "") + f" | Closed: {action.reason}",
                    "metadata": json.dumps(meta)
                }
            )

            # 7. Update Account currentBalance
            new_balance = account.currentBalance + cash_effect
            await self.db.account.update(
                where={"id": account.id},
                data={"currentBalance": new_balance}
            )

            logger.info(f"PaperExecutor: Successfully closed trade {trade.id} ({status_label}). Realized P&L: ${trade_pnl:+,.2f}. Cash impact: ${cash_effect:+,.2f}. New Balance: ${new_balance:,.2f}")

            # Discord Trade Exit Notification
            try:
                # Re-fetch trade with legs to get updated database values (e.g. closePrice)
                trade_updated = await self.db.trade.find_unique(
                    where={"id": trade.id},
                    include={"legs": True, "account": True}
                )
                
                pnl_indicator = "🏆 **WIN**" if trade_pnl >= 0.0 else "⚠️ **LOSS**"
                outcome_str = f"{pnl_indicator}"
                if is_assignment:
                    outcome_str = "📦 **ASSIGNED**"
                
                legs_str = ""
                legs_to_format = trade_updated.legs if trade_updated else trade_full.legs
                for leg in legs_to_format:
                    strike_str = f" ${leg.strike}" if leg.strike else ""
                    open_px = leg.openPrice if leg.openPrice is not None else 0.0
                    close_px = leg.closePrice if leg.closePrice is not None else 0.0
                    legs_str += f"• **{leg.side}** {leg.optionType}{strike_str} (Open: ${open_px:.2f} | Close: ${close_px:.2f})\n"
                
                exit_msg = (
                    f"📤 **STRATEGY ENGINE: POSITION CLOSED**\n\n"
                    f"* **Silo:** `{trade_full.account.name}`\n"
                    f"* **Underlying:** `{trade_full.ticker}`\n"
                    f"* **Outcome:** {outcome_str}\n"
                    f"* **Realized P&L:** `${trade_pnl:+,.2f}`\n"
                    f"* **New Account Balance:** `${new_balance:,.2f}`\n"
                    f"* **Legs Details:**\n{legs_str}"
                    f"* **Exit Reason:** {action.reason}"
                )
                self._notify_discord(exit_msg)
            except Exception as de:
                logger.warning(f"PaperExecutor: Failed to queue Discord exit notification: {de}")

            return True

        except Exception as e:
            logger.error(f"PaperExecutor: Failed to close trade {trade.id}: {e}", exc_info=True)
            return False
