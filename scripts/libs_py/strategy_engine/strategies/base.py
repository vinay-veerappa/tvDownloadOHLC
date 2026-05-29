from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)

@dataclass
class LegSpec:
    """A single leg the strategy wants to open."""
    option_type: str                # "CALL" | "PUT" | "STOCK"
    side: str                       # "LONG" | "SHORT"
    strike: Optional[float]         # None for STOCK
    expiry: Optional[date]          # None for STOCK
    quantity: int

    # Populated by strategy from chain lookup
    symbol: Optional[str] = None
    mid: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    iv: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None


@dataclass
class Signal:
    """A complete trade idea to be paper-executed."""
    research_strategy_id: str       # links to ResearchStrategy.id (the parameterized variant)
    strategy_category: str          # "WHEEL" | "ZERO_DTE_PCS" | etc. (links to Strategy.name)
    underlying: str
    legs: List[LegSpec]

    # Sizing inputs
    max_risk_per_contract: float
    max_capital_per_contract: float

    # Exit rule parameters (passed through to manage())
    profit_target_pct: float = 0.5
    stop_loss_mult: float = 2.0
    time_stop_minutes_before_close: Optional[int] = None
    time_stop_dte: Optional[int] = None
    roll_at_dte: Optional[int] = None

    # Context features at entry (logged into Trade.metadata)
    entry_features: Dict[str, Any] = field(default_factory=dict)

    # Human-readable
    notes: str = ""


@dataclass
class NearMiss:
    """A signal that almost fired but failed a filter."""
    research_strategy_id: str
    ticker: str
    underlying_px: float
    failing_filter: str
    filter_value: Optional[float]
    filter_threshold: Optional[float]
    context: Dict[str, Any]


@dataclass
class ManageAction:
    """Decision returned by Strategy.manage() for an open trade."""
    close: bool
    reason: Optional[str] = None    # "TARGET" | "STOP" | "EOD" | "REGIME_SHIFT" | "ASSIGNMENT" | "ROLL" | "SIGNAL"
    roll_to: Optional[dict] = None  # for rolls: new strike/expiry params


@dataclass
class StrategyParams:
    """Parameter set for one strategy variant.

    Each row in ResearchStrategy maps to one StrategyParams instance.
    Loaded from config.yaml at startup.
    """
    research_strategy_id: str
    name: str                       # e.g. "NVDA_WHEEL_30D_45DTE"
    category: str                   # e.g. "WHEEL"
    underlying: str
    account_id: str                 # the capital silo
    params: Dict[str, Any]          # strategy-specific knobs
    enabled: bool = True


class Strategy(ABC):
    """Abstract base for all strategies.

    Each concrete strategy:
    - Implements scan() and manage()
    - Declares which services it needs in __init__
    - Logs filter values to Signal.entry_features for every scan
    - Logs near-misses for every filter that fails
    """

    def __init__(self, params: StrategyParams, services: Dict[str, Any]):
        """
        Args:
            params: parameters for this variant (loaded from ResearchStrategy + config.yaml).
            services: dict of service instances:
                {
                    "broker": BrokerService,
                    "regime": RegimeService,
                    "em": ExpectedMoveService,
                    "iv": IvService,
                    "ict": IctService,
                    "calendar": CalendarService,
                    "earnings": EarningsService,
                    "holdings": HoldingsService,
                    "sizing": SizingService,
                    "leg_quote": LegQuoteService,
                    "prisma": PrismaClient,
                    "near_miss_log": NearMissLogger,
                }
        """
        self.params = params
        self.s = services
        self.name = params.name
        self.underlying = params.underlying
        self.p = params.params      # short alias for params dict

    def get_min_iv_rank_for_ticker(self, ticker: str, fallback: float) -> float:
        """
        Dynamically determine min_iv_rank threshold for a ticker based on the
        Tastytrade Volatility Playbook configured under volatility_grades.
        Falls back to the provided fallback value if the ticker is not categorized.
        """
        cfg = self.s.get("config", {})
        vol_grades = cfg.get("volatility_grades", {})
        for grade_name, grade_cfg in vol_grades.items():
            tickers = grade_cfg.get("tickers", [])
            if ticker in tickers:
                return float(grade_cfg.get("min_iv_rank", fallback))
        return float(fallback)

    # M7: Centralised exit-rule reader — strategies call self._exit_rules instead of hardcoding
    @property
    def _exit_rules(self) -> Dict[str, Any]:
        """
        Return exit-rule params sourced from config.yaml variant params with safe defaults.

        Defaults are tuned for CREDIT spreads. DEBIT strategies (e.g. wall_break) must
        use stop_loss_pct. Wheel-style "no stop" strategies should override stop_loss_mult to 99.0.
        """
        return {
            "profit_target_pct":         float(self.p.get("profit_target_pct", 0.50)),
            "stop_loss_mult":            float(self.p.get("stop_loss_mult", 2.0)),    # CREDIT
            "stop_loss_pct":             float(self.p.get("stop_loss_pct", 0.50)),    # DEBIT
            "roll_at_dte":               self.p.get("roll_at_dte"),
            "time_stop_dte":             self.p.get("time_stop_dte"),
            "flat_before_close_minutes": int(self.p.get("flat_before_close_minutes", 30)),
        }

    @abstractmethod
    async def scan(self, now: datetime) -> List[Signal]:
        """Evaluate entry conditions; return zero or more signals.

        For every filter that fails, call self._log_near_miss().
        For every signal that fires, populate signal.entry_features with
        all observed values.
        """
        pass

    @abstractmethod
    async def manage(
        self,
        trade: Any,                 # Trade row with eagerly-loaded legs and recent snapshots
        current_mtm: Any,           # TradeMtm from leg_quote_service
        now: datetime,
    ) -> ManageAction:
        """Evaluate exit conditions for an open trade.

        Default implementations of common exits (profit target, stop loss, time stop)
        are provided as helper methods; concrete strategies override only what's
        strategy-specific.
        """
        pass

    # ─── Common helper methods ─────────────────────────────────────────

    async def _log_near_miss(
        self,
        ticker: str,
        underlying_px: float,
        failing_filter: str,
        filter_value: Optional[float],
        filter_threshold: Optional[float],
        context: Dict[str, Any],
    ) -> None:
        """Record a near-miss via the SignalNearMiss table."""
        try:
            prisma = self.s["prisma"]
            import json
            await prisma.signalnearmiss.create(
                data={
                    "researchStrategyId": self.params.research_strategy_id,
                    "ticker": ticker,
                    "underlyingPx": float(underlying_px),
                    "failingFilter": failing_filter,
                    "filterValue": float(filter_value) if filter_value is not None else None,
                    "filterThreshold": float(filter_threshold) if filter_threshold is not None else None,
                    "context": json.dumps(context),
                }
            )
        except Exception as e:
            logger.error(f"Error logging near-miss for strategy {self.name}: {e}")

    async def _check_profit_target(
        self,
        trade: Any,
        current_mtm: Any,
        target_pct: float = 0.5,
    ) -> Optional[ManageAction]:
        """unrealized_pnl is already direction-correct (LegQuoteService handles CREDIT vs DEBIT)."""
        entry_price = trade.entryPrice or 0.0
        if entry_price <= 0.0:
            return None
        qty = trade.quantity
        pnl_per_share = current_mtm["unrealized_pnl"] / (qty * 100.0)
        if pnl_per_share >= entry_price * target_pct:
            return ManageAction(close=True, reason="TARGET")
        return None

    async def _check_stop_loss(
        self,
        trade: Any,
        current_mtm: Any,
        stop_mult: float = 2.0,
        stop_pct: Optional[float] = None,
    ) -> Optional[ManageAction]:
        """Back-compat: routes by trade.direction. Prefer the direction-specific helpers below."""
        if trade.direction == "CREDIT":
            return await self._check_stop_loss_credit(trade, current_mtm, stop_mult=stop_mult)
        elif trade.direction == "DEBIT":
            return await self._check_stop_loss_debit(
                trade, current_mtm,
                stop_pct=(stop_pct if stop_pct is not None else 0.5),
            )
        return None

    async def _check_stop_loss_credit(
        self,
        trade: Any,
        current_mtm: Any,
        stop_mult: float = 2.0,
    ) -> Optional[ManageAction]:
        """CREDIT stop: exit when cost-to-close >= stop_mult × credit received."""
        entry_price = trade.entryPrice or 0.0
        if entry_price <= 0.0:
            return None
        qty = trade.quantity
        net_per_share = current_mtm["net_value"] / (qty * 100.0)
        if net_per_share >= entry_price * stop_mult:
            return ManageAction(close=True, reason="STOP")
        return None

    async def _check_stop_loss_debit(
        self,
        trade: Any,
        current_mtm: Any,
        stop_pct: float = 0.5,
    ) -> Optional[ManageAction]:
        """DEBIT stop: exit when current value <= (1 - stop_pct) × debit paid.

        Sign convention: LegQuoteService.net_value is cost-to-close (positive = pay to close).
        For a long debit spread, closing returns money, so net_value is typically NEGATIVE.
        Current value per share = -net_per_share.
        """
        entry_price = trade.entryPrice or 0.0
        if entry_price <= 0.0:
            return None
        qty = trade.quantity
        net_per_share = current_mtm["net_value"] / (qty * 100.0)
        current_value_per_share = -net_per_share
        if current_value_per_share <= entry_price * (1.0 - stop_pct):
            return ManageAction(close=True, reason="STOP")
        return None

    async def _check_time_stop(
        self,
        trade: Any,
        now: datetime,
        flat_by_minutes_before_close: int = 30,
    ) -> Optional[ManageAction]:
        """Force close N minutes before market close (for 0DTE strategies)."""
        # Market close is 16:00 ET (Eastern)
        # Convert now to Eastern time
        import pytz
        tz_et = pytz.timezone("America/New_York")
        now_et = now.astimezone(tz_et)
        
        # Calculate close time
        close_time = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        time_until_close = (close_time - now_et).total_seconds() / 60.0
        
        if time_until_close <= flat_by_minutes_before_close:
            return ManageAction(close=True, reason="EOD")
            
        return None

    async def _check_dte_time_stop(
        self,
        trade: Any,
        now: datetime,
        close_at_dte: int = 21,
        reason: str = "ROLL",   # C9: caller specifies reason; no brittle self.name check
    ) -> Optional[ManageAction]:
        """For longer-dated trades: close at N DTE (the Tastytrade 21-DTE rule)."""
        # Find first leg's expiry date
        if not trade.legs:
            return None

        leg = trade.legs[0]
        if not leg.expiry:
            return None

        import pytz
        expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry

        # Calculate DTE remaining based on now (in NY/Eastern)
        tz_et = pytz.timezone("America/New_York")
        now_et = now.astimezone(tz_et).date()

        dte = (expiry_date - now_et).days
        if dte <= close_at_dte:
            return ManageAction(close=True, reason=reason)

        return None

    async def _check_regime_invalidation(
        self,
        trade: Any,
        now: datetime,
        require_positive_gamma: bool = True,
    ) -> Optional[ManageAction]:
        """If trade required positive gamma at entry and regime has shifted, close."""
        if not require_positive_gamma:
            return None
            
        try:
            regime = await self.s["regime"].get_gex_regime(trade.ticker)
            if not regime or regime.get("gexRegime") != "POSITIVE":
                return ManageAction(close=True, reason="REGIME_SHIFT")
        except Exception as e:
            logger.error(f"Error checking regime invalidation: {e}")
            
        return None
