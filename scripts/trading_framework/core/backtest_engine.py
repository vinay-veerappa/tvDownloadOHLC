import pandas as pd
import numpy as np
import uuid
from typing import Dict, Any, List, Optional, Union

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.trading_framework.core.base import BaseBacktester

class VectorizedBacktester(BaseBacktester):
    """
    High-performance Vectorized / Semi-Vectorized Backtesting Engine.
    Layer 5 of the Statistical Trading Framework.
    """
    
    def __init__(self, commission: float = 2.05, slippage_pct: float = 0.0001, account_size: float = 50000.0):
        self.commission = commission
        self.slippage_pct = slippage_pct
        self.account_size = account_size
        
        # Standard Institutional Multipliers
        self.tick_multipliers = {
            'NQ1': 20.0,
            'NQ': 20.0,
            'MNQ': 2.0,
            'ES1': 50.0,
            'ES': 50.0,
            'MES': 5.0,
            'CL': 1000.0,
            'GC': 100.0
        }

    @staticmethod
    def _standard_signal_columns() -> List[str]:
        return ['signal_time', 'direction', 'entry_price', 'stop_price', 'target1_price']

    def _normalize_standardized_signals(self, signals: pd.DataFrame) -> pd.DataFrame:
        """Defensive normalization for standardized signal frames.

        Ensures missing/invalid no-signal outputs never crash the engine and
        returns an empty canonical-schema DataFrame when input is unusable.
        """
        cols = self._standard_signal_columns()
        if signals is None or not isinstance(signals, pd.DataFrame):
            return pd.DataFrame(columns=cols)

        if signals.empty:
            if not all(c in signals.columns for c in cols):
                return pd.DataFrame(columns=cols)
            return signals[cols].copy()

        if not all(c in signals.columns for c in cols):
            return pd.DataFrame(columns=cols)

        out = signals[cols].copy()
        out['signal_time'] = pd.to_datetime(out['signal_time'], errors='coerce')
        out['direction'] = out['direction'].astype(str).str.lower()

        for c in ['entry_price', 'stop_price', 'target1_price']:
            out[c] = pd.to_numeric(out[c], errors='coerce')

        out = out[
            out['signal_time'].notna()
            & out['direction'].isin(['long', 'short'])
            & out['entry_price'].notna()
            & out['stop_price'].notna()
            & out['target1_price'].notna()
        ]
        return out
        
    # ------------------------------------------------------------------
    # Signal / frame alignment
    #
    # `Index.get_indexer(..., method='bfill')` snaps a missing timestamp to the
    # NEXT available bar with NO distance limit, and returns -1 only when there
    # is no later bar at all. That is a silent, unbounded reindex: signals
    # generated on a DIFFERENT frame than the one being backtested do not error,
    # they execute at whatever bar happens to come next.
    #
    # Measured 2026-09-04: passing a train fold's signals against a test fold's
    # frame mapped EVERY pre-frame signal to index 0 and passed the `!= -1`
    # check, so the whole set was scored as if it had entered on the first bar
    # of the test window. The purged-CV machinery wrapped around that could not
    # see it, because the signals had never been indexed to the test fold at all.
    #
    # Note the bound is in TIME, not bars. Between two adjacent bars there are
    # no other bars, so bfill always lands exactly one bar forward and a
    # bar-count limit can never bind. What varies is how much wall clock that
    # one bar spans -- a signal at 17:05 on a frame that jumps 17:00 -> 18:00
    # snaps forward 55 minutes and still measures as "one bar".
    #
    # Rules:
    #   * a snap is allowed up to `max_snap_seconds`, defaulting to the frame's
    #     own modal bar spacing (i.e. at most one normal bar late);
    #   * anything beyond that is DROPPED, and every drop is COUNTED and
    #     returned, so a caller passing the wrong frame gets a number instead of
    #     a plausible Sharpe;
    #   * `strict_alignment=True` turns any drop into a raise, for callers that
    #     know the two frames must correspond exactly.
    # ------------------------------------------------------------------
    @staticmethod
    def _frame_bar_seconds(data: pd.DataFrame) -> float:
        if len(data.index) < 3:
            return 60.0
        diffs = np.diff(data.index.values[:5000]).astype('timedelta64[s]').astype(float)
        diffs = diffs[diffs > 0]
        if diffs.size == 0:
            return 60.0
        return float(np.median(diffs))

    @classmethod
    def _align_signals_to_frame(cls, signals: pd.DataFrame, data: pd.DataFrame,
                                risk_params: Dict[str, Any]):
        """Map signal_time -> bar index, bounding the forward snap in TIME.

        Returns (signals, entry_indices, report). `report` is always populated and
        is carried into the metrics dict, so a run record can store it and a gate
        can assert on it.
        """
        bar_seconds = cls._frame_bar_seconds(data)
        max_snap = float(risk_params.get('max_snap_seconds', bar_seconds))
        strict = bool(risk_params.get('strict_alignment', False))
        n_in = int(len(signals))

        sig_ns = signals['signal_time'].to_numpy(dtype='datetime64[ns]')
        idx_ns = data.index.to_numpy(dtype='datetime64[ns]')

        raw = data.index.get_indexer(signals['signal_time'], method='bfill')
        exact = data.index.get_indexer(signals['signal_time'])

        past_frame_end = raw == -1
        safe = np.where(past_frame_end, 0, raw)
        snap_seconds = (idx_ns[safe] - sig_ns).astype('timedelta64[s]').astype(float)
        snap_seconds = np.where(past_frame_end, np.inf, snap_seconds)

        before_frame_start = sig_ns < idx_ns[0]
        too_far = snap_seconds > max_snap
        keep = (~past_frame_end) & (~too_far)

        report = {
            'signals_in': n_in,
            'signals_kept': int(keep.sum()),
            'dropped_past_frame_end': int(past_frame_end.sum()),
            'dropped_before_frame_start': int((before_frame_start & ~keep).sum()),
            'dropped_snap_too_far': int((too_far & ~past_frame_end).sum()),
            'snapped_within_tolerance': int((keep & (exact == -1)).sum()),
            'max_snap_seconds_allowed': max_snap,
            'frame_bar_seconds': bar_seconds,
            'frame_start': str(data.index[0]) if len(data.index) else None,
            'frame_end': str(data.index[-1]) if len(data.index) else None,
        }

        n_dropped = n_in - report['signals_kept']
        if n_dropped and strict:
            raise ValueError(
                "strict_alignment: {} of {} signals could not be placed on the "
                "backtest frame [{} .. {}] within {:.0f}s. "
                "before_frame_start={}, snap_too_far={}, past_frame_end={}. "
                "This almost always means the signals were generated on a "
                "different frame than the one passed as `data`.".format(
                    n_dropped, n_in, report['frame_start'], report['frame_end'],
                    max_snap, report['dropped_before_frame_start'],
                    report['dropped_snap_too_far'], report['dropped_past_frame_end'])
            )
        if report['dropped_before_frame_start']:
            print("[backtest_engine] WARNING: {} signal(s) predate the backtest frame "
                  "and were dropped, not snapped forward to bar 0. Frames likely mismatched."
                  .format(report['dropped_before_frame_start']))

        return signals[keep].copy(), raw[keep], report

    def run(self, signals: Union[pd.Series, pd.DataFrame], data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(signals, pd.Series):
            return self._run_raw_vectorized(signals, data, risk_params)
        elif isinstance(signals, pd.DataFrame):
            return self._run_standardized_matches(signals, data, risk_params)
        else:
            raise ValueError("Unsupported signal format. Use pd.Series or pd.DataFrame.")

    def _run_raw_vectorized(self, signals: pd.Series, data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        # `execution_signals * data['returns']` is an INDEX-ALIGNED multiply:
        # pandas silently unions the two indexes and fills NaN, so passing a
        # signal series from a different frame returns NaN metrics rather than
        # raising. Same family as the bfill snap on the standardized path --
        # the wrong frame produces a number instead of a complaint. Here the
        # two indexes must be identical, so say so.
        if not signals.index.equals(data.index):
            overlap = int(signals.index.isin(data.index).sum())
            raise ValueError(
                "raw-vectorized backtest requires the signal series and the price "
                "frame to share one index; got {} signal rows vs {} bars with {} "
                "overlapping. An index-aligned multiply would have returned NaN "
                "metrics instead of failing.".format(
                    len(signals.index), len(data.index), overlap)
            )
        execution_signals = signals.shift(1).fillna(0)
        strategy_returns = execution_signals * data['returns']
        trades = execution_signals.diff().abs()
        costs = trades * self.slippage_pct
        net_returns = strategy_returns - costs
        cum_returns = (1 + net_returns).cumprod()
        
        return {
            'total_return_%': (cum_returns.iloc[-1] - 1) * 100,
            'sharpe_ratio': self._calculate_sharpe(net_returns),
            'max_drawdown_%': self._calculate_max_drawdown(cum_returns) * 100,
            'num_trades': int(trades.sum()),
            'equity_curve': cum_returns,
            'trade_returns_pct': net_returns[execution_signals != 0]
        }

    def _run_standardized_matches(self, signals: pd.DataFrame, data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        signals = self._normalize_standardized_signals(signals)
        if signals.empty:
            # Still report an alignment block, so a consumer can distinguish
            # "the strategy produced no signals" from "the engine is too old to
            # tell you". Both used to arrive as an absent key.
            return self._null_metrics(data, alignment={
                'signals_in': 0,
                'signals_kept': 0,
                'dropped_past_frame_end': 0,
                'dropped_before_frame_start': 0,
                'dropped_snap_too_far': 0,
                'snapped_within_tolerance': 0,
                'note': 'no signals reached the engine (empty or non-canonical frame)',
                'frame_start': str(data.index[0]) if len(data.index) else None,
                'frame_end': str(data.index[-1]) if len(data.index) else None,
            })

        # 1. Alignment and Pre-check -- see _align_signals_to_frame for why this
        #    is bounded in time rather than left to get_indexer's silent snap.
        signals, entry_indices, alignment = self._align_signals_to_frame(
            signals, data, risk_params)

        if signals.empty:
            return self._null_metrics(data, alignment=alignment)

        # 2. Performance Matrix Search (Layer 5 - ADR-008)
        MAX_SEARCH = 1440 
        n_sigs = len(signals)
        n_bars = len(data)
        CHUNK_SIZE = 25000

        high_vals = data['high'].values.astype(np.float32)
        low_vals = data['low'].values.astype(np.float32)
        close_vals = data['close'].values.astype(np.float32)

        all_hit_occurred = []
        all_hit_bars = []
        all_is_sl = []
        all_mae = []
        all_mfe = []
        all_exit_closes = []
        all_mfe_wick = []
        all_mfe_close = []

        ticker = risk_params.get('ticker', 'NQ1')

        for i in range(0, n_sigs, CHUNK_SIZE):
            c_indices = entry_indices[i : i + CHUNK_SIZE]
            c_targets = signals['target1_price'].values[i : i + CHUNK_SIZE, None].astype(np.float32)
            c_stops = signals['stop_price'].values[i : i + CHUNK_SIZE, None].astype(np.float32)
            c_is_long = (signals['direction'] == 'long').values[i : i + CHUNK_SIZE, None]
            c_is_long_flat = c_is_long.flatten()
            c_entries = signals['entry_price'].values[i : i + CHUNK_SIZE, None].astype(np.float32)

            offsets = np.arange(MAX_SEARCH)
            f_indices = np.clip(c_indices[:, None] + offsets, 0, n_bars - 1)

            c_highs = high_vals[f_indices]
            c_lows = low_vals[f_indices]
            c_closes = close_vals[f_indices]

            tp_hits = np.where(c_is_long, c_highs >= c_targets, c_lows <= c_targets)
            sl_hits = np.where(c_is_long, c_lows <= c_stops, c_highs >= c_stops)

            any_hit = tp_hits | sl_hits
            c_hit_occurred = np.any(any_hit, axis=1)
            c_hit_bars = np.where(c_hit_occurred, np.argmax(any_hit, axis=1), MAX_SEARCH - 1)
            
            mask = offsets[None, :] <= c_hit_bars[:, None]

            c_max_adv_long = np.min(np.where(mask, c_lows, 1e9), axis=1)
            c_max_adv_short = np.max(np.where(mask, c_highs, -1e9), axis=1)
            c_max_fav_long = np.max(np.where(mask, c_highs, -1e9), axis=1)
            c_max_fav_short = np.min(np.where(mask, c_lows, 1e9), axis=1)

            c_entries_flat = c_entries.flatten()
            c_max_adv = np.where(c_is_long_flat, c_max_adv_long, c_max_adv_short)
            c_max_fav = np.where(c_is_long_flat, c_max_fav_long, c_max_fav_short)

            c_mae = np.where(
                c_is_long_flat,
                ((c_max_adv - c_entries_flat) / c_entries_flat) * 100,
                ((c_entries_flat - c_max_adv) / c_entries_flat) * 100,
            )
            c_mfe = np.where(
                c_is_long_flat,
                ((c_max_fav - c_entries_flat) / c_entries_flat) * 100,
                ((c_entries_flat - c_max_fav) / c_entries_flat) * 100,
            )

            c_is_sl = sl_hits[np.arange(len(c_indices)), c_hit_bars]

            # By-performance measurement: wick vs close excursion
            c_mfe_wick_long = ((np.max(c_highs, axis=1) - c_entries_flat) / c_entries_flat) * 100
            c_mfe_wick_short = ((c_entries_flat - np.min(c_lows, axis=1)) / c_entries_flat) * 100
            c_mfe_close_long = ((np.max(c_closes, axis=1) - c_entries_flat) / c_entries_flat) * 100
            c_mfe_close_short = ((c_entries_flat - np.min(c_closes, axis=1)) / c_entries_flat) * 100

            c_mfe_wick = np.where(c_is_long_flat, c_mfe_wick_long, c_mfe_wick_short)
            c_mfe_close = np.where(c_is_long_flat, c_mfe_close_long, c_mfe_close_short)

            all_hit_occurred.append(c_hit_occurred)
            all_hit_bars.append(c_hit_bars)
            all_is_sl.append(c_is_sl)
            all_mae.append(c_mae)
            all_mfe.append(c_mfe)
            all_exit_closes.append(c_closes[np.arange(len(c_indices)), MAX_SEARCH - 1])
            all_mfe_wick.append(c_mfe_wick)
            all_mfe_close.append(c_mfe_close)

        if not all_hit_occurred:
            return self._null_metrics(data)

        # 3. Outcomes Concat
        hit_occurred = np.concatenate(all_hit_occurred)
        hit_bars = np.concatenate(all_hit_bars)
        is_sl = np.concatenate(all_is_sl)
        mae_vec = np.concatenate(all_mae)
        mfe_vec = np.concatenate(all_mfe)
        exit_closes = np.concatenate(all_exit_closes)
        mfe_wick_vec = np.concatenate(all_mfe_wick)
        mfe_close_vec = np.concatenate(all_mfe_close)

        # 4. Returns Synthesis
        entry_prices = signals['entry_price'].values
        exit_prices = np.where(is_sl, signals['stop_price'].values, signals['target1_price'].values)
        exit_prices[~hit_occurred] = exit_closes[~hit_occurred]
        
        direction_vec = np.where(signals['direction'] == 'long', 1, -1)
        trade_returns = ((exit_prices - entry_prices) / entry_prices) * direction_vec
        
        # Apply Institutional Multipliers and Costs
        multiplier = self.tick_multipliers.get(ticker, 1.0)
        
        # BL-5 FIX: Apply per-contract commission as % of notional
        # commission is $ per round-turn per contract (default $2.05 for Micros)
        # As a fraction of notional: commission / (entry_price * multiplier)
        # This is a conservative approximation — actual commission is fixed $,
        # not % of notional, but this is close enough for backtest purposes.
        if self.commission > 0 and len(entry_prices) > 0:
            commission_pct = self.commission / (np.median(entry_prices) * multiplier)
            trade_returns -= commission_pct
        
        # BL-5: Also apply slippage (already present, kept as-is)
        trade_returns -= self.slippage_pct 

        # BL-6: ADR-020 — Force exit at 16:00 ET if neither TP nor SL hit
        # Check if a forced exit time is provided in risk_params
        exit_pos = np.clip(entry_indices + hit_bars, 0, n_bars - 1)
        force_exit_time = risk_params.get('force_exit_time')  # e.g., "16:00"
        if force_exit_time:
            from datetime import time as dtime
            if isinstance(force_exit_time, str):
                h, m = map(int, force_exit_time.split(':'))
                force_exit = dtime(h, m)
            else:
                force_exit = force_exit_time
            # Find the first bar at or after force_exit on each trade's entry day
            bar_times = data.index.time
            # For trades that didn't hit TP/SL, use the 16:00 close instead
            for i in range(len(trade_returns)):
                if not hit_occurred[i]:
                    # exit_closes already has the close at MAX_SEARCH-1 position
                    # Override with 16:00 close if available
                    entry_idx = entry_indices[i]
                    # Find bars after entry on the same trading day
                    entry_date = data.index[entry_idx].date()
                    for j in range(entry_idx, min(entry_idx + MAX_SEARCH, n_bars)):
                        if data.index[j].date() != entry_date:
                            break
                        if bar_times[j] >= force_exit:
                            exit_prices[i] = close_vals[j]
                            trade_returns[i] = ((exit_prices[i] - entry_prices[i]) / entry_prices[i]) * direction_vec[i]
                            if self.commission > 0:
                                trade_returns[i] -= commission_pct
                            trade_returns[i] -= self.slippage_pct
                            # Update exit position and time
                            exit_pos[i] = j
                            break

        # 5. Equity Curve Mapping
        exit_pos = np.clip(exit_pos, 0, n_bars - 1)
        exit_times = data.index[exit_pos]
        equity_returns = pd.Series(0.0, index=data.index)
        equity_returns.loc[exit_times] += trade_returns
        cum_returns = (1 + equity_returns).cumprod()

        trades_detailed = pd.DataFrame({
            'pnl_pct': trade_returns * 100,
            'mae_pct': mae_vec,
            'mfe_pct': mfe_vec,
            'mfe_wick_pct': mfe_wick_vec,
            'mfe_close_pct': mfe_close_vec,
            'exit_time': exit_times
        }, index=signals.index)

        rolling_perf = self._calculate_rolling_performance(trades_detailed, windows_days=(30, 90))
        perf_by_measurement = {
            'wick': float(np.nanmean(mfe_wick_vec)) if len(mfe_wick_vec) else 0.0,
            'close': float(np.nanmean(mfe_close_vec)) if len(mfe_close_vec) else 0.0,
        }

        return {
            # Echoed so a result can never be read without knowing how many
            # signals actually reached the frame it was scored on.
            'signal_alignment': alignment,
            'total_return_%': (cum_returns.iloc[-1] - 1) * 100,
            'sharpe_ratio': self._calculate_sharpe(equity_returns),
            'max_drawdown_%': self._calculate_max_drawdown(cum_returns) * 100,
            'win_rate_%': (len(trade_returns[trade_returns > 0]) / len(trade_returns)) * 100 if len(trade_returns) > 0 else 0.0,
            'avg_mae_%': mae_vec.mean() if len(mae_vec) > 0 else 0.0,
            'num_trades': n_sigs,
            'equity_curve': cum_returns,
            'trade_returns_pct': pd.Series(trade_returns, index=signals.index),
            'trades_detailed': trades_detailed,
            'rolling_performance': rolling_perf,
            'performance_by_measurement': perf_by_measurement,
        }

    def _null_metrics(self, data: pd.DataFrame,
                      alignment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # An empty result and a MISALIGNED result look identical in every metric,
        # so the alignment report travels with the null case too.
        return {
            'signal_alignment': alignment or {},
            'total_return_%': 0.0, 'sharpe_ratio': 0.0, 'max_drawdown_%': 0.0,
            'num_trades': 0, 'equity_curve': pd.Series(1.0, index=data.index),
            'trade_returns_pct': pd.Series([], dtype=float),
            'trades_detailed': pd.DataFrame(),
            'rolling_performance': {
                '30d': {'win_rate_%': 0.0, 'avg_r_multiple': 0.0, 'sharpe_ratio': 0.0, 'max_drawdown_%': 0.0, 'num_trades': 0},
                '90d': {'win_rate_%': 0.0, 'avg_r_multiple': 0.0, 'sharpe_ratio': 0.0, 'max_drawdown_%': 0.0, 'num_trades': 0},
            },
            'performance_by_measurement': {'wick': 0.0, 'close': 0.0},
        }

    def _calculate_sharpe(self, returns: pd.Series, periods: int = 252 * 6.5 * 60) -> float:
        if returns.std() == 0: return 0.0
        return np.sqrt(periods) * returns.mean() / returns.std()
        
    def _calculate_max_drawdown(self, cum_returns: pd.Series) -> float:
        rolling_max = cum_returns.cummax()
        drawdown = (cum_returns - rolling_max) / rolling_max
        return drawdown.min()

    def _calculate_rolling_performance(self, trades_detailed: pd.DataFrame, windows_days: tuple[int, int] = (30, 90)) -> Dict[str, Dict[str, float]]:
        """Compute rolling window performance stats over recent N days."""
        out: Dict[str, Dict[str, float]] = {}

        if trades_detailed is None or trades_detailed.empty or 'exit_time' not in trades_detailed.columns:
            for w in windows_days:
                out[f'{w}d'] = {
                    'win_rate_%': 0.0,
                    'avg_r_multiple': 0.0,
                    'sharpe_ratio': 0.0,
                    'max_drawdown_%': 0.0,
                    'num_trades': 0,
                }
            return out

        td = trades_detailed.copy()
        td['exit_time'] = pd.to_datetime(td['exit_time'])
        td = td.sort_values('exit_time')
        last_ts = td['exit_time'].max()

        for w in windows_days:
            cutoff = last_ts - pd.Timedelta(days=w)
            sub = td[td['exit_time'] >= cutoff].copy()

            if sub.empty:
                out[f'{w}d'] = {
                    'win_rate_%': 0.0,
                    'avg_r_multiple': 0.0,
                    'sharpe_ratio': 0.0,
                    'max_drawdown_%': 0.0,
                    'num_trades': 0,
                }
                continue

            pnl_frac = pd.to_numeric(sub['pnl_pct'], errors='coerce').fillna(0.0) / 100.0
            wins = pnl_frac[pnl_frac > 0]
            losses = pnl_frac[pnl_frac < 0]
            avg_loss = abs(float(losses.mean())) if len(losses) > 0 else np.nan
            avg_r = float(wins.mean() / avg_loss) if (len(wins) > 0 and avg_loss and not np.isnan(avg_loss)) else 0.0

            if pnl_frac.std() and not np.isnan(float(pnl_frac.std())) and float(pnl_frac.std()) > 0:
                sharpe = float(np.sqrt(252) * pnl_frac.mean() / pnl_frac.std())
            else:
                sharpe = 0.0

            equity = (1.0 + pnl_frac).cumprod()
            roll_max = equity.cummax()
            mdd = float(((equity - roll_max) / roll_max).min()) * 100.0

            out[f'{w}d'] = {
                'win_rate_%': float((pnl_frac > 0).mean() * 100.0),
                'avg_r_multiple': avg_r,
                'sharpe_ratio': sharpe,
                'max_drawdown_%': mdd,
                'num_trades': int(len(sub)),
            }

        return out
