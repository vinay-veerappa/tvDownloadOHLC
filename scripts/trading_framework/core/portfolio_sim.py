"""
Multi-strategy portfolio simulator with session and account risk.

Active in "portfolio" risk mode.
"""
from dataclasses import dataclass
from typing import Optional
import pandas as pd

from scripts.libs.risk.risk_config import Signal, TradeRecord, TradeStatus
from scripts.libs.risk.session_manager import SessionRiskManager
from scripts.libs.risk.account_manager import AccountRiskManager
from scripts.trading_framework.core.engine import BacktestEngine, BacktestResult
from scripts.trading_framework.core.execution import apply_slippage


@dataclass
class PortfolioResult:
    per_strategy_results: dict[str, BacktestResult]
    combined_trades: list[TradeRecord]
    combined_equity_curve: pd.Series
    combined_daily_pnl: pd.Series
    session_summaries: list[dict]      # Per-day summary
    account_summary: dict
    prop_eval_passed: bool
    days_to_pass: Optional[int]


class PortfolioSimulator:
    """
    Simulates multiple strategies sharing the same account and session limits.
    """
    def __init__(self, config):
        self.config = config
        self.session_mgr = SessionRiskManager(config.session_risk, config.sessions)
        self.account_mgr = AccountRiskManager(config.account_risk)
        self.engines = {}
        
    def run(self, strategy_signals: dict[str, list[Signal]], df_1m: pd.DataFrame) -> PortfolioResult:
        all_signals = []
        for strat_name, signals in strategy_signals.items():
            # In a real environment, strategies might have different configs. 
            # We initialize engines here if they don't exist
            if strat_name not in self.engines:
                # We could pull strategy-specific configs here, 
                # but for now we'll supply the global config
                self.engines[strat_name] = BacktestEngine(self.config)
            all_signals.extend(signals)
            
        # 1. Merge all signals across strategies into a single time-sorted list
        all_signals = sorted(all_signals, key=lambda x: x.timestamp)
        
        # Determine all available trading dates
        df_1m.index = pd.to_datetime(df_1m.index)
        trading_dates = pd.Series(df_1m.index.date).unique()
        
        combined_trades = []
        session_summaries = []
        days_to_pass = None
        
        symbol_data = getattr(self.config.execution, "tick_size", {"MES": 0.25})
        slippage_ticks = getattr(self.config.execution, "slippage_ticks", 1)
        
        # Group signals by date for easier lookup
        signals_by_date = {}
        for s in all_signals:
            d = s.timestamp.date()
            if d not in signals_by_date:
                signals_by_date[d] = []
            signals_by_date[d].append(s)
        
        # Helper to simulate single trade bar-by-bar to allow session check interruptions
        def _simulate_single_trade_with_session_check(engine, sig, df_1m, start_idx):
            # This replicates the inner loop of BacktestEngine.run but allows checking session_mgr
            tick_size = symbol_data.get(sig.symbol, 0.25)
            pt_value = getattr(self.config.execution, "point_value", {"MES": 5.0}).get(sig.symbol, 5.0)
            commission = getattr(self.config.execution, "commission_per_contract", 0.62)
            default_contracts = getattr(self.config.execution, "default_contracts", 1)
            
            entry_fill = apply_slippage(sig.entry_price, sig.direction, tick_size, slippage_ticks, is_entry=True)
            trade = TradeRecord(
                signal=sig, status=TradeStatus.OPEN,
                entry_time=sig.timestamp, entry_fill_price=entry_fill,
                policy_name=engine.config.trade_risk_policy
            )
            
            engine.policy.reset()
            current_contracts = default_contracts
            
            from scripts.trading_framework.core.execution import compute_commission, compute_pnl
            from scripts.libs.risk.trade_policies import PolicyAction
            from scripts.libs.risk.risk_config import TradeDirection
            
            max_bars = len(df_1m)
            step_count = 0
            
            for step, i in enumerate(range(start_idx, max_bars)):
                step_count = step
                current_time = df_1m.index[i]
                bar = df_1m.iloc[i].to_dict()
                
                # Check session flatten rules
                if self.session_mgr.check_flatten(current_time):
                    trade.exit_time = current_time
                    trade.exit_fill_price = apply_slippage(bar["close"], sig.direction, tick_size, slippage_ticks, is_entry=False)
                    trade.exit_reason = "session_risk"
                    trade.status = TradeStatus.CLOSED
                    break
                    
                # Update MAE / MFE
                hi = bar["high"]
                lo = bar["low"]
                if sig.direction == TradeDirection.LONG:
                    trade.mae_points = max(trade.mae_points, entry_fill - lo)
                    trade.mfe_points = max(trade.mfe_points, hi - entry_fill)
                else:
                    trade.mae_points = max(trade.mae_points, hi - entry_fill)
                    trade.mfe_points = max(trade.mfe_points, entry_fill - lo)
                    
                decision = engine.policy.manage(trade, bar, step)
                
                if decision.action == PolicyAction.TAKE_PARTIAL or decision.action == PolicyAction.TAKE_PARTIAL_AND_MOVE_STOP:
                    trade.partial_exit_time = current_time
                    trade.partial_exit_pct = decision.partial_pct
                    trade.partial_exit_price = apply_slippage(bar["close"], sig.direction, tick_size, slippage_ticks, is_entry=False)
                    trade.status = TradeStatus.PARTIAL
                    current_contracts = max(1, int(default_contracts * (1 - decision.partial_pct)))
                    if decision.action == PolicyAction.TAKE_PARTIAL_AND_MOVE_STOP:
                        trade.signal.stop_price = decision.new_stop_price
                elif decision.action == PolicyAction.MOVE_STOP:
                    trade.signal.stop_price = decision.new_stop_price
                elif decision.action == PolicyAction.EXIT_FULL:
                    trade.exit_time = current_time
                    trade.exit_fill_price = apply_slippage(bar["close"], sig.direction, tick_size, slippage_ticks, is_entry=False)
                    trade.exit_reason = decision.exit_reason
                    trade.status = TradeStatus.CLOSED
                    break
                    
            trade.bars_in_trade = step_count
            
            if trade.partial_exit_price is not None:
                partial_ct = default_contracts - current_contracts
                comm = compute_commission(partial_ct, commission)
                pnl1 = compute_pnl(entry_fill, trade.partial_exit_price, sig.direction, partial_ct, pt_value, comm)
                
                comm2 = compute_commission(current_contracts, commission)
                pnl2 = compute_pnl(entry_fill, trade.exit_fill_price, sig.direction, current_contracts, pt_value, comm2) if trade.exit_fill_price else 0
                trade.realized_pnl = pnl1 + pnl2
            elif trade.exit_fill_price is not None:
                comm = compute_commission(default_contracts, commission)
                trade.realized_pnl = compute_pnl(entry_fill, trade.exit_fill_price, sig.direction, default_contracts, pt_value, comm)
            else:
                trade.realized_pnl = 0.0
                
            return trade

        last_week = None
        
        for date_obj in trading_dates:
            dt_ts = pd.Timestamp(date_obj)
            
            current_week = dt_ts.isocalendar()[1]
            if last_week is not None and current_week != last_week:
                self.account_mgr.on_week_start()
            last_week = current_week
            
            if not self.account_mgr.can_trade_today():
                continue
                
            self.session_mgr.on_session_open(date_obj)
            
            day_signals = signals_by_date.get(date_obj, [])
            for sig in day_signals:
                if self.session_mgr.request_entry(sig, sig.timestamp):
                    engine = self.engines[sig.strategy_name]
                    start_idx = df_1m.index.get_loc(sig.timestamp)
                    
                    trade = _simulate_single_trade_with_session_check(engine, sig, df_1m, start_idx)
                    
                    self.session_mgr.record_trade_result(trade)
                    combined_trades.append(trade)
                    
            self.account_mgr.on_session_close(self.session_mgr.state.session_pnl)
            session_summaries.append(self.session_mgr.get_session_summary())
            
            if self.account_mgr.has_passed_eval() and days_to_pass is None:
                days_to_pass = self.account_mgr.state.days_traded
                break
                
            if self.account_mgr.state.is_blown:
                break
                
        # To compute per-strategy results accurately, we separate them
        strat_trades = {name: [] for name in strategy_signals.keys()}
        for t in combined_trades:
            strat_trades[t.signal.strategy_name].append(t)
            
        per_strat_results = {}
        for name, trades_list in strat_trades.items():
            engine = getattr(self, "engines", {}).get(name, BacktestEngine(self.config))
            m, eq, d = engine._compute_metrics(trades_list)
            per_strat_results[name] = BacktestResult(trades=trades_list, equity_curve=eq, daily_pnl=d, metrics=m)
            
        # Overall portfolio metrics
        temp_engine = BacktestEngine(self.config)
        _, overall_eq, overall_d_pnl = temp_engine._compute_metrics(combined_trades)

        # Offset the equity curve to start at the account's starting balance rather than zero. 
        if not overall_eq.empty:
            overall_eq += self.config.account_risk.starting_equity

        return PortfolioResult(
            per_strategy_results=per_strat_results,
            combined_trades=combined_trades,
            combined_equity_curve=overall_eq,
            combined_daily_pnl=overall_d_pnl,
            session_summaries=session_summaries,
            account_summary=self.account_mgr.get_account_summary(),
            prop_eval_passed=self.account_mgr.has_passed_eval(),
            days_to_pass=days_to_pass
        )
