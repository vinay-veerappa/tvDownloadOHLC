# IB Strategy Data Gathering & Derived Data Plan

**Date:** 2026-07-24
**Goal:** Gather all possible data to test/validate IB strategies, create reusable derived data, and build a master confluence table for multi-strategy use.

---

## 1. Data Inventory — What Exists Today

### 1.1 IB-Specific Data (✅ Complete)

| Table | Location | Rows | Key Fields |
|---|---|---|---|
| `ib_facts_{SYM}.parquet` | `data/derived/` | 1 per day×session×time_basis | All §2 fields: range geometry, bias variants, play results, mid-lock, FVG timing, DST flags |
| `ib_ext_detail_{SYM}.parquet` | `data/derived/` | Long: per level×side | Extension hit bool + minutes for 0.25x-4x |
| `ib_play_detail_{SYM}.parquet` | `data/derived/` | Long: per play | result, MFE, MAE, realized_r, timeout_loss, loss_reason |
| `ib_level_touch_detail_{SYM}.parquet` | `data/derived/` | Long: per level×phase | Touch count, first/last touch time by phase |
| `ib_fvg_detail_{SYM}.parquet` | `data/derived/` | Per FVG event | (Deprecated v6, kept for backward compat) |

**Coverage:** 6 instruments (NQ1, ES1, YM1, RTY1, CL1, GC1), 6 sessions, 2 time_basis variants for Tokyo/London, ~20 years.

### 1.2 Daily Context Data (✅ Complete)

| Table | Key Fields |
|---|---|
| `daily_context_{SYM}.parquet` | VIX regime, ATR, gap stats, PDH/PDL, overnight range, first-hour direction, session direction, streak, event flags, OPEX week, weekly levels |
| `{SYM}_daily_classification.parquet` | `type` (R1/R2/DWP/DNP), `or_high`, `or_low`, `touches`, `broke`, `returned` |

### 1.3 Session/Profiler Data (✅ Complete)

| Table | Key Fields |
|---|---|
| `{SYM}_profiler_lookup.json` | Per-session status (LT/LF/ST/SF), broken, price stats, conditional probabilities |
| `NQ1_herman_stats.parquet` | Asia/London/NY session ranges, sweep flags, continuation signals |

### 1.4 Other Available Data

| Table | Key Fields |
|---|---|
| `{SYM}_features_1m.parquet` | 1m feature vectors (ICT features, etc.) |
| `fvg_detail.parquet` | All FVGs across all sessions |
| `gap_records.parquet` | Gap events |
| `macro_records.parquet` | Macro swing points |
| `range_records.parquet` | Range detection |
| `streak_records.parquet` | Directional streaks |
| `reference_levels.parquet` | Key reference levels |
| `hourly_quarter_stats_{SYM}.json` | Quarterly theory stats per hour |
| `volatility_stats.json` | Volatility distributions |
| `market_friction_matrix.parquet` | Friction metrics |
| `session_breakout_records.parquet` | Session breakout events |
| `daily_confluence_records.parquet` | Multi-signal confluence |
| `occ_records.parquet` | Order block / CISD events |

---

## 2. What's Missing — Data Gaps

### 2.1 🔴 CRITICAL: Aggregate Stats Tables (Spec-Defined, Not Built)

The `IB_STATS_PIPELINE_SPEC_v5.md` defines these aggregate tables in §3. They do NOT exist:

| Missing Table | What It Provides | Priority |
|---|---|---|
| `ib_agg_bias_compare.parquet` | Per-variant DIR%/HIT%/LIFT/N — which bias works best | P0 |
| `ib_agg_timing.parquet` | Mode/median break time, extension timing, mid-retest timing distributions | P0 |
| `ib_agg_extension_ladder.parquet` | Conditional P(hit L+0.5 \| hit L) | P0 |
| `ib_agg_plays_by_regime.parquet` | Play WR by range_bucket, VIX, DOW, bias agreement | P0 |
| `ib_agg_bias_conflict.parquet` | Pairwise conflict matrix — when biases disagree, who wins? | P1 |
| `ib_agg_no_signal.parquet` | Chop statistics for sparse variants | P1 |
| `ib_agg_dst_validation.parquet` | ET_fixed vs event_anchored comparison | P2 |

### 2.2 🔴 CRITICAL: Master Confluence Table (Does Not Exist)

No single table joins IB data with all other available signals. This is the #1 blocker for testing multi-signal strategies.

### 2.3 🟡 MISSING: IB-Specific Derived Fields (Not Computed)

| Field | Computation | Use |
|---|---|---|
| `ib_range_pct_of_daily` | IB range / eventual daily range | Day type prediction (trend vs range) |
| `ib_range_5d_contracting` | 5-day rolling IB range < 20th percentile | Pre-break anticipation |
| `ib_range_5d_expanding` | 5-day rolling IB range > 80th percentile | Volatility already priced in |
| `ib_high_touch_count` | How many bars touched IB high during formation | Level conviction |
| `ib_low_touch_count` | How many bars touched IB low during formation | Level conviction |
| `ib_poc_price` | Price with most TPOs during IB (Point of Control) | Market Profile fair value |
| `ib_vah` / `ib_val` | Value Area High/Low (70% of TPOs) | More meaningful than IB high/low |
| `ib_tpo_skew` | TPO distribution skew (top-heavy vs bottom-heavy) | Bias signal |
| `ib_open_drive_dir` | Direction of first 5 min of IB vs prior close | Opening auction signal |
| `ib_break_speed` | Points per minute of the first break | Momentum filter |
| `ib_vs_overnight_ratio` | IB range / overnight (18:00-9:30) range | RTH vs overnight dominance |
| `ib_inside_outside` | Inside/outside/overlapping vs prior day IB | Multi-day context |
| `ib_3day_composite_high` / `_low` | 3-day composite IB range | The "real" range |
| `ib_failure_mode` | Classification of each loss: fakeout/fade/chop/wrong_dir | Failure analysis |

### 2.4 🟡 MISSING: Cross-Strategy Confluence Fields

| Field | Source | What It Tells IB Strategy |
|---|---|---|
| `profiler_overnight_regime` | Profiler lookup | Trending vs contradicting overnight → IB breakout vs fade |
| `herman_asia_size` | Herman stats | Small Asia → trend; Large Asia → caution |
| `herman_pl_sweep` | Herman stats | Pre-London sweep → reversal or continuation signal |
| `herman_ny_am_sweep_london` | Herman stats | NY AM sweep of London → 64.5% bullish close |
| `daily_classification` | Daily classification | R1 → fade; DWP → retest; DNP → breakout |
| `hourly_quarter_mode` | Quarterly stats | 10:00 hour = Reversion → fade breakouts |
| `noon_curve_active` | SecondBrain rules | High set before 11:00 → new low after noon |
| `sdev_touch_level` | SDEV stats | 0.5/1.0/1.5 SD touch → reversion probability |
| `nine_am_candle_color` | Daily context | Green 9AM → 70.6% NY close green |
| `economic_event_today` | Calendar | Skip FOMC/NFP/CPI days |
| `opex_week` | Daily context | Options expiration → unusual behavior |

### 2.5 🟡 MISSING: News Timing Impact (9:45 & 10:00 AM)

Economic releases at 9:45 and 10:00 AM ET are the single biggest intraday volatility events. They directly affect IB timing, break quality, and extension probability:

| News Time | Typical Releases | Effect on IB |
|---|---|---|
| **9:45 AM** | S&P Global PMI (Manufacturing/Services/Composite) | Hits during IB formation (9:30-10:30). Can cause a sharp spike that sets the IB extreme prematurely, then reverses. The "news IB" has different statistical properties than a "clean IB" |
| **10:00 AM** | ISM Manufacturing/Services PMI, Consumer Confidence, ISM Prices | Hits at IB close or just after. Can cause an immediate break that looks like a valid breakout but is news-driven — different follow-through probability |
| **10:30 AM** | EIA Petroleum Status (Wednesdays), sometimes other releases | Hits exactly at IB close. Can cause a "gap break" that retraces |

**Data source: Prisma DB (`EconomicEvent` table)** — 11,684 events with UTC timestamps, name, impact level. Already loaded by `scripts/edgeful/lib/context.py` (`_load_events_by_date`). **Do NOT recreate this data.**

**Fields needed (computed from existing Prisma DB events):**

| Field | Computation | Use |
|---|---|---|
| `news_0945_today` | bool — any HIGH/MEDIUM event at 9:45 ET today (from Prisma DB) | Filter: skip or reduce size on news IB |
| `news_1000_today` | bool — any HIGH/MEDIUM event at 10:00 ET today | Filter: delay entry until 10:05 to let news settle |
| `news_1030_today` | bool — any HIGH/MEDIUM event at 10:30 ET today | Filter: IB close may be news-distorted |
| `news_impact_level` | "HIGH" / "MEDIUM" / "none" — highest impact among 9:45-10:30 events | Position sizing scalar |
| `news_release_name` | str — event name(s) at 9:45/10:00/10:30 | Context: ISM vs PMI vs Consumer Confidence |
| `ib_news_distorted` | bool — did a 9:45 release occur during IB formation? | Separate analysis: "clean IB" vs "news IB" stats |
| `ib_news_break` | bool — did first break occur within 2 min of a 10:00/10:30 release? | These breaks have different follow-through |
| `minutes_since_news` | Minutes from last 9:45/10:00/10:30 release to first break | Timing filter: wait N minutes after news |

### 2.6 🟡 MISSING: OPEX Week Effects

Options expiration (OPEX) — typically the 3rd Friday of each month, plus the week leading up to it — has measurable effects on IB behavior:

| OPEX Effect | Mechanism | Expected Impact on IB |
|---|---|---|
| **Pin risk** | Market makers hedge delta near large open interest strikes | IB range compresses toward strike clusters |
| **Gamma effects** | Dealers long gamma suppress volatility; short gamma amplify it | IB range can be artificially small or large |
| **Quarterly OPEX** (Mar/Jun/Sep/Dec) | Triple witching — futures, options, index options all expire | Largest distortion; IB stats from these weeks should be analyzed separately |
| **Monthly OPEX** | Standard monthly expiration | Moderate distortion |
| **OPEX Friday** | Expiration day itself | Often range-bound until afternoon, then volatile into close |
| **OPEX week (Mon-Thu)** | Week leading up to expiration | Range compression, then expansion on Friday |

**Fields needed:**

| Field | Computation | Use |
|---|---|---|
| `is_opex_week` | bool — already in `daily_context` | Filter: separate OPEX stats from non-OPEX |
| `is_opex_friday` | bool — is today OPEX Friday? | Filter: different play selection |
| `is_quarterly_opex` | bool — is this a triple-witching expiration? | Filter: highest distortion, consider skipping |
| `days_to_opex` | int — days until next OPEX Friday (negative = days since) | Regime: compression vs expansion phase |
| `opex_phase` | "pre_opex" / "opex_week" / "opex_friday" / "post_opex" / "normal" | Regime selector for play/position sizing |
| `opex_ib_range_pctile` | IB range as percentile within OPEX-week distribution | Normalize: is this a "large" IB for OPEX standards? |

### 2.7 ✅ CONFIRMED: SDEV Fields (Already Computable)

SDEVs are the **standard deviation of price for each range** — computed from the session open. Per SecondBrain §4.3, SDEVs are measured from the **08:00 ET open**:

- **0.5 SD**: 69% reversion probability
- **1.0 SD**: 84% reversion (strong edge)
- **1.5 SD**: 93% reversion

**Fields needed:**

| Field | Computation | Use |
|---|---|---|
| `sdev_base_time` | 08:00 ET (configurable) | Anchor for SDEV computation |
| `sdev_05_price` | open_0800 + 0.5 × rolling_stdev | Upper reversion level |
| `sdev_10_price` | open_0800 + 1.0 × rolling_stdev | Strong reversion level |
| `sdev_15_price` | open_0800 + 1.5 × rolling_stdev | Extreme reversion level |
| `sdev_05_touched` | bool — did price touch 0.5 SD in outcome window? | 69% reversion edge |
| `sdev_10_touched` | bool — did price touch 1.0 SD? | 84% reversion edge |
| `sdev_15_touched` | bool — did price touch 1.5 SD? | 93% reversion edge |
| `sdev_direction` | +1 if price above open (positive SD), -1 if below | Which side SD was touched |

**Computation:** Rolling stdev of 1m closes from 08:00 anchor, projected as price levels. Computed in Phase 2.6 alongside AVWAP.

### 2.8 ✅ CONFIRMED: SecondBrain Rule Fields (Already Computable)

These fields map to existing data or are simple computations from 1m bars:

| Field | Source | Computation |
|---|---|---|
| `sb_nine_am_candle_green` | `daily_context.first_hour_direction` | `first_hour_direction == 'GREEN'` (already computed) |
| `sb_noon_curve_active` | `ib_facts` | `first_break_dir == 1 AND first_break_minutes < 90` → high set before 11:00 |
| `sb_ib_midpoint_bias` | `ib_facts` | `ib_close > ib_mid` → upper 50% close → 82.3% high break |

No new computation needed — these are derived from existing fields in the master confluence join.

### 2.9 🟡 MISSING: Custom-Anchor VWAP & Trend Confirmations

A VWAP anchored at a user-specified time (e.g., IB start at 9:30) provides a dynamic trend filter that evolves throughout the session. Unlike a fixed IB mid, the anchored VWAP (AVWAP) moves with price and volume, giving real-time trend confirmation.

**Core concept:** Price above AVWAP = bullish trend intact; price below = bearish. The relationship between price and AVWAP at the time of an IB break is a powerful confluence filter.

**Fields needed (per custom anchor time T):**

| Field | Computation | Use |
|---|---|---|
| `avwap_{T}_price` | Anchored VWAP from time T to current bar (cumulative) | Trend direction: price > AVWAP = bullish |
| `avwap_{T}_deviation_pct` | (close - AVWAP) / AVWAP × 100 at IB close | How far is price from fair value? |
| `avwap_{T}_slope` | AVWAP slope over last 15 min of IB | Is the trend accelerating or decelerating? |
| `avwap_{T}_above_count` | Number of 1m bars above AVWAP during IB | Trend consistency: >80% = strong trend |
| `avwap_{T}_below_count` | Number of 1m bars below AVWAP during IB | Same for bearish |
| `avwap_{T}_touch_count` | How many times price touched AVWAP during IB | AVWAP as support/resistance quality |
| `avwap_{T}_break_direction` | At first break time, is price above or below AVWAP? | Confluence: break direction = AVWAP direction → higher conviction |
| `avwap_{T}_distance_at_break` | Distance from break price to AVWAP in % | How extended is price from fair value at entry? |
| `avwap_{T}_std_upper` / `_lower` | AVWAP ± 1σ / 2σ bands (rolling stdev of price from AVWAP) | Dynamic support/resistance levels |

**Default anchor times to precompute:**

| Anchor | Label | Purpose |
|---|---|---|
| 09:30 ET | `avwap_0930` | IB start — the primary trend filter for all IB plays |
| 18:00 ET | `avwap_1800` | Globex open — overnight trend filter |
| 00:00 ET | `avwap_0000` | Midnight — ICT midnight open trend |
| 08:00 ET | `avwap_0800` | Pre-market open — NY pre-market trend |
| 09:00 ET | `avwap_0900` | 9AM hour start — 1H continuation signal anchor |
| 10:00 ET | `avwap_1000` | Post-IB — trend after IB close |
| 13:30 ET | `avwap_1330` | NY PM IB start — afternoon trend |

**Additional simple trend confirmations (non-VWAP):**

| Field | Computation | Use |
|---|---|---|
| `ema_20_vs_ema_50` | EMA20 > EMA50 at IB close? | Simple trend direction |
| `ema_slope_20` | Slope of EMA20 over last 10 bars of IB | Trend strength |
| `higher_highs_ib` | Did IB make at least 2 higher highs AND higher lows? | Uptrend structure within IB |
| `lower_lows_ib` | Did IB make at least 2 lower lows AND lower highs? | Downtrend structure within IB |
| `ib_close_vs_avwap` | IB close relative to AVWAP(09:30) | Final trend verdict at IB close |
| `break_vs_avwap` | Break direction vs AVWAP direction | Confluence: agree = +1, disagree = -1 |
| `avwap_confluence_score` | 0-3: AVWAP(09:30) + AVWAP(18:00) + AVWAP(00:00) all agree? | Multi-timeframe trend alignment |

---

## 3. Implementation Plan

### Phase 1: Aggregate Stats Builder (P0 — 2 days)

**Script:** `scripts/edgeful/ib_aggregates.py`

Reads existing `ib_facts_*.parquet` + `ib_play_detail_*.parquet` + `ib_ext_detail_*.parquet` and produces:

```
data/derived/
├── ib_agg_bias_compare.parquet      # Per variant: DIR%, HIT% at 0.25/0.5/0.75/1x, LIFT, N
├── ib_agg_timing.parquet             # Per session: mode break bucket, median break min,
│                                     #   median time to 0.5x/1x/1.5x ext, mid-retest timing
├── ib_agg_extension_ladder.parquet   # Per level: P(hit L+0.5 | hit L), N
├── ib_agg_plays_by_regime.parquet    # Per play × range_bucket × VIX × DOW: WR, expectancy, N
├── ib_agg_bias_conflict.parquet      # Pairwise: N_conflict, winA%, winB%, winner, edge
└── ib_agg_no_signal.parquet          # Per sparse variant: N_absent, chop_rate
```

**Key design decisions:**
- All % cells include N so significance can be assessed
- Traffic-light coloring: ≥60% green, 50-60% orange, <50% red
- `range_bucket` and `vix_bucket` use **trailing** cutpoints for SUGGESTED, **full-sample** for descriptive tables
- Bias comparison uses empirical baselines (not fixed 50%)
- **All timing measurements are reported in 5-minute buckets.** Raw minute columns remain in `ib_facts_*.parquet` for diagnostics, but aggregate tables and strategy inputs use `first_break_minutes_5min`, `mid_retest_minutes_5min`, `gap_fill_minutes_5min`, extension `minutes_5min`, and 5-minute clock buckets. This aligns entries/exits to the bar grid and makes timing probabilities directly actionable.

### Phase 2: IB Derived Fields Builder (P0 — 2 days)

**Script:** `scripts/edgeful/ib_derived_fields.py`

Adds new columns to `ib_facts_*.parquet` (or creates a companion `ib_derived_{SYM}.parquet`):

```python
# New fields to compute:
DERIVED_FIELDS = {
    # Market Profile / TPO-based
    'ib_poc_price': 'Price with most 1m bars during IB',
    'ib_vah': 'Value Area High — upper bound of 70% TPO zone',
    'ib_val': 'Value Area Low — lower bound of 70% TPO zone',
    'ib_tpo_skew': '+1 if TPOs concentrated in upper 50%, -1 if lower, 0 if balanced',
    'ib_high_touch_count': 'Number of 1m bars that touched ib_high during formation',
    'ib_low_touch_count': 'Number of 1m bars that touched ib_low during formation',
    
    # Multi-day context
    'ib_range_pct_of_daily': 'ib_range / (daily_high - daily_low) * 100',
    'ib_range_5d_contracting': '5d rolling ib_range < 20th pctile of 60d',
    'ib_range_5d_expanding': '5d rolling ib_range > 80th pctile of 60d',
    'ib_vs_overnight_ratio': 'ib_range / overnight_range',
    'ib_inside_outside': '"inside" | "outside" | "overlapping" vs prior day IB',
    'ib_3day_composite_high': 'max(ib_high) over last 3 days',
    'ib_3day_composite_low': 'min(ib_low) over last 3 days',
    
    # Break characteristics
    'ib_break_speed': 'range_pts / first_break_minutes_5min (pts/min)',
    'ib_open_drive_dir': '+1 if 9:30-9:35 range entirely above prior close, -1 if below, 0 if straddles',
    'first_break_minutes_5min': 'floor(first_break_minutes / 5) * 5',
    'mid_retest_minutes_5min': 'floor(mid_retest_minutes / 5) * 5',
    'gap_fill_minutes_5min': 'floor(gap_fill_minutes / 5) * 5',
    'ext_minutes_5min': 'floor(extension minutes / 5) * 5',
    
    # Failure classification
    'ib_failure_mode_play1': '"fakeout" | "fade" | "chop" | "wrong_dir" | "none"',
    'ib_failure_mode_play2': '...',
    'ib_failure_mode_play3': '...',
}
```

**Failure mode classification logic:**
```python
def classify_failure(row, play_n):
    if row[f'play{play_n}_result'] != -1:
        return 'none'
    if row['false_break_high'] or row['false_break_low']:
        return 'fakeout'
    if row['retrace_depth_pct'] > 50:
        return 'fade'
    if row[f'play{play_n}_timeout_loss']:
        return 'chop'
    return 'wrong_dir'
```

### Phase 2.5: News & OPEX Impact Builder (P0 — 1 day)

**Script:** `scripts/edgeful/ib_news_opex.py`

**Inputs:**
- Economic calendar CSV (manually curated or scraped from Investing.com/ForexFactory)
- OPEX calendar (3rd Friday rule + holiday adjustments)
- Existing `ib_facts_*.parquet`

**Output:** `data/derived/ib_news_opex_{SYM}.parquet` — one row per `(symbol, trading_day, session_slot)`

```python
NEWS_OPEX_FIELDS = {
    # ── News Timing ──
    'news_0945_today': 'bool — 9:45 AM economic release today?',
    'news_1000_today': 'bool — 10:00 AM economic release today?',
    'news_1030_today': 'bool — 10:30 AM economic release today?',
    'news_impact_level': '"high" | "medium" | "low" | "none"',
    'news_release_name': 'str — e.g. "ISM Manufacturing", "PMI", "Consumer Confidence"',
    'ib_news_distorted': 'bool — did a 9:45 release occur during IB formation?',
    'ib_news_break': 'bool — did first break occur within 2 min of 10:00/10:30 release?',
    'minutes_since_news': 'int — minutes from last news release to first break (null if no news)',
    
    # ── OPEX ──
    'is_opex_week': 'bool — already in daily_context, promoted here',
    'is_opex_friday': 'bool — is today the expiration Friday?',
    'is_quarterly_opex': 'bool — triple witching (Mar/Jun/Sep/Dec)?',
    'days_to_opex': 'int — trading days until next OPEX Friday (negative = days since)',
    'opex_phase': '"pre_opex" | "opex_week" | "opex_friday" | "post_opex" | "normal"',
    'opex_ib_range_pctile': 'float — IB range as percentile within OPEX-week distribution',
}
```

**News data source:** Query the existing Prisma DB (`web/prisma/dev.db`) `EconomicEvent` table (11,684 events with UTC timestamps, name, impact level). Filter for HIGH/MEDIUM events between 9:45-10:30 ET. The `datetime` column is UTC epoch milliseconds; convert to ET and group by trading date. Reuse the existing `_load_events_by_date` logic in `scripts/edgeful/lib/context.py`. **Do NOT recreate this data.**

**OPEX calendar logic:** Reuse `scripts/edgeful/calendar_generator.py` which already computes `is_monthly_opex`, `is_quarterly_opex`, `is_opex_week`, `is_opex_minus_1`, `days_to_monthly_opex`. Extend with `is_opex_friday` and `opex_phase` fields.
    """Standard US equity options expire on the 3rd Friday of each month.
    If Friday is a holiday, expiration moves to Thursday."""
    # Reuse calendar_generator.py logic (already computes this)
    # Generate all 3rd Fridays
    # Adjust for NYSE holidays (Good Friday, etc.)
    # Tag quarterly (Mar, Jun, Sep, Dec) as triple witching
    # Add: is_opex_friday, opex_phase
```

### Phase 2.6: Custom-Anchor VWAP & Trend Builder (P0 — 2 days)

**Script:** `scripts/edgeful/ib_avwap_trend.py`

**Core library:** `scripts/libs_py/avwap.py` — reusable anchored VWAP computation

```python
# scripts/libs_py/avwap.py
def compute_anchored_vwap(df_1m: pd.DataFrame, anchor_time: time, 
                          anchor_session: str = 'NY AM IB') -> pd.DataFrame:
    """
    Compute anchored VWAP from a custom start time, resetting each trading day.
    
    Args:
        df_1m: 1-minute OHLCV data with DatetimeIndex (ET)
        anchor_time: e.g., time(9, 30) for IB start
        anchor_session: session label for column naming
    
    Returns DataFrame with columns:
        avwap_{session}_price: cumulative VWAP from anchor
        avwap_{session}_std_upper: +1σ band
        avwap_{session}_std_lower: -1σ band
        avwap_{session}_std2_upper: +2σ band
        avwap_{session}_std2_lower: -2σ band
    """
    # Vectorized: cumulative (price * volume) / cumulative volume
    # Reset at each anchor_time crossing
    # Compute rolling stdev of price deviation from VWAP for bands
```

**Precomputed anchors (stored in `ib_derived_{SYM}.parquet`):**

| Anchor | Column Prefix | Purpose |
|---|---|---|
| 09:30 ET | `avwap_0930` | IB start — primary trend filter |
| 18:00 ET | `avwap_1800` | Globex open — overnight trend |
| 00:00 ET | `avwap_0000` | Midnight — ICT midnight open |
| 08:00 ET | `avwap_0800` | Pre-market open |
| 09:00 ET | `avwap_0900` | 9AM hour start |
| 10:00 ET | `avwap_1000` | Post-IB trend |
| 13:30 ET | `avwap_1330` | NY PM IB start |

For each anchor, compute these **snapshot fields at IB close** (10:30 ET):

```python
AVWAP_SNAPSHOT_FIELDS = {
    f'avwap_{anchor}_price': 'AVWAP price at IB close',
    f'avwap_{anchor}_deviation_pct': '(close - AVWAP) / AVWAP × 100 at IB close',
    f'avwap_{anchor}_slope': 'AVWAP slope over last 15 min of IB (pts/min)',
    f'avwap_{anchor}_above_count': 'Number of 1m bars above AVWAP during IB',
    f'avwap_{anchor}_below_count': 'Number of 1m bars below AVWAP during IB',
    f'avwap_{anchor}_touch_count': 'How many times price touched AVWAP during IB',
    f'avwap_{anchor}_std_upper': '+1σ band at IB close',
    f'avwap_{anchor}_std_lower': '-1σ band at IB close',
}
```

Plus **break-time fields** (at the moment of first break):

```python
AVWAP_BREAK_FIELDS = {
    f'avwap_{anchor}_break_direction': '+1 if break price > AVWAP, -1 if below, 0 if at',
    f'avwap_{anchor}_distance_at_break_pct': 'abs(break_price - AVWAP) / AVWAP × 100',
}
```

**Simple trend confirmations (non-VWAP):**

```python
TREND_FIELDS = {
    'ema_20_vs_ema_50': '+1 if EMA20 > EMA50 at IB close, -1 if below, 0 if equal',
    'ema_slope_20': 'Slope of EMA20 over last 10 bars of IB (pts/bar)',
    'higher_highs_ib': 'bool — did IB make ≥2 higher highs AND higher lows?',
    'lower_lows_ib': 'bool — did IB make ≥2 lower lows AND lower highs?',
    'ib_close_vs_avwap_0930': '+1 if close > AVWAP(09:30), -1 if below',
    'break_vs_avwap_0930': '+1 if break direction = AVWAP direction, -1 if opposite',
    'avwap_confluence_score': '0-3: count of AVWAP(09:30) + AVWAP(18:00) + AVWAP(00:00) agreeing with break direction',
}
```

**Configurable anchor system:**
The `compute_anchored_vwap` function accepts any `datetime.time` as anchor. A YAML config file controls which anchors are precomputed:

```yaml
# config/avwap_anchors.yaml
anchors:
  - time: "09:30"
    label: "0930"
    description: "IB start — RTH open"
  - time: "18:00"
    label: "1800"
    description: "Globex open"
  - time: "00:00"
    label: "0000"
    description: "Midnight open (ICT)"
  - time: "08:00"
    label: "0800"
    description: "Pre-market open"
  - time: "09:00"
    label: "0900"
    description: "9AM hour start"
  - time: "10:00"
    label: "1000"
    description: "Post-IB"
  - time: "13:30"
    label: "1330"
    description: "NY PM IB start"
```

To test a custom anchor (e.g., 9:45 news time):
```bash
.\.venv\Scripts\python.exe -m scripts.edgeful.ib_avwap_trend --anchor 09:45 --label 0945
```

### Phase 3: Master Confluence Table (P0 — 3 days)

**Script:** `scripts/edgeful/ib_master_confluence.py`

**Output:** `data/derived/ib_master_confluence_{SYM}.parquet`

One row per `(symbol, trading_day, session_slot, time_basis)`. Joins ALL available signals:

```python
MASTER_CONFLUENCE_SCHEMA = {
    # ── IB Core (from ib_facts) ──
    'ib_high', 'ib_low', 'ib_mid', 'ib_range', 'range_pct', 'range_bucket_full',
    'range_bucket_trailing', 'mid_lock_frac', 'early_mid_event',
    'first_break_dir', 'first_break_minutes', 'first_break_minutes_5min', 'first_break_bucket',
    'double_break', 'false_break_high', 'false_break_low',
    'max_ext_up', 'max_ext_down', 'behavior',
    
    # ── IB Bias Variants ──
    'bias_formation_firstreach', 'bias_formation_lasttouch',
    'bias_close_dir', 'bias_fvg', 'bias_fvg_ifvg',
    'bias_fvg_rth', 'bias_fvg_1011',
    'bias_correct_formation_firstreach_05x', 'bias_correct_formation_firstreach_1x',
    'bias_correct_formation_lasttouch_05x', 'bias_correct_formation_lasttouch_1x',
    'bias_correct_close_dir_05x', 'bias_correct_close_dir_1x',
    'bias_correct_fvg_05x', 'bias_correct_fvg_1x',
    'bias_correct_fvg_ifvg_05x', 'bias_correct_fvg_ifvg_1x',
    
    # ── IB Play Results ──
    'play1_result', 'play1_rr', 'play1_mfe', 'play1_mae', 'play1_timeout_loss',
    'play2_result', 'play2_rr', 'play2_mfe', 'play2_mae', 'play2_timeout_loss',
    'play3_result', 'play3_rr', 'play3_mfe', 'play3_mae', 'play3_timeout_loss',
    
    # ── IB Derived (from Phase 2) ──
    'ib_poc_price', 'ib_vah', 'ib_val', 'ib_tpo_skew',
    'ib_high_touch_count', 'ib_low_touch_count',
    'ib_range_pct_of_daily', 'ib_range_5d_contracting', 'ib_range_5d_expanding',
    'ib_vs_overnight_ratio', 'ib_inside_outside',
    'ib_3day_composite_high', 'ib_3day_composite_low',
    'ib_break_speed', 'ib_open_drive_dir',
    'ib_failure_mode_play1', 'ib_failure_mode_play2', 'ib_failure_mode_play3',
    
    # ── Daily Context (from daily_context) ──
    'day_of_week', 'vix_close', 'vix_regime', 'vix_pctile_60d',
    'atr_14d', 'session_range', 'atr_usage_pct',
    'pdh', 'pdl', 'pd_mid', 'pd_range',
    'gap_size_pct', 'gap_direction', 'gap_filled',
    'overnight_high', 'overnight_low', 'midnight_open',
    'is_inside_day', 'is_outside_day',
    'first_hour_direction', 'first_hour_continued',
    'session_direction', 'streak_length', 'streak_direction',
    'is_event_day', 'event_type', 'is_opex_week',
    
    # ── Daily Classification ──
    'daily_classification',  # R1/R2/DWP/DNP
    
    # ── Profiler Overnight (from profiler_lookup) ──
    'profiler_asia_status',      # LT/LF/ST/SF/None
    'profiler_london_status',    # LT/LF/ST/SF/None
    'profiler_ny1_status',       # LT/LF/ST/SF/None
    'profiler_asia_broken',      # bool
    'profiler_london_broken',    # bool
    'profiler_overnight_regime', # "trending" | "contradicting"
    
    # ── Herman (from herman_stats) ──
    'herman_asia_range', 'herman_asia_type',  # Small/Large
    'herman_pl_sweeps_asia_h', 'herman_pl_sweeps_asia_l',
    'herman_lon_sweeps_asia_h', 'herman_lon_sweeps_asia_l',
    'herman_ny_am_sweeps_lon_h', 'herman_ny_am_sweeps_lon_l',
    'herman_ny_am_sweeps_asia_h', 'herman_ny_am_sweeps_asia_l',
    
    # ── Quarterly Theory (from hourly_quarter_stats) ──
    'qtr_09_hour_mode',   # Expansion
    'qtr_10_hour_mode',   # Reversion
    'qtr_09_q1_high',     # bool — did Q1 form the high?
    'qtr_10_q1_high',     # bool
    
    # ── SecondBrain Rules ──
    'sb_noon_curve_active',     # High set before 11:00 → new low after noon
    'sb_nine_am_candle_green',  # 9AM candle green → 70.6% NY close green
    'sb_ib_midpoint_bias',      # Close in upper 50% → 82.3% high break
    
    # ── SDEV / Reversion ──
    'sdev_05_touched',    # bool
    'sdev_10_touched',    # bool
    'sdev_15_touched',    # bool
    
    # ── Economic Calendar ──
    'is_fomc_day', 'is_nfp_day', 'is_cpi_day', 'is_ism_day',
    
    # ── News Timing (from Phase 2.5) ──
    'news_0945_today', 'news_1000_today', 'news_1030_today',
    'news_impact_level', 'news_release_name',
    'ib_news_distorted', 'ib_news_break', 'minutes_since_news',
    
    # ── OPEX (from Phase 2.5) ──
    'is_opex_week', 'is_opex_friday', 'is_quarterly_opex',
    'days_to_opex', 'opex_phase', 'opex_ib_range_pctile',
    
    # ── Anchored VWAP (from Phase 2.6) ──
    'avwap_0930_price', 'avwap_0930_deviation_pct', 'avwap_0930_slope',
    'avwap_0930_above_count', 'avwap_0930_below_count', 'avwap_0930_touch_count',
    'avwap_0930_std_upper', 'avwap_0930_std_lower',
    'avwap_0930_break_direction', 'avwap_0930_distance_at_break_pct',
    'avwap_1800_price', 'avwap_1800_deviation_pct', 'avwap_1800_break_direction',
    'avwap_0000_price', 'avwap_0000_deviation_pct', 'avwap_0000_break_direction',
    'avwap_0800_price', 'avwap_0800_break_direction',
    'avwap_0900_price', 'avwap_0900_break_direction',
    'avwap_1000_price', 'avwap_1000_break_direction',
    'avwap_1330_price', 'avwap_1330_break_direction',
    
    # ── Simple Trend Confirmations (from Phase 2.6) ──
    'ema_20_vs_ema_50', 'ema_slope_20',
    'higher_highs_ib', 'lower_lows_ib',
    'ib_close_vs_avwap_0930', 'break_vs_avwap_0930',
    'avwap_confluence_score',  # 0-3: multi-timeframe AVWAP agreement
    
    # ── Composite Scores ──
    'conviction_score_naive',    # 0-10 hand-tuned BASELINE (§7.3) — for comparison only
    'conviction_score_v2',       # 0-1 empirically weighted (Phase 4) — the production score
    'conviction_filters_active', # JSON list of which validated filters fired today
    'bias_agreement_count',      # How many bias variants agree (0-4)
    'suggested_play',            # Best play for this regime (from Phase 6 regime classifier)
    'suggested_direction',       # +1/-1
    'suggested_expectancy',      # Expected R (from Phase 5/6 backtest)
}
```

### Phase 4: Validation Harness & Empirical Conviction (P0 — 3 days)

**Script:** `scripts/edgeful/ib_validate_confluences.py`

**Goal:** Test individual filters and combinations to improve WR and expectancy, then derive an *empirically-weighted* conviction score. This phase produces the validated score — Phase 3 only stores raw filter flags (no hand-tuned composite).

**4a. Single-filter effectiveness (per play):**
```python
# For each filter F and each play P:
#   1. Split: F=True vs F=False
#   2. Measure: WR, expectancy (R), N for each split
#   3. Lift = WR(F=True) - WR(F=False)
#   4. Significance: chi-square / bootstrap CI on lift
#   5. Filter precision (P(loss | F=True)), recall (P(F=True | loss))
#   Output: ib_filter_effectiveness.parquet (one row per filter × play)
```

**4b. Filter independence & redundancy:**
```python
#   1. Pairwise activation correlation across all filters
#   2. VIF / condition number check (drop filters with rho > 0.85)
#   3. Build a non-redundant filter pool per play
#   Output: ib_filter_correlation.parquet
```

**4c. Combination search (pairs, triples, stacks):**
```python
#   1. For all pairs/triples of non-redundant filters: combined WR, expectancy, N
#   2. Greedy forward selection: start with best single filter, add filters by marginal lift
#   3. Track N-shrinkage (each added filter reduces sample size) — stop when N < min_trades
#   4. Output the optimal filter STACK per play (the set that maximizes expectancy at N ≥ min)
#   Output: ib_filter_stacks.parquet (one row per stack × play, with the filter list + metrics)
```

**4d. Empirical conviction score (output of this phase):**
```python
#   Weight each filter by its validated lift (or a simple logistic regression on P(win)).
#   conviction_score_v2 = sum(filter_active × validated_lift) / sum(validated_lift)
#   → normalized 0–1; a filter with negative lift gets weight 0 (dropped).
#   Output: ib_conviction_weights.parquet (filter → weight per play)
#   Add column conviction_score_v2 to ib_master_confluence (joined back)
```

**Outputs:**
```
data/derived/
├── ib_filter_effectiveness.parquet    # 4a — per-filter lift per play
├── ib_filter_correlation.parquet      # 4b — pairwise correlations, redundancy flags
├── ib_filter_stacks.parquet           # 4c — optimal filter combos per play
└── ib_conviction_weights.parquet      # 4d — validated weights → conviction_score_v2
```

**Why this replaces the hand-tuned score (§7.3):** The old `conviction_score` asserted fixed integer weights (+2/−2/−1). Phase 4 learns weights from data and drops filters that don't help. The hand-tuned version is kept only as a naive baseline for comparison (see §7.3).

### Phase 5: Strategy-Specific Derived Data (P1 — 2 days)

#### 5.1 MAE-Calibrated Stop Levels

**Script:** `scripts/edgeful/ib_mae_stops.py`

```python
# For each play, compute optimal stop as P95 MAE of winners
# Output: ib_optimal_stops.parquet
# Columns: symbol, session_slot, play, p95_mae_winners, p99_mae_winners,
#          optimal_stop_r, wr_at_optimal_stop, expectancy_at_optimal_stop
```

#### 5.2 Time-Decay Exit Schedule

**Script:** `scripts/edgeful/ib_time_decay.py`

```python
# For each play, compute P(win | elapsed_minutes) curve
# Output: ib_time_decay_curves.parquet
# Columns: symbol, session_slot, play, elapsed_minutes, win_prob, N_remaining
```

#### 5.3 Partial Profit Ladder Optimization

**Script:** `scripts/edgeful/ib_ladder_optimizer.py`

```python
# For each play, find optimal TP ladder (TP1%, TP2%, TP3%, runner%)
# that maximizes expectancy
# Output: ib_optimal_ladders.parquet
```

#### 5.4 Break Speed Distribution

**Script:** `scripts/edgeful/ib_break_speed.py`

```python
# Compute break speed (pts/min) distribution and its relationship to outcomes
# Output: ib_break_speed_stats.parquet
```

---

## 4. Output File Manifest

All output goes to `data/derived/`:

```
data/derived/
├── ib_agg_bias_compare.parquet          # Phase 1
├── ib_agg_timing.parquet                 # Phase 1
├── ib_agg_extension_ladder.parquet       # Phase 1
├── ib_agg_plays_by_regime.parquet        # Phase 1
├── ib_agg_bias_conflict.parquet          # Phase 1
├── ib_agg_no_signal.parquet              # Phase 1
├── ib_derived_{SYM}.parquet              # Phase 2 (or merged into ib_facts)
├── ib_news_opex_{SYM}.parquet            # Phase 2.5
├── ib_master_confluence_{SYM}.parquet    # Phase 3
├── ib_filter_effectiveness.parquet       # Phase 4
├── ib_optimal_stops.parquet              # Phase 5.1
├── ib_time_decay_curves.parquet          # Phase 5.2
├── ib_optimal_ladders.parquet            # Phase 5.3
└── ib_break_speed_stats.parquet          # Phase 5.4

config/
└── avwap_anchors.yaml                    # Phase 2.6 config

# Data sources (already exist — do NOT recreate):
# - web/prisma/dev.db → EconomicEvent table (11,684 events, UTC timestamps)
# - data/{SYM}_1m.parquet → 1m OHLCV with volume column
# - scripts/derived/precompute_herman_stats.py → builds Herman for any ticker

scripts/
├── edgeful/
│   ├── ib_aggregates.py                  # Phase 1
│   ├── ib_derived_fields.py              # Phase 2
│   ├── ib_news_opex.py                   # Phase 2.5
│   ├── ib_avwap_trend.py                 # Phase 2.6
│   ├── ib_master_confluence.py           # Phase 3
│   ├── ib_validate_confluences.py        # Phase 4
│   ├── ib_mae_stops.py                   # Phase 5.1
│   ├── ib_time_decay.py                  # Phase 5.2
│   ├── ib_ladder_optimizer.py            # Phase 5.3
│   └── ib_break_speed.py                 # Phase 5.4
└── libs_py/
    └── avwap.py                          # Phase 2.6 library (reusable)
```

---

## 5. Reuse Across Other Strategies

The master confluence table is designed to be strategy-agnostic. Any strategy can join on `(symbol, trading_date)`:

| Strategy | Confluence Fields Used |
|---|---|
| **VWAP Reclaim** | `daily_classification`, `vix_regime`, `first_hour_direction`, `gap_filled` |
| **EMA Pullback** | `daily_classification`, `streak_direction`, `atr_14d`, `session_range` |
| **Failed Auction** | `profiler_overnight_regime`, `herman_pl_sweep`, `pdh`/`pdl` |
| **6AM Reversal** | `herman_ny_am_sweeps_lon_h`, `overnight_high`/`low`, `midnight_open` |
| **Box Reversion** | `daily_classification`, `profiler_asia_status`, `profiler_london_status` |
| **Mean Reversion** | `sdev_05_touched`, `sdev_10_touched`, `vix_regime` |

---

## 6. Execution Order & Dependencies

```
Phase 1 (ib_aggregates.py)
    ↓ reads ib_facts + ib_play_detail + ib_ext_detail
    ↓
Phase 2 (ib_derived_fields.py)
    ↓ reads ib_facts + 1m data (for TPO computation)
    ↓
Phase 2.5 (ib_news_opex.py) ───────────────────┐
    ↓ reads ib_facts + Prisma DB EconomicEvent    │
    ↓                                            │
Phase 2.6 (ib_avwap_trend.py) ──────────────────┤
    ↓ reads 1m data + avwap_anchors.yaml        │
    ↓                                            │
Phase 3 (ib_master_confluence.py) ←─────────────┘
    ↓ reads ib_facts + ib_derived + ib_news_opex
    ↓       + daily_context + daily_classification
    ↓       + profiler_lookup + herman_stats + hourly_quarter_stats
    ↓       + Prisma DB EconomicEvent
    ↓
Phase 4 (ib_validate_confluences.py)
    ↓ reads ib_master_confluence
    ↓
Phase 5 (strategy-specific scripts)
    ↓ reads ib_master_confluence + ib_play_detail
```

**Parallelizable:** Phases 2.5 and 2.6 can run in parallel with Phase 2 since they read different inputs. Phase 1 must complete first (it's read-only, no dependency on derived fields).

---

## 7. Technical Notes

### 7.1 TPO Computation (Phase 2)

TPO (Time Price Opportunity) requires 1m bar data for the IB window. For each trading day:
- Filter bars to IB window (e.g., 9:30-10:30 ET)
- Group by price (rounded to tick size)
- Count bars at each price level
- POC = price with max count
- Value Area = price range containing 70% of TPOs, centered on POC

### 7.2 Profiler Overnight Regime (Phase 3)

```python
def classify_overnight_regime(asia_status, london_status):
    """Trending = both True in same direction or both False in same direction.
       Contradicting = one True, one False, or opposite directions."""
    if asia_status in ('LT', 'ST') and london_status in ('LT', 'ST'):
        if (asia_status == 'LT') == (london_status == 'LT'):
            return 'trending'
    if asia_status in ('LF', 'SF') and london_status in ('LF', 'SF'):
        if (asia_status == 'LF') == (london_status == 'LF'):
            return 'trending'
    return 'contradicting'
```

### 7.3 Conviction Score (two versions)

**Important:** This hand-tuned score is a **naive baseline only** — kept for comparison against the empirically-derived `conviction_score_v2` produced by Phase 4. Do NOT use it as the production filter. Its fixed integer weights are asserted, not validated; a +2 bonus may have no edge or even hurt WR. Phase 4 learns the actual weights from `ib_filter_effectiveness.parquet` and drops non-contributing filters.

**Architecture:** Phase 3 stores *raw filter flags* in the master confluence table (no composite). Phase 4 validates each filter, learns weights, and writes `conviction_score_v2` back to the master confluence table. This keeps filtering testable: any individual filter or combination can be sliced independently.

```python
def compute_conviction_score_naive(row):  # BASELINE ONLY — see Phase 4 for the validated version
    score = 0
    
    # ── Bonuses ──
    # Profiler overnight regime
    if row['profiler_overnight_regime'] == 'trending':
        score += 2
    # Herman Asia size
    if row['herman_asia_type'] == 'Small':
        score += 2
    # Mid lock timing (range settled early = conviction)
    if row['mid_lock_frac'] < 0.5:
        score += 1
    # Formation bias agreement (firstreach == lasttouch)
    if row['bias_formation_firstreach'] == row['bias_formation_lasttouch']:
        score += 1
    # FVG agrees with formation
    if row['bias_fvg'] == row['bias_formation_firstreach']:
        score += 1
    # 9AM candle aligns with bias
    if row['sb_nine_am_candle_green'] and row['bias_formation_firstreach'] == 1:
        score += 1
    elif not row['sb_nine_am_candle_green'] and row['bias_formation_firstreach'] == -1:
        score += 1
    # Gap unfilled (trend day signal)
    if not row['gap_filled']:
        score += 1
    # AVWAP confluence: break direction agrees with AVWAP(09:30)
    if row['break_vs_avwap_0930'] == 1:
        score += 1
    # Multi-timeframe AVWAP agreement
    score += row['avwap_confluence_score']  # 0-3
    
    # ── Penalties ──
    # Range day classification
    if row['daily_classification'] == 'R1':
        score -= 2
    # Contradicting overnight
    if row['profiler_overnight_regime'] == 'contradicting':
        score -= 2
    # 10:00 hour Q1 high (fade signal)
    if row['qtr_10_q1_high']:
        score -= 1
    # News-distorted IB
    if row['ib_news_distorted']:
        score -= 2
    # News break (break within 2 min of 10:00/10:30 release)
    if row['ib_news_break']:
        score -= 2
    # Quarterly OPEX (triple witching)
    if row['is_quarterly_opex']:
        score -= 2
    # OPEX Friday
    if row['is_opex_friday']:
        score -= 1
    # Break direction disagrees with AVWAP
    if row['break_vs_avwap_0930'] == -1:
        score -= 1
    # EMA trend disagrees with break direction
    if row['ema_20_vs_ema_50'] != 0 and row['ema_20_vs_ema_50'] != row['first_break_dir']:
        score -= 1
    
    return max(0, min(10, score))
```

### 7.4 Performance Considerations

- Phase 1-2: Pure parquet reads, vectorized pandas — fast (< 5 min per symbol)
- Phase 3: Multiple joins across different data sources — may need chunked processing for 20-year history
- Phase 4: Combinatorial filter testing — use joblib parallel for filter pair/triple sweeps
- All phases: ADR-017 compliant (vectorized, no loops in calculation paths)

---

## 8. Success Criteria

After all phases complete, you should be able to answer:

1. **Which bias variant is most accurate?** → `ib_agg_bias_compare.parquet`
2. **When should I enter?** → `ib_agg_timing.parquet` (mode break time)
3. **Which play for today's regime?** → `ib_agg_plays_by_regime.parquet`
4. **What's my optimal stop?** → `ib_optimal_stops.parquet`
5. **When should I exit if target not hit?** → `ib_time_decay_curves.parquet`
6. **What's my conviction score today?** → `ib_master_confluence.parquet` (live query)
7. **Which filters actually improve WR?** → `ib_filter_effectiveness.parquet`
8. **Can I get to 80% WR?** → Filter stack from Phase 4, applied to Phase 3 data
9. **How does 9:45/10:00 news affect IB breaks?** → `ib_news_opex_{SYM}.parquet` sliced by `ib_news_distorted` / `ib_news_break`
10. **Should I skip OPEX weeks?** → `ib_agg_plays_by_regime.parquet` sliced by `opex_phase`
11. **Does AVWAP(09:30) direction improve break accuracy?** → `ib_filter_effectiveness.parquet` testing `break_vs_avwap_0930`
12. **What's the best custom anchor for trend confirmation?** → Test any anchor via `--anchor HH:MM` flag
13. **How does multi-timeframe AVWAP confluence affect WR?** → `avwap_confluence_score` 0-3 vs play outcomes
14. **Are news-distorted IBs tradeable at all?** → Separate stats: "clean IB" vs "news IB" win rates

---

## 9. External Research — Additional Concepts (2026-07-25)

Cross-walk of external IB research against Phases 1–5. Items already covered are marked ✅; genuinely-new additions are marked 🆕 and assigned a phase.

### 9.1 Market Profile / Steidlmayer (Part 1 of research)

| Concept | Status | Mapping |
|---|---|---|
| Point of Control (POC) — price with most TPOs | ✅ | `ib_poc_price` (Phase 2) |
| Value Area (70% TPOs ±1σ) | ✅ | `ib_vah` / `ib_val` (Phase 2) |
| TPO count by price | ✅ | Backing calc for POC/VA — keep intermediate in `ib_derived` |
| TPO skew (top-heavy vs bottom-heavy) | ✅ | `ib_tpo_skew` (Phase 2) |

### 9.2 Volume-Weighted IB Levels 🆕

The 1m parquet already has a `volume` column, so these are computable now — they augment (not replace) the TPO-based POC/VA from Phase 2.

| Field | Computation | Use |
|---|---|---|
| `ib_vwap` 🆕 | Σ(px × vol) / Σ(vol) during IB | Dynamic mid — more accurate than arithmetic `ib_mid` |
| `ib_vol_at_high` 🆕 | Sum(volume) on bars tagging `ib_high` | Which extreme had participation? |
| `ib_vol_at_low` 🆕 | Sum(volume) on bars tagging `ib_low` | Companion to above |
| `ib_vol_poc_price` 🆕 | Price level with max cumulative volume in IB | Volume-node S/R — harder to break than TPO POC |
| `ib_vol_skew` 🆕 | +1 if upper-half volume > lower-half, -1 else | Volume-confirmed bias (vs TPO skew) |

**Phase:** Add to Phase 2 (`ib_derived_fields.py`) as a sub-block. No new data source required.

### 9.3 Multi-Day IB Context

| Concept | Status | Mapping |
|---|---|---|
| Inside / outside / overlapping day | ✅ | `ib_inside_outside` (Phase 2) |
| 3-day composite high/low | ✅ | `ib_3day_composite_high` / `_low` (Phase 2) |
| 5-day rolling contraction/expansion | ✅ | `ib_range_5d_contracting` / `_expanding` (Phase 2) |
| Contraction→expansion cycle as **pre-break strategy** | 🆕 | See §9.9 (strategy module, not just a flag) |

### 9.4 IB as % of Daily Range (Day-Type Prediction)

| Concept | Status | Mapping |
|---|---|---|
| `ib_range_pct_of_daily` | ✅ | Phase 2 |
| Day-type buckets (<30% trend, 30–50% normal, 50–70% normal-var, >70% range) | 🆕 | Derive `ib_day_type_predicted` categorical from the ratio; backtest WR by bucket in Phase 4 |

**Note:** `ib_range_pct_of_daily` is only knowable *after* the close. For a *pre-trade* filter, use the trailing distribution (Phase 4) to estimate P(trend | today's IB size vs trailing 60d).

### 9.5 Opening Auction (First 5 Minutes)

| Field | Status | Mapping |
|---|---|---|
| `ib_open_drive_dir` (9:30–9:35 vs prior close) | ✅ | Phase 2 |
| Opening range (first 5 min high/low) | 🆕 | `ib_or5_high` / `ib_or5_low` |
| OR break timing (<15 min → trend, else → range) | 🆕 | `ib_or5_break_minutes` + `ib_or5_broken_in_15` bool |
| OR direction vs IB close agreement | 🆕 | `ib_or5_ib_close_agree` (+1/-1) — conviction flag |

**Phase:** Add to Phase 2.

### 9.6 Entry Strategy Innovations (Part 2)

| Concept | Status | Notes |
|---|---|---|
| Scale-in ladder entries | 🆕 | Strategy module (Phase 6) — 3-tier ladder at break / +0.25x / +0.5x |
| Time-qualified entries (size by break bucket) | 🆕 (partial) | `first_break_bucket` exists; sizing ruleset is new → Phase 6 |
| 80% rule (POC-time-above-mid conviction) | 🆕 | `ib_pct_time_above_mid` field (Phase 2) + entry rule (Phase 6) |
| Two-timeframe (5m confirm + 1m trigger) | 🆕 | Requires 5m resample pipeline — Phase 6, blocked on Phase 2 5m bars |
| Failed-breakout opposite entry | 🆕 | Distinct from Play 3 fade — Phase 6 strategy module |
| Opening-drive entry (9:30–9:45) | 🆕 | Phase 6 — uses §9.5 fields |

**New derived field for the 80% rule:**

| Field | Computation | Use |
|---|---|---|
| `ib_pct_time_above_mid` 🆕 | % of 1m bars during IB with close > `ib_mid` | >80% → mid accepted as support; <20% → high-break likely fakeout |

### 9.7 Exit Strategy Innovations (Part 3)

| Concept | Status | Mapping |
|---|---|---|
| MAE-calibrated stops (P95 of winners) | ✅ | Phase 5.1 |
| Partial profit ladder | ✅ | Phase 5.3 |
| Time-decay exit schedule | ✅ | Phase 5.2 |
| Trailing stop by IB-range fractions | 🆕 | `ib_trail_schedule` — Phase 6 exit module |
| Session-boundary exits (11:30 / 13:30 / 15:50) | 🆕 | Phase 6 exit module (13:30 NY PM IB & 15:50 prop-firm rule per ADR-020) |
| VWAP-cross exit (break fails if price re-crosses IB VWAP) | 🆕 | Phase 6 exit module — uses `ib_vwap` from §9.2 |
| Opposite-side liquidity target (PDH/PDL/P12 next-level) | 🆕 | Phase 6 exit module — joins `reference_levels` from §1.4 |

### 9.8 New Strategy Concepts (Part 4)

| Concept | Status | Notes |
|---|---|---|
| IB contraction/expansion cycle (pre-break) | 🆕 | Phase 6 — uses `ib_range_5d_contracting`; enters *before* the break on vol-expansion trigger |
| IB vs overnight range relationship | ✅ | `ib_vs_overnight_ratio` (Phase 2) |
| Cumulative delta within IB | 🆕 (deferred) | Needs bid/ask volume — Tier 3, not in current data |
| IB break speed filter | ✅ | `ib_break_speed` (Phase 2) + Phase 5.4 stats |
| Pre-IB telegraph (9:25–9:30) | 🆕 | `ib_pre_telegraph_dir` — 5-min window before IB start |
| Three-touches rule | ✅ | `ib_high_touch_count` / `ib_low_touch_count` (Phase 2) — threshold ≥3 = confirmed |
| Post-break mid magnet study | 🆕 | `ib_mid_revisited_post_break` bool + `ib_mid_revisit_minutes` — distinct from pre-break mid retest |
| Economic calendar filter (skip FOMC/NFP/CPI/ISM) | ✅ | Phase 2.5 (`is_fomc_day` etc.) |

**New fields:**

| Field | Computation | Use |
|---|---|---|
| `ib_pre_telegraph_dir` 🆕 | +1 if 9:25–9:30 range closes above 9:25 open, -1 below, 0 doji | Pre-IB direction hint |
| `ib_mid_revisited_post_break` 🆕 | bool — did price return to `ib_mid` *after* first break closed outside? | Regime: magnet day vs trend day |
| `ib_mid_revisit_post_break_minutes` 🆕 | Minutes from break close to next mid touch | If fast revisit → magnet regime |

### 9.9 Regime-Switching System Architecture (Part 5)

The research's "path to 80% WR" is explicitly **not** a single strategy — it's a regime classifier that routes each day to the optimal play. This is a Phase 6 architecture sitting on top of Phases 1–5.

**Regime classifier → play router:**

| Regime | Trigger | Play | Target WR |
|---|---|---|---|
| Trend day | `ib_range_pct_of_daily` < 30% (trailing estimate) + fast break + POC near extreme | Play 1 breakout, full size | 65–70% |
| Normal day | 30–50% + moderate break + POC near mid | Play 2 retest, half→full | 60–65% |
| Range day | > 50% + slow/no break + POC centered | Play 3 fade | 60–70% |
| Skip day | FOMC/NFP/CPI/ISM, contradictory overnight, late mid-lock | No trade | — |

**New derived field:**

| Field | Computation | Use |
|---|---|---|
| `ib_regime` 🆕 | "trend" / "normal" / "range" / "skip" — classifier combining the above | Master play router |
| `ib_regime_confidence` 🆕 | 0–1 — agreement score across regime triggers | Sizing scalar |

**Phase:** Phase 6 — `scripts/edgeful/ib_regime_classifier.py`. Depends on Phases 2, 2.5, 2.6 (all derived fields), Phase 4 (validated filters), Phase 5 (entry/exit modules).

### 9.10 Implementation Priority (revised, incorporating §9)

| Tier | Items | Phase |
|---|---|---|
| **Tier 1 — Immediate (1–2 wk)** | MAE-calibrated stops (5.1) ✅, time-qualified entries 🆕, partial profit ladder (5.3) ✅, economic calendar filter (2.5) ✅, **volume-weighted IB (§9.2)** 🆕, **80% rule field (§9.6)** 🆕 | Phase 2 + 5 + 6 |
| **Tier 2 — Medium (2–3 wk)** | Value Area/POC (Phase 2) ✅, multi-day context (Phase 2) ✅, break speed filter (5.4) ✅, **failed-breakout entry** 🆕, **opening-drive entry** 🆕, **pre-IB telegraph** 🆕, **post-break mid magnet** 🆕, **trailing-by-IB-fractions** 🆕, **session-boundary exits** 🆕, **VWAP-cross exit** 🆕, **liquidity targets** 🆕 | Phase 2 + 6 |
| **Tier 3 — New data (3–4 wk)** | Cumulative delta (needs tick data), two-timeframe entry (needs 5m pipeline) 🆕, **regime classifier (§9.9)** 🆕 | Phase 6 |

### 9.11 New Scripts & Fields Summary

**New scripts (Phase 6):**
- `scripts/edgeful/ib_regime_classifier.py` — trend/normal/range/skip router
- `scripts/edgeful/ib_entry_modules.py` — scale-in, time-qualified, 80%-rule, failed-breakout, opening-drive, two-timeframe
- `scripts/edgeful/ib_exit_modules.py` — trailing-by-IB-fractions, session-boundary, VWAP-cross, liquidity-target
- `scripts/edgeful/ib_pre_break.py` — contraction/expansion cycle strategy

**New derived fields (added to Phase 2):**
- Volume-weighted: `ib_vwap`, `ib_vol_at_high`, `ib_vol_at_low`, `ib_vol_poc_price`, `ib_vol_skew`
- Opening auction: `ib_or5_high`, `ib_or5_low`, `ib_or5_break_minutes`, `ib_or5_broken_in_15`, `ib_or5_ib_close_agree`
- 80% rule: `ib_pct_time_above_mid`
- Pre-IB telegraph: `ib_pre_telegraph_dir`
- Post-break magnet: `ib_mid_revisited_post_break`, `ib_mid_revisit_post_break_minutes`
- Day-type: `ib_day_type_predicted` (categorical from `ib_range_pct_of_daily` buckets)
- Regime: `ib_regime`, `ib_regime_confidence` (computed in Phase 6, joined back to master confluence)

**New derived fields from §10.14 external research (added to Phase 2):**
- ACD framework: `ib_or_acd_a_up`, `ib_or_acd_a_down`, `ib_or_acd_c_level`, `ib_or_acd_a_held`
- VCP contraction: `ib_vcp_3day_contracting`, `ib_vcp_volume_ratio`, `ib_vcp_setup`
- Single prints: `ib_has_upper_single_print`, `ib_has_lower_single_print`, `ib_single_print_high`, `ib_single_print_low`
- RVOL: `ib_rvol` (= VCP volume ratio, reused), `ib_rvol_bucket`
- VIX term structure: `vix_term_structure`, `vix_regime_intraday` (Tier 1 if VIX futures data loaded, else Tier 3)
- Empirical baselines (§10.14.8): `ib_range_size_class`, `ib_break_urgency`, `ib_extension_expectation`
- Wicks/bodies: `ib_high_wick_pct`, `ib_low_wick_pct`, `ib_high_body_close`, `ib_low_body_close`
- Sweep detail: `ib_high_swept`, `ib_low_swept`, `ib_sweep_reclaim_dir`
- Tier 3 (deferred): `breadth_ad_ratio_at_break`, `breadth_divergence`, CVD/delta fields (need tick/breadth feed)

**New Phase 4 baseline file:** `data/derived/ib_empirical_baselines.json` — TrevorTrades 10-year ES probabilities (§10.14.8) used as the no-filter reference distribution for every filter's lift calculation.

**Updated output manifest (additions):**
```
data/derived/
├── ib_derived_{SYM}.parquet              # Phase 2 (+ §9.2, §9.5, §9.6, §9.8 fields)
├── ib_regime_{SYM}.parquet               # Phase 6 — regime classifier output
├── ib_entry_signals_{SYM}.parquet        # Phase 6 — entry module signals
├── ib_exit_signals_{SYM}.parquet         # Phase 6 — exit module signals
└── ib_pre_break_signals_{SYM}.parquet    # Phase 6 — contraction/expansion pre-break
```

---

## 10. Strategy Catalog — All Testable IB Strategies

Comprehensive list of every strategy the IB system can produce, so none are forgotten. Each is a testable hypothesis against the master confluence table. The **regime-switching router (§10.5)** selects among these per-day rather than running them all blindly.

### 10.1 Core IB Plays (existing — from `ib_facts` / `ib_play_detail`)

| # | Strategy | Entry | Stop | Target | Phase | Status |
|---|---|---|---|---|---|---|
| 1 | **Play 1 — IB Breakout** | Enter at IB high/low break (close outside) | Opposite IB boundary | 0.5x / 1.0x / 1.5x extensions | Existing | ✅ |
| 2 | **Play 2 — IB Retest** | Enter on retest of IB high/low from outside after a break | Opposite IB boundary | 0.5x / 1.0x | Existing | ✅ |
| 3 | **Play 3 — IB Fade** | Enter fade at 0.5x / 1.0x extension (mean reversion) | IB high/low + buffer | IB mid | Existing | ✅ |

### 10.2 Market Profile / TPO-Based Strategies (Phase 2 data)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 4 | **VAH Break with POC-top** | Break of VAH when POC is in top half of IB | VAH−1.0×IB range | 1.0x extension | 2 |
| 5 | **VAL Break with POC-bottom** | Symmetric short | VAL+1.0×IB range | 1.0x extension | 2 |
| 6 | **POC Reversion** | Fade first touch of POC from outside VA | VA boundary | Opposite VA boundary | 2 |
| 7 | **80% Rule Long** | If >80% of IB time above mid, enter long on first mid touch after high break | IB low | IB high + 0.5x | 2+6 |
| 8 | **80% Rule Short** | Symmetric: <20% above mid → high break = fakeout → short | IB high | IB low − 0.5x | 2+6 |
| 9 | **Three-Touches Breakout** | Break of a level touched ≥3× during IB formation | Opposite boundary | 1.0x | 2 |

### 10.3 Volume-Weighted Strategies (Phase 2 §9.2)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 10 | **IB VWAP Trend** | Enter at IB high break only if break is above `ib_vwap` | `ib_vwap` | 1.0x | 2+6 |
| 11 | **Volume-Node Break** | Break of `ib_vol_poc_price` (high-volume node) — stronger S/R | Opposite IB boundary | 1.0x | 2+6 |
| 12 | **Volume Skew Filter** | Only take breakouts in direction of `ib_vol_skew` | Opposite boundary | 1.0x | 2 |
| 13 | **Volume-at-Extreme Fade** | Fade IB high if `ib_vol_at_high` < `ib_vol_at_low` (low participation extreme) | IB high + 0.25x | IB mid | 2+6 |

### 10.4 Multi-Day Context Strategies (Phase 2 §9.3)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 14 | **Inside-Day Breakout** | Today's IB inside yesterday's → trade the break of either IB extreme | 3-day composite low/high | 3-day composite | 2+6 |
| 15 | **Outside-Day Fade** | Today's IB engulfs yesterday's → fade extensions (mean reversion likely) | 1.5× IB range | IB mid | 2+6 |
| 16 | **3-Day Composite Break** | Break of `ib_3day_composite_high`/`_low` | Opposite composite boundary | 1.0× composite range | 2+6 |
| 17 | **5-Day Contraction Pre-Break** | When `ib_range_5d_contracting`, enter vol-expansion trigger before the break | 5-day low/high | 1.0× avg expanded range | 2+6 |

### 10.5 Day-Type / Regime Strategies (Phase 6 §9.9)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 18 | **Trend Day Breakout** | `ib_range_pct_of_daily` <30% (trailing est) + fast break + POC near extreme | MAE-calibrated | 1.5x+ runner | 6 |
| 19 | **Normal Day Retest** | 30–50% ratio + moderate break + POC near mid | Opposite boundary | 1.0x | 6 |
| 20 | **Range Day Fade** | >50% ratio + POC centered + no clean break | 0.25x past extreme | IB mid | 6 |
| 21 | **Regime Router (system)** | Routes each day to strategies 18/19/20/skip via `ib_regime` classifier | — | — | 6 |

### 10.6 Entry Innovation Strategies (Phase 6 §9.6)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 22 | **Scale-In Ladder** | 3 entries: at break / +0.25x / +0.5x (40%/30%/30% size) | Opposite boundary | Laddered 0.5x/1.0x/trail | 6 |
| 23 | **Time-Qualified Entry** | Full size 10:30–10:45, half 10:45–11:30, skip 11:30–13:00, half 13:00–14:30, skip late | Opposite boundary | 1.0x | 6 |
| 24 | **Two-Timeframe (5m+1m)** | 5m close above IB high → wait for 1m pullback to 5m bar mid → enter on next 1m close above 5m bar high | 5m bar low | 1.0x | 6 |
| 25 | **Failed-Breakout Reversal** | Price breaks high, closes back inside IB → enter SHORT (opposite) | IB high + 0.25x | IB low | 6 |
| 26 | **Opening Drive Entry** | First 15 min (9:30–9:45) sets tone; enter continuation if OR5 breaks in direction of `ib_open_drive_dir` | OR5 opposite | 1.0x | 6 |
| 27 | **Pre-IB Telegraph** | 9:25–9:30 closes above 9:25 open → bias long for IB break | Opposite boundary | 1.0x | 2+6 |

### 10.7 Exit Innovation Strategies (Phase 6 §9.7)

| # | Strategy | Mechanism | Phase |
|---|---|---|---|
| 28 | **MAE-Calibrated Stop** | Stop at P95 MAE of winners (from `ib_play_detail`) instead of opposite boundary | 5.1 |
| 29 | **Trailing by IB Fractions** | +0.25x→BE, +0.5x→+0.25x, +0.75x→+0.5x, +1.0x→+0.5x trail, >1.0x→0.5x trail | 6 |
| 30 | **Time-Decay Exit** | 0–30min hold, 30–60 tighten to BE, 60–90 exit 50%, 90–120 exit rest, after 13:00 exit all | 5.2 |
| 31 | **Session-Boundary Exit** | Reduce at 11:30 (NY2), re-eval at 13:30 (PM IB), exit all at 15:50 (ADR-020) | 6 |
| 32 | **Partial Profit Ladder** | 40% at 0.5x / 30% at 1.0x / 20% at 1.5x / 10% trailing | 5.3 |
| 33 | **VWAP-Cross Exit** | If price breaks IB high then re-crosses `ib_vwap` → exit immediately (failed break) | 6 |
| 34 | **Liquidity Target** | Target next PDH/PDL/P12 level from `reference_levels` instead of fixed extension | 6 |

### 10.8 Post-Break Magnet Strategies (Phase 2 §9.8)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 35 | **Mid-Magnet Fast Exit** | If `ib_mid_revisit_post_break_minutes` < 15 (magnet regime) → exit early at mid | — | — | 2+6 |
| 36 | **Trend-Day Hold** | If `ib_mid_revisited_post_break` = False (no magnet) → hold to 1.5x+ | — | — | 2+6 |

### 10.9 News / OPEX Filter Strategies (Phase 2.5)

| # | Strategy | Rule | Phase |
|---|---|---|---|
| 37 | **News-Distortion Skip** | Skip trade if `ib_news_distorted` = True | 2.5 |
| 38 | **News-Break Skip** | Skip if `ib_news_break` = True | 2.5 |
| 39 | **Post-News Entry** | Wait N minutes after news (`minutes_since_news`) before entering | 2.5 |
| 40 | **OPEX Friday Range Fade** | On `is_opex_friday`, prefer Play 3 (fade) over breakout | 2.5 |
| 41 | **Quarterly OPEX Skip** | Skip on `is_quarterly_opex` (triple witching) | 2.5 |
| 42 | **Calendar Hard Skip** | Skip FOMC/NFP/CPI/ISM days (from `is_fomc_day` etc.) | 2.5 |

### 10.10 Trend / Confluence Filter Strategies (Phase 2.6 + Phase 4)

| # | Strategy | Filter | Phase |
|---|---|---|---|
| 43 | **AVWAP(09:30) Confluence** | Only take breaks where `break_vs_avwap_0930` = +1 | 2.6+4 |
| 44 | **Multi-TF AVWAP Stack** | `avwap_confluence_score` ≥ 2 required | 2.6+4 |
| 45 | **EMA20>EMA50 Trend Filter** | Only take breakouts in EMA trend direction | 2.6+4 |
| 46 | **HH/HL Structure Filter** | Only long if `higher_highs_ib`, only short if `lower_lows_ib` | 2.6+4 |
| 47 | **Validated Filter Stack** | Use the optimal stack from `ib_filter_stacks.parquet` (Phase 4c) | 4 |
| 48 | **Conviction Score v2** | Trade only when `conviction_score_v2` ≥ threshold (empirically tuned) | 4 |

### 10.11 Overnight / Cross-Session Strategies (existing data + Phase 2)

| # | Strategy | Filter | Phase |
|---|---|---|---|
| 49 | **IB-vs-Overnight Dominance** | `ib_vs_overnight_ratio` >1 → trade breaks aggressively; <1 → fade | 2+6 |
| 50 | **Profiler Trending Overnight** | `profiler_overnight_regime` = trending → favor breakouts | existing |
| 51 | **Herman Asia Size** | `herman_asia_type` = Small → favor trend; Large → caution | existing |
| 52 | **Herman PL Sweep** | `herman_pl_sweep` = True → reversal/continuation signal | existing |
| 53 | **9AM Candle Color** | `sb_nine_am_candle_green` aligned with bias → +1 confluence | existing |
| 54 | **Midpoint Bias** | `ib_close > ib_mid` → 82.3% high break edge | existing |

### 10.12 Quarterly Theory Strategies (existing data)

| # | Strategy | Filter | Phase |
|---|---|---|---|
| 55 | **10:00 Reversion Hour** | `qtr_10_hour_mode` = Reversion → fade breakouts in 10:00 hour | existing |
| 56 | **09:00 Expansion Hour** | `qtr_09_hour_mode` = Expansion → favor breakouts in 09:00 hour | existing |

### 10.13 SDEV Reversion Strategies (Phase 2.7)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 57 | **0.5 SD Reversion** | Fade at `sdev_05_price` touch | 1.0 SD | Open anchor | 2 |
| 58 | **1.0 SD Reversion** | Fade at `sdev_10_price` (84% edge) | 1.5 SD | Open anchor | 2 |
| 59 | **1.5 SD Reversion** | Fade at `sdev_15_price` (93% edge) | 2.0 SD | Open anchor | 2 |

### 10.14 External Research Additions (2026-07-25)

Concepts from external research (TrevorTrades stats, ACD/Fisher, VCP, order-flow labs, volatility-box, breadth literature) that were NOT in the prior catalog.

#### 10.14.1 Opening Range / ACD Framework (Mark Fisher)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 60 | **ACD Pivot Trade** | Mark Fisher ACD: A-up (OR high + 0.1×OR) holds → long; A-down holds → short | A-down / A-up level | C level (3× OR distance) | 2+6 |
| 61 | **ACD Failure (Key Reversal)** | Price breaks A-up then closes back below OR high → short (failed A-up) | A-up + buffer | OR low | 2+6 |
| 62 | **Pivot Range Break** | Fisher daily pivot range (prior H/L range) — break above pivot range = trend day | Opposite pivot | Next pivot | 2+6 |

**New derived fields:** `ib_or_acd_a_up` (OR5 high + 0.1×OR5 range), `ib_or_acd_a_down`, `ib_or_acd_c_level` (3×OR5 from open), `ib_or_acd_a_held` (bool — did price hold above A-up for ≥5 min).

#### 10.14.2 Volatility Contraction Pattern (Minervini VCP) applied to IB

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 63 | **VCP IB Contraction** | 3-day sequence of shrinking IB ranges (IB₁ > IB₂ > IB₃) → enter break of IB₃ | IB₃ opposite | Avg(IB₁,IB₂) range extension | 2+6 |
| 64 | **VCP Volume Dry-Up** | VCP contraction + IB volume < 60% of 20-day avg IB volume → high-prob break | IB opposite | 1.5× IB₃ range | 2+6 |

**New derived fields:** `ib_vcp_3day_contracting` (bool — IB₁>IB₂>IB₃), `ib_vcp_volume_ratio` (today's IB volume / 20d avg IB volume), `ib_vcp_setup` (contraction AND volume dry-up).

#### 10.14.3 Single Prints / Fast-Move TPO Strategy (Market Profile)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 65 | **Single-Print Reclaim** | If a single-print TPO column exists in upper IB (fast up-move) and price reclaims it after pullback → long (single prints = support, un-revisited) | Below single print | Next VAH / 1.0x | 2 |
| 66 | **Single-Print Fade** | If price re-enters a single-print zone from above (failed trend) → fade (single prints = excess, not value) | Single print + buffer | IB mid | 2 |

**New derived fields:** `ib_has_upper_single_print` (bool — TPO column with single count in upper IB), `ib_has_lower_single_print`, `ib_single_print_high`, `ib_single_print_low`.

#### 10.14.4 Order Flow / Delta Divergence (if tick/volume data available)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 67 | **CVD Bullish Divergence at IB Low** | Price makes IB low but cumulative delta makes higher low → bullish absorption → long | IB low − 0.25x | IB high | 6 (Tier 3) |
| 68 | **CVD Bearish Divergence at IB High** | Price makes IB high but CVD makes lower high → bearish exhaustion → short | IB high + 0.25x | IB low | 6 (Tier 3) |
| 69 | **Delta-Confirmed Break** | IB high break + positive delta spike (aggressive buyers) → take breakout | Opposite boundary | 1.0x | 6 (Tier 3) |
| 70 | **Delta-Fade Break (Absorption)** | IB high break but delta flat/negative (absorbed) → fade the break | IB high + 0.25x | IB mid | 6 (Tier 3) |

**Status:** Tier 3 — needs bid/ask volume or tick data (currently not in 1m parquet). Defer to Phase 6+ pending data pipeline. Proxy available: intrabar volume distribution if 1m data has up/down volume split (check `data/{SYM}_1m.parquet` columns during Phase 2 implementation).

#### 10.14.5 Relative Volume (RVOL) Filters

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 71 | **High-RVOL IB Break Filter** | Only take IB breakouts when IB RVOL ≥ 1.5 (high participation confirms break) | Opposite boundary | 1.0x | 2 |
| 72 | **Low-RVOL Fade Filter** | If IB RVOL < 0.7 (low participation), prefer fade/Play 3 (breakouts likely fail) | — | — | 2 |
| 73 | **RVOL-Scaled Position Sizing** | Position size = f(IB RVOL): RVOL<0.7 → 0.5×, 0.7–1.5 → 1.0×, >1.5 → 1.5× | — | — | 2+6 |

**New derived fields:** `ib_rvol` (IB volume / 20d avg IB volume — same as VCP volume ratio, reused), `ib_rvol_bucket` ("low"/"normal"/"high").

#### 10.14.6 Market Breadth Divergence (index futures only)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 74 | **Breadth-Confirmed Break** | IB high break + breadth (adv/dec ratio) expanding >1.2 → take break (broad participation) | Opposite boundary | 1.0x | 6 (Tier 3) |
| 75 | **Breadth Divergence Fade** | IB high break but breadth <0.8 (narrow rally) → fade the break (index driven by few stocks) | IB high + 0.25x | IB mid | 6 (Tier 3) |

**Status:** Tier 3 — needs intraday advance/decline data (NYSE/TICK). Available via Schwab/TOS RTD feed per `OPTIONS_INVENTORY.md`. Defer to Phase 6+ pending feed integration. Proxy: TICK readings at IB break time (already potentially capturable).

**New derived fields (Tier 3):** `breadth_ad_ratio_at_break`, `breadth_divergence` (bool — price break direction ≠ breadth direction).

#### 10.14.7 VIX Term Structure Regime Filter

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 76 | **Contango Breakout Bias** | VIX contango (front < back) → favor IB breakouts (calm regime, trend days) | Opposite boundary | 1.0x | 2+4 |
| 77 | **Backwardation Fade Bias** | VIX backwardation (front > back) → favor IB fades (stress regime, mean reversion) | — | — | 2+4 |
| 78 | **VIX Regime Position Scalar** | Position size scaled by VIX regime: low-vol → 1.0×, high-vol → 0.5× | — | — | 2+6 |

**New derived fields:** `vix_term_structure` ("contango"/"flat"/"backwardation" — from VIX futures, requires daily VIX futures data or proxy via VIX9D vs VIX), `vix_regime_intraday` ("low"/"mid"/"high" — already in `daily_context.vix_regime`, promoted to intraday filter). Tier 1 if VIX futures data already loaded; Tier 3 otherwise.

#### 10.14.8 IB Probability Stats (TrevorTrades findings — empirically validated baselines)

These aren't new strategies but **empirical priors** from a 10-year ES study (n=2,577) that should calibrate the regime classifier (§9.9) and Phase 4 baselines:

| Stat | Value | Use |
|---|---|---|
| High breakout (any time) | 67.1% | Baseline for breakout strategies |
| Low breakout (any time) | 72.4% | Baseline (slightly bearish skew) |
| Both breached | 40.1% | Warning: 40% of days break both — manage risk |
| Contained in IB | 0.6% | IB containment is essentially zero — always plan for a break |
| IB close above mid → high breakout | 83.5% | **Validates `sb_ib_midpoint_bias` strategy #54** |
| IB close below mid → low breakout | 94.9% | Strong bearish-confirmation edge |
| 25% extension hit | 85.3% | Most extensions reach 0.25x — set partials early |
| 50% extension hit | 69.5% | |
| 100% extension hit | 44.5% | Less than half reach full extension — don't hold all for 1.0x |
| Breakouts in first 30 min | 84.1% | **Time decay is steep — entries after 30min are late** |
| Breakouts in first 60 min | 91.8% | After 10:30, only 8% of breaks remain |
| Avg first breakout | 18 min | Median 2 min — early breaks dominate |

**Action:** Store these as `ib_empirical_baselines.json` in Phase 4 as the "no-filter" reference distribution. Every filter's lift is measured against THESE baselines, not against a naive 50%.

**New derived fields (categorical, from TrevorTrades):**

| Field | Computation | Use |
|---|---|---|
| `ib_range_size_class` 🆕 | "small" (<12pt ES-equiv) / "average" / "large" (>25pt) — per TrevorTrades thresholds | Position sizing: small=1.5×, large=0.75× conviction |
| `ib_break_urgency` 🆕 | "high" (break <30min) / "medium" (30–60) / "low" (>60) | High-urgency breaks = 84% of all breaks |
| `ib_extension_expectation` 🆕 | "likely_25" / "likely_50" / "unlikely_100" — categorical from extension probabilities | Sets default partial-profit ladder |

#### 10.14.9 IB High/Low Symmetry & Wicks

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 79 | **Wick-Dominant Extreme Fade** | If IB high is a single-bar wick (close far below high) and IB low is a body close → fade the high (it's not "accepted") | IB high + 0.1x | IB mid | 2 |
| 80 | **Body-Close Extreme Break** | If IB high close is near the high (body close, small upper wick) → high is "accepted" → favor breakouts | Opposite boundary | 1.0x | 2 |

**New derived fields:** `ib_high_wick_pct` ((ib_high − max(close at high bar)) / ib_range × 100), `ib_low_wick_pct`, `ib_high_body_close` (bool — close within 10% of high), `ib_low_body_close`.

#### 10.14.10 Gap-and-Crumb (Liquidity Sweep at IB)

| # | Strategy | Entry | Stop | Target | Phase |
|---|---|---|---|---|---|
| 81 | **IB High Sweep + Reclaim** | Price pokes above IB high then closes back inside → short (liquidity sweep / stop run) | IB high + 0.1x | IB mid | 2+6 |
| 82 | **IB Low Sweep + Reclaim** | Symmetric long | IB low − 0.1x | IB mid | 2+6 |
| 83 | **Sweep + MSS Confirmation** | IB sweep + market structure shift (close back through prior 1m high) → enter reversal | Sweep extreme | Opposite IB boundary | 2+6 |

**New derived fields:** `ib_high_swept` (bool — high exceeded intrabar but close back inside), `ib_low_swept`, `ib_sweep_reclaim_dir` (+1 low sweep bullish, −1 high sweep bearish, 0 none). This extends existing `false_break_high`/`false_break_low` with intrabar sweep detail.

**Updated grand total: 83 testable strategies** (3 existing core + 80 new across Phases 2–6, including 14 Tier-3 strategies pending tick/breadth/VIX-futures data). Each is a hypothesis testable against `ib_master_confluence_{SYM}.parquet` via Phase 4's validation harness. The 14 Tier-3 strategies are stubbed in the catalog and gated behind Phase 6+ data pipeline work.

### 10.15 Entry Techniques (building blocks)

Each strategy in §10.1–10.14 is built from one or more of these entry *techniques*. Enumerated separately so no entry mechanic is forgotten when assembling new strategies or testing variants.

| # | Technique | Mechanic | Used by | Phase |
|---|---|---|---|---|
| E1 | **Break-close entry** | Enter on first 1m close outside IB boundary | 1, 4, 5, 14, 16, 60 | existing |
| E2 | **Break-tick entry** | Enter on first tick beyond IB boundary (aggressive) | variant of 1 | existing |
| E3 | **Retest entry** | Enter on first pullback to IB high/low from outside | 2, 6 | existing |
| E4 | **Mid retest entry** | Enter on first pullback to IB mid after a break | variant of 2 | existing |
| E5 | **Scale-in ladder** | 3 entries at break / +0.25x / +0.5x (40/30/30) | 22 | 6 |
| E6 | **Time-qualified size** | Size by break bucket: full 10:30–10:45, half 10:45–11:30, skip 11:30–13:00, half 13:00–14:30, skip late | 23 | 6 |
| E7 | **Two-timeframe trigger** | 5m close confirms break → 1m pullback to 5m mid → enter on next 1m close above 5m bar high | 24 | 6 |
| E8 | **Failed-breakout reversal** | Price breaks high then closes back inside IB → enter opposite | 25, 61, 81 | 6 |
| E9 | **Opening-drive continuation** | Enter continuation of first 15-min direction | 26 | 6 |
| E10 | **Pre-IB telegraph** | Enter in direction of 9:25–9:30 close vs 9:25 open | 27 | 2+6 |
| E11 | **80%-rule mid-touch** | Enter long on mid touch (after high break) only if >80% IB time was above mid | 7, 8 | 2+6 |
| E12 | **ACD A-up/A-down hold** | Enter when price holds beyond A level for ≥5 min | 60 | 2+6 |
| E13 | **VCP contraction break** | Enter break of smallest of 3 contracting IBs | 63, 64 | 2+6 |
| E14 | **Single-print reclaim** | Enter on reclaim of a single-print TPO column | 65 | 2 |
| E15 | **Sweep + reclaim** | Enter after IB extreme swept then close back inside | 81, 82, 83 | 2+6 |
| E16 | **Sweep + MSS** | Sweep + market structure shift confirmation | 83 | 2+6 |
| E17 | **Body-close break** | Only enter break when extreme was a body-close (accepted), not a wick | 80 | 2 |
| E18 | **Wick-dominant fade** | Fade wick-dominant extreme (unaccepted) | 79 | 2 |
| E19 | **CVD divergence entry** | Enter reversal on price/CVD divergence at IB extreme | 67, 68 | 6 (Tier 3) |
| E20 | **Delta-confirmed break** | Take break only with positive delta spike | 69 | 6 (Tier 3) |
| E21 | **Post-news entry** | Wait N min after 10:00/10:30 release then enter | 39 | 2.5 |

**21 entry techniques total** (8 existing, 13 new). Each can be swapped into any strategy in §10 as a parameter, enabling combinatorial strategy-space testing in Phase 4/6.

### 10.16 Stop-Loss Techniques (building blocks)

| # | Technique | Mechanic | Used by | Phase |
|---|---|---|---|---|
| S1 | **Opposite IB boundary** | Stop at opposite IB high/low (current default, 1.0× range) | 1, 2, 3 | existing |
| S2 | **MAE-calibrated (P95 winners)** | Stop at P95 of winning-trade MAE from `ib_play_detail` | 18, 28 | 5.1 |
| S3 | **MAE-calibrated (P99 winners)** | Wider P99 variant for higher win rate | variant | 5.1 |
| S4 | **AVWAP stop** | Stop at `ib_vwap` (or AVWAP(09:30)) instead of IB boundary | 10, 33 | 2+6 |
| S5 | **3-day composite stop** | Stop at 3-day composite high/low | 14, 16 | 2+6 |
| S6 | **VCP range stop** | Stop at avg(IB₁,IB₂) opposite | 63, 64 | 2+6 |
| S7 | **Single-print stop** | Stop below/above the single-print zone | 65, 66 | 2 |
| S8 | **Sweep-extreme stop** | Stop just beyond the sweep extreme + buffer | 81, 82, 83 | 2+6 |
| S9 | **OR5 stop** | Stop at OR5 opposite (for opening-drive entries) | 26 | 2+6 |
| S10 | **ACD stop** | Stop at A-down (long) / A-up (short) level | 60 | 2+6 |
| S11 | **VWAP-2σ band stop** | Stop at AVWAP ±2σ band | — | 2.6 |
| S12 | **SDEV stop** | Stop at 1.0/1.5/2.0 SD level for SDEV-reversion strategies | 57, 58, 59 | 2 |
| S13 | **ATR-based stop** | Stop at N×ATR from entry (regime-scaled) | — | 2 |
| S14 | **Time-based invalidation** | If trade not profitable by T minutes → exit (not a stop per se but a risk control) | 30 | 5.2 |
| S15 | **Trailing by IB fractions** | +0.25x→BE, +0.5x→+0.25x, +0.75x→+0.5x, +1.0x→+0.5x trail, >1.0x→0.5x trail | 29 | 6 |
| S16 | **Break-even after +0.25x** | Move stop to BE once +0.25× IB reached | variant of S15 | 6 |
| S17 | **Liquidity-stop (below prior-day low / above PDH)** | Stop beyond the relevant liquidity level | — | 6 |

**17 stop techniques total** (1 existing default, 16 new). Stop selection is a per-strategy parameter testable in Phase 4 (each stop × each entry × each strategy = full combinatorial sweep).

### 10.17 Take-Profit Techniques (building blocks)

| # | Technique | Mechanic | Used by | Phase |
|---|---|---|---|---|
| T1 | **Fixed extension 0.5x / 1.0x / 1.5x** | Exit at IB range × multiplier | 1, 2, 3 | existing |
| T2 | **Opposite IB boundary** | Target opposite IB high/low (full range) | variants of 1 | existing |
| T3 | **IB mid** | Target mid (for fade/reversion plays) | 3, 6, 13, 25, 79 | existing |
| T4 | **Partial profit ladder** | 40% at 0.5x / 30% at 1.0x / 20% at 1.5x / 10% trailing | 22, 32 | 5.3 |
| T5 | **VWAP-cross exit** | Exit if price re-crosses `ib_vwap` after break (failed break) | 33 | 6 |
| T6 | **Liquidity target (next PDH/PDL/P12)** | Target next liquidity level from `reference_levels` | 34 | 6 |
| T7 | **3-day composite target** | Target opposite 3-day composite boundary | 14, 16 | 2+6 |
| T8 | **VCP expansion target** | Target avg(IB₁,IB₂) extension | 63, 64 | 2+6 |
| T9 | **ACD C level** | Target at 3×OR distance from open (Fisher) | 60 | 2+6 |
| T10 | **Single-print reclaim target** | Target next VAH / 1.0x after single-print reclaim | 65 | 2 |
| T11 | **Sweep opposite boundary** | Target opposite IB boundary for sweep-reversal | 81, 82, 83 | 2+6 |
| T12 | **SDEV open anchor** | Target session open (0 SD) for SDEV fades | 57, 58, 59 | 2 |
| T13 | **Trailing stop only** | No fixed target; trail until trailing stop hit | trend-day holds (36) | 6 |
| T14 | **Time-decay ladder exit** | Exit 50% at 60–90 min, rest 90–120 min, all by 13:00 | 30 | 5.2 |
| T15 | **Session-boundary exit** | Reduce at 11:30, re-eval 13:30, exit all 15:50 (ADR-020) | 31 | 6 |
| T16 | **Extension-probability target** | Use `ib_extension_expectation` to set ladder: likely_25 → TP at 0.25x, unlikely_100 → don't hold for 1.0x | 32 variant | 2 |
| T17 | **MAE-scaled target** | Target = 2× the MAE-calibrated stop distance (2:1 R minimum) | — | 5.1 |
| T18 | **Next-volume-node target** | Target `ib_vol_poc_price` on opposite side (next high-volume node) | variant of 11 | 2 |
| T19 | **Round-number / strike target** | Target nearest 00/50 handle or large OI strike (OPEX weeks) | — | 6 |
| T20 | **Runner after partial** | 10% position trailing after 90% taken at fixed targets | 22, 32 | 5.3 |

**20 take-profit techniques total** (3 existing, 17 new). Like stops, TP selection is a per-strategy parameter.

### 10.18 Combinatorial Strategy Space

The full strategy space is the cross-product of entry × stop × TP techniques:

$$\text{strategies} = \sum_{E \in \text{Entries}} \sum_{S \in \text{Stops}} \sum_{T \in \text{TPs}} \mathbb{1}[\text{compatible}(E,S,T)]$$

With 21 entries × 17 stops × 20 TPs = **7,140 theoretical combinations**. Most are incompatible (e.g., a fade entry + a full-extension target). Phase 4's validation harness tests the *compatible subset* per play per regime, not the full grid. This is why the techniques are enumerated separately: the catalog in §10.1–10.14 lists **validated configurations**, while §10.15–10.17 list the **building blocks** for future exploration.

---

## 11. Conviction Score — Final Design

### 11.1 Why the Old Score Was Wrong for Filter Testing

The original `conviction_score` (§7.3) is a **fixed-weighted composite** with hand-tuned integer bonuses/penalties. This breaks the filter-testing goal in three ways:

1. **Non-decomposable** — once summed, you can't tell which filter drove the score.
2. **Weights asserted, not validated** — a +2 bonus may have zero or negative edge.
3. **Bypasses Phase 4** — Phase 4 validates filters individually and in combos, but the composite pre-bakes a fixed weighting that ignores empirical results.

### 11.2 New Architecture

| Layer | What it stores | Who computes |
|---|---|---|
| **Phase 3 (master confluence)** | Raw filter flags only (`profiler_overnight_regime`, `break_vs_avwap_0930`, `ib_news_distorted`, etc.) — NO composite | Phase 3 join |
| **Phase 4a (single-filter)** | Per-filter lift, WR, expectancy, N, significance | `ib_filter_effectiveness.parquet` |
| **Phase 4b (independence)** | Pairwise correlations, redundancy drops | `ib_filter_correlation.parquet` |
| **Phase 4c (stacks)** | Optimal filter combos per play via greedy forward selection | `ib_filter_stacks.parquet` |
| **Phase 4d (weights)** | Validated weight per filter (lift-weighted or logistic coef) | `ib_conviction_weights.parquet` |
| **Phase 4 → Phase 3 (join back)** | `conviction_score_v2` (0–1, empirical) + `conviction_filters_active` (which fired) written to master confluence | Phase 4 |

### 11.3 How to Test Filters / Combos with This Design

| Question | How to answer |
|---|---|
| Does filter F improve WR for play P? | Slice `ib_master_confluence` by F=True/False, compare play P WR — or read `ib_filter_effectiveness.parquet` |
| Are filters F1 and F2 redundant? | Read `ib_filter_correlation.parquet` (rho > 0.85 = redundant) |
| What's the best filter combo for play P? | Read `ib_filter_stacks.parquet` (greedy-selected, N-shrinkage-bounded) |
| What's today's conviction? | Read `conviction_score_v2` (sum of active filters × validated weights) |
| Does the old hand-tuned score beat the empirical one? | Compare `conviction_score_naive` vs `conviction_score_v2` as predictors of play outcomes (Phase 4 sanity check) |

### 11.4 Key Constraint

**Never collapse filters before Phase 4 validates them.** The master confluence table must keep every filter as its own column so the validation harness can test any subset, combination, or interaction. The conviction score is the *output* of validation, not the *input*.

---

## 12. Revised Execution Order (with §10/§11)

```
Phase 1 (ib_aggregates.py)           — aggregate stats from existing tables
    ↓
Phase 2 (ib_derived_fields.py)       — + §9.2 volume-weighted, §9.5 OR5, §9.6 80%-rule,
    ↓                                  §9.8 pre-telegraph, mid-magnet fields
Phase 2.5 (ib_news_opex.py)          — news timing + OPEX phases
    ↓
Phase 2.6 (ib_avwap_trend.py)        — anchored VWAP + trend confirmations
    ↓
Phase 3 (ib_master_confluence.py)    — join ALL fields; store raw filter flags only
    ↓                                  (no composite conviction score here)
Phase 4 (ib_validate_confluences.py)— 4a single-filter, 4b independence,
    ↓                                  4c stacks, 4d empirical weights → conviction_score_v2
Phase 5 (ib_mae_stops / time_decay / — exit mechanics (calibrated stops, ladders)
         ladder_optimizer / break_speed)
    ↓
Phase 6 (ib_regime_classifier +      — regime router + entry/exit modules + pre-break
         ib_entry_modules + ib_exit_modules + ib_pre_break)
    ↓
Validation: run all §10 strategies through PropFirmSimulator (ADR-021)
```
