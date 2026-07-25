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
    'conviction_score',          # 0-10 composite
    'bias_agreement_count',      # How many bias variants agree (0-4)
    'suggested_play',            # Best play for this regime
    'suggested_direction',       # +1/-1
    'suggested_expectancy',      # Expected R
}
```

### Phase 4: Validation Harness (P1 — 2 days)

**Script:** `scripts/edgeful/ib_validate_confluences.py`

For each confluence signal, measure its predictive power:

```python
# For each filter F and each play P:
#   1. Split data: F=True vs F=False
#   2. Measure: WR, expectancy, N for each split
#   3. Measure: filter precision (P(loss | F=True)), recall (P(F=True | loss))
#   4. Measure: independence between filters (correlation of filter activations)
#   5. Output: ranked list of filters by lift

# For filter combinations:
#   1. Test all pairs, triples of independent filters
#   2. Measure combined WR and expectancy
#   3. Identify the optimal filter stack per play per regime
```

**Output:** `data/derived/ib_filter_effectiveness.parquet`

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

### 7.3 Conviction Score (Phase 3 — updated with news/OPEX/AVWAP)

```python
def compute_conviction_score(row):
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
