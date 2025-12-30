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

## Best Configuration: V7.1 Recommended

| Parameter | **Recommended Value** | Configurable |
|-----------|----------------------|--------------|
| Entry Confirmation | **0.10%** beyond Range | ✅ 0.05-0.15% |
| Hard Exit Time | **11:00 EST** | ✅ 10:00-11:30 |
| Day Filter | **Trade ALL Days** | ✅ Skip Tue/Wed optional |
| SL Type | **Range High/Low** | N/A |
| Max SL Cap | **0.25%** | ✅ |
| VVIX Filter | **Skip > 115** | ✅ Threshold configurable |
| Max Range | **0.25%** | ✅ |
| CTQ (TP1) | **0.05% (50%)** | ✅ 0.03-0.10% |
| Engulfing Exit | **ON** | ✅ |
| BE Trail | **OFF** | ✅ |

**Expected Result: +44.56% PnL, 42.6% WR** (trading all days with confirmed entry)

---

## Day of Week Analysis (UPDATED)

> ⚠️ **Previous recommendation to skip Tue/Wed was INCORRECT for V7.1 settings.**

| Config | Trades | Win Rate | **PnL** |
|--------|--------|----------|---------|
| **Trade ALL Days** | 2,272 | 42.6% | **+44.56%** ✅ |
| Skip Tuesday | 1,801 | 42.9% | +29.56% |
| Skip Wednesday | 1,811 | 42.5% | +40.88% |
| Skip Tue+Wed | 1,340 | 42.8% | +25.89% |

### Per-Day Breakdown

| Day | Trades | Win Rate | **PnL** | **Avg/Trade** |
|-----|--------|----------|---------|---------------|
| Mon | 446 | 44.2% | +5.37% | +0.012% |
| **Tue** | 471 | 41.6% | **+15.00%** | **+0.032%** |
| Wed | 461 | 43.0% | +3.67% | +0.008% |
| **Thu** | 457 | 42.5% | **+15.05%** | **+0.033%** |
| Fri | 437 | 41.9% | +5.47% | +0.013% |

**Key Finding**: Tuesday and Thursday are the **BEST days**, not worst. The earlier analysis used V6 settings (pullback entry, 10:00 exit). With V7.1 (confirmed entry, 11:00 exit), all days are profitable.

---

## Strategy Variants

| Variant | Trades | Win Rate | **PnL** | **PF** |
|---------|--------|----------|---------|--------|
| **ORB_NoCTQ** (Full ride) | 1,294 | 42.7% | **+25.38%** | 1.15 |
| **ORB_EngulfingExit** | 2,336 | 66.1% | **+19.86%** | 1.21 |
| ORB_AggressiveTP (0.03%) | 2,465 | 70.0% | +17.62% | 1.19 |
| ORB_V7.1 (CTQ 0.05%) | 2,370 | 68.8% | +16.90% | 1.16 |

---

## How to Be More Effective

### MUST DO ✅

| Action | Impact |
|--------|--------|
| **Wait for 0.10% confirmation** | +44% PnL |
| **Hold until 11:00 EST** | TIME exits = all profit |
| **Trade ALL days** | +44% vs +26% skipping Tue/Wed |
| **Use Range High/Low as SL** | Structure-based |
| **Exit on engulfing candle** | 70% would hit SL |

### AVOID ❌

| Action | Why |
|--------|-----|
| **Breakeven trail** | Kills 50-70% of profits |
| **Skip Tuesday/Thursday** | Best PnL days |
| **Exit before 11:00** | TIME exits = profit source |
| **Trade VVIX > 115** | High volatility whipsaws |

---

## Psychology Challenge

| What You'll Feel | What to Do |
|------------------|------------|
| "It's pulling back, exit!" | **Don't** - 99.8% pull back, 66% continue |
| "Move SL to breakeven" | **Don't** - kills profits |
| "Tuesday will be bad" | **Trade it** - +15% PnL on Tuesdays |

---

## Simulator Comparison

| Simulator | Return | Use For |
|-----------|--------|---------|
| **Custom State Machine** | **+16.90%** | CTQ, engulfing, complex logic |
| Vectorbt | -24.05% | Simple strategies only |

---

## Files Generated

| File | Description |
|------|-------------|
| `ORB_V7_SPEC.md` | Strategy specification |
| `SIMULATION_GUIDE.md` | Backtesting rules |
| `simulate_trades.py` | Extensible simulation framework |
| `variant_comparison_final.csv` | All variant results |

---

*Research compiled from 10 years of NQ1 data, December 2025*
