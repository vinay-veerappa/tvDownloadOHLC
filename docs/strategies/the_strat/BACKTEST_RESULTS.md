# The Strat Backtest Results & Optimization Log

## Test Parameters & Assumptions
- **Asset**: NQ1 (E-mini Nasdaq 100 Futures)
- **Timeframe**: 5-Minute
- **Historical Period**: 2024-01-01 to 2025-12-31 (2 full years, 146,983 5m bars)
- **Execution Friction**: 1 Tick Slippage ($0.25 pt) + $2.05 Commission per contract
- **Session Hours**: RTH Execution (09:30 - 15:30 ET)

---

## Institutional Trader Critique: The "1-2 Point Scalping Illusion"

### Why Micro-Scalps (< 5-10 pts on NQ) Fail in Live Trading:
1. **Friction Destruction**:
   On NQ, with a 1-tick entry slip ($0.25) + 1-tick exit slip ($0.25) + $4.10 round-turn commission, a 2-point gross scalp is reduced to a meager 1.3 pt net gain.
2. **Inverted Risk-Reward Ratio**:
   In a naive 2-1-2 where Target = `High[2]` (often only 2-3 pts away), but the Stop Loss is placed at `Low[1]` (6-12 pts away), the trade has an inverted $1:4$ risk-to-reward ratio. A single loss destroys 4 consecutive wins!
3. **Execution Latency & Volatility**:
   NQ has an intraday 5-minute ATR of 15–35 points. Trying to catch 2 points is picking up pennies in front of a steamroller.

---

## Institutional Upgrade: 15–25pt Targets + 2-Tier Execution (2024–2025)

We upgraded the engine to:
- Enforce a **minimum 15–20 pt Target 1** (or $0.75 \times \text{ATR}$).
- Implement **2-Tier Position Execution**: Scale 50% at Target 1, move Stop to Breakeven, and let the remaining 50% runner ride until 5m 9 EMA trailing breakdown.
- Blackout **midday chop (11:30–13:45 ET)**.

### Institutional Strategy Benchmark Table (NQ 5-Min, 2024–2025)

| # | Strategy Variant | Trades | Win Rate | Profit Factor | Net PnL ($) | Max DD ($) | Avg Win / Avg Loss | Avg Trade |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | **Inst 2-1-2 Trend Scalper (Min 15pt TP + Runner)** | 842 | **65.3%** | **1.50** | **+$56,929.76** | **$4,466.60** | **+15.7 pt / -19.2 pt** | **+3.59 pts** |
| **2** | **Inst 2-1-2 Trend Scalper (Min 20pt TP + Runner)** | 829 | **59.2%** | **1.45** | **+$59,620.56** | **$4,889.30** | **+19.7 pt / -19.4 pt** | **+3.80 pts** |
| **3** | **Inst 2-2 Reversals (Min 20pt TP + Runner)** | 2,883 | **58.2%** | **1.21** | **+$147,012.56** | **$17,561.60** | **+25.1 pt / -28.4 pt** | **+2.75 pts** |
| **4** | **Inst 2-2 Reversals (Min 25pt TP + Runner)** | 2,751 | **54.3%** | **1.19** | **+$139,351.26** | **$17,666.49** | **+29.1 pt / -28.6 pt** | **+2.74 pts** |
| **5** | **Master Institutional Strat Portfolio (15pt+)** | 3,518 | **63.0%** | **1.26** | **+$185,598.52** | **$20,324.60** | **+20.6 pt / -27.4 pt** | **+2.84 pts** |
| **6** | **Master Institutional Strat Portfolio (20pt+)** | 3,281 | **58.4%** | **1.23** | **+$175,043.79** | **$20,078.00** | **+24.4 pt / -27.3 pt** | **+2.87 pts** |

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
