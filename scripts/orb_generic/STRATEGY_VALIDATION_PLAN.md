# MNQ/MES Prop Firm Bot — Strategy Validation Plan

## Overview

**Goal:** Statistically validate trading strategies on ES and NQ 1-min OHLCV data (20 years) before building execution bots for NinjaTrader. All strategies must be viable under prop firm constraints (< $2,000 drawdown).

**Instruments:** ES (MES) and NQ (MNQ)
**Data:** 1-min OHLCV parquet files, ~20 years
**Execution Stack:** Python (validation) → Pine Script (visual confirmation) → NinjaScript (live bot)
**Risk Constraint:** Max $100 risk/trade, max $300 daily loss, trailing drawdown < $2,000

---

## Data Preparation (Run First)

### Script: `00_data_prep.py`

Before any study, we need to standardize the data and compute session-level reference points.

**Input:** Raw parquet files for ES and NQ (1-min OHLCV with timestamps)

**Tasks:**

1. **Load and validate data**
   - Read parquet files into pandas DataFrames
   - Confirm columns: `datetime`, `open`, `high`, `low`, `close`, `volume`
   - Ensure datetime is timezone-aware (convert to US/Eastern if not already)
   - Check for gaps — log any missing trading days or suspicious gaps within sessions
   - Filter to RTH (Regular Trading Hours: 9:30-16:00 ET) and ETH (Extended Trading Hours: 18:00-17:00 ET next day) separately
   - Create a `trade_date` column: the calendar date each bar belongs to (ETH bars before midnight belong to next trade_date)

2. **Compute daily reference levels** — output as `daily_levels.parquet`

   For each `trade_date`, calculate:
   ```
   - prev_day_high (PDH): prior RTH session high
   - prev_day_low (PDL): prior RTH session low
   - prev_day_close (PDC): prior RTH session close (16:00 bar close)
   - prev_day_open (PDO): prior RTH session open (9:30 bar open)
   - overnight_high (ONH): high from 18:00 prev day to 9:29 current day
   - overnight_low (ONL): low from 18:00 prev day to 9:29 current day
   - weekly_open: Monday's RTH 9:30 open (carry forward Tue-Fri)
   - prev_week_high: prior week's RTH high (Mon-Fri)
   - prev_week_low: prior week's RTH low (Mon-Fri)
   - day_of_week: 0=Mon, 4=Fri
   ```

3. **Compute session ranges** — output as `session_ranges.parquet`

   For each `trade_date`, calculate:
   ```
   - asia_high: high from 20:00-00:00 ET (prior evening)
   - asia_low: low from 20:00-00:00 ET
   - london_high: high from 02:00-05:00 ET
   - london_low: low from 02:00-05:00 ET
   - london_open_high: high from 02:00-03:00 ET (first hour)
   - london_open_low: low from 02:00-03:00 ET
   - pre_market_high: high from 08:00-09:29 ET
   - pre_market_low: low from 08:00-09:29 ET
   ```

4. **Compute opening ranges** — output as `opening_ranges.parquet`

   For each `trade_date`, calculate:
   ```
   - or_5min_high: high of 9:30-9:34 (first 5 bars)
   - or_5min_low: low of 9:30-9:34
   - or_15min_high: high of 9:30-9:44 (first 15 bars)
   - or_15min_low: low of 9:30-9:44
   - or_30min_high: high of 9:30-9:59 (first 30 bars)
   - or_30min_low: low of 9:30-9:59
   - or_60min_high: high of 9:30-10:29 (first 60 bars)
   - or_60min_low: low of 9:30-10:29
   - or_15min_width: or_15min_high - or_15min_low (in points)
   - or_30min_width: or_30min_high - or_30min_low
   ```

**Output files:**
- `daily_levels.parquet` — one row per trade_date per instrument
- `session_ranges.parquet` — one row per trade_date per instrument
- `opening_ranges.parquet` — one row per trade_date per instrument
- `data_quality_report.txt` — summary of gaps, missing days, date range covered

---

## Study 1: Opening Range Breakout/Failure Statistics

### Script: `01_opening_range_study.py`

**Purpose:** Determine if the Opening Range has a statistically exploitable edge, and under what conditions.

**Dependencies:** Outputs from `00_data_prep.py` + raw 1-min data

### Analysis 1.1: Basic OR Breakout Rates

For each OR duration (5min, 15min, 30min, 60min):

```
For each trade_date:
  - Did price break above the OR high during RTH (10:00-16:00 for 30min OR)?  → bool
  - Did price break below the OR low during RTH?  → bool
  - Which side broke first?  → 'high_first' | 'low_first' | 'simultaneous' | 'neither'
  - Time of first breakout (minutes after OR close)
  - Did the OTHER side also get taken out after the first break?  → bool (Judas swing)
  - Time between first break and second break (if both broken)
```

**Output table:** `or_breakout_rates.csv`
| Metric | OR_5min | OR_15min | OR_30min | OR_60min |
|--------|---------|----------|----------|----------|
| % days high broken | | | | |
| % days low broken | | | | |
| % days both broken | | | | |
| % days neither broken | | | | |
| % high broken first | | | | |
| % low broken first | | | | |
| % Judas swing (first break fails, other side taken) | | | | |
| Avg time to first break (minutes) | | | | |
| Median time to first break | | | | |

Compute separately for ES and NQ.

### Analysis 1.2: OR Breakout Excursion

After the OR is broken, how far does price travel before reversing?

```
For each trade_date where OR high was broken:
  - max_excursion_up: highest price reached after breaking OR high, minus OR high (points)
  - max_adverse_after_break: lowest price reached after breaking OR high, minus OR high (negative = went back below)
  - Did price close the day above OR high?  → bool

For each trade_date where OR low was broken:
  - max_excursion_down: OR low minus lowest price reached after breaking OR low (points)  
  - max_adverse_after_break: highest price after breaking OR low, minus OR low (positive = went back above)
  - Did price close the day below OR low?  → bool
```

**Output:** Distribution statistics (mean, median, 25th/75th percentile, std) for each metric. Also output raw arrays for histogram plotting.

**Output file:** `or_excursion_stats.csv` + `or_excursion_raw.parquet` (for plotting)

### Analysis 1.3: OR Width as Predictor

Does the width of the opening range predict the day's behavior?

```
For each trade_date:
  - Bucket OR width into quintiles (narrowest 20%, next 20%, etc.)
  - For each bucket, compute:
    - % Judas swing
    - Average max excursion after breakout
    - % trend day (only one side broken, large excursion)
    - % chop day (both sides broken, small net move)
    - RTH range (day high - day low) as multiple of OR width
```

**Output file:** `or_width_analysis.csv`

### Analysis 1.4: OR + Context (Key Levels)

How do OR breakout stats change based on WHERE the OR forms relative to key levels?

```
For each trade_date:
  - OR position relative to PDH/PDL:
    - 'above_PDH': OR low > PDH (gap up above prior day)
    - 'below_PDL': OR high < PDL (gap down below prior day)
    - 'inside': OR is between PDH and PDL
    - 'straddle_PDH': PDH is inside OR range
    - 'straddle_PDL': PDL is inside OR range
    
  - OR position relative to ONH/ONL:
    - 'above_ONH': OR formed above overnight high
    - 'below_ONL': OR formed below overnight low
    - 'inside_ON': OR is within overnight range
    
  - For each context bucket, compute:
    - Breakout direction bias (% high first vs low first)
    - Judas swing rate
    - Average excursion
    - Win rate for: long on OR high break, short on OR low break
    - Win rate for: fade the first break (Judas trade)
```

**Output file:** `or_context_analysis.csv`

### Analysis 1.5: OR by Day of Week

```
For each day (Mon-Fri):
  - All metrics from 1.1, 1.2, 1.3
  - Specific focus: Does Monday have different OR behavior? (Weekly open = fresh range)
  - Tuesday/Wednesday: Are these the "real move" days?
```

**Output file:** `or_day_of_week.csv`

---

## Study 2: Session Sweep Sequences

### Script: `02_session_sweep_study.py`

**Purpose:** Validate the ICT concept that London sweeps Asia liquidity and NY often reverses or continues from London's move.

**Dependencies:** `session_ranges.parquet`, `daily_levels.parquet`, raw 1-min data

### Analysis 2.1: London vs Asia

```
For each trade_date:
  - Did London break above Asia high?  → bool
  - Did London break below Asia low?  → bool
  - Which side did London sweep first?  → 'high' | 'low' | 'both' | 'neither'
  - London net direction: close of 05:00 bar vs 02:00 bar open → 'up' | 'down'
  - Did London sweep ONE side only (single sweep = cleaner setup)?
```

**Output:** Frequency table of sweep patterns

### Analysis 2.2: NY Response to London Sweep

```
For each trade_date where London made a clear single-side sweep:
  - Did NY (09:30-12:00) reverse the London direction?
  - Did NY take out the opposite side of the Asia range?
  - How far did NY extend from the London extreme?
  - What was the max drawdown of a trade entered at NY open in the reversal direction?
```

**Output:** `session_sweep_stats.csv` with:
- % NY reversal when London swept Asia high only
- % NY reversal when London swept Asia low only  
- Average NY excursion on reversal
- Average MAE (max adverse excursion) on reversal trade

### Analysis 2.3: Overnight Range as Day Framing

```
For each trade_date:
  - % of days where ONH = day high (overnight high holds all day)
  - % of days where ONL = day low
  - % of days where BOTH ONH and ONL hold (inside day relative to overnight)
  - When ONH is broken in RTH: avg continuation above ONH
  - When ONL is broken in RTH: avg continuation below ONL
  - Time of day when ONH/ONL typically gets broken
```

**Output file:** `overnight_range_stats.csv`

---

## Study 3: Key Level Rejection/Acceptance

### Script: `03_key_level_study.py`

**Purpose:** Quantify how price behaves at PDH, PDL, PDC, Weekly Open, ONH, ONL.

**Dependencies:** `daily_levels.parquet`, raw 1-min data

### Analysis 3.1: PDH/PDL Touch Statistics

```
For each trade_date:
  For each level (PDH, PDL):
    - Did price reach within 2 points of the level?  → bool
    - If reached, did it REJECT (close back away within 15 min)?  → bool
    - If reached, did it ACCEPT (close 3+ bars beyond the level)?  → bool
    - On rejection: max retracement from level (points)
    - On acceptance: max continuation beyond level (points)
    - Time of day when level was first tested
    - Number of times level was tested before final resolution
```

**Key metrics to compute:**
```
- Overall rejection rate at PDH
- Overall rejection rate at PDL
- Rejection rate when price approaches PDH from below during first 2 hours
- Rejection rate when price approaches PDL from above during first 2 hours
- Average reject distance (how far does price bounce?)
- Average accept continuation (how far does it go through?)
- Does rejection rate change based on # of prior tests?
```

**Output file:** `key_level_stats.csv`

### Analysis 3.2: Weekly Open as S/R

```
For each trade_date (Tue-Fri only):
  - Price position relative to weekly open at 9:30: above or below?
  - Number of times price crosses weekly open during RTH
  - Does weekly open act as S/R? 
    - When above: does it hold as support on retest?
    - When below: does it hold as resistance on retest?
  - Stats by day of week (does weekly open matter more on Tue than Fri?)
```

**Output file:** `weekly_open_stats.csv`

### Analysis 3.3: PDC (Previous Day Close) as Magnet

```
For each trade_date:
  - Gap size: 9:30 open vs PDC (points)
  - Did price fill the gap (return to PDC)?  → bool
  - Time to gap fill (minutes from 9:30)
  - % gap fill by gap size bucket (small < 10pts, medium 10-30pts, large > 30pts)
  - For NQ specifically: gap fill rates (NQ tends to be more volatile)
```

**Output file:** `gap_fill_stats.csv`

---

## Study 4: Macro Time Window Analysis

### Script: `04_macro_time_study.py`

**Purpose:** Validate ICT macro times (x:50 to x+1:10) as high-displacement windows.

**Dependencies:** Raw 1-min data

### Analysis 4.1: Volatility by Time Window

```
For each 20-minute window in the trading day (9:30-9:50, 9:50-10:10, 10:10-10:30, ...):
  - Average range (high - low of that 20-min block)
  - Average absolute price change (|close - open| of the block)
  - Average volume
  - Displacement rate: % of blocks where |close - open| > 0.7 * (high - low)
    (This measures strong directional moves vs. choppy consolidation)
```

**Compare macro windows (x:50-x:10) against non-macro windows.**

**Output file:** `macro_time_volatility.csv`

Specific macro windows to flag:
```
- 09:50 - 10:10 ET (first post-OR macro)
- 10:50 - 11:10 ET 
- 13:50 - 14:10 ET (post-lunch)
- 14:50 - 15:10 ET (afternoon)
```

### Analysis 4.2: FVG Formation During Macro Times

```
FVG Detection Logic (1-min bars):
  Bullish FVG: bar[0].high < bar[2].low (gap between bar 0 high and bar 2 low)
  Bearish FVG: bar[0].low > bar[2].high

For each 20-minute window:
  - Count of FVGs formed
  - Average size of FVGs (gap width in points)
  - Fill rate: % of FVGs that get at least 50% filled within next 30 minutes
  - Respect rate: % of FVGs where price touches the FVG and reverses (within 2 hours)
```

**Output file:** `macro_fvg_stats.csv`

---

## Study 5: Day-of-Week and Weekly Profile

### Script: `05_weekly_profile_study.py`

**Purpose:** Validate ICT weekly profile concepts — Monday sets range, Tue/Wed deliver, Thu reverses.

**Dependencies:** `daily_levels.parquet`, raw 1-min data

### Analysis 5.1: Which Day Sets the Week's High/Low?

```
For each trading week:
  - Which day made the week's high? (Mon/Tue/Wed/Thu/Fri)
  - Which day made the week's low?
  - Range contribution: each day's range as % of the total weekly range
  - Did Monday's high or low hold as the week's high or low?
```

**Output:**
| Day | % Week High | % Week Low | Avg Range Contribution |
|-----|-------------|------------|----------------------|
| Mon | | | |
| Tue | | | |
| Wed | | | |
| Thu | | | |
| Fri | | | |

### Analysis 5.2: Day-to-Day Continuation/Reversal

```
For each consecutive day pair:
  - If Monday was bullish (close > open), what % of Tuesdays are also bullish?
  - If Tuesday set a new weekly high, what % of Wednesdays reverse?
  - Continuation vs reversal rates for each day pair
  - Average follow-through distance when continuing vs reversing
```

**Output file:** `daily_continuation_rates.csv`

---

## Study 6: Prop Firm Viability Simulation

### Script: `06_prop_sim.py`

**Purpose:** Given the statistical edges found in Studies 1-5, simulate actual prop firm account performance with realistic constraints.

**Dependencies:** Results from all prior studies + raw 1-min data for walk-forward testing

### Simulation Parameters

```python
config = {
    # Prop firm constraints
    "max_drawdown": 2000,          # dollars
    "daily_loss_limit": 300,       # dollars - self-imposed (15% of drawdown)
    "max_trades_per_day": 3,
    "trailing_drawdown": True,     # most prop firms use trailing until funded
    
    # Position sizing (MNQ)
    "mnq_tick_value": 0.50,        # $0.50 per tick (0.25 point)
    "mnq_point_value": 2.00,       # $2.00 per point
    "contracts": 1,                # start with 1
    
    # Position sizing (MES)  
    "mes_tick_value": 0.3125,      # $0.3125 per tick (0.25 point)
    "mes_point_value": 1.25,       # $1.25 per point
    
    # Strategy parameters (to be filled from study results)
    "stop_loss_points": None,      # determined by study
    "target_points": None,         # determined by study
    "entry_logic": None,           # determined by study
}
```

### Simulation Logic

```
For each trade_date in test period (walk-forward: train on 2 years, test on next 6 months, slide):
  
  1. Check daily P&L — if daily loss limit hit, skip day
  2. Check account equity — if within $200 of max drawdown, reduce to MES only
  3. Check account equity — if max drawdown hit, account blown (log it)
  
  4. Run strategy signals for the day:
     - Identify OR levels, session context, key levels
     - Generate entry signals with stop and target
     - Execute up to max_trades_per_day
  
  5. For each trade:
     - Entry at signal bar close (conservative) or signal bar + 1 tick (aggressive)
     - Track bar-by-bar: check if stop or target hit first
     - Log: entry_time, entry_price, exit_time, exit_price, P&L, MAE, MFE
  
  6. End of day: update equity curve, drawdown tracker

Output:
  - equity_curve.csv: date, daily_pnl, cumulative_pnl, drawdown, max_drawdown_used
  - trade_log.csv: every trade with full details
  - Summary: total trades, win rate, avg win, avg loss, profit factor, max drawdown,
    Sharpe ratio, avg trades/day, longest losing streak, 
    # of accounts blown (in Monte Carlo), % of simulations passing eval
```

### Monte Carlo Overlay

Run 1,000 random permutations of the trade sequence to estimate:
- Probability of passing a prop firm eval (e.g., hit $3,000 profit before $2,000 drawdown)
- Expected time to pass (trading days)
- Risk of ruin
- Optimal position sizing

**Output file:** `monte_carlo_results.csv` + `equity_curves_sample.png`

---

## Execution Order

```
Phase 1: Data Foundation
  └── Run 00_data_prep.py
  └── Verify data_quality_report.txt — fix any issues before proceeding

Phase 2: Core Studies (can run in parallel)
  ├── Run 01_opening_range_study.py     ← HIGHEST PRIORITY
  ├── Run 02_session_sweep_study.py
  ├── Run 03_key_level_study.py
  ├── Run 04_macro_time_study.py
  └── Run 05_weekly_profile_study.py

Phase 3: Synthesis
  └── Review all output CSVs
  └── Identify the 1-2 strategies with clearest statistical edge
  └── Define exact entry/exit rules with specific parameters

Phase 4: Simulation
  └── Run 06_prop_sim.py with the selected strategy
  └── Run Monte Carlo analysis
  └── Determine if the strategy passes prop firm viability threshold

Phase 5: Platform Implementation
  └── Build Pine Script indicator for visual confirmation on TradingView
  └── Build NinjaScript strategy for Strategy Analyzer backtesting
  └── Run NinjaTrader Market Replay testing
  └── Sim trading for 30+ trades
  └── Go live on prop firm eval
```

---

## Output Directory Structure

```
/strategy_validation/
├── data/
│   ├── ES_1min.parquet          (raw input)
│   ├── NQ_1min.parquet          (raw input)
│   ├── daily_levels.parquet     (from 00)
│   ├── session_ranges.parquet   (from 00)
│   └── opening_ranges.parquet   (from 00)
├── results/
│   ├── data_quality_report.txt
│   ├── or_breakout_rates.csv
│   ├── or_excursion_stats.csv
│   ├── or_excursion_raw.parquet
│   ├── or_width_analysis.csv
│   ├── or_context_analysis.csv
│   ├── or_day_of_week.csv
│   ├── session_sweep_stats.csv
│   ├── overnight_range_stats.csv
│   ├── key_level_stats.csv
│   ├── weekly_open_stats.csv
│   ├── gap_fill_stats.csv
│   ├── macro_time_volatility.csv
│   ├── macro_fvg_stats.csv
│   ├── daily_continuation_rates.csv
│   ├── monte_carlo_results.csv
│   └── equity_curves_sample.png
├── scripts/
│   ├── 00_data_prep.py
│   ├── 01_opening_range_study.py
│   ├── 02_session_sweep_study.py
│   ├── 03_key_level_study.py
│   ├── 04_macro_time_study.py
│   ├── 05_weekly_profile_study.py
│   └── 06_prop_sim.py
└── pine/
    └── (Pine Script indicators — Phase 5)
```

---

## Key Assumptions & Notes

1. **Timezone consistency is critical.** All times in ET. Parquet timestamps must be converted correctly — verify DST handling. CME futures switch at 2am ET with the rest of the US.

2. **RTH vs ETH matters.** PDH/PDL should be calculated on RTH only (9:30-16:00 ET). Overnight range uses ETH (18:00 prior day to 9:29). Some strategies may need ETH data for session sweeps.

3. **Contract rollover.** If the 20 years of data includes front-month rollovers, there may be price gaps at rollover dates. Flag these in data_quality_report and exclude rollover days from studies (or use continuous/back-adjusted contracts if that's what the parquet contains).

4. **Statistical significance.** With ~5,000 trading days, even sub-patterns should have sufficient sample size. Target minimum 100 occurrences for any pattern before drawing conclusions. Report sample size alongside every metric.

5. **Slippage and execution.** In the prop sim (Study 6), assume 1 tick slippage on entry and 1 tick on exit for market orders. Limit order entries assume fill at limit price only if price trades through by 1 tick.

6. **No lookahead bias.** Every calculation must use only data available at the time of the signal. OR levels are known only after the OR period closes. PDH/PDL use prior completed sessions only.

7. **Parquet file format.** Expecting columns: `datetime` (or `timestamp`), `open`, `high`, `low`, `close`, `volume`. Script 00 should be flexible enough to handle common column name variations and print the actual column names found for verification.

---

## Success Criteria

A strategy is worth building into a bot if:

- **Win rate × avg win > Loss rate × avg loss** (positive expectancy, obviously)
- **Profit factor > 1.5** on out-of-sample data
- **Win rate > 50%** (prop firms punish losing streaks hard with trailing drawdown)
- **Max drawdown in simulation < $1,500** (leaves $500 buffer on $2,000 limit)
- **Monte Carlo: > 60% probability of passing eval** within 30 trading days
- **Average trades per day: 1-3** (enough to make progress, not overtrading)
- **No single day accounts for > 30% of total profit** (consistency rule)
- **Edge is present in BOTH ES and NQ** (or at least one with strong confidence)
- **Edge persists across multiple years** (not regime-dependent)
