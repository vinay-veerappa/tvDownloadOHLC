# Consolidation, Range Trading & Anti-Chop Architecture — Research Backlog F12

> **NotebookLM Knowledge Base**: [Consolidation & Range Day Trading Strategies](https://notebooklm.google.com/notebook/b52fb636-8a91-40f3-9035-def8b94cb090) (`b52fb636-8a91-40f3-9035-def8b94cb090`)
> **Standard**: Universal Basis Points (bps), Zero Lookahead, Closed-Bar Execution.
> **Core Theme**: Regime Classification, Box Identification & Systematic Capital Protection against Chop.

---

## 1. Mathematical Regime Identification & Chop Detection

Trading systems must programmatically distinguish between **trending (expansion)** and **ranging (compression)** regimes. Deploying trend-following algorithms in chop produces repeated whipsaws:

* **Kaufman Efficiency Ratio (KER)**:
  $$\text{KER} = \frac{|\text{Close}_t - \text{Close}_{t-n}|}{\sum_{i=0}^{n-1} |\text{Close}_{t-i} - \text{Close}_{t-i-1}|}$$
  * $\text{KER} \ge 0.60$: Highly efficient trend. Engage momentum/breakout hunters.
  * $\text{KER} < 0.30$: Mathematically proven chop. **Disable trend hunters; activate range boundary fades**.
* **Average Directional Index (ADX)**:
  * $\text{ADX} < 20$: Range-bound environment. Mean-reversion gates enabled.
  * $\text{ADX} \ge 20$: Trending environment. Range-fade gates automatically disabled.
* **Ornstein-Uhlenbeck (OU) Mean-Reversion Half-Life**:
  $$dx = \kappa (\theta - x)dt + \sigma dW, \quad \text{Half-Life} = \frac{\ln(2)}{\kappa}$$
  * A stationary deviation with a known $\kappa$ dictates the optimal holding period and time-stop (1.0 to 1.5 half-lives). If reversion does not complete within this window, exit immediately.

---

## 2. Structural Consolidation Boxes & Volume Profile Framework

* **Darvas & Congestion Boxes**:
  * Formed when price creates an established swing high and low and oscillates within those boundaries for $\ge 5$ consecutive candles without exceeding extremes.
* **Volume Profile POC, VAH, and VAL Boundaries**:
  * **Value Area (VA)**: Contains $70\%$ of session volume ($1\sigma$).
  * **POC (Point of Control)**: The single highest-volume transacted price. Acts as an equilibrium magnet.
  * **HVN (High Volume Nodes)**: Areas of price agreement. Price grinds and slows inside HVNs (ideal targets, poor breakout entries).
  * **LVN (Low Volume Nodes)**: Thin liquidity voids. Price accelerates rapidly through LVNs (high-probability continuation runways).

---

## 3. Dalton's 80% Rule Setup (`RANGE-80PCT`)
**Status**: ⬜

* **Source**: James Dalton "Mind Over Markets", Alchemy Markets, Bookmap Market Profile.
* **Triage Score**: **92 / 100** (Pass)
* **Core Hypothesis**: When a market opens outside or tests outside the prior day's Value Area and then records two consecutive 30-minute bar closes back inside the prior Value Area, there is an **80% historical probability** that price auctions across the entire range to test the opposite Value Area boundary.
* **Mechanics**:
  * *Timeframe*: 30m context; 5m entry refinement.
  * *Setup*: Mark Prior Day VAH and VAL. Price must explore outside the Value Area.
  * *Trigger*: Two consecutive 30m bars close back inside the Value Area (e.g. crossing back below VAH into the Value Area for short, or above VAL for long).
  * *Risk*: Stop Loss placed 15 bps outside the Value Area boundary; Target 1 at the POC; Target 2 at the opposite Value Area extreme (VAL/VAH).
* **Param Grid**:
  * Timeframe: `["30m_Closes", "15m_Closes"]`
  * Stop Buffer: `[10.0, 15.0, 20.0]` bps

---

## 4. The 5 Anti-Chop Defensive Rules & Circuit Breakers

To protect trading capital during choppy regimes, every intraday strategy in this repo adheres to the following five rules:

1. **The Minimum Range Width Gate**:
   * Never trade a breakout if the box or initial opening range height is $< 20\text{ bps}$ ($0.20\%$ of asset price). Sub-20 bps ranges are statistical noise.
2. **The 1-Minute Volatility Gate (ATR Ratio)**:
   * Condition: $0.7 \times \text{ATR}_{20} \le \text{ATR}_{1m} \le 1.8 \times \text{ATR}_{20}$.
   * $\text{ATR} < 0.7\times \implies$ dead, untradeable chop.
   * $\text{ATR} > 1.8\times \implies$ high-slippage news spike. Stand aside.
3. **Candle Close Rule (No Wick Execution)**:
   * Breakout entries require a full closed candle body outside the range boundary, followed by a pullback test of the broken boundary holding as new support/resistance.
4. **Time-Stop Decay**:
   * If a trade does not generate momentum within 3 to 6 bars after fill, exit at market. Do not sit in chop waiting for a stop loss to be tagged.
5. **Account-Level Circuit Breakers**:
   * Hard Daily Drawdown Limit: $-2R$ or $-3R$ maximum account loss per day.
   * **3 Consecutive Loser Cooling Pause**: After 3 consecutive losses, all automated trading is locked out for 60 minutes.
   * **5-Minute Post-Stop Cooldown**: Enforces a 5-minute freeze immediately after any stop-out to prevent revenge-trading churn.
