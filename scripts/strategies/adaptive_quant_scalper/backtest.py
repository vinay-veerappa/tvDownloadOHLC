#!/usr/bin/env python3
"""
Unified Adaptive Quant Scalper Backtester
==========================================
Combines Blueprint 1 (HMA Slope + SuperTrend Expansion) & Blueprint 2 (Bollinger Squeeze Mean Reversion)
into a dynamic, regime-switching quant scalping engine.

Dynamic Regime Switching Logic:
- Squeeze State (BBW <= BBW_SMA): Activates Mode 1 (Mean Reversion fading outer 2.5 StdDev bands to 20 SMA).
- Expansion State (BBW > BBW_SMA): Activates Mode 2 (Trend Continuation limit entry on HMA slope inflection + SuperTrend).
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


@jit(nopython=True, fastmath=True)
def calc_wma(prices: np.ndarray, period: int) -> np.ndarray:
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
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))

    wma_half = calc_wma(prices, half_period)
    wma_full = calc_wma(prices, period)

    raw_hma = 2.0 * wma_half - wma_full
    hma = calc_wma(raw_hma, sqrt_period)
    return hma


@jit(nopython=True, fastmath=True)
def compute_supertrend_numba(high: np.ndarray, low: np.ndarray, close: np.ndarray, atr: np.ndarray, multiplier: float):
    n = len(close)
    st = np.full(n, np.nan, dtype=np.float64)
    direction = np.zeros(n, dtype=np.int32)

    upper_band = (high + low) / 2.0 + multiplier * atr
    lower_band = (high + low) / 2.0 - multiplier * atr

    final_ub = np.full(n, np.nan, dtype=np.float64)
    final_lb = np.full(n, np.nan, dtype=np.float64)

    for i in range(1, n):
        if np.isnan(atr[i]):
            continue

        if lower_band[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1] or np.isnan(final_lb[i - 1]):
            final_lb[i] = lower_band[i]
        else:
            final_lb[i] = final_lb[i - 1]

        if upper_band[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1] or np.isnan(final_ub[i - 1]):
            final_ub[i] = upper_band[i]
        else:
            final_ub[i] = final_ub[i - 1]

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
def run_adaptive_scalper_simulation(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    sma20: np.ndarray,
    upper_band: np.ndarray,
    lower_band: np.ndarray,
    hma: np.ndarray,
    atr: np.ndarray,
    mode1_signals: np.ndarray,  # Squeeze Mean Reversion Signals
    mode2_signals: np.ndarray,  # Expansion Trend Signals
    sl_atr_mode1: float,
    sl_atr_mode2: float,
    tp_atr_mode2: float,
    max_hold_mode1: int,
    max_hold_mode2: int,
    tick_size: float,
    point_value: float,
    slippage_ticks: float,
):
    """Numba execution simulator for the combined Adaptive Scalper."""
    n = len(closes)

    entry_indices = np.zeros(n, dtype=np.int32)
    exit_indices = np.zeros(n, dtype=np.int32)
    trade_modes = np.zeros(n, dtype=np.int32)  # 1 for Mean Reversion, 2 for Trend Expansion
    directions = np.zeros(n, dtype=np.int32)
    entry_prices = np.zeros(n, dtype=np.float64)
    exit_prices = np.zeros(n, dtype=np.float64)
    pnl_points = np.zeros(n, dtype=np.float64)
    pnl_dollars = np.zeros(n, dtype=np.float64)
    pnl_r = np.zeros(n, dtype=np.float64)
    durations = np.zeros(n, dtype=np.int32)
    exit_reasons = np.zeros(n, dtype=np.int32)

    trade_count = 0
    in_trade = False
    entry_idx = 0
    trade_mode = 0
    trade_dir = 0
    trade_entry_p = 0.0
    trade_sl = 0.0
    trade_tp = 0.0
    risk_pts = 0.0

    slippage_pts = slippage_ticks * tick_size

    for i in range(1, n - 1):
        if not in_trade:
            # Check Mode 2 (Expansion Trend Scalp) first
            sig2 = mode2_signals[i]
            sig1 = mode1_signals[i]

            if sig2 != 0 and not np.isnan(atr[i]) and atr[i] > 0:
                target_limit = hma[i]
                next_low = lows[i + 1]
                next_high = highs[i + 1]

                filled = False
                if sig2 == 1 and next_low <= target_limit:
                    trade_entry_p = target_limit
                    filled = True
                elif sig2 == -1 and next_high >= target_limit:
                    trade_entry_p = target_limit
                    filled = True

                if filled:
                    in_trade = True
                    entry_idx = i + 1
                    trade_mode = 2
                    trade_dir = sig2
                    risk_pts = sl_atr_mode2 * atr[i]
                    if trade_dir == 1:
                        trade_sl = trade_entry_p - risk_pts
                        trade_tp = trade_entry_p + (tp_atr_mode2 * atr[i])
                    else:
                        trade_sl = trade_entry_p + risk_pts
                        trade_tp = trade_entry_p - (tp_atr_mode2 * atr[i])

            elif sig1 != 0 and not np.isnan(atr[i]) and atr[i] > 0 and not np.isnan(sma20[i]):
                # Mode 1 (Squeeze Mean Reversion with Limit Order @ Outer Band)
                limit_target = lower_band[i] if sig1 == 1 else upper_band[i]
                next_low = lows[i + 1]
                next_high = highs[i + 1]

                filled = False
                if sig1 == 1 and next_low <= limit_target:
                    trade_entry_p = limit_target
                    filled = True
                elif sig1 == -1 and next_high >= limit_target:
                    trade_entry_p = limit_target
                    filled = True

                if filled:
                    in_trade = True
                    entry_idx = i + 1
                    trade_mode = 1
                    trade_dir = sig1
                    risk_pts = sl_atr_mode1 * atr[i]
                    if trade_dir == 1:
                        trade_sl = trade_entry_p - risk_pts
                        trade_tp = sma20[i + 1]
                    else:
                        trade_sl = trade_entry_p + risk_pts
                        trade_tp = sma20[i + 1]

        else:
            hold_len = i - entry_idx + 1
            curr_h = highs[i]
            curr_l = lows[i]

            exit_price = 0.0
            reason = 0

            if trade_mode == 1:
                # Mode 1 (Mean Reversion) Exits
                target_p = sma20[i]
                if trade_dir == 1:
                    if curr_l <= trade_sl:
                        reason = 2
                        exit_price = trade_sl - slippage_pts
                    elif curr_h >= target_p:
                        reason = 1
                        exit_price = target_p
                    elif hold_len >= max_hold_mode1:
                        reason = 3
                        exit_price = closes[i]
                else:
                    if curr_h >= trade_sl:
                        reason = 2
                        exit_price = trade_sl + slippage_pts
                    elif curr_l <= target_p:
                        reason = 1
                        exit_price = target_p
                    elif hold_len >= max_hold_mode1:
                        reason = 3
                        exit_price = closes[i]

            else:
                # Mode 2 (Trend Expansion) Exits
                if trade_dir == 1:
                    if curr_l <= trade_sl:
                        reason = 2
                        exit_price = trade_sl - slippage_pts
                    elif curr_h >= trade_tp:
                        reason = 1
                        exit_price = trade_tp
                    elif hold_len >= max_hold_mode2:
                        reason = 3
                        exit_price = closes[i]
                else:
                    if curr_h >= trade_sl:
                        reason = 2
                        exit_price = trade_sl + slippage_pts
                    elif curr_l <= trade_tp:
                        reason = 1
                        exit_price = trade_tp
                    elif hold_len >= max_hold_mode2:
                        reason = 3
                        exit_price = closes[i]

            if reason != 0:
                pnl_p = (exit_price - trade_entry_p) if trade_dir == 1 else (trade_entry_p - exit_price)
                pnl_d = pnl_p * point_value
                r_multiple = pnl_p / risk_pts if risk_pts > 0 else 0.0

                entry_indices[trade_count] = entry_idx
                exit_indices[trade_count] = i
                trade_modes[trade_count] = trade_mode
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
        trade_modes[:trade_count],
        directions[:trade_count],
        entry_prices[:trade_count],
        exit_prices[:trade_count],
        pnl_points[:trade_count],
        pnl_dollars[:trade_count],
        pnl_r[:trade_count],
        durations[:trade_count],
        exit_reasons[:trade_count],
    )


class AdaptiveQuantScalperBacktester:
    def __init__(self, data_path: str, ticker: str = "NQ1"):
        self.data_path = Path(data_path)
        self.ticker = ticker.upper()

        if "NQ" in self.ticker:
            self.tick_size = 0.25
            self.point_value = 20.0
        elif "ES" in self.ticker:
            self.tick_size = 0.25
            self.point_value = 50.0
        else:
            self.tick_size = 0.25
            self.point_value = 20.0

    def load_data(self) -> pd.DataFrame:
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found at: {self.data_path}")

        df = pd.read_parquet(self.data_path)

        if "timestamp" in df.columns:
            df["time"] = pd.to_datetime(df["timestamp"])
            df.set_index("time", inplace=True)
        elif not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        df.sort_index(inplace=True)

        col_map = {c: c.capitalize() for c in df.columns}
        df.rename(columns=col_map, inplace=True)

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
        st_mult: float = 2.0,
        bb_period: int = 20,
        std_dev: float = 2.5,
        ema_filter_period: int = 200,
        sl_mode1: float = 1.0,
        sl_mode2: float = 2.0,
        tp_mode2: float = 1.5,
        max_hold_mode1: int = 5,
        max_hold_mode2: int = 6,
        rth_only: bool = True,
        slippage_ticks: float = 0.5,
    ) -> dict:
        t0 = time.time()

        closes = df["Close"].values.astype(np.float64)
        highs = df["High"].values.astype(np.float64)
        lows = df["Low"].values.astype(np.float64)
        opens = df["Open"].values.astype(np.float64)
        n = len(closes)

        # 1. Indicators
        prev_closes = np.roll(closes, 1)
        prev_closes[0] = closes[0]
        tr = np.maximum(
            highs - lows,
            np.maximum(np.abs(highs - prev_closes), np.abs(lows - prev_closes)),
        )
        atr = pd.Series(tr).ewm(alpha=1.0 / 14, adjust=False).mean().values

        hma = calc_hma(closes, hma_period)
        st_line, st_dir = compute_supertrend_numba(highs, lows, closes, atr, st_mult)

        sma20 = pd.Series(closes).rolling(bb_period).mean().values
        std20 = pd.Series(closes).rolling(bb_period).std().values
        upper_band = sma20 + std_dev * std20
        lower_band = sma20 - std_dev * std20

        bbw = (upper_band - lower_band) / sma20
        bbw_sma = pd.Series(bbw).rolling(bb_period).mean().values

        squeeze_mask = (bbw <= bbw_sma)
        expansion_mask = (bbw > bbw_sma)

        # 2. EMA Filter
        if ema_filter_period > 0:
            ema_filter = pd.Series(closes).ewm(span=ema_filter_period, adjust=False).mean().values
            long_ema_ok = closes > ema_filter
            short_ema_ok = closes < ema_filter
        else:
            long_ema_ok = np.ones(n, dtype=bool)
            short_ema_ok = np.ones(n, dtype=bool)

        # 3. Signals
        # Mode 1: Squeeze Mean Reversion
        m1_long = squeeze_mask & (lows <= lower_band) & (closes > lower_band)
        m1_short = squeeze_mask & (highs >= upper_band) & (closes < upper_band)

        # Mode 2: Expansion Trend Scalp
        hma_inc = np.zeros(n, dtype=bool)
        hma_dec = np.zeros(n, dtype=bool)
        hma_inc[2:] = (hma[2:] > hma[1:-1]) & (hma[1:-1] <= hma[:-2])
        hma_dec[2:] = (hma[2:] < hma[1:-1]) & (hma[1:-1] >= hma[:-2])

        m2_long = expansion_mask & (st_dir == 1) & (lows <= hma) & hma_inc & long_ema_ok
        m2_short = expansion_mask & (st_dir == -1) & (highs >= hma) & hma_dec & short_ema_ok

        if rth_only and "rth_mask" in df.columns:
            rth_mask = df["rth_mask"].values
            m1_long = m1_long & rth_mask
            m1_short = m1_short & rth_mask
            m2_long = m2_long & rth_mask
            m2_short = m2_short & rth_mask

        signals_m1 = np.zeros(n, dtype=np.int32)
        signals_m1[m1_long] = 1
        signals_m1[m1_short] = -1

        signals_m2 = np.zeros(n, dtype=np.int32)
        signals_m2[m2_long] = 1
        signals_m2[m2_short] = -1

        # 4. Simulation
        (
            e_idx,
            x_idx,
            t_modes,
            dirs,
            e_price,
            x_price,
            pnl_pts,
            pnl_dlr,
            pnl_r,
            durations,
            exit_reasons,
        ) = run_adaptive_scalper_simulation(
            opens,
            highs,
            lows,
            closes,
            sma20,
            upper_band,
            lower_band,
            hma,
            atr,
            signals_m1,
            signals_m2,
            sl_mode1,
            sl_mode2,
            tp_mode2,
            max_hold_mode1,
            max_hold_mode2,
            self.tick_size,
            self.point_value,
            slippage_ticks,
        )

        elapsed = time.time() - t0

        total_trades = len(pnl_dlr)
        if total_trades == 0:
            return {"error": "No trades generated."}

        wins = pnl_dlr > 0
        losses = pnl_dlr < 0

        win_rate = (np.sum(wins) / total_trades) * 100.0
        gross_profit = np.sum(pnl_dlr[wins]) if np.sum(wins) > 0 else 0.0
        gross_loss = np.abs(np.sum(pnl_dlr[losses])) if np.sum(losses) > 0 else 1.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan

        net_profit = np.sum(pnl_dlr)
        exp_dollars = net_profit / total_trades
        exp_r = np.mean(pnl_r)

        cum_pnl = np.cumsum(pnl_dlr)
        peak = np.maximum.accumulate(cum_pnl)
        drawdown = peak - cum_pnl
        max_dd_dollars = np.max(drawdown)

        # Mode Breakdown
        m1_trades = t_modes == 1
        m2_trades = t_modes == 2

        m1_win_rate = (np.sum(pnl_dlr[m1_trades] > 0) / np.sum(m1_trades)) * 100.0 if np.sum(m1_trades) > 0 else 0.0
        m2_win_rate = (np.sum(pnl_dlr[m2_trades] > 0) / np.sum(m2_trades)) * 100.0 if np.sum(m2_trades) > 0 else 0.0

        results = {
            "Ticker": self.ticker,
            "Strategy": "Unified Adaptive Quant Scalper (Combined)",
            "Total Trades": total_trades,
            "Mode 1 (Mean Rev) Trades": int(np.sum(m1_trades)),
            "Mode 1 Win Rate (%)": round(m1_win_rate, 2),
            "Mode 2 (Trend Exp) Trades": int(np.sum(m2_trades)),
            "Mode 2 Win Rate (%)": round(m2_win_rate, 2),
            "Combined Win Rate (%)": round(win_rate, 2),
            "Profit Factor": round(profit_factor, 2),
            "Net Profit ($)": round(net_profit, 2),
            "Expectancy ($/trade)": round(exp_dollars, 2),
            "Expectancy (R/trade)": round(exp_r, 2),
            "Max Drawdown ($)": round(max_dd_dollars, 2),
            "Avg Duration (bars)": round(np.mean(durations), 1),
            "Execution Time (s)": round(elapsed, 4),
        }

        return results


def main():
    parser = argparse.ArgumentParser(description="Unified Adaptive Quant Scalper Backtester")
    parser.add_argument("--ticker", type=str, default="NQ1", help="Ticker name (NQ1, ES1)")
    parser.add_argument("--data_path", type=str, default=None, help="Path to parquet file")
    parser.add_argument("--hma_period", type=int, default=14, help="HMA Period (default 14)")
    parser.add_argument("--st_mult", type=float, default=2.0, help="SuperTrend Multiplier (default 2.0)")
    parser.add_argument("--sl_mode1", type=float, default=1.0, help="Mode 1 SL ATR (default 1.0)")
    parser.add_argument("--sl_mode2", type=float, default=2.0, help="Mode 2 SL ATR (default 2.0)")
    parser.add_argument("--tp_mode2", type=float, default=1.5, help="Mode 2 TP ATR (default 1.5)")
    args = parser.parse_args()

    if args.data_path is None:
        data_path = PROJECT_ROOT / "data" / f"{args.ticker}_1m.parquet"
    else:
        data_path = Path(args.data_path)

    print("=" * 80)
    print(f"UNIFIED ADAPTIVE QUANT SCALPER (COMBINED ENGINE)")
    print(f"Ticker: {args.ticker} | Data File: {data_path.name}")
    print("=" * 80)

    backtester = AdaptiveQuantScalperBacktester(str(data_path), ticker=args.ticker)
    print("Loading Parquet dataset...")
    df = backtester.load_data()
    print(f"Loaded {len(df):,} 1-minute bars spanning {df.index[0]} to {df.index[-1]}")

    print("\nRunning Adaptive Simulation...")
    res = backtester.run_backtest(
        df,
        hma_period=args.hma_period,
        st_mult=args.st_mult,
        sl_mode1=args.sl_mode1,
        sl_mode2=args.sl_mode2,
        tp_mode2=args.tp_mode2,
    )

    print("\nBACKTEST PERFORMANCE REPORT")
    print("-" * 55)
    for k, v in res.items():
        print(f"  {k:<28}: {v}")
    print("-" * 55)


if __name__ == "__main__":
    main()
