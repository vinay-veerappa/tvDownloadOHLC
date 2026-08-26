"""
Keltner Channel APEX Strategy Backtesting & Parity Engine
Evaluates multiple strategy archetypes on NQ, MNQ, ES, and MES 5m data:
  1. Naive Mean Reversion (Raw %B Reversal)
  2. WaveTrend-Filtered Mean Reversion
  3. Regime-Filtered Mean Reversion (Trend Slope Gate + WT)
  4. Trend-Pullback Continuation Strategy
  5. Adaptive Hybrid Strategy (Pullbacks in Trend, Fades in Range)

Features full institutional trade management mirroring RiskManagerBase:
  - ATR/Swing structural stop loss with point risk cap
  - R-multiple & Centerline targets
  - Breakeven trigger at 1.0R
  - Max Daily Loss & Max Trades Per Day circuit breakers
  - Exact futures point values, tick size, slippage, and exchange commissions
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Multiplier & Cost Specifications
INSTRUMENT_SPECS = {
    "NQ": {
        "parquet": "data/NQ1_5m.parquet",
        "point_value": 20.0,
        "tick_size": 0.25,
        "commission": 2.05,
        "slippage_ticks": 1,
        "max_risk_pts": 40.0,
        "default_slope_thresh": 3.0,
    },
    "MNQ": {
        "parquet": "data/NQ1_5m.parquet",
        "point_value": 2.0,
        "tick_size": 0.25,
        "commission": 0.55,
        "slippage_ticks": 1,
        "max_risk_pts": 40.0,
        "default_slope_thresh": 3.0,
    },
    "ES": {
        "parquet": "data/ES1_5m.parquet",
        "point_value": 50.0,
        "tick_size": 0.25,
        "commission": 2.05,
        "slippage_ticks": 1,
        "max_risk_pts": 10.0,
        "default_slope_thresh": 0.75,
    },
    "MES": {
        "parquet": "data/ES1_5m.parquet",
        "point_value": 5.0,
        "tick_size": 0.25,
        "commission": 0.55,
        "slippage_ticks": 1,
        "max_risk_pts": 10.0,
        "default_slope_thresh": 0.75,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# ══ FAST VECTORIZED INDICATOR HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def compute_ema(series: np.ndarray, length: int) -> np.ndarray:
    alpha = 2.0 / (length + 1.0)
    out = np.empty_like(series, dtype=np.float64)
    out[0] = series[0]
    for i in range(1, len(series)):
        out[i] = alpha * series[i] + (1.0 - alpha) * out[i - 1]
    return out


def compute_sma(series: np.ndarray, length: int) -> np.ndarray:
    return pd.Series(series).rolling(window=length, min_periods=1).mean().to_numpy()


def compute_ma_variant(series: np.ndarray, length: int, ma_type: str = "EMA") -> np.ndarray:
    ma = ma_type.upper()
    if ma == "SMA":
        return compute_sma(series, length)
    else:
        return compute_ema(series, length)


def compute_true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    return np.maximum(tr1, np.maximum(tr2, tr3))


def compute_wavetrend(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                      channel_len: int = 10, ma_len: int = 3, smooth_len: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    hlc3 = (high + low + close) / 3.0
    wt_ma = compute_ema(hlc3, channel_len)
    wt_diff = compute_ema(np.abs(hlc3 - wt_ma), channel_len)
    denom = 0.015 * wt_diff
    denom = np.where(denom == 0, 1e-6, denom)
    wt_ci = (hlc3 - wt_ma) / denom
    wt1 = compute_ema(wt_ci, ma_len)
    wt2 = compute_sma(wt1, smooth_len)
    return wt1, wt2


# ══════════════════════════════════════════════════════════════════════════════
# ══ CONFIGURATION & PREPARATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StrategyConfig:
    symbol: str = "NQ"
    point_value: float = 20.0
    tick_size: float = 0.25
    slippage_pts: float = 0.25
    commission_per_contract: float = 2.05
    max_risk_pts: float = 40.0

    # Keltner Base Parameters
    ma_type: str = "EMA"
    ma_length: int = 34
    atr_ma_type: str = "EMA"
    atr_length: int = 88
    atr_mult_min: float = 1.5
    atr_mult_max: float = 3.5

    # %B Deviation Parameters
    dev_length: int = 34
    dev_multiplier: float = 2.0
    overbought: float = 1.0
    oversold: float = 0.0

    # WaveTrend Parameters
    wt_channel_len: int = 10
    wt_ma_len: int = 3
    wt_smooth_len: int = 3
    wt_ob_thresh: float = 70.0
    wt_os_thresh: float = -70.0

    # Trend / Slope Filter
    trend_slope_len: int = 10
    trend_slope_thresh_pts: float = 3.0

    # Strategy Mode
    mode: str = "AdaptiveHybrid"

    # Risk Management & Exits
    stop_atr_mult: float = 1.0
    target_r_multiple: float = 2.0
    use_breakeven: bool = True
    breakeven_trigger_r: float = 1.0

    # Session & Risk Gates
    earliest_entry_time: int = 930   # 09:30 EST
    latest_entry_time: int = 1530    # 15:30 EST
    flatten_time: int = 1600         # 16:00 EST
    max_daily_loss: float = 1000.0   # $
    max_trades_per_day: int = 4


@dataclass
class Trade:
    trade_id: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: int            # 1 for Long, -1 for Short
    strategy_mode: str
    entry_price: float
    exit_price: float
    contracts: int
    gross_pnl_pts: float
    gross_pnl_dollars: float
    net_pnl_dollars: float
    bars_held: int
    exit_reason: str


def prepare_keltner_dataset(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    df = df.copy()
    close = df['close'].to_numpy(dtype=np.float64)
    high = df['high'].to_numpy(dtype=np.float64)
    low = df['low'].to_numpy(dtype=np.float64)
    
    # 1. Keltner Centerline and Range
    df['kc_mid'] = compute_ma_variant(close, cfg.ma_length, cfg.ma_type)
    df['tr'] = compute_true_range(high, low, close)
    df['kc_range'] = compute_ma_variant(df['tr'].to_numpy(), cfg.atr_length, cfg.atr_ma_type)
    
    # 2. Dual Keltner Bands
    df['kc_top_min'] = df['kc_mid'] + df['kc_range'] * cfg.atr_mult_min
    df['kc_top_max'] = df['kc_mid'] + df['kc_range'] * cfg.atr_mult_max
    df['kc_bot_min'] = df['kc_mid'] - df['kc_range'] * cfg.atr_mult_min
    df['kc_bot_max'] = df['kc_mid'] - df['kc_range'] * cfg.atr_mult_max
    
    # 3. %B Bollinger/Keltner Bands
    df['stdev'] = df['close'].rolling(cfg.dev_length, min_periods=cfg.dev_length).std().bfill()
    df['dev'] = cfg.dev_multiplier * df['stdev']
    df['sig_upper'] = df['kc_mid'] + df['dev']
    df['sig_lower'] = df['kc_mid'] - df['dev']
    
    spread = df['sig_upper'] - df['sig_lower']
    df['bbr'] = np.where(spread > 1e-6, (df['close'] - df['sig_lower']) / spread, 0.5)
    
    # 4. WaveTrend
    df['wt1'], df['wt2'] = compute_wavetrend(
        high, low, close, cfg.wt_channel_len, cfg.wt_ma_len, cfg.wt_smooth_len
    )
    
    # 5. ATR for Stop Loss calculation
    df['atr'] = df['tr'].rolling(14, min_periods=1).mean()
    
    # 6. Trend Slope
    df['kc_mid_slope'] = df['kc_mid'] - df['kc_mid'].shift(cfg.trend_slope_len).fillna(0)
    
    # 7. Raw Signal Triggers
    bbr_prev = df['bbr'].shift(1).fillna(0.5)
    df['sig_sell_bbr'] = (bbr_prev > cfg.overbought) & (df['bbr'] < cfg.overbought)
    df['sig_buy_bbr'] = (bbr_prev < cfg.oversold) & (df['bbr'] > cfg.oversold)
    
    # Support and Resistance persistent tracking
    res_levels = np.zeros(len(df), dtype=np.float64)
    sup_levels = np.zeros(len(df), dtype=np.float64)
    
    high_prev = df['high'].shift(1).to_numpy()
    low_prev = df['low'].shift(1).to_numpy()
    sell_sig = df['sig_sell_bbr'].to_numpy()
    buy_sig = df['sig_buy_bbr'].to_numpy()
    
    curr_res = high[0]
    curr_sup = low[0]
    for i in range(len(df)):
        if sell_sig[i] and i >= 1:
            curr_res = high_prev[i]
        if buy_sig[i] and i >= 1:
            curr_sup = low_prev[i]
        res_levels[i] = curr_res
        sup_levels[i] = curr_sup
        
    df['res_level'] = res_levels
    df['sup_level'] = sup_levels
    
    return df


# ══════════════════════════════════════════════════════════════════════════════
# ══ EVENT SIMULATION
# ══════════════════════════════════════════════════════════════════════════════

def run_backtest_simulation(df: pd.DataFrame, cfg: StrategyConfig) -> Tuple[pd.DataFrame, Dict]:
    if 'kc_mid' in df.columns:
        df_prep = df
    else:
        df_prep = prepare_keltner_dataset(df, cfg)
    
    times = df_prep['datetime'].to_numpy()
    dates = df_prep['date'].to_numpy()
    clock_times = df_prep['time'].to_numpy()
    opens = df_prep['open'].to_numpy()
    highs = df_prep['high'].to_numpy()
    lows = df_prep['low'].to_numpy()
    closes = df_prep['close'].to_numpy()
    
    kc_mids = df_prep['kc_mid'].to_numpy()
    kc_top_mins = df_prep['kc_top_min'].to_numpy()
    kc_bot_mins = df_prep['kc_bot_min'].to_numpy()
    
    wt1s = df_prep['wt1'].to_numpy()
    wt2s = df_prep['wt2'].to_numpy()
    atrs = df_prep['atr'].to_numpy()
    slopes = df_prep['kc_mid_slope'].to_numpy()
    
    sig_buy_bbr = df_prep['sig_buy_bbr'].to_numpy()
    sig_sell_bbr = df_prep['sig_sell_bbr'].to_numpy()
    res_levels = df_prep['res_level'].to_numpy()
    sup_levels = df_prep['sup_level'].to_numpy()
    
    trades: List[Trade] = []
    
    in_position = False
    pos_dir = 0
    pos_entry_price = 0.0
    pos_entry_idx = 0
    pos_stop_loss = 0.0
    pos_target_1 = 0.0
    pos_target_2 = 0.0
    pos_is_breakeven = False
    pos_contracts = 1
    pos_mode = ""
    
    current_date = None
    daily_pnl_dollars = 0.0
    daily_trades_count = 0
    
    n_bars = len(df_prep)
    warmup = max(cfg.ma_length, cfg.atr_length, cfg.dev_length, cfg.trend_slope_len) + 5
    
    for i in range(warmup, n_bars - 1):
        d = dates[i]
        t = clock_times[i]
        
        # Reset Day
        if d != current_date:
            current_date = d
            daily_pnl_dollars = 0.0
            daily_trades_count = 0
            
        daily_locked = (daily_pnl_dollars <= -cfg.max_daily_loss) or (daily_trades_count >= cfg.max_trades_per_day)
        
        # ── 1. MANAGE OPEN POSITION ──
        if in_position:
            bars_held = i - pos_entry_idx
            bar_h = highs[i]
            bar_l = lows[i]
            bar_c = closes[i]
            bar_o = opens[i]
            
            trade_closed = False
            exit_price = 0.0
            exit_reason = ""
            
            if t >= cfg.flatten_time:
                exit_price = bar_c - (pos_dir * cfg.slippage_pts)
                exit_reason = "SessionClose"
                trade_closed = True
            elif pos_dir == 1:
                if bar_l <= pos_stop_loss:
                    exit_price = min(bar_o, pos_stop_loss) - cfg.slippage_pts
                    exit_reason = "Breakeven" if pos_is_breakeven else "StopLoss"
                    trade_closed = True
                elif bar_h >= pos_target_2:
                    exit_price = max(bar_o, pos_target_2) - cfg.slippage_pts
                    exit_reason = "Target2"
                    trade_closed = True
                elif bar_h >= pos_target_1:
                    if cfg.use_breakeven and not pos_is_breakeven:
                        pos_stop_loss = pos_entry_price
                        pos_is_breakeven = True
            elif pos_dir == -1:
                if bar_h >= pos_stop_loss:
                    exit_price = max(bar_o, pos_stop_loss) + cfg.slippage_pts
                    exit_reason = "Breakeven" if pos_is_breakeven else "StopLoss"
                    trade_closed = True
                elif bar_l <= pos_target_2:
                    exit_price = min(bar_o, pos_target_2) + cfg.slippage_pts
                    exit_reason = "Target2"
                    trade_closed = True
                elif bar_l <= pos_target_1:
                    if cfg.use_breakeven and not pos_is_breakeven:
                        pos_stop_loss = pos_entry_price
                        pos_is_breakeven = True
            
            if trade_closed:
                gross_pts = (exit_price - pos_entry_price) * pos_dir
                gross_dollars = gross_pts * cfg.point_value * pos_contracts
                net_dollars = gross_dollars - (cfg.commission_per_contract * pos_contracts)
                
                daily_pnl_dollars += net_dollars
                trades.append(Trade(
                    trade_id=len(trades) + 1,
                    entry_time=pd.Timestamp(times[pos_entry_idx]),
                    exit_time=pd.Timestamp(times[i]),
                    direction=pos_dir,
                    strategy_mode=pos_mode,
                    entry_price=pos_entry_price,
                    exit_price=exit_price,
                    contracts=pos_contracts,
                    gross_pnl_pts=gross_pts,
                    gross_pnl_dollars=gross_dollars,
                    net_pnl_dollars=net_dollars,
                    bars_held=bars_held,
                    exit_reason=exit_reason
                ))
                in_position = False
                pos_dir = 0
                continue
        
        # ── 2. SIGNAL GENERATION ──
        if in_position or daily_locked:
            continue
            
        if not (cfg.earliest_entry_time <= t <= cfg.latest_entry_time):
            continue
            
        signal_long = False
        signal_short = False
        trade_mode_tag = ""
        
        is_trending_up = slopes[i] > cfg.trend_slope_thresh_pts
        is_trending_down = slopes[i] < -cfg.trend_slope_thresh_pts
        is_ranging = not is_trending_up and not is_trending_down
        
        if cfg.mode == "NaiveMeanReversion":
            if sig_buy_bbr[i]:
                signal_long = True
                trade_mode_tag = "Naive_MR_Long"
            elif sig_sell_bbr[i]:
                signal_short = True
                trade_mode_tag = "Naive_MR_Short"
                
        elif cfg.mode == "WaveTrendMeanReversion":
            if sig_buy_bbr[i] and (wt2s[i] < cfg.wt_os_thresh or wt1s[i] < -50):
                signal_long = True
                trade_mode_tag = "WT_MR_Long"
            elif sig_sell_bbr[i] and (wt2s[i] > cfg.wt_ob_thresh or wt1s[i] > 50):
                signal_short = True
                trade_mode_tag = "WT_MR_Short"
                
        elif cfg.mode == "RegimeMeanReversion":
            if is_ranging or (wt2s[i] < cfg.wt_os_thresh):
                if sig_buy_bbr[i] and not is_trending_down:
                    signal_long = True
                    trade_mode_tag = "Regime_MR_Long"
            if is_ranging or (wt2s[i] > cfg.wt_ob_thresh):
                if sig_sell_bbr[i] and not is_trending_up:
                    signal_short = True
                    trade_mode_tag = "Regime_MR_Short"
                    
        elif cfg.mode == "TrendPullback":
            if is_trending_up:
                if lows[i] <= kc_mids[i] and closes[i] > kc_mids[i] and wt1s[i] > wt2s[i]:
                    signal_long = True
                    trade_mode_tag = "Trend_PB_Long"
            elif is_trending_down:
                if highs[i] >= kc_mids[i] and closes[i] < kc_mids[i] and wt1s[i] < wt2s[i]:
                    signal_short = True
                    trade_mode_tag = "Trend_PB_Short"
                    
        elif cfg.mode == "AdaptiveHybrid":
            if is_trending_up:
                if (lows[i] <= kc_mids[i] or lows[i] <= kc_bot_mins[i]) and closes[i] > kc_mids[i] and wt1s[i] > wt2s[i]:
                    signal_long = True
                    trade_mode_tag = "Adaptive_PB_Long"
            elif is_trending_down:
                if (highs[i] >= kc_mids[i] or highs[i] >= kc_top_mins[i]) and closes[i] < kc_mids[i] and wt1s[i] < wt2s[i]:
                    signal_short = True
                    trade_mode_tag = "Adaptive_PB_Short"
            else:
                if sig_buy_bbr[i] and wt2s[i] < -60:
                    signal_long = True
                    trade_mode_tag = "Adaptive_MR_Long"
                elif sig_sell_bbr[i] and wt2s[i] > 60:
                    signal_short = True
                    trade_mode_tag = "Adaptive_MR_Short"
        
        # ── 3. EXECUTE ENTRY ──
        if signal_long or signal_short:
            next_open = opens[i + 1]
            atr_val = atrs[i]
            
            if signal_long:
                entry_p = next_open + cfg.slippage_pts
                sl = max(lows[i] - (cfg.stop_atr_mult * atr_val), entry_p - cfg.max_risk_pts)
                risk = max(entry_p - sl, cfg.tick_size * 4)
                tp1 = entry_p + (cfg.breakeven_trigger_r * risk)
                tp2 = entry_p + (cfg.target_r_multiple * risk)
                
                in_position = True
                pos_dir = 1
                pos_entry_price = entry_p
                pos_entry_idx = i + 1
                pos_stop_loss = sl
                pos_target_1 = tp1
                pos_target_2 = tp2
                pos_is_breakeven = False
                pos_contracts = 1
                pos_mode = trade_mode_tag
                daily_trades_count += 1
                
            elif signal_short:
                entry_p = next_open - cfg.slippage_pts
                sl = min(highs[i] + (cfg.stop_atr_mult * atr_val), entry_p + cfg.max_risk_pts)
                risk = max(sl - entry_p, cfg.tick_size * 4)
                tp1 = entry_p - (cfg.breakeven_trigger_r * risk)
                tp2 = entry_p - (cfg.target_r_multiple * risk)
                
                in_position = True
                pos_dir = -1
                pos_entry_price = entry_p
                pos_entry_idx = i + 1
                pos_stop_loss = sl
                pos_target_1 = tp1
                pos_target_2 = tp2
                pos_is_breakeven = False
                pos_contracts = 1
                pos_mode = trade_mode_tag
                daily_trades_count += 1

    trades_df = pd.DataFrame([t.__dict__ for t in trades]) if trades else pd.DataFrame()
    metrics = calculate_metrics(trades_df)
    return trades_df, metrics


def calculate_metrics(trades_df: pd.DataFrame) -> Dict:
    if trades_df.empty:
        return {
            "Total Trades": 0, "Win Rate (%)": 0.0, "Profit Factor": 0.0,
            "Net PnL ($)": 0.0, "Max Drawdown ($)": 0.0, "Average Trade ($)": 0.0,
            "Sharpe Ratio": 0.0, "Long Trades": 0, "Short Trades": 0,
        }
        
    total_trades = len(trades_df)
    wins = trades_df[trades_df['net_pnl_dollars'] > 0]
    losses = trades_df[trades_df['net_pnl_dollars'] <= 0]
    
    win_rate = (len(wins) / total_trades) * 100.0 if total_trades > 0 else 0.0
    gross_profits = wins['net_pnl_dollars'].sum()
    gross_losses = abs(losses['net_pnl_dollars'].sum())
    pf = (gross_profits / gross_losses) if gross_losses > 0 else (99.0 if gross_profits > 0 else 0.0)
    net_pnl = trades_df['net_pnl_dollars'].sum()
    avg_trade = trades_df['net_pnl_dollars'].mean()
    
    equity = trades_df['net_pnl_dollars'].cumsum()
    peak = equity.cummax()
    drawdown = peak - equity
    max_dd = drawdown.max()
    
    trades_df['date'] = trades_df['entry_time'].dt.date
    daily_pnl = trades_df.groupby('date')['net_pnl_dollars'].sum()
    sharpe = (daily_pnl.mean() / daily_pnl.std() * np.sqrt(252)) if (len(daily_pnl) > 1 and daily_pnl.std() > 0) else 0.0
    
    return {
        "Total Trades": total_trades,
        "Win Rate (%)": round(win_rate, 2),
        "Profit Factor": round(pf, 2),
        "Net PnL ($)": round(net_pnl, 2),
        "Max Drawdown ($)": round(max_dd, 2),
        "Average Trade ($)": round(avg_trade, 2),
        "Sharpe Ratio": round(sharpe, 2),
        "Long Trades": len(trades_df[trades_df['direction'] == 1]),
        "Short Trades": len(trades_df[trades_df['direction'] == -1]),
    }


# ══════════════════════════════════════════════════════════════════════════════
# ══ MULTI-ASSET (ES + NQ) BENCHMARK RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_es_and_nq_backtests(start_year: int = 2023) -> pd.DataFrame:
    symbols = ["NQ", "ES"]
    archetypes = [
        ("1. Naive Mean Reversion", "NaiveMeanReversion"),
        ("2. WaveTrend Filtered MR", "WaveTrendMeanReversion"),
        ("3. Regime Filtered MR", "RegimeMeanReversion"),
        ("4. Trend Pullback Strategy", "TrendPullback"),
        ("5. Adaptive Hybrid Strategy", "AdaptiveHybrid"),
    ]
    
    all_results = []
    
    for sym in symbols:
        spec = INSTRUMENT_SPECS[sym]
        data_path = Path(spec["parquet"])
        if not data_path.exists():
            print(f"Error: {data_path} not found.")
            continue
            
        print(f"\n{'='*70}\n[Loading Data] Loading {sym} 5m data from {data_path}...\n{'='*70}")
        df = pd.read_parquet(data_path)
        df['datetime_utc'] = pd.to_datetime(df.index, utc=True)
        df = df.reset_index(drop=True)
        df['datetime'] = df['datetime_utc'].dt.tz_convert('America/New_York')
        df['time'] = df['datetime'].dt.hour * 100 + df['datetime'].dt.minute
        df['date'] = df['datetime'].dt.date
        df = df.drop(columns=['datetime_utc']).sort_values('datetime').reset_index(drop=True)
        
        df = df[df['datetime'].dt.year >= start_year].reset_index(drop=True)
        print(f"[{sym} Filtered] {len(df):,} bars from {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
        
        for name, mode in archetypes:
            cfg = StrategyConfig(
                symbol=sym,
                point_value=spec["point_value"],
                tick_size=spec["tick_size"],
                slippage_pts=spec["tick_size"] * spec["slippage_ticks"],
                commission_per_contract=spec["commission"],
                max_risk_pts=spec["max_risk_pts"],
                trend_slope_thresh_pts=spec["default_slope_thresh"],
                mode=mode
            )
            trades_df, metrics = run_backtest_simulation(df, cfg)
            metrics["Symbol"] = sym
            metrics["Archetype"] = name
            all_results.append(metrics)
            print(f"[{sym}] {name:30s} | Net PnL: ${metrics['Net PnL ($)']:>10,.2f} | WinRate: {metrics['Win Rate (%)']:>5.1f}% | PF: {metrics['Profit Factor']:>4.2f} | Trades: {metrics['Total Trades']:>5d} | MaxDD: ${metrics['Max Drawdown ($)']:>8,.2f}")
            
    summary_df = pd.DataFrame(all_results)
    cols = ["Symbol", "Archetype", "Total Trades", "Win Rate (%)", "Profit Factor", "Net PnL ($)", "Max Drawdown ($)", "Average Trade ($)", "Sharpe Ratio"]
    summary_df = summary_df[cols]
    
    print("\n" + "="*95)
    print(f"MULTI-ASSET KELTNER CHANNEL STRATEGY COMPARISON ({start_year}-2026)")
    print("="*95)
    print(summary_df.to_string(index=False))
    print("="*95)
    
    out_dir = Path("results/keltner_backtest")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(out_dir / f"keltner_es_nq_comparison_{start_year}_2026.csv", index=False)
    print(f"\nSaved summary to {out_dir / f'keltner_es_nq_comparison_{start_year}_2026.csv'}")
    
    return summary_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Keltner Channel Multi-Asset Backtester")
    parser.add_argument("--start_year", type=int, default=2023, help="Start year (default 2023)")
    args = parser.parse_args()
    
    run_es_and_nq_backtests(start_year=args.start_year)
