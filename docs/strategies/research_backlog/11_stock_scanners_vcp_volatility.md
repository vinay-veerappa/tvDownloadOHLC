# Stock Scanners, Screeners & Volatility Systems — Research Backlog F11

> **Dedicated Google NotebookLM Registries**:
> 1. **Stock Scanners & Screeners**: [80b7afae-c643-4af5-89ce-fdf309ab3034](https://notebooklm.google.com/notebook/80b7afae-c643-4af5-89ce-fdf309ab3034)
> 2. **Volatility Systems & VCP**: [6c55f605-5ce5-4530-bba4-14c4be9a4cfd](https://notebooklm.google.com/notebook/6c55f605-5ce5-4530-bba4-14c4be9a4cfd)
> **Standard**: Universal Basis Points (bps) & Percentage Travel, Zero Lookahead, Finviz / Trade Ideas Math.

---

## Domain Architecture

Professional equity desks operate an algorithmic funnel:
1. **Universe Screening (Scanners)**: Filter 10,000+ US equities down to the top 0.1% displaying abnormal institutional participation (Relative Volume $\text{RVOL} \ge 2.0\times$), catalyst gapping, or fundamental episodic pivots.
2. **Setup Geometry (Volatility Contraction)**: Identify mathematical coiling (Mark Minervini's VCP, Toby Crabel's NR7, Linda Raschke's 80-20 rule) where risk is bounded within tiny price percentages (2–5%).
3. **Execution & Risk Management**: Enter on volume-confirmed pivot breaks with stops under the contraction pivot low and targets scaled out dynamically.

---

## Section 1: Algorithmic Stock Scanners (`stock_scanners_screeners`)

### SCAN-1. Pradeep Bonde (Stockbee) Episodic Pivot (EP) Engine
**Status**: ⬜

* **Source**: Richard Moglen / TraderLion (`H1fUbgfutAo`), Pradeep Bonde (`aXqr5YVMjQQ`).
* **Triage Score**: **94 / 100** (Pass)
* **Core Hypothesis**: A stock opening with a $>8\%$ gap on $>3\times$ 50-day average volume driven by a fundamental catalyst (earnings blowout, FDA approval, guidance raise) represents institutional institutional regime change, producing sustained multi-week continuation with win rate $>68\%$.
* **Quantitative Screener Criteria**:
  1. Price $\ge \$5.00$; 50-day Average Daily Volume $\ge 100,000$ shares.
  2. 1-day percentage change: $\ge +8\%$.
  3. Relative Volume: $\text{RVOL} \ge 3.0\times$ (or Day 1 Volume $\ge 1,000,000$ shares).
  4. Day 1 Close: Closes in the upper $30\%$ of the daily range (Close $\ge \text{Low} + 0.70 \times (\text{High} - \text{Low})$).
* **Execution Trigger**: Enter on Day 1 at the break of the first 5m/15m opening range high, OR on Day 2 upon breaking the Day 1 high.
* **Risk Management**: Stop Loss placed at the Day 1 low (or 1st 15m candle low for day trade); Target: hold 3–5 days with trailing stop on 10 EMA.

### SCAN-2. Momentum Burst & 4% Gapper Scanner
**Status**: ⬜

* **Source**: Stockbee Momentum Burst (`aXqr5YVMjQQ`), Warrior Trading (`HpA3dWHPnkI`, `JiGRJAy4Ufg`).
* **Triage Score**: **89 / 100** (Pass)
* **Core Hypothesis**: Stocks breaking out of a 3-to-5 day tight consolidation ($Range \le 3\%$) with a 1-day burst $\ge +4\%$ and $\text{RVOL} \ge 2.0\times$ produce a rapid 3-to-5 day directional continuation.
* **Quantitative Screener Criteria**:
  * Prior 3 days price range: $\max(\text{High}) - \min(\text{Low}) \le 0.04 \times \text{Price}$.
  * Today's Gain: $\ge +4.0\%$.
  * Today's Volume: $\ge 2.0 \times \text{SMA}(Volume, 20)$.

---

## Section 2: Volatility Contraction & Breakout Systems (`volatility_systems_vcp`)

### VCP-1. Mark Minervini Volatility Contraction Pattern (VCP)
**Status**: ⬜

* **Source**: Mark Minervini (`M_tD6X0CSOI`, `Tm0dkf8_giA`), TraderLion.
* **Triage Score**: **95 / 100** (Pass)
* **Core Hypothesis**: A stock in a Stage 2 structural uptrend undergoing 2 to 4 successive contractions of decreasing depth (e.g., $T_1: -18\% \to T_2: -8\% \to T_3: -3\%$) accompanied by volume drying up to $<50\%$ of 50-day average has exhausted seller supply, resulting in explosive breakout expansion.
* **Quantitative Rulebook**:
  1. **Trend Template Gate**:
     * $Price > SMA_{50} > SMA_{150} > SMA_{200}$.
     * $SMA_{200}$ trending upward for at least 1 month.
     * Price is at least $30\%$ above its 52-week low and within $25\%$ of its 52-week high.
  2. **Contraction Geometry**:
     * Contraction 1 ($T_1$): $-10\%$ to $-25\%$ depth over 2–6 weeks.
     * Contraction 2 ($T_2$): $-5\%$ to $-12\%$ depth over 1–3 weeks.
     * Contraction 3 ($T_3$): $-2\%$ to $-5\%$ depth over 3–10 days (tight pivot area).
  3. **Volume Dry-Up**: Volume on the final contraction must fall below $60\%$ of the 50-day average.
* **Trigger**: Buy Stop placed at the high of the final tight contraction pivot $+1$ tick.
* **Risk**: Stop loss placed strictly at the pivot low ($2.5\%$ to $5.0\%$ max risk floor); Profit target: scale out $1/3$ at $+3\times$ risk, trail balance on 20 EMA.

### VCP-2. Toby Crabel NR7 & Inside Day (ID-NR4) Expansion System
**Status**: ⬜

* **Source**: Toby Crabel (`QtIQplVNHO0`, `f5mZfQ3dVaA`), StockCharts School.
* **Triage Score**: **91 / 100** (Pass)
* **Core Hypothesis**: When daily price range contracts to the narrowest bar of the last 7 sessions (NR7) or an inside day that is narrowest in 4 sessions (ID-NR4), price is at peak compression and resolves into a sustained directional expansion on the next session's open.
* **Quantitative Formula**:
  * $\text{Range}_t = \text{High}_t - \text{Low}_t$.
  * Condition: $\text{Range}_t < \min(\text{Range}_{t-1}, \dots, \text{Range}_{t-6})$.
* **Trigger**: Bracket order on Day $t+1$: Buy Stop at $\text{High}_t + 1$ tick, Sell Stop at $\text{Low}_t - 1$ tick.
* **Risk**: Stop Loss placed at the opposite extreme of the NR7 bar; Target: $1.5\times$ the NR7 range width.

### VCP-3. Linda Raschke 80-20 Reversal Setup
**Status**: ⬜

* **Source**: Linda Raschke (`kv2H152ISdM`, `bjexjGcLn8g`).
* **Triage Score**: **88 / 100** (Pass)
* **Core Hypothesis**: An intraday candle that opens in the bottom $20\%$ of its range and closes in the top $20\%$ (or opens in top $20\%$ and closes in bottom $20\%$) reflects extreme exhaustion of momentum, yielding an $80\%$ probability of a morning reversal on the following session.
* **Quantitative Formulas**:
  * Bullish Setup: $\text{Open} \le \text{Low} + 0.20 \times (\text{High} - \text{Low})$ AND $\text{Close} \ge \text{High} - 0.20 \times (\text{High} - \text{Low})$.
  * Next Day Trigger: Sell short if price on Day $t+1$ rallies to test $\text{High}_t$ and reverses back below $\text{High}_t$ by 5 bps.
  * Stop Loss: Placed 10 bps above the high of the test; Target: Day $t$ midpoint ($50\%$ retracement).
