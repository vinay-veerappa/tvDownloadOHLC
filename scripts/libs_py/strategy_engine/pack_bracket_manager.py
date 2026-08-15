"""
========================================================================================
Pack Bracket Manager: 2-Contract Scale-Out & Breakeven Lock Engine
========================================================================================
A reusable quantitative trade-management module implementing the institutional
2-Contract "Pack Trading" architecture:

Core Mechanics:
---------------
1. Contract 1 (The Queen):
   - Targets an empirical high-probability quick scale-out (default: 10 Basis Points).
   - Once Queen fills, position risk drops to zero.
2. Breakeven Stop Lock:
   - Upon Queen fill, the stop loss on Contract 2 is immediately moved to the exact
     Entry Price (Breakeven).
3. Contract 2 (The Runner):
   - Rides the remaining position to full intraday expansion targets (30-60 bps).
   - Generates asymmetric payoff ratio (> 2.5:1).
========================================================================================
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import numpy as np

@dataclass
class PackPosition:
    direction: int              # +1 for Long, -1 for Short
    entry_price: float
    entry_time: any
    entry_bar: int
    orig_stop_loss: float
    cur_stop_loss: float
    queen_target: float
    runner_target: float
    queen_filled: bool = False
    max_mfe_pts: float = 0.0
    max_mae_pts: float = 0.0

@dataclass
class PackExitResult:
    trade_id: int
    direction: int
    entry_time: any
    exit_time: any
    entry_price: float
    queen_filled: bool
    exit_reason: str            # "STOP_LOSS", "BREAKEVEN", "RUNNER_TARGET", "EOD"
    net_pnl_pts: float
    net_pnl_usd: float
    mfe_pts: float
    mae_pts: float
    bars_held: int

class PackBracketManager:
    """
    Universal 2-Contract Pack Scale-Out & Risk Manager.
    """
    def __init__(
        self,
        queen_bps: float = 10.0,
        runner_bps: float = 40.0,
        runner_pm_bps: float = 60.0,
        point_value: float = 2.0,
        comm_per_contract: float = 0.52,
        tick_size: float = 0.25,
    ):
        self.queen_bps = queen_bps
        self.runner_bps = runner_bps
        self.runner_pm_bps = runner_pm_bps
        self.point_value = point_value
        self.comm_per_contract = comm_per_contract
        self.tick_size = tick_size

        self.active_position: Optional[PackPosition] = None
        self.completed_trades = []
        self.trade_counter = 0

    def calc_bps_distance(self, price: float, bps: float) -> float:
        dist = price * (bps / 10000.0)
        return round(dist / self.tick_size) * self.tick_size

    def open_pack(
        self,
        direction: int,
        entry_price: float,
        stop_loss: float,
        bar_idx: int,
        bar_time: any,
        is_pm_macro: bool = False,
    ) -> PackPosition:
        """
        Opens a 2-contract Pack position.
        """
        runner_target_bps = self.runner_pm_bps if is_pm_macro else self.runner_bps

        dist_queen = self.calc_bps_distance(entry_price, self.queen_bps)
        dist_runner = self.calc_bps_distance(entry_price, runner_target_bps)

        if direction == 1:
            queen_tp = entry_price + dist_queen
            runner_tp = entry_price + dist_runner
        else:
            queen_tp = entry_price - dist_queen
            runner_tp = entry_price - dist_runner

        self.active_position = PackPosition(
            direction=direction,
            entry_price=entry_price,
            entry_time=bar_time,
            entry_bar=bar_idx,
            orig_stop_loss=stop_loss,
            cur_stop_loss=stop_loss,
            queen_target=queen_tp,
            runner_target=runner_tp,
            queen_filled=False,
            max_mfe_pts=0.0,
            max_mae_pts=0.0,
        )
        return self.active_position

    def update_bar(
        self,
        bar_idx: int,
        bar_time: any,
        high: float,
        low: float,
        close: float,
        is_eod_bar: bool = False,
    ) -> Optional[PackExitResult]:
        """
        Evaluates position state, Queen scale-outs, BE stops, and Runner exits.
        Returns PackExitResult upon full position closure.
        """
        pos = self.active_position
        if pos is None:
            return None

        # Track Intrabar MAE/MFE
        if pos.direction == 1:
            cur_fav = high - pos.entry_price
            cur_adv = pos.entry_price - low
        else:
            cur_fav = pos.entry_price - low
            cur_adv = high - pos.entry_price

        pos.max_mfe_pts = max(pos.max_mfe_pts, cur_fav)
        pos.max_mae_pts = max(pos.max_mae_pts, cur_adv)

        # 1. EOD Flatten
        if is_eod_bar:
            if not pos.queen_filled:
                q_pnl = (close - pos.entry_price) * pos.direction
                r_pnl = (close - pos.entry_price) * pos.direction
            else:
                q_pnl = (pos.queen_target - pos.entry_price) * pos.direction
                r_pnl = (close - pos.entry_price) * pos.direction

            total_pts = q_pnl + r_pnl
            total_usd = (total_pts * self.point_value) - (4 * self.comm_per_contract)
            self.trade_counter += 1

            res = PackExitResult(
                trade_id=self.trade_counter,
                direction=pos.direction,
                entry_time=pos.entry_time,
                exit_time=bar_time,
                entry_price=pos.entry_price,
                queen_filled=pos.queen_filled,
                exit_reason="EOD",
                net_pnl_pts=total_pts,
                net_pnl_usd=total_usd,
                mfe_pts=pos.max_mfe_pts,
                mae_pts=pos.max_mae_pts,
                bars_held=bar_idx - pos.entry_bar,
            )
            self.active_position = None
            self.completed_trades.append(res)
            return res

        # 2. Long Position Evaluation
        if pos.direction == 1:
            # Stop Loss / Breakeven Hit
            if low <= pos.cur_stop_loss:
                if not pos.queen_filled:
                    q_pnl = -(pos.entry_price - pos.orig_stop_loss)
                    r_pnl = -(pos.entry_price - pos.orig_stop_loss)
                    reason = "STOP_LOSS"
                else:
                    q_pnl = (pos.queen_target - pos.entry_price)
                    r_pnl = 0.0  # Stopped at Breakeven
                    reason = "BREAKEVEN"

                total_pts = q_pnl + r_pnl
                total_usd = (total_pts * self.point_value) - (4 * self.comm_per_contract)
                self.trade_counter += 1

                res = PackExitResult(
                    trade_id=self.trade_counter,
                    direction=1,
                    entry_time=pos.entry_time,
                    exit_time=bar_time,
                    entry_price=pos.entry_price,
                    queen_filled=pos.queen_filled,
                    exit_reason=reason,
                    net_pnl_pts=total_pts,
                    net_pnl_usd=total_usd,
                    mfe_pts=pos.max_mfe_pts,
                    mae_pts=pos.max_mae_pts,
                    bars_held=bar_idx - pos.entry_bar,
                )
                self.active_position = None
                self.completed_trades.append(res)
                return res

            # Queen TP1 Hit -> Move Stop to Breakeven
            if not pos.queen_filled and high >= pos.queen_target:
                pos.queen_filled = True
                pos.cur_stop_loss = pos.entry_price  # Locked to Breakeven!

            # Runner TP2 Hit
            if high >= pos.runner_target:
                q_pnl = (pos.queen_target - pos.entry_price)
                r_pnl = (pos.runner_target - pos.entry_price)
                total_pts = q_pnl + r_pnl
                total_usd = (total_pts * self.point_value) - (4 * self.comm_per_contract)
                self.trade_counter += 1

                res = PackExitResult(
                    trade_id=self.trade_counter,
                    direction=1,
                    entry_time=pos.entry_time,
                    exit_time=bar_time,
                    entry_price=pos.entry_price,
                    queen_filled=True,
                    exit_reason="RUNNER_TARGET",
                    net_pnl_pts=total_pts,
                    net_pnl_usd=total_usd,
                    mfe_pts=pos.max_mfe_pts,
                    mae_pts=pos.max_mae_pts,
                    bars_held=bar_idx - pos.entry_bar,
                )
                self.active_position = None
                self.completed_trades.append(res)
                return res

        # 3. Short Position Evaluation
        elif pos.direction == -1:
            # Stop Loss / Breakeven Hit
            if high >= pos.cur_stop_loss:
                if not pos.queen_filled:
                    q_pnl = -(pos.orig_stop_loss - pos.entry_price)
                    r_pnl = -(pos.orig_stop_loss - pos.entry_price)
                    reason = "STOP_LOSS"
                else:
                    q_pnl = (pos.entry_price - pos.queen_target)
                    r_pnl = 0.0
                    reason = "BREAKEVEN"

                total_pts = q_pnl + r_pnl
                total_usd = (total_pts * self.point_value) - (4 * self.comm_per_contract)
                self.trade_counter += 1

                res = PackExitResult(
                    trade_id=self.trade_counter,
                    direction=-1,
                    entry_time=pos.entry_time,
                    exit_time=bar_time,
                    entry_price=pos.entry_price,
                    queen_filled=pos.queen_filled,
                    exit_reason=reason,
                    net_pnl_pts=total_pts,
                    net_pnl_usd=total_usd,
                    mfe_pts=pos.max_mfe_pts,
                    mae_pts=pos.max_mae_pts,
                    bars_held=bar_idx - pos.entry_bar,
                )
                self.active_position = None
                self.completed_trades.append(res)
                return res

            # Queen TP1 Hit
            if not pos.queen_filled and low <= pos.queen_target:
                pos.queen_filled = True
                pos.cur_stop_loss = pos.entry_price

            # Runner TP2 Hit
            if low <= pos.runner_target:
                q_pnl = (pos.entry_price - pos.queen_target)
                r_pnl = (pos.entry_price - pos.runner_target)
                total_pts = q_pnl + r_pnl
                total_usd = (total_pts * self.point_value) - (4 * self.comm_per_contract)
                self.trade_counter += 1

                res = PackExitResult(
                    trade_id=self.trade_counter,
                    direction=-1,
                    entry_time=pos.entry_time,
                    exit_time=bar_time,
                    entry_price=pos.entry_price,
                    queen_filled=True,
                    exit_reason="RUNNER_TARGET",
                    net_pnl_pts=total_pts,
                    net_pnl_usd=total_usd,
                    mfe_pts=pos.max_mfe_pts,
                    mae_pts=pos.max_mae_pts,
                    bars_held=bar_idx - pos.entry_bar,
                )
                self.active_position = None
                self.completed_trades.append(res)
                return res

        return None
