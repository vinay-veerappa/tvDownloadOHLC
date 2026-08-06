# Candle Science Master Domain Blueprint & Secret Sauce Playbook

> **Source**: NotebookLM Query on *Pack Oct Bootcamp*, *Pack Live Wargaming*, & TCM System
> **Purpose**: Technical and operational guide documenting Matt Mickey's exact Candle Science price action nuances, $C_1$ magnifiers, $C_2$ Open line-in-the-sand rules, $Q_1-Q_4$ quarter footprint responses, and 3-tier TP execution mechanics.

---

## 1. Core Concept: Objective Probability Over Subjective Patterns

Candle Science predicts the behavior of the **next candle ($C_3$)** by analyzing the structural relationship between **$C_1$ (2 bars ago)** and **$C_2$ (last closed bar)** across thousands of historical 3-candle triplets.

Rather than buying or selling breakout candles blindly, Candle Science provides objective probabilities for:
1. **$P(C_3 \text{ Bull})$ vs $P(C_3 \text{ Bear})$**: Directional close probability.
2. **$P(C_3H > C_2H)$**: Probability of reaching/breaching reference high.
3. **$P(C_3L < C_2L)$**: Probability of reaching/breaching reference low.
4. **$P(C_3C > C_2C)$**: Probability of closing above reference close.
5. **MFE / MAE Excursion Percentiles**: P30 (cash-flow target), P50 (median target), P70, P90.

---

## 2. The "Secret Sauce" Price Action Nuances

### Nuance 1: The $C_2$ Open Price — "The Line in the Sand"
The $C_2$ Open Price is the ultimate structural pivot that validates continuation or confirms a reversal:
- **Bullish Momentum Active**: As long as $C_3$ opens and remains above the $C_2$ Open price, bullish momentum is active ($P \approx 65\% - 85\%$). Traders buy red pullback candles in $Q_1/Q_2$ near $C_2$ Open and ignore selling attempts.
- **The Reversal Confirmation Signature**: The MOMENT $C_3$ breaches below the $C_2$ Open:
  - Probability of $C_3$ reaching $C_2$ High **COMPLETELY DROPS**.
  - Probabilities shift heavily toward taking out $C_2$ Low instead ($66\% - 68\%$).
- **Intraday Reclaim Rule (Whipsaw Filter)**:
  - A single-bar wick breach of $C_2$ Open is an initial **Reversal Warning**.
  - **Confirmed Reversal**: Requires a 5-minute candle close below $C_2$ Open.
  - **Reclaim Restoration**: If $C_3$ breaches $C_2$ Open on a wick but reclaims and closes back above $C_2$ Open, the original bullish continuation probabilities are restored (with a 5-10% probability decay).
- **Bearish Momentum Active**: As long as $C_3$ stays below $C_2$ Open, bearish momentum holds. Reclaiming above $C_2$ Open drops $C_2$ Low odds and shifts targets to $C_2$ High.

### Nuance 2: The $C_1$ Red vs. $C_1$ Green "Probability Magnifier"
The closing color of $C_1$ acts as a probability magnifier on $C_3$:

| $C_1$ Color | $C_2$ Action | Setup Type | Statistical Impact on $C_3$ |
| :--- | :--- | :--- | :--- |
| **RED** | $C_2$ breaks $C_1$ High | **High-Probability Bull** | **+8% to +9% boost** in $P(C_3 \text{ close} > C_2 \text{ Open})$. Buy red pullbacks toward $C_2$ Open with max confidence. |
| **GREEN** | $C_2$ breaks $C_1$ High | **Extended Bull** | Lowest probability bullish continuation ($58\% - 64\%$). Buyers are extended; watch for exhaustion. |
| **RED** | $C_2$ breaks $C_1$ Low | **Reversal Alert Bear** | Bearish candles statistically "do not like to close below $C_2$ Low". High chance $C_3$ sweeps $C_2$ Low and closes back INSIDE $C_2$ range ("screwing the shorts"). |
| **GREEN** | $C_2$ breaks $C_1$ Low | **High-Probability Bear** | Strong downward continuation odds ($64\%$ chance $C_3H < C_2H$, $58\%$ chance $C_3L < C_2L$). |

### Nuance 3: $C_2$ Close Relative to $C_1$ Upper Wick Footprint
- **A+ Continuation Close ($C_2$ Close > $C_1$ High)**: Highest statistical probability of $C_3$ high expansion ($>81\%$). Buy pullbacks.
- **Weak Close Inside $C_1$ Upper Wick**: $C_2$ breaches $C_1$ High but closes inside $C_1$'s upper wick footprint. Alerts trader to **Apex (Reversal) risk**. $C_3$ has a $59\% - 62\%$ probability of staying below $C_2$ High.

### Nuance 4: Intraday Quarters ($Q_1$ to $Q_4$) & Footprint Response
- **Footprints**: Wicks of the previous hour / previous daily candle ($C_2$).
- **$Q_1$ (09:30 – 09:45 AM EST)**: Watch price response at previous hour 50% and $C_2$ Open.
- **0-5 Box 10 Basis Point (0.10%) Rule**:
  - Requires a 10 bps breach (approx 24 NQ handles) in $Q_1$ to confirm sustainable RTH momentum.
  - Failure to reach 10 bps and returning inside 0-5 box flags a false breakout, establishing an **Instant High/Low**.

---

## 3. Mickey's Execution & Position Management Playbook

### Rule 1: Buying Red & Selling Green
- **Never buy green breakout candles or sell red breakdown candles blindly**.
- Buy red pullback candles in bullish daily configurations (pullbacks to $C_2$ Open or 09:00 50% line).
- Sell green rally candles in bearish daily configurations.

### Rule 2: Risk & Invalidation
- **Stop Loss Placement**: Placed strictly at the structural invalidation point ($C_2$ Open Price or $C_2$ Low/High).
- **Position Sizing**: Risk amount (e.g. $225 on a $4,500 account = 5% risk) divided by distance to invalidation stop.

### Rule 3: 3-Tier Take Profit (TP) Scaling System
1. **TP1 (Cover the Queen)**: Close **50% of contracts at 10 basis points** (approx 24 NQ handles) or when profit equals initial risk ($1\text{R}$). Position becomes completely risk-free.
2. **TP2 (Statistical Target)**: Close remaining portion at **P30** (reliable cash-flow target) or **P50 (Median MFE)** of historical expansion (e.g. 50% of the 09:30–10:00 DRO).
3. **TP3 (Time-Based / Reversal Exit)**: Hard exit all remaining runners at **09:44 AM EST** before the high-probability 09:45 AM morning pivot window.

---

## 4. Intraday Verification Protocol (1m OHLCV Backtest)

To verify that Candle Science probabilities hold up in actual intraday price action, our validation engine must test 1m OHLCV bars for specific historical dates:

```
[Target Date T]
   ├── 1. Read C1 (T-2) and C2 (T-1) Daily OHLC
   ├── 2. Extract C2 Open, C2 High, C2 Low, C1 Color Magnifier
   ├── 3. Track RTH 1m Bars (09:30 - 16:00 ET):
   │      ├── Check C3 Open vs C2 Open
   │      ├── Monitor C2 Open Breach Timestamp (Did P(High/Low) flip as predicted?)
   │      ├── Measure Q1 (09:30-09:45) 0-5 Box 10 bps Breach (24 NQ pts)
   │      ├── Measure TP1 (10 bps / 1R) Hit Time
   │      ├── Measure TP2 (P30 / P50 Median MFE) Hit Time
   │      └── Measure Exit at 09:44 AM vs 09:45 AM Reversal Pivot
   └── 4. Compute Intraday Alignment Scorecard
```

---
*Document Location: `docs/features/CandleScience/BLUEPRINT.md`*
