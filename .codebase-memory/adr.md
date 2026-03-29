# ADR: Statistical Normalization Standard

## Context
When analyzing trading statistics such as Mean, Median, MAE (Maximum Adverse Excursion), and MFE (Maximum Favorable Excursion), absolute price values are context-dependent and cannot be reliably compared across different tickers or even the same ticker over long time horizons (e.g., NQ at 10,000 vs. NQ at 20,000).

## Decision
All statistical reporting and internal calculations for performance metrics (MAE, MFE, expected moves, and session averages) MUST use **Price Percentage** as the primary basis. 

### Implementation Rules:
1. **Basis**: Percentage of the reference price (e.g., Midnight Open or Session Start).
2. **Reporting**: Report values in percentage (e.g., "MFE: +0.42%") rather than points.
3. **Calculation**: `(Target Price - Reference Price) / Reference Price * 100`
4. **Exceptions**: Only use absolute points for execution-level "tick" calculations (e.g., slippage measurement), but normalize immediately for aggregate analysis.

## Consequences
- Cross-ticker comparisons (e.g., ES vs. NQ) become valid.
- Historical data from different volatility regimes remains statistically relevant.
- All "Briefing" reports and Profiler outputs must be updated to reflect percentage-based metrics.
