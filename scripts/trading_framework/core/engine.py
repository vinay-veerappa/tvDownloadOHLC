"""
Core backtest engine. Processes signals through trade management.

Active in "strategy" and "portfolio" risk modes.
"""
from dataclasses import dataclass
import pandas as pd
import numpy as np

from scripts.libs.risk.risk_config import Signal, TradeRecord, TradeStatus, TradeDirection
from scripts.libs.risk.trade_policies import get_policy, PolicyAction
from scripts.trading_framework.core.execution import apply_slippage, compute_commission, compute_pnl


@dataclass
class BacktestResult:
    trades: list[TradeRecord]
    equity_curve: pd.Series          # Cumulative P&L over time
    daily_pnl: pd.Series             # Daily P&L
    metrics: dict                     # Summary statistics


class BacktestEngine:
    def __init__(self, config):
        self.config = config
        
        policy_name = getattr(config, "trade_risk_policy", "fixed_target")
        policy_params = getattr(config, "trade_risk_policies", {}).get(policy_name, {})
        self.policy = get_policy(policy_name, policy_params)
        
    def run(self, signals: list[Signal], df_1m: pd.DataFrame) -> BacktestResult:
        trades = []
        
        symbol_data = getattr(self.config.execution, "tick_size", {"MES": 0.25})
        pt_values = getattr(self.config.execution, "point_value", {"MES": 5.0})
        slippage_ticks = getattr(self.config.execution, "slippage_ticks", 1)
        commission = getattr(self.config.execution, "commission_per_contract", 0.62)
        default_contracts = getattr(self.config.execution, "default_contracts", 1)
        flatten_time = pd.to_datetime(self.config.sessions.flatten_by).time()
        
        # Sort signals chronologically
        signals = sorted(signals, key=lambda x: x.timestamp)
        
        for sig in signals:
            if sig.timestamp not in df_1m.index:
                continue
                
            tick_size = symbol_data.get(sig.symbol, 0.25)
            pt_value = pt_values.get(sig.symbol, 5.0)
            
            # 1. Apply entry slippage
            entry_fill = apply_slippage(sig.entry_price, sig.direction, tick_size, slippage_ticks, is_entry=True)
            
            # 2. Create trade
            trade = TradeRecord(
                signal=sig, status=TradeStatus.OPEN,
                entry_time=sig.timestamp, entry_fill_price=entry_fill,
                policy_name=self.config.trade_risk_policy
            )
            
            # Find integer location of entry bar to walk forward
            start_idx = df_1m.index.get_loc(sig.timestamp)
            current_contracts = default_contracts
            
            self.policy.reset()
            
            max_bars = len(df_1m)
            
            # 3. Walk forward
            for step, i in enumerate(range(start_idx, max_bars)):
                current_time = df_1m.index[i]
                bar = df_1m.iloc[i].to_dict()
                
                # Check forced flatten by EOD
                if current_time.time() >= flatten_time:
                    trade.exit_time = current_time
                    trade.exit_fill_price = apply_slippage(bar["close"], sig.direction, tick_size, slippage_ticks, is_entry=False)
                    trade.exit_reason = "flatten"
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
                    
                decision = self.policy.manage(trade, bar, step)
                
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
            
            trade.bars_in_trade = step
            
            # Pnl Computation
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
                trade.realized_pnl = 0.0 # Never closed correctly
                
            trades.append(trade)
            
        metrics, eq, d_pnl = self._compute_metrics(trades)
        return BacktestResult(trades=trades, equity_curve=eq, daily_pnl=d_pnl, metrics=metrics)
        
    def _compute_metrics(self, trades: list[TradeRecord]):
        if not trades:
            return {}, pd.Series(), pd.Series()
            
        pnls = [t.realized_pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses)) if losses else 0.0001
        
        df_trades = pd.DataFrame([{"time": t.entry_time, "pnl": t.realized_pnl} for t in trades if t.entry_time])
        df_trades.set_index("time", inplace=True)
        cur = df_trades["pnl"].cumsum()
        daily = df_trades["pnl"].resample('D').sum().dropna()
        daily = daily[daily != 0]

        metrics = {
            "total_pnl": sum(pnls),
            "trade_count": len(trades),
            "win_rate": len(wins) / max(1, len(trades)),
            "profit_factor": gross_profit / gross_loss,
            "avg_win": sum(wins)/len(wins) if wins else 0,
            "avg_loss": sum(losses)/len(losses) if losses else 0
        }
        return metrics, cur, daily
