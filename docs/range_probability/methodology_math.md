# Range Probability Methodology & Mathematical Foundations

## 1. Overview
The Range Probability Engine models intraday price auction dynamics by dividing trading into fixed-length range intervals ($T \in \{15, 30, 60, 120, 240\}$ minutes) anchored to the futures session opening hour (**18:00 ET**).

It establishes an empirical prior: **where a new range opens relative to the previous range's boundaries strongly conditions its likelihood of expanding beyond the prior high or low.**

---

## 2. Mathematical Definitions

### 2.1 Range Boundaries
For any completed range $R_{t-1}$:
- $\text{High}_{t-1} = \max_{i \in R_{t-1}} (\text{High}_i)$
- $\text{Low}_{t-1} = \min_{i \in R_{t-1}} (\text{Low}_i)$
- $\text{Span}_{t-1} = \text{High}_{t-1} - \text{Low}_{t-1}$
- $\text{Midpoint}_{t-1} = \frac{\text{High}_{t-1} + \text{Low}_{t-1}}{2}$

### 2.2 Normalized Opening Position ($\text{Pos}_t$)
When a new range $R_t$ opens with initial price $\text{Open}_t$:
$$\text{Pos}_t = \frac{\text{Open}_t - \text{Low}_{t-1}}{\text{High}_{t-1} - \text{Low}_{t-1}}$$

### 2.3 Discrete Decile Bucketing (12 States)
$$\text{Bucket}(\text{Pos}_t) = 
\begin{cases}
0, & \text{if } \text{Pos}_t < 0.0 \quad (\text{Opened below prior low}) \\
1, & \text{if } 0.0 \le \text{Pos}_t < 0.1 \quad (\text{Decile 1}) \\
2, & \text{if } 0.1 \le \text{Pos}_t < 0.2 \quad (\text{Decile 2}) \\
\vdots & \vdots \\
10, & \text{if } 0.9 \le \text{Pos}_t < 1.0 \quad (\text{Decile 10}) \\
11, & \text{if } \text{Pos}_t \ge 1.0 \quad (\text{Opened at/above prior high})
\end{cases}$$

### 2.4 Realized Resolution / Outcome
Evaluated strictly at the **Close of Range $R_t$ ($C_t$)**:
- **UP Resolution**: $C_t > \text{High}_{t-1}$
- **DOWN Resolution**: $C_t < \text{Low}_{t-1}$
- **INSIDE (No Result)**: $\text{Low}_{t-1} \le C_t \le \text{High}_{t-1}$

> **Note**: Intrabar wicks that breach prior levels but retrace to close inside are scored as `INSIDE`. Only the candle close at range expiration decides the resolution.

---

## 3. Probability Metrics & Formulas

For each specific tuple of $(\text{Timeframe}, \text{Slot}_{\text{HHMM}}, \text{Bucket})$:

### 3.1 Base Rate / Resolve Rate
$$P(\text{Outside}) = \frac{N_{\text{Up}} + N_{\text{Down}}}{N_{\text{Total}}}$$

### 3.2 Conditional Directional Probability
$$P(\text{Up} \mid \text{Outside}) = \frac{N_{\text{Up}}}{N_{\text{Up}} + N_{\text{Down}}}$$
$$P(\text{Down} \mid \text{Outside}) = \frac{N_{\text{Down}}}{N_{\text{Up}} + N_{\text{Down}}}$$

### 3.3 Unconditional Distribution (Sum to 100%)
- $P(\text{Close } > \text{High}_{t-1}) = P(\text{Up} \mid \text{Outside}) \times P(\text{Outside})$
- $P(\text{Close } < \text{Low}_{t-1}) = P(\text{Down} \mid \text{Outside}) \times P(\text{Outside})$
- $P(\text{Close Inside}) = 1.0 - P(\text{Outside})$

### 3.4 Statistical Significance (Z-Score)
Tests whether the directional edge deviates significantly from a 50/50 null hypothesis:
$$Z = \frac{\hat{p} - 0.50}{\sqrt{\frac{0.25}{N_{\text{resolved}}}}}$$
A $|Z| \ge 1.96$ indicates statistical significance at $p < 0.05$.

---

## 4. Pine Script LUT Encoding Specification

Each record in the lookup table is encoded as a compact **17-character ASCII string**:

| Field | Length | Description | Example |
|---|---|---|---|
| `Slot` | 4 chars | Time-of-day in ET (`HHMM`) | `1000` (10:00 ET) |
| `Bucket` | 1 char | Bucket character (`0`..`9`, `a`, `b`) | `9` (Decile 9) |
| `Direction` | 1 char | Preferred directional resolution | `U` (Up) or `D` (Down) |
| `Train Prob` | 3 chars | Training sample winning probability (%) | `084` (84%) |
| `Test Prob` | 3 chars | Held-out test winning probability (%) | `082` (82%) |
| `Sample N` | 3 chars | Historical sample size | `107` ($N=107$) |
| `Resolve Rate` | 2 chars | Base resolve rate (%) | `48` (48%) |

**Full Record Example**: `10009U08408210748`
- Slot: `10:00 ET`
- Bucket: `9` (0.8 - 0.9)
- Direction: `U` (Closes Above High)
- Train Prob: `84%`, Test Prob: `82%`
- Sample: `107` ranges, Resolve: `48%`
