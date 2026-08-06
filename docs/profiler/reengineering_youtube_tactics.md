# Post-Market Re-Engineering & Performance Analytics SOP

> **Source**: NotebookLM - *Pack Trading Reengineering YouTube Sessions* (`31b98584-2dbc-4fcc-9f12-d5fd2034d281`)
> **Authors**: Matt Mickey & Austin
> **Purpose**: Systematic post-market re-engineering, daily classification verification, MAE/MFE analytics, manual data collection, and edge resetting protocols.

---

## 1. The Core 3-Step Re-Engineering Framework

1. **Step 1: Project In-Stat & Out-of-Stat Daily Extremes**:
   - Identify where daily candle wicks are statistically high-probability to form vs. which extremes are unlikely to be violated.
2. **Step 2: Pre-Market P12 Level Interactions**:
   - Analyze how live price accepts or rejects P12 High, Low, and Mid (18:00–06:00).
   - *Rule*: P12 defines the first half of the daily candle; observing whether live price accepts or rejects P12 Mid provides the directional switch for 09:30 distribution.
3. **Step 3: Daily Profiler Conditional Cross-Reference**:
   - Input overnight session variables to run conditional probabilities (session True vs. False breakout rates) and establish concrete targets.

---

## 2. Intraday Daily Classifications & Signatures

| Classification | Structural Live Price Signature | Strategy SOP |
| :--- | :--- | :--- |
| **Range One (R1)** | Price repeatedly sweeps **both sides** of the 09:00 or 09:30 open range box. | Mean-reversion & quick cash-flow scalps. |
| **Range Two (R2)** | Consolidated morning range where core expansion or major reversal starts later (**around 11:00 AM**). | Wait for 11:00 AM expansion signature before entering. |
| **Directional No Pullback (DNP)** | Expansive trend session with high follow-through without retracements. | Momentum continuation. Buy dips / sell rips only. |
| **Directional With Pullback (DWP)** | 09:30 range holds with **no sweeping action** back into the open range after the first 5 minutes. | Ride initial momentum, transition to short-range scalps in afternoon. |

---

## 3. End-of-Session Review Protocols

### 1. Manual Data Collection vs. Automated Overfitting
- Hand-collecting data forces traders to observe live price nuances, validate variables, and avoid static target overfitting.
- Build high-probability environment models rather than rigid static stops/TPs.

### 2. Using Statistics to Identify Statistical Failure
- Recognize when 80%–90% probability levels fail to get swept by major time cut-offs (**09:45 AM or 10:45 AM**).
- *Rule*: Blowing past a 90% probability level indicates extreme institutional trend strength in the opposite direction.

### 3. Resetting the Edge
- When market action becomes foggy, choppy, or falls outside a trader's core strength (e.g., trend trader in a Range 1 day), reset focus to the next clean time anchor (**12:00 PM, Midnight, 21:00**) rather than overtrading.

---

## 4. Trade Performance & Risk Metrics

### 1. MAE & MFE Percentile Distributions
- **25th Percentile**: ~10 basis points (initial cash flow target).
- **50th Percentile (Median)**: ~20 basis points (primary target).
- **75th Percentile**: ~50 basis points (runner target).

### 2. "Covering the Queen" (Core Cash Flow Protocol)
- Scale out half of the position at 10 basis points to eliminate risk, cover stop loss, and secure a risk-free runner.

### 3. Business Plan Variance Management
- Monitor Consecutive Loss & Max Drawdown metrics to manage strategy variance and preserve funded accounts.

---
*Last Updated: 2026-08-05. Extracted from 53 processed live Re-Engineering YouTube sessions.*
