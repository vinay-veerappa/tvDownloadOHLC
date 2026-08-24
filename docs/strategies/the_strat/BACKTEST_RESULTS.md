# The Strat Backtest Results & Optimization Log

## Test Parameters & Assumptions
- **Asset**: NQ1 (E-mini Nasdaq 100 Futures)
- **Timeframe**: 5-Minute
- **Historical Period**: 2024-01-01 to 2025-12-31 (2 full years, 146,983 5m bars)
- **Execution Friction**: 1 Tick Slippage ($0.25 pt) + $2.05 Commission per contract
- **Session Hours**: RTH Execution (09:30 - 15:30 ET)

---

## Benchmark Comparison Table

| # | Strategy Configuration | Trades | Win Rate | Profit Factor | Net PnL ($) | Net Points | Max Drawdown | Avg Trade |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | **Pure 2-1-2 Continuation (Baseline)** | 1,499 | **77.5%** | **1.49** | **+$35,784.10** | **+1,789.2 pts** | **$3,870.80** | +1.40 pts |
| **2** | **High-Conviction 2-1-2 ($R:R \ge 1.0$)** | 28 | 60.7% | 1.24 | +$1,170.20 | +58.5 pts | $2,782.80 | +2.29 pts |
| **3** | **2-2 Momentum Reversals (RevStrat)** | 3,123 | **60.8%** | **1.22** | **+$147,200.70** | **+8,000.3 pts** | $30,160.80 | +2.56 pts |
| **4** | **3-1-2 Broadening Expansion Breakouts** | 71 | 49.3% | 1.05 | +$843.90 | +42.2 pts | $5,758.80 | +0.80 pts |
| **5** | **Multi-Setup Strat Portfolio** | 1,772 | **55.1%** | **1.29** | **+$120,449.80** | **+6,022.5 pts** | **$13,007.40** | **+3.60 pts** |

---

## Detailed Performance Breakdown: Top Strategies

### 1. Pure 2-1-2 Continuation
- **Win Rate**: **77.52%** (1,162 Wins / 337 Losses)
- **Profit Factor**: **1.49**
- **Max Drawdown**: **$3,870.80** (Extremely smooth equity curve)
- **Trade Duration**: Average 3.2 bars (16 minutes)
- **Mechanism**: The 2-1-2 continuation exploits the high-probability re-expansion of energy following inside bar coiling. Because the target (Magnitude 1) is simply the prior 2-bar extreme, it achieves rapid fill before mean-reverting.

### 2. 2-2 Momentum Reversals (RevStrat Traps)
- **Win Rate**: **60.81%** (1,899 Wins / 1,224 Losses)
- **Profit Factor**: **1.22**
- **Net Profit**: **+$147,200.70** (+8,000.25 pts NQ)
- **Avg Win / Avg Loss**: **+21.68 pts / -27.10 pts**
- **Mechanism**: Captures failure of directional continuation. When aggressive sellers attempt a 2D and fail, price snaps through the high of the 2D bar, creating rapid short-covering.

---

## Active Optimization Roadmap

| Phase | Target Mechanism | Hypothesis | Status |
|---|---|---|---|
| **Phase 1** | **FTFC Gating Filter** | Filtering 2-1-2 and 2-2 entries to only trade when $15\text{m} + 1\text{H} + \text{Daily}$ FTFC agree ($\text{Score} \ge +2$). | 🟢 In Progress |
| **Phase 2** | **Wick Ratio / Rejection Gate** | Requiring 2-2 reversals to have formed a Hammer/Shooter ($\ge 65\%$ wick rejection) before triggering. | 🟢 In Progress |
| **Phase 3** | **Dynamic 2-Tier Bracket Targets** | Taking 50% profit at Magnitude 1, moving stop to breakeven, and trailing runner along 5m EMA 9 to capture trend runners. | 🟡 Planned |
| **Phase 4** | **Session Time-of-Day Filter** | Restricting entries to 09:45–11:30 ET and 14:00–15:30 ET, eliminating lunchtime chop (12:00–13:30 ET). | 🟡 Planned |
| **Phase 5** | **Cross-Platform Reconciliation** | Running tick-by-tick reconciliation between NinjaTrader 8 Strategy Analyzer and Python trade logs to verify exact fill parity. | 🟡 Planned |
