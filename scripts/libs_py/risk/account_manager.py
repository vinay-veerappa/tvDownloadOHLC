"""
Account-level risk manager. Tracks equity across sessions.
"""
from enum import Enum
import pandas as pd
from scripts.libs_py.risk.risk_config import AccountState


class AccountRiskManager:
    """
    Tracks account-level state across sessions, ensuring daily and weekly limits
    align with typical proprietary trading evaluations.
    """
    def __init__(self, config_account_risk):
        self.config = config_account_risk
        self.state = AccountState()
        self.state.equity = getattr(config_account_risk, "starting_equity", 50000.0)
        self.state.high_water_mark = self.state.equity
        self.state.peak_equity = self.state.equity
        self.state.trailing_drawdown_remaining = getattr(config_account_risk, "trailing_drawdown", 2000.0)
        self.state.weekly_start_equity = self.state.equity

    def on_session_close(self, daily_pnl: float):
        self.state.equity += daily_pnl
        self.state.daily_pnls.append(daily_pnl)
        self.state.days_traded += 1
        
        # EOD Trailing DD Update
        from scripts.trading_framework.config.config_loader import TrailingType
        trailing_type = getattr(self.config, "trailing_type", TrailingType.EOD)
        if trailing_type == TrailingType.EOD or (isinstance(trailing_type, str) and trailing_type.lower() == "eod"):
            self.state.high_water_mark = max(self.state.high_water_mark, self.state.equity)
            self.state.trailing_drawdown_remaining = (
                self.config.trailing_drawdown - (self.state.high_water_mark - self.state.equity)
            )
            if self.state.equity < self.state.high_water_mark - self.config.trailing_drawdown:
                self.state.is_blown = True
                
        # Weekly tracking
        self.state.weekly_pnl += daily_pnl
        if self.state.weekly_pnl <= -self.config.weekly_drawdown_limit:
            self.state.is_in_observation = True

    def on_week_start(self):
        self.state.weekly_pnl = 0.0
        self.state.weekly_start_equity = self.state.equity
        self.state.is_in_observation = False

    def can_trade_today(self) -> bool:
        if self.state.is_blown:
            return False
        if self.state.is_in_observation and getattr(self.config, "weekly_action", "observation") == "observation":
            return False
        return True

    def has_passed_eval(self) -> bool:
        return (
            self.state.equity >= self.config.starting_equity + self.config.profit_target
            and not self.state.is_blown
        )

    def get_equity_curve(self) -> pd.Series:
        return pd.Series(self.state.daily_pnls).cumsum() + self.config.starting_equity

    def get_account_summary(self) -> dict:
        return {
            "current_equity": self.state.equity,
            "high_water_mark": self.state.high_water_mark,
            "drawdown_remaining": self.state.trailing_drawdown_remaining,
            "days_traded": self.state.days_traded,
            "is_blown": self.state.is_blown,
            "has_passed": self.has_passed_eval(),
            "weekly_pnl": self.state.weekly_pnl
        }
