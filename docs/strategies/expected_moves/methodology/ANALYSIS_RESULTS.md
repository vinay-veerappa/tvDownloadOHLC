# Expected Move Accuracy Analysis (SPY)

This analysis compares the behavior of different Expected Move (EM) calculation methods against realized price action for **SPY** over a 500-day sample (2023-2025).

## Performance Comparison

| Method | Prediction Type | Containment (Close)% | Containment (Excur)% | Avg "Buffer" (Points) |
| :--- | :--- | :--- | :--- | :--- |
| **Straddle x0.85** | High Probability | **98.1%** | 95.2% | 9.23 |
| **VIX Scaled (2.0x)** | High Probability | **98.0%** | 96.6% | 8.99 |
| **VIX Raw (1-day)** | Standard 1-SD | 81.6% | 66.3% | 3.69 |
| **IV-252 (Trading)** | Standard 1-SD | 78.7% | 55.6% | 3.17 |
| **IV-365 (Calendar)**| Aggressive | 68.6% | 45.1% | 2.76 |

### Definitions
- **In (Close)%**: % of days where the Close-to-Close move stayed inside the EM range.
- **In (Excur)%**: % of days where the intraday High/Low extremes (absolute excursion from previous close) stayed inside the EM range.
- **Avg Buffer**: The average distance between the EM boundary and the actual realized move. A higher number indicates a "wider" or more conservative range.

## Key Findings

### 1. The "Safety" vs. "Precision" Trade-off
- **Straddle-Based EM** (and its VIX-scaled proxy) acts as a **High-Probability Boundary**. It captures nearly all (~95-98%) market moves, making it excellent for setting "Stop Loss" levels or "Safe" entry targets.
- **IV-365 / IV-252** act as **Statistical 1-SD Boundaries**. They are much tighter and "fail" about 20-30% of the time, which is consistent with the theoretical expectation that a 1-Standard Deviation move is exceeded ~32% of the time.

### 2. VIX as a "Scaled" Proxy
- The **VIX Scaled (2.0x)** method perfectly mirrors the behavior of the At-The-Money straddle. This validates our earlier experiment and confirms that for futures/indices without liquid option chains, doubling the 1-day VIX theoretical move is a highly reliable way to "synthesize" a straddle-based EM.

### 3. Calendars vs. Trading Days
- Using the **252-day** denominator (Trading Days) provides a significantly better "fit" (78% vs 68%) for daily price action than the 365-day calendar year denominator. 

## Recommendation

- **For Defensive Levels (Support/Resistance)**: Use **Straddle x 0.85** or **VIX Scaled (2.0x)**.
- **For Statistical Analysis / Edge Detection**: Use **IV-252** or **VIX Raw**, as they more closely represent the "normal" range of expectation.
