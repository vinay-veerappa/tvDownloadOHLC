# HitTracking v1.0 — Library Specification

| Field          | Value                                     |
| -------------- | ----------------------------------------- |
| **Status**     | v1.0 spec, ready for implementation       |
| **Supersedes** | `HitTracking.md` (context doc, v0.1)      |
| **Library**    | `vveerappa/HitTracking/1`                 |
| **Depends on** | `vveerappa/StatsLib/3`                    |
| **Platforms**  | Pine v6. NinjaScript out of scope for v1. |
| **Owner**      | vveerappa                                 |

---

## 1. Purpose

Replace the per-indicator hit-rate tracking implementations in Daily Profiler, Probability Engine, MFE Tracker, and Daily NY Levels with a single shared library. Callers register what they want tracked, drive arm/tick/disarm explicitly, and query computed stats at display time. The library owns all sample collection, availability semantics, history storage, filtering, and statistics computation. The calling indicator owns only the registration vocabulary, the arming policy, and the display.

---

## 2. Architecture

### 2.1 Layering

```
┌─────────────────────────────────────────────────┐
│  Indicator (Profiler, NY Levels, MFE Tracker)   │
│  - registers instances                          │
│  - drives arm / update_target / tick / disarm   │
│  - queries stats at display time                │
│  - renders output                               │
└────────────────┬────────────────────────────────┘
                 │ uses
                 ▼
┌─────────────────────────────────────────────────┐
│  HitTracking/1                                  │
│  - state machine (caller-held HitTracker UDT)   │
│  - 3-state availability                         │
│  - history storage with cap                     │
│  - filtering (DOW, tag)                         │
│  - delegates streak/rate math                   │
└────────────────┬────────────────────────────────┘
                 │ uses
                 ▼
┌─────────────────────────────────────────────────┐
│  StatsLib/3                                     │
│  - f_streak_stats                               │
│  - f_rolling_win_rate                           │
│  - percentile / mean / mode primitives          │
└─────────────────────────────────────────────────┘
```

`HitTracking` has no knowledge of clocks, time ranges, or session detection. Callers that want time-windowed sessions use `RangeSessionLib` to drive arm/disarm; callers that want condition-armed sessions (e.g., post-breakout) use their own logic. Either way, the library's contract is the same.

### 2.2 State ownership

Pine libraries cannot own state that crosses calls; `var` inside a library function persists per call site in the host script. The library therefore stores no state of its own. The calling indicator holds a single `HitTracker` UDT (created once at startup) and passes it into every library call. The library reads from and mutates the UDT in place.

This means each indicator that imports the library has its own private state, automatically. There is no cross-indicator sharing in Pine — that's a NinjaScript-tier feature deferred to a later version.

### 2.3 Lifecycle

Per bar, in order:

1. **Setup** (once, on `barstate.isfirst`): caller creates the `HitTracker` and registers each instance.
2. **Arm** (when caller's session start condition fires): caller calls `f_arm(tracker, session_key)`.
3. **Update targets** (every bar between arm and disarm): caller calls `f_update_target` for each registered instance, passing the current target value or `na` if the level doesn't yet exist.
4. **Tick** (every bar between arm and disarm, after target updates): caller calls `f_tick(tracker)`. The library evaluates predicates on all currently armed instances and records the first hit.
5. **Disarm** (when caller's session end condition fires): caller calls `f_disarm(tracker, session_key, tag)`. The library flushes a sample column for every instance in that session.
6. **Query** (any time, typically at display): caller calls `f_query(...)` and renders the returned `HitStats`.

The arm/disarm pair _defines_ a session — instances registered under the same `session_key` are flushed together as a single column. Instances registered under different `session_key`s are flushed independently.

---

## 3. Public API

### 3.1 Types

```pine
// Hit kind discriminator constants — exported as int values
KIND_LEVEL_WICK     = 0
KIND_LEVEL_BODY     = 1
KIND_LEVEL_CROSS_UP = 2
KIND_LEVEL_CROSS_DN = 3
KIND_THRESH_GTE     = 4
KIND_THRESH_LTE     = 5

// Default registration parameters
DEFAULT_MAX_DAYS        = 500
DEFAULT_READY_THRESHOLD = 2
DEFAULT_BUCKET_MS       = 300000  // 5 minutes

// Output of every f_query call.
type HitStats
    bool   ready                       // sample_n >= ready_threshold
    int    sample_n                    // count after filter, window, unavailable-strip
    float  rate_pct                    // 100 * hits / sample_n; na if sample_n = 0
    int    current_streak              // length of trailing streak in slice
    bool   current_streak_is_hit       // direction of trailing streak
    int    max_hit_streak              // longest hit run in slice
    int    max_miss_streak             // longest miss run in slice
    float  avg_hit_streak              // mean length of completed hit runs
    float  avg_miss_streak             // mean length of completed miss runs
    float  time_to_hit_median_ms       // over hit days only; na if no hits in slice
    float  time_to_hit_mean_ms         // over hit days only; na if no hits
    float  time_to_hit_mode_bucket_ms  // bucket midpoint, bucket size at registration
    bool   today_in_scope              // true if session is armed and target seen today
    bool   today_hit                   // true if hit fired today (only meaningful if today_in_scope)
    int    today_time_to_hit_ms        // ms from arm to first hit today; -1 if no hit yet

// Per-session storage. One per distinct session_key.
// Held inside HitTracker; not directly manipulated by callers.
type SessionStorage
    string         session_key
    array<string>  instance_keys
    array<int>     hit_kinds
    array<int>     bucket_ms_values
    array<int>     ready_thresholds
    int            max_days_cap          // session-level (max across instances)

    // Live state — common to all instances in this session
    bool           sess_armed
    int            sess_arm_time_ms
    int            sess_arm_dow

    // Per-instance live state
    array<bool>    live_hit
    array<int>     live_hit_times_ms
    array<float>   live_targets
    array<float>   live_prev_targets
    array<bool>    live_target_seen

    // History — rows = instances in this session, cols = flushed days
    matrix<int>    samples_mat           // 1 = hit, 0 = miss, -1 = unavailable
    matrix<int>    time_to_hit_mat       // ms offset from arm; -1 if miss/unavailable

    // Per-day metadata, one entry per flushed column
    array<int>     dow_history
    array<string>  tag_history

// Top-level state object held by the calling indicator.
type HitTracker
    array<SessionStorage> sessions
```

### 3.2 Functions

```pine
// Construction
f_new() => HitTracker

// Registration (call once per instance, on barstate.isfirst)
f_register(HitTracker tracker, string instance_key, string session_key,
           int kind,
           int max_days = 500, int ready_threshold = 2, int bucket_ms = 300000)
    => void

// Lifecycle (caller-driven)
f_arm(HitTracker tracker, string session_key) => void
f_update_target(HitTracker tracker, string instance_key, string session_key, float target_value) => void
f_tick(HitTracker tracker) => void
f_disarm(HitTracker tracker, string session_key, string tag = "") => void

// Query (call anytime, typically on barstate.islast)
f_query(HitTracker tracker, string instance_key, string session_key,
        int window = 0, int dow = 0, string tag = "", bool include_today = false)
    => HitStats
```

Parameter semantics:

| Param                   | Behavior when default / sentinel                                            |
| ----------------------- | --------------------------------------------------------------------------- |
| `max_days = 500`        | Storage cap. Session-level cap = max across all registered instances.       |
| `ready_threshold = 2`   | Per-instance warm-up. `ready` flag flips after this many in-slice samples.  |
| `bucket_ms = 300000`    | 5-min buckets for time-of-hit mode.                                         |
| `tag = ""` (in disarm)  | No tag recorded for the day.                                                |
| `window = 0` (in query) | All available history.                                                      |
| `dow = 0` (in query)    | No DOW filter. Pine `dayofweek` returns 1–7, so 0 is unambiguous.           |
| `tag = ""` (in query)   | No tag filter.                                                              |
| `include_today = false` | Historical only. Today's live state excluded from rate, streak, time stats. |

---

## 4. Hit definition kinds

| `kind` | Constant              | Predicate                                      | Notes                                                         |
| ------ | --------------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| 0      | `KIND_LEVEL_WICK`     | `low <= target <= high`                        | **Default for level-style.** Honest "did price go there."     |
| 1      | `KIND_LEVEL_BODY`     | `min(open,close) <= target <= max(open,close)` | Stricter. Used by current Profiler implementation.            |
| 2      | `KIND_LEVEL_CROSS_UP` | `close > target and close[1] <= target`        | Directional close-side cross upward.                          |
| 3      | `KIND_LEVEL_CROSS_DN` | `close < target and close[1] >= target`        | Directional close-side cross downward.                        |
| 4      | `KIND_THRESH_GTE`     | `high >= target`                               | **Default for threshold-style.** Did the bar reach or exceed. |
| 5      | `KIND_THRESH_LTE`     | `low <= target`                                | Did the bar fall to or below.                                 |

The `target` value comes from the caller's most recent `f_update_target` call. Predicates evaluate `na` targets as no-op (no fire). For cross kinds, `target` and the previous bar's `target` are both checked — if either is `na`, no fire.

---

## 5. Three-state availability model

Each flushed column entry per (instance, session, day) is one of three values:

| Value       | Stored as | Meaning                                                                                       |
| ----------- | --------- | --------------------------------------------------------------------------------------------- |
| Hit         | `1`       | Predicate fired at least once during the armed window.                                        |
| Miss        | `0`       | Predicate never fired, **and** the target was non-`na` at some point during the armed window. |
| Unavailable | `-1`      | Target was `na` for the entire armed window, or the session was never armed today.            |

**Auto-derivation rule:** the library tracks `live_target_seen` per instance. It flips to `true` the first time `f_update_target` receives a non-`na` value while the session is armed. At `f_disarm` time:

- If `live_target_seen` is `true` and `live_hit` is `true` → **1**
- If `live_target_seen` is `true` and `live_hit` is `false` → **0**
- If `live_target_seen` is `false` (or session never armed) → **-1**

Unavailable days are excluded from both numerator and denominator of every statistic. The caller does not need to call `mark_available` or anything analogous — the model is fully derived from `f_update_target` honesty (caller passes `na` whenever the level genuinely doesn't exist yet).

This fixes the bias bug in the current Profiler implementation, which writes only 0/1 and silently inflates the denominator with not-yet-existed levels.

---

## 6. Filtering

Two filter dimensions, both query-time:

**DOW** — captured automatically at `f_arm` time using the bar's `dayofweek` (1=Sunday … 7=Saturday). Stored per flushed column. Query parameter `dow` (1–7) restricts to matching days; `dow = 0` (default) means no filter.

**Tag** — single string supplied by caller at `f_disarm` time. Caller decides what tags mean (regime label, trade outcome, custom condition). Defaults to `""` (no tag). Query parameter `tag` (any string) restricts to matching days; `tag = ""` (default) means no filter.

Combining filters AND-conditions them: `query(window=60, dow=2, tag="TRENDING")` returns stats over the last 60 Mondays-with-TRENDING-tag — and "60" here is _after_ filtering, not before, so the slice walks history backwards collecting matching days until 60 are found or history is exhausted.

The "outcome-conditional cross-reference" feature in current Profiler (rate of level X given trade outcome Y) collapses cleanly into this model: caller computes the outcome at end of session and passes it as the disarm tag.

---

## 7. Storage and query windows

Two distinct concepts, one for memory, one for analysis scope.

**Storage cap** is set at registration via `max_days`. The session-level cap equals the max across all instances registered to that session_key. Once the matrix exceeds this column count, the oldest column is dropped. Defaults to 500.

**Query window** is set at query time via `window`. When `window > 0`, the query walks history backwards from the most recent flushed column and collects up to `window` non-unavailable, filter-matching samples. `window = 0` (default) means unbounded. The same windowed slice feeds rate, streaks, and time-of-hit stats — they're internally consistent.

This separation supports the 20/40/60-day comparison pattern naturally:

```pine
stats_20 = HitTracking.f_query(tracker, "PDH", "asia", window = 20)
stats_40 = HitTracking.f_query(tracker, "PDH", "asia", window = 40)
stats_60 = HitTracking.f_query(tracker, "PDH", "asia", window = 60)
```

No multi-window convenience API in v1 — three calls is fine.

---

## 8. Today vs history

History and today's live state are stored separately and never silently merged.

`include_today = false` (the default) returns stats over flushed history only. The displayed numbers are stable and reflect the predict-today-from-history use case.

`include_today = true` appends today's live state to the slice (as one extra sample) before computing stats. Useful only when the display is explicitly "history vs today" — and only meaningful between `f_arm` and `f_disarm`. After disarm, today's sample is in history; the flag has no effect.

Independently of `include_today`, every query returns `today_hit` and `today_time_to_hit_ms` slots — these always reflect the current live state and let callers display "today" alongside the historical view without polluting the historical numbers.

---

## 9. Time-of-hit semantics

**First hit only.** When the predicate fires for the first time in an armed session, the library records `time` (current bar's ms timestamp) as `live_hit_times_ms`. Subsequent fires within the same session are ignored.

**Measured from arm.** At disarm, `time_to_hit_offset = live_hit_times_ms - sess_arm_time_ms`. This is what gets stored in `time_to_hit_mat`. For breakout-armed sessions, the offset is from breakout, not from start-of-day — which is the meaningful quantity.

**Stats over hit days only.** Median, mean, and mode are computed only over days where the sample is `1`. Miss days and unavailable days don't contribute.

**Mode bucketing.** Raw timestamps don't cluster, so mode requires bucketing. Default bucket size is 5 minutes (300000 ms), set per-instance at registration. The returned `time_to_hit_mode_bucket_ms` is the bucket's lower edge (e.g., `1500000` for the 25–30 minute bucket).

---

## 10. Caller responsibilities

The library is internally honest about state, but it cannot enforce these caller-side invariants. Violating them produces wrong numbers, not crashes.

**Set `max_bars_back` high enough.** The library's history is rebuilt by replaying bar history on every reload. If `max_bars_back` is too low, the matrix won't fill. A typical setting is `max_bars_back(time, 5000)` for daily-flushed sessions with a 500-day cap on a 1-minute chart. Callers must set this themselves; the library can't.

**Keep arm and tag decisions deterministic across replays.** If the caller's `f_arm` condition or `f_disarm` tag depends on real-time-only data (random, live tick state, anything that changes between replays), the rebuilt history will diverge from the previous run. The bias is silent. Predicates inside the library are deterministic by construction; the caller's lifecycle drivers must be too.

**Don't change registration parameters between runs.** If `kind`, `max_days`, or `bucket_ms` change for the same instance between sessions, the rebuilt history is mixed-semantics. Either keep these stable or document the migration explicitly. Adding new instances mid-history is fine — they get unavailable padding for prior days.

**Honor `na` on `update_target`.** The 3-state availability model depends on the caller passing `na` whenever the level genuinely doesn't exist yet. Passing `0.0` or any sentinel non-`na` value when the level is logically not in scope will be tracked as a miss, biasing the rate downward.

**Tick after update_target, before disarm.** The order within a bar must be:

1. `f_arm` (if applicable, only on session start)
2. `f_update_target` for each instance
3. `f_tick`
4. `f_disarm` (if applicable, only on session end)

Calls outside this order produce defined but probably-not-what-you-want behavior.

---

## 11. Delegation to StatsLib

To avoid duplication, the library delegates to `StatsLib/3` for these primitives:

| HitTracking computes        | StatsLib function used                        | What HitTracking does locally                            |
| --------------------------- | --------------------------------------------- | -------------------------------------------------------- |
| Streaks (current, max, avg) | `f_streak_stats(array<bool>)`                 | Strip unavailables, build bool array from filtered slice |
| Rolling rate over window    | `f_rolling_win_rate(array<bool>, window)`     | Same prep                                                |
| Percentile-style time stats | `array.percentile_nearest_rank` (Pine native) | Sort, median, mean, bucket-mode                          |

What HitTracking implements locally (no StatsLib equivalent):

- The state machine (arm, tick, disarm, registration)
- 3-state availability with auto-derivation from `na` tracking
- DOW + tag filtering
- The 5 hit-kind predicates
- Per-instance / per-session bookkeeping

StatsLib stays domain-agnostic. HitTracking does the unavailable-stripping before handing arrays over. No StatsLib changes are needed for v1.

---

## 12. Usage examples

### 12.1 Time-windowed (Profiler-style)

```pine
import vveerappa/HitTracking/1 as HT
import vveerappa/RangeSessionLib/6 as RS

// Setup once
var HT.HitTracker tracker = HT.f_new()
if barstate.isfirst
    HT.f_register(tracker, "PDH",     "asia", HT.KIND_LEVEL_WICK)
    HT.f_register(tracker, "PDL",     "asia", HT.KIND_LEVEL_WICK)
    HT.f_register(tracker, "P12_high","asia", HT.KIND_LEVEL_WICK)  // not yet finalized in Asia
    // ... etc

// Drive lifecycle from session detection
bool asia_started = RS.f_is_new_session_pine("1930-0229:1234567", "America/New_York")
bool asia_in      = RS.f_in_session_pine    ("1930-0229:1234567", "America/New_York")
bool asia_ended   = not asia_in and asia_in[1]

if asia_started
    HT.f_arm(tracker, "asia")

if asia_in
    HT.f_update_target(tracker, "PDH",      "asia", pd_h)            // real value
    HT.f_update_target(tracker, "PDL",      "asia", pd_l)
    HT.f_update_target(tracker, "P12_high", "asia", p12_finalized ? p12_h : na)  // na before 06:00
    HT.f_tick(tracker)

if asia_ended
    HT.f_disarm(tracker, "asia", current_regime)  // tag with regime label

// Display
if barstate.islast
    stats = HT.f_query(tracker, "PDH", "asia", window = 60)
    label.new(bar_index, high, str.format("PDH {0,number,#.#}% ({1}/{2})",
        stats.rate_pct, stats.current_streak, stats.sample_n))
```

### 12.2 Breakout-armed (NY Levels-style)

```pine
import vveerappa/HitTracking/1 as HT

var HT.HitTracker tracker = HT.f_new()
if barstate.isfirst
    HT.f_register(tracker, "OR_high_retest", "post_breakout", HT.KIND_LEVEL_WICK)
    HT.f_register(tracker, "OR_low_retest",  "post_breakout", HT.KIND_LEVEL_WICK)

// Caller's existing breakout logic decides arming
if breakout_just_fired and not session_already_armed_today
    HT.f_arm(tracker, "post_breakout")
    session_already_armed_today := true

if session_already_armed_today and not session_disarmed_today
    HT.f_update_target(tracker, "OR_high_retest", "post_breakout", or_high)
    HT.f_update_target(tracker, "OR_low_retest",  "post_breakout", or_low)
    HT.f_tick(tracker)

if end_of_trading_day and session_already_armed_today and not session_disarmed_today
    HT.f_disarm(tracker, "post_breakout", breakout_direction)  // tag = "long" or "short"
    session_disarmed_today := true

// Display: rate of OR-high retest given long breakouts, last 40 sessions
if barstate.islast
    stats = HT.f_query(tracker, "OR_high_retest", "post_breakout",
                       window = 40, tag = "long")
    // ... render
```

Both consumers use identical primitives. The breakout case is not a special mode; it's just a different driver of arm/disarm.

---

## 13. Profiler migration notes

The current Daily Profiler implementation has two issues that this library design fixes:

**Issue 1: missing 3-state availability.** `f_flush_session` writes only 0 or 1 to the matrix. Levels that don't exist during a session (P12 during Asia, NY1 Mid during Asia/London/NY1) get written as 0 every day, polluting the denominator and biasing rates downward. Profiler papers over this on the display side by routing queries to a "best session" via `f_hr_best_sess`, but the underlying matrix is still wrong. Migration: pass `na` from `f_update_target` whenever the level doesn't yet exist; the library writes -1 sentinels and excludes those days from the rate.

**Issue 2: today's live state polluting historical rate.** `f_hr_live_v3` adds today's live flag into both numerator and denominator while the session is live, causing the displayed number to drift mid-bar. Migration: leave `include_today = false` (the default) for the historical view; render `today_hit` separately if a "today vs history" comparison is wanted.

Migration path: leave Profiler on its current implementation until ready. When migrating, expect the displayed rates to change — they were biased before, they'll be correct after. Validate against the underlying Profiler matrix by spot-checking a few levels before publishing.

No other current Profiler features lose functionality. Streak, max-up, max-down, the rate panel, label formatting — all map directly onto the v1 query slots.

---

## 14. Deferred for future versions

Explicit list of what v1 does not cover, so callers are not surprised:

| Feature                                     | Reason                                               | Likely version                     |
| ------------------------------------------- | ---------------------------------------------------- | ---------------------------------- |
| Multi-tag filtering                         | Single string tag suffices for current use cases     | v2 if needed                       |
| Numeric range filters                       | No current consumer                                  | v2+                                |
| Compound filter expressions (OR, NOT)       | No current consumer                                  | v2+                                |
| Confidence band / standard error on rate    | Not requested                                        | v2 if needed                       |
| Rate trend (rising/falling)                 | Caller can derive from two windowed queries          | Not planned                        |
| `time_to_hit_pXX` percentiles beyond median | Not requested                                        | Easy add when needed               |
| Last-hit / last-miss date slots             | Not requested                                        | Easy add                           |
| Multi-window query convenience              | Three plain queries are fine                         | Not planned                        |
| Cross-symbol correlation                    | Different module entirely                            | Different project                  |
| ML/predictive layer                         | Out of scope — this is descriptive stats             | Different project                  |
| Historical seeding from research data       | Caller already has matrix replay; sufficient for v1  | v2 if research-baked path is built |
| **NinjaScript port**                        | Different platform; needs its own persistence design | NT8 v1, separate effort            |

---

## 15. Document status

| Version | Date       | Changes                                                                                                                               |
| ------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 1.0     | 2026-05-02 | Initial spec. Closes all open questions from `HitTracking.md` v0.1 context doc. Two known Profiler bugs documented for migration day. |
