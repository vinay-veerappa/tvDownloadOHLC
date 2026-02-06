# Candle Science Dashboard

## Overview
The Candle Science Dashboard is a predictive analytics tool that profiles the probabilistic behavior of the next candle (Candle 3) based on the context set by the previous two candles (Candle 1 & 2). It answers the question: *"Given what just happened (C1 & C2), what usually happens next?"*

## Key Features

### 1. Cycle 3 Projections (Primary Signal)
- **Visual Diagram**: A dynamic, scaled representation of the C1-C2-C3 sequence.
- **Probability Lines**: Dotted lines projecting the likelihood of:
    - **New High**: C3 High exceeding C2 High.
    - **New Low**: C3 Low breaking C2 Low.
    - **Higher Close**: C3 Close finishing above C2 Close.
    - **Gap Up**: C3 Open starting above C2 Close.
- **Signal Cards**: High-visibility cards displaying Bull/Bear probabilities and the statistical "Edge".

### 2. Cycle 2 Context (Confirmation)
- **Context Analysis**: Analyze precisely *how* Candle 2 formed relative to Candle 1.
- **Extension Stats**: Did C2 extend past C1's High/Low?
- **Close Strength**: Did C2 close strong (above C1 High) or weak (below C1 Low)?
- **Gap Significance**: How often do gaps occur in this sequence?

### 3. Dynamic Filtering
- **Time/Day Filters**: Drill down into specific years, months, or days of the week.
- **Reference Filters**: Isolate specific market conditions.
    - *Example*: "Show me stats ONLY when C2 Closed above C1 High AND C3 Opened below C2 Close."
- **Real-Time Updates**: Every filter change instantly recalculates probabilities from the historical dataset (2018-Present).

## Usage Guide
1.  **Select Ticker/Timeframe**: (e.g., `NQ1`, `1d`).
2.  **Observe Base Probabilities**: Look at the "Candle Trend Probability" cards for the raw historical bias.
3.  **Apply Logic Filters**: Use the Sidebar to define the current market state (e.g., "C2 was Bullish").
4.  **Read the Edge**: Check the "Candle 3 Projections" cards for a statistical edge > 10%.
5.  **Visualize**: Use the diagram to see the projected range and likely closing zones.
