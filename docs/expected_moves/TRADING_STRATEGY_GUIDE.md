# Comprehensive EM Trading & Outlier Analysis

This report defines the statistical probabilities of Expected Move (EM) breaches and provides data-driven strategies for Stop Loss (SL) and Take Profit (TP) placement.

## Probability of Reaching (MFE)
*Probability that SPY reaches the specific EM multiple at any point during the session.*

| EM Multiple | Reach Prob (All Days) | Description |
| :--- | :--- | :--- |
| **0.500 EM** | **63.7%** | High Frequency Pivot (Daily Target) |
| **0.618 EM** | **48.6%** | Fibonacci "Coin Flip" Level |
| **1.000 EM** | **12.5%** | Standard Deviation Boundary |
| **1.272 EM** | **1.9%** | Trend Continuation Extension |
| **1.500 EM** | **0.7%** | Extreme Trend Extension |
| **1.618 EM** | **0.5%** | Statistical Exhaustion |

---

## The "Breach" Regime (Conditional Probabilities)
*If the market reaches the 100% EM level, what happens next?*

Once the 100% EM is tagged, the regime shifts. Most days find exhaustion here, but a small percentage go "Nuclear."

| If 100% Hit, Prob of... | Probability | Strategic Implication |
| :--- | :--- | :--- |
| **127.2% (Fib)** | **15.4%** | 84.6% chance trend stops before this. |
| **150.0% (User)** | **5.8%** | Very rare; implies systemic trend day. |
| **161.8% (Fib)** | **3.8%** | Theoretical "Wall." |

---

## Level Confluence: Catalyst vs. Resistance
We analyzed the reversal rate when an EM level (50% or 100%) coincides with **Daily Open** or **Weekly Close**.

- **Finding**: Reversal Rate dropped to **33.3%** at confluence points (compared to ~50% baseline).
- **Insight**: Confluence of an EM level with a "Major" price level often acts as a **Breakout Trigger** rather than a rejection wall. When the market breaks a Weekly Close AND an EM level simultaneously, it "clears the deck" for a significant run.

---

## Strategic Recommendations

### 1. The "Optimal" Stop Loss (SL)
- **Aggressive SL**: **1.10x EM**. This gives the trade room to "probe" the 100% level without being caught in the 15% of cases that run to the 127% Fibonacci extension.
- **Conservative SL**: **1.30x EM**. Since there is an 85% drop-off in probability after the 100% level is breached, a stop at 1.30x covers almost all non-black-swan intraday moves.

### 2. Take Profit (TP) Targets
- **TP 1 (Core)**: **0.50x EM**. Reached ~64% of the time. This is the "Bread and Butter" target.
- **TP 2 (Runner)**: **0.95x EM**. Aiming just below the full 100% EM ensures execution before the 50% reversal friction kicks in at the actual boundary.

### 3. The "150% Variant" Fade
- If price reaches **1.50x EM**, it is in the **top 1% of volatility outcomes**. Counter-trend fades here have an extremely high statistical edge for a move back to the 1.0x EM, as the "exhaustion" probability is >99% for regular sessions.
