import logging
import asyncio
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class TradeMtm:
    """
    Container for aggregate and per-leg mark-to-market (MTM) calculations.
    """
    def __init__(self, net_value: float, unrealized_pnl: float, leg_details: dict, underlying_px: float):
        self.net_value = net_value             # Net aggregate cost-to-close (positive if it costs cash to exit)
        self.unrealized_pnl = unrealized_pnl   # Cumulative open paper profit/loss
        self.leg_details = leg_details         # Map of option symbol/ticker -> latest quotes and greeks
        self.underlying_px = underlying_px     # Current underlying price

class LegQuoteService:
    """
    Aggregates real-time or cached mark-to-market (MTM) valuations across trade legs.
    Uses BrokerService to fetch underlying spot and individual option leg quotes.
    """
    def __init__(self, broker_service):
        self.broker = broker_service

    async def calculate_mtm(self, trade: Any) -> TradeMtm:
        """
        Fetches fresh quotes for all legs in a trade and computes aggregate net value & unrealized PnL.
        
        Math:
        - Long Option: Cost-to-close = -Mark * Quantity * 100, PnL = (Mark - OpenPrice) * Quantity * 100
        - Short Option: Cost-to-close = Mark * Quantity * 100, PnL = (OpenPrice - Mark) * Quantity * 100
        - Long Stock: Cost-to-close = -Spot * Quantity, PnL = (Spot - OpenPrice) * Quantity
        - Short Stock: Cost-to-close = Spot * Quantity, PnL = (OpenPrice - Spot) * Quantity
        """
        ticker = trade.ticker.upper()
        
        # 1. Fetch spot price
        try:
            spot_quote = await self.broker.get_stock_quote(ticker)
            spot = spot_quote["last"]
        except Exception as e:
            logger.error(f"LegQuoteService: Failed to fetch spot price for {ticker}: {e}")
            raise

        total_cost_to_close = 0.0
        total_unrealized_pnl = 0.0
        leg_details = {}

        # 2. Iterate through each trade leg
        for leg in trade.legs:
            symbol = leg.symbol.upper()
            qty = int(leg.quantity)
            side = leg.side.upper()         # "LONG" | "SHORT"
            leg_type = leg.optionType.upper() # "CALL" | "PUT" | "STOCK"
            open_price = leg.openPrice
            
            # Default fallbacks
            mark = open_price
            bid = open_price
            ask = open_price
            iv = 0.0
            delta = 0.0
            gamma = 0.0
            theta = 0.0
            vega = 0.0

            if leg_type == "STOCK":
                mark = spot
                bid = spot
                ask = spot
                
                # Math
                if side == "LONG":
                    cost = -spot * qty
                    pnl = (spot - open_price) * qty
                else: # SHORT
                    cost = spot * qty
                    pnl = (open_price - spot) * qty
            else:
                # Option contract
                try:
                    oq = await self.broker.get_option_quote(symbol)
                    mark = oq.get("mark", open_price)
                    bid = oq.get("bid", mark)
                    ask = oq.get("ask", mark)
                    iv = oq.get("iv", 0.0)
                    delta = oq.get("delta", 0.0)
                    gamma = oq.get("gamma", 0.0)
                    theta = oq.get("theta", 0.0)
                    vega = oq.get("vega", 0.0)
                except Exception as ex:
                    logger.warning(f"LegQuoteService: Quote lookup failed for option {symbol}. Falling back to open price. Error: {ex}")
                
                # Math (Option multiplier is 100)
                if side == "LONG":
                    cost = -mark * qty * 100.0
                    pnl = (mark - open_price) * qty * 100.0
                else: # SHORT
                    cost = mark * qty * 100.0
                    pnl = (open_price - mark) * qty * 100.0

            total_cost_to_close += cost
            total_unrealized_pnl += pnl

            # Record details for snapshot logging
            leg_details[symbol] = {
                "bid": bid,
                "ask": ask,
                "mark": mark,
                "iv": iv,
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega
            }

        logger.debug(
            f"Mtm Calculation for trade {trade.id} ({ticker}): "
            f"Underlying={spot:.2f}, Cost-to-Close={total_cost_to_close:,.2f}, PnL={total_unrealized_pnl:,.2f}"
        )
        
        return TradeMtm(
            net_value=total_cost_to_close,
            unrealized_pnl=total_unrealized_pnl,
            leg_details=leg_details,
            underlying_px=spot
        )
