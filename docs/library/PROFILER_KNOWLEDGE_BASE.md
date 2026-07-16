# Daily Profiler — Knowledge Base

> **Status:** Documented from PineScript source + architecture docs + Boot Camp material
> **Date:** 2026-07-13
> **Related:** Profiler module (`scripts/trader/signals/profiler.py`), PineScript (`scripts/indicators-pine/profiler/`)

---

## 1. Core Philosophy — The "08-12" Session Box System

The Profiler tracks 4 time-based "Session Boxes" and classifies how price interacts with each. It does NOT use daily classifications (R1/R2). Instead it focuses on the **structural outcome** of key trading sessions.

### Trading Day Definition
- **Start**: 18:00 ET (previous calendar day, Globex open)
- **End**: 17:00 ET (current calendar day)
- **Anchor**: All calculations anchored to 18:00 ET

### Session Definitions (ET)

| Session | Classification Window (box H/L set) | Full Session Window (status determined) | Broken Window |
|---|---|---|---|
| **Asia** | 18:00-19:29 | 19:30-02:29 | 02:30-17:00 |
| **London** | 02:30-03:29 | 03:30-07:29 | 07:30-17:00 |
| **NY1** | 07:30-08:29 | 08:30-11:29 | 11:30-17:00 |
| **NY2** | 11:30-12:29 | 12:30-15:59 | 16:00-17:00 |

- **Mid** = `(Session High + Session Low) / 2`

> **PineScript Bug (fixed 2026-07-13):** The `time()` function treats session end time as **EXCLUSIVE** (half-open interval `[start, end)`). The original session strings used `end_time` as the last intended minute (e.g., `"1800-1929"`), which excluded the last bar (19:29). Fixed by using `end_time + 1` (e.g., `"1800-1930"`). This applies to all classification, full session, broken, play, fin_, P12, and NY P12 windows.

---

## 2. Status Logic (The Play-Out)

Status is determined by price action **after** the classification window ends, during the full session window. It assesses which range boundary broke first and whether the opposite side held.

### Status Codes (numeric, from PineScript `f_calc_status`)

| Code | Status | Meaning | Can it change? |
|---|---|---|---|
| 0 | None/Neutral | Not started or inside range | Yes → 1, 2, 3 |
| 1 | Long True (LT) | Broke High, never broke Low | PENDING → can flip to 2 |
| 2 | Long False (LF) | Broke High first, then broke Low (fakeout) | FINAL |
| 3 | Short True (ST) | Broke Low, never broke High | PENDING → can flip to 4 |
| 4 | Short False (SF) | Broke Low first, then broke High (fakeout) | FINAL |

### How Status Evolves (from `f_calc_status`)
```
mode == 0 (neutral):
  if break_high AND NOT break_low → mode = 1 (LT pending)
  elif break_low AND NOT break_high → mode = 3 (ST pending)
  elif break_high AND break_low → mode = 2 (LF — high first then low)

mode == 1 (LT pending):
  if break_low → mode = 2 (LF — the low broke, so it was a fakeout)

mode == 3 (ST pending):
  if break_high → mode = 4 (SF — the high broke, so it was a fakeout)
```

**Key insight**: "True" is only confirmed when the play window ends without the opposite side breaking. The status determination is **sequential** — whichever side breaks first determines the initial direction, then if the other side breaks later, it becomes False.

### Display Strings (from `f_status_str`)
- Code 1 + active → "Long (Pend)" or "Long True" if confirmed
- Code 2 → "Long False"
- Code 3 + active → "Short (Pend)" or "Short True" if confirmed
- Code 4 → "Short False"
- If broken → append " (BK)"

---

## 3. Broken Logic

The "Broken" status checks if price **retraces to the session midpoint** during the broken window (after the next session starts).

- **Broken (Yes)**: Session Mid `(H+L)/2` is touched or crossed during the broken window
- **Held (No)**: Session Mid is respected (not touched)
- **One-way**: Once broken, it stays broken — there's no "un-breaking"
- **Timing**: A session cannot be broken by price within its own evaluation window. The check starts strictly after the next session begins.

### Broken Windows
- Asia: 02:30 → 17:00 (starts when London session begins)
- London: 07:30 → 17:00 (starts when NY1 begins)
- NY1: 11:30 → 17:00 (starts when NY2 begins)
- NY2: 16:00 → 17:00 (brief window at end of day)

### `f_check_broken` Logic (from PineScript)
```
if NOT already broken AND in broken window AND H and L are valid:
  mid = (H + L) / 2
  if low <= mid AND high >= mid:  # bar's range crosses the mid
    broken = true
```

---

## 4. Reference Levels

### Level Definitions & Time Windows

| Level | Definition | Established | Valid Touch Window | Chart Start |
|---|---|---|---|---|
| PDH | Previous Day High | 18:00 | 18:00-17:00 | 18:00 |
| PDL | Previous Day Low | 18:00 | 18:00-17:00 | 18:00 |
| PDM | Previous Day Mid | 18:00 | 18:00-17:00 | 18:00 |
| P12 High | Overnight High (18:00-06:00) | 06:00 | 06:00-17:00 | 06:00 |
| P12 Low | Overnight Low (18:00-06:00) | 06:00 | 06:00-17:00 | 06:00 |
| P12 Mid | Overnight Midpoint | 06:00 | 06:00-17:00 | 06:00 |
| Daily Open | Globex Open (18:00) | 18:00 | 18:00-17:00 | 18:00 |
| Midnight Open | 00:00 price | 00:00 | 00:00-17:00 | 00:00 |
| 07:30 Open | Pre-Market Open | 07:30 | 07:30-17:00 | 07:30 |
| NY P12 H/M/L | Previous day's 06:00-17:59 range | 18:00 | 18:00-17:00 | 18:00 |
| Asia Mid | Asia session midpoint | 02:00 | 02:00-17:00 | 02:00 |
| London Mid | London session midpoint | 07:00 | 07:00-17:00 | 07:00 |
| NY1 Mid | NY1 session midpoint | 12:00 | 12:00-17:00 | 12:00 |
| NY2 Mid | NY2 session midpoint | 16:00 | (removed from UI) | 16:00 |

### Cross-Session "Prev" Mids
To avoid lookahead bias, earlier sessions analyze their relationship to the **previous day's** session mids until the current day's mids are formed.

### Level Availability by Session
- Asia: PDH, PDL, PDM, Globex Open, Prev NY P12 (no Midnight, no P12, no session mids)
- London: All Asia's + Midnight, Asia Mid (no 07:30, no P12, no London Mid)
- NY1: All London's + 07:30, P12, London Mid (no NY1 Mid)
- NY2: All NY1's + NY1 Mid (no NY2 Mid — forms during NY2 itself)

---

## 5. Auto-Filter Logic (The Prediction Engine)

### Auto Target Detection (`tgt_idx`)

The PineScript auto-detects which session to predict next based on time:

| Current Time (ET) | tgt_idx | Predicting |
|---|---|---|
| Before 02:30 | 0 | Asia |
| 02:30 - 07:29 | 1 | London |
| 07:30 - 11:29 | 2 | NY1 |
| 11:30 - 16:14 | 3 | NY2 |
| 16:15+ | 0 | Next day Asia |

### Context Dependency Chain

| Target Session | Context Filter (from `PROFILER_ARCHITECTURE.md §6`) |
|---|---|
| Asia | prev NY1 + prev NY2 |
| London | curr Asia + prev NY2 |
| NY1 | curr Asia + curr London |
| NY2 | curr Asia + curr London + curr NY1 |

### `f_match` — The Filter Function

This is the core matching logic that determines whether a historical day matches the current live signature:

```
f_match(hc, hb, lc, lb, loose, ignore_bk):
  Status matching:
    - lc == 0 (no filter) → always matches
    - loose mode: lc==1 matches hc==1 OR hc==2 (pending Long can become LF)
                  lc==3 matches hc==3 OR hc==4 (pending Short can become SF)
    - strict mode: hc == lc (exact match)
  Broken matching (ASYMMETRIC):
    - If live NOT broken (lb=false) → match any historical (both broken and held)
    - If live IS broken (lb=true) → historical MUST also be broken (hb==1)
```

**Why asymmetric?** A held session is a stronger structural signal. A broken session doesn't filter out held historical days — because the broken state is less informative (the range failed, so it's a weaker constraint).

### The Filter Loop (Intersection)

For each historical day, the PineScript checks:
1. If predicting London (tgt_idx=1): does Asia match? (status + broken via `f_match`)
2. If predicting NY1 (tgt_idx=2): do Asia AND London match?
3. If predicting NY2 (tgt_idx=3): do Asia, London, AND NY1 match?
4. For Asia/London predictions: also check prev NY1 and prev NY2 context

For matching days, tally:
- Outcome distribution (LT/LF/ST/SF counts → probabilities)
- HOD/LOD times and % excursions → price model paths
- Level touch counts per outcome → conditional level hit rates

### Hierarchical Fallback (S3 Architecture)
- Level 1: Full context (all predecessor directions)
- Level 2: Single closest predecessor fallback
- Level 3: Baseline (no context filter)
- Minimum sample size: N ≥ 30

---

## 6. Session Independence (Reset Flag Logic)

The probability of a level being hit is calculated **independently** for each session. A hit in Asia does NOT preclude a hit in London. The "Hit Flag" is reset at the start of each session's play window.

- **Granularity**: 5-minute distinct buckets for storage
- **Precision**: Zero tolerance — `Bar Low <= Level <= Bar High` (a miss by 1 tick is a miss)
- **Uniqueness**: Only the **First Hit** per session counts toward probability

---

## 7. P12 Scenario Classification (06:00-08:30 ET)

The 06:00-08:30 window is the **first quarter** of the 12-hour cycle (06:00-18:00). Price action around P12 levels during this window provides clues about the expected market behavior.

| # | Scenario | Price Action | Implication |
|---|---|---|---|
| 1 | P12 Mid Rejection | Tests P12 Mid and rejects, or looks below/above and finds footing | Directional move likely. MAE already completed (shallow). |
| 2 | Look Outside and Return | Moves outside P12 H/L but returns to P12 Mid | True NY1 direction likely (trend continuation). |
| 3 | Mid-Range Consolidation | Ranges between P12 Mid and one extreme, eventual breakout | Watch for 09:30-10:15 reversal. Range set up for break. |
| 4 | Look and Stay Outside | Moves outside P12 and fails to return to Mid | P12 acting as strong S/R. Market committed. |
| 5 | Swipe Both Sides / Mid Engagement | Touches both P12 H and L, or heavily engages Mid | Expect Range One day (tight range). |

**Key question**: Has the MAE (wick) already been put in during 06:00-08:30, or is the major pivot yet to come at 09:30-10:15?

---

## 8. HOD/LOD Timing Assessment

Based on 20-year statistical data for index HOD/LOD timing:

| Time Window | Probability | Frequency | Notes |
|---|---|---|---|
| 09:30-09:45 | **Highest** | 2-3x/week | Four Step Reversal confirmation |
| 09:45-10:00 | 2nd Highest | 1-2x/week | "9:45 reversal" |
| 10:00-10:15 | Moderate | 1-2x/2 weeks | Drop-off after 10:00 |
| 10:15-10:30 | Lowest | 1-2x/month | Rare |
| 16:10-16:25 | HOD mode (indexes) | Frequent | End-of-day close push |

Secondary windows: London open (02:30-03:30), NY1 pre-market (07:30-08:30), NY2 open (11:30-12:30), late session (15:00-16:00).

---

## 9. Overnight Direction Combinations (Boot Camp Week 2 Day 5)

### Trending Combinations (Bullish Examples)

| Asia / London | Asia OU Break (mode) | London OU Break (mode) | 18:00 LOD Support | NY1 Expectation |
|---|---|---|---|---|
| LT / SF | 75% (9:30-9:45) | 80% (7:45-8:30) | ✓ | Best for hitting Asia OU during NY1 |
| LT / LT | 59% (02:30) | 73% (9:30-9:45) | ✓ | Lower prob of Asia OU break |
| SF / LT | 76% (10:00) | 75% (9:30) | ✓ | — |
| SF / SF (Firecracker) | 91% (02:30-03:30) | 86% (7:30-9:45) | ✗ NO | Crashes through P12, new LOD even in bullish trend |

### Contradicting Markets (Asia and London disagree)
- Market ranged overnight
- Both OU likely broken ("broken broken")
- LOD/HOD more likely after RTH open
- NY1: range-bound, focus on 9:45/four-step reversal
- Use range/cash-flow systems, not trend systems

---

## 10. Data Architecture

### Source Files (all in `data/`)
| File | Content | Used For |
|---|---|---|
| `{ticker}_profiler.json` | Full session records (20+ years, ~5000 days) | Status, broken, range, times, excursions, historical filtering |
| `{ticker}_level_touches.json` | Per-day level touch data | Level prices, touch status, touch times, hit rate computation |
| `{ticker}_asia_predictions.json` | Precomputed: prev_ny1\|prev_ny2 → Asia | Fast lookup (NQ1 only) |
| `{ticker}_london_predictions.json` | Precomputed: prev_ny2\|curr_asia → London | Fast lookup (NQ1 only) |

### Profiler JSON Record Structure
```json
{
  "date": "2006-01-05",
  "session": "NY2",
  "open": 4799.5,
  "prior_close": 4799.0,
  "range_high": 4805.5,
  "range_low": 4798.5,
  "mid": 4802.0,
  "high_time": "12:02",
  "low_time": "11:30",
  "high_pct": 0.13,
  "low_pct": -0.02,
  "close_pct": 0.06,
  "status": "Short False",
  "status_time": "2006-01-05T16:14:00-05:00",
  "broken": false,
  "broken_time": null,
  "start_time": "2006-01-05T11:30:00-05:00",
  "start_ts": 1136478600,
  "end_time": "2006-01-05T12:30:00-05:00",
  "end_ts": 1136482200,
  "high_ts": 1136480520,
  "low_ts": 1136478600,
  "status_ts": 1136495640
}
```

### Level Touches Record Structure
```json
{
  "pdh": {"level": 30701.25, "touched": false, "touch_times": []},
  "p12m": {"level": 29738.62, "touched": true, "touch_times": ["20:07", "20:08", ...]}
}
```

---

## 11. PineScript Design (for reference)

### Architecture
- `ProfilerIndicator.pine` — main indicator with session boxes, stats table, reference levels, embedded price models
- `PriceModelIndicator.pine` — standalone contextual price model overlay with hierarchical fallback
- Data libraries: `ProfilerData_*.pine` (bit-packed arrays for sessions, broken, touches, context, models)

### Bit-Packing (15:1 ratio)
- Binary data (broken, touches): packed as bits in integers
- Codes (status): packed as 3-bit values in integers (base-8)
- Decompression: `math.floor(val / math.pow(base, pos)) % base`
- ~90% size reduction, allowing 15+ years of data

### Price Model Data
- 243 pre-computed contextual models as quantized integer strings
- Values × 1000 for ~40% size reduction
- 10-minute bucket resolution
- Hierarchical lookup: Level 1 (full context) → Level 2 (single predecessor) → Level 3 (baseline)

### Design Docs
- `scripts/indicators-pine/profiler/PROFILER_ARCHITECTURE.md`
- `scripts/indicators-pine/profiler/PROFILER_REQUIREMENTS.md`
- `docs/features/profiler/REQUIREMENTS.md`
- `docs/profiler/REQUIREMENTS.md`
- `docs/architecture/PROFILER_PREDICTION_ENGINE.md`
- `docs/architecture/PROFILER_DATA_DESIGN.md`