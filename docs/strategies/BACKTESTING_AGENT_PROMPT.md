# Backtesting Simulation Prompt for Agents

## Purpose
Use this prompt when asking an AI agent to work on backtesting or trade simulation for the 9:30 ORB strategy (or future strategies).

---

## Context to Provide

When starting a backtesting session, copy this context to the agent:

```
## Trade Simulation Framework

We have an extensible backtesting framework at:
`scripts/backtest/framework/simulate_trades.py`

### Key Components:
- `BaseStrategy` - Abstract class all strategies inherit from
- `TradeSimulator` - Engine that runs any strategy bar-by-bar
- `ORB_V7_Strategy` - Implementation for 9:30 ORB breakout

### How to Create a New Strategy:
1. Inherit from `BaseStrategy`
2. Implement required methods:
   - `should_trade_day(context)` - Day-level filters
   - `should_enter(bar, state, context)` - Entry logic
   - `should_exit(bar, state, context)` - Exit logic
3. Run with `TradeSimulator(YourStrategy()).run()`

### Simulation Rules (CRITICAL):
- Read `docs/strategies/9_30_breakout/SIMULATION_GUIDE.md` before making changes
- Entry must use bar CLOSE (not High/Low) for confirmation
- TP fills at exact TP price, SL fills at exact SL price
- Time exit fills at bar close
- Track state: FLAT → ENTERED → PARTIAL → CLOSED
- 99.8% of trades pull back to entry - this is NORMAL
- Do NOT use BE trail (kills profits)

### Data Available:
- `data/{TICKER}_opening_range.json` - Range High/Low/Open
- `data/{TICKER}_1m.parquet` - 1-minute OHLC bars
- `data/VVIX_1d.parquet` - VVIX daily opens

### Running Tests:
```bash
python scripts/backtest/framework/simulate_trades.py
```

### Key Files:
- `docs/strategies/9_30_breakout/ORB_V7_SPEC.md` - Strategy specification
- `docs/strategies/9_30_breakout/SIMULATION_GUIDE.md` - Simulation rules
- `scripts/backtest/9_30_breakout/analyze_realistic_scenarios.py` - Post-breakout analysis
```

---

## Common Mistakes to Avoid

Tell the agent to avoid these errors:

1. **Using High/Low for entry** - Must use bar CLOSE
2. **Entering immediately on range break** - Must wait for 0.10% confirmation
3. **Using breakeven trail** - Kills 50-70% of profits
4. **Ignoring pullback behavior** - 99.8% of trades pull back; this is normal
5. **Fixed % SL instead of Range-based** - Use Range High/Low as SL
6. **Not tracking partial exits** - CTQ exits 50% at TP1, 50% runs to time

---

## Example Agent Prompt

```
I want to test a new variant of the ORB strategy. 

Context:
[Paste the context section above]

Task:
Create a new strategy that waits for price to pull back to Range High 
after initial breakout, then enters. Compare results to the standard 
V7.1 strategy using the same simulation framework.

Use the BaseStrategy class to implement this and provide:
1. The new strategy class
2. Comparison of results (trades, WR, PnL, PF)
3. Analysis of when each approach works better
```

---

## Framework Extension Points

When the agent needs to add features:

| Feature | Where to Add |
|---------|--------------|
| New filter | `should_trade_day()` method |
| New entry logic | `should_enter()` method |
| New exit logic | `should_exit()` method |
| New SL/TP type | `on_entry()` + `should_exit()` |
| Track new metrics | Add to `TradeState.custom` dict |
| Re-entry logic | Add state in `TradeState`, check in `should_enter()` |

---

## Current Strategy: ORB V7.1

Quick reference for agents:

| Parameter | Value |
|-----------|-------|
| Entry | Confirmed 0.10% beyond Range |
| TP1 | 0.05% (50% partial exit) |
| SL | Range High/Low (structure-based) |
| Hard Exit | 11:00 EST |
| Skip Days | Tuesday, Wednesday |
| VVIX Filter | Skip if > 115 |
| BE Trail | NO (kills profits) |
