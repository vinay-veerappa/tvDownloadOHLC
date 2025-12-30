# ORB Strategy Trade Simulation Guide

## Purpose
This document explains how to properly simulate trades for the 9:30 ORB Breakout strategy. Use this as a reference when building or modifying backtesting code.

---

## Simulation Approaches

### 1. Custom State Machine (`simulate_orb_trades.py`)
Event-driven, bar-by-bar simulation with full state tracking.

### 2. Vectorbt (`simulate_orb_vectorbt.py`)
Vectorized backtesting using the vectorbt library.

---

## Critical Simulation Rules

### Entry Logic
1. **Wait for Confirmation**: Do NOT enter immediately on Range break
   - Long: Wait for bar CLOSE > Range High × 1.001 (0.10% above)
   - Short: Wait for bar CLOSE < Range Low × 0.999 (0.10% below)
   
2. **Entry Price**: Use bar CLOSE, not High/Low (we enter on close confirmation)

3. **No Entry After 10:30**: If no confirmation by 10:30, no trade for that day

### Exit Logic (Order of Priority)
1. **Engulfing Candle Exit** (Optional): If next bar engulfs breakout bar, exit immediately
   - Long: Exit if next bar close < breakout bar open AND high > breakout bar close
   - Stats: Only 3% of trades show engulfing, but 70% of those hit SL

2. **TP1 (Cover the Queen)**: Exit 50% at Entry + 0.05%
   - Long: TP1 = Entry × 1.0005
   - Fill at TP1 price (not bar close)

3. **Stop Loss**: Exit at Range opposite
   - Long SL = Range Low
   - Short SL = Range High
   - Fill at SL price (assumes stop order fill)
   
4. **Time Exit**: Exit all remaining at 11:00 bar close

### Position Tracking
```
State Machine States:
- FLAT: No position, looking for entry
- ENTERED: Full position, TP1 not hit
- PARTIAL: 50% exited at TP1, 50% remaining
- CLOSED: Trade complete
```

### Re-Entry Rules (Optional Enhancement)
If stopped at BE after TP1:
- May re-enter if price closes above previous entry level
- Limit: 1 re-entry per day

---

## Fill Price Assumptions

| Event | Fill Price |
|-------|------------|
| Entry | Bar Close (we enter on confirmation close) |
| TP1 | TP1 level (limit order assumption) |
| SL | SL level (stop order assumption) |
| Time Exit | Bar Close |

---

## What Pullback Analysis Showed

From `analyze_realistic_scenarios.py`:
- **99.8%** of trades pull back to entry level
- Pullback happens within **1.1 bars** on average
- **66%** of pullback trades continue to +0.10% after
- **Conclusion**: Pullback is NORMAL, not failure. Do NOT use BE trail.

---

## What Engulfing Analysis Showed

- Only **3%** of trades show engulfing candle
- But **70%** of engulfing trades hit SL (vs 27% without)
- **Conclusion**: Engulfing CAN be used as exit signal, but rare

---

## Simulation Checklist

Before running any simulation, verify:
- [ ] Using bar CLOSE for entry confirmation (not High/Low)
- [ ] Confirmation is 0.10% beyond Range (not just touching)
- [ ] TP1 fills at exact TP1 price (not bar close)
- [ ] SL fills at exact SL price (not bar close)
- [ ] Position tracking handles partial exits correctly
- [ ] No BE trail (kills the strategy)
- [ ] Time exit at 11:00 (not 10:00)
- [ ] Filters: Skip Tuesday, Wednesday, VVIX > 115, Range > 0.25%
