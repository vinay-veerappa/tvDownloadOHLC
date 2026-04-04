# ADR-017: Modular Vectorized Strategy Architecture

## Status
Accepted / Verified (2026-04-04)

## Context
As we scale the **Statistical Trading Framework**, we need a high-performance, standardized way to write, optimize, and visualize strategies. Legacy strategies are often "event-driven" (looping over bars), which is too slow for Optuna optimizations and difficult to reuse across instruments.

## Decision
All future strategies in this repository MUST follow the **Modular Vectorized Signal Pattern**. This pattern decomposes a trading system into three atomic, reusable layers:

1.  **Triggers (Layer 4a)**: The core mathematical logic that generates raw entry/exit signals (e.g., IB Break, RSI Overbought, Mid-reversion).
2.  **Filters (Layer 4b)**: Contextual "gates" that block or allow signals (e.g., ICT Kill Zones, Volatility Regimes, News Imminence).
3.  **Risk Modules (Layer 4c)**: Standardized methods for calculating stops and targets (e.g., ATR-based stops, technical level stops).

### Mandatory Requirements:
*   **Vectorization**: Zero `for` loops in signal generation. Use NumPy/Pandas native operations for speed.
*   **Optuna Hook**: Strategies must expose a `get_param_grid()` method to define their hyperparameter search space.
*   **Integration**: Signal generators must output a standardized `pd.DataFrame` containing `signal_time`, `direction`, `entry_price`, `stop_price`, and `target1_price`.

## Consequences
*   **Efficiency**: 10-year backtests on 1m data will take seconds rather than minutes.
*   **Reusability**: We can "hot-swap" filters (e.g., applying the ICT Kill Zone filter to the Box Reversion strategy) without rewriting code.
*   **Research Hub Unity**: The 1m granularity for the Next.js visualizer becomes a default capability of the framework.
