## 🏛️ WEEKLY MACRO EXECUTION HORIZON — 2026-06-29 to 2026-07-03

### 1. Executive Risk Core
The macro environment is dominated by a Negative GEX regime across major indices, signaling a trend-following environment where dealer hedging amplifies volatility. High skew premium in SPX (>3%) indicates significant put-heavy hedging demand, increasing the probability of accelerated downside velocity if support walls fail.

### 2. High-Impact Economic Milestones
- *No specific economic events provided in payload.*

### 3. AAPL — Structural Sandbox
**Spot Reference**: 282.5 (N/A%) | **Active GEX Tape**: POSITIVE / 21,479,421.71
**Primary Boundaries**: Call Wall: 285.0 | Put Wall: 280.0 | Zero Gamma: 279.94
**Weekly Risk Envelope**: Upper EM: 290.86 ↔ Lower EM: 274.14 (Straddle Pricing: ±2.96%)

**Mandated Execution Mode**:
- `TRACK B: PREMIUM/DISCOUNT FADE` -> Execute exclusively on mean-reversion; enter short at Call Wall or long at Put Wall targeting the Gamma Magnet.

**Tactical Boundary Scenarios**:
- 🟢 Bullish Acceleration: N/A (Breakouts strictly prohibited per Track B). Fade rallies toward 285.00.
- 🔴 Bearish Acceleration: N/A (Breakouts strictly prohibited per Track B). Fade selloffs toward 280.00.
- 🔄 Range Rebalancing: Price remains tethered between 280.00 and 285.00, oscillating toward the Gamma Magnet at 285.83.

### 3. IWM — Structural Sandbox
**Spot Reference**: 295.0 (N/A%) | **Active GEX Tape**: NEGATIVE / -10,464,846.56
**Primary Boundaries**: Call Wall: 300.0 | Put Wall: 290.0 | Zero Gamma: 296.89
**Weekly Risk Envelope**: Upper EM: 301.28 ↔ Lower EM: 288.72 (Straddle Pricing: ±2.13%)

**Mandated Execution Mode**:
- `TRACK A: BREAKOUT/MOMENTUM` -> Join established direction on retest of walls; trail stops aggressively and do not attempt to fade moves.

**Tactical Boundary Scenarios**:
- 🟢 Bullish Acceleration: Acceptance above 300.00 activates upside expansion. Target terminal boundary at 301.28.
- 🔴 Bearish Acceleration: Acceptance below 290.00 activates short hedging velocity. Target terminal liquidation boundary at 288.72.
- 🔄 Range Rebalancing: Price remains tethered between 290.00 and 300.00, oscillating toward the Gamma Magnet at 295.29.

### 3. QQQ — Structural Sandbox
**Spot Reference**: 706.0 (-4.38%) | **Active GEX Tape**: NEGATIVE / -191,251,078.14
**Primary Boundaries**: Call Wall: 715.0 | Put Wall: 690.0 | Zero Gamma: 725.0
**Weekly Risk Envelope**: Upper EM: 724.63 ↔ Lower EM: 687.37 (Straddle Pricing: ±2.64%)

**Mandated Execution Mode**:
- `TRACK A: BREAKOUT/MOMENTUM` -> Join established direction on retest of walls; trail stops aggressively and do not attempt to fade moves.

**Tactical Boundary Scenarios**:
- 🟢 Bullish Acceleration: Acceptance above 715.00 activates upside expansion. Target terminal boundary at 724.63.
- 🔴 Bearish Acceleration: Acceptance below 690.00 activates short hedging velocity. Target terminal liquidation boundary at 687.37.
- 🔄 Range Rebalancing: Price remains tethered between 690.00 and 715.00, oscillating toward the Gamma Magnet at 704.54.

### 3. SPX — Structural Sandbox
**Spot Reference**: 7353.01 (-1.97%) | **Active GEX Tape**: NEGATIVE / -435,814,570.27
**Primary Boundaries**: Call Wall: 7495.35 | Put Wall: 7313.77 | Zero Gamma: 7343.83
**Weekly Risk Envelope**: Upper EM: 7495.35 ↔ Lower EM: 7229.71 (Straddle Pricing: ±1.94%)

**Mandated Execution Mode**:
- `TRACK A: BREAKOUT/MOMENTUM` -> Join established direction on retest of walls; trail stops aggressively and do not attempt to fade moves.

**Tactical Boundary Scenarios**:
- 🟢 Bullish Acceleration: Acceptance above 7495.35 activates upside expansion. Target terminal boundary at 7476.31.
- 🔴 Bearish Acceleration: Acceptance below 7313.77 activates short hedging velocity. Target terminal liquidation boundary at 7229.71.
- 🔄 Range Rebalancing: Price remains tethered between 7313.77 and 7495.35, oscillating toward the Gamma Magnet at 7343.83.

### 3. SPY — Structural Sandbox
**Spot Reference**: 731.2 (-2.01%) | **Active GEX Tape**: NEGATIVE / -435,814,570.27
**Primary Boundaries**: Call Wall: 743.0 | Put Wall: 725.0 | Zero Gamma: 727.98
**Weekly Risk Envelope**: Upper EM: 743.42 ↔ Lower EM: 718.98 (Straddle Pricing: ±1.67%)

**Mandated Execution Mode**:
- `TRACK A: BREAKOUT/MOMENTUM` -> Join established direction on retest of walls; trail stops aggressively and do not attempt to fade moves.

**Tactical Boundary Scenarios**:
- 🟢 Bullish Acceleration: Acceptance above 743.00 activates upside expansion. Target terminal boundary at 743.42.
- 🔴 Bearish Acceleration: Acceptance below 725.00 activates short hedging velocity. Target terminal liquidation boundary at 718.98.
- 🔄 Range Rebalancing: Price remains tethered between 725.00 and 743.00, oscillating toward the Gamma Magnet at 727.98.

### 4. Account Protection & Invalidation Metrics
- **AAPL**: Structural Model Fractures at 274.14 (downside) / 290.86 (upside). Distribution model fractured. Cease all strategy execution on AAPL if price achieves a 30-minute close acceptance beyond 274.14 (bullish break) or 290.86 (bearish break).
  - Distance to bullish invalidation: 2.96% | Distance to bearish invalidation: 2.96%
- **IWM**: Structural Model Fractures at 288.72 (downside) / 301.28 (upside). Distribution model fractured. Cease all strategy execution on IWM if price achieves a 30-minute close acceptance beyond 288.72 (bullish break) or 301.28 (bearish break).
  - Distance to bullish invalidation: 2.13% | Distance to bearish invalidation: 2.13%
- **QQQ**: Structural Model Fractures at 687.37 (downside) / 724.63 (upside). Distribution model fractured. Cease all strategy execution on QQQ if price achieves a 30-minute close acceptance beyond 687.37 (bullish break) or 724.63 (bearish break).
  - Distance to bullish invalidation: 2.64% | Distance to bearish invalidation: 2.64%
- **SPX**: Structural Model Fractures at 7229.71 (downside) / 7495.35 (upside). Distribution model fractured. Cease all strategy execution on SPX if price achieves a 30-minute close acceptance beyond 7229.71 (bullish break) or 7495.35 (bearish break).
  - Distance to bullish invalidation: 1.68% | Distance to bearish invalidation: 1.94%
- **SPY**: Structural Model Fractures at 718.98 (downside) / 743.42 (upside). Distribution model fractured. Cease all strategy execution on SPY if price achieves a 30-minute close acceptance beyond 718.98 (bullish break) or 743.42 (bearish break).
  - Distance to bullish invalidation: 1.67% | Distance to bearish invalidation: 1.67%

### 5. Key Risks This Week
- **Regime Conflict**: AAPL is the sole asset in a Positive GEX (pinned) regime; any shift toward Negative GEX will invalidate the "Fade" mandate.
- **S&P Put Skew**: SPX skew premium at 3.82% indicates aggressive hedging; a breach of the 7313.77 Put Wall likely triggers a rapid move toward the 7229.71 invalidation boundary.
- **Tight Invalidation Windows**: SPY/SPX have the narrowest risk envelopes (<2%), leaving minimal room for error before account invalidation.

### 6. Watch List
1. Monitor SPX 7313.77 Put Wall for 30-min close acceptance (Trigger for bearish momentum).
2. Monitor AAPL 280.00/285.00 boundaries for fade entries toward 285.83.
3. Track QQQ 690.00 Put Wall for short-hedging velocity activation.
4. Monitor IWM 300.00 Call Wall for upside expansion trigger.
5. Daily check of 30-min closes against all Invalidation Prices listed in Section 4.