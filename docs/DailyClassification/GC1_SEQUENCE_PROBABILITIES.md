# GC1 Sequential Classification Analysis

This document analyzes the probability of today's Daily Classification (R1, R2, DWP, DNP) based on previous day sequences.

## 1. Daily Transition Matrix (P(Today | Yesterday))
If Yesterday was X, what is the probability of Today being Y?

| Yesterday \ Today | R1% | R2% | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DNP** | **22.9%** | **28.3%** | **32.9%** | **16.0%** | 764 |
| **DWP** | **22.2%** | **30.1%** | **30.9%** | **16.7%** | 1443 |
| **R1** | **23.7%** | **28.4%** | **30.9%** | **17.0%** | 1050 |
| **R2** | **23.5%** | **27.0%** | **32.4%** | **17.1%** | 1298 |

## 2. Common 3-Day Patterns
Most frequent sequences of 3 days and what usually follows on Day 4.

| 3-Day Sequence | n | Next Day (Day 4) Probabilities |
| :--- | :--- | :--- |
| DWP -> R2 -> DWP | 148 | **DWP**=36%, **R2**=24%, **R1**=24% |
| DWP -> DWP -> DWP | 147 | **DWP**=34%, **R2**=27%, **R1**=26% |
| DWP -> DWP -> R2 | 130 | **DWP**=38%, **R2**=28% |
| R2 -> DWP -> R2 | 129 | **DWP**=33%, **R2**=29%, **R1**=24% |
| DWP -> R2 -> R2 | 122 | **DWP**=31%, **R2**=29%, **R1**=23% |
| R2 -> DWP -> DWP | 117 | **DWP**=32%, **R2**=29%, **R1**=21% |
| R2 -> R2 -> DWP | 106 | **R2**=31%, **DWP**=26%, **R1**=25% |
| R1 -> DWP -> DWP | 104 | **DWP**=38%, **R2**=31% |
| DWP -> R2 -> R1 | 102 | **DWP**=32%, **R2**=26%, **R1**=23% |
| R2 -> DWP -> R1 | 101 | **R2**=29%, **R1**=28%, **DWP**=22%, **DNP**=22% |

## 3. Streak Analysis
Does the probability change after N consecutive days of the same type?

- After 2x **R1** (n=188): **DWP (35.1%)** | Continuation: 23.4%
- After 3x **R1** (n=44): **R1 (31.8%)** | Continuation: 31.8%
- After 2x **R2** (n=258): **DWP (29.8%)** | Continuation: 28.3%
- After 3x **R2** (n=73): **DWP (30.1%)** | Continuation: 19.2%
- After 2x **DWP** (n=299): **DWP (32.4%)** | Continuation: 32.4%
- After 3x **DWP** (n=97): **DWP (37.1%)** | Continuation: 37.1%
- After 2x **DNP** (n=101): **R2 (28.7%)** | Continuation: 19.8%
- After 3x **DNP** (n=20): **DWP (45.0%)** | Continuation: 5.0%
