#!/usr/bin/env python3
"""
Bollinger Squeeze Mean Reversion Scalper Backtester (Blueprint 2)
===================================================================
High-performance, vectorized & Numba-accelerated mean reversion strategy.

Strategy Rules:
1. Squeeze Filter: Bollinger Band Width (BBW) <= SMA(20) of BBW (Low Volatility Compression).
2. Outer Band Touch & Bounce:
   - Long: Low <= Lower Band (2.5 StdDev) AND Close > Lower Band
   - Short: High >= Upper Band (2.5 StdDev) AND Close < Upper Band
3. Exits:
   - Target: Middle Bollinger Band (20 SMA)
   - Stop Loss: 1.0 * ATR(14)
   - Time Decay Exit: 5 bars max hold
4. Session Filter: RTH Session Windows (09:30 AM - 11:30 AM & 14:00 PM - 15:30 PM EST).
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
def run_fast_mean_reversion_simulation(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    sma20: np.ndarray,
    atr: np.ndarray,
    signals: np.ndarray,  # 1 for Long, -1 for Short, 0 for None
    sl_mult: float,
    max_hold_bars: int,
    tick_size: float,
    point_value: float,
    slippage_ticks: float,
):
    """Numba-accelerated event-driven execution simulator for mean reversion."""
    n = len(closes)

    entry_indices = np.zeros(n, dtype=np.int32)
    exit_indices = np.zeros(n, dtype=np.int32)
    directions = np.zeros(n, dtype=np.int32)
    entry_prices = np.zeros(n, dtype=np.float64)
    exit_prices = np.zeros(n, dtype=np.float64)
    pnl_points = np.zeros(n, dtype=np.float64)
    pnl_dollars = np.zeros(n, dtype=np.float64)
    pnl_r = np.zeros(n, dtype=np.float64)
    durations = np.zeros(n, dtype=np.int32)
    exit_reasons = np.zeros(n, dtype=np.int32)  # 1: Target (Middle Band), 2: SL, 3: Time Decay Exit

    trade_count = 0
    in_trade = False
    entry_idx = 0
    trade_dir = 0
    trade_entry_p = 0.0
    trade_sl = 0.0
    risk_pts = 0.0

    slippage_pts = slippage_ticks * tick_size

    for i in range(1, n - 1):
        if not in_trade:
            sig = signals[i]
            if sig != 0 and not np.isnan(atr[i]) and atr[i] > 0 and not np.isnan(sma20[i]):
                in_trade = True
                entry_idx = i + 1
                trade_dir = sig

                raw_entry = opens[i + 1]
                if trade_dir == 1:
                    trade_entry_p = raw_entry + slippage_pts
                    risk_pts = sl_mult * atr[i]
                    trade_sl = trade_entry_p - risk_pts
                else:
                    trade_entry_p = raw_entry - slippage_pts
                    risk_pts = sl_mult * atr[i]
                    trade_sl = trade_entry_p + risk_pts

        else:
            hold_len = i - entry_idx + 1
            curr_h = highs[i]
            curr_l = lows[i]
            target_p = sma20[i]  # Target is dynamic Middle Band (20 SMA)

            exit_price = 0.0
            reason = 0

            if trade_dir == 1:
                # Check SL first
                if curr_l <= trade_sl:
                    reason = 2  # SL
                    exit_price = trade_sl - slippage_pts
                elif curr_h >= target_p:
                    reason = 1  # Target hit
                    exit_price = target_p
                elif hold_len >= max_hold_bars:
                    reason = 3  # Time Decay
                    exit_price = closes[i]
            else:
                # Short Position
                if curr_h >= trade_sl:
                    reason = 2  # SL
                    exit_price = trade_sl + slippage_pts
                elif curr_l <= target_p:
                    reason = 1  # Target hit
                    exit_price = target_p
                elif hold_len >= max_hold_bars:
                    reason = 3  # Time Decay
                    exit_price = closes[i]

            if reason != 0:
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


class BollingerSqueezeMeanReversionBacktester:
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

        # Precompute RTH session mask
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
        bb_period: int = 20,
        std_dev: float = 2.5,
        sl_atr: float = 1.0,
        max_hold: int = 5,
        rth_only: bool = True,
        slippage_ticks: float = 0.5,
    ) -> dict:
        t0 = time.time()

        closes = df["Close"].values.astype(np.float64)
        highs = df["High"].values.astype(np.float64)
        lows = df["Low"].values.astype(np.float64)
        opens = df["Open"].values.astype(np.float64)
        n = len(closes)

        # 1. ATR(14)
        prev_closes = np.roll(closes, 1)
        prev_closes[0] = closes[0]
        tr = np.maximum(
            highs - lows,
            np.maximum(np.abs(highs - prev_closes), np.abs(lows - prev_closes)),
        )
        atr = pd.Series(tr).ewm(alpha=1.0 / 14, adjust=False).mean().values

        # 2. Bollinger Bands(20, std_dev)
        sma20 = pd.Series(closes).rolling(bb_period).mean().values
        std20 = pd.Series(closes).rolling(bb_period).std().values
        upper_band = sma20 + std_dev * std20
        lower_band = sma20 - std_dev * std20

        bbw = (upper_band - lower_band) / sma20
        bbw_sma = pd.Series(bbw).rolling(bb_period).mean().values
        squeeze_mask = (bbw <= bbw_sma)  # Volatility compression regime

        # 3. Signals (Bounce off outer bands during squeeze)
        long_cond = squeeze_mask & (lows <= lower_band) & (closes > lower_band)
        short_cond = squeeze_mask & (highs >= upper_band) & (closes < upper_band)

        if rth_only and "rth_mask" in df.columns:
            rth_mask = df["rth_mask"].values
            long_cond = long_cond & rth_mask
            short_cond = short_cond & rth_mask

        signals = np.zeros(n, dtype=np.int32)
        signals[long_cond] = 1
        signals[short_cond] = -1

        # 4. Run Numba Simulation
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
        ) = run_fast_mean_reversion_simulation(
            opens,
            highs,
            lows,
            closes,
            sma20,
            atr,
            signals,
            sl_atr,
            max_hold,
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

        results = {
            "Ticker": self.ticker,
            "Strategy": "Bollinger Squeeze Mean Reversion (Blueprint 2)",
            "Total Trades": total_trades,
            "Win Rate (%)": round(win_rate, 2),
            "Profit Factor": round(profit_factor, 2),
            "Net Profit ($)": round(net_profit, 2),
            "Expectancy ($/trade)": round(exp_dollars, 2),
            "Expectancy (R/trade)": round(exp_r, 2),
            "Max Drawdown ($)": round(max_dd_dollars, 2),
            "Avg Duration (bars)": round(np.mean(durations), 1),
            "Target Exits": int(np.sum(exit_reasons == 1)),
            "SL Exits": int(np.sum(exit_reasons == 2)),
            "Time Decay Exits": int(np.sum(exit_reasons == 3)),
            "Execution Time (s)": round(elapsed, 4),
        }

        return results


def main():
    parser = argparse.ArgumentParser(description="Bollinger Squeeze Mean Reversion Scalper Backtester")
    parser.add_argument("--ticker", type=str, default="NQ1", help="Ticker name (NQ1, ES1)")
    parser.add_argument("--data_path", type=str, default=None, help="Path to parquet file")
    parser.add_argument("--bb_period", type=int, default=20, help="BB Period (default 20)")
    parser.add_argument("--std_dev", type=float, default=2.5, help="StdDev multiplier (default 2.5)")
    parser.add_argument("--sl_atr", type=float, default=1.0, help="Stop Loss ATR Multiple (default 1.0)")
    parser.add_argument("--max_hold", type=int, default=5, help="Max hold duration in bars (default 5)")
    args = parser.parse_args()

    if args.data_path is None:
        data_path = PROJECT_ROOT / "data" / f"{args.ticker}_1m.parquet"
    else:
        data_path = Path(args.data_path)

    print("=" * 80)
    print(f"BOLLINGER SQUEEZE MEAN REVERSION SCALPER (BLUEPRINT 2)")
    print(f"Ticker: {args.ticker} | Data File: {data_path.name}")
    print("=" * 80)

    backtester = BollingerSqueezeMeanReversionBacktester(str(data_path), ticker=args.ticker)
    print("Loading Parquet dataset...")
    df = backtester.load_data()
    print(f"Loaded {len(df):,} 1-minute bars spanning {df.index[0]} to {df.index[-1]}")

    print("\nRunning Simulation...")
    res = backtester.run_backtest(
        df,
        bb_period=args.bb_period,
        std_dev=args.std_dev,
        sl_atr=args.sl_atr,
        max_hold=args.max_hold,
    )

    print("\nBACKTEST PERFORMANCE REPORT")
    print("-" * 50)
    for k, v in res.items():
        print(f"  {k:<22}: {v}")
    print("-" * 50)


if __name__ == "__main__":
    main()
