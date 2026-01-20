# NQ1 Sequential Classification Analysis

This document analyzes the probability of today's Daily Classification (R1, R2, DWP, DNP) based on previous day sequences.

## 1. Daily Transition Matrix (P(Today | Yesterday))
If Yesterday was X, what is the probability of Today being Y?

| Yesterday \ Today | R1% | R2% | DWP% | DNP% | n |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DNP** | **19.0%** | **35.4%** | **29.7%** | **15.9%** | 822 |
| **DWP** | **20.2%** | **33.8%** | **30.3%** | **15.7%** | 1557 |
| **R1** | **18.5%** | **32.5%** | **31.4%** | **17.6%** | 1030 |
| **R2** | **21.5%** | **32.8%** | **30.2%** | **15.5%** | 1717 |

## 2. Common 3-Day Patterns
Most frequent sequences of 3 days and what usually follows on Day 4.

| 3-Day Sequence | n | Next Day (Day 4) Probabilities |
| :--- | :--- | :--- |
| R2 -> R2 -> R2 | 180 | **R2**=32%, **DWP**=28%, **R1**=27% |
| R2 -> DWP -> R2 | 176 | **R2**=36%, **DWP**=28% |
| DWP -> R2 -> R2 | 167 | **R2**=31%, **DWP**=31%, **R1**=22% |
| DWP -> R2 -> DWP | 161 | **R2**=35%, **DWP**=30% |
| R2 -> R2 -> DWP | 160 | **R2**=32%, **DWP**=30%, **R1**=21% |
| R2 -> DWP -> DWP | 160 | **R2**=33%, **DWP**=31% |
| DWP -> DWP -> R2 | 150 | **DWP**=37%, **R2**=27% |
| DWP -> DWP -> DWP | 142 | **DWP**=32%, **R2**=29%, **R1**=26% |
| R2 -> R2 -> R1 | 136 | **DWP**=35%, **R2**=28%, **R1**=21% |
| R2 -> R1 -> R2 | 123 | **R2**=34%, **DWP**=33% |

## 3. Streak Analysis
Does the probability change after N consecutive days of the same type?

- After 2x **R1** (n=152): **DWP (32.9%)** | Continuation: 21.7%
- After 3x **R1** (n=33): **DWP (45.5%)** | Continuation: 12.1%
- After 2x **R2** (n=382): **R2 (32.2%)** | Continuation: 32.2%
- After 3x **R2** (n=123): **R2 (32.5%)** | Continuation: 32.5%
- After 2x **DWP** (n=329): **R2 (33.1%)** | Continuation: 29.5%
- After 3x **DWP** (n=97): **DWP (33.0%)** | Continuation: 33.0%
- After 2x **DNP** (n=113): **R2 (37.2%)** | Continuation: 14.2%
- After 3x **DNP** (n=16): **DWP (37.5%)** | Continuation: 12.5%
