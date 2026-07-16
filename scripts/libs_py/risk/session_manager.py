"""
Session-level risk manager. Strategy-AGNOSTIC.

It does not know or care which strategy is requesting a trade.
It only sees: "a trade request with X risk dollars" and approves/denies
based on the current session state.
"""
import pandas as pd
from datetime import timedelta
import logging


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

from scripts.libs_py.risk.risk_config import Signal, TradeRecord, SessionState


class SessionRiskManager:
    def __init__(self, config_session_risk, config_sessions):
        self.config = config_session_risk
        self.sessions = config_sessions
        self.state = SessionState()
        self.logger = logging.getLogger(__name__)

    def on_session_open(self, trading_date: pd.Timestamp):
        """Reset session state for a new trading day."""
        self.state.trading_date = trading_date
        self.state.trade_count = 0
        self.state.consecutive_losers = 0
        self.state.session_pnl = 0.0
        self.state.is_paused = False
        self.state.pause_until = None
        self.state.is_stopped_for_day = False
        self.state.open_position = None
        self.state.trades = []

    def request_entry(self, signal: Signal, current_time: pd.Timestamp) -> bool:
        """Evaluate if the signal can be traded."""
        if self.state.is_stopped_for_day:
            self.logger.info(f"Entry denied: Stopped for the day (Session PnL: {self.state.session_pnl})")
            return False

        if self.state.is_paused:
            if self.state.pause_until and current_time > self.state.pause_until:
                self.state.is_paused = False
                self.logger.info("Session unpaused.")
            else:
                self.logger.info(f"Entry denied: Session paused until {self.state.pause_until}")
                return False

        if self.state.trade_count >= self.config.max_trades_per_day:
            self.logger.info(f"Entry denied: Max trades per day ({self.config.max_trades_per_day}) reached.")
            return False

        if self.state.open_position is not None:
            # Note: Max concurrent positions logic is simplified here as open_position holds a single trade.
            # To support config.max_concurrent_positions > 1 we would need a list.
            if self.config.max_concurrent_positions <= 1:
                self.logger.info("Entry denied: Already holding max concurrent positions.")
                return False

        # Convert timestamp to HH:MM strings for comparison using zero-padded time formats
        rth_start_time = pd.to_datetime(self.sessions.rth_start).time()
        last_entry_time = pd.to_datetime(self.sessions.last_entry).time()
        current_clock_time = current_time.time()

        if current_clock_time < rth_start_time:
            self.logger.info("Entry denied: Before RTH start.")
            return False

        if current_clock_time > last_entry_time:
            self.logger.info("Entry denied: After last entry time.")
            return False

        if self.state.session_pnl - signal.risk_dollars <= -self.config.daily_max_loss:
            self.logger.info("Entry denied: Trade risk would breach daily max loss limit.")
            return False

        return True

    def record_trade_result(self, trade: TradeRecord):
        """Update session state after a trade closes."""
        self.state.session_pnl += trade.realized_pnl
        self.state.trade_count += 1
        
        if trade.realized_pnl < 0:
            self.state.consecutive_losers += 1
        else:
            self.state.consecutive_losers = 0

        current_time = trade.exit_time or pd.Timestamp.now()

        if self.state.consecutive_losers >= self.config.max_consecutive_losers:
            self.state.is_paused = True
            self.state.pause_until = current_time + timedelta(minutes=self.config.pause_after_consecutive_minutes)

        if self.state.consecutive_losers >= self.config.hard_stop_consecutive_losers:
            self.state.is_stopped_for_day = True
            
        if self.state.session_pnl <= -self.config.daily_max_loss:
            self.state.is_stopped_for_day = True

        self.state.trades.append(trade)
        self.state.open_position = None

    def check_flatten(self, current_time: pd.Timestamp) -> bool:
        """Returns True if all positions should be flattened."""
        current_clock_time = current_time.time()
        flatten_time = pd.to_datetime(self.sessions.flatten_by).time()
        
        if current_clock_time >= flatten_time:
            return True
        if self.state.session_pnl <= -self.config.daily_max_loss:
            return True
        return False

    def get_session_summary(self) -> dict:
        winners = len([t for t in self.state.trades if t.realized_pnl > 0])
        losers = len([t for t in self.state.trades if t.realized_pnl < 0])
        return {
            "trade_count": self.state.trade_count,
            "winners": winners,
            "losers": losers,
            "session_pnl": self.state.session_pnl,
            "max_consecutive_losers": self.state.consecutive_losers,
            "is_stopped_for_day": self.state.is_stopped_for_day
        }
