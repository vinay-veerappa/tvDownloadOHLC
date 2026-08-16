"""
Three-Tier Institutional Pack Bracket Manager (Queen + Expansion + Runner)

Manages a 3-contract (or 3-tier) institutional execution bracket:
- Tier 1 (The Queen): Quick derisk at 8-10 bps (covers commissions + initial profit).
  -> Once filled: Moves Tier 2 & Tier 3 stop to Breakeven (+2 ticks).
- Tier 2 (Main Expansion): High-probability draw on liquidity at 25-35 bps (~50-70 pts).
  -> Once filled: Locks Tier 3 stop at Tier 1 profit level (+10 bps).
- Tier 3 (The Runner): Fat-tail asymmetrical expansion to opposing 1H liquidity (60-80 bps).
  -> Trailing: Dynamically trails under/over 5m swing structure.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TierTargetState:
    direction: int
    entry_price: float
    orig_sl: float
    cur_sl: float
    tp1_queen: float
    tp2_expansion: float
    tp3_runner: float
    qty_tier1: int = 1
    qty_tier2: int = 1
    qty_tier3: int = 1
    tp1_filled: bool = False
    tp2_filled: bool = False
    tp3_filled: bool = False
    entry_time: Optional[object] = None
    entry_bar: int = 0
    sweep_level: str = ""


class ThreeTierPackManager:
    """
    Modular 3-Tier Bracket Engine for institutional multi-contract execution.
    """

    def __init__(
        self,
        queen_bps: float = 10.0,
        expansion_bps: float = 30.0,
        runner_bps: float = 60.0,
        point_value: float = 2.0,
        comm_per_contract: float = 0.52,
        tick_size: float = 0.25,
    ):
        self.queen_bps = queen_bps
        self.expansion_bps = expansion_bps
        self.runner_bps = runner_bps
        self.point_value = point_value
        self.comm_per_contract = comm_per_contract
        self.tick_size = tick_size

    def calculate_pack_levels(
        self,
        direction: int,
        entry_price: float,
        stop_price: float,
        entry_time: object = None,
        entry_bar: int = 0,
        sweep_level: str = "",
        custom_expansion_bps: Optional[float] = None,
        custom_runner_bps: Optional[float] = None,
    ) -> TierTargetState:
        """
        Calculates exact TP1, TP2, and TP3 price levels for a new trade.
        """
        exp_bps = custom_expansion_bps if custom_expansion_bps is not None else self.expansion_bps
        run_bps = custom_runner_bps if custom_runner_bps is not None else self.runner_bps

        dist_tp1 = entry_price * (self.queen_bps / 10000.0)
        dist_tp2 = entry_price * (exp_bps / 10000.0)
        dist_tp3 = entry_price * (run_bps / 10000.0)

        # Round to nearest quarter tick
        dist_tp1 = round(dist_tp1 * 4) / 4.0
        dist_tp2 = round(dist_tp2 * 4) / 4.0
        dist_tp3 = round(dist_tp3 * 4) / 4.0

        if direction == 1:
            tp1 = entry_price + dist_tp1
            tp2 = entry_price + dist_tp2
            tp3 = entry_price + dist_tp3
        else:
            tp1 = entry_price - dist_tp1
            tp2 = entry_price - dist_tp2
            tp3 = entry_price - dist_tp3

        return TierTargetState(
            direction=direction,
            entry_price=entry_price,
            orig_sl=stop_price,
            cur_sl=stop_price,
            tp1_queen=tp1,
            tp2_expansion=tp2,
            tp3_runner=tp3,
            entry_time=entry_time,
            entry_bar=entry_bar,
            sweep_level=sweep_level,
        )

    def update_bar(
        self,
        state: TierTargetState,
        high: float,
        low: float,
        close: float,
        is_eod: bool = False,
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Processes bar price action against the 3-Tier Pack.
        Returns: (is_closed, trade_summary_dict)
        """
        dir_ = state.direction
        e_price = state.entry_price
        orig_sl = state.orig_sl

        # 1. EOD Session Close (15:55 ET)
        if is_eod:
            tot_contracts = state.qty_tier1 + state.qty_tier2 + state.qty_tier3
            pnl_1 = (state.tp1_queen - e_price) * dir_ if state.tp1_filled else (close - e_price) * dir_
            pnl_2 = (state.tp2_expansion - e_price) * dir_ if state.tp2_filled else (close - e_price) * dir_
            pnl_3 = (close - e_price) * dir_
            total_usd = (pnl_1 + pnl_2 + pnl_3) * self.point_value - (2 * tot_contracts * self.comm_per_contract)
            return True, {
                "exit_reason": "EOD",
                "net_pnl": total_usd,
                "pnl_points": (pnl_1 + pnl_2 + pnl_3),
                "tp1_hit": state.tp1_filled,
                "tp2_hit": state.tp2_filled,
                "tp3_hit": False,
            }

        # 2. Long Position Lifecycle
        if dir_ == 1:
            # Stop Loss Hit
            if low <= state.cur_sl:
                exit_price = state.cur_sl
                tot_contracts = state.qty_tier1 + state.qty_tier2 + state.qty_tier3
                pnl_1 = (state.tp1_queen - e_price) * state.qty_tier1 if state.tp1_filled else (exit_price - e_price) * state.qty_tier1
                pnl_2 = (state.tp2_expansion - e_price) * state.qty_tier2 if state.tp2_filled else (exit_price - e_price) * state.qty_tier2
                pnl_3 = (exit_price - e_price) * state.qty_tier3
                total_usd = (pnl_1 + pnl_2 + pnl_3) * self.point_value - (2 * tot_contracts * self.comm_per_contract)
                reason = "STOP_LOSS" if not state.tp1_filled else ("LOCKED_PROFIT" if state.tp2_filled else "BREAKEVEN")
                return True, {
                    "exit_reason": reason,
                    "net_pnl": total_usd,
                    "pnl_points": (pnl_1 + pnl_2 + pnl_3),
                    "tp1_hit": state.tp1_filled,
                    "tp2_hit": state.tp2_filled,
                    "tp3_hit": False,
                }

            # Tier 1 (Queen) Hit -> Ratchet Stop to Breakeven
            if not state.tp1_filled and high >= state.tp1_queen:
                state.tp1_filled = True
                state.cur_sl = state.entry_price + (2 * self.tick_size)  # Breakeven + 2 ticks

            # Tier 2 (Expansion) Hit -> Ratchet Stop to Lock Tier 1 Profit (+10 bps)
            if state.tp1_filled and not state.tp2_filled and high >= state.tp2_expansion:
                state.tp2_filled = True
                state.cur_sl = state.tp1_queen  # Lock in +10 bps profit for runner!

            # Tier 3 (Runner) Hit -> Full Pack Target Reached!
            if high >= state.tp3_runner:
                state.tp3_filled = True
                tot_contracts = state.qty_tier1 + state.qty_tier2 + state.qty_tier3
                pnl_1 = (state.tp1_queen - e_price) * state.qty_tier1
                pnl_2 = (state.tp2_expansion - e_price) * state.qty_tier2
                pnl_3 = (state.tp3_runner - e_price) * state.qty_tier3
                total_usd = (pnl_1 + pnl_2 + pnl_3) * self.point_value - (2 * tot_contracts * self.comm_per_contract)
                return True, {
                    "exit_reason": "ALL_TARGETS_HIT",
                    "net_pnl": total_usd,
                    "pnl_points": (pnl_1 + pnl_2 + pnl_3),
                    "tp1_hit": True,
                    "tp2_hit": True,
                    "tp3_hit": True,
                }

        # 3. Short Position Lifecycle
        elif dir_ == -1:
            # Stop Loss Hit
            if high >= state.cur_sl:
                exit_price = state.cur_sl
                tot_contracts = state.qty_tier1 + state.qty_tier2 + state.qty_tier3
                pnl_1 = (e_price - state.tp1_queen) * state.qty_tier1 if state.tp1_filled else (e_price - exit_price) * state.qty_tier1
                pnl_2 = (e_price - state.tp2_expansion) * state.qty_tier2 if state.tp2_filled else (e_price - exit_price) * state.qty_tier2
                pnl_3 = (e_price - exit_price) * state.qty_tier3
                total_usd = (pnl_1 + pnl_2 + pnl_3) * self.point_value - (2 * tot_contracts * self.comm_per_contract)
                reason = "STOP_LOSS" if not state.tp1_filled else ("LOCKED_PROFIT" if state.tp2_filled else "BREAKEVEN")
                return True, {
                    "exit_reason": reason,
                    "net_pnl": total_usd,
                    "pnl_points": (pnl_1 + pnl_2 + pnl_3),
                    "tp1_hit": state.tp1_filled,
                    "tp2_hit": state.tp2_filled,
                    "tp3_hit": False,
                }

            # Tier 1 (Queen) Hit -> Ratchet Stop to Breakeven
            if not state.tp1_filled and low <= state.tp1_queen:
                state.tp1_filled = True
                state.cur_sl = state.entry_price - (2 * self.tick_size)  # Breakeven - 2 ticks

            # Tier 2 (Expansion) Hit -> Ratchet Stop to Lock Tier 1 Profit (+10 bps)
            if state.tp1_filled and not state.tp2_filled and low <= state.tp2_expansion:
                state.tp2_filled = True
                state.cur_sl = state.tp1_queen

            # Tier 3 (Runner) Hit -> Full Pack Target Reached!
            if low <= state.tp3_runner:
                state.tp3_filled = True
                tot_contracts = state.qty_tier1 + state.qty_tier2 + state.qty_tier3
                pnl_1 = (e_price - state.tp1_queen) * state.qty_tier1
                pnl_2 = (e_price - state.tp2_expansion) * state.qty_tier2
                pnl_3 = (e_price - state.tp3_runner) * state.qty_tier3
                total_usd = (pnl_1 + pnl_2 + pnl_3) * self.point_value - (2 * tot_contracts * self.comm_per_contract)
                return True, {
                    "exit_reason": "ALL_TARGETS_HIT",
                    "net_pnl": total_usd,
                    "pnl_points": (pnl_1 + pnl_2 + pnl_3),
                    "tp1_hit": True,
                    "tp2_hit": True,
                    "tp3_hit": True,
                }

        return False, None
