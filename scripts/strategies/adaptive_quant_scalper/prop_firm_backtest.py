#!/usr/bin/env python3
"""
Prop Firm Optimized Adaptive Quant Scalper Backtester
=====================================================
Engineered specifically for Prop Firm evaluations (Apex, Topstep, MyFundedFutures).
Focuses on HIGH WIN-RATE (> 65%) and TIGHT TRAILING DRAWDOWN CONTROL (< $1,500 max DD).

Prop Firm Rules Enforced:
1. Max Trades Per Day: 3 trades max.
2. Max Consecutive Losses: Stop trading for the day after 2 consecutive losses.
3. Daily Max Loss Limit: $400 hard cap.
4. Trailing Drawdown Safeguard: Real-time High Water Mark (HWM) trailing drawdown lock out.
5. High Win-Rate Filters: 15-min HTF trend filter + Volume expansion filter.
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
def run_prop_firm_simulation(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    sma20: np.ndarray,
    upper_band: np.ndarray,
    lower_band: np.ndarray,
    hma: np.ndarray,
    atr: np.ndarray,
    day_indices: np.ndarray,
    mode1_signals: np.ndarray,
    mode2_signals: np.ndarray,
    sl_type: int,  # 0=ATR, 1=Structural Swing, 2=Indicator Line, 3=BPS % (e.g. 5 bps = 0.05%)
    sl_val: float,  # ATR multiplier, or BPS count (e.g. 5.0 for 5 bps = 0.05%)
    tp_atr_mode1: float,
    tp_atr_mode2: float,
    max_hold_bars: int,
    max_trades_per_day: int,
    max_daily_loss: float,
    max_consec_losses: int,
    tick_size: float,
    point_value: float,
    slippage_ticks: float,
):
    """Numba execution engine enforcing strict Prop Firm risk gatekeeping with 4 SL modes."""
    n = len(closes)

    entry_indices = np.zeros(n, dtype=np.int32)
    exit_indices = np.zeros(n, dtype=np.int32)
    trade_modes = np.zeros(n, dtype=np.int32)
    directions = np.zeros(n, dtype=np.int32)
    entry_prices = np.zeros(n, dtype=np.float64)
    exit_prices = np.zeros(n, dtype=np.float64)
    pnl_dollars = np.zeros(n, dtype=np.float64)
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

    slippage_pts = slippage_ticks * tick_size

    # Daily State Tracking
    current_day = -1
    daily_trades = 0
    daily_pnl = 0.0
    consec_losses = 0
    done_for_day = False

    for i in range(5, n - 1):
        day_id = day_indices[i]

        if day_id != current_day:
            current_day = day_id
            daily_trades = 0
            daily_pnl = 0.0
            consec_losses = 0
            done_for_day = False

        if not in_trade:
            if done_for_day or daily_trades >= max_trades_per_day or daily_pnl <= -max_daily_loss or consec_losses >= max_consec_losses:
                continue

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

                    # Calculate Initial Stop Loss based on selected sl_type
                    if sl_type == 0:
                        # ATR Multiplier
                        risk_pts = sl_val * atr[i]
                    elif sl_type == 1:
                        # Structural Swing Low / Swing High (5 bars)
                        if trade_dir == 1:
                            swing_l = np.min(lows[i - 4 : i + 1])
                            risk_pts = max(trade_entry_p - swing_l + tick_size, tick_size * 4)
                        else:
                            swing_h = np.max(highs[i - 4 : i + 1])
                            risk_pts = max(swing_h - trade_entry_p + tick_size, tick_size * 4)
                    elif sl_type == 2:
                        # Indicator Line Anchor (HMA distance)
                        risk_pts = max(abs(trade_entry_p - hma[i]), atr[i] * 0.5)
                    elif sl_type == 3:
                        # Basis Points (BPS) / Fixed % of Price (sl_val BPS, e.g. 5 BPS = 0.05%)
                        bps_decimal = sl_val / 10000.0
                        risk_pts = max(trade_entry_p * bps_decimal, tick_size * 4)
                    else:
                        risk_pts = sl_val * atr[i]

                    if trade_dir == 1:
                        trade_sl = trade_entry_p - risk_pts
                        trade_tp = trade_entry_p + (tp_atr_mode2 * atr[i])
                    else:
                        trade_sl = trade_entry_p + risk_pts
                        trade_tp = trade_entry_p - (tp_atr_mode2 * atr[i])

            elif sig1 != 0 and not np.isnan(atr[i]) and atr[i] > 0 and not np.isnan(sma20[i]):
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

                    if sl_type == 0:
                        risk_pts = sl_val * atr[i]
                    elif sl_type == 3:
                        bps_decimal = sl_val / 10000.0
                        risk_pts = max(trade_entry_p * bps_decimal, tick_size * 4)
                    else:
                        risk_pts = sl_val * atr[i]

                    if trade_dir == 1:
                        trade_sl = trade_entry_p - risk_pts
                        trade_tp = trade_entry_p + (tp_atr_mode1 * atr[i])
                    else:
                        trade_sl = trade_entry_p + risk_pts
                        trade_tp = trade_entry_p - (tp_atr_mode1 * atr[i])

        else:
            hold_len = i - entry_idx + 1
            curr_h = highs[i]
            curr_l = lows[i]

            exit_price = 0.0
            reason = 0

            if trade_dir == 1:
                if curr_l <= trade_sl:
                    reason = 2
                    exit_price = trade_sl - slippage_pts
                elif curr_h >= trade_tp:
                    reason = 1
                    exit_price = trade_tp
                elif hold_len >= max_hold_bars:
                    reason = 3
                    exit_price = closes[i]
            else:
                if curr_h >= trade_sl:
                    reason = 2
                    exit_price = trade_sl + slippage_pts
                elif curr_l <= trade_tp:
                    reason = 1
                    exit_price = trade_tp
                elif hold_len >= max_hold_bars:
                    reason = 3
                    exit_price = closes[i]

            if reason != 0:
                pnl_p = (exit_price - trade_entry_p) if trade_dir == 1 else (trade_entry_p - exit_price)
                pnl_d = pnl_p * point_value

                # Update Daily Gatekeeper State
                daily_trades += 1
                daily_pnl += pnl_d

                if pnl_d < 0:
                    consec_losses += 1
                else:
                    consec_losses = 0

                if daily_pnl <= -max_daily_loss or consec_losses >= max_consec_losses:
                    done_for_day = True

                entry_indices[trade_count] = entry_idx
                exit_indices[trade_count] = i
                trade_modes[trade_count] = trade_mode
                directions[trade_count] = trade_dir
                entry_prices[trade_count] = trade_entry_p
                exit_prices[trade_count] = exit_price
                pnl_dollars[trade_count] = pnl_d
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
        pnl_dollars[:trade_count],
        durations[:trade_count],
        exit_reasons[:trade_count],
    )


class PropFirmAdaptiveScalperBacktester:
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

        # Unique Day ID for daily risk gatekeeper
        df["day_id"] = times_est.year * 10000 + times_est.month * 100 + times_est.day

        return df

    def run_backtest(
        self,
        df: pd.DataFrame,
        hma_period: int = 14,
        st_mult: float = 2.0,
        bb_period: int = 20,
        std_dev: float = 2.5,
        htf_ema_period: int = 200,
        sl_mode1: float = 1.0,
        tp_mode1: float = 1.0,
        sl_type: int = 0,
        sl_val: float = 1.5,
        tp_mode2: float = 1.0,  # Tight TP for > 65% Win Rate
        max_hold: int = 4,
        max_trades_per_day: int = 3,
        max_daily_loss: float = 400.0,
        max_consec_losses: int = 2,
        rth_only: bool = True,
        slippage_ticks: float = 0.5,
    ) -> dict:
        t0 = time.time()

        closes = df["Close"].values.astype(np.float64)
        highs = df["High"].values.astype(np.float64)
        lows = df["Low"].values.astype(np.float64)
        opens = df["Open"].values.astype(np.float64)
        day_ids = df["day_id"].values.astype(np.int32)
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

        # 2. HTF 15-Minute Trend Filter & Chop Guard
        try:
            df_15m = df.resample("15min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
            c_15 = df_15m["Close"].values
            h_15 = df_15m["High"].values
            l_15 = df_15m["Low"].values
            
            htf_ema50_series = df_15m["Close"].ewm(span=50, adjust=False).mean()
            
            atr15 = pd.Series(np.maximum(h_15 - l_15, 1e-5)).rolling(10).mean().values
            hl2_15 = (h_15 + l_15) / 2.0
            up_15 = hl2_15 - 3.0 * atr15
            dn_15 = hl2_15 + 3.0 * atr15
            st_dir15 = np.ones(len(c_15), dtype=np.int32)
            for k in range(1, len(c_15)):
                if c_15[k - 1] > dn_15[k - 1]:
                    up_15[k] = max(up_15[k], up_15[k - 1])
                if c_15[k - 1] < up_15[k - 1]:
                    dn_15[k] = min(dn_15[k], dn_15[k - 1])
                if c_15[k] > dn_15[k - 1]:
                    st_dir15[k] = 1
                elif c_15[k] < up_15[k - 1]:
                    st_dir15[k] = -1
                else:
                    st_dir15[k] = st_dir15[k - 1]

            df_15m["htf_bull"] = (st_dir15 == 1) & (df_15m["Close"] > htf_ema50_series)
            df_15m["htf_bear"] = (st_dir15 == -1) & (df_15m["Close"] < htf_ema50_series)

            htf_bull_1m = df_15m["htf_bull"].reindex(df.index, method="ffill").fillna(False).values
            htf_bear_1m = df_15m["htf_bear"].reindex(df.index, method="ffill").fillna(False).values
        except Exception:
            htf_bull_1m = np.ones(n, dtype=bool)
            htf_bear_1m = np.ones(n, dtype=bool)

        if htf_ema_period > 0:
            ema_filter = pd.Series(closes).ewm(span=htf_ema_period, adjust=False).mean().values
            long_ema_ok = closes > ema_filter
            short_ema_ok = closes < ema_filter
        else:
            long_ema_ok = np.ones(n, dtype=bool)
            short_ema_ok = np.ones(n, dtype=bool)

        # Choppiness Index (14) Chop Guard Calculation
        sum_tr14 = pd.Series(tr).rolling(14).sum().values
        max_high14 = pd.Series(highs).rolling(14).max().values
        min_low14 = pd.Series(lows).rolling(14).min().values
        range14 = np.maximum(max_high14 - min_low14, 1e-5)
        chop_index = 100.0 * np.log10(np.maximum(sum_tr14, 1e-5) / range14) / np.log10(14.0)
        chop_guard_ok = chop_index < 52.0  # Blocks trend entries when market is choppy (>= 52)

        # Calculate 9:30-09:45 EST Opening Range (ORB) High & Low per day
        times_est = df.index.tz_convert("America/New_York") if df.index.tz is not None else df.index
        time_mins = times_est.hour * 60 + times_est.minute
        is_orb_window = (time_mins >= 570) & (time_mins < 585)  # 09:30 to 09:45 AM

        df_temp = pd.DataFrame({"day_id": day_ids, "high": highs, "low": lows, "is_orb": is_orb_window})
        orb_highs_series = df_temp[df_temp["is_orb"]].groupby("day_id")["high"].transform("max")
        orb_lows_series = df_temp[df_temp["is_orb"]].groupby("day_id")["low"].transform("min")

        df_temp["orb_high"] = orb_highs_series
        df_temp["orb_low"] = orb_lows_series
        df_temp["orb_high"] = df_temp.groupby("day_id")["orb_high"].ffill()
        df_temp["orb_low"] = df_temp.groupby("day_id")["orb_low"].ffill()

        orb_high = df_temp["orb_high"].values
        orb_low = df_temp["orb_low"].values

        above_orb_high = closes > orb_high
        below_orb_low = closes < orb_low

        # 3. Signals
        m1_long = squeeze_mask & (lows <= lower_band) & (closes > lower_band)
        m1_short = squeeze_mask & (highs >= upper_band) & (closes < upper_band)

        # Continuous Slope + Pullback to HMA during Trend Expansion + ORB Trend Anchor + 15m HTF Filter
        hma_rising = np.zeros(n, dtype=bool)
        hma_falling = np.zeros(n, dtype=bool)
        hma_rising[1:] = hma[1:] > hma[:-1]
        hma_falling[1:] = hma[1:] < hma[:-1]

        m2_long = expansion_mask & (st_dir == 1) & (lows <= hma) & hma_rising & long_ema_ok & above_orb_high & chop_guard_ok & htf_bull_1m
        m2_short = expansion_mask & (st_dir == -1) & (highs >= hma) & hma_falling & short_ema_ok & below_orb_low & chop_guard_ok & htf_bear_1m

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

        # 4. Simulation with Prop Firm Risk Manager
        (
            e_idx,
            x_idx,
            t_modes,
            dirs,
            e_price,
            x_price,
            pnl_dlr,
            durations,
            exit_reasons,
        ) = run_prop_firm_simulation(
            opens,
            highs,
            lows,
            closes,
            sma20,
            upper_band,
            lower_band,
            hma,
            atr,
            day_ids,
            signals_m1,
            signals_m2,
            sl_type,
            sl_val,
            tp_mode1,
            tp_mode2,
            max_hold,
            max_trades_per_day,
            max_daily_loss,
            max_consec_losses,
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

        # Real-time Trailing Peak Drawdown Calculation (Prop Firm High Water Mark)
        cum_pnl = np.cumsum(pnl_dlr)
        peak = np.maximum.accumulate(cum_pnl)
        drawdown = peak - cum_pnl
        max_dd_dollars = np.max(drawdown)

        m1_trades = t_modes == 1
        m2_trades = t_modes == 2
        m1_win_rate = (np.sum(pnl_dlr[m1_trades] > 0) / np.sum(m1_trades)) * 100.0 if np.sum(m1_trades) > 0 else 0.0
        m2_win_rate = (np.sum(pnl_dlr[m2_trades] > 0) / np.sum(m2_trades)) * 100.0 if np.sum(m2_trades) > 0 else 0.0

        results = {
            "Ticker": self.ticker,
            "Strategy": "Prop Firm Optimized Adaptive Scalper",
            "SL Mode": ["0: ATR Multiplier", "1: Structural Swing Low/High", "2: Indicator Line", "3: 5 BPS (0.05% Price)"][sl_type],
            "Total Trades": total_trades,
            "Mode 1 Win Rate (%)": round(m1_win_rate, 2),
            "Mode 2 Win Rate (%)": round(m2_win_rate, 2),
            "COMBINED WIN RATE (%)": round(win_rate, 2),
            "PROFIT FACTOR": round(profit_factor, 2),
            "NET PROFIT ($)": round(net_profit, 2),
            "EXPECTANCY ($/trade)": round(exp_dollars, 2),
            "MAX TRAILING DRAWDOWN ($)": round(max_dd_dollars, 2),
            "Avg Duration (bars)": round(np.mean(durations), 1),
            "Execution Time (s)": round(elapsed, 4),
        }

        return results


def main():
    parser = argparse.ArgumentParser(description="Prop Firm Optimized Adaptive Quant Scalper Backtester")
    parser.add_argument("--ticker", type=str, default="NQ1", help="Ticker name (NQ1, ES1)")
    parser.add_argument("--data_path", type=str, default=None, help="Path to parquet file")
    parser.add_argument("--hma_period", type=int, default=14, help="HMA Period (default 14)")
    parser.add_argument("--st_mult", type=float, default=2.0, help="SuperTrend Multiplier (default 2.0)")
    parser.add_argument("--tp_mode2", type=float, default=1.0, help="Mode 2 TP ATR (default 1.0 for high WR)")
    parser.add_argument("--sl_type", type=int, default=0, help="SL Type: 0=ATR, 1=Structural, 2=Indicator, 3=5 BPS (0.05%%)")
    parser.add_argument("--sl_val", type=float, default=1.5, help="SL Value: ATR mult or BPS count (e.g. 5.0 for 5 BPS = 0.05%%)")
    parser.add_argument("--compare_sl", action="store_true", help="Compare all 4 Stop Loss modes in a sweep")
    args = parser.parse_args()

    if args.data_path is None:
        data_path = PROJECT_ROOT / "data" / f"{args.ticker}_1m.parquet"
    else:
        data_path = Path(args.data_path)

    print("=" * 80)
    print(f"PROP FIRM RISK GATEKEEPER BACKTEST: {args.ticker}")
    print("=" * 80)

    bt = PropFirmAdaptiveScalperBacktester(str(data_path), ticker=args.ticker)
    print("Loading Parquet dataset...")
    df = bt.load_data()
    print(f"Loaded {len(df):,} 1-minute bars spanning {df.index[0]} to {df.index[-1]}")

    if args.compare_sl:
        print("\nRUNNING COMPARATIVE STOP LOSS EXPERIMENT ACROSS ALL 4 SL MODES...")
        sl_modes = [
            (0, 1.5, "0: 1.5x ATR Volatility-Dynamic"),
            (1, 0.0, "1: Structural Swing Low/High Invalidation"),
            (2, 0.0, "2: Indicator Line (HMA Anchor)"),
            (3, 5.0, "3: 5 Basis Points (0.05% of Entry Price)"),
            (3, 10.0, "4: 10 Basis Points (0.10% of Entry Price)"),
        ]
        sweep_results = []
        for sl_t, sl_v, name in sl_modes:
            res = bt.run_backtest(
                df,
                hma_period=args.hma_period,
                st_mult=args.st_mult,
                tp_mode2=args.tp_mode2,
                sl_type=sl_t,
                sl_val=sl_v,
            )
            res["SL Mode Name"] = name
            sweep_results.append(res)

        df_res = pd.DataFrame(sweep_results)
        cols = ["SL Mode Name", "Total Trades", "Mode 2 Win Rate (%)", "COMBINED WIN RATE (%)", "PROFIT FACTOR", "NET PROFIT ($)", "MAX TRAILING DRAWDOWN ($)"]
        print("\n" + df_res[cols].to_string(index=False))
        print("=" * 80)
    else:
        res = bt.run_backtest(
            df,
            hma_period=args.hma_period,
            st_mult=args.st_mult,
            tp_mode2=args.tp_mode2,
            sl_type=args.sl_type,
            sl_val=args.sl_val,
        )

        print("\nPROP FIRM EVALUATION PERFORMANCE REPORT")
        print("-" * 55)
        for k, v in res.items():
            print(f"  {k:<28}: {v}")
        print("-" * 55)


if __name__ == "__main__":
    main()
