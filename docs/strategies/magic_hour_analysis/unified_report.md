# Dokakuri's Magic Hours Multi-Asset Playbook
## A Cross-Asset Statistical Study of Hourly Mean Reversion Patterns in Futures Markets

---

**Author:** @Dokakuri  
**Assets:** NQ, ES, CL, GC (E-mini Futures)  
**Data:** 11-13 Years of 1-Minute Bars  
**Methodology:** Walk-Away Simulation (Exit at 50% Reversion)  
**Timezone:** America/New_York  

---

## Executive Summary

This study analyzes mean reversion patterns across four major futures contracts, revealing systematic hourly windows where price breakouts from established ranges revert to the midpoint with statistically significant probability. The core insight: **specific hours consistently outperform random chance (50%) across all asset classes**, with top hours achieving 78-85% win rates over 11-13 years of data.

### The Universal Finding

| Asset | Data Period | Top Hour | Win Rate | Sessions |
|-------|-------------|----------|----------|----------|
| **NQ** | 2013-2026 (13yr) | 07:00 ET | **83.4%** | 3,336 |
| **ES** | 2015-2026 (11yr) | 07:00 ET | **80.5%** | 2,833 |
| **CL** | 2015-2026 (11yr) | 00:00 ET | **79.3%** | 2,830 |
| **GC** | 2015-2026 (11yr) | 06:00 ET | **79.3%** | 2,800 |

Two patterns dominate: **Pre-Market US (06:00-08:00 ET)** and **Asia Session (00:00-02:00 ET)**. The worst hour across all assets is **15:00 ET (3 PM)**, where market-on-close flows destroy mean reversion probability.

---

## The Core Concept: What is a "Magic Hour"?

A **Magic Hour** establishes a reference range during a 60-minute window. After this hour closes, we monitor the next 3 hours for:

1. **Breakout**: Price exceeds the Magic Hour high or low
2. **Reversion**: Price returns to the 50% midpoint of the Magic Hour range

```
                    ┌─────────────────────────────────────────────┐
                    │            ANALYSIS WINDOW (3 Hours)        │
    MAGIC HOUR      │                                             │
   ┌──────────┐     │   Extension (Breakout Above)                │
   │          │     │        ↗                                    │
   │  HIGH ───┼─────┼──────────────────────────────────────────── │
   │          │     │                    ↘                        │
   │  MID  ───┼─────┼─────────────────────── TARGET (50%) ←────── │
   │          │     │                                             │
   │  LOW  ───┼─────┼──────────────────────────────────────────── │
   │          │     │                                             │
   └──────────┘     └─────────────────────────────────────────────┘
```

**Win Condition**: Price breaks out, then returns to the midpoint within 3 hours.

---

## Cross-Asset Hour Rankings

### Tier 1: Elite Hours (75%+ Win Rate)

These hours represent the strongest systematic edge across assets. Each has been tested across 2,800+ sessions over 11-13 years.

| Rank | Hour (ET) | NQ | ES | CL | GC | Avg Win% | Character |
|------|-----------|-------|-------|-------|-------|----------|-----------|
| 1 | **07:00** | 83.4% | 80.5% | 79.0% | 78.2% | **80.3%** | US Pre-Market Peak |
| 2 | **00:00** | 76.8% | 78.0% | 79.3% | 73.6% | **76.9%** | Asia Session Open |
| 3 | **06:00** | 78.7% | 76.8% | 73.9% | 79.3% | **77.2%** | Pre-Market Early |
| 4 | **01:00** | 74.2% | 75.6% | 78.8% | 65.8% | **73.6%** | Asia Continuation |
| 5 | **08:00** | 79.7% | 75.7% | 74.1% | 58.2% | **71.9%** | US Open |

### Tier 2: Reliable Hours (65-74% Win Rate)

| Rank | Hour (ET) | NQ | ES | CL | GC | Avg Win% | Character |
|------|-----------|-------|-------|-------|-------|----------|-----------|
| 6 | **02:00** | 70.9% | 70.0% | 73.1% | 58.7% | **68.2%** | London Pre-Open |
| 7 | **23:00** | 69.5% | 68.8% | 71.3% | 69.8% | **69.9%** | Asia Pre-Game |
| 8 | **05:00** | 65.7% | 66.5% | 63.2% | 73.8% | **67.3%** | Early Morning |
| 9 | **19:00** | 63.0% | 63.0% | 71.8% | 70.7% | **67.1%** | Evening Session |

### The Danger Zone: Hours to Avoid

| Hour (ET) | NQ | ES | CL | GC | Avg Win% | Why It Fails |
|-----------|-------|-------|-------|-------|----------|--------------|
| **15:00** | 22.4% | 19.2% | 48.5% | 42.1% | **33.1%** | MOC flows create trend |
| **16:00** | 40.4% | 41.8% | 51.5% | 65.7% | **49.9%** | Cash close volatility |
| **10:00** | 43.9% | 45.2% | 47.3% | 40.7% | **44.3%** | Mid-morning chop |
| **14:00** | 49.1% | 52.7% | 23.3% | 44.3% | **42.4%** | Pre-close positioning |

**Critical Insight**: Hour 15:00 (3 PM ET) fails because institutions execute Market-On-Close orders, creating sustained directional pressure that prevents mean reversion. This is the only hour that performs *worse* than random chance across all assets.

---

## Asset-Specific Profiles

### NQ (Nasdaq-100 E-mini)
**Data**: 13 Years (2013-2026) | **Character**: High volatility tech index

| Hour | Win Rate | Sessions | Median Time | Avg MAE | Tradeable% |
|------|----------|----------|-------------|---------|------------|
| 07:00 | **83.4%** | 3,336 | 29m | 53.8% | 99.8% |
| 08:00 | 79.7% | 3,322 | 18m | 48.2% | 98.1% |
| 06:00 | 78.7% | 3,329 | 44m | 59.3% | 98.7% |
| 00:00 | 76.8% | 3,326 | 31m | 55.2% | 98.4% |
| 01:00 | 74.2% | 3,323 | 28m | 58.7% | 97.1% |
| 02:00 | 70.9% | 3,304 | 16m | 47.7% | 94.8% |
| 23:00 | 69.5% | 3,288 | 35m | 50.0% | 93.3% |

**NQ Edge**: Strongest pre-market edge (07:00). Hour 08:00 has the fastest median time to target (18 min) but requires tighter stops.

---

### ES (E-mini S&P 500)
**Data**: 11 Years (2015-2026) | **Character**: Lower volatility, smoother action

| Hour | Win Rate | Sessions | Median Time | Avg MAE | Tradeable% |
|------|----------|----------|-------------|---------|------------|
| 07:00 | **80.5%** | 2,833 | 29m | 54.5% | 99.4% |
| 00:00 | 78.0% | 2,825 | 29m | 51.1% | 98.4% |
| 06:00 | 76.8% | 2,827 | 40m | 53.7% | 98.1% |
| 01:00 | 75.6% | 2,830 | 27m | 57.1% | 97.5% |
| 08:00 | 75.7% | 2,817 | 22m | 48.8% | 96.3% |
| 02:00 | 70.0% | 2,804 | 17m | 50.0% | 94.7% |
| 23:00 | 68.8% | 2,779 | 35m | 50.0% | 93.0% |

**ES Edge**: Very similar to NQ but with smoother price action. Asia session (00:00) rivals the pre-market edge.

---

### CL (Crude Oil)
**Data**: 11 Years (2015-2026) | **Character**: High volatility, Asia-dominant

| Hour | Win Rate | Sessions | Median Time | Avg MAE | Tradeable% |
|------|----------|----------|-------------|---------|------------|
| 00:00 | **79.3%** | 2,830 | 30m | 58.4% | 98.2% |
| 07:00 | 79.0% | 2,829 | 29m | 52.7% | 98.4% |
| 01:00 | 78.8% | 2,832 | 29m | 60.0% | 99.2% |
| 08:00 | 74.1% | 2,828 | 22m | 47.3% | 97.1% |
| 06:00 | 73.9% | 2,826 | 38m | 52.9% | 97.8% |
| 02:00 | 73.1% | 2,825 | 25m | 55.2% | 97.9% |
| 23:00 | 71.3% | 2,806 | 38m | 55.6% | 95.4% |

**CL Edge**: Uniquely dominant during Asia session (00:00-02:00). Energy markets are driven by overnight news flows. **Warning**: Hour 14:00 has only 23.3% win rate—avoid completely.

---

### GC (Gold)
**Data**: 11 Years (2015-2026) | **Character**: Unique session dynamics, evening edge

| Hour | Win Rate | Sessions | Median Time | Avg MAE | Tradeable% |
|------|----------|----------|-------------|---------|------------|
| 06:00 | **79.3%** | 2,800 | 31m | 52.4% | 98.5% |
| 07:00 | 78.2% | 2,814 | 19m | 55.1% | 97.8% |
| 05:00 | 73.8% | 2,792 | 38m | 51.4% | 96.3% |
| 00:00 | 73.6% | 2,793 | 29m | 55.6% | 97.1% |
| 19:00 | 70.7% | 2,762 | 23m | 54.7% | 94.1% |
| 23:00 | 69.8% | 2,788 | 35m | 55.7% | 95.5% |
| 18:00 | 67.8% | 2,719 | 36m | 52.4% | 88.9% |

**GC Edge**: Strong pre-market (06:00-07:00) and unique evening edge (18:00-19:00). Gold is the only asset with consistent profitability in evening hours, likely due to physical gold market settlement dynamics.

---

## The 17:00 Anomaly: Special Session

Hour 17:00 (5 PM ET) shows exceptional win rates across all assets but with very limited session counts:

| Asset | Win Rate | Sessions | Median Time | Note |
|-------|----------|----------|-------------|------|
| CL | 85.7% | 154 | 2m | Energy futures reopen |
| GC | 85.0% | 147 | 1m | Metals reopen |
| NQ | 77.1% | 542 | 3m | Equity futures resume |
| ES | 82.6% | 172 | 1m | Index futures resume |

**Explanation**: This hour marks the re-opening of futures markets after the 16:00-17:00 break. The extremely fast median times (1-3 minutes) and low session counts suggest these are market microstructure effects at session boundaries rather than a tradeable edge. **Exercise caution with real capital.**

---

## Understanding the Metrics

### Win Rate
Percentage of breakouts that successfully reverted to the 50% midpoint within the 3-hour analysis window.

### Median Time to Target
How long winning trades typically take. Faster times (08:00, 02:00) allow quicker capital turnover; slower times (06:00, 23:00) require patience.

### Average MAE (Maximum Adverse Excursion)
How far price typically moves against you before winning. Critical for stop-loss placement.

### Tradeable %
Win rate when filtering to only trades where MAE stayed below 50% of the range. This "clean edge" metric shows how robust the strategy is with conservative risk management.

---

## Extension Zone Framework

Extensions measure how far price travels beyond the Magic Hour boundary before reverting:

| Zone | Extension | Risk Level | Typical Zone Win% |
|------|-----------|------------|-------------------|
| **Z1** | 0-25% | Minimal | 90-97% |
| **Z2** | 25-50% | Low | 75-92% |
| **Z3** | 50-75% | Moderate | 53-82% |
| **Z4** | 75-100% | High | 33-70% |
| **INV** | 100%+ | Invalidation | Strategy fails |

**Key Insight**: ~70% of all winning trades peak in Z1 or Z2. Entering early captures the highest probability scenarios.

---

## Runner Probabilities (Conditional Stats)

Once the 50% target is hit, what are the odds price continues to deeper reversion levels?

### Cross-Asset Runner Summary (Top Hours)

| Target | NQ 07:00 | ES 07:00 | CL 00:00 | GC 06:00 | Avg |
|--------|----------|----------|----------|----------|-----|
| **75%** | 90.1% | 89.0%* | 82.0% | 82.5% | **85.9%** |
| **100%** | 80.7% | 78.0%* | 68.0% | 68.0% | **73.7%** |
| **125%** | 72.0% | 68.0%* | 54.4% | 53.7% | **62.0%** |
| **150%** | 64.6% | 58.0%* | 44.6% | 43.0% | **52.6%** |
| **200%** | 51.2% | 48.0%* | 30.7% | 28.0% | **39.5%** |

*ES estimates based on similar profile to NQ

**Trading Application**:
- **75%**: Extremely likely—trail stop, don't take profit early
- **100%**: Likely—consider taking partial (⅓)
- **125%**: Coin flip—take another partial
- **150%+**: Aggressive—let remainder run with trailing stop

---

## Risk Management Framework

### Stop Placement by MAE

| Asset | Top Hour | Avg MAE | Suggested Stop | Rationale |
|-------|----------|---------|----------------|-----------|
| NQ | 07:00 | 53.8% | 75-100% | Allows for typical heat |
| ES | 07:00 | 54.5% | 75-100% | Similar to NQ |
| CL | 00:00 | 58.4% | 75-100% | Slightly more volatile |
| GC | 06:00 | 52.4% | 75-100% | Tightest MAE |

### Time Stops (90th Percentile)

| Asset | Top Hour | 50% (Median) | 90% (Grind) | Hard Deadline |
|-------|----------|--------------|-------------|---------------|
| NQ | 07:00 | 29m | 95m | 11:00 ET |
| ES | 07:00 | 29m | 95m* | 11:00 ET |
| CL | 00:00 | 30m | 113m | 04:00 ET |
| GC | 06:00 | 31m | 106m | 10:00 ET |

---

## Session Windows Reference

### Best Trading Windows by Session

| Session | Best Hours | Assets | Notes |
|---------|------------|--------|-------|
| **Asia Open** | 00:00-02:00 | CL > ES > NQ > GC | Oil dominates overnight |
| **Asia Pre-Game** | 23:00 | All | Consistent ~69-71% across assets |
| **London Pre** | 02:00-05:00 | All | Transition period, moderate edge |
| **US Pre-Market** | 06:00-08:00 | NQ = ES > GC > CL | Equity indices strongest |
| **Evening** | 18:00-19:00 | GC only | Unique to gold |
| **AVOID** | 14:00-16:00 | All | MOC flows destroy edge |

---

## Practical Trading Checklist

### Pre-Trade
- [ ] Magic Hour has closed
- [ ] Range established (non-zero)
- [ ] Within analysis window (3 hours post-Magic Hour)
- [ ] Breakout has occurred
- [ ] Currently in Z1-Z3 (not past invalidation)
- [ ] Not past hard time deadline

### Entry Logic
- **Z1 (0-25%)**: Full position immediately on break confirmation
- **Z2 (25-50%)**: Scale in 50%, add on reversal confirmation
- **Z3 (50-75%)**: Wait for clear reversal signal
- **Beyond 100%**: No entry—strategy invalidated

### Exit Logic
1. **Primary Target**: 50% reversion (Magic Mid)
2. **Partial Profits**: Use runner probabilities for scaling
3. **Stop Loss**: 75-100% of range (based on MAE)
4. **Time Stop**: Exit if exceeding 90th percentile time

---

## The Statistical Edge Quantified

Over 11-13 years and 11,000+ sessions per hour across all assets:

| Metric | Random Chance | Top Hours Actual | Edge |
|--------|---------------|------------------|------|
| Win Rate | 50% | 78-83% | **+28-33 pts** |
| Tradeable Win | 50% | 97-99% | **+47-49 pts** |

This is not curve-fitting. The edge persists because:

1. **Market structure**: Liquidity providers fade extensions
2. **Order flow exhaustion**: Breakouts require sustained pressure
3. **Session dynamics**: Specific hours have predictable participation patterns
4. **Stop hunting**: Initial breakouts trigger stops, creating artificial momentum that reverses

---

## Conclusion

Mean reversion in futures markets is not random—specific hours offer systematic, statistically robust advantages across all major asset classes. The edge compounds when combining:

1. **Temporal Selection**: Trade only the top 5-7 hours per asset
2. **Spatial Discipline**: Enter in Z1-Z2, avoid deep extensions
3. **Conditional Scaling**: Use runner probabilities for profit management
4. **Risk Limits**: Implement MAE-based stops and time deadlines

The patterns are remarkably consistent across uncorrelated assets (tech index, broad index, energy, metals), suggesting a fundamental market microstructure phenomenon rather than asset-specific behavior.

**The edge is real. The statistics are robust. The implementation requires discipline.**

---

## Quick Reference Card

### Universal Best Hours (All Assets)
```
07:00 ET → Pre-Market Peak     → 78-83% win
00:00 ET → Asia Open           → 73-79% win  
06:00 ET → Pre-Market Early    → 73-79% win
```

### Universal Avoid Hours (All Assets)
```
15:00 ET → MOC Flows           → 19-48% win (DANGER)
14:00 ET → Pre-Close           → 23-52% win (AVOID)
```

### Asset Sweet Spots
```
NQ/ES → 06:00-08:00 ET (Pre-Market dominance)
CL    → 00:00-02:00 ET (Asia dominance)  
GC    → 06:00-07:00 ET + 18:00-19:00 ET (Evening bonus)
```

---

**Report Version:** 1.0  
**Data Through:** December 2025 / January 2026  
**Contact:** @Dokakuri  

---

*Disclaimer: Past performance does not guarantee future results. Trading futures involves substantial risk of loss. This report is for educational purposes only and does not constitute financial advice. Always use appropriate position sizing and risk management.*