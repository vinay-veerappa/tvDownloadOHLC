# YM1 Sequential Classification Analysis

This document analyzes the probability of today's Daily Classification (R1, R2, DWP, DNP) based on previous day sequences.

## 1. Daily Transition Matrix (P(Today | Yesterday))
If Yesterday was X, what is the probability of Today being Y?

| Yesterday \ Today | R1% | R2% | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DNP** | **24.3%** | **36.4%** | **26.2%** | **13.0%** | 645 |
| **DWP** | **24.0%** | **34.7%** | **28.1%** | **13.2%** | 1338 |
| **R1** | **17.6%** | **35.4%** | **32.1%** | **14.9%** | 998 |
| **R2** | **21.1%** | **35.5%** | **28.9%** | **14.5%** | 1631 |

## 2. Common 3-Day Patterns
Most frequent sequences of 3 days and what usually follows on Day 4.

| 3-Day Sequence | n | Next Day (Day 4) Probabilities |
| :--- | :--- | :--- |
| R2 -> R2 -> R2 | 218 | **R2**=35%, **DWP**=31%, **R1**=23% |
| DWP -> R2 -> R2 | 169 | **R2**=35%, **DWP**=25%, **DNP**=21% |
| R2 -> DWP -> R2 | 164 | **R2**=34%, **DWP**=32%, **R1**=20% |
| R2 -> R2 -> DWP | 153 | **R2**=33%, **DWP**=31%, **R1**=26% |
| R2 -> DWP -> DWP | 140 | **R2**=34%, **DWP**=27%, **R1**=24% |
| DWP -> R2 -> DWP | 139 | **DWP**=30%, **R2**=29%, **R1**=28% |
| DWP -> DWP -> R2 | 132 | **R2**=36%, **DWP**=31%, **R1**=21% |
| R2 -> R2 -> R1 | 124 | **R2**=36%, **DWP**=30% |
| R1 -> R2 -> R2 | 123 | **R2**=43%, **R1**=22% |
| R2 -> DWP -> R1 | 118 | **R2**=35%, **DWP**=33% |

## 3. Streak Analysis
Does the probability change after N consecutive days of the same type?

- After 2x **R1** (n=144): **R2 (38.2%)** | Continuation: 18.1%
- After 3x **R1** (n=26): **R2 (38.5%)** | Continuation: 19.2%
- After 2x **R2** (n=361): **R2 (39.1%)** | Continuation: 39.1%
- After 3x **R2** (n=141): **R2 (33.3%)** | Continuation: 33.3%
- After 2x **DWP** (n=281): **R2 (33.1%)** | Continuation: 25.6%
- After 3x **DWP** (n=72): **R2 (36.1%)** | Continuation: 26.4%
- After 2x **DNP** (n=70): **DWP (28.6%)** | Continuation: 17.1%
- After 3x **DNP** (n=12): **DWP (50.0%)** | Continuation: 8.3%
