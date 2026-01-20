# CL1 Sequential Classification Analysis

This document analyzes the probability of today's Daily Classification (R1, R2, DWP, DNP) based on previous day sequences.

## 1. Daily Transition Matrix (P(Today | Yesterday))
If Yesterday was X, what is the probability of Today being Y?

| Yesterday \ Today | R1% | R2% | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DNP** | **19.3%** | **32.0%** | **32.2%** | **16.6%** | 706 |
| **DWP** | **22.3%** | **28.1%** | **34.5%** | **15.2%** | 1492 |
| **R1** | **21.6%** | **28.1%** | **32.4%** | **17.9%** | 967 |
| **R2** | **22.1%** | **30.2%** | **33.4%** | **14.4%** | 1313 |

## 2. Common 3-Day Patterns
Most frequent sequences of 3 days and what usually follows on Day 4.

| 3-Day Sequence | n | Next Day (Day 4) Probabilities |
| :--- | :--- | :--- |
| DWP -> DWP -> DWP | 166 | **DWP**=35%, **R2**=33% |
| R2 -> DWP -> DWP | 153 | **DWP**=30%, **R2**=29%, **R1**=23% |
| DWP -> DWP -> R2 | 149 | **DWP**=34%, **R2**=26%, **R1**=25% |
| R2 -> R2 -> DWP | 133 | **R2**=36%, **DWP**=32%, **R1**=21% |
| DWP -> R2 -> R2 | 132 | **R2**=36%, **DWP**=33%, **R1**=23% |
| DWP -> R2 -> DWP | 130 | **DWP**=34%, **R1**=27%, **R2**=23% |
| R2 -> R2 -> R2 | 125 | **DWP**=35%, **R2**=25%, **R1**=22% |
| R1 -> DWP -> DWP | 121 | **R2**=31%, **DWP**=28%, **R1**=22% |
| R2 -> DWP -> R2 | 116 | **DWP**=29%, **R2**=28%, **R1**=27% |
| DWP -> DWP -> R1 | 116 | **DWP**=34%, **R2**=27%, **R1**=23% |

## 3. Streak Analysis
Does the probability change after N consecutive days of the same type?

- After 2x **R1** (n=162): **DWP (32.1%)** | Continuation: 22.2%
- After 3x **R1** (n=36): **DWP (44.4%)** | Continuation: 22.2%
- After 2x **R2** (n=271): **R2 (34.7%)** | Continuation: 34.7%
- After 3x **R2** (n=94): **DWP (35.1%)** | Continuation: 25.5%
- After 2x **DWP** (n=348): **DWP (31.0%)** | Continuation: 31.0%
- After 3x **DWP** (n=108): **DWP (36.1%)** | Continuation: 36.1%
- After 2x **DNP** (n=96): **R2 (34.4%)** | Continuation: 20.8%
- After 3x **DNP** (n=20): **R1 (40.0%)** | Continuation: 5.0%
