# MNQ/MES Prop Firm Trading Bot — Complete Project Documentation
## Last Updated: End of v6 iteration

---

## Project Overview

**Goal:** Build a statistically validated, automated trading bot for NQ (MNQ) and ES (MES) futures that can pass prop firm evaluations with < $2,000 drawdown.

**Approach:** Data-driven. Validate strategies on 20 years of 1-min OHLCV data before building execution bots.

**Current Status:** CHOCH Fade + IB Bias is the winning combination (v5: 64.3% WR, PF 2.17, $778 MaxDD). The v6 zone-based rewrite attempted to include OR-internal structure but introduced a zone expiration bug that degraded performance. The zone architecture concept is correct but needs expiration/freshness logic. Pine Script v4 is functional with IB bias + full structure from 9:30.

**Instruments:** ES1 (S&P 500 futures, continuous), NQ1 (Nasdaq 100 futures, continuous), both back-adjusted, 2006-2026.

**Data:** 1-min OHLCV parquet files at `C:\Users\vinay\tvDownloadOHLC\data`. Timestamps in UTC, converted to US/Eastern.

**Execution Stack:** Python (validation) → Pine Script (visual confirmation on TradingView) → NinjaScript (live bot on NinjaTrader).

---

## Version History

| Version | Architecture | Best Result (NQ1 CHOCH) | Key Change |
|---|---|---|---|
| v1-v3 | Post-OR only, event-based | 89 trades, 65.2% WR, PF 2.80 | Original implementation |
| v4 | Post-OR, 7 strategies compared | Same — CHOCH only profitable | Head-to-head comparison |
| **v5** | **OR-start structure + IB Bias** | **112 trades, 64.3% WR, PF 2.17, $778 DD** | **IB bias filter added, structure from 9:30** |
| v6 | Zone-based + IB Bias | 712 trades, 43.1% WR, PF 0.82 | Zone entry on pullback — BROKEN (no expiration) |

**v5 is the current best implementation.** v6 concept is sound but needs fixes before use.

---

## Directory Structure

```
strategy_validation/
├── config/
│   ├── __init__.py
│   └── settings.py              ← Master config: sessions, instruments, OR durations, prop rules
├── scripts/
│   ├── __init__.py
│   ├── utils.py                 ← Shared helpers: data loading, date normalization
│   ├── market_structure.py      ← VWAP, swings, BOS/CHOCH, OBs, FVGs, fibs, ATR
│   ├── signal_generators.py     ← 7 strategy generators (v5=event-based, v6=zone-based)
│   ├── 00_data_prep.py          ← Parquet → cached CSV
│   ├── 01_opening_range_study.py
│   ├── 02_session_sweep_study.py
│   ├── 03_key_level_study.py
│   ├── 04_macro_time_study.py
│   ├── 05_weekly_profile_study.py
│   ├── 06_prop_sim.py           ← Prop firm simulation + Monte Carlo
│   ├── 07_strategy_comparison.py ← Head-to-head strategy runner
│   └── 08_ib_bias_study.py      ← IB bias validation
├── data/raw/                    ← Parquet files
├── data/derived/                ← Cached CSVs
├── results/                     ← Study outputs
└── pine/
    └── OR_Strategy_Lab_v4.pine  ← TradingView strategy visualizer
```

---

## Scripts Reference

### Config & Utilities

**`config/settings.py`** — Master configuration: session times (RTH 9:30-16:00, Asia 20:00-00:00, London 02:00-05:00), OR durations (5/15/30/45/60 min), instrument specs (MNQ $2/pt, MES $1.25/pt), prop firm rules (max DD $2000, daily limit $300), timezone (`raw_timezone: "UTC"`, `target_timezone: "US/Eastern"`).

**`scripts/utils.py`** — `load_parquet()`, `load_derived()` (forces UTC parse for `_1min` files), `normalize_trade_date()` (critical date matching fix), session filtering, OR computation, FVG detection, data quality checks.

**`scripts/market_structure.py`** — `compute_vwap()`, `detect_swings()`, `detect_structure_shifts()` (BOS/CHOCH with HH/HL/LH/LL trend tracking, level consumption after break), `detect_order_blocks()`, `detect_fvgs()`, `fib_levels()`/`fib_zone()`, `compute_atr()`, percentage normalization helpers.

### Study Scripts (00-08)

| Script | Purpose | Key Output |
|---|---|---|
| `00_data_prep.py` | Parquet → cached CSV | daily_levels, session_ranges, opening_ranges, rth_1min |
| `01_opening_range_study.py` | OR breakout rates, Judas swings | Breakout %, excursion stats, width analysis, day-of-week |
| `02_session_sweep_study.py` | London/Asia sweeps, NY response | Sweep rates, NY reversal %, overnight framing |
| `03_key_level_study.py` | PDH/PDL/ONH/ONL, gap fills | Level rejection/acceptance, 100% gap fill rate |
| `04_macro_time_study.py` | ICT macro windows, FVG by time | Macro 9-11% more volatile, NOT more directional |
| `05_weekly_profile_study.py` | Weekly extremes, continuation | Monday = week's low 35%, Thu reversal = coin flip |
| `06_prop_sim.py` | Trade simulation + Monte Carlo | Original OR fade: blown (inverted R:R) |
| `07_strategy_comparison.py` | 7 strategies head-to-head | CHOCH only profitable; v5 and v6 versions exist |
| `08_ib_bias_study.py` | Which extreme formed first | 71% accuracy, stronger for wider ORs |

**Running data prep:** `python scripts/00_data_prep.py --input-dir "C:\Users\vinay\tvDownloadOHLC\data"`

**Running comparison (v5):** `python scripts/07_strategy_comparison.py --symbol NQ1 --use-ib-bias`

### Signal Generators (Two Versions Exist)

**v5 (event-based, CURRENT BEST):** `signal_generators.py` from `strategy_v5_ib_bias.tar.gz`. Each strategy detects structural events and enters on the event bar. Structure detection runs from OR start (9:30). `get_day_context()` takes `or_start_idx` and `or_end_idx`. IB bias computed via `compute_ib_bias()`. All generators accept `bias` parameter.

**v6 (zone-based, NEEDS FIXES):** `signal_generators.py` from `strategy_v6_zones.tar.gz`. Builds zones from 9:30 (Fib, FVG, OB, CHOCH, OR boundary, VWAP), scores by confluence, scans for price entering zones post-OR. **Problem: zones never expire, causing stale entries.** See "v6 Zone Architecture Issues" section below.

---

## Key Results

### Study 1: Opening Range (NQ 30-min, 4,082 days)

- Low breaks first 43.7% vs high first 34.6%
- Judas swing rate: 24.8%
- Median excursion: 23-27 pts
- 30-min Judas median R:R: 1.14
- OR inside prior day range → 91% both sides broken

### Study 2: Session Sweeps

- London swept Asia high only → NY reverses **72.2%** (NQ)
- London swept Asia low only → NY reverses **60.8%** (NQ)

### Study 3: Key Levels

- ONH break-through: 92.4% (NQ) — continuation level, don't fade
- ONL break-through: 95.1%
- Gap fill: **100% across all sizes, 20 years**
- PDH/PDL: DATA BUG (0% break-through due to proximity logic flaw)

### Study 4: Macro Times

- Macro windows 9-11% more volatile, but **same displacement rate** as non-macro
- FVG formation/fill/respect rates identical for macro vs non-macro

### Study 5: Weekly Profile

- Monday sets week's low **35%** of the time
- Monday bullish → week bullish 68-70%
- Thursday reversal = **50.5% (coin flip, NOT supported)**
- Friday missing from weekly extremes (data prep bug)

### Study 7: Strategy Comparison (v5, IB Bias)

| Strategy | NQ1 PF | NQ1 WR | Trades | P&L | MaxDD | Verdict |
|---|---|---|---|---|---|---|
| **CHOCH Fade** | **2.17** | **64.3%** | **112** | **+$8,131** | **$778** | **WINNER** |
| FVG Displacement | 1.03 | 45.7% | 1,303 | +$2,033 | $8,721 | Break-even |
| All others | <0.83 | <37% | varies | negative | huge | Losing |

### Study 8: IB Bias ("Which Extreme Formed First")

| OR Duration | NQ Accuracy | Best Width Bucket |
|---|---|---|
| **15 min** | **70.6%** | 0.4-0.6%: **78.2%** |
| 30 min | 70.3% | 0.4-0.6%: 75.0% |
| 45 min | 68.7% | 0.4-0.6%: 74.9% |
| 60 min | 68.3% | 0.6-0.9%: 74.3% |

- **"Low formed first → high break" is 5-7% stronger** than reverse (73% vs 67%)
- Narrow ORs (<0.2%) have weak prediction (55-66%)
- 15-min gives strongest signal; use for direction, 30-min for levels

### Prop Firm Viability (v5)

| Config | Trades/Year | Max DD | Survives $2K? |
|---|---|---|---|
| NQ1 + IB Bias | 5.6 | $778 | **Yes** |
| ES1 + IB Bias | 4.4 | $514 | **Yes** |
| **NQ1+ES1 Combined** | **10.0** | **$731** | **Yes** |

---

## v6 Zone Architecture — Diagnosis & Fix Plan

### What v6 Tried To Do

Replace event-based entries with zone-based entries. Instead of entering on the CHOCH bar itself, build a zone at the CHOCH level and enter on the pullback to that zone. This should give better entries (deeper into the range = better R:R) and catch setups that form during the OR period.

### What Went Wrong

**Zones never expire.** A CHOCH at 9:45 creates a zone that stays active all day. Price touching that level at 2:30 PM triggers an entry even though market structure has completely changed. Result: 7-9x more trades than v5, but 20pp lower win rate (43% vs 64%).

**Every zone type had the same problem:**
- CHOCH zones: stale after structure shifts again
- FVG zones: stale after being filled/mitigated
- OB zones: stale after being traded through
- Fib zones: less affected (they're static relative to OR) but still generated too many entries

### Specific Numbers

| Version | Trades | Win Rate | PF | Max DD |
|---|---|---|---|---|
| v5 CHOCH (IB) | 112 | 64.3% | 2.17 | $778 |
| v6 CHOCH (no IB) | 1,022 | 43.1% | 0.84 | $23,037 |
| v6 CHOCH (IB) | 712 | 43.1% | 0.82 | $16,181 |

### Required Fixes for v6

1. **Zone expiration:** Each zone valid for max N bars (e.g., 30 bars = 30 min on 1-min chart) after creation, then deactivated permanently.

2. **One-touch rule:** Once price enters a zone and triggers a trade (or is rejected by risk check), that zone is consumed and cannot trigger again. No second chances.

3. **Freshness requirement:** Only enter on the FIRST touch of a zone after the OR closes. Zones created during the OR should be valid for one pullback entry attempt only.

4. **Structure invalidation:** When a new CHOCH fires in the opposite direction, all previous CHOCH zones in the old direction must be invalidated. The market has changed its mind — old zones are obsolete.

5. **Zone count limit:** Maximum 1-2 active zones per direction at any time. If a new bullish zone is created when 2 bullish zones already exist, the oldest one expires.

6. **FVG mitigation:** Once an FVG is filled (price trades through it), the zone should deactivate. Currently FVG zones persist even after complete fill.

7. **OB mitigation:** Same — once an OB is traded through, deactivate the zone.

### How To Implement

In `scan_for_entries()`, add to each zone:
```python
@dataclass
class Zone:
    ...
    created_bar: int = 0       # bar index when zone was created
    max_life_bars: int = 30    # expire after this many bars
    touched: bool = False      # has price entered this zone?
    consumed: bool = False     # has this zone generated a trade attempt?
    invalidated: bool = False  # has opposite structure invalidated this?
```

Before checking each zone:
```python
# Skip expired zones
if (current_bar - z.created_bar) > z.max_life_bars:
    continue
if z.consumed or z.invalidated:
    continue
```

After a zone triggers (trade or rejection):
```python
z.consumed = True
```

When new CHOCH fires:
```python
for z in zones:
    if z.zone_type == "choch" and z.direction != new_choch_direction:
        z.invalidated = True
```

---

## Pine Script — OR Strategy Lab v4

**File:** `OR_Strategy_Lab_v4.pine`

### Features
- Strategy selector dropdown (7 strategies)
- **IB Bias detection** at configurable minute mark (default 15min)
- Structure detection from 9:30 (includes OR period)
- OR Box (blue=valid, red=filtered)
- Fib levels with labels (23.6%, 38.2% Discount, 50% EQ, 61.8% Premium, 78.6%)
- VWAP line (session-anchored, purple)
- Swing markers (triangles, post-9:30)
- CHOCH/BOS labels with "✓" when OR swept
- OR Sweep markers (orange "SWEEP↑/↓")
- FVG boxes (green/red)
- OB boxes (teal/maroon)
- TP/SL lines with % labels
- Entry labels with strategy, direction, E/SL/TP, R:R, IB bias
- Rejection labels (yellow, shows why setup was rejected)
- IB Bias arrow at detection mark
- Dashboard: OR range, IB bias, VWAP, swings, structure, sweep status, position, trades, rejection reason

### Pine Script Design Notes
- All visuals use `line.new()`/`box.new()`/`label.new()` — no `plot()` for levels
- Historical objects never deleted (scroll history preserved)
- `var` references track current day's objects for updating
- Structure detection matches Python: `ta.pivothigh`/`ta.pivotlow` from 9:30, HH/HL/LH/LL trend state, level consumption after break
- CHOCH requires OR sweep verification
- One signal per day (`signalFired` flag)
- All values in price percentage
- One known indentation error was fixed manually by user

---

## Known Bugs

1. **PDH/PDL key level detection** (Script 03): Shows 0% break-through. Proximity logic flaw — needs approach-direction redesign.
2. **Friday missing from weekly extremes** (Script 05): `daily_levels.csv` drops Friday data.
3. **Closing Half Rule ~0%** (Script 08): Boolean averaging bug. Core IB bias results unaffected.
4. **v6 zone expiration** (signal_generators.py v6): Zones never expire, causing stale entries. See fix plan above.

---

## What We've Proven (Statistically Validated)

1. **Judas swing is real** — 25% of days, low breaks first 44% of the time
2. **CHOCH Fade is the only profitable entry** — 2.17 PF, 64.3% WR (v5 with IB bias)
3. **IB bias ("which side formed first") = 70-71% accurate** — strongest at 15min, wider ORs
4. **"Low formed first" is more reliable** — 73% vs 67% for "high formed first"
5. **London sweep predicts NY reversal 69-72%** — when single side swept
6. **Monday sets week's low 35%** — strongest day-of-week pattern
7. **Gaps fill 100%** — every gap, every size, 20 years
8. **Macro windows NOT more directional** — slightly more volatile, same displacement
9. **Thursday does NOT reverse Wednesday** — 50.5% = coin flip
10. **ONH/ONL are continuation levels** — 82-95% break-through rate

---

## Next Steps (Priority Order)

### Immediate: Fix v6 Zone Expiration
- Add zone expiration (30 bars), one-touch rule, structure invalidation
- Re-run comparison to see if zone-based entries with proper expiration beat v5
- This is the most impactful change — it could unlock the OR-internal structure edge

### If v6 Fixed Works: Prop Sim
- Run Study 06 Monte Carlo with the best v6 configuration
- Verify MaxDD < $2,000 across 1,000 permutations
- Test both MNQ and MES sizing

### If v6 Fixed Doesn't Work: Optimize v5
- Parameter sensitivity: swing lookback (2,3,4,5), R:R (1:1, 1.5:1, 2:1), max risk %
- Add London sweep as additional filter on top of IB bias
- Explore loosening CHOCH detection to increase trade frequency

### Then: Walk-Forward Testing
- Split 20 years: train 2yr, test 6mo, slide forward
- Verify edge persists out-of-sample
- Identify parameter overfitting

### Then: Build NinjaScript Bot
- Convert validated strategy to C# NinjaScript
- Strategy Analyzer backtesting
- Market Replay testing
- Sim trade 30+ signals
- Go live on prop firm eval

### Then: Multi-Instrument
- Run on NQ + ES simultaneously (~10 trades/year combined)
- Evaluate RTY, YM, CL, GC
- Portfolio-level drawdown analysis

---

## Technical Notes

### Date Matching
All scripts use `normalize_trade_date()` converting to `YYYY-MM-DD` strings. `load_derived()` forces `pd.to_datetime(df.index, utc=True).tz_convert("US/Eastern")` for `_1min` files.

### Percentage Normalization
All risk management uses % of price: OR width filter (0.05-0.50%), max risk (0.15-0.20%), stop buffer (0.03%), IB bias min width (0.20%). This ensures regime independence across NQ 2,000 (2006) to 22,000 (2025).

### Performance
Studies process ~5,000 days. Scripts use NumPy vectorized ops where possible. Strategy comparison with 7 strategies takes ~5-10 minutes locally.

### Configuration
- Input: `--input-dir "C:\Users\vinay\tvDownloadOHLC\data"`
- Parquet naming: `{SYMBOL}1_1m.parquet`
- Raw timezone: UTC
- OR durations: configurable, default [5, 15, 30, 45, 60]
- IB bias: `--use-ib-bias --ib-bias-minutes 15 --ib-min-width-pct 0.20`

### File Versions
- `strategy_v5_ib_bias.tar.gz` — **CURRENT BEST** (event-based + IB bias)
- `strategy_v6_zones.tar.gz` — Zone-based (BROKEN, needs expiration fix)
- `OR_Strategy_Lab_v4.pine` — **CURRENT Pine Script** (IB bias + full structure)
