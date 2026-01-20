# ES1 Sequential Classification Analysis

This document analyzes the probability of today's Daily Classification (R1, R2, DWP, DNP) based on previous day sequences.

## 1. Daily Transition Matrix (P(Today | Yesterday))
If Yesterday was X, what is the probability of Today being Y?

| Yesterday \ Today | R1% | R2% | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DNP** | **26.1%** | **35.0%** | **24.7%** | **14.2%** | 777 |
| **DWP** | **24.7%** | **36.6%** | **23.6%** | **15.0%** | 1316 |
| **R1** | **23.9%** | **34.6%** | **26.1%** | **15.3%** | 1266 |
| **R2** | **24.5%** | **32.7%** | **27.2%** | **15.6%** | 1772 |

## 2. Common 3-Day Patterns
Most frequent sequences of 3 days and what usually follows on Day 4.

| 3-Day Sequence | n | Next Day (Day 4) Probabilities |
| :--- | :--- | :--- |
| R2 -> DWP -> R2 | 182 | **R2**=36%, **DWP**=29% |
| DWP -> R2 -> R2 | 173 | **R2**=34%, **R1**=28%, **DWP**=21% |
| R2 -> R2 -> R2 | 168 | **DWP**=30%, **R2**=28%, **R1**=24% |
| R2 -> R2 -> R1 | 160 | **R2**=35%, **R1**=27%, **DWP**=24% |
| R2 -> R1 -> R2 | 151 | **R2**=33%, **DWP**=31%, **R1**=24% |
| R2 -> R2 -> DWP | 149 | **R2**=32%, **R1**=30%, **DWP**=23% |
| R1 -> R2 -> R2 | 149 | **R1**=31%, **R2**=28%, **DWP**=25% |
| DWP -> R2 -> DWP | 138 | **R2**=44%, **R1**=22%, **DWP**=20% |
| R2 -> DWP -> R1 | 127 | **DWP**=33%, **R2**=28%, **R1**=21% |
| R1 -> R2 -> DWP | 121 | **R2**=40%, **R1**=26%, **DWP**=21% |

## 3. Streak Analysis
Does the probability change after N consecutive days of the same type?

- After 2x **R1** (n=229): **R2 (35.8%)** | Continuation: 26.2%
- After 3x **R1** (n=60): **R2 (31.7%)** | Continuation: 20.0%
- After 2x **R2** (n=411): **R2 (29.2%)** | Continuation: 29.2%
- After 3x **R2** (n=120): **DWP (30.0%)** | Continuation: 26.7%
- After 2x **DWP** (n=243): **R2 (37.0%)** | Continuation: 23.0%
- After 3x **DWP** (n=56): **R2 (37.5%)** | Continuation: 19.6%
- After 2x **DNP** (n=95): **R2 (32.6%)** | Continuation: 15.8%
- After 3x **DNP** (n=15): **R2 (60.0%)** | Continuation: 0.0%
