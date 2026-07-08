# Narrative Feedback Loop Architecture

> **Version:** 0.1 (2026-07-07)
> **Role:** Quantitative Analyst and Trading Strategist
> **Objective:** Build a robust, iterative feedback loop between daily, mid-week, and weekly narratives to ensure trading bias remains dynamic and data-driven rather than static. Focus on quantifying drawdowns, validating level accuracy, and refining the transition from overnight analysis to real-time price action.

---

## 1. The Feedback Loop

```
Weekly Briefing (Sunday/Monday)
  ↓ Reviews prior week performance (win rate, level accuracy, drawdown)
  ↓ Sets macro regime, tracks, key levels for the new week
  ↓ Outputs: mandated track, invalidation levels, risk envelope

Open Narrative (Daily AM)
  ↓ Reads overnight EOD plan from DB (continuity)
  ↓ Reads FRESH option chain levels (may differ from EOD close)
  ↓ Overnight Delta: compares EOD levels vs current open levels
  ↓ Bias is influenced by overnight but NOT dictated by it
  ↓ If overnight invalidated the EOD plan (regime flip, wall break), override
  ↓ If overnight confirmed the EOD plan, refine entries to current spot
  ↓ Outputs: today's trade plan with live levels

EOD Narrative (Daily PM)
  ↓ Grades today's trades: Win/Loss/No Entry, $ P&L, MAE/MFE
  ↓ Drawdown analysis: cumulative P&L, trailing DD remaining
  ↓ Level accuracy audit: did walls hold? Did EM contain price? Did magnet attract?
  ↓ Overnight Considerations: what to watch in globex
  ↓ Tomorrow's Setup: plan using today's close
  ↓ Outputs: tomorrow's plan saved to DB

Mid-Week Review (Wednesday EOD)
  ↓ Aggregates Mon-Wed performance
  ↓ Compares actual vs weekly briefing expectations
  ↓ Flags regime drift, level migration, track misalignment
  ↓ Adjusts Thursday/Friday bias if needed
  ↓ Outputs: mid-week correction or confirmation

Weekly Briefing (Next Sunday/Monday)
  ↓ Reviews full week: win rate, total P&L, max drawdown, level accuracy
  ↓ Identifies patterns: which regimes produced wins, which levels held
  ↓ Feeds insights into next week's briefing
  ↓ Outputs: new weekly briefing with prior week lessons
```

---

## 2. EOD Narrative — Daily Review Exercise

The EOD is the core feedback mechanism. It should be structured as a daily review exercise, not just a trade grader.

### 2.1 EOD Sections

| Section | Purpose | Data Source |
|---|---|---|
| Today's Regime | What regime were we in? | Compact EOD JSON |
| Session Log | Win/Loss/No Entry per instrument, $ P&L | DB trades + price action |
| Drawdown Tracker | Cumulative P&L, trailing DD remaining, days to breach | DB trades |
| Level Accuracy Audit | Did walls hold? EM contain? Magnet attract? Flip zone respect? | Compact EOD JSON (level_flags) |
| Trade Quality | MAE/MFE analysis — how much heat before profit? | DB trades (mae/mfe fields) |
| Note of the Day | One crucial observation | LLM synthesis |
| Overnight Considerations | Globex watch list | LLM + EOD levels |
| Tomorrow's Setup | Plan using today's close | LLM + EOD levels |
| Tomorrow's Risk Budget | Risk dollars, contracts, daily stop | Position sizing |
| `<plan_json>` | Tomorrow's plan saved to DB | Parsed by Python |

### 2.2 Drawdown Tracking

Python should compute the actual drawdown from DB trades, not let the LLM estimate it:

```python
async def get_drawdown_status() -> dict:
    """Query DB for cumulative P&L and compute trailing drawdown remaining."""
    # Sum all closed trade pnl for the account
    # trailing_dd_remaining = 2000 - abs(min(0, cumulative_pnl))
    # If trailing_dd_remaining <= 0: account blown
    # Return: {cumulative_pnl, trailing_dd_remaining, trades_count, win_rate}
```

### 2.3 Level Accuracy Audit

Python should pre-compute which levels held vs broke, using the `level_flags` from the compact EOD:

```
Level Accuracy (SPY):
  Call Wall 750.00: HELD (not tested) | Put Wall 745.00: BROKEN
  EM Upper 748.69: TESTED | EM Lower 743.33: HELD
  Zero Gamma 748.59: RESPECTED | Magnet 738.84: NOT TESTED
```

---

## 3. Open Narrative — Overnight Transition

### 3.1 Key Principle

The overnight EOD plan is a **reference, not a mandate**. The open narrative should:

1. **Check if the EOD plan is still valid** — did overnight price action invalidate any entries?
2. **Update bias from overnight** — gap direction, globex range, level tests
3. **Focus on what price is saying NOW** — the live levels are the truth, not yesterday's plan
4. **Override if needed** — if regime flipped or walls broke overnight, the EOD plan is dead

### 3.2 Overnight Delta Section

The LLM should answer:
- Did the EOD's planned entry get hit overnight? (gap through it = filled)
- Did any walls shift from EOD close to open? (level migration)
- Did the regime change? (compare EOD META_REGIME vs open META_REGIME)
- Is the EOD plan still valid, needs adjustment, or is invalidated?

---

## 4. Mid-Week Review

### 4.1 Purpose

Wednesday EOD runs a special mid-week review that:
- Aggregates Mon-Wed performance (P&L, win rate, level accuracy)
- Compares actual price action vs the weekly briefing's expectations
- Flags if the weekly mandated track is still appropriate
- Adjusts Thu/Fri bias if the week is off-track

### 4.2 Implementation

Add a `--session midweek` option to `daily_narrative.py` that:
- Loads the weekly briefing from DB
- Loads Mon-Wed EOD narratives from DB
- Computes aggregate stats
- Uses a `midweek_review.md` prompt template

---

## 5. Weekly Briefing — Prior Week Review

### 5.1 Prior Week Performance Section

The weekly briefing should start with a review of the previous week:
- Total P&L per instrument
- Win rate
- Max drawdown
- Level accuracy score (what % of walls held?)
- Regime accuracy (did the mandated track produce wins?)
- Key lesson: what worked, what didn't

### 5.2 Implementation

Add `get_prior_week_performance()` to `briefing_core.py` that queries the DB for the previous week's closed trades and computes aggregate stats. Inject this into the weekly prompt as `{{INSERT_PRIOR_WEEK_REVIEW}}`.

---

## 6. Implementation Plan

| Phase | Component | Priority |
|---|---|---|
| 1 | EOD drawdown tracking (Python computes from DB) | High |
| 2 | EOD level accuracy audit (Python pre-computes from level_flags) | High |
| 3 | EOD prompt restructured as daily review exercise | High |
| 4 | Open prompt: overnight delta logic clarified | Medium |
| 5 | Mid-week review prompt + session type | Medium |
| 6 | Weekly prompt: prior week review section | Medium |
| 7 | `get_prior_week_performance()` function | Medium |
| 8 | `get_drawdown_status()` function | High |
| 9 | `get_midweek_stats()` function | Low |