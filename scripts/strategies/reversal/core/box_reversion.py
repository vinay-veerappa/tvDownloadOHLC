import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import time as dtime

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

from scripts.trading_framework.library.adapters.nqstats_adapter import NQStatsAdapter
from scripts.trading_framework.reporting.decision_log import GateRecorder

class BoxReversionStrategy:
    """
    Box Reversion Strategy (Vectorized ADR-017).
    Identifies institutional 'False Breakout' states and targets session mid-points.
    
    Adheres to STRATEGY_WORKFLOW.md section 2 (the hunt() contract, Zero-Loop).
    """
    
    def __init__(self, ticker: str = "NQ1"):
        self.ticker = ticker
        self.adapter = NQStatsAdapter()
        self.output_cols = ['signal_time', 'direction', 'entry_price', 'stop_price', 'target1_price']
        # Section 5.5: the criteria this hunter evaluates. None means not
        # instrumented; set by hunt().
        self.last_decisions: Optional[pd.DataFrame] = None
        
    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Main signal hunting method (Zero-Loop).
        
        Args:
            data: Standard OHLC DataFrame.
            params: Dictionary of overrides for optimization (Optuna).
            
        Returns:
            Signal DataFrame compliant with the Design Standard.
        """
        p = params or {}
        
        # 1. Borrow normalized features from the NQStats Adapter
        features = self.adapter.get_box_features(data)
        data = data.copy()
        
        # 2. Map necessary columns
        # `.get(..., Series(0))` fallbacks are how this strategy spent its
        # whole life emitting ZERO signals on all data without a word: the
        # adapter produced no 'feat_ny1_mid_dist' (a column-name defect,
        # fixed 2026-09-05) and the zero fallback made the distance gate
        # unconditionally False. A missing feature is a wiring error and must
        # refuse, not trade as if the distance were zero.
        ny1_status = features.get('feat_ny1_status')
        mid_dist = features.get('feat_ny1_mid_dist')
        if ny1_status is None or mid_dist is None:
            missing = [n for n, v in (
                ('feat_ny1_status', ny1_status),
                ('feat_ny1_mid_dist', mid_dist)) if v is None]
            raise ValueError(
                "box_reversion: the NQStats adapter produced no {} -- the "
                "wiring between the adapter and this hunter is broken and "
                "every signal would be fabricated. Refusing rather than "
                "falling back to zeros.".format(missing))
        
        # 3. Dynamic Hyperparameters
        min_dist = p.get('min_dist', 0.0005)
        sl_dist = p.get('sl_dist', 0.0050)
        
        # 4. Entry Filters (Regime & Distance)
        valid_mask = pd.Series(True, index=data.index)
        
        # A. High Volatility Filter (Regime 2 = High Vol)
        if p.get('filter_high_vol', False) and 'regime' in data.columns:
            valid_mask &= (data['regime'] != 2)
            
        # B. Minimum Distance to Target Filter
        valid_mask &= (mid_dist.abs() >= min_dist)

        # 5. Core Entry Masks (Zero-Loop)
        # LONG: Short False (-1)
        long_mask = (ny1_status == -1) & valid_mask
        # SHORT: Long False (1)
        short_mask = (ny1_status == 1) & valid_mask

        # 5b. THE TARGET MUST BE ON THE REVERSION SIDE. mid_dist is signed:
        # (mid - close)/close, positive when the mid is ABOVE price. A
        # "false-breakout DOWN" (Short False, long) only reverts UP -- so a
        # long with mid_dist < 0 has its target BELOW entry, and the signal
        # geometry criterion fails the whole run (a target beyond the stop
        # is nonsense). Until this check (2026-09-05) the min_dist gate
        # matched magnitude only and emitted e.g. longs with the target
        # beneath the stop.
        long_mask &= (mid_dist > 0)
        short_mask &= (mid_dist < 0)

        # 5c. CAUSALITY. The shared session layer (sessions.py
        # get_nq_session_ranges) stamps the whole day's final box
        # aggregate onto EVERY bar of the logical trading day -- including
        # bars from 18:00 the prior evening, before the NY1 box
        # (07:30-08:29 ET) exists. The causality probe caught it on a live
        # run (LOOKAHEAD at 1 of 3 informative cutoffs: a 01:21 signal
        # changed when future bars were appended). The status only becomes
        # knowable in the evaluation window, so entries are restricted to
        # it: NY1 evaluates 08:30-11:30 ET (session_box_status.py
        # EVAL_CONFIG), which is when the reversion trade is actually taken
        # anyway. The shared-layer lookahead itself is research item REG-2
        # (research_backlog/14) -- it contaminates every consumer of
        # '{session}_mid/high/low' and is not fixed from here.
        et = data.index.tz_convert('US/Eastern') if data.index.tz else data.index
        et_times = et.time
        in_eval_window = ((et_times >= dtime(8, 30)) & (et_times < dtime(11, 30)))
        long_mask &= in_eval_window
        short_mask &= in_eval_window
        
        # 6. Optimized Synthesis (Zero-Loop)
        data['direction'] = pd.Series(pd.NA, index=data.index, dtype='object')
        data.loc[long_mask, 'direction'] = 'long'
        data.loc[short_mask, 'direction'] = 'short'

        combined = data.dropna(subset=['direction']).copy()
        if not combined.empty:
            combined['date'] = combined.index.normalize()
        first_sigs = (combined.groupby('date').head(1).copy()
                      if 'date' in combined.columns and not combined.empty
                      else combined)
        is_first = pd.Series(False, index=data.index)
        if len(first_sigs):
            is_first.loc[first_sigs.index] = True

        # 4b. Decision log (section 5.5). The TRIGGER is the false-breakout
        # status (SF says long, LF says short); every gate below is a
        # criterion that can still block it. The sign gate is
        # DIRECTION-AWARE (a long needs the mid above price, a short below),
        # expressed as one per-bar mask; the eval-window gate is the
        # causality gate (item 5c).
        sign_ok = (((ny1_status == -1) & (mid_dist > 0))
                   | ((ny1_status == 1) & (mid_dist < 0)))
        self.last_decisions = (
            GateRecorder(data.index, run_id="", strategy="box_reversion")
            .trigger((ny1_status == -1), "long")
            .trigger((ny1_status == 1), "short")
            .gate("target_on_reversion_side", sign_ok,
                  value=mid_dist, threshold=0)
            .gate("within_ny1_eval_window", in_eval_window)
            .gate("min_distance_to_mid",
                  (mid_dist.abs() >= min_dist),
                  value=mid_dist.abs(), threshold=min_dist)
            .gate("first_signal_of_day", is_first)
            .to_frame(signal_prefix="bxr_")
        )

        if combined.empty:
            return pd.DataFrame(columns=self.output_cols)

        # 7. Vectorized Price Calculation
        first_sigs['signal_time'] = first_sigs.index
        first_sigs['entry_price'] = first_sigs['close']
        
        # Target calculation (reverses mid_dist normalization)
        # mid_dist = (mid - close) / close  => mid = close * (1 + mid_dist)
        first_sigs['target1_price'] = first_sigs['close'] * (1 + mid_dist.loc[first_sigs.index])
        
        # Stop calculation
        first_sigs['stop_price'] = np.where(
            first_sigs['direction'] == 'long',
            first_sigs['entry_price'] * (1 - sl_dist),
            first_sigs['entry_price'] * (1 + sl_dist)
        )
        
        # Final Schema Formatting
        return first_sigs[self.output_cols].reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        """
        Returns the standard optimization grid for Optuna.
        """
        return {
            'min_dist': ('float', 0.0001, 0.0010),
            'sl_dist': ('float', 0.0030, 0.0080),
            'filter_high_vol': ('categorical', [True, False])
        }
