# The Strat Strategy Architecture & Master Specification

## Executive Summary
**The Strat** (created by Rob Smith) is a deterministic price-action methodology based on multi-timeframe auction equilibrium, expansion, and broadening mechanics. It requires **zero order-flow / DOM data** and operates purely on candle-to-candle High and Low relationships across multiple timeframes.

---

## 1. Universal Candle Taxonomy

Every candle on every timeframe is mathematically classified into one of three universal numbers:

| Type | Name | Mathematical Condition | Market Auction Dynamic |
|---|---|---|---|
| **`1`** | **Inside Bar** | $\text{High}[0] \le \text{High}[1] \text{ and } \text{Low}[0] \ge \text{Low}[1]$ | **Equilibrium / Coiling**: Balance of buyers & sellers. Energy accumulation. |
| **`2U`** | **Directional Up** | $\text{High}[0] > \text{High}[1] \text{ and } \text{Low}[0] \ge \text{Low}[1]$ | **Bullish Expansion**: Buyers in control; taking out prior high only. |
| **`2D`** | **Directional Down** | $\text{Low}[0] < \text{Low}[1] \text{ and } \text{High}[0] \le \text{High}[1]$ | **Bearish Expansion**: Sellers in control; taking out prior low only. |
| **`3`** | **Outside Bar** | $\text{High}[0] > \text{High}[1] \text{ and } \text{Low}[0] < \text{Low}[1]$ | **Broadening / Discovery**: Both sides trapped; volatility expansion. |

### Actionable Wick Classification (Hammer & Shooter)
- **Hammer**: $\text{Lower Wick} \ge 65\%$ of candle range and $\text{Close} \ge \text{Low} + 0.5 \times \text{Range}$.
- **Shooter**: $\text{Upper Wick} \ge 65\%$ of candle range and $\text{Close} \le \text{Low} + 0.5 \times \text{Range}$.

---

## 2. Core Strat Setups

### 1. `2-1-2` Continuation & Reversal
- **Bullish 2-1-2 Continuation (`2U-1-2U`)**:
  - `Bar[2]` is `2U`, `Bar[1]` is `1` (Inside Bar).
  - **Entry Trigger**: Buy Stop @ $\text{High}[1] + 1\text{ tick}$.
  - **Stop Loss**: $\text{Low}[1] - 1\text{ tick}$.
  - **Target (Magnitude 1)**: $\text{High}[2]$.
- **Bearish 2-1-2 Continuation (`2D-1-2D`)**:
  - `Bar[2]` is `2D`, `Bar[1]` is `1` (Inside Bar).
  - **Entry Trigger**: Sell Stop @ $\text{Low}[1] - 1\text{ tick}$.
  - **Stop Loss**: $\text{High}[1] + 1\text{ tick}$.
  - **Target (Magnitude 1)**: $\text{Low}[2]$.

### 2. `2-2` Momentum Reversal (The RevStrat Trap)
- **Bullish 2-2 Reversal (`2D-2U`)**:
  - `Bar[1]` is `2D` (pushed down taking prior low).
  - `Bar[0]` fails to follow through and breaks above $\text{High}[1]$ $\rightarrow$ becomes `2U`.
  - **Entry Trigger**: Buy Stop @ $\text{High}[1] + 1\text{ tick}$.
  - **Stop Loss**: $\text{Low}[1] - 1\text{ tick}$.
  - **Target**: $\text{High}[2]$ or prior swing high.

### 3. `3-1-2` Broadening Squeeze Breakout
- An outside bar (`3`) creates a wide volatility boundary $\rightarrow$ followed by an inside bar (`1`) $\rightarrow$ directional breakout (`2U` or `2D`) targets the outer boundary of the `3` bar.

---

## 3. Full Time Frame Continuity (FTFC)

FTFC determines market trend alignment by comparing current price to the **bar open price** across multiple timeframes:
- **Timeframes**: Month (M), Week (W), Daily (D - Globex 18:00 ET open), 4-Hour (4H), 1-Hour (1H), 15-Min (15m), 5-Min (5m).
- **Rule**:
  - Full Green (Bullish FTFC) $\rightarrow$ Long setups only.
  - Full Red (Bearish FTFC) $\rightarrow$ Short setups only.
  - Timeframe Conflict $\rightarrow$ Stand aside or scale down target size.

---

## 4. Code & Architecture Layout

- **Python Library**: [`scripts/libs_py/the_strat/`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/the_strat/)
  - `taxonomy.py`: Bar classification and wick ratio functions.
  - `ftfc.py`: Session-aware multi-timeframe continuity engine.
  - `combos.py`: Setup and Magnitude target detection engine.
  - `strategy.py`: Vectorized backtest simulator.
- **Python Strategy Interface**: [`scripts/strategies/the_strat/`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/the_strat/)
  - `core/strat_strategy.py`: `hunt()` method conforming to framework simulator.
  - `core/run_strat_backtest.py`: Benchmark suite runner.
- **NinjaScript 8 (C#)**: [`scripts/ninjatrader/`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/ninjatrader/)
  - `indicators/the_strat/TheStratClassifier.cs`: Visual numbering and series exporter.
  - `indicators/the_strat/TheStratFTFCHud.cs`: Real-time HUD continuity matrix.
  - `strategies/the_strat/Strat212ContinuationBot.cs`: Automated 2-1-2 execution (`RiskManagerBase`).
  - `strategies/the_strat/Strat22RevStratBot.cs`: Automated 2-2 reversal execution (`RiskManagerBase`).
