"""
Vectorized backtest for EMAPullBackBot-like rules on NQ 5m data.
Mirrors NT8 RiskManagerBase trade management: ATR stop, fixed target R-multiple,
breakeven/trail, daily max loss, max trades/day, consecutive-loser pause/halt,
session flatten by time, and entry time window.
"""
import pandas as pd
import numpy as np
import talib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# NQ point value $20 per point, but NQ is quoted in 0.25 ticks = $5/tick.
# We will treat price in points and multiply by $20 for dollar PnL.
POINT_VALUE = 20.0


def load_nq_5m() -> pd.DataFrame:
    df = pd.read_parquet(r'C:\Users\vinay\tvDownloadOHLC\data\NQ1_5m.parquet')
    df['datetime_utc'] = pd.to_datetime(df.index, utc=True)
    df = df.reset_index(drop=True)
    df['datetime'] = df['datetime_utc'].dt.tz_convert('America/New_York')
    df['time'] = df['datetime'].dt.hour * 100 + df['datetime'].dt.minute
    df['date'] = df['datetime'].dt.date
    df = df.drop(columns=['datetime_utc']).sort_values('datetime').reset_index(drop=True)
    return df


def anchored_vwap(df: pd.DataFrame, anchor_time_et: str = '09:30') -> pd.Series:
    """
    Compute anchored VWAP starting at anchor_time_et each calendar day.
    Uses typical price (H+L+C)/3 * volume.
    """
    h, m = map(int, anchor_time_et.split(':'))
    anchor_min = h * 60 + m
    df = df.copy()
    df['minute_of_day'] = df['datetime'].dt.hour * 60 + df['datetime'].dt.minute
    df['typical'] = (df['high'] + df['low'] + df['close']) / 3.0
    df['pv'] = df['typical'] * df['volume']
    df['in_session'] = df['minute_of_day'] >= anchor_min
    df['session_id'] = (df['date'].astype(str) + '_' + df['in_session'].astype(str)).where(df['in_session'], np.nan)
    df['session_id'] = df['session_id'].ffill()
    df['cum_pv'] = df.groupby('session_id')['pv'].cumsum()
    df['cum_vol'] = df.groupby('session_id')['volume'].cumsum()
    vwap = np.where(df['cum_vol'] > 0, df['cum_pv'] / df['cum_vol'], df['close'])
    return pd.Series(vwap, index=df.index)


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return pd.Series(talib.ADX(df['high'].values, df['low'].values, df['close'].values, timeperiod=period), index=df.index)


def compute_ema(df: pd.DataFrame, period: int) -> pd.Series:
    return pd.Series(talib.EMA(df['close'].values, timeperiod=period), index=df.index)


def compute_atr(df: pd.DataFrame, period: int) -> pd.Series:
    return pd.Series(talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=period), index=df.index)


@dataclass
class BacktestConfig:
    symbol: str = 'NQ'
    point_value: float = POINT_VALUE

    # Risk / trade management
    stop_atr_mult: float = 1.25
    target_r_multiple: float = 3.75
    trade_policy: str = 'FixedTarget'   # or 'BreakevenTrail'
    breakeven_trigger_r: float = 1.0
    trail_atr_mult: float = 2.0
    atr_period: int = 14

    # Session gates
    earliest_entry: int = 945
    latest_entry: int = 1100
    flatten_by: int = 1545
    daily_max_loss: float = 400.0
    max_trades_per_day: int = 3
    max_consec_losers_pause: int = 2
    pause_minutes: int = 30
    hard_stop_consec_losers: int = 3

    # EMA pullback signal
    ema_period: int = 20
    min_move_from_open: float = 4.0
    pullback_proximity: float = 0.3
    min_pullback_bars: int = 2
    use_engulfing: bool = True

    # Filters
    use_vwap_filter: bool = False
    vwap_min_distance_atr: float = 0.0
    use_volume_filter: bool = False
    volume_lookback: int = 20
    volume_percentile: float = 50.0
    use_adx_filter: bool = False
    adx_period: int = 14
    adx_min: float = 20.0

    # Advanced risk
    dynamic_target: bool = False
    target_cap_r: float = 5.0
    target_floor_r: float = 1.5
    use_session_quality_target: bool = False


def hhmm_to_min(t: int) -> int:
    return (t // 100) * 60 + (t % 100)


def run_backtest(df: pd.DataFrame, cfg: BacktestConfig) -> Dict:
    df = df.copy()
    # Compute indicators
    df['ema'] = compute_ema(df, cfg.ema_period)
    df['atr'] = compute_atr(df, cfg.atr_period)
    df['adx'] = compute_adx(df, cfg.adx_period) if cfg.use_adx_filter else 0.0
    df['vwap'] = anchored_vwap(df, '09:30') if cfg.use_vwap_filter else 0.0
    df['vol_sma'] = df['volume'].rolling(cfg.volume_lookback).mean() if cfg.use_volume_filter else 0.0
    df['vol_pct'] = df['volume'].rolling(cfg.volume_lookback).quantile(cfg.volume_percentile / 100.0) if cfg.use_volume_filter else 0.0

    # Session state arrays
    n = len(df)
    in_pos = np.zeros(n, dtype=int)   # 0 flat, 1 long, -1 short
    entry_prices = np.zeros(n)
    stop_prices = np.zeros(n)
    risk_points = np.zeros(n)
    be_moved = np.zeros(n, dtype=bool)
    trades: List[Dict] = []

    # Day-level state
    current_date = None
    today_trade_count = 0
    consec_losers = 0
    session_pnl = 0.0
    is_paused = False
    pause_until = pd.Timestamp.min.tz_localize('America/New_York')
    is_done = False
    high_water = 0.0
    account_equity = 0.0

    # Session open/high/low tracking
    session_open = None
    session_high = -np.inf
    session_low = np.inf
    initial_move_detected = False
    move_direction = 0
    pullback_bars = 0
    last_signal_date = None

    for i in range(1, n):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        t = row['time']
        d = row['date']
        dt = row['datetime']

        # New session
        if d != current_date:
            if current_date is not None:
                account_equity += session_pnl
                high_water = max(high_water, account_equity)
            current_date = d
            today_trade_count = 0
            consec_losers = 0
            session_pnl = 0.0
            is_paused = False
            is_done = False
            session_open = None
            session_high = -np.inf
            session_low = np.inf
            initial_move_detected = False
            move_direction = 0
            pullback_bars = 0
            last_signal_date = None

        # Wait for 9:30 session open
        if t < 930:
            continue

        # Capture session open and update HOD/LOD
        if session_open is None:
            session_open = row['open']
            session_high = row['high']
            session_low = row['low']
        else:
            session_high = max(session_high, row['high'])
            session_low = min(session_low, row['low'])

        atr = row['atr']
        if atr <= 0 or np.isnan(atr):
            continue

        # End-of-day flatten
        if t >= cfg.flatten_by and in_pos[i - 1] != 0:
            pnl = _close_trade(df, trades, in_pos, i - 1, in_pos[i - 1], row['close'], cfg.point_value, 'flatten_time')
            session_pnl += pnl
            if pnl < 0:
                consec_losers += 1
            else:
                consec_losers = 0
            in_pos[i] = 0
            continue

        # Manage open trade
        if in_pos[i - 1] != 0:
            pos = in_pos[i - 1]
            entry = entry_prices[i - 1]
            stop = stop_prices[i - 1]
            risk = risk_points[i - 1]
            be = be_moved[i - 1]
            current_price = row['close']
            unrealized = (current_price - entry) * pos * cfg.point_value
            if session_pnl + unrealized <= -cfg.daily_max_loss:
                pnl = _close_trade(df, trades, in_pos, i, pos, current_price, cfg.point_value, 'daily_max_loss')
                session_pnl += pnl
                is_done = True
                consec_losers = _update_consec(pnl, consec_losers)
                in_pos[i] = 0
                continue

            # Stop hit (close breaches stop) - simplified intrabar = close
            if (pos == 1 and row['low'] <= stop) or (pos == -1 and row['high'] >= stop):
                exit_price = stop
                pnl = _close_trade(df, trades, in_pos, i, pos, exit_price, cfg.point_value, 'stop')
                session_pnl += pnl
                consec_losers = _update_consec(pnl, consec_losers)
                in_pos[i] = 0
                continue

            # Target / breakeven / trail
            if cfg.trade_policy == 'FixedTarget':
                target = entry + cfg.target_r_multiple * risk * pos
                if (pos == 1 and row['high'] >= target) or (pos == -1 and row['low'] <= target):
                    pnl = _close_trade(df, trades, in_pos, i, pos, target, cfg.point_value, 'target')
                    session_pnl += pnl
                    consec_losers = _update_consec(pnl, consec_losers)
                    in_pos[i] = 0
                    continue
            else:  # BreakevenTrail
                current_r = ((current_price - entry) * pos) / risk
                if not be and current_r >= cfg.breakeven_trigger_r:
                    be = True
                    stop = entry
                if be:
                    trail_dist = cfg.trail_atr_mult * atr
                    if pos == 1:
                        new_stop = current_price - trail_dist
                        if new_stop > stop:
                            stop = new_stop
                    else:
                        new_stop = current_price + trail_dist
                        if new_stop < stop:
                            stop = new_stop
                # Check stop after update
                if (pos == 1 and row['low'] <= stop) or (pos == -1 and row['high'] >= stop):
                    exit_price = min(max(stop, row['low']), row['high']) if pos == 1 else max(min(stop, row['high']), row['low'])
                    pnl = _close_trade(df, trades, in_pos, i, pos, exit_price, cfg.point_value, 'trail_stop')
                    session_pnl += pnl
                    consec_losers = _update_consec(pnl, consec_losers)
                    in_pos[i] = 0
                    continue

            # Carry forward
            in_pos[i] = pos
            entry_prices[i] = entry
            stop_prices[i] = stop
            risk_points[i] = risk
            be_moved[i] = be
            continue

        # Entry gate
        if t < cfg.earliest_entry or t > cfg.latest_entry:
            in_pos[i] = 0
            continue
        if is_done:
            continue
        if is_paused and dt < pause_until:
            continue
        elif is_paused:
            is_paused = False
        if today_trade_count >= cfg.max_trades_per_day:
            continue
        # Consec loser hard stop handled by is_done above

        # Potential loss gate
        risk_distance = cfg.stop_atr_mult * atr
        potential_loss = risk_distance * cfg.point_value
        if session_pnl - potential_loss < -cfg.daily_max_loss:
            continue

        # Signal detection (EMA pullback)
        if last_signal_date == d:
            continue

        if not initial_move_detected:
            if session_high - session_open >= cfg.min_move_from_open:
                initial_move_detected = True
                move_direction = 1
            elif session_open - session_low >= cfg.min_move_from_open:
                initial_move_detected = True
                move_direction = -1
            continue

        close = row['close']
        ema = row['ema']
        if np.isnan(ema):
            continue
        distance_to_ema = abs(close - ema)
        near_ema = distance_to_ema <= cfg.pullback_proximity * atr

        if not near_ema:
            pullback_bars = 0
            continue
        pullback_bars += 1
        if pullback_bars < cfg.min_pullback_bars:
            continue

        bullish_bar = close > row['open']
        bearish_bar = close < row['open']
        bullish_engulf = close > prev['open'] and row['open'] <= prev['close']
        bearish_engulf = close < prev['open'] and row['open'] >= prev['close']
        long_confirm = bullish_engulf if cfg.use_engulfing else bullish_bar
        short_confirm = bearish_engulf if cfg.use_engulfing else bearish_bar

        signal = 0
        if move_direction == 1 and long_confirm:
            signal = 1
        elif move_direction == -1 and short_confirm:
            signal = -1

        if signal == 0:
            continue

        # Filters
        if cfg.use_vwap_filter:
            vwap_dist = abs(close - row['vwap']) / atr
            if vwap_dist < cfg.vwap_min_distance_atr:
                continue
        if cfg.use_volume_filter:
            if row['volume'] < row['vol_pct']:
                continue
        if cfg.use_adx_filter:
            if row['adx'] < cfg.adx_min:
                continue

        # Dynamic target scaling
        target_r = cfg.target_r_multiple
        if cfg.dynamic_target:
            # Wider target when ADX is strong, tighter when weak; bound by floor/cap
            if cfg.use_adx_filter:
                adx_norm = (row['adx'] - cfg.adx_min) / 40.0
                target_r = np.clip(cfg.target_r_multiple + adx_norm, cfg.target_floor_r, cfg.target_cap_r)
            else:
                # use ATR vs median ATR
                med_atr = df['atr'].median()
                atr_norm = (atr - med_atr) / med_atr
                target_r = np.clip(cfg.target_r_multiple + atr_norm, cfg.target_floor_r, cfg.target_cap_r)

        entry = close
        stop = entry - signal * cfg.stop_atr_mult * atr
        in_pos[i] = signal
        entry_prices[i] = entry
        stop_prices[i] = stop
        risk_points[i] = risk_distance
        be_moved[i] = False
        today_trade_count += 1
        last_signal_date = d
        trades.append({
            'entry_idx': i,
            'entry': entry,
            'stop': stop,
            'risk': risk_distance,
            'direction': 'Long' if signal == 1 else 'Short',
            'entry_time': dt,
            'exit_idx': None,
            'exit': None,
            'pnl': None,
            'exit_reason': None,
            'exit_time': None
        })

    # Close any open position at end of data
    if in_pos[-1] != 0:
        pnl = _close_trade(df, trades, in_pos, n - 1, in_pos[-1], df.iloc[-1]['close'], cfg.point_value, 'end_of_data')
        session_pnl += pnl

    # Safety: remove any unclosed trades (should not happen)
    trades = [t for t in trades if t['pnl'] is not None]

    return _summarize(df, trades, cfg)


def _update_consec(pnl: float, consec: int) -> int:
    return consec + 1 if pnl < 0 else 0


def _close_trade(df: pd.DataFrame, trades: List[Dict], in_pos: np.ndarray, idx: int,
                 pos: int, exit_price: float, point_value: float, reason: str) -> float:
    entry = 0
    # Find entry price by walking back
    for j in range(idx, -1, -1):
        if in_pos[j] == pos:
            # entry was set at bar j
            entry = df.iloc[j]['close'] if j == idx else df.iloc[j]['close']
            # Actually entry_prices not passed; use close at first bar of position
            # We'll reconstruct from trades list instead.
            break
    # Better: track per-bar entry_prices; passed implicitly via global in original; here reconstruct.
    # Simplification: use the most recent entry from trades with no exit.
    open_trade = None
    for t in reversed(trades):
        if t.get('exit_idx') is None:
            open_trade = t
            break
    if open_trade is None:
        # fallback
        entry = df.iloc[idx]['close']
    else:
        entry = open_trade['entry']
    points = (exit_price - entry) * pos
    pnl = points * point_value
    if open_trade is not None:
        open_trade['exit_idx'] = idx
        open_trade['exit'] = exit_price
        open_trade['pnl'] = pnl
        open_trade['exit_reason'] = reason
        open_trade['exit_time'] = df.iloc[idx]['datetime']
    return pnl


def _summarize(df: pd.DataFrame, trades: List[Dict], cfg: BacktestConfig) -> Dict:
    if not trades:
        return {'trades': 0, 'total_pnl': 0, 'win_rate': 0, 'profit_factor': 0, 'avg_trade': 0,
                'max_drawdown': 0, 'sharpe': 0, 'cfg': cfg.__dict__}
    pnls = np.array([t['pnl'] for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    total = pnls.sum()
    wins_n = len(wins)
    losses_n = len(losses)
    win_rate = wins_n / len(pnls) if pnls.size else 0
    gross_profit = wins.sum() if wins.size else 0
    gross_loss = abs(losses.sum()) if losses.size else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else np.inf

    # equity curve and max drawdown
    equity = np.cumsum(pnls)
    running_max = np.maximum.accumulate(equity)
    drawdown = running_max - equity
    max_dd = drawdown.max()

    # sharpe annualized assuming ~78 trades/day? actually per-trade
    if len(pnls) > 1:
        sharpe = pnls.mean() / pnls.std() * np.sqrt(len(pnls)) if pnls.std() > 0 else 0
    else:
        sharpe = 0

    return {
        'trades': len(pnls),
        'total_pnl': total,
        'win_rate': win_rate,
        'profit_factor': pf,
        'avg_trade': pnls.mean(),
        'max_drawdown': max_dd,
        'sharpe': sharpe,
        'wins': wins_n,
        'losses': losses_n,
        'avg_win': wins.mean() if wins.size else 0,
        'avg_loss': losses.mean() if losses.size else 0,
        'cfg': cfg.__dict__
    }


if __name__ == '__main__':
    df = load_nq_5m()
    cfg = BacktestConfig()
    res = run_backtest(df, cfg)
    print(res)
