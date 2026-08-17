"""
Confluence Backtester Engine
Simulates and evaluates trading strategies combining:
- Range Probability (Opening Decile Empirical Transition Edge)
- Pack Group Quarters Theory (Q1/Q2/Q3 Entry Timing & Valid H/L Sweeps)
- Candle Science (Directional Drift, State Vector Alignment, and Anti-Doji Filters)
"""

from typing import Dict, List, Optional, Any, Union
import numpy as np
import pandas as pd


class ConfluenceBacktester:
    def __init__(
        self,
        min_prob: float = 70.0,
        min_resolve_rate: float = 40.0,
        min_sample_size: int = 10,
        entry_timing: str = "range_open",  # 'range_open', 'q2_sweep_entry', 'q3_distribution_entry'
        cs_filter_mode: str = "none",     # 'none', 'directional_agreement', 'expansion_only', 'full_confluence'
        cs_threshold: float = 55.0,
        target_mode: str = "range_close", # 'range_close', 'prior_boundary', 'fixed_rr'
        risk_reward: float = 1.5,
        stop_mode: str = "prior_opposite",# 'prior_opposite', 'prior_midpoint', 'q1_extreme', 'fixed_pts'
        fixed_stop_pts: float = 20.0,
        point_value: float = 20.0,        # NQ=$20/pt, ES=$50/pt, YM=$5/pt, RTY=$50/pt, CL=$1000/pt, GC=$100/pt
        slippage_pts: float = 0.5,
        commission_per_contract: float = 2.0,
        allowed_hours: Optional[List[int]] = None,
    ):
        self.min_prob = min_prob
        self.min_resolve_rate = min_resolve_rate
        self.min_sample_size = min_sample_size
        self.entry_timing = entry_timing
        self.cs_filter_mode = cs_filter_mode
        self.cs_threshold = cs_threshold
        self.target_mode = target_mode
        self.risk_reward = risk_reward
        self.stop_mode = stop_mode
        self.fixed_stop_pts = fixed_stop_pts
        self.point_value = point_value
        self.slippage_pts = slippage_pts
        self.commission_per_contract = commission_per_contract
        self.allowed_hours = allowed_hours

    def run_backtest(self, feature_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Executes backtest over feature dataframe containing Range Prob,
        Quarters Theory, and Candle Science columns.
        """
        df = feature_df.copy().reset_index(drop=True)
        if df.empty:
            return self._empty_result()

        trades = []
        equity = [0.0]
        cumulative_pnl = 0.0

        records = df.to_dict("records")
        for row in records:
            if not row.get("is_adjacent", True) or pd.isna(row.get("open_pos")):
                continue

            prob = row.get("s_prob", 0.0)
            res_rate = row.get("s_res_rate", 0.0)
            n_sample = row.get("s_n", 0)
            direction = row.get("s_dir", "NONE")

            # 1. Base Range Probability Filter
            if pd.isna(prob) or prob < self.min_prob:
                continue
            if pd.isna(res_rate) or res_rate < self.min_resolve_rate:
                continue
            if n_sample < self.min_sample_size:
                continue
            if direction not in ["U", "D"]:
                continue

            # 2. Time-of-Day Hourly Filter (if specified)
            entry_time = row["start_time_ny"]
            if self.allowed_hours is not None and entry_time.hour not in self.allowed_hours:
                continue

            # 3. Candle Science Filter
            cs_bull = row.get("cs_bull_prob", 50.0)
            cs_exp = row.get("cs_expansion_prob", 50.0)

            if self.cs_filter_mode in ["directional_agreement", "full_confluence"]:
                if direction == "U" and cs_bull < self.cs_threshold:
                    continue  # Long vetoed by Candle Science
                elif direction == "D" and cs_bull > (100.0 - self.cs_threshold):
                    continue  # Short vetoed by Candle Science

            if self.cs_filter_mode in ["expansion_only", "full_confluence"]:
                if cs_exp < 55.0:
                    continue  # Inside/outside bar chop veto

            # 4. Pack Group Quarters Theory Entry Timing & Price Selection
            prior_h = row["prior_high"]
            prior_l = row["prior_low"]
            prior_mid = (prior_h + prior_l) / 2.0

            if self.entry_timing == "range_open":
                entry_price = row["open"]
                sim_high = row["high"]
                sim_low = row["low"]
                sim_close = row["close"]
            elif self.entry_timing == "q2_sweep_entry":
                # Only enter if Q2 swept and reclaimed the opposing side
                if direction == "U":
                    if not row.get("q2_bull_sweep", False):
                        continue
                    entry_price = row.get("q2_close", row["open"])
                else:
                    if not row.get("q2_bear_sweep", False):
                        continue
                    entry_price = row.get("q2_close", row["open"])

                # Post-entry movement happens during Q3 and Q4
                q3_h = row.get("q3_high", entry_price)
                q4_h = row.get("q4_high", entry_price)
                q3_l = row.get("q3_low", entry_price)
                q4_l = row.get("q4_low", entry_price)

                sim_high = max(q3_h if not pd.isna(q3_h) else entry_price, q4_h if not pd.isna(q4_h) else entry_price)
                sim_low = min(q3_l if not pd.isna(q3_l) else entry_price, q4_l if not pd.isna(q4_l) else entry_price)
                sim_close = row.get("q4_close", row["close"])
            elif self.entry_timing == "q3_distribution_entry":
                # Enter at the open of Q3 (Minute :30 on 60m range)
                q3_o = row.get("q3_open")
                if pd.isna(q3_o):
                    continue
                entry_price = q3_o

                # Post-entry movement happens during Q3 and Q4
                q3_h = row.get("q3_high", entry_price)
                q4_h = row.get("q4_high", entry_price)
                q3_l = row.get("q3_low", entry_price)
                q4_l = row.get("q4_low", entry_price)

                sim_high = max(q3_h if not pd.isna(q3_h) else entry_price, q4_h if not pd.isna(q4_h) else entry_price)
                sim_low = min(q3_l if not pd.isna(q3_l) else entry_price, q4_l if not pd.isna(q4_l) else entry_price)
                sim_close = row.get("q4_close", row["close"])
            else:
                entry_price = row["open"]
                sim_high = row["high"]
                sim_low = row["low"]
                sim_close = row["close"]

            if pd.isna(entry_price):
                continue

            # 5. Stop Loss & Target Calculation
            if direction == "U":
                trade_side = "LONG"
                # Stop price
                if self.stop_mode == "prior_opposite":
                    stop_price = prior_l
                elif self.stop_mode == "prior_midpoint":
                    stop_price = prior_mid
                elif self.stop_mode == "q1_extreme":
                    q1_l = row.get("q1_low", prior_mid)
                    stop_price = q1_l if not pd.isna(q1_l) else prior_mid
                else:
                    stop_price = entry_price - self.fixed_stop_pts

                # Target price
                if self.target_mode == "prior_boundary":
                    target_price = prior_h
                elif self.target_mode == "fixed_rr":
                    risk = max(5.0, entry_price - stop_price)
                    target_price = entry_price + risk * self.risk_reward
                else:  # 'range_close'
                    target_price = np.inf

                # Sanitize stop
                if stop_price >= entry_price:
                    stop_price = entry_price - 10.0

                # Execution Simulation
                hit_stop = sim_low <= stop_price
                hit_target = sim_high >= target_price if target_price != np.inf else False

                if hit_stop and hit_target:
                    # Conservative collision: assume stopped out first
                    exit_price = stop_price
                    exit_reason = "STOP"
                elif hit_target:
                    exit_price = target_price
                    exit_reason = "TARGET"
                elif hit_stop:
                    exit_price = stop_price
                    exit_reason = "STOP"
                else:
                    exit_price = sim_close
                    exit_reason = "RANGE_CLOSE"

                raw_pts = exit_price - entry_price - (self.slippage_pts * 2.0)
                dollar_pnl = (raw_pts * self.point_value) - self.commission_per_contract

            else:  # direction == "D"
                trade_side = "SHORT"
                # Stop price
                if self.stop_mode == "prior_opposite":
                    stop_price = prior_h
                elif self.stop_mode == "prior_midpoint":
                    stop_price = prior_mid
                elif self.stop_mode == "q1_extreme":
                    q1_h = row.get("q1_high", prior_mid)
                    stop_price = q1_h if not pd.isna(q1_h) else prior_mid
                else:
                    stop_price = entry_price + self.fixed_stop_pts

                # Target price
                if self.target_mode == "prior_boundary":
                    target_price = prior_l
                elif self.target_mode == "fixed_rr":
                    risk = max(5.0, stop_price - entry_price)
                    target_price = entry_price - risk * self.risk_reward
                else:  # 'range_close'
                    target_price = -np.inf

                # Sanitize stop
                if stop_price <= entry_price:
                    stop_price = entry_price + 10.0

                # Execution Simulation
                hit_stop = sim_high >= stop_price
                hit_target = sim_low <= target_price if target_price != -np.inf else False

                if hit_stop and hit_target:
                    exit_price = stop_price
                    exit_reason = "STOP"
                elif hit_target:
                    exit_price = target_price
                    exit_reason = "TARGET"
                elif hit_stop:
                    exit_price = stop_price
                    exit_reason = "STOP"
                else:
                    exit_price = sim_close
                    exit_reason = "RANGE_CLOSE"

                raw_pts = entry_price - exit_price - (self.slippage_pts * 2.0)
                dollar_pnl = (raw_pts * self.point_value) - self.commission_per_contract

            cumulative_pnl += dollar_pnl
            equity.append(cumulative_pnl)

            trades.append({
                "entry_time": entry_time,
                "side": trade_side,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "pts_pnl": raw_pts,
                "dollar_pnl": dollar_pnl,
                "cum_pnl": cumulative_pnl,
                "prob": prob,
                "res_rate": res_rate,
                "cs_bull": cs_bull,
                "cs_exp": cs_exp,
            })

        return self._compute_performance_metrics(trades, equity)

    def _compute_performance_metrics(self, trades: List[Dict[str, Any]], equity: List[float]) -> Dict[str, Any]:
        if not trades:
            return self._empty_result()

        tdf = pd.DataFrame(trades)
        total_trades = len(tdf)
        winning_trades = len(tdf[tdf["dollar_pnl"] > 0])
        losing_trades = len(tdf[tdf["dollar_pnl"] < 0])
        scratch_trades = total_trades - winning_trades - losing_trades

        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_profit = tdf[tdf["dollar_pnl"] > 0]["dollar_pnl"].sum()
        gross_loss = abs(tdf[tdf["dollar_pnl"] < 0]["dollar_pnl"].sum())

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        net_pnl = tdf["dollar_pnl"].sum()
        avg_trade = net_pnl / total_trades if total_trades > 0 else 0.0

        # Max Drawdown
        eq_arr = np.array(equity)
        peak = np.maximum.accumulate(eq_arr)
        drawdown = peak - eq_arr
        max_drawdown = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        # Sharpe Ratio
        pnl_std = tdf["dollar_pnl"].std()
        sharpe = float((avg_trade / pnl_std * np.sqrt(252 * 6.5))) if pnl_std > 0 else 0.0

        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "net_pnl": round(net_pnl, 2),
            "avg_trade": round(avg_trade, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 2),
            "trades_df": tdf,
        }

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "net_pnl": 0.0,
            "avg_trade": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "trades_df": pd.DataFrame(),
        }
