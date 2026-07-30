"""
Faster vectorized backtest for EMAPullBackBot-like rules on NQ 5m data.
Avoids df.iloc per bar; uses numpy arrays and pre-computed daily session info.
"""
import pandas as pd
import numpy as np
import talib
from dataclasses import dataclass, asdict
from typing import Dict, List
from pathlib import Path
import json

POINT_VALUE = 20.0


def load_nq_5m() -> pd.DataFrame:
    df = pd.read_parquet(r'C:\Users\vinay\tvDownloadOHLC\data\NQ1_5m.parquet')
    df['datetime_utc'] = pd.to_datetime(df.index, utc=True)
    df = df.reset_index(drop=True)
    df['datetime'] = df['datetime_utc'].dt.tz_convert('America/New_York')
    df['time'] = df['datetime'].dt.hour * 100 + df['datetime'].dt.minute
    df['minute'] = df['datetime'].dt.hour * 60 + df['datetime'].dt.minute
    df['date'] = df['datetime'].dt.date
    df = df.drop(columns=['datetime_utc']).sort_values('datetime').reset_index(drop=True)
    return df


def anchored_vwap_values(df: pd.DataFrame, anchor_min: int = 9 * 60 + 30) -> np.ndarray:
    typical = (df['high'].values + df['low'].values + df['close'].values) / 3.0
    volume = df['volume'].values
    minute = df['minute'].values
    dates = df['date'].values
    n = len(df)
    pv = typical * volume
    cum_pv = np.zeros(n)
    cum_vol = np.zeros(n)
    for i in range(n):
        if i == 0 or dates[i] != dates[i - 1]:
            session_start = i
        if minute[i] >= anchor_min:
            if i == session_start or minute[i - 1] < anchor_min:
                anchor_idx = i
            if i == session_start:
                cum_pv[i] = pv[i]
                cum_vol[i] = volume[i]
            else:
                cum_pv[i] = cum_pv[i - 1] + pv[i]
                cum_vol[i] = cum_vol[i - 1] + volume[i]
        else:
            cum_pv[i] = 0
            cum_vol[i] = 0
    return np.where(cum_vol > 0, cum_pv / cum_vol, df['close'].values)


@dataclass
class BacktestConfig:
    symbol: str = 'NQ'
    point_value: float = POINT_VALUE
    stop_atr_mult: float = 1.25
    target_r_multiple: float = 3.75
    trade_policy: str = 'FixedTarget'
    breakeven_trigger_r: float = 1.0
    trail_atr_mult: float = 2.0
    atr_period: int = 14
    earliest_entry: int = 945
    latest_entry: int = 1100
    flatten_by: int = 1545
    daily_max_loss: float = 400.0
    max_trades_per_day: int = 3
    max_consec_losers_pause: int = 2
    pause_minutes: int = 30
    hard_stop_consec_losers: int = 3
    ema_period: int = 20
    min_move_from_open: float = 4.0
    pullback_proximity: float = 0.3
    min_pullback_bars: int = 2
    use_engulfing: bool = True
    use_vwap_filter: bool = False
    vwap_min_distance_atr: float = 0.0
    use_volume_filter: bool = False
    volume_lookback: int = 20
    volume_percentile: float = 50.0
    use_adx_filter: bool = False
    adx_period: int = 14
    adx_min: float = 20.0
    dynamic_target: bool = False
    target_cap_r: float = 5.0
    target_floor_r: float = 1.5


def run_backtest(df: pd.DataFrame, cfg: BacktestConfig) -> Dict:
    open_ = df['open'].values
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    volume = df['volume'].values
    t = df['time'].values
    minute = df['minute'].values
    dates = df['date'].values
    datetimes = df['datetime'].values
    n = len(df)

    ema = talib.EMA(close, timeperiod=cfg.ema_period)
    atr = talib.ATR(high, low, close, timeperiod=cfg.atr_period)
    adx = talib.ADX(high, low, close, timeperiod=cfg.adx_period) if cfg.use_adx_filter else np.zeros(n)
    vwap = anchored_vwap_values(df) if cfg.use_vwap_filter else np.zeros(n)
    vol_pct = np.zeros(n)
    if cfg.use_volume_filter:
        for i in range(n):
            start = max(0, i - cfg.volume_lookback)
            vol_pct[i] = np.percentile(volume[start:i], cfg.volume_percentile) if i > 0 else volume[0]

    in_pos = np.zeros(n, dtype=int)
    entry_prices = np.zeros(n)
    stop_prices = np.zeros(n)
    risk_points = np.zeros(n)
    be_moved = np.zeros(n, dtype=bool)
    trades: List[Dict] = []

    today_trade_count = 0
    consec_losers = 0
    session_pnl = 0.0
    is_paused = False
    pause_until = -1
    is_done = False
    account_equity = 0.0
    high_water = 0.0

    session_open = 0.0
    session_high = -np.inf
    session_low = np.inf
    initial_move_detected = False
    move_direction = 0
    pullback_bars = 0
    last_signal_date = None
    current_date = None

    for i in range(1, n):
        if dates[i] != current_date:
            if current_date is not None:
                account_equity += session_pnl
                high_water = max(high_water, account_equity)
            current_date = dates[i]
            today_trade_count = 0
            consec_losers = 0
            session_pnl = 0.0
            is_paused = False
            is_done = False
            session_open = 0.0
            session_high = -np.inf
            session_low = np.inf
            initial_move_detected = False
            move_direction = 0
            pullback_bars = 0
            last_signal_date = None

        if t[i] < 930:
            continue

        if session_open == 0.0:
            session_open = open_[i]
            session_high = high[i]
            session_low = low[i]
        else:
            session_high = max(session_high, high[i])
            session_low = min(session_low, low[i])

        if np.isnan(atr[i]) or atr[i] <= 0:
            continue

        if t[i] >= cfg.flatten_by and in_pos[i - 1] != 0:
            _close_trade(trades, i - 1, in_pos[i - 1], close[i], cfg.point_value, 'flatten_time', datetimes[i])
            in_pos[i] = 0
            continue

        if in_pos[i - 1] != 0:
            pos = in_pos[i - 1]
            entry = entry_prices[i - 1]
            stop = stop_prices[i - 1]
            risk = risk_points[i - 1]
            be = be_moved[i - 1]
            unrealized = (close[i] - entry) * pos * cfg.point_value
            if session_pnl + unrealized <= -cfg.daily_max_loss:
                _close_trade(trades, i, pos, close[i], cfg.point_value, 'daily_max_loss', datetimes[i])
                session_pnl += trades[-1]['pnl']
                is_done = True
                consec_losers = _update_consec(trades[-1]['pnl'], consec_losers)
                in_pos[i] = 0
                continue

            # Stop hit
            if (pos == 1 and low[i] <= stop) or (pos == -1 and high[i] >= stop):
                exit_p = stop
                _close_trade(trades, i, pos, exit_p, cfg.point_value, 'stop', datetimes[i])
                session_pnl += trades[-1]['pnl']
                consec_losers = _update_consec(trades[-1]['pnl'], consec_losers)
                in_pos[i] = 0
                continue

            if cfg.trade_policy == 'FixedTarget':
                target = entry + cfg.target_r_multiple * risk * pos
                if (pos == 1 and high[i] >= target) or (pos == -1 and low[i] <= target):
                    _close_trade(trades, i, pos, target, cfg.point_value, 'target', datetimes[i])
                    session_pnl += trades[-1]['pnl']
                    consec_losers = _update_consec(trades[-1]['pnl'], consec_losers)
                    in_pos[i] = 0
                    continue
            else:
                current_r = ((close[i] - entry) * pos) / risk
                if not be and current_r >= cfg.breakeven_trigger_r:
                    be = True
                    stop = entry
                if be:
                    trail_dist = cfg.trail_atr_mult * atr[i]
                    if pos == 1:
                        new_stop = close[i] - trail_dist
                        if new_stop > stop:
                            stop = new_stop
                    else:
                        new_stop = close[i] + trail_dist
                        if new_stop < stop:
                            stop = new_stop
                if (pos == 1 and low[i] <= stop) or (pos == -1 and high[i] >= stop):
                    _close_trade(trades, i, pos, stop, cfg.point_value, 'trail_stop', datetimes[i])
                    session_pnl += trades[-1]['pnl']
                    consec_losers = _update_consec(trades[-1]['pnl'], consec_losers)
                    in_pos[i] = 0
                    continue

            in_pos[i] = pos
            entry_prices[i] = entry
            stop_prices[i] = stop
            risk_points[i] = risk
            be_moved[i] = be
            continue

        # Entry gate
        if t[i] < cfg.earliest_entry or t[i] > cfg.latest_entry:
            continue
        if is_done:
            continue
        if is_paused and minute[i] < pause_until:
            continue
        elif is_paused:
            is_paused = False
        if today_trade_count >= cfg.max_trades_per_day:
            continue
        if consec_losers >= cfg.hard_stop_consec_losers:
            is_done = True
            continue

        risk_distance = cfg.stop_atr_mult * atr[i]
        potential_loss = risk_distance * cfg.point_value
        if session_pnl - potential_loss < -cfg.daily_max_loss:
            continue

        if last_signal_date == current_date:
            continue

        if not initial_move_detected:
            if session_high - session_open >= cfg.min_move_from_open:
                initial_move_detected = True
                move_direction = 1
            elif session_open - session_low >= cfg.min_move_from_open:
                initial_move_detected = True
                move_direction = -1
            continue

        c = close[i]
        e = ema[i]
        if np.isnan(e):
            continue
        if abs(c - e) > cfg.pullback_proximity * atr[i]:
            pullback_bars = 0
            continue
        pullback_bars += 1
        if pullback_bars < cfg.min_pullback_bars:
            continue

        bullish_bar = c > open_[i]
        bearish_bar = c < open_[i]
        bullish_engulf = c > open_[i - 1] and open_[i] <= close[i - 1]
        bearish_engulf = c < open_[i - 1] and open_[i] >= close[i - 1]
        long_confirm = bullish_engulf if cfg.use_engulfing else bullish_bar
        short_confirm = bearish_engulf if cfg.use_engulfing else bearish_bar

        signal = 0
        if move_direction == 1 and long_confirm:
            signal = 1
        elif move_direction == -1 and short_confirm:
            signal = -1

        if signal == 0:
            continue

        if cfg.use_vwap_filter:
            if abs(c - vwap[i]) / atr[i] < cfg.vwap_min_distance_atr:
                continue
        if cfg.use_volume_filter:
            if volume[i] < vol_pct[i]:
                continue
        if cfg.use_adx_filter:
            if np.isnan(adx[i]) or adx[i] < cfg.adx_min:
                continue

        target_r = cfg.target_r_multiple
        if cfg.dynamic_target:
            if cfg.use_adx_filter:
                adx_norm = (adx[i] - cfg.adx_min) / 40.0
                target_r = np.clip(cfg.target_r_multiple + adx_norm, cfg.target_floor_r, cfg.target_cap_r)
            else:
                med_atr = np.nanmedian(atr)
                atr_norm = (atr[i] - med_atr) / med_atr
                target_r = np.clip(cfg.target_r_multiple + atr_norm, cfg.target_floor_r, cfg.target_cap_r)

        entry = c
        stop = entry - signal * risk_distance
        in_pos[i] = signal
        entry_prices[i] = entry
        stop_prices[i] = stop
        risk_points[i] = risk_distance
        be_moved[i] = False
        today_trade_count += 1
        last_signal_date = current_date
        trades.append({
            'entry_idx': i, 'entry': entry, 'stop': stop, 'risk': risk_distance,
            'direction': 'Long' if signal == 1 else 'Short', 'entry_time': datetimes[i],
            'target_r': target_r, 'exit_idx': None, 'exit': None, 'pnl': None,
            'exit_reason': None, 'exit_time': None
        })

    # Close any open position at end of data
    if in_pos[-1] != 0:
        _close_trade(trades, n - 1, in_pos[-1], close[-1], cfg.point_value, 'end_of_data', datetimes[-1])

    trades = [t for t in trades if t['pnl'] is not None]
    return _summarize(trades, cfg)


def _update_consec(pnl: float, consec: int) -> int:
    return consec + 1 if pnl < 0 else 0


def _close_trade(trades: List[Dict], idx: int, pos: int, exit_price: float,
                 point_value: float, reason: str, exit_time):
    open_trade = None
    for t in reversed(trades):
        if t.get('exit_idx') is None:
            open_trade = t
            break
    if open_trade is None:
        return
    entry = open_trade['entry']
    points = (exit_price - entry) * pos
    pnl = points * point_value
    open_trade['exit_idx'] = idx
    open_trade['exit'] = exit_price
    open_trade['pnl'] = pnl
    open_trade['exit_reason'] = reason
    open_trade['exit_time'] = exit_time


def _summarize(trades: List[Dict], cfg: BacktestConfig) -> Dict:
    if not trades:
        return {'trades': 0, 'total_pnl': 0, 'win_rate': 0, 'profit_factor': 0, 'avg_trade': 0,
                'max_drawdown': 0, 'sharpe': 0, 'wins': 0, 'losses': 0, 'avg_win': 0, 'avg_loss': 0,
                'cfg': asdict(cfg)}
    pnls = np.array([t['pnl'] for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    total = pnls.sum()
    win_rate = len(wins) / len(pnls)
    gp = wins.sum() if wins.size else 0
    gl = abs(losses.sum()) if losses.size else 0
    pf = gp / gl if gl > 0 else np.inf
    equity = np.cumsum(pnls)
    running_max = np.maximum.accumulate(equity)
    max_dd = (running_max - equity).max()
    sharpe = pnls.mean() / pnls.std() * np.sqrt(len(pnls)) if pnls.std() > 0 else 0
    return {
        'trades': len(pnls), 'total_pnl': total, 'win_rate': win_rate,
        'profit_factor': pf, 'avg_trade': pnls.mean(), 'max_drawdown': max_dd,
        'sharpe': sharpe, 'wins': len(wins), 'losses': len(losses),
        'avg_win': wins.mean() if wins.size else 0, 'avg_loss': losses.mean() if losses.size else 0,
        'cfg': asdict(cfg)
    }


if __name__ == '__main__':
    df = load_nq_5m()
    cfg = BacktestConfig()
    res = run_backtest(df, cfg)
    print(res)
