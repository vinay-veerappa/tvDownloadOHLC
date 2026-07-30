import pandas as pd
import numpy as np
import argparse
import json
from datetime import datetime, time
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from pathlib import Path

"""
parity_check_v2.py
Resolves NT8 SA vs Python discrepancy for ORB strategy family.

Key Fixes based on Empirical Tracer:
- H3 (Dominant): Implements strict RTH filtering (09:30-16:00 ET) via tz_convert.
- H1 (Secondary): Added --entry-mode (bar_close vs next_open) to quantify slippage.
- H2 (Isolation): Added --fill-mode (bar_close vs intra_bar_high_low) to isolate stop/target fill discrepancy.
- H6 (Structural): Single-exit model used for parity baseline; flagged if NT8 uses multi-TP.
- ADR-017: Vectorized logic where possible, pandas-based simulation.
- ADR-020: EOD liquidation uses explicit 15:59 ET bar close instead of last index.
- ADR-001: tz_convert performed before date filtering to preserve session boundaries.
- Edge Cases: Same-bar stop+target tie-break detection, next_open at last bar fallback, missing bar gap detection.
"""

class Trade:
    def __init__(self, entry_time, entry_price, exit_time, exit_price, side, pnl, pnl_pct):
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.side = side
        self.pnl = pnl
        self.pnl_pct = pnl_pct

    def to_dict(self):
        return self.__dict__

class ParityStrategy(ABC):
    @abstractmethod
    def simulate(self, df: pd.DataFrame, params: Dict[str, Any]) -> List[Trade]:
        pass

    @property
    @abstractmethod
    def expected_nt8_strategy_name(self) -> str:
        pass

class ORBStrategy(ParityStrategy):
    """Opening Range Breakout Implementation"""
    @property
    def expected_nt8_strategy_name(self) -> str:
        return "ORB_AllDay_MultiTP"

    def simulate(self, df: pd.DataFrame, params: Dict[str, Any]) -> List[Trade]:
        # Parameters
        or_duration = params.get('or_duration', 30)
        target_r = params.get('target_r', 2.0)
        entry_mode = params.get('entry_mode', 'bar_close')
        fill_mode = params.get('fill_mode', 'intra_bar_high_low')  # H2 isolation
        comm_rt = params.get('commission_rt', 0.0)
        slip_ticks = params.get('slippage_ticks', 0)
        tick_size = 0.25  # Standard NQ tick

        # 1. Define OR Window (9:30 to 9:30 + duration)
        df = df.sort_index()
        rth_start = time(9, 30)
        rth_end = time(15, 59)  # ADR-020: exclude 16:00 bar
        eod_liquidation_time = time(15, 59)  # ADR-020: explicit 15:59 ET bar close

        # Filter for RTH only (H3 Fix)
        df_rth = df.between_time(rth_start, rth_end).copy()
        if df_rth.empty:
            return []

        # Check for missing bars in the OR window (edge case)
        self._check_bar_gaps(df_rth, "RTH session")

        # Identify OR Range
        or_start_time = df_rth.index[0]
        # Use duration to find the bar where OR closes
        or_end_idx = df_rth.index.get_loc(or_start_time) + or_duration
        if or_end_idx >= len(df_rth):
            return []
        
        or_data = df_rth.iloc[:or_end_idx]
        or_high = or_data['high'].max()
        or_low = or_data['low'].min()
        risk = or_high - or_low

        if risk <= 0:
            print("Warning: Zero-range OR encountered. Skipping day.")
            return []

        # 2. Trading Window (Post-OR until 15:59)
        trading_df = df_rth.iloc[or_end_idx:].copy()
        
        trades = []
        position = None  # None, 'long', 'short'
        entry_price = 0.0
        entry_time = None
        stop = 0.0
        target = 0.0
        same_bar_ambiguity_count = 0  # H2 tie-break counter

        for i in range(len(trading_df)):
            bar = trading_df.iloc[i]
            current_time = trading_df.index[i]

            if position is None:
                # Entry Logic
                triggered = False
                if bar['close'] > or_high:
                    side = 'long'
                    triggered = True
                elif bar['close'] < or_low:
                    side = 'short'
                    triggered = True
                
                if triggered:
                    # Determine entry price and time
                    if entry_mode == 'next_open':
                        if i + 1 < len(trading_df):
                            entry_price = trading_df.iloc[i+1]['open']
                            entry_time = trading_df.index[i+1]
                        else:
                            # Edge case: trigger on last bar, no next bar
                            print(f"Warning: next_open triggered on last bar at {current_time}. Skipping trade to avoid mismatch.")
                            continue  # skip this trade
                    else:
                        entry_price = bar['close']
                        entry_time = current_time
                    
                    # Guard against zero entry price (edge case fix)
                    if entry_price == 0:
                        print(f"Warning: Zero entry price at {entry_time}. Skipping trade.")
                        continue
                    
                    # Apply slippage
                    if side == 'long':
                        entry_price += (slip_ticks * tick_size)
                        stop = or_low
                        target = entry_price + (risk * target_r)
                    else:  # short
                        entry_price -= (slip_ticks * tick_size)
                        stop = or_high
                        target = entry_price - (risk * target_r)
                    
                    position = side
                else:
                    continue
            else:
                # Exit Logic
                exit_price = None
                exit_time = None
                
                # Check for target/stop hit based on fill_mode (H2 isolation)
                if fill_mode == 'intra_bar_high_low':
                    if position == 'long':
                        hit_target = bar['high'] >= target
                        hit_stop = bar['low'] <= stop
                        if hit_target and hit_stop:
                            same_bar_ambiguity_count += 1
                            print(f"Warning: Same-bar stop+target tie-break at {current_time}. Exiting at target (first check).")
                            exit_price, exit_time = target, current_time
                        elif hit_target:
                            exit_price, exit_time = target, current_time
                        elif hit_stop:
                            exit_price, exit_time = stop, current_time
                    else:  # short
                        hit_target = bar['low'] <= target
                        hit_stop = bar['high'] >= stop
                        if hit_target and hit_stop:
                            same_bar_ambiguity_count += 1
                            print(f"Warning: Same-bar stop+target tie-break at {current_time}. Exiting at target (first check).")
                            exit_price, exit_time = target, current_time
                        elif hit_target:
                            exit_price, exit_time = target, current_time
                        elif hit_stop:
                            exit_price, exit_time = stop, current_time
                else:  # bar_close
                    if position == 'long':
                        if bar['close'] >= target:
                            exit_price, exit_time = target, current_time
                        elif bar['close'] <= stop:
                            exit_price, exit_time = stop, current_time
                    else:  # short
                        if bar['close'] <= target:
                            exit_price, exit_time = target, current_time
                        elif bar['close'] >= stop:
                            exit_price, exit_time = stop, current_time
                
                # EOD Liquidation at 15:59 ET (ADR-020)
                if exit_price is None and current_time.time() >= eod_liquidation_time:
                    exit_price, exit_time = bar['close'], current_time

                if exit_price:
                    pnl_raw = (exit_price - entry_price) if position == 'long' else (entry_price - exit_price)
                    pnl_net = pnl_raw - comm_rt
                    pnl_pct = (pnl_net / entry_price) * 100
                    trades.append(Trade(entry_time, entry_price, exit_time, exit_price, position, pnl_net, pnl_pct))
                    position = None
                    entry_price = 0.0
                    entry_time = None
                    stop = 0.0
                    target = 0.0

        if same_bar_ambiguity_count > 0:
            print(f"Parity Flag: {same_bar_ambiguity_count} same-bar stop+target tie-breaks occurred (H2 diagnostic).")

        return trades

    def _check_bar_gaps(self, df: pd.DataFrame, label: str) -> None:
        """Warn if consecutive bars have a gap > 1 minute (missing bars)."""
        if len(df) < 2:
            return
        time_diffs = df.index.to_series().diff().dropna()
        # Convert to seconds
        gap_seconds = time_diffs.dt.total_seconds()
        gaps = gap_seconds[gap_seconds > 90]  # allow 1.5 min tolerance
        if not gaps.empty:
            print(f"Warning: Missing bars detected in {label}. Gaps at indices: {gaps.index[:5].tolist()}")

def load_data(ticker: str, date_str: str) -> pd.DataFrame:
    path = Path(f"data/live/live_storage_-{ticker}.parquet")
    if not path.exists():
        raise FileNotFoundError(f"Data not found at {path}")
    
    df = pd.read_parquet(path)
    # Ensure UTC to America/New_York conversion (H3 Fix)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    # ADR-001: Convert timezone BEFORE filtering by date string
    df.index = df.index.tz_convert('America/New_York')
    
    # Filter for specific date
    df = df.loc[date_str].copy()
    return df

def detect_multi_tp(nt8_trades: List[Dict], py_trades: List[Trade]) -> bool:
    """Check if NT8 has multiple exits from the same entry (multi-TP)."""
    # Group NT8 trades by entry time (within 60s tolerance)
    from collections import defaultdict
    entry_groups = defaultdict(list)
    for nt in nt8_trades:
        nt_time = pd.to_datetime(nt.get('EntryTime', 0))
        # Round to minute to group
        key = nt_time.floor('min')
        entry_groups[key].append(nt)
    
    # Check if any group has more than one trade
    for key, group in entry_groups.items():
        if len(group) > 1:
            # Verify that the exit times differ
            exit_times = [pd.to_datetime(nt.get('ExitTime', 0)) for nt in group]
            if len(set(exit_times)) > 1:
                return True
    return False

def run_parity_check():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="NQ1")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--or-duration", type=int, default=30)
    parser.add_argument("--target-r", type=float, default=2.0)
    parser.add_argument("--entry-mode", choices=['bar_close', 'next_open'], default='bar_close')
    parser.add_argument("--fill-mode", choices=['bar_close', 'intra_bar_high_low'], default='intra_bar_high_low')  # H2 isolation
    parser.add_argument("--commission-rt", type=float, default=2.5)
    parser.add_argument("--slippage-ticks", type=int, default=1)
    parser.add_argument("--nt8-json", required=True)
    args = parser.parse_args()

    # Python Sim
    df = load_data(args.ticker, args.date)
    strat = ORBStrategy()
    params = {
        'or_duration': args.or_duration, 'target_r': args.target_r,
        'entry_mode': args.entry_mode, 'fill_mode': args.fill_mode,
        'commission_rt': args.commission_rt, 'slippage_ticks': args.slippage_ticks
    }
    py_trades = strat.simulate(df, params)

    # Load NT8
    with open(args.nt8_json, 'r') as f:
        nt8_data = json.load(f)
    
    # Handle NT8 JSON schema (Trades vs Results.Trades)
    nt8_trades_raw = nt8_data.get('trades') or nt8_data.get('Results', {}).get('Trades', [])
    
    print(f"\n--- Parity Report: {args.date} | {args.ticker} ---")
    print(f"Python Trades: {len(py_trades)} | NT8 Trades: {len(nt8_trades_raw)}")
    
    if len(py_trades) != len(nt8_trades_raw):
        print("CRITICAL: Trade count mismatch. (H3: Check RTH vs ETH session filters)")
        # H6 detection: check for multi-TP
        if detect_multi_tp(nt8_trades_raw, py_trades):
            print("H6 Flag: NT8 appears to use multiple take-profit levels (Multi-TP) while Python uses single-exit. Consider aligning exit model.")
        else:
            print("H6 Flag: Trade count mismatch not due to multi-TP. Investigate other causes (e.g., entry filters, session boundaries).")

    # Match and Diff
    for pt in py_trades:
        # Find matching NT8 trade (within 60s tolerance)
        match = None
        for nt in nt8_trades_raw:
            # Map NT8 entry price aliases
            nt_entry = nt.get('EntryPrice') or nt.get('AvgEntryPrice')
            # Parse NT8 time
            nt_time = pd.to_datetime(nt.get('EntryTime', 0))
            if abs((pt.entry_time - nt_time).total_seconds()) <= 60:
                match = nt
                break
        
        if match:
            nt_entry = match.get('EntryPrice') or match.get('AvgEntryPrice')
            nt_exit = match.get('ExitPrice') or match.get('AvgExitPrice')
            print(f"MATCHED: PyEntry {pt.entry_price:.2f} vs NT8Entry {nt_entry:.2f} | Diff: {pt.entry_price - nt_entry:.2f}")
        else:
            print(f"ORPHAN PYTHON TRADE: {pt.entry_time} at {pt.entry_price:.2f}")

    # Output MCP Command for User
    print("\n--- Next Steps for NT8 Configuration ---")
    print(f"To align NT8 with this result, ensure the .cs strategy contains:")
    print(f"Set Trade Date Time Range: 09:30 to 15:59 ET")
    print(f"MCP Command: mcp_nt-mcp-server_nt_backtest --strategy {strat.expected_nt8_strategy_name} --ticker {args.ticker} --date {args.date}")

if __name__ == "__main__":
    run_parity_check()