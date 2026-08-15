"""
========================================================================================
Intermarket SMT (Smart Money Technique) Divergence Engine
========================================================================================
A reusable, decoupled quantitative module to detect institutional SMT divergences
between correlated asset pairs (e.g. NQ vs ES, YM vs NQ, Gold vs DXY).

Key Capabilities:
-----------------
1. Swing-Pivot SMT:
   - Evaluates confirmed fractal swing high/low sweeps on Primary Asset (e.g., NQ)
   - Checks whether Benchmark Asset (e.g., ES) confirms with a sweep or fails to sweep.
   - Generates Bullish SMT (+1) or Bearish SMT (-1) divergence signals.
2. Vectorized and Streaming API for real-time live trading and backtesting.
3. Fully reusable across ORB, CISD, BPR, Profiler, and ICT strategies.
========================================================================================
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

@dataclass
class SMTResult:
    bar_index: int
    bullish_smt: bool
    bearish_smt: bool
    primary_swept_bsl: bool
    primary_swept_ssl: bool
    benchmark_swept_bsl: bool
    benchmark_swept_ssl: bool

class SMTDivergenceEngine:
    """
    Decoupled Intermarket SMT Divergence Detector.
    """
    def __init__(self, pivot_left: int = 3, pivot_right: int = 3, max_swings_tracked: int = 10):
        self.pivot_left = pivot_left
        self.pivot_right = pivot_right
        self.max_swings = max_swings_tracked

        self.primary_bsl: List[float] = []
        self.primary_ssl: List[float] = []
        self.benchmark_bsl: List[float] = []
        self.benchmark_ssl: List[float] = []

    def update_bar(
        self,
        bar_idx: int,
        p_high: float,
        p_low: float,
        p_close: float,
        b_high: float,
        b_low: float,
        b_close: float,
        p_swing_high: Optional[float] = None,
        p_swing_low: Optional[float] = None,
        b_swing_high: Optional[float] = None,
        b_swing_low: Optional[float] = None,
    ) -> SMTResult:
        """
        Process a single bar update and check for SMT Divergence.
        """
        if p_swing_high is not None and not np.isnan(p_swing_high):
            self.primary_bsl.append(p_swing_high)
            if len(self.primary_bsl) > self.max_swings:
                self.primary_bsl.pop(0)

        if p_swing_low is not None and not np.isnan(p_swing_low):
            self.primary_ssl.append(p_swing_low)
            if len(self.primary_ssl) > self.max_swings:
                self.primary_ssl.pop(0)

        if b_swing_high is not None and not np.isnan(b_swing_high):
            self.benchmark_bsl.append(b_swing_high)
            if len(self.benchmark_bsl) > self.max_swings:
                self.benchmark_bsl.pop(0)

        if b_swing_low is not None and not np.isnan(b_swing_low):
            self.benchmark_ssl.append(b_swing_low)
            if len(self.benchmark_ssl) > self.max_swings:
                self.benchmark_ssl.pop(0)

        # Check Sweeps
        p_bsl_swept = any(p_high > b for b in self.primary_bsl)
        p_ssl_swept = any(p_low < s for s in self.primary_ssl)

        b_bsl_swept = any(b_high > b for b in self.benchmark_bsl)
        b_ssl_swept = any(b_low < s for s in self.benchmark_ssl)

        # Bullish SMT: Primary sweeps SSL while Benchmark holds higher low (fails to sweep)
        bull_smt = (p_ssl_swept and not b_ssl_swept)

        # Bearish SMT: Primary sweeps BSL while Benchmark holds lower high (fails to sweep)
        bear_smt = (p_bsl_swept and not b_bsl_swept)

        return SMTResult(
            bar_index=bar_idx,
            bullish_smt=bull_smt,
            bearish_smt=bear_smt,
            primary_swept_bsl=p_bsl_swept,
            primary_swept_ssl=p_ssl_swept,
            benchmark_swept_bsl=b_bsl_swept,
            benchmark_swept_ssl=b_ssl_swept,
        )
