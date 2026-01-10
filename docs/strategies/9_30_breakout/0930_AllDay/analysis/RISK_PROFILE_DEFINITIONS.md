# The Edge System: Risk Profile Master Guide

**Source**: User Provided Text
**Purpose**: The complete blueprint to measure system quality, durability, and survival probability.

---

## 🛑 SECTION 1 — INTRODUCTION
"Today we’re going to break down the real edge of a trading system.
Not the setup. Not the indicators. Not win rate.
But the mathematics that decide whether your system survives or dies.
Most traders obsess over entries.
Professionals obsess over expectancy, risk of ruin, drawdown, MAE/MFE, and position sizing.
This class will give you the complete blueprint to measure system quality, system durability, and system survival probability.
If you master this, you can trade any strategy with confidence."

---

## 🛑 SECTION 2 — DEFINE RISK FIRST
**"No metric matters until you define your risk."**

*   **Definition**: Risk per trade = the maximum dollar amount you will lose on a trade.
*   **Example**: Risk per trade ($R) = $225.
*   **Crucial Rule**: Every other metric — EV, PF, DD, RoR — depends on this number.

---

## 🧬 SECTION 3 — EXPECTED VALUE (EV)

### What it is
The average amount of money your system makes or loses per trade. "Does my system make money over time?"

### Formula
```
EV = (Win% * AvgWin$) - (Loss% * AvgLoss$)
```

### Step-by-step
1.  Measure 50–100 trades.
2.  Count how many wins = Win%.
3.  Take the average win in dollars.
4.  Take the average loss in dollars.
5.  Plug into formula.

### Hidden Assumption Exposed
You assume that your past win/loss profile will remain stable. Markets change, and your EV changes with it.

### Counterpoints
1.  A high win rate can hide a terrible EV (scalper trap).
2.  A low win rate can have huge EV if winners are large (trend systems).

### How to improve a failing EV
*   Increase AvgWin (bigger targets, allow trend holds)
*   Reduce AvgLoss (tighter stops)
*   Improve Win% (better filters)
*   Reduce risk per trade (cuts loss impact)
*   Improve MAE (cleaner entries)

### 🧠 Teaching Prompt
"EV answers: if I take this trade forever, how many dollars does it pay me per trade on average?"

---

## 🧼 SECTION 4 — PROFIT FACTOR (PF)

### What it is
A measure of system cleanliness. "How efficient is your strategy at converting risk into net profit?" / "How smooth is the ride?"

### Formula
```
PF = Total Gross Wins / Total Gross Losses
OR
PF = (Win% * AvgWin) / (Loss% * AvgLoss)
```

### Interpretation
*   **> 2.0**: Very clean system (A-Grade)
*   **1.4 – 2.0**: Solid (B-Grade)
*   **1.1 – 1.4**: Weak (C-Grade)
*   **< 1.0**: Losing system (F-Grade)

### Hidden Assumption Exposed
PF assumes losses remain consistent. If your system occasionally takes giant outlier losses, PF lies.

### Counterpoints
1.  PF can look amazing even with terrible EV (small wins, massive losses).
2.  PF doesn’t tell you about drawdown intensity.

### How to improve PF
*   Decrease AvgLoss
*   Eliminate outlier losses (MAE control)
*   Increase AvgWin
*   Tighten risk per trade

### 🧠 Teaching Prompt
"PF answers: for every dollar I lose, how many dollars do I win back?"

---

## 🔗 SECTION 5 — COMBINED EDGE (EV × PF)

### What it is
This multiplies the average edge (EV) and the quality of the edge (PF) into one power score.

### Formula (Normalized)
1.  **Normalize EV**: `EV_R = EV$ / Risk$`
2.  **Calculate**: `CombinedEdge = EV_R * PF`

### Why it works
*   EV tells you how profitable each trade is on average.
*   PF tells you how "clean" the flow of profits is.
*   CombinedEdge multiplies both into one score.

### Grading
*   **> 100**: Excellent (A)
*   **50 – 100**: Good (B/C)
*   **20 – 50**: Weak (D)
*   **< 20**: Fail (F)

### Hidden Assumption
Assumes EV and PF are independent — they’re not. Your stop width changes both.

### 🧠 Teaching Prompt
"CombinedEdge takes how much you make on average (EV) and how clean your wins/losses are (PF), and turns it into one power score."

---

## ☠️ SECTION 6 — RISK OF RUIN (RoR)

### What it is
The probability your system will hit a catastrophic drawdown (zero or blowout threshold) if you keep trading it.

### Formula
1.  **Bankroll Losses**: `Units = AccountSize / Risk$`
2.  **Calculation**:
    ```
    RoR = ((1 - CombinedEdge) / (1 + CombinedEdge)) ^ Units
    ```

### Interpretation
*   **< 1%**: Professional Grade (Excellent)
*   **1 – 5%**: Acceptable
*   **5 – 20%**: Dangerous
*   **> 20%**: Lethal / Guaranteed Failure

### Hidden Assumption
Assumes trades are independent — real markets cluster losses.

### How to fix high RoR
*   **Reduce risk per trade** (Primary Fix)
*   Increase AvgWin
*   Reduce AvgLoss
*   Improve PF

### 🧠 Teaching Prompt
"RoR answers: what is the chance this system kills my account before my edge pays off?"

---

## 📉 SECTION 7 — CONSECUTIVE LOSS FORMULA

### What it is
Predicts your worst losing streak. "The worst punch your system will throw at your psychology."

### Formula
```
Max Streak ≈ ln(N_Trades) / ln(1 / Loss_Rate)
```

### Example
If N=200 trades, Win%=45% (Loss%=55%):
`ln(200) / ln(1/0.55) ≈ 5.3 / 0.6 ≈ 8.8` (Expect ~9 losses in a row).

### Hidden Assumption
Assumes no regime shifts.

### Fixing huge losing streaks
*   Improve Win rate
*   Reduce Risk per trade
*   Adjust MAE for cleaner entries

---

## 🌊 SECTION 8 — MAX DRAWDOWN (MDD) & DRR

### Max Drawdown
This is your largest decline from peak to trough.

### Drawdown Risk Rating (DRR)
A simple way to relate expected max drawdown to your risk per trade and grade the danger. "How many full-loss trades does it take to hit your likely big drawdown?"

### Formula
```
DRR = Max_Drawdown% / Risk_Per_Trade%
(Approximation: DRR ≈ MaxLosingStreak)
```

### Grading
*   **< 4**: Very Healthy (A)
*   **4 – 7**: Okay but stressful (B/C)
*   **7 – 10**: High Risk (D)
*   **> 10**: Very Dangerous (F)

---

## 🎯 SECTION 9 — MAE & MFE

### MAE (Maximum Adverse Excursion)
*   **What it is**: How far price moves against you (worst unrealized loss).
*   **Use**: Compare MAE to Risk. If MAE is low on winners, you can tighten stops.
*   **Prompt**: "MAE tells you how much heat your trades usually take before they work or fail."

### MFE (Maximum Favorable Excursion)
*   **What it is**: How far price moves in your favor (best unrealized profit).
*   **Use**: Compare MFE to AvgWin. If MFE >> AvgWin, you are leaving money on the table (exiting too early).
*   **Prompt**: "MFE tells you the best the market offered you, so you can see if you kept enough of it."

### Impact
*   **Low MAE** = cleaner entries = smaller stops = better EV + PF.
*   **High MFE** = more potential profit = higher EV.

---

## ⭐ SECTION 10 — SQN (System Quality Number)

### What it is
Van Tharp’s metric for system quality based on trade R-multiples. "How strong and consistent is your R-multiple distribution?"

### Formula
1.  Calculate R for each trade: `R = PnL / Risk$`
2.  Calculate Mean and StdDev of those R's.
3.  `SQN = (Mean / StdDev) * Sqrt(N_Trades)`

### Grading
*   **> 3.0**: Excellent (A)
*   **2.0 – 3.0**: Very Good (B)
*   **1.6 – 2.0**: Good (C)
*   **< 1.6**: Average/Poor (D/F)

---

## 🔧 SECTION 11 — THE FIX TABLE
*"When a metric is failing, you don’t guess. You adjust the lever connected to that metric."*

| Metric Failing | Fix #1 | Fix #2 | Fix #3 |
| :--- | :--- | :--- | :--- |
| **EV** | Increase AvgWin | Reduce AvgLoss | Improve Win Filters |
| **PF** | Remove Large Losses (MAE) | Reduce Stop | Increase MFE Capture |
| **CombinedEdge** | Improve EV or PF | Reduce AvgLoss | Reduce Risk Per Trade |
| **RoR** | **Reduce Risk Per Trade** | Improve PF | Reduce Drawdown |
| **Max Drawdown** | Reduce Risk Per Trade | Increase AvgWin | Improve Win% |
| **MAE** | Cleaner Entries | Stop Refinement | Avoid Chop |
| **MFE** | Improve Partials | Extend Runners | Trade Trends |
| **Losing Streak** | Improve Win% | Reduce Risk | Skip Chop Period |

---

## ⚖️ SECTION 12 — POSITION SIZING GUIDE
*How to choose risk based on System Grade:*

*   **Grade A** (Excellent): Risk **2% – 5%**
*   **Grade B** (Good): Risk **1% – 2%**
*   **Grade C** (Weak): Risk **0.5% – 1%**
*   **Grade D** (Poor): Risk **0.25% – 0.5%**
*   **Grade F** (Fail): **Do Not Trade** (0%)

---

## 📚 SECTION 13 — TEN FULL EXAMPLE SYSTEMS

### NEGATIVE-R SYSTEMS (BAD → OK)
*(Risking $225 to make LESS than $225)*

1.  **Horrible System (N1)**: Win 30%. EV -$127. PF 0.19. **Grade F**.
2.  **Losing Flip (N2)**: Win 40%. EV -$55. PF 0.59. **Grade F**.
3.  **Slight Edge Reward (N3)**: Win 35%. EV -$93. PF 0.36. **Grade F**.
4.  **Almost Breakeven (N4)**: Win 45%. EV -$33. PF 0.73. **Grade D/F**.
5.  **Breakeven System (N5)**: Win 50%. EV -$12. PF 0.89. **Grade D**.

### POSITIVE-R SYSTEMS (GOOD → EXCELLENT)
*(Risking $225 to make $225 or MORE)*

1.  **Small Real Edge (P1)**: Win 55%. EV $36. PF 1.36. **Grade B**.
2.  **Trend Following (P2)**: Win 45%. EV $33. PF 1.27. **Grade B**.
3.  **Big R-Multiple (P3)**: Win 30%. EV $82. PF 1.52. **Grade A-**. (Watch streaks).
4.  **High PF System (P4)**: Win 60%. EV $90. PF 2.0. **Grade A**.
5.  **Excellent Balanced (P5)**: Win 55%. EV $146. PF 2.44. CombinedEdge 357. **Grade A+**.

---

## 🎬 WRAP-UP STATEMENT
"A trading system is not defined by charts or entries.
It is defined by numbers.
Your EV tells you whether you make money.
Your PF tells you how clean your system is.
MAE and MFE tell you how the trade behaves.
SQN tells you the quality of the system.
DRR shows the danger level.
Consecutive losses show the emotional load.
Risk of Ruin shows whether you survive long enough.
CombinedEdge shows overall system strength.
If you understand this, you are already far ahead of most traders."
