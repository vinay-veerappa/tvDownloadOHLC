# Gamma Exposure (GEX) & Market Maker Positioning — Research Backlog F9

> **NotebookLM Knowledge Base**: [Gamma Exposure (GEX) & Market Maker Hedging Strategies](https://notebooklm.google.com/notebook/dbbc0d63-d9df-4378-a958-d8f15ac60f3b) (`dbbc0d63-d9df-4378-a958-d8f15ac60f3b`)
> **Standard**: Universal Basis Points (bps), Zero Lookahead, Closed-Bar Execution.
> **Structural Domain**: Market Microstructure & Dealer Delta/Gamma Hedging Obligations.

---

## Domain Overview & Dealer Microstructure Mechanics

Unlike retail price indicators, **Gamma Exposure (GEX)** measures non-discretionary dealer inventory rebalancing:
* **Positive Gamma Regime ($GEX > 0$)**: Option market makers are net long gamma. As the underlying price rises, dealers must sell futures/underlying to maintain delta neutrality; as price falls, dealers must buy. This creates **volatility dampening and mean reversion** toward high-open-interest strike anchors (Call Wall, Put Wall, Absolute Gamma Strike).
* **Negative Gamma Regime ($GEX < 0$)**: Option market makers are net short gamma. As price falls, dealers are forced to sell into declining markets; as price rises, dealers must buy into rallies. This creates **volatility acceleration, directional momentum cascades, and sharp expansion**.
* **Zero Gamma Flip Point**: The critical inflection boundary where dealer hedging flips from stabilizing (mean-reverting) to destabilizing (trend-accelerating).

---

## GEX-1. SPX Zero Gamma Regime Router & Volatility Trigger
**Status**: ⬜ (Candidate for Hunter Integration)

* **Source**: Doc McGraw SPX Gamma Roadmaps (`DlBD7Jw-7Hc`, `ppbBzKSZN1o`), SpotGamma, MenthorQ.
* **Triage Score**: **92 / 100** (Pass)
  * *G1 (Rule Precision)*: 28/30 (Strict mathematical threshold: Price relative to Zero Gamma strike).
  * *G2 (Risk Architecture)*: 23/25 (Defined stop beyond inflection strike; +10 bps TP1 scale-out).
  * *G3 (Lookahead Immunity)*: 20/20 (Calculated prior to 09:30 RTH open from 08:30 CBOE option open interest).
  * *G4 (Friction Resilience)*: 12/15 (Trades on liquid SPX/ES/NQ instruments).
  * *G5 (Regime Specificity)*: 9/10 (Explicitly conditions trend continuation vs mean-reversion).
* **Core Hypothesis**: When SPX opens and sustains below the Zero Gamma Flip level, intraday breakout continuation setups exhibit >65% directional follow-through, whereas opens above the Flip level produce mean reversion toward the Call Wall or High OI node with >70% pinning probability.
* **Independent Test Arms**:
  * `Arm 0 (Baseline)`: Raw ORB breakout or mean-reversion without GEX state.
  * `Arm 1`: GEX Regime Gate (Longs permitted only above Zero Gamma; Shorts permitted only below Zero Gamma).
  * `Arm 2`: GEX Regime Gate + Gamma Distance (Distance from Zero Gamma $\ge 15$ bps to filter chop near the flip line).
* **Mechanics**:
  * *Timeframe*: 1m / 5m ES1/NQ1 execution; Daily GEX strike calculations.
  * *Setup*: Compute Net GEX across all active strikes. Identify Strike $K_{zero}$ where Net GEX = 0.
  * *Trigger*: 
    * *Short Acceleration*: Price crosses below $K_{zero}$ with 5m bar close confirming $Close < K_{zero} - 2\text{ bps}$.
    * *Long Mean Reversion*: Price sweeps Put Wall / $K_{zero}$ and prints 5m bullish rejection candle back above $K_{zero}$.
  * *Risk*: Stop Loss placed 15 bps beyond $K_{zero}$; Target 1 (+10 bps "Cover the Queen" scale-out); Target 2 (Call Wall or Put Wall anchor).
* **Param Grid**:
  * Gamma Calculation: `["All_Expirations", "0DTE_Only"]`
  * Buffer Bps: `[2.0, 5.0, 10.0]`

---

## GEX-2. Call Wall & Put Wall Boundary Fade (Long Gamma Regime)
**Status**: ⬜

* **Source**: Doc McGraw SPX IF/THEN Roadmaps (`DlBD7Jw-7Hc`), ShadowTrader Market Profile (`XChcBeixyCY`).
* **Triage Score**: **88 / 100** (Pass)
* **Core Hypothesis**: In positive gamma regimes ($GEX > 0$), price probes into the Call Wall (highest call gamma) or Put Wall (highest put gamma) are absorbed by dealer counter-hedging, resulting in mean-reversion fades back toward the Volume POC / Volatility Trigger with >62% win rate.
* **Independent Test Arms**:
  * `Arm 0`: Raw fade on first touch of Call/Put Wall.
  * `Arm 1`: Fade conditioned on $GEX > 0$ and 15m candle rejection wick ($\ge 50\%$ upper/lower wick).
  * `Arm 2`: Fade conditioned on $GEX > 0$ + CVD absorption divergence at the wall.
* **Mechanics**:
  * *Setup*: Net GEX > 0. Mark Call Wall ($K_{call\_max}$) and Put Wall ($K_{put\_max}$).
  * *Trigger*: Price touches within 5 bps of $K_{call\_max}$ (for short) or $K_{put\_max}$ (for long), and subsequent 5m bar closes back inside the boundary.
  * *Risk*: Stop Loss placed 12 bps beyond the Wall extreme; TP1 +10 bps (50% scale-out + BE lock); TP2 Session POC / Net Gamma Midpoint.
* **Param Grid**:
  * Proximity Threshold (bps): `[3.0, 5.0, 8.0]`
  * Rejection Wick Minimum: `[0.40, 0.50, 0.60]`

---

## GEX-3. Market Magnet Gravity & OPEX Pinning Excursion
**Status**: ⬜

* **Source**: Doc McGraw Daily GEX Roadmaps (`9VIodGJ59KA`), MenthorQ.
* **Triage Score**: **85 / 100** (Pass)
* **Core Hypothesis**: On OPEX days (Monthly 3rd Friday & Weekly Friday closes) after 13:30 ET, price deviations from the Maximum Net Gamma strike by $>30$ bps revert toward the pin strike before 16:00 ET due to gamma decay ($\theta$) and delta collapse.
* **Independent Test Arms**:
  * `Arm 0`: Unconditional 14:00 ET fade toward High OI strike.
  * `Arm 1`: Fade only when distance from Absolute Gamma Strike exceeds 25 bps.
  * `Arm 2`: Arm 1 + VIX < 18 (low systemic volatility environment).
* **Mechanics**:
  * *Setup*: OPEX Friday session. Calculate Absolute Net Gamma Strike $K_{abs}$.
  * *Trigger*: At 14:00 ET, if $|Price - K_{abs}| > 25\text{ bps}$, enter directional position toward $K_{abs}$.
  * *Risk*: Stop Loss: 20 bps from entry; Target: $K_{abs}$ (or 15:55 ET market-on-close hard exit).
