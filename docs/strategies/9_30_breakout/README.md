# 9:30 Opening Range Breakout Strategy

## Overview
This strategy captures the US Equities Open volatility impulse (9:30 AM EST) in NQ futures. Based on **10 years of backtesting (2016-2025)**, the strategy proves to be a high-alpha trend-following model when given sufficient time to run.

---

## 🚀 Long-Term Performance (10-Year Alpha)
Extensive backtesting over **980+ trades** reveals significant profitability, specifically when traditional time constraints are relaxed.

| Metric | V1 (9:44 AM Hard Exit) | V2 (No Time Exit / 4 PM) |
|:---|:---|:---|
| **Total Net PnL** | **+4,418 pts** | **+9,478 pts** |
| **Win Rate** | ~37% | ~23% |
| **Avg Trade** | +4.48 pts | **+9.54 pts** |
| **Profit Factor** | 1.59 | 1.42 |
| **Max Drawdown** | (See Research) | (Higher - Volatile) |

> [!IMPORTANT]
> **The alpha is in the "Runners"**: Removing the 9:44 AM exit constraint **more than doubles** total profitability. While the win rate drops (due to fewer "saved" small losses), the winners capture the full daily extension.

---

## Strategy Comparison

| Aspect | V1 (Baseline) | V2 (Optimized/Aggressive) |
|:---|:---|:---|
| **Entry Window** | 09:31 - 09:44 | 09:31 - 09:35 (Tight) |
| **Hard Exit** | 09:44 AM (14 min) | 4:00 PM (EOD) OR 10:30 AM |
| **Stop Loss** | Opposite side of range | Tighter of: 0.20% OR structural |
| **Take Profit** | 2R fixed | 0.80x of 9:30 range (dynamic) |
| **Key Filter** | None | Tuesday Avoidance, Extreme Range Filter |

---

## 🔬 Research & Optimization Insights
We have conducted extensive multi-year research (2016-2025) on the 9:30 breakout strategy. All detailed reports are available in the [**research/**](research/) folder:

- **[Win Rate Optimization](research/winrate_optimization.md)**: Analyzes trade frequency vs. quality. 1R target with a 0.25% range filter is the "Best Balance" config, yielding **+1,254 pts** over 500 trades with a **47% win rate**.
- **[Time Exit Analysis](research/time_exit_analysis.md)**: Proves that removing the 9:44 AM exit constraint **more than doubles** total profitability (+9,478 pts vs +4,418 pts).
- **[MFE Profit Targets](research/mfe_profit_targets.md)**: Statistics on Maximum Favorable Excursion. Median follow-through expansion is ~83% of the 9:30 candle range.
- **[Risk of Ruin](research/risk_of_ruin.md)**: Position sizing and drawdown analysis for various contract sizes.
- **[Session Context](research/session_context.md)**: impact of overnight (GLOBEX) gaps and volume regimes on 9:30 breakout success.
- **[Timing Analysis](research/timing_analysis.md)**: Optimization of the entry window. Best results found by entering only between 09:31 and 09:35 EST.
- **[Loss Analysis & Mitigation](research/LOSS_ANALYSIS.md)**: Categorizes reasons for the ~38% win rate and identifies the Bear Regime as the primary avoidance zone.
- **[Position Sizing Calculator](research/position_sizing_calculator.md)**: Practical guide for risk-adjusted contract sizing.
- **[Detailed Analysis Report](research/analysis_report.md)**: A comprehensive summary of all strategy research findings.

### Key Performance Rules
> [!CAUTION]
> **The Bear Trap**: Win rate drops from **45% in Bull regimes** to just **18% in Bear regimes**. Mitigation research suggests skipping initial breakouts in Bear markets.
> [!TIP]
> **Best Exit Time**: Data suggests **10:00 AM EST** is the optimal balance between capturing the impulse and avoiding the mid-morning reversal, though EOD (4:00 PM) maximizes total PnL.
> **Target Logic**: Setting TP at **80% of the opening candle range** (Dynamic TP) scales with volatility and yields the highest expectancy.
> **Day Filter**: Tuesdays show consistently lower follow-through; **V2** recommends skipping these days entirely.

---

## Performance Summary (Recent Verification)
*Dec 2025 Verification (Last 30 Days)*
- **Trades**: 19
- **Win Rate**: 36.8% (Captured via V1 rules)
- **Net PnL**: -38.50 pts (Short-term noise vs 10-year trend)

---

## Implementation & Tools
- **Strategy Logic (TS)**: [nq-1min-strategy.ts](../../../web/lib/backtest/strategies/nq-1min-strategy.ts)
- **Full Scale Runner (TS)**: [full-scale-backtest.ts](../../../scripts/backtest/full-scale-backtest.ts)
- **TV Scripts**: Located in [pinescript/](pinescript/)
- **Derived Data**: Precomputed ranges for ES/NQ in [data/](../../../data/) (`{ticker}_opening_range.json`)

---

## Next Steps / TODO
- [ ] Implement the **0.25% Range Filter** in the TypeScript runner.
- [ ] Backtest the **V2 Tuesday Filter** over the full 10-year dataset.
- [ ] Standardize the **80% Range Dynamic TP** across all futures tickers.
