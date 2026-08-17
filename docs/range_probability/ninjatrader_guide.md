# NinjaTrader 8 Integration Guide: Range Probability Suite

This guide explains how to install, compile, and trade the **Range Probability Indicator** and **Automated Strategy** inside NinjaTrader 8.

---

## 1. File Locations & Installation

Copy the C# NinjaScript files to your NinjaTrader 8 Custom directories:

### Indicator Installation
- Source: `scripts/ninjatrader/indicators/range_probability/RangeProbabilityIndicator.cs`
- Target: `Documents/NinjaTrader 8/bin/Custom/Indicators/RangeProbabilityIndicator.cs`

### Strategy Installation
- Source: `scripts/ninjatrader/strategies/range_probability/RangeProbabilityStrategy.cs`
- Target: `Documents/NinjaTrader 8/bin/Custom/Strategies/RangeProbabilityStrategy.cs`

---

## 2. Compilation in NinjaTrader 8
1. Open NinjaTrader 8.
2. In the Control Center, click **Tools** -> **NinjaScript Editor** (or press `F5`).
3. In the NinjaScript Editor window, press `F5` (or click **Compile** in the toolbar).
4. Verify that the compile status bar displays `"NinjaScript files successfully compiled"`.

---

## 3. Using the Indicator on Charts

1. Open any chart (e.g. `NQ 09-26` or `ES 09-26`, 1-Minute or 5-Minute timeframe).
2. Right-click the chart -> **Indicators** (`Ctrl+I`).
3. Select **`RangeProbabilityIndicator`** from the list and click **Add**.
4. Configure Parameters:
   - **Range Minutes**: `60` (or `15`, `30`, `120`, `240`).
   - **Anchor Hour (ET)**: `18` (matches futures session open).
   - **Draw Range Boxes**: `True`.
   - **Show Prior High/Mid/Low**: `True`.
   - **Show HUD Statistics Table**: `True`.
   - **Min Probability Edge (%)**: `70.0`.
5. Click **OK**.

### Chart Visual Features:
- **Prior Range Box**: Shows previous range boundaries.
- **Reference Lines**: Blue line for Prior High, dashed gray line for Prior Midpoint, and red line for Prior Low.
- **HUD Box (Top-Right)**: Displays current slot, opening decile position, empirical resolution probability, and live rolling audit scorecard with drift tracking.
- **Signal Arrows**: Green arrow up for $\ge 70\%$ Long edge, red arrow down for $\ge 70\%$ Short edge.

---

## 4. Running the Automated Strategy in Strategy Analyzer

1. In NinjaTrader 8 Control Center, click **New** -> **Strategy Analyzer**.
2. Set **Strategy** to `RangeProbabilityStrategy`.
3. Set **Instrument** to `NQ` (or `MNQ`, `ES`, `MES`, `YM`, `RTY`, `CL`, `GC`).
4. Set **Interval** to `1 Minute` or `5 Minute`.
5. Configure Parameters:
   - **Range Minutes**: `60`.
   - **Anchor Hour ET**: `18`.
   - **Order Quantity**: `1`.
   - **Stop Mode**: `PriorMidpoint` (or `FixedTicks`).
   - **Fixed Stop Ticks**: `40`.
   - **Fixed Target Ticks**: `80`.
6. Click **Run Backtest** to generate equity curves, performance graphs, trade-by-trade analytics, and drawdown metrics.
