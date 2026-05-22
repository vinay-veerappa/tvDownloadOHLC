"""
ICT Strategy Suite — Harmonised Pillar 2 Implementations
==========================================================
ADR-020 compliant (16:00 ET hard exit).
ADR-017 compliant (zero-loop vectorization).
ADR-002 compliant (percentage-normalised stops/targets).

All strategies accept a NY-timezone-aware OHLCV DataFrame from the
DataLoader and return a canonical Signal List DataFrame for the
VectorizedBacktester.

Available strategies (registry keys):
    ict_displacement   — Market Structure Shift (MSS/BOS) entries
    ict_liquidity_sweep — Stop hunt + CISD reversal entries
    ict_fvg_rejection  — FVG zone rejection entries
    ict_ny_session     — NY AM killzone sweep + CISD entries
    ict_asia_volatility — Judas Swing / Asia range reversal entries
"""
from .ict_displacement    import ICTDisplacementStrategy
from .ict_liquidity_sweep import ICTLiquiditySweepStrategy
from .ict_fvg_rejection   import ICTFVGRejectionStrategy
from .ict_ny_session      import ICTNYSessionStrategy
from .ict_asia_volatility import ICTAsiaVolatilityStrategy

__all__ = [
    "ICTDisplacementStrategy",
    "ICTLiquiditySweepStrategy",
    "ICTFVGRejectionStrategy",
    "ICTNYSessionStrategy",
    "ICTAsiaVolatilityStrategy",
]
