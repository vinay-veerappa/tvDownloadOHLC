# Actionable Recommendations: V7G Strategy Optimization
## Final Verdict | Run 6 Analysis (Risk Verified)

---

## 🏆 THE REAL WINNER: V2 (Baseline)

Our final verified analysis (Run 6) including Risk Profiling shows V2 outperforms V7G significantly across the board.

| Metric | V2 (Run 6) | V7G (Run 6) | Comparison |
|--------|------------|-------------|------------|
| **Total Net Profit** | **$64,347** | $16,310 | **V2 4x Profit** |
| **Profit Factor** | **1.24** | 1.16 | **V2 Higher Efficiency** |
| **SQN** | **4.84** | 1.70 | **V2 Higher Quality** |
| **Max Drawdown** | **$-7,045** | $-7,575 | **V2 Lower Risk** |
| **Win Rate** | 39.7% | **40.5%** | **V7G slightly higher** |

### Conclusion
V2 captures more runners and generates significantly more alpha.
V7G is a stable strategy (PF 1.16 is profitable), but it leaves too much money on the table compared to V2.

---

## � THE HIDDEN GOLD: Missed MFE Analysis
We analyzed 2,135 trades to see what happens *after* V7G exits. The results are staggering.

- **Total Missed Opportunity**: **$433,694** (If 1 runner was held to session extreme).
- **Average Missed per Trade**: **101 Points** ($203).
- **37%** of all trades missed a runner of more than **100 points**.

### Why?
The "Breakeven + Tight Trailing" logic chokes the trade.
Example: Trade #2060 exited at 9:45 AM (Short), missing **1217 points** ($2,435).
V2 captures this via its Time Exit. V7G gets stopped out early.

## ✅ RECOMMENDATION
**Adopt V3 Adaptive Strategy (`orb_v3_adaptive.pine`)**.

It combines:
1.  **V2's Power** (Time Exit) to capture Trend Days (Afternoon HOD).
2.  **Safety Logic** (Wide Trailing) to prevent Giveback on Reversal Days (Morning HOD).

**Next Step**: Backtest V3 in "Adaptive" mode against V2 logic to verify the uplift.

