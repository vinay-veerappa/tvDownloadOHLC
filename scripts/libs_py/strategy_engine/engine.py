import logging
import os
import yaml
import json
from datetime import datetime, timedelta, date
import pytz

from scripts.libs_py.strategy_engine.strategies import (
    WheelStrategy,
    ZeroDtePcsStrategy,
    LongDteCreditStrategy,
    MeanReversionEmStrategy,
    WallBreakStrategy,
    IncomeCcStrategy,
    EarningsStrangleStrategy
)
from scripts.libs_py.strategy_engine.strategies.base import StrategyParams, Signal, LegSpec
from scripts.libs_py.strategy_engine.paper_exec import PaperExecutor

# Import all services
from scripts.libs_py.strategy_engine.services.broker_service import BrokerService
from scripts.libs_py.strategy_engine.services.regime_service import RegimeService
from scripts.libs_py.strategy_engine.services.em_service import ExpectedMoveService
from scripts.libs_py.strategy_engine.services.iv_service import IvService
from scripts.libs_py.strategy_engine.services.ict_service import IctService
from scripts.libs_py.strategy_engine.services.calendar_service import CalendarService
from scripts.libs_py.strategy_engine.services.earnings_service import EarningsService
from scripts.libs_py.strategy_engine.services.holding_service import HoldingService
from scripts.libs_py.strategy_engine.services.sizing_service import SizingService
from scripts.libs_py.strategy_engine.services.leg_quote_service import LegQuoteService

logger = logging.getLogger(__name__)


def serialize_signal(signal: Signal) -> str:
    """Helper to serialize a dataclass Signal to JSON, handling dates/datetimes."""
    from dataclasses import asdict
    
    def json_serial(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
        
    return json.dumps(asdict(signal), default=json_serial)


def deserialize_signal(signal_json: str) -> Signal:
    """Helper to deserialize JSON back into a dataclass Signal object."""
    data = json.loads(signal_json)
    
    legs = []
    for l in data.get("legs", []):
        expiry_val = l.get("expiry")
        expiry_dt = None
        if expiry_val:
            try:
                if "T" in expiry_val:
                    expiry_dt = datetime.fromisoformat(expiry_val).date()
                else:
                    expiry_dt = date.fromisoformat(expiry_val)
            except Exception:
                expiry_dt = expiry_val
            
        leg = LegSpec(
            option_type=l.get("option_type"),
            side=l.get("side"),
            strike=l.get("strike"),
            expiry=expiry_dt,
            quantity=l.get("quantity"),
            symbol=l.get("symbol"),
            mid=l.get("mid"),
            bid=l.get("bid"),
            ask=l.get("ask"),
            iv=l.get("iv"),
            delta=l.get("delta"),
            gamma=l.get("gamma"),
            theta=l.get("theta"),
            vega=l.get("vega")
        )
        legs.append(leg)
        
    signal = Signal(
        research_strategy_id=data.get("research_strategy_id"),
        strategy_category=data.get("strategy_category"),
        underlying=data.get("underlying"),
        legs=legs,
        max_risk_per_contract=data.get("max_risk_per_contract"),
        max_capital_per_contract=data.get("max_capital_per_contract"),
        profit_target_pct=data.get("profit_target_pct", 0.5),
        stop_loss_mult=data.get("stop_loss_mult", 2.0),
        time_stop_minutes_before_close=data.get("time_stop_minutes_before_close"),
        time_stop_dte=data.get("time_stop_dte"),
        roll_at_dte=data.get("roll_at_dte"),
        entry_features=data.get("entry_features", {}),
        notes=data.get("notes", "")
    )
    return signal


STRATEGY_CLASSES = {
    "WHEEL": WheelStrategy,
    "ZERO_DTE_PCS": ZeroDtePcsStrategy,
    "LONG_DTE_CREDIT": LongDteCreditStrategy,
    "MEAN_REVERSION_EM": MeanReversionEmStrategy,
    "WALL_BREAK": WallBreakStrategy,
    "INCOME_CC": IncomeCcStrategy,
    "EARNINGS_STRANGLE": EarningsStrangleStrategy
}

INDEX_TICKERS = {"SPY", "SPX", "QQQ", "IWM"}
STOCK_TICKERS = {"NVDA", "TSLA", "AAPL", "GOOGL", "MSFT", "AMZN", "RIVN"}
DAILY_STRATEGY_CODES = {"WHEEL", "EARNINGS_STRANGLE", "INCOME_CC","LONG_DTE_CREDIT"}

class Engine:
    """
    Main Strategy Engine.
    Coordinating tick scanning, real-time mark-to-market management, 
    service initializations, and order executions.
    """
    def __init__(self, prisma, config_path: str):
        self.db = prisma
        self.config_path = config_path
        self.config = {}
        self.services = {}
        self.active_strategies = {}
        self.executor = None
        self._staleness_cache = {}  # C1: per-tick staleness cache

    async def initialize(self):
        """Initializes all services and instantiates enabled strategy variants."""
        logger.info("Initializing Options Strategy Engine...")
        
        # 1. Load config
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # 2. Instantiate and wire Services
        # In a real environment, we'd pass active calculators/fetchers to the services.
        # Here we initialize them with the prisma client and standard parameters.
        broker = BrokerService() # internal mock/direct Schwab API
        regime = RegimeService(db=self.db)
        em = ExpectedMoveService(db=self.db)
        iv = IvService(db=self.db) # direct EOD fallbacks
        ict = IctService()
        calendar = CalendarService(prisma_client=self.db)
        earnings = EarningsService(prisma_client=self.db)
        holdings = HoldingService(prisma_client=self.db)
        sizing = SizingService(prisma_client=self.db)
        leg_quote = LegQuoteService(broker_service=broker)

        self.services = {
            "prisma": self.db,
            "broker": broker,
            "regime": regime,
            "em": em,
            "iv": iv,
            "ict": ict,
            "calendar": calendar,
            "earnings": earnings,
            "holdings": holdings,
            "sizing": sizing,
            "leg_quote": leg_quote,
            "config": self.config
        }

        self.executor = PaperExecutor(self.db, broker, holdings)

        # 3. Instantiate enabled Strategy combinations (silos)
        loaded = 0
        skipped_disabled = 0
        for strategy_code, strat_cfg in self.config.get("strategies", {}).items():
            tickers = strat_cfg.get("tickers", [])
            variants = strat_cfg.get("variants", {})

            for variant_name, variant_params in variants.items():
                variant_params = variant_params or {}

                # M10: Skip disabled variants — log WARNING so operator is aware
                is_enabled = variant_params.get("enabled", True)  # default True if not specified
                if not is_enabled:
                    logger.warning(
                        f"Engine: Variant '{strategy_code}/{variant_name}' is DISABLED in config.yaml. Skipping all {len(tickers)} ticker(s)."
                    )
                    skipped_disabled += len(tickers)
                    continue

                for ticker in tickers:
                    comb_name = f"{strategy_code}_{variant_name}_{ticker}"

                    # Look up ResearchStrategy to link its DB id
                    research_strat = await self.db.researchstrategy.find_unique(where={"name": comb_name})
                    if not research_strat:
                        logger.warning(f"Engine: Seed data missing for ResearchStrategy '{comb_name}'. Skipping.")
                        continue

                    # Instantiate Strategy class
                    strat_class = STRATEGY_CLASSES.get(strategy_code)
                    if not strat_class:
                        logger.error(f"Engine: Unknown strategy code '{strategy_code}'")
                        continue

                    # Look up Account to get account_id
                    account = await self.db.account.find_first(where={"name": comb_name})
                    account_id = account.id if account else "unknown"

                    params = StrategyParams(
                        research_strategy_id=research_strat.id,
                        name=comb_name,
                        category=strategy_code,
                        underlying=ticker,
                        account_id=account_id,
                        params=variant_params,   # M7: full variant dict (incl. exit rules) passed through
                        enabled=True             # already filtered above
                    )

                    strategy_instance = strat_class(
                        params=params,
                        services=self.services
                    )

                    self.active_strategies[comb_name] = strategy_instance
                    loaded += 1

        logger.info(
            f"Engine: Loaded {loaded} active strategy combinations "
            f"({skipped_disabled} skipped — disabled in config)."
        )

    async def run_scan_tick(self, now: datetime, cadence: str = "index"):
        """
        Entry scan tick. Cadence filters which strategies execute:
          "index"  — only strategies whose underlying is an index/ETF
          "stock"  — only strategies whose underlying is a stock
          "daily"  — only strategies in DAILY_STRATEGY_CODES (Wheel, Earnings)
        """
        logger.info(f"Engine: Starting scan tick [{cadence}] at {now}")

        for name, strategy in self.active_strategies.items():
            try:
                # Cadence routing
                strategy_code = strategy.params.category
                underlying = strategy.params.underlying

                if cadence == "index":
                    if underlying not in INDEX_TICKERS:
                        continue
                    if strategy_code in DAILY_STRATEGY_CODES:
                        continue  # Wheel/Earnings on indices run only at 10:00
                elif cadence == "stock":
                    if underlying not in STOCK_TICKERS:
                        continue
                    if strategy_code in DAILY_STRATEGY_CODES:
                        continue
                elif cadence == "daily":
                    if strategy_code not in DAILY_STRATEGY_CODES:
                        continue

                # Staleness check for indices
                if underlying in INDEX_TICKERS:
                    is_stale = await self._check_index_staleness(underlying, now, strategy_code)
                    if is_stale:
                        logger.warning(f"Engine: Skipping entry scan for index silo '{name}' — GEX data stale.")
                        continue

                signals = await strategy.scan(now)
                for signal in signals:
                    # 1. Determine execution buffer delay
                    buffer_seconds = strategy.params.params.get(
                        "execution_buffer_seconds",
                        self.config.get("execution_buffer_seconds", 60)
                    )
                    execute_after = now + timedelta(seconds=buffer_seconds)
                    
                    # 2. Serialize Signal to JSON
                    serialized_signal = serialize_signal(signal)
                    
                    # 3. Parse variant name safely
                    variant_name = name
                    if name.startswith(strategy_code + "_"):
                        variant_name = name[len(strategy_code) + 1:]
                    if variant_name.endswith("_" + underlying):
                        variant_name = variant_name[:-len(underlying) - 1]
                    
                    # 4. Stage signal in the database
                    staged = await self.db.stagedsignal.create(
                        data={
                            "strategyName": name,
                            "strategyCode": strategy_code,
                            "variantName": variant_name,
                            "ticker": underlying,
                            "stagedAt": now,
                            "executeAfter": execute_after,
                            "status": "PENDING",
                            "signalJson": serialized_signal
                        }
                    )
                    
                    logger.info(f"Engine: Staged new pending signal {staged.id} for strategy '{name}' with {buffer_seconds}s execution buffer.")
                    
                    # 5. Notify Discord with a beautiful "Staged Setup Card"
                    try:
                        net_premium = 0.0
                        for leg in signal.legs:
                            premium = leg.mid if leg.mid is not None else (
                                (leg.bid + leg.ask) / 2.0 if (leg.bid and leg.ask) else 0.0
                            )
                            if leg.side == "SHORT":
                                net_premium += premium
                            else:
                                net_premium -= premium
                        
                        is_credit = net_premium >= 0.0
                        est_entry_price = abs(net_premium)
                        trade_direction = "CREDIT" if is_credit else "DEBIT"
                        qty = signal.legs[0].quantity
                        
                        legs_str = ""
                        for leg in signal.legs:
                            strike_str = f" ${leg.strike}" if leg.strike else ""
                            expiry_str = f" expiring {leg.expiry}" if leg.expiry else ""
                            legs_str += f"• **{leg.side}** {leg.option_type}{strike_str}{expiry_str} (Qty: {leg.quantity})\n"
                        
                        pt_str = f"{signal.profit_target_pct:.0%}" if signal.profit_target_pct is not None else "N/A"
                        sl_str = f"{signal.stop_loss_mult:.1f}x" if signal.stop_loss_mult is not None else "N/A"
                        
                        from zoneinfo import ZoneInfo
                        tz_et = ZoneInfo("America/New_York")
                        staged_at_et = now.astimezone(tz_et)
                        execute_after_et = execute_after.astimezone(tz_et)
                        
                        staged_msg = (
                            f"📝 **STRATEGY ENGINE: NEW SETUP STAGED**\n\n"
                            f"* **Silo:** `{name}`\n"
                            f"* **Underlying:** `{signal.underlying}`\n"
                            f"* **Action:** Stage {trade_direction} position\n"
                            f"* **Est. Entry Price:** `${est_entry_price:.2f}`\n"
                            f"* **Max Risk:** `${signal.max_risk_per_contract * qty:.2f}`\n"
                            f"* **Legs:**\n{legs_str}"
                            f"* **Exit Rules:** Target profit {pt_str} | Stop loss {sl_str}\n"
                            f"* **Staged At:** `{staged_at_et.strftime('%H:%M:%S')} ET`\n"
                            f"* **Execute After:** `{execute_after_et.strftime('%H:%M:%S')} ET` (Buffer: {buffer_seconds}s)\n"
                            f"* **Validation Guards:**\n"
                            f"  🛡️ *Underlying Breach Guard* (Spot must not breach short strikes)\n"
                            f"  🛡️ *Premium Deterioration Guard* (Credit must not drop by >10% / Debit must not increase by >10%)\n"
                            f"* **Notes:** {signal.notes}"
                        )
                        self.executor._notify_discord(staged_msg)
                    except Exception as de:
                        logger.warning(f"Engine: Failed to send Staged Setup Card to Discord: {de}")

            except Exception as e:
                logger.error(f"Engine: Error during scan tick for strategy '{name}': {e}", exc_info=True)

    async def run_staged_execution_tick(self, now: datetime):
        """
        Process all pending staged signals that have passed their execution delay buffer window.
        Performs underlying level breach checks and premium slippage deterioration guards before executing.
        """
        # Ensure now is timezone-aware
        if now.tzinfo is None:
            now = pytz.utc.localize(now)

        # 1. Fetch pending staged signals
        pending_signals = await self.db.stagedsignal.find_many(
            where={
                "status": "PENDING",
                "executeAfter": {"lte": now}
            }
        )

        if not pending_signals:
            return

        logger.info(f"Engine: Found {len(pending_signals)} pending staged signal(s) eligible for execution check.")

        for staged in pending_signals:
            try:
                # 2. Deserialize signal
                signal = deserialize_signal(staged.signalJson)
                underlying = signal.underlying
                strategy_name = staged.strategyName
                strategy_code = staged.strategyCode
                
                # Retrieve strategy instance to check per-variant parameters
                strategy = self.active_strategies.get(strategy_name)
                if not strategy:
                    logger.error(f"Engine: Strategy instance '{strategy_name}' not loaded. Expiring staged signal.")
                    await self.db.stagedsignal.update(
                        where={"id": staged.id},
                        data={"status": "EXPIRED"}
                    )
                    continue

                # 3. Fetch fresh spot price for Underlying Level Breach Guard
                quote = await self.services["broker"].get_stock_quote(underlying)
                spot = quote.get("last")
                if spot is None:
                    logger.error(f"Engine: Could not fetch stock quote for {underlying}. Skipping tick for this signal.")
                    continue

                # --- GUARD 1: Underlying Level Breach Guard ---
                is_valid = True
                fail_reason = ""
                
                short_legs = [leg for leg in signal.legs if leg.side == "SHORT"]
                for leg in short_legs:
                    if leg.option_type == "PUT":
                        if leg.strike is not None and spot <= leg.strike:
                            is_valid = False
                            fail_reason = f"Underlying Spot ${spot:.2f} breached short Put strike ${leg.strike:.2f}."
                            break
                    elif leg.option_type == "CALL":
                        if leg.strike is not None and spot >= leg.strike:
                            is_valid = False
                            fail_reason = f"Underlying Spot ${spot:.2f} breached short Call strike ${leg.strike:.2f}."
                            break

                # --- GUARD 2: Premium Deterioration Guard (Slippage) ---
                if is_valid:
                    # Calculate original entry price (credit/debit)
                    original_net_premium = 0.0
                    for leg in signal.legs:
                        premium = leg.mid
                        if premium is None:
                            if leg.bid is not None and leg.ask is not None:
                                premium = (leg.bid + leg.ask) / 2.0
                            else:
                                premium = 0.0
                        
                        if leg.side == "SHORT":
                            original_net_premium += premium
                        else:
                            original_net_premium -= premium
                    
                    is_credit = original_net_premium >= 0.0
                    original_premium_value = abs(original_net_premium)

                    # Fetch fresh option leg quotes and calculate fresh net premium
                    fresh_net_premium = 0.0
                    fresh_legs_data = []
                    
                    for leg in signal.legs:
                        oq = await self.services["broker"].get_option_quote(leg.symbol)
                        bid = oq.get("bid")
                        ask = oq.get("ask")
                        mark = oq.get("mark")
                        mid = mark if mark is not None else (((bid + ask) / 2.0) if (bid and ask) else 0.0)
                        
                        fresh_legs_data.append({
                            "bid": bid,
                            "ask": ask,
                            "mid": mid,
                            "iv": oq.get("iv", 0.0),
                            "delta": oq.get("delta", 0.0),
                            "gamma": oq.get("gamma", 0.0),
                            "theta": oq.get("theta", 0.0),
                            "vega": oq.get("vega", 0.0)
                        })
                        
                        if leg.side == "SHORT":
                            fresh_net_premium += mid
                        else:
                            fresh_net_premium -= mid

                    if is_credit:
                        fresh_premium_value = fresh_net_premium
                        # Credit must be >= 90% of staged credit, and >= $0.05
                        if fresh_premium_value < 0.90 * original_premium_value:
                            is_valid = False
                            fail_reason = f"Credit deteriorated: Fresh Credit ${fresh_premium_value:.2f} < 90% of Staged Credit ${original_premium_value:.2f}."
                        elif fresh_premium_value < 0.05:
                            is_valid = False
                            fail_reason = f"Credit deteriorated: Fresh Credit ${fresh_premium_value:.2f} < absolute minimum $0.05."
                    else:
                        fresh_premium_value = -fresh_net_premium
                        # Debit must be <= 110% of staged debit
                        if fresh_premium_value > 1.10 * original_premium_value:
                            is_valid = False
                            fail_reason = f"Debit deteriorated: Fresh Debit ${fresh_premium_value:.2f} > 110% of Staged Debit ${original_premium_value:.2f}."

                # 4. Finalize execution or expire staged signal
                if is_valid:
                    # Update signal legs with fresh prices/greeks before executing
                    for idx, leg in enumerate(signal.legs):
                        fd = fresh_legs_data[idx]
                        leg.bid = fd["bid"]
                        leg.ask = fd["ask"]
                        leg.mid = fd["mid"]
                        leg.iv = fd["iv"]
                        leg.delta = fd["delta"]
                        leg.gamma = fd["gamma"]
                        leg.theta = fd["theta"]
                        leg.vega = fd["vega"]

                    # Execute the trade paper Ledger entry
                    slippage_pct = strategy.params.params.get("slippage_pct", 0.02)
                    trade = await self.executor.execute_signal(strategy_name, signal, now, slippage_pct=slippage_pct)
                    
                    if trade:
                        # Update status in db
                        await self.db.stagedsignal.update(
                            where={"id": staged.id},
                            data={"status": "EXECUTED"}
                        )
                        logger.info(f"Engine: Staged signal {staged.id} successfully VALIDATED and EXECUTED as trade {trade.id}.")
                    else:
                        logger.error(f"Engine: PaperExecutor failed to open trade for staged signal {staged.id}.")
                else:
                    # Expire staged signal
                    await self.db.stagedsignal.update(
                        where={"id": staged.id},
                        data={"status": "EXPIRED"}
                    )
                    logger.warning(f"Engine: Staged signal {staged.id} EXPIRED due to validation failure: {fail_reason}")
                    
                    # Notify Discord of the cancellation/expiration
                    try:
                        from zoneinfo import ZoneInfo
                        tz_et = ZoneInfo("America/New_York")
                        staged_at_et = staged.stagedAt.astimezone(tz_et)
                        expired_at_et = now.astimezone(tz_et)
                        
                        cancel_msg = (
                            f"⚠️ **STRATEGY ENGINE: SETUP EXPIRED / CANCELLED**\n\n"
                            f"* **Silo:** `{staged.strategyName}`\n"
                            f"* **Underlying:** `{signal.underlying}`\n"
                            f"* **Action:** Cancel entry\n"
                            f"* **Staged At:** `{staged_at_et.strftime('%H:%M:%S')} ET`\n"
                            f"* **Expired At:** `{expired_at_et.strftime('%H:%M:%S')} ET`\n"
                            f"* **Reason for Cancellation:**\n"
                            f"  ❌ {fail_reason}\n"
                            f"* **Notes:** Staged setup conditions no longer met at execution window boundary."
                        )
                        self.executor._notify_discord(cancel_msg)
                    except Exception as de:
                        logger.warning(f"Engine: Failed to send staged expiration Discord notification: {de}")

            except Exception as e:
                logger.error(f"Engine: Error processing staged signal {staged.id}: {e}", exc_info=True)

    async def run_manage_tick(self, now: datetime, cadence: str = "index"):
        """
        Mark-to-market management tick. Only manages trades belonging to the
        strategies active in the given cadence to avoid redundant MTM work.
        """
        logger.info(f"Engine: Starting management tick [{cadence}] at {now}")

        # Fetch all open trades
        open_trades = await self.executor.list_open_trades()

        for trade in open_trades:
            try:
                # Find matching strategy instance by Account name
                account_name = trade.account.name
                strategy = self.active_strategies.get(account_name)
                if not strategy:
                    logger.warning(f"Engine: Open trade {trade.id} linked to account '{account_name}', but no strategy instance is loaded.")
                    continue

                # Cadence filter — only manage trades that belong to this tier
                underlying = strategy.params.underlying
                strategy_code = strategy.params.category
                if cadence == "index" and underlying not in INDEX_TICKERS:
                    continue
                if cadence == "stock" and underlying not in STOCK_TICKERS:
                    continue
                if cadence == "daily":
                    continue  # daily scan doesn't manage open trades

                # Get real-time MTM valuation
                current_mtm = await self.services["leg_quote"].get_trade_mtm(trade)
                if not current_mtm:
                    continue

                # Create MTM QuoteSnapshot record
                await self.db.quotesnapshot.create(
                    data={
                        "tradeId": trade.id,
                        "takenAt": now,
                        "underlyingPx": float(current_mtm["underlying_px"]),
                        "netValue": float(current_mtm["net_value"]),
                        "unrealizedPnl": float(current_mtm["unrealized_pnl"]),
                        "legPrices": current_mtm["leg_prices_json"]
                    }
                )

                # Evaluate strategy management exit conditions
                action = await strategy.manage(trade, current_mtm, now)
                if action.close:
                    logger.info(f"Engine: Exit triggered for trade {trade.id}. Reason: {action.reason or 'Management Rule'}")
                    # Close the trade
                    slippage_pct = strategy.params.params.get("slippage_pct", 0.02)
                    await self.executor.close_trade(
                        trade,
                        action,
                        current_mtm["net_value_per_contract"],
                        now,
                        slippage_pct=slippage_pct
                    )

            except Exception as e:
                logger.error(f"Engine: Error managing trade {trade.id}: {e}", exc_info=True)

    @staticmethod
    def _is_rth(now: datetime) -> bool:
        """Return True if `now` falls within RTH (9:30–16:00 ET, Mon–Fri)."""
        from zoneinfo import ZoneInfo
        now_et = now.astimezone(ZoneInfo("America/New_York"))
        if now_et.weekday() >= 5:
            return False
        mkt_open  = now_et.replace(hour=9,  minute=30, second=0, microsecond=0)
        mkt_close = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)
        return mkt_open <= now_et <= mkt_close

    async def _check_index_staleness(self, ticker: str, now: datetime, strategy_code: Optional[str] = None) -> bool:
        """
        For indices (SPX, SPY, etc.), any GEX/EM snapshot older than the strategy threshold
        during RTH indicates that the upstream streaming pipeline has stopped.
        In this scenario, entries must be blocked to prevent stale-data entries.

        Outside RTH the GEX writer does not run, so old data is expected — scans
        are silently skipped (DEBUG) without raising a WARNING.
        """
        # C1: check per-tick cache
        cache_key = (ticker, strategy_code)
        if cache_key in self._staleness_cache:
            cache_val, cache_ts = self._staleness_cache[cache_key]
            if cache_ts == now:
                return cache_val

        # Outside RTH the pipeline does not write GEX snapshots; data will always
        # appear stale.  Skip silently — this is not an actionable warning.
        if not self._is_rth(now):
            logger.debug(f"Engine: Staleness check skipped for {ticker} — outside RTH.")
            self._staleness_cache[cache_key] = (True, now)
            return True

        try:
            # Query the latest GexSnapshot for this ticker — use timestamp, not createdAt (B7)
            latest_gex = await self.db.gexsnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            if not latest_gex:
                logger.warning(f"Engine: No GexSnapshot found for {ticker} during RTH — pipeline may not have started.")
                self._staleness_cache[cache_key] = (True, now)
                return True

            # Calculate time difference — convert (not relabel) to UTC (B7)
            gex_time = latest_gex.timestamp
            if gex_time.tzinfo is None:
                gex_time = pytz.utc.localize(gex_time)
            now_utc = now.astimezone(pytz.utc)
            diff_seconds = (now_utc - gex_time).total_seconds()

            # Strategy-specific threshold: 180 seconds (3 minutes) for ZERO_DTE_PCS to accommodate the 
            # 60s-120s (averaging ~92s) live pipeline write cycle, otherwise 15 minutes (900s).
            threshold = 180.0 if strategy_code == "ZERO_DTE_PCS" else 900.0

            if diff_seconds > threshold:
                logger.warning(
                    f"Engine: Staleness alert! Latest GEX snapshot for {ticker} is "
                    f"{diff_seconds:.1f}s old during RTH (Strategy: {strategy_code}, Limit: {threshold}s) — upstream pipeline may have stopped."
                )
                self._staleness_cache[cache_key] = (True, now)
                return True

            self._staleness_cache[cache_key] = (False, now)
            return False

        except Exception as e:
            logger.error(f"Engine: Error checking staleness for {ticker}: {e}")
            return True
