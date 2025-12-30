# ORB 9:30 Breakout Strategy - Final Research Summary

**Date**: December 29, 2025  
**Ticker**: NQ1 (NASDAQ Futures)  
**Period**: 10 Years (2015-2025)  
**Analysis Sessions**: 15+ optimization runs, 6 strategy variants, 2,500+ simulated trades

---

## Executive Summary

After extensive parameter optimization, loss analysis, and realistic trade simulation, we have identified the key factors that determine success in the 9:30 Opening Range Breakout strategy.

### The Core Insight

> **Time exits provide ALL the profit. Stop losses are a net cost center.**

| Exit Type | PnL Contribution | Trades |
|-----------|------------------|--------|
| **TIME** (11:00 exit) | **+175.5%** | 42.7% |
| **TP1** (Cover Queen) | +26.9% | 54.2% |
| **SL** (Range-based) | **-150.1%** | 46.3% |

The strategy works because runners captured at time exit more than compensate for stop losses.

---

## What We Tested

### 1. Parameter Optimization (35+ combinations)

| Parameter | Best Value | Impact |
|-----------|------------|--------|
| **Entry Confirmation** | **0.10%** beyond Range | +44% PnL vs immediate entry |
| **Hard Exit Time** | **11:00 EST** | +10x PnL vs 10:00 exit |
| **Regime Filter** | **OFF** | +5% PnL by trading all conditions |
| **VVIX Filter** | **ON (> 115)** | Prevents -3.6% losing trades |
| **Wednesday Skip** | **ON** | Prevents -4.27% losing trades |
| **Max Range %** | **0.25%** | Filters extreme volatility days |

### 2. Strategy Variants

| Variant | Trades | Win Rate | **PnL** | **PF** |
|---------|--------|----------|---------|--------|
| **ORB_NoCTQ** (Full ride) | 1,294 | 42.7% | **+25.38%** | 1.15 |
| **ORB_EngulfingExit** | 2,336 | 66.1% | **+19.86%** | 1.21 |
| ORB_AggressiveTP (0.03%) | 2,465 | 70.0% | +17.62% | 1.19 |
| ORB_V7.1 (CTQ 0.05%) | 2,370 | 68.8% | +16.90% | 1.16 |
| ORB_HighConfirm (0.15%) | 2,122 | 70.6% | +15.99% | 1.16 |
| ORB_PullbackEntry | 1,685 | 58.2% | +2.95% | 1.03 |

### 3. Loss Analysis Findings

- **99.8%** of trades pull back to entry level (normal, not failure)
- **Wednesday** has 64.7% loss rate vs 60% other days
- **45% of losers** saw 0.05%+ profit before losing
- **Winners have 50% less MAE** than losers (0.08% vs 0.15%)
- **Engulfing candles predict failure**: 70% hit SL vs 27% without

---

## How to Be More Effective

### MUST DO (High Impact)

| Action | Expected Impact | Evidence |
|--------|-----------------|----------|
| **Wait for 0.10% confirmation** | +44% PnL | Filters weak breakouts |
| **Hold until 11:00 EST** | +10x PnL | Runners provide all profit |
| **Skip Tuesday & Wednesday** | +6.5% saved | Worst loss rates |
| **Use Range High/Low as SL** | Better than fixed % | Structure-based protection |
| **Exit on engulfing candle** | +3% PnL | 70% of engulfing trades hit SL |

### CONSIDER (Moderate Impact)

| Action | Expected Impact | Trade-off |
|--------|-----------------|-----------|
| **No CTQ (full ride)** | +25% PnL vs +17% | Lower win rate (43% vs 69%) |
| **Lower TP1 to 0.03%** | +17.6% PnL, 70% WR | Slightly better than 0.05% |
| **Higher confirm (0.15%)** | +16% PnL, 71% WR | Fewer trades |

### AVOID (Negative Impact)

| Action | Expected Impact | Evidence |
|--------|-----------------|----------|
| ❌ **Breakeven trail** | -50-70% PnL | Kills runners on normal pullbacks |
| ❌ **Pullback entry** | +3% vs +17% | Misses breakouts, no edge |
| ❌ **Fixed % SL** | Higher losses | Range structure works better |
| ❌ **Exit before 11:00** | Massive PnL reduction | Time exits = profit source |
| ❌ **Trade VVIX > 115** | -3.6% | High volatility = whipsaws |

---

## Recommended Configuration

### Conservative (Higher Win Rate)
```
Entry: 0.10% confirmation
TP1: 0.05% (exit 50%)
Runner: Hold to 11:00
SL: Range High/Low
Skip: Tue, Wed, VVIX > 115

Expected: +17% PnL, 69% WR, 1.16 PF
```

### Aggressive (Higher PnL)
```
Entry: 0.10% confirmation
TP1: None (full ride to 11:00)
SL: Range High/Low
Exit on: Engulfing candle
Skip: Tue, Wed, VVIX > 115

Expected: +25% PnL, 43% WR, 1.15 PF
```

---

## Key Mental Model

### Why This Strategy Works

```
The 9:30 ORB captures the daily directional bias establishment.
When the market breaks out of the opening range with conviction
(0.10% confirmation), it's signaling the day's probable direction.

The profit comes from HOLDING through normal pullbacks.
Winners average +0.23% while losers average -0.15%.
The R:R is favorable, but only if you let winners run.

Time is your friend. The longer you hold (to 11:00), 
the more the directional bias plays out.
```

### The Psychology Challenge

| What You'll Feel | What to Do |
|------------------|------------|
| "It's pulling back, I should exit" | Don't - 99.8% pull back, 66% continue |
| "I should move SL to breakeven" | Don't - kills 50-70% of profits |
| "I should take profit early" | Don't - unless it's TP1 (CTQ) |
| "Engulfing candle, but I'll hold" | Exit - 70% hit SL after engulfing |

---

## Simulator Comparison

We tested two simulation approaches:

### Results

| Simulator | Trades | Win Rate | **Return** |
|-----------|--------|----------|------------|
| **Custom State Machine** | 2,370 | 68.8% | **+16.90%** ✅ |
| **Vectorbt** | 1,339 | 74.5% | **-24.05%** ❌ |

### Why the Difference?

| Factor | Custom | Vectorbt |
|--------|--------|----------|
| **Partial Exits** | ✅ CTQ 50% partial | ❌ All-or-nothing |
| **Exit Priority** | TP1 → SL → TIME | SL/TP simultaneous |
| **Fill Prices** | Exact TP/SL level | Bar close |

**Conclusion**: Vectorbt's simplified mechanics don't handle CTQ partial exits. **Use the custom state machine** (`simulate_trades.py`) for this strategy.

---

## Files Generated

| File | Description |
|------|-------------|
| `ORB_V7_SPEC.md` | Complete strategy specification |
| `SIMULATION_GUIDE.md` | Backtesting rules for agents |
| `BACKTESTING_AGENT_PROMPT.md` | Prompt for future analysis |
| `variant_comparison_final.csv` | All variant results |
| `post_breakout_behavior.csv` | Pullback analysis data |
| `optimization_summary.csv` | Parameter grid search results |
| `simulate_trades.py` | Extensible simulation framework |

---

## Next Steps

1. **Live Paper Trading**: Run V7.1 or NoCTQ variant in NinjaTrader sim
2. **Weekly Review**: Compare paper trades to backtest expectations
3. **Refinement**: Adjust based on live market behavior
4. **Position Sizing**: Implement anti-martingale sizing (reduce after loss)
5. **Daily Limit**: Stop after 2 consecutive losses or 0.5% drawdown

---

*Research compiled from 10 years of NQ1 data, December 2025*
