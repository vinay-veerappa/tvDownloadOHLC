# Risk Profile Definitions & Formulas
**Source**: User Provided Text (The "Edge System")
**Purpose**: The standard mathematical framework for evaluating all strategies in this project.

## 1. Core Definitions

### Risk ($R)
*   **Definition**: The fixed dollar risk per trade (or the average loss if fixed risk isn't strictly enforced).
*   **Script Implementation**: Use `Abs(AvgLoss)` from the backtest as the proxy for `$R`.

### Expected Value (EV)
*   **Definition**: Average dollar amount the system makes/loses per trade.
*   **Formula**:
    ```
    EV = (Win% * AvgWin$) - (Loss% * AvgLoss$)
    ```
*   **Normalized EV (EV_R)**:
    ```
    EV_R = EV$ / Risk$
    ```

### Profit Factor (PF)
*   **Definition**: Efficiency of converting risk to profit.
*   **Formula**:
    ```
    PF = (Win% * AvgWin$) / (Loss% * AvgLoss$)
    (Equivalent to TotalGrossWin / TotalGrossLoss)
    ```

### Combined Edge
*   **Definition**: A single quality score combining Edge strength and cleanliness.
*   **Formula**:
    ```
    CombinedEdge = EV_R * PF
    ```
    *(Note: This differs from (Win%*Payoff)-Loss%)*

## 2. Advanced Metrics

### System Quality Number (SQN)
*   **Definition**: Quality of the system adjusted for consistency and sample size.
*   **Steps**:
    1.  Calculate R-multiple for every trade: `R_i = Trade_PnL / Risk$`
    2.  Calculate Mean (`Mean_R`) and Standard Deviation (`Std_R`) of these R-multiples.
    3.  **Formula**:
        ```
        SQN = (Mean_R / Std_R) * Sqrt(Number_of_Trades)
        ```

### Max Losing Streak (Theoretical)
*   **Definition**: The worst expected losing streak over N trades.
*   **Formula**:
    ```
    Streak_Max = ln(N_Trades) / ln(1 / Loss_Rate)
    ```
    *Where `Loss_Rate` is a decimal (e.g., 0.60).*

### Risk of Ruin (RoR)
*   **Definition**: Probability of blowing the account.
*   **Inputs**:
    *   `Bankroll_Units` = Total Account / Risk$ (User example: 20 units).
*   **Formula**:
    ```
    RoR = ((1 - CombinedEdge) / (1 + CombinedEdge)) ^ Bankroll_Units
    ```

### Drawdown Risk Rating (DRR)
*   **Definition**: Risk rating based on expected drawdown.
*   **Formula**:
    ```
    DRR = Streak_Max
    ```
    *(Based on: Expected_DD% = Streak_Max * Risk%; DRR = DD% / Risk% = Streak_Max)*

## 3. Metrics Intepretation Table

| Metric | Bad/Fail | Good | Excellent |
| :--- | :--- | :--- | :--- |
| **Combined Edge** | < 20 | 50 - 100 | > 100 |
| **SQN** | < 1.5 | 2.0 - 3.0 | > 3.0 |
| **Profit Factor** | < 1.0 | 1.4 - 1.8 | > 2.0 |
| **RoR** | > 10% | < 5% | < 1% |

## 4. Reference Examples

### NEGATIVE-R SYSTEMS (BAD → OK)
*Risking $225 to make LESS than $225*

#### Example N1 — Horrible System (Negative R)
*   **Win%**: 30%
*   **AvgWin**: $100
*   **AvgLoss**: $225
*   **EV**: -$127.5
*   **PF**: 0.19
*   **CombinedEdge**: -24.3
*   **Grade**: F (Position size: $0)

#### Example N2 — Losing Flip (Negative R)
*   **Win%**: 40%
*   **AvgWin**: $200
*   **AvgLoss**: $225
*   **EV**: -$55
*   **PF**: 0.59
*   **CombinedEdge**: -32.45
*   **Grade**: F

#### Example N3 — Slight Edge on Reward but Still Negative R
*   **Win%**: 35%
*   **AvgWin**: $150
*   **AvgLoss**: $225
*   **EV**: -$93.75
*   **PF**: 0.36
*   **CombinedEdge**: -33.75
*   **Grade**: F

#### Example N4 — Almost Break-Even but Negative R
*   **Win%**: 45%
*   **AvgWin**: $200
*   **AvgLoss**: $225
*   **EV**: -$33.75
*   **PF**: 0.73
*   **CombinedEdge**: -24.6
*   **Grade**: D/F

#### Example N5 — Breakeven System (Negative R shape)
*   **Win%**: 50%
*   **AvgWin**: $200
*   **AvgLoss**: $225
*   **EV**: -$12.5
*   **PF**: 0.89
*   **CombinedEdge**: -11.1
*   **Grade**: D

### POSITIVE-R SYSTEMS (GOOD → EXCELLENT)
*Risking $225 to make $225 or MORE*

#### Example P1 — Small Real Edge (Positive R)
*   **Win%**: 55%
*   **AvgWin**: $250
*   **AvgLoss**: $225
*   **EV**: $36.25
*   **PF**: 1.36
*   **CombinedEdge**: 49.3
*   **Grade**: B (Risk 1-2%)

#### Example P2 — Trend Following Edge (Positive R)
*   **Win%**: 45%
*   **AvgWin**: $350
*   **AvgLoss**: $225
*   **EV**: $33.75
*   **PF**: 1.27
*   **CombinedEdge**: 42.8
*   **Grade**: B (Risk 1%)

#### Example P3 — Big R-Multiple System
*   **Win%**: 30%
*   **AvgWin**: $800
*   **AvgLoss**: $225
*   **EV**: $82.5
*   **PF**: 1.52
*   **CombinedEdge**: 125.4
*   **Grade**: A- (Stay small due to streak risk)

#### Example P4 — High PF System (Positive R)
*   **Win%**: 60%
*   **AvgWin**: $300
*   **AvgLoss**: $225
*   **EV**: $90
*   **PF**: 2.0
*   **CombinedEdge**: 180
*   **Grade**: A (Risk 2-3%)

#### Example P5 — Excellent Balanced System (Positive R)
*   **Win%**: 55%
*   **AvgWin**: $450
*   **AvgLoss**: $225
*   **EV**: $146.25
*   **PF**: 2.44
*   **CombinedEdge**: 357.8
*   **Grade**: A+ (Risk 2-3%)
