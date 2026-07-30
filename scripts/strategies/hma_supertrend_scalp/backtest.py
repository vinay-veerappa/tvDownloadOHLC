#!/usr/bin/env python3
"""
HMA Slope + SuperTrend Trend Scalper Backtester
=================================================
High-performance, vectorized & Numba-accelerated quantitative scalping engine.

Strategy Rules:
1. Regime Filter: SuperTrend(10, 2.0) defines trend direction (+1 Bullish, -1 Bearish).
2. Pullback & Slope Inflection:
   - Long: SuperTrend Bullish AND Low <= HMA AND HMA[t] > HMA[t-1] AND HMA[t-1] <= HMA[t-2]
   - Short: SuperTrend Bearish AND High >= HMA AND HMA[t] < HMA[t-1] AND HMA[t-1] >= HMA[t-2]
3. Risk Management:
   - SL: 1.0 * ATR(14)
   - TP: 1.5 * ATR(14) (1.5 R:R ratio)
   - Max Hold: 6 bars (Time decay exit)
4. Session Filter: 09:30 AM - 11:30 AM & 14:00 PM - 15:30 PM EST (RTH expansion windows).
"""

import argparse
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
from numba import jit

# Force root directory into python path for module imports
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# NUMBA VECTORIZED CORE CALCULATIONS
# ============================================================================

@jit(nopython=True, fastmath=True)
def calc_wma(prices: np.ndarray, period: int) -> np.ndarray:
    """Compute Weighted Moving Average using Numba loop."""
    n = len(prices)
    wma = np.full(n, np.nan, dtype=np.float64)
    weights = np.arange(1, period + 1, dtype=np.float64)
    weight_sum = weights.sum()

    for i in range(period - 1, n):
        window = prices[i - period + 1 : i + 1]
        if not np.isnan(window).any():
            wma[i] = np.dot(window, weights) / weight_sum
    return wma


def calc_hma(prices: np.ndarray, period: int) -> np.ndarray:
    """Compute Hull Moving Average (HMA)."""
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))

    wma_half = calc_wma(prices, half_period)
    wma_full = calc_wma(prices, period)

    raw_hma = 2.0 * wma_half - wma_full
    hma = calc_wma(raw_hma, sqrt_period)
    return hma


@jit(nopython=True, fastmath=True)
def compute_supertrend_numba(high: np.ndarray, low: np.ndarray, close: np.ndarray, atr: np.ndarray, multiplier: float):
    """Numba-accelerated SuperTrend state machine."""
    n = len(close)
    st = np.full(n, np.nan, dtype=np.float64)
    direction = np.zeros(n, dtype=np.int32)  # 1 for Bullish, -1 for Bearish

    upper_band = (high + low) / 2.0 + multiplier * atr
    lower_band = (high + low) / 2.0 - multiplier * atr

    # Final Bands
    final_ub = np.full(n, np.nan, dtype=np.float64)
    final_lb = np.full(n, np.nan, dtype=np.float64)

    for i in range(1, n):
        if np.isnan(atr[i]):
            continue

        # Lower Band logic
        if lower_band[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1] or np.isnan(final_lb[i - 1]):
            final_lb[i] = lower_band[i]
        else:
            final_lb[i] = final_lb[i - 1]

        # Upper Band logic
        if upper_band[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1] or np.isnan(final_ub[i - 1]):
            final_ub[i] = upper_band[i]
        else:
            final_ub[i] = final_ub[i - 1]

        # Direction logic
        prev_dir = direction[i - 1] if i > 1 else 1
        if prev_dir == 1:
            if close[i] < final_lb[i]:
                direction[i] = -1
                st[i] = final_ub[i]
            else:
                direction[i] = 1
                st[i] = final_lb[i]
        else:
            if close[i] > final_ub[i]:
                direction[i] = 1
                st[i] = final_lb[i]
            else:
                direction[i] = -1
                st[i] = final_ub[i]

    return st, direction


@jit(nopython=True, fastmath=True)
def run_fast_backtest_simulation(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    hma: np.ndarray,
    signals: np.ndarray,  # 1 for Long, -1 for Short, 0 for None
    tp_mult: float,
    sl_mult: float,
    max_hold_bars: int,
    tick_size: float,
    point_value: float,
    slippage_ticks: float,
    use_limit_order: bool = True,
):
    """Numba-accelerated event-driven execution simulator with O(1) performance."""
    n = len(closes)
    
    # Pre-allocate result buffers (max n trades)
    entry_indices = np.zeros(n, dtype=np.int32)
    exit_indices = np.zeros(n, dtype=np.int32)
    directions = np.zeros(n, dtype=np.int32)
    entry_prices = np.zeros(n, dtype=np.float64)
    exit_prices = np.zeros(n, dtype=np.float64)
    pnl_points = np.zeros(n, dtype=np.float64)
    pnl_dollars = np.zeros(n, dtype=np.float64)
    pnl_r = np.zeros(n, dtype=np.float64)
    durations = np.zeros(n, dtype=np.int32)
    exit_reasons = np.zeros(n, dtype=np.int32)  # 1: TP, 2: SL, 3: Time Decay Exit

    trade_count = 0
    in_trade = False
    entry_idx = 0
    trade_dir = 0
    trade_entry_p = 0.0
    trade_sl = 0.0
    trade_tp = 0.0
    risk_pts = 0.0

    slippage_pts = slippage_ticks * tick_size

    for i in range(1, n - 1):
        if not in_trade:
            sig = signals[i]
            if sig != 0 and not np.isnan(atr[i]) and atr[i] > 0:
                target_limit = hma[i]
                next_low = lows[i + 1]
                next_high = highs[i + 1]
                
                # Check limit order fill condition on next bar
                filled = False
                if use_limit_order:
                    if sig == 1 and next_low <= target_limit:
                        trade_entry_p = target_limit
                        filled = True
                    elif sig == -1 and next_high >= target_limit:
                        trade_entry_p = target_limit
                        filled = True
                else:
                    raw_entry = opens[i + 1]
                    trade_entry_p = raw_entry + slippage_pts if sig == 1 else raw_entry - slippage_pts
                    filled = True

                if filled:
                    in_trade = True
                    entry_idx = i + 1
                    trade_dir = sig
                    risk_pts = sl_mult * atr[i]
                    if trade_dir == 1:
                        trade_sl = trade_entry_p - risk_pts
                        trade_tp = trade_entry_p + (tp_mult * atr[i])
                    else:
                        trade_sl = trade_entry_p + risk_pts
                        trade_tp = trade_entry_p - (tp_mult * atr[i])

        else:
            # Check exit conditions inside current bar i
            hold_len = i - entry_idx + 1
            curr_h = highs[i]
            curr_l = lows[i]

            exit_price = 0.0
            reason = 0

            if trade_dir == 1:
                # Check Stop Loss first (conservative evaluation)
                if curr_l <= trade_sl:
                    reason = 2  # SL
                    exit_price = trade_sl - slippage_pts
                elif curr_h >= trade_tp:
                    reason = 1  # TP
                    exit_price = trade_tp
                elif hold_len >= max_hold_bars:
                    reason = 3  # Time Decay
                    exit_price = closes[i]
            else:
                # Short Position
                if curr_h >= trade_sl:
                    reason = 2  # SL
                    exit_price = trade_sl + slippage_pts
                elif curr_l <= trade_tp:
                    reason = 1  # TP
                    exit_price = trade_tp
                elif hold_len >= max_hold_bars:
                    reason = 3  # Time Decay
                    exit_price = closes[i]

            if reason != 0:
                # Close Trade
                pnl_p = (exit_price - trade_entry_p) if trade_dir == 1 else (trade_entry_p - exit_price)
                pnl_d = pnl_p * point_value
                r_multiple = pnl_p / risk_pts if risk_pts > 0 else 0.0

                entry_indices[trade_count] = entry_idx
                exit_indices[trade_count] = i
                directions[trade_count] = trade_dir
                entry_prices[trade_count] = trade_entry_p
                exit_prices[trade_count] = exit_price
                pnl_points[trade_count] = pnl_p
                pnl_dollars[trade_count] = pnl_d
                pnl_r[trade_count] = r_multiple
                durations[trade_count] = hold_len
                exit_reasons[trade_count] = reason

                trade_count += 1
                in_trade = False

    return (
        entry_indices[:trade_count],
        exit_indices[:trade_count],
        directions[:trade_count],
        entry_prices[:trade_count],
        exit_prices[:trade_count],
        pnl_points[:trade_count],
        pnl_dollars[:trade_count],
        pnl_r[:trade_count],
        durations[:trade_count],
        exit_reasons[:trade_count],
    )


# ============================================================================
# PYTHON BACKTEST ENGINE & METRICS
# ============================================================================

class HMASuperTrendScalpBacktester:
    def __init__(self, data_path: str, ticker: str = "NQ1"):
        self.data_path = Path(data_path)
        self.ticker = ticker.upper()

        # Contract Specifications
        if "NQ" in self.ticker:
            self.tick_size = 0.25
            self.point_value = 20.0  # $20 per NQ point
        elif "ES" in self.ticker:
            self.tick_size = 0.25
            self.point_value = 50.0  # $50 per ES point
        elif "RTY" in self.ticker:
            self.tick_size = 0.10
            self.point_value = 50.0
        elif "CL" in self.ticker:
            self.tick_size = 0.01
            self.point_value = 1000.0
        else:
            self.tick_size = 0.25
            self.point_value = 20.0

    def load_data(self) -> pd.DataFrame:
        """Load Parquet dataset and normalize columns."""
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found at: {self.data_path}")

        df = pd.read_parquet(self.data_path)
        
        # Ensure standard datetime index
        if "timestamp" in df.columns:
            df["time"] = pd.to_datetime(df["timestamp"])
            df.set_index("time", inplace=True)
        elif not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        df.sort_index(inplace=True)
        
        # Standardize column casing
        col_map = {c: c.capitalize() for c in df.columns}
        df.rename(columns=col_map, inplace=True)

        # Precompute RTH session mask (09:30 AM - 11:30 AM & 14:00 PM - 15:30 PM EST)
        if df.index.tz is None:
            times_est = df.index.tz_localize("UTC").tz_convert("America/New_York")
        else:
            times_est = df.index.tz_convert("America/New_York")

        time_minutes = times_est.hour * 60 + times_est.minute
        df["rth_mask"] = (
            ((time_minutes >= 570) & (time_minutes <= 690)) |  # 9:30 AM - 11:30 AM
            ((time_minutes >= 840) & (time_minutes <= 930))    # 2:00 PM - 3:30 PM
        )

        return df

    def run_backtest(
        self,
        df: pd.DataFrame,
        hma_period: int = 14,
        st_period: int = 10,
        st_mult: float = 2.0,
        sl_atr: float = 1.0,
        tp_atr: float = 1.5,
        max_hold: int = 6,
        ema_filter_period: int = 0,
        rth_only: bool = True,
        slippage_ticks: float = 1.0,
    ) -> dict:
        """Run vectorized indicator generation + Numba simulation."""
        t0 = time.time()

        closes = df["Close"].values.astype(np.float64)
        highs = df["High"].values.astype(np.float64)
        lows = df["Low"].values.astype(np.float64)
        opens = df["Open"].values.astype(np.float64)
        n = len(closes)

        # 1. Compute ATR(14)
        prev_closes = np.roll(closes, 1)
        prev_closes[0] = closes[0]
        tr = np.maximum(
            highs - lows,
            np.maximum(np.abs(highs - prev_closes), np.abs(lows - prev_closes)),
        )
        atr = pd.Series(tr).ewm(alpha=1.0 / 14, adjust=False).mean().values

        # 2. Compute HMA(hma_period)
        hma = calc_hma(closes, hma_period)

        # 3. Compute SuperTrend(st_period, st_mult)
        st_line, st_dir = compute_supertrend_numba(highs, lows, closes, atr, st_mult)

        # 4. Compute optional EMA Trend Filter (e.g., EMA 200)
        if ema_filter_period > 0:
            ema_filter = pd.Series(closes).ewm(span=ema_filter_period, adjust=False).mean().values
            long_ema_ok = closes > ema_filter
            short_ema_ok = closes < ema_filter
        else:
            long_ema_ok = np.ones(n, dtype=bool)
            short_ema_ok = np.ones(n, dtype=bool)

        # 5. Compute Bollinger Band Width Expansion Filter
        # BB(20, 2.0)
        sma20 = pd.Series(closes).rolling(20).mean().values
        std20 = pd.Series(closes).rolling(20).std().values
        bbw = (2.0 * 2.0 * std20) / sma20  # BandWidth ratio
        bbw_sma = pd.Series(bbw).rolling(20).mean().values
        bbw_ok = (bbw > bbw_sma)  # Volatility expansion mask

        # 6. Generate Signal Array
        signals = np.zeros(n, dtype=np.int32)

        hma_inc = np.zeros(n, dtype=bool)
        hma_dec = np.zeros(n, dtype=bool)
        
        hma_inc[2:] = (hma[2:] > hma[1:-1]) & (hma[1:-1] <= hma[:-2])
        hma_dec[2:] = (hma[2:] < hma[1:-1]) & (hma[1:-1] >= hma[:-2])

        long_cond = (st_dir == 1) & (lows <= hma) & hma_inc & long_ema_ok & bbw_ok
        short_cond = (st_dir == -1) & (highs >= hma) & hma_dec & short_ema_ok & bbw_ok

        # RTH Session Filter (09:30 AM - 11:30 AM EST & 14:00 PM - 15:30 PM EST)
        if rth_only and "rth_mask" in df.columns:
            rth_mask = df["rth_mask"].values
            long_cond = long_cond & rth_mask
            short_cond = short_cond & rth_mask

        signals[long_cond] = 1
        signals[short_cond] = -1

        # 5. Run Numba Accelerated Simulation
        (
            e_idx,
            x_idx,
            dirs,
            e_price,
            x_price,
            pnl_pts,
            pnl_dlr,
            pnl_r,
            durations,
            exit_reasons,
        ) = run_fast_backtest_simulation(
            opens,
            highs,
            lows,
            closes,
            atr,
            hma,
            signals,
            tp_atr,
            sl_atr,
            max_hold,
            self.tick_size,
            self.point_value,
            slippage_ticks,
            True,  # Limit order fill at HMA price
        )

        elapsed = time.time() - t0

        # Calculate Statistics
        total_trades = len(pnl_dlr)
        if total_trades == 0:
            return {"error": "No trades generated with current parameters."}

        wins = pnl_dlr > 0
        losses = pnl_dlr < 0
        evens = pnl_dlr == 0

        win_rate = (np.sum(wins) / total_trades) * 100.0
        gross_profit = np.sum(pnl_dlr[wins]) if np.sum(wins) > 0 else 0.0
        gross_loss = np.abs(np.sum(pnl_dlr[losses])) if np.sum(losses) > 0 else 1.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan

        net_profit = np.sum(pnl_dlr)
        exp_dollars = net_profit / total_trades
        exp_r = np.mean(pnl_r)

        # Drawdown calculation
        cum_pnl = np.cumsum(pnl_dlr)
        peak = np.maximum.accumulate(cum_pnl)
        drawdown = peak - cum_pnl
        max_dd_dollars = np.max(drawdown)

        # Exit reasons breakdown
        tp_count = np.sum(exit_reasons == 1)
        sl_count = np.sum(exit_reasons == 2)
        time_count = np.sum(exit_reasons == 3)

        results = {
            "Ticker": self.ticker,
            "Total Trades": total_trades,
            "Win Rate (%)": round(win_rate, 2),
            "Profit Factor": round(profit_factor, 2),
            "Net Profit ($)": round(net_profit, 2),
            "Expectancy ($/trade)": round(exp_dollars, 2),
            "Expectancy (R/trade)": round(exp_r, 2),
            "Max Drawdown ($)": round(max_dd_dollars, 2),
            "Avg Duration (bars)": round(np.mean(durations), 1),
            "TP Exits": int(tp_count),
            "SL Exits": int(sl_count),
            "Time Decay Exits": int(time_count),
            "Execution Time (s)": round(elapsed, 4),
            "HMA Period": hma_period,
            "SuperTrend Mult": st_mult,
            "SL ATR": sl_atr,
            "TP ATR": tp_atr,
        }

        return results


# ============================================================================
# CLI MAIN INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="HMA Slope + SuperTrend Trend Scalper Backtester")
    parser.add_argument("--ticker", type=str, default="NQ1", help="Ticker name (NQ1, ES1)")
    parser.add_argument("--data_path", type=str, default=None, help="Path to parquet file")
    parser.add_argument("--hma_period", type=int, default=14, help="HMA Period (default 14)")
    parser.add_argument("--st_period", type=int, default=10, help="SuperTrend Period (default 10)")
    parser.add_argument("--st_mult", type=float, default=2.0, help="SuperTrend Multiplier (default 2.0)")
    parser.add_argument("--sl_atr", type=float, default=1.0, help="Stop Loss ATR Multiple (default 1.0)")
    parser.add_argument("--tp_atr", type=float, default=1.5, help="Take Profit ATR Multiple (default 1.5)")
    parser.add_argument("--max_hold", type=int, default=6, help="Max hold duration in bars (default 6)")
    parser.add_argument("--rth_only", action="store_true", default=True, help="Filter RTH session windows")
    parser.add_argument("--sweep", action="store_true", help="Run parameter optimization grid search")
    args = parser.parse_args()

    if args.data_path is None:
        data_path = PROJECT_ROOT / "data" / f"{args.ticker}_1m.parquet"
    else:
        data_path = Path(args.data_path)

    print("=" * 80)
    print(f"HMA SLOPE + SUPERTREND TREND SCALPER BACKTESTER")
    print(f"Ticker: {args.ticker} | Data File: {data_path.name}")
    print("=" * 80)

    backtester = HMASuperTrendScalpBacktester(str(data_path), ticker=args.ticker)
    print("Loading Parquet dataset...")
    df = backtester.load_data()
    print(f"Loaded {len(df):,} 1-minute bars spanning {df.index[0]} to {df.index[-1]}")

    if not args.sweep:
        print("\nRunning Baseline Simulation...")
        res = backtester.run_backtest(
            df,
            hma_period=args.hma_period,
            st_period=args.st_period,
            st_mult=args.st_mult,
            sl_atr=args.sl_atr,
            tp_atr=args.tp_atr,
            max_hold=args.max_hold,
            rth_only=args.rth_only,
        )

        print("\nBACKTEST PERFORMANCE REPORT")
        print("-" * 50)
        for k, v in res.items():
            print(f"  {k:<22}: {v}")
        print("-" * 50)

    else:
        print("\nRUNNING VECTORIZED PARAMETER OPTIMIZATION GRID SEARCH...")
        parser.add_argument("--ema_filter", type=int, default=0, help="EMA filter period")
        
        hma_periods = [9, 14, 21]
        st_mults = [1.5, 2.0, 2.5]
        sl_atrs = [1.2, 1.5, 2.0, 2.5]
        tp_atrs = [1.0, 1.5, 2.0]
        ema_filters = [0, 200]
        max_holds = [6, 12]

        sweep_results = []
        t_start = time.time()

        for hma_p in hma_periods:
            for st_m in st_mults:
                for sl_a in sl_atrs:
                    for tp_a in tp_atrs:
                        for ema_f in ema_filters:
                            for m_hold in max_holds:
                                r = backtester.run_backtest(
                                    df,
                                    hma_period=hma_p,
                                    st_mult=st_m,
                                    sl_atr=sl_a,
                                    tp_atr=tp_a,
                                    max_hold=m_hold,
                                    ema_filter_period=ema_f,
                                    rth_only=args.rth_only,
                                )
                                if "error" not in r:
                                    r["EMA Filter"] = ema_f
                                    r["Max Hold"] = m_hold
                                    sweep_results.append(r)

        sweep_df = pd.DataFrame(sweep_results)
        sweep_df.sort_values(by="Profit Factor", ascending=False, inplace=True)
        total_time = time.time() - t_start

        print(f"\nGrid Search Completed in {total_time:.2f} seconds across {len(sweep_results)} combinations!\n")
        print("TOP 15 PARAMETER CONFIGURATIONS (BY PROFIT FACTOR):")
        print("=" * 115)
        top_cols = ["HMA Period", "SuperTrend Mult", "SL ATR", "TP ATR", "EMA Filter", "Max Hold", "Total Trades", "Win Rate (%)", "Profit Factor", "Expectancy ($/trade)", "Max Drawdown ($)"]
        print(sweep_df[top_cols].head(15).to_string(index=False))
        print("=" * 115)


if __name__ == "__main__":
    main()
