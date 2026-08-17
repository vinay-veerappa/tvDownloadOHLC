"""
Range Probability Backtest Adapter
Provides vectorized and event-driven backtesting engines for Range Probability strategies in Python.
Computes PnL, Win Rate, Profit Factor, Expectancy, Max Drawdown, and Sharpe Ratio.
"""

from typing import Dict, List, Optional, Any, Union
import numpy as np
import pandas as pd


class RangeProbBacktester:
    def __init__(
        self,
        min_prob: float = 70.0,
        min_resolve_rate: float = 40.0,
        min_sample_size: int = 20,
        target_mode: str = "prior_boundary",  # 'prior_boundary', 'fixed_rr', 'range_close'
        risk_reward: float = 2.0,
        stop_mode: str = "prior_midpoint",     # 'prior_midpoint', 'prior_opposite', 'fixed_pts'
        fixed_stop_pts: float = 20.0,
        point_value: float = 20.0,            # NQ = $20/pt, ES = $50/pt, etc.
        slippage_pts: float = 0.5,
        commission_per_contract: float = 2.0,
    ):
        self.min_prob = min_prob
        self.min_resolve_rate = min_resolve_rate
        self.min_sample_size = min_sample_size
        self.target_mode = target_mode
        self.risk_reward = risk_reward
        self.stop_mode = stop_mode
        self.fixed_stop_pts = fixed_stop_pts
        self.point_value = point_value
        self.slippage_pts = slippage_pts
        self.commission_per_contract = commission_per_contract

    def run_backtest(self, feature_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Executes backtest over feature dataframe.
        Each trade is evaluated from range open to range resolution/close.
        """
        df = feature_df.copy().reset_index(drop=True)

        trades = []
        equity = [0.0]
        cumulative_pnl = 0.0

        for i, row in df.iterrows():
            if not row.get("is_adjacent", True) or pd.isna(row.get("open_pos")):
                continue

            prob = row.get("s_prob", 0.0)
            res_rate = row.get("s_res_rate", 0.0)
            n_sample = row.get("s_n", 0)
            direction = row.get("s_dir", "NONE")

            # Filter for qualified statistical edge
            if pd.isna(prob) or prob < self.min_prob:
                continue
            if pd.isna(res_rate) or res_rate < self.min_resolve_rate:
                continue
            if n_sample < self.min_sample_size:
                continue
            if direction not in ["U", "D"]:
                continue

            entry_time = row["start_time_ny"]
            entry_price = row["open"]
            prior_h = row["prior_high"]
            prior_l = row["prior_low"]
            prior_mid = (prior_h + prior_l) / 2.0
            range_h = row["high"]
            range_l = row["low"]
            range_c = row["close"]

            if direction == "U":
                # Long Trade
                trade_side = "LONG"
                target_price = prior_h if self.target_mode == "prior_boundary" else entry_price + (entry_price - prior_mid) * self.risk_reward

                if self.stop_mode == "prior_midpoint":
                    stop_price = prior_mid
                elif self.stop_mode == "prior_opposite":
                    stop_price = prior_l
                else:
                    stop_price = entry_price - self.fixed_stop_pts

                # Simulate execution during range bar
                # 1. Did price hit target?
                hit_target = range_h >= target_price
                # 2. Did price hit stop?
                hit_stop = range_l <= stop_price

                if hit_target and not hit_stop:
                    exit_price = target_price
                    exit_reason = "TARGET"
                elif hit_stop and not hit_target:
                    exit_price = stop_price
                    exit_reason = "STOP"
                elif hit_target and hit_stop:
                    # Intrabar collision: pessimistic assumption -> STOP first
                    exit_price = stop_price
                    exit_reason = "STOP_COLLISION"
                else:
                    # Exited at range close
                    exit_price = range_c
                    exit_reason = "RANGE_CLOSE"

                points = exit_price - entry_price - self.slippage_pts
                gross_pnl = points * self.point_value
                net_pnl = gross_pnl - self.commission_per_contract

            else:
                # Short Trade
                trade_side = "SHORT"
                target_price = prior_l if self.target_mode == "prior_boundary" else entry_price - (prior_mid - entry_price) * self.risk_reward

                if self.stop_mode == "prior_midpoint":
                    stop_price = prior_mid
                elif self.stop_mode == "prior_opposite":
                    stop_price = prior_h
                else:
                    stop_price = entry_price + self.fixed_stop_pts

                hit_target = range_l <= target_price
                hit_stop = range_h >= stop_price

                if hit_target and not hit_stop:
                    exit_price = target_price
                    exit_reason = "TARGET"
                elif hit_stop and not hit_target:
                    exit_price = stop_price
                    exit_reason = "STOP"
                elif hit_target and hit_stop:
                    exit_price = stop_price
                    exit_reason = "STOP_COLLISION"
                else:
                    exit_price = range_c
                    exit_reason = "RANGE_CLOSE"

                points = entry_price - exit_price - self.slippage_pts
                gross_pnl = points * self.point_value
                net_pnl = gross_pnl - self.commission_per_contract

            cumulative_pnl += net_pnl
            equity.append(cumulative_pnl)

            trade_record = {
                "trade_idx": len(trades) + 1,
                "time": entry_time,
                "slot": row["slot"],
                "bucket": row["bucket"],
                "bucket_name": row["bucket_name"],
                "side": trade_side,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "target_price": target_price,
                "stop_price": stop_price,
                "exit_reason": exit_reason,
                "points": round(points, 2),
                "net_pnl": round(net_pnl, 2),
                "cum_pnl": round(cumulative_pnl, 2),
                "is_win": net_pnl > 0,
                "edge_prob": prob,
                "edge_res": res_rate,
                "sample_size": n_sample,
            }
            trades.append(trade_record)

        # Performance summary metrics
        trades_df = pd.DataFrame(trades)
        if len(trades_df) == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "net_profit": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "trades": trades_df,
            }

        wins = trades_df[trades_df["net_pnl"] > 0]
        losses = trades_df[trades_df["net_pnl"] <= 0]

        total_gain = wins["net_pnl"].sum()
        total_loss = abs(losses["net_pnl"].sum())
        profit_factor = (total_gain / total_loss) if total_loss > 0 else np.nan

        # Drawdown computation
        eq_series = pd.Series(equity)
        peak = eq_series.cummax()
        drawdown = peak - eq_series
        max_dd = drawdown.max()

        # Sharpe ratio (annualized per trade)
        pnl_series = trades_df["net_pnl"]
        sharpe = (pnl_series.mean() / pnl_series.std() * np.sqrt(252 * 4)) if pnl_series.std() > 0 else 0.0

        return {
            "total_trades": len(trades_df),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(trades_df) * 100.0, 1),
            "net_profit": round(cumulative_pnl, 2),
            "gross_profit": round(total_gain, 2),
            "gross_loss": round(total_loss, 2),
            "profit_factor": round(profit_factor, 2) if not pd.isna(profit_factor) else 99.0,
            "avg_trade_pnl": round(trades_df["net_pnl"].mean(), 2),
            "avg_win": round(wins["net_pnl"].mean(), 2) if len(wins) > 0 else 0.0,
            "avg_loss": round(losses["net_pnl"].mean(), 2) if len(losses) > 0 else 0.0,
            "max_drawdown": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "trades": trades_df,
        }
