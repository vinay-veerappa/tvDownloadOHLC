# Institutional Reporting Metrics Guide

## Overview
Institutional strategy assessment moves beyond absolute P&L to measure **risk efficiency** and **statistical expectancy**. This guide defines the core metrics used by the Unified Research Suite for A-F grading.

---

## 1. Expected Value (EV)
The total probabilistic payout of the strategy.
- **Formula**: `(WinRate * AvgWin) - (LossRate * AvgLoss)`
- **Institutional Context**: Measures if the strategy has a positive edge after accounting for trade friction.
- **Grading**:
  - `A`: > $100 per Entry
  - `B`: > $50 per Entry
  - `C`: > $10 per Entry
  - `F`: < $0 (Negative Expectancy)

## 2. System Quality Number (SQN)
A metric developed by Van Tharp to measure the "tradeability" of a strategy.
- **Formula**: `(Avg R-Multiple * sqrt(Total Trades)) / StdDev(R-Multiples)`
- **Institutional Context**: Normalizes performance across different trade counts and volatility. High SQN indicates high stability and reliability.
- **Grading**:
  - `A`: > 3.0 (Holy Grail)
  - `B`: > 2.5 (Excellent)
  - `C`: > 2.0 (Good)
  - `D`: > 1.5 (Fair)
  - `F`: < 1.5 (Poor/Unreliable)

## 3. Drawdown Risk Rating (DRR)
Normalizes the maximum drawdown against the unit risk (R).
- **Formula**: `Abs(MaxDD%) / (UnitRisk / AccountSize * 100)`
- **Institutional Context**: Measures how many "R-multiple" units of account heat the strategy takes. Low DRR indicates high capital efficiency.
- **Grading**:
  - `A`: < 4.0 Units
  - `B`: < 6.0 Units
  - `C`: < 8.0 Units
  - `F`: > 10.0 Units (Dangerous Over-Risk)

## 4. Combined Edge (CE)
The primary sorting metric for the Research Leaderboard.
- **Formula**: `Expectancy(R) * ProfitFactor`
- **Institutional Context**: Balances high-win-rate systems with high-reward-ratio systems.
- **Grading**:
  - `A`: > 150
  - `B`: > 100
  - `C`: > 50
  - `D`: > 20

## 5. Risk of Ruin (RoR)
The mathematical probability of losing a defined percentage of the account (typically 100%).
- **Formula**: `((1 - Edge) / (1 + Edge)) ^ Bankroll_Units`
- **Institutional Context**: A hard "Pass/Fail" gate. Institutional funds typically require `RoR < 1%`.
- **Thresholds**:
  - `< 0.01%`: Excellent
  - `> 10.0%`: High Risk of Liquidation
