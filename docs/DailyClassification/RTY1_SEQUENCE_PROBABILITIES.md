# RTY1 Sequential Classification Analysis

This document analyzes the probability of today's Daily Classification (R1, R2, DWP, DNP) based on previous day sequences.

## 1. Daily Transition Matrix (P(Today | Yesterday))
If Yesterday was X, what is the probability of Today being Y?

| Yesterday \ Today | R1% | R2% | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DNP** | **22.3%** | **24.5%** | **38.9%** | **14.3%** | 314 |
| **DWP** | **18.8%** | **32.6%** | **33.8%** | **14.8%** | 772 |
| **R1** | **17.8%** | **32.5%** | **35.6%** | **14.0%** | 421 |
| **R2** | **19.8%** | **29.6%** | **36.0%** | **14.6%** | 663 |

## 2. Common 3-Day Patterns
Most frequent sequences of 3 days and what usually follows on Day 4.

| 3-Day Sequence | n | Next Day (Day 4) Probabilities |
| :--- | :--- | :--- |
| DWP -> R2 -> DWP | 97 | **R2**=36%, **DWP**=26%, **R1**=23% |
| DWP -> DWP -> DWP | 94 | **DWP**=39%, **R2**=21%, **DNP**=20% |
| R2 -> DWP -> R2 | 85 | **DWP**=39%, **R2**=27% |
| DWP -> DWP -> R2 | 79 | **DWP**=37%, **R2**=27%, **R1**=22% |
| R2 -> R2 -> DWP | 71 | **DWP**=32%, **R2**=32%, **R1**=23% |
| R2 -> DWP -> DWP | 69 | **R2**=42%, **DWP**=32% |
| DWP -> R2 -> R2 | 66 | **R1**=32%, **DWP**=30%, **R2**=29% |
| DWP -> R1 -> DWP | 62 | **DWP**=35%, **R2**=31% |
| R2 -> R2 -> R2 | 61 | **DWP**=39%, **R2**=28% |
| R1 -> DWP -> DWP | 52 | **R2**=37%, **DWP**=29%, **R1**=21% |

## 3. Streak Analysis
Does the probability change after N consecutive days of the same type?

- After 2x **R1** (n=61): **R2 (39.3%)** | Continuation: 19.7%
- After 3x **R1** (n=12): **R2 (41.7%)** | Continuation: 16.7%
- After 2x **R2** (n=134): **DWP (35.1%)** | Continuation: 32.8%
- After 3x **R2** (n=44): **DWP (40.9%)** | Continuation: 22.7%
- After 2x **DWP** (n=167): **R2 (35.3%)** | Continuation: 34.1%
- After 3x **DWP** (n=57): **DWP (36.8%)** | Continuation: 36.8%
- After 2x **DNP** (n=38): **R1 (34.2%)** | Continuation: 15.8%
- After 3x **DNP** (n=6): **R2 (50.0%)** | Continuation: 16.7%
