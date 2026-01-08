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
