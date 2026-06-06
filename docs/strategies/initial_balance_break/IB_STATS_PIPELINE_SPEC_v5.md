# Multi-Session Initial Balance (IB) Statistics — Edgeful Pipeline Spec

**Purpose.** Compute extensive IB statistics across multiple intraday sessions, multiple
bias-definition variants, and multiple conditioning regimes, over ~20 years of 1-minute
data (ES, NQ, YM, RTY, CL, GC). This mirrors and extends the on-chart Pine indicator
(`IB Stats & Extensions`), which is the eyeball tool; this pipeline is the rigorous
A/B harness.

This document is the design reference. It is intentionally implementation-light on code
and heavy on definitions, because the value is in pinning down *exactly* how each stat is
computed so Pine and DuckDB produce matching numbers.

---

## Changelog — v5

- **§1.2 / §1.4 (new):** Foreign slots (Tokyo, London) are now **event-anchored**, not fixed
  to an ET clock. The anchoring is a ±1h ET-clock shift driven by the US-DST flag — *all data
  stays in UTC→ET as today; no JST/London timezone math enters the pipeline.* Both an
  `ET_fixed` and an `event_anchored` variant are materialized over identical dates so §3.10
  can measure whether anchoring changes the numbers. Reports always print ET and carry a
  `dst_regime` label.
- **§1.3:** Outcome stats are still measured only in the outcome window (unchanged), but we
  now **also monitor the formation window** for the level-touch / front-running layer (§2.10).
  Headline stats do not move; formation monitoring is an additive layer.
- **§2.5:** Formation bias is split into **two independent variants** (`firstreach` /
  `lasttouch`) and A/B'd. NY-AM `bias_fvg_1011` redefined to the **ICT 10:00 macro window
  (09:50) through 11:00**, with the FVG level persisting for later entries and a leakage guard
  on grading.
- **§2.6:** Bias grading is **order-sensitive** (target before opposite-boundary close, not
  mere occurrence) + leakage guard for FVG variants that finalize inside the outcome window.
- **§2.8:** Play 3 fill made explicit (touch-back required; no-setup if never returns).
- **§2.10 (new):** Level-touch tracking for IB quarters {0, 25, 50, 75, 100}% + front-running
  mid (lock timing, formation-phase touches, `early_mid_event`).
- **§2.11:** FVG **reuse** tracking (v5) — **superseded in v6**: reuse catalog and `ib_fvg_detail` removed; FVG is captured by bias + single inversion (§2.5) and entry-touch timing (§2.10a).
- **§2.1 / §2.7 / §3.9:** Tercile / VIX cutpoints computed **both ways** — full-sample for
  descriptive tables, trailing/expanding for anything feeding the live SUGGESTED line.
- **§3.10 / §3.11 (new):** DST-validation table; level-touch / front-running table.

---

## 1. Core concepts & keys

### 1.1 Logical trading day
All sessions are grouped by a **trading-day key that rolls at 18:00 ET**. A bar at 18:00 ET
Monday and a bar at 10:00 ET Tuesday belong to the **same** logical trading day. This makes
"Globex IB bias → NY day outcome" a coherent same-key question.

```
trading_day = date of (timestamp_ET + 6 hours)   # so 18:00 Sun .. 17:59 Mon -> Mon
```

NOTE: this is a **close-side key** (it labels by the calendar date on which the futures trading
day ends at 17:00 ET). This aligns with the common desk convention: 18:00 Sun through 17:00 Mon
is counted as Monday.

### 1.2 Session slots (all configurable)
| Slot        | IB window (ET)    | Outcome deadline (ET) | time_basis     | Notes |
|-------------|-------------------|------------------------|----------------|-------|
| Globex IB   | 18:00–19:00       | 20:00 (or London)      | ET_fixed       | overnight; CME event, ET-native |
| Tokyo IB    | 19:00/20:00–+1h   | 02:00                  | event_anchored | Tokyo cash open 09:00 JST = 00:00 UTC (§1.4) |
| London IB   | 03:00–04:00 (±1h) | 06:00                  | event_anchored | London open 08:00 local (§1.4) |
| Midnight OR | 00:00–00:30       | 16:00 (EOD)            | ET_fixed       | ICT midnight open range; holds to EOD |
| NY AM IB    | 09:30–10:30       | 16:00                  | ET_fixed       | RTH initial balance |
| NY PM IB    | 13:30–14:30       | 16:00 (or 17:00)       | ET_fixed       | post-lunch range |

ICT also uses the **midnight open as a single line** (the 00:00 ET open price). Track both:
the 00:00–00:30 range (slot above) and the bare 00:00 open price level, so you can test
range-break stats vs simple "above/below midnight open" day-bias.

The schema must let you add arbitrary slots (name, start, end, deadline, gap-ref, time_basis)
without code changes — store them as rows in a `sessions` config table.

### 1.3 Outcome window
For a given session, the **outcome window** runs from IB close to the session's outcome
deadline. All canonical "did X happen" stats (extension hits, mid retest, break direction,
the three plays) are measured **only within this window**, never spilling into the next
session — this is unchanged and keeps headline numbers comparable across versions.

**Formation monitoring (additive, v5).** The level-touch / front-running layer (§2.10)
additionally records what happens *during* the IB formation window (e.g. the final-mid level
being tagged before IB close). This is stored in separate fields and a separate detail table;
it never alters the canonical outcome-window stats.

**Cross-midnight constraint (implementation).** Tokyo and Globex outcome windows wrap past
midnight (`start_min > end_min`, e.g. 21:00→02:00). The time mask must handle the wrap
(`m >= start OR m < end`), and `outcome_close` / `realized_dir_close` must take the **timestamp-max**
bar of the logical day's outcome window, not a positional `last`. Grouping is by `trading_day`
(the 18:00 roll already keeps the wrapped bars together). Unit-test: a 21:00 bar and a 01:00 bar
fall in the same `in_out` for one logical day.

### 1.4 Event-anchored foreign slots (DST) — the trade is the open auction
The premise: when we trade Tokyo/London IB we are trading the **liquidity event** (the
open auction), so the IB window must follow the event, not a fixed wall-clock. Because the
event sits at a fixed UTC instant, "follow the event" reduces to a **±1h shift of the ET
window driven by the US-DST flag** — there is no JST or London timezone conversion in the
pipeline. Everything is stored and reported in ET exactly as today; the only change is which
ET hour the window opens on, plus a regime label.

**Tokyo.** Tokyo cash opens 09:00 JST = 00:00 UTC (JST has no DST). In ET that is:
- US on **EST** (winter): open = **19:00 ET** → event-anchored IB `19:00–20:00`.
- US on **EDT** (summer): open = **20:00 ET** → event-anchored IB `20:00–21:00`.

The current fixed window `20:00–21:00` is therefore correct in summer and starts an hour
late through the ~4 EST months.

**London.** London opens 08:00 local. London-local DST (BST) and US DST mostly coincide, so
08:00 local = **03:00 ET** for most of the year. They are misaligned only during the ~3
shoulder weeks each spring/autumn when the UK and US switch on different dates; in those
weeks 08:00 local = **04:00 ET** → event-anchored IB shifts to `04:00–05:00`. A UK-DST flag
catches this.

**Outcome deadlines** stay at their fixed ET clock times (they represent the next liquidity
handoff, which is its own event); only the IB window start/end shift. Per-slot config may
override.

**Validation harness (resolve, don't assume).** For Tokyo and London, materialize **two
slot variants over identical dates**: `… · ET-fixed` (current behavior) and `… · event-anchored`
(§1.4 shift). §3.10 compares their headline stats directly. If the variants are statistically
indistinguishable at the available N, keep `ET_fixed` and drop the anchored variant; otherwise
the anchored variant is canonical for that slot.

**Per-row regime fields** (in `ib_facts`):
- `time_basis` = ET_fixed | event_anchored
- `us_dst` (bool), `uk_dst` (bool; null unless slot references London)
- `et_window_offset_hours` = the ±1h applied vs the ET_fixed window (0 when aligned)
- `dst_regime` = "aligned" | "shifted" (window moved vs the ET_fixed baseline)

---

## 2. Per-session computed fields (the fact table)

One row per `(symbol, trading_day, session_slot, time_basis)`. Columns:

### 2.1 Range geometry
- `ib_high`, `ib_low`, `ib_mid`, `ib_open`, `ib_close`
- `range_pts` = ib_high − ib_low
- `range_pct` = range_pts / **ib_mid** × 100  (ib_mid denominator everywhere — the
  cross-instrument comparable; do **not** use ib_low)
- `range_atr` = range_pts / ATR(14, daily)  — ATR-normalized cross-regime comparable
- `range_pctile_20`, `range_pctile_60` = percentile of range_pts vs trailing 20 / 60 sessions
  of same slot
- `range_bucket` = Small / Medium / Large by **terciles of `range_pct`** per (symbol, slot).
  **Cutpoints are computed two ways (v5):** `range_bucket_full` over the full sample (for the
  descriptive aggregate tables) and `range_bucket_trailing` over a trailing/expanding window
  (for anything that feeds the live SUGGESTED line — no look-ahead). Buckets report break%,
  median extension reached, P75 extension (stretch target), and 0.5x-hit%.

### 2.2 Opening gap
- `prior_session_close` = for **NY AM, the prior RTH close** (16:00). For overnight slots
  (Globex/Tokyo/London) the prior same-slot IB close. Per-slot config field; under the day-roll
  this is a **cross-key lookup** (prior RTH close lives in `trading_day − 1`), not a same-key
  reference — implement accordingly.
- `gap_pts` = ib_open − prior_session_close
- `gap_pct` = gap_pts / prior_session_close × 100
- `gap_dir` = sign(gap_pts)
- `gap_filled` = did price trade back to prior_session_close within outcome window (bool)
- `gap_fill_minutes` = minutes from IB close to gap fill (null if unfilled)

### 2.3 Breakout / extension
- `first_break_dir` = +1 if IB high broken before IB low (within outcome window), −1 if low
  first, 0 if neither
- `first_break_minutes` = minutes from IB close to first break
- `double_break` = both boundaries taken out (bool); `double_break_order` = "HL" or "LH"
- `false_break_high`, `false_break_low`: a break is **false** if, after price breaks that
  boundary, **either (a)** a bar later **closes beyond the opposite IB boundary** (full reversal),
  **or (b)** the break side **never reaches `false_break_min_ext`** before the outcome deadline.
  **Order precedence (v5):** evaluate (a) and (b) over the window; if **both** boundaries close
  beyond, flag **both** sides false. `false_break_min_ext` default 0.5x; also test 0.25x (ICT min).
- Extension hits — for each level L in {0.25,0.5,1,1.5,2,2.5,3,3.5,4} and each side {up,down}:
  - `ext_up_{L}_hit` (bool), `ext_up_{L}_minutes` (time-to-hit, null if not hit); same for down
  - Extension price = ib_high + L×range_pts (up), ib_low − L×range_pts (down)
- `max_ext_up`, `max_ext_down` = furthest extension reached (in L units), within window
- `either_side_{L}_hit` = up OR down hit at level L

### 2.4 Mid / retrace
- `mid_retest` = after first break, did price return to ib_mid within the **outcome window**
  (bool) — *canonical, unchanged.* (Front-running / pre-close mid touches are in §2.10.)
- `mid_retest_minutes` = time from first break to mid retest
- `retrace_depth_pct` = deepest pullback into the range after first break, measured from the
  running **post-break extreme**, as % of range
- `behavior` = "trend" (broke & extended, shallow retrace) vs "fade" (returned to/through mid)
  — define by retrace_depth_pct threshold (e.g. ≥50% = fade)

### 2.5 Bias variants (one column each, value in {+1, −1, 0})
Compute **every** variant independently every session so they can be A/B'd in §3.2:

- `bias_formation_firstreach` — uses the **first bar that reaches** each extreme. The extreme
  established **earlier** signals the push direction: low established first ⇒ **bullish (+1)**,
  high established first ⇒ bearish (−1). Tie → `sign(ib_close - ib_open)` (0 on doji).
- `bias_formation_lasttouch` — same idea but using the **last bar that touches** each extreme
  (the current Pine `>= / <=` behavior). A flat top revisited near the close counts as "formed
  later" here, so this variant can disagree with `firstreach` on the same day — which is the
  point of carrying both. (This settles the spec's own open question: a consistently sub-50%
  formation hit rate means it's a fade signal, which is itself tradeable. Let §3.2 rank the two.)

**FVG detector gap safety (implementation constraint).**
The fixed-5m FVG detector must preserve empty maintenance/weekend bins as NaN barriers and only
evaluate 3-bar relationships where both compared bars are non-null. This prevents `shift(2)`
bridging across trading gaps and creating spurious cross-gap FVGs.
- `bias_close_dir` = sign(ib_close − ib_open)
- `bias_fvg` = direction of the **first 5m FVG inside the IB window** (bullish gap = +1). FVG =
  classic 3-bar displacement gap (bull: `bar[2].high < bar[0].low`; bear: `bar[2].low >
  bar[0].high`). Detect on **fixed 5m**. Store the **gap zone** `[fvg_bottom, fvg_top]` **and the
  3-bar pattern extreme** `fvg_low` / `fvg_high` — bull gap `fvg_low = min(low)` across the three
  forming bars (the swing/structure low); bear gap `fvg_high = max(high)`. The **pattern extreme,
  not the gap edge, is the invalidation anchor**. (Experienced-ICT reading: the gap is the entry
  zone; the displacement structure is what fails. Applies to all FVG variants incl. `bias_fvg_rth`
  / `bias_fvg_1011`.)
- `bias_fvg_ifvg` = `bias_fvg`, but **inverts once** if the gap is invalidated within the outcome
  window. **Invalidation = a bar that CLOSES beyond the 3-bar pattern extreme** (bull:
  `close < fvg_low`; bear: `close > fvg_high`) — explicitly **not** a close through the gap edge,
  and **not** a wick. A wick below `fvg_low` (or a close below the gap *bottom* that holds above
  `fvg_low`) is a deep fill / liquidity sweep — often a continuation signal, **not** an inversion.
  **Single inversion only**; the bias reflects the gap's *current* directional state at grade time.
  The IFVG finalizes at the inversion bar (used by the §2.6 leakage guard).
- **FVG entry-touch** (the pullback fill; timing in §2.10a): first bar that re-enters the gap zone
  and **holds** on the valid side of the invalidation level — bull: `low <= fvg_top AND
  close >= fvg_low`; bear: `high >= fvg_bottom AND close <= fvg_high`. By construction a bar is
  **either** an entry-touch (held) **or** an invalidation (closed beyond the pattern extreme),
  never both; a sweep-and-reclaim bar counts as an entry-touch. Touch-of-zone for entry,
  close-of-structure for invalidation — the one deliberate close-based test (§2.6).
- **NY AM only — dual FVG (A/B which predicts NY-AM extension better):**
  - `bias_fvg_rth` = first FVG from 09:30
  - `bias_fvg_1011` = first FVG forming in the **ICT 10:00 macro window (09:50)** through
    **11:00**. The level **persists** so an entry can fire after 11:00 even though the bias is
    fixed at first formation. Because part of this window is past the 10:30 IB close, its
    grading uses the **leakage guard** (§2.6).
- `bias_combined` = sign of sum of enabled variants (configurable weight vector)

The downstream playable layer (Pine table + Python `IBBreakStrategy`) must be runnable
**against any single variant** (a `bias_variant` selector), so we can see which bias makes
each *play* profitable — not just which bias is most accurate in the abstract.

### 2.6 Bias outcome grading (self-contained, order-sensitive)
For each variant, grade against **four target levels, tracked separately**:
`bias_correct_{variant}_025x`, `bias_correct_{variant}_05x`,
`bias_correct_{variant}_075x`, and `bias_correct_{variant}_1x` (bool) =
the session's extension on the bias side is hit within the outcome window
**before** the opposite IB boundary is violated.

**Order matters (v5):** occurrence is not enough — the bias-side target must be reached *before*
the opposite-boundary wick violation, evaluated bar-by-bar. A day that reverses through the far
side first and only later tags the bias extension grades **incorrect**.

**Leakage guard (v5):** for any variant whose bias can finalize *inside* the outcome window
(`bias_fvg_1011`, and the IFVG flip), count only extension hits that occur **after** the bias
is finalized. Formation / close-dir / first-RTH-FVG are fixed at/by IB close and are unaffected.
For `bias_fvg_ifvg`, "finalized" = the inversion bar (the close beyond the pattern extreme, §2.5):
grade the pre-inversion direction up to that bar and the inverted direction after.

**Entry / stop mechanics (v6) — by order type, not a blanket rule.** Close-based tests exist in
exactly **three** places: (a) **FVG invalidation** (§2.5, a close beyond the 3-bar pattern
extreme); (b) **Play 1 breakout entry** confirmation (close beyond the boundary); and (c) **Play 3
fade touch-back fill** confirmation (close back inside the boundary). **Everything else is touch
(wick) based** — all stops, all targets, and the **Play 2 limit entry at the mid** — matching live
fills: stops, targets, and limit orders fill on trade-through; only breakout/fade *entries* and the
FVG invalidation are confirmed on close. Rule of thumb for any future play: **limit => touch;
stop / breakout / confirmation entry => close.** For `bias_fvg_ifvg`, "finalized" = the inversion
bar (the close beyond the pattern extreme); grade the pre-inversion direction up to that bar and the
inverted direction after.

**Additive realized-direction comparators (v5+):**
- `realized_dir_break` = `first_break_dir` (+1/-1/0)  [default comparator]
- `realized_dir_close` = sign(`outcome_close - ib_close`)
- `realized_dir_ext` = sign(`max_ext_up - max_ext_down`)

Days where selected `realized_dir_* = 0` are excluded from DIR% denominators and reported in
the no-resolution bucket.

### 2.7 Conditioning keys (for slicing)
- `dow` = day of week (of the logical trading day)
- `vix_close` (prior day) and `vix_bucket` (low/mid/high terciles — **both full-sample and
  trailing**, same rule as range buckets in §2.1)
- `prior_day_result` = sign of prior same-slot day's outcome
- `range_bucket` (from 2.1)
- `dst_regime` (from §1.4 — only meaningful for event-anchored foreign slots)

### 2.8 The three plays (per-day outcome, win/loss/no-setup)
Each day, evaluate all three plays **bar-by-bar within the outcome window** so target-before-stop
ordering is correct. Store `play{1,2,3}_result` ∈ {+1 win, −1 loss, 0 no setup}, plus realized
excursion. All entry/target/stop levels are **configurable** (these are the Pine defaults):

**Execution/labeling rules (agreed policy):**
- If a setup never triggers, it is **No-Setup (0)**.
- If a setup triggers, it is a live trade and must be graded as **Win or Loss only**.
- Win requires target-first ordering; any triggered non-target outcome is a **Loss (-1)**.
- Same-bar ambiguity is handled conservatively: if entry and stop can occur on the same bar
  (extraordinary volatility), treat the setup as **triggered** and classify it as a **Loss (-1)**,
  not No-Setup.
- If target and stop are both satisfied on the same post-entry bar, classify as **Loss (-1)**
  (stop-first tie-break) to avoid optimistic bias.
- Loss diagnostics are split into `stop` vs `timeout` for reporting without changing win/loss math.

- **① Breakout (continuation):** enter at the IB boundary on a **close-confirmed** break;
  target = `p1_tgt_ext`
  (default 1.0×, i.e. `ib_high + 1.0×range_pts` for an up-break, anchored to the **boundary**,
  not to entry); stop = opposite IB boundary. Win = target wick-hit before opposite-boundary
  wick stop.
- **② Retest-continuation:** wait for a break, then a return to mid; enter at mid via a **resting
  limit order — filled on TOUCH** (price trades through/at the mid in the break direction; the
  close is irrelevant, as with any limit order); target = `p2_tgt_ext` (default 0.5× break side,
  boundary-anchored); stop = opposite boundary. Win = target wick-hit after the limit fills.
  (Edgeful Manip-style play.)
- **③ Fade-to-mid (mean reversion):** wait for an overshoot to `p3_overshoot_ext` (default 0.25×)
  beyond the boundary; **then require a close-confirmed touch-back to the boundary to fill the
  fade entry** — if price never returns to the boundary before the deadline, it is
  **no-setup (0)**, not a loss. Target = mid; stop = `p3_stop_ext` (default 0.5×, further out).
  Win = target wick-hit before wick stop.

For each play also store `play{n}_rr` (structural reward:risk in range units, **derived from the
configured level — not hard-coded**; e.g. Play 2 RR at level L = `(0.5 + L) / 0.5` for entry at
mid with stop at the opposite boundary, so it equals 2.0 only when L = 0.5) and the realized
**MFE/MAE**. The MFE/MAE feed (a) the Edgeful full-ladder expectancy (cover-the-queen at 75%,
TP1 at 1:1, TP2 at 0.25x/0.5x ext, runner) and (b) a later **MAE-driven refinement of the Play 3
overshoot/stop** (parked — the per-play MAE distribution is the handle for that, no rework needed).

Diagnostics captured per play event in `ib_play_detail`:
- `timeout_loss` (bool): true when a triggered trade loses by session expiry instead of stop.
- `loss_reason` (enum): `no_setup` | `target` | `stop` | `timeout`.

### 2.9 Event timing (mode + median)
- `first_break_bucket` = **5-min** clock bucket (ET) of the first break → enables **mode** break
  time (most common clock slot), not just median minutes-after-IB.
- Mid-touch and FVG entry-touch timing buckets are defined in §2.10 / §2.10a, **split by phase**
  (formation vs outcome). All clock buckets use a **5-minute** minimum granularity.

### 2.10 Level-touch tracking — quarters + front-running mid (v5)
Track touches of the IB structural levels both **during formation** and **during the outcome
window**. Levels, as fraction of range: **{0, 25, 50, 75, 100}%** (0 = ib_low, 50 = ib_mid,
100 = ib_high; 25/75 = the IB quarters). Stored long in `ib_level_touch_detail` (§4).

For each `(level, phase)` capture: `first_touch_time`, `first_touch_phase`, `last_touch_time`,
`touch_count`. **Phase** = `formation_pre_lock` | `formation_post_lock` | `outcome`.

**Mid lock + front-running fields** (in `ib_facts`, the 50% row promoted for convenience):
- `mid_lock_time` = the **last bar in the IB window that set a new H or L**. After this bar the
  provisional range (and thus provisional mid) equals the final range — i.e. the mid stops
  moving. `provisional_mid == final_mid` from `mid_lock_time` onward.
- `mid_lock_frac` = `mid_lock_time` as a fraction of IB duration (e.g. 35/60 = 0.58).
- - Against the **final** mid level scanned across the whole session:
  `mid_touch_first_time`, `mid_touch_first_phase`, `mid_touch_last_formation_time`,
  `mid_touch_count_formation`, `mid_touch_count_outcome`, and `mid_touched_again` (touched again
  after its first post-lock touch — the "set H/L early, then revisit mid" pattern you want to
  size up).
- **Split first-touch (v6 — headline front-running stat):**
  `mid_touch_first_formation_time` / `mid_touch_first_formation_bucket` (first touch where phase ∈
  {formation_pre_lock, formation_post_lock}) **and** `mid_touch_first_outcome_time` /
  `mid_touch_first_outcome_bucket` (first touch where phase = outcome), each floored to a **5-min**
  ET bucket. The **mode** of each — when the mid is first hit *before* IB close vs *after* — is the
  deliverable (§3.11). A single all-phase bucket is insufficient: a formation touch masks the
  outcome-window touch.
- `early_mid_event` (bool) = **mid locked in the first ⅔ of formation AND the final-mid level
  touched after lock but before IB close.** This is the single flag whose frequency answers
  "is front-running the mid a real, common opportunity?"

Front-run equality checks for `provisional_mid == final_mid` should use tolerant float
comparison (e.g., `np.isclose` with tight absolute tolerance), not exact equality.

**Honesty constraint.** `mid_lock_frac` and "touched before IB close" are **live-feasible**
signals (you'd know them in real time). The touch *time relative to the final mid* is
**retrospective** — fine for measuring opportunity, **not yet a live rule.** This layer is
measurement only; the provisional-mid *tradeable* rule is deferred until the data shows the
opportunity is worth it (see §3.11).

### 2.10a FVG entry-touch timing (v6)
Symmetric with the mid-touch timing, for the IB FVG (and, on NY AM, the 09:50–11:00 FVG). Uses the
**entry-touch** definition in §2.5 (re-enter the zone and hold above the invalidation level):
- `fvg_touch_first_formation_time` / `fvg_touch_first_formation_bucket` = first entry-touch at/after
  the gap finalizes, while still inside the IB window.
- `fvg_touch_first_outcome_time` / `fvg_touch_first_outcome_bucket` = first entry-touch in the
  outcome window.

Buckets floored to **5-min** ET. The **mode** answers "when does price typically come back to fill
the gap, before vs after IB close." Measurement only; no FVG entry rule is graded. Promoted into
`ib_facts` (like the mid timing) — no separate detail table. Note: the `bias_fvg_1011` gap can form
*after* the 10:30 IB close, so its formation-phase entry-touch may be empty; that is expected.

### 2.11 FVG handling — single inversion + entry-touch (v6, replaces reuse tracking)
The per-touch FVG **reuse catalog** (and the `ib_fvg_detail` table) is **removed** — de-scoped. The
FVG is fully characterized by: (a) its **bias** (`bias_fvg`) and **at-most-one inversion**
(`bias_fvg_ifvg`, §2.5) via the close-beyond-pattern-extreme rule; and (b) its **entry-touch
timing** (§2.10a). No inversion count, no touch count. As long as the bias points the correct
direction (single inversion handled) and we know *when* the entry-touch occurred relative to IB
close, the FVG is fully captured for the harness.

---

## 3. Aggregate stats (the dashboard tables)

All computed per `(symbol, session_slot, time_basis)` and sliced by the conditioning keys in
§2.7. Report N, median, mode, P25/P75/P90, IQR on every distribution.

### 3.1 Extension table (the headline)
Per level: hit % up, hit % down, either-side %, and the **conditional ladder**:
`P(hit (L+0.5) | hit L)` — the most actionable single addition.

### 3.2 Bias accuracy table (the A/B harness — primary deliverable)
Per variant — `bias_formation_firstreach`, `bias_formation_lasttouch`, `bias_close_dir`,
`bias_fvg`, `bias_fvg_ifvg`, NY-AM `bias_fvg_rth` / `bias_fvg_1011`, `bias_combined` — report
hit rate at each graded level (0.25x / 0.5x / 0.75x / 1x, headlining 0.5x and 1x), N, and **lift =
hit_rate − base** (empirical baseline per the "Empirical baselines" block below, not a fixed 0.50).
Then:
- **Agreement lift:** hit rate when ≥2 variants agree vs when they disagree.
- Bias hit rate sliced by range_bucket, dow, vix_bucket.
- Directly answers "does criterion X improve or degrade win rate," and ranks the two formation
  definitions head-to-head.

**Bias comparison split (additive):** separate direction correctness from extension hits.
- `DIR%` uses a selectable comparator (`realized_dir_break` / `realized_dir_close` /
  `realized_dir_ext`) and is computed over rows where both variant and comparator are non-zero.
- `TARGET 0.5x%` and `TARGET 1x%` remain extension-hit statistics.

**Empirical baselines (used for lift and coloring):**
- `base_dir = max(P(realized_dir=+1), P(realized_dir=-1))` over resolved days.
- `base_tgt = P(V=+1)*P(max_ext_up>=0.5) + P(V=-1)*P(max_ext_down>=0.5)` over firing days.
- `LIFT_dir = DIR% - base_dir`, `LIFT_tgt = TARGET0.5% - base_tgt`.

Add a **BASELINE** row at top of the direction table.

### 3.2a No-signal buckets (new)
For sparse variants (`bias_fvg`, `bias_fvg_ifvg`) report:
- `N_absent = count(V==0)`
- `chop_rate_absent`
- `chop_rate_all`

Format: `No-<variant> day -> chop X% (vs Y% baseline, N=Z)`.

### 3.2b Conflict matrix (new)
At minimum include Formation×FVG, Formation×FVG→IFVG, FVG×Close-Dir, Formation×Close-Dir.
On rows where both fire, disagree, and realized direction resolves:
- `N_conflict`
- `winA%`, `winB%`
- winner + edge

Headline style: `When A & B disagree (N=x): A right y%, B z%`.

### 3.2c Agreement lift (new)
Compare `agree_2plus` and `agree_all` buckets against best single-variant DIR%.

### 3.3 Geometry / gap table
Range %, range ATR, gap %, gap-fill rate, median gap-fill minutes — by slot, by dow.

### 3.4 Timing table
Median time-to-first-break, time-to-each-extension, time-to-mid-retest. Split trend vs fade.

### 3.5 Mid / fade table
Mid retest %, median retrace depth, fade vs trend split. Connects to the Edgeful Manip finding
(72% mid retest, 58% continuation at mid-retest entry). **Cross-ref §3.11** for the front-running
/ formation-phase mid view.

### 3.6 Sequencing table
Directional streak distribution, inside/outside IB days, and **cross-session agreement**:
Globex bias → NY AM bias agreement → NY day follow-through. (Requires the 18:00 day-roll key.)

### 3.7 Day-of-week / range-size / formation tables
Per slot. DOW shows the **best-win-rate play per weekday**. Range-size shows break% + median ext
+ P75 ext + 0.5x-hit per tercile.

### 3.8 Three-plays comparison table (the decision centerpiece)
Per (symbol, slot, time_basis): for each play, **win% · R:R · expectancy(R)**, expectancy =
win × RR − loss. Extend beyond Pine's single-target to the **full-ladder expectancy** (partial
TPs + runner, from MFE/MAE) and slice by range_bucket, bias-agreement, VIX, DOW. The play with
the best expectancy in the current regime is the trade.

Dashboard/report requirement:
- Show loss decomposition for each play as `stop_loss_rate` and `timeout_loss_rate`.
- Show `no_setup_rate` separately so non-trigger days do not pollute play win/loss quality.

### 3.9 The SUGGESTED line (heuristic synthesis)
Cross-table: **bias direction × best play** → one-line suggestion. Editable lookup. Sub-50%
dominant bias flips the direction to a fade. Selector: highest-expectancy (respects R:R),
not highest-win-rate. **Any bucket feeding SUGGESTED uses the trailing/expanding cutpoints**
(§2.1), never the full-sample ones, to keep the live read look-ahead-free.

Dominant signal summary (additive): choose the variant with strongest conflict wins and highest
`LIFT_dir`; if its `DIR%` falls below `base_dir`, present as a fade-biased signal.

### 3.10 DST-validation table (v5 — Tokyo / London only)
For each event-anchored foreign slot, compare the `ET_fixed` and `event_anchored` variants over
identical dates: headline stats (bias hit% at 0.5x/1x, play win%/expectancy, range_pct, break%)
side-by-side, with N and effect size per cell, plus the same stats sliced by `dst_regime`
(aligned vs shifted). **Decision rule:** indistinguishable at the available N (overlapping CIs)
→ keep `ET_fixed`, drop the anchored variant; otherwise the anchored variant is canonical for
that slot. This turns "I assume DST matters" into a measured fact.

### 3.11 Level-touch / front-running table (v5)
Per slot, touch-rate for each level {0, 25, 50, 75, 100}% **conditioned on phase and on
first-break-having-occurred** (raw rates are misleading — 25%/75% sit near the boundaries where
price spends formation time, so they look artificially "active" unless conditioned). Plus:
- "How often is 25% hit vs 50% vs 75%" within each phase.
- Distribution of `mid_lock_frac` (how early the range typically locks).
- `early_mid_event` frequency and the clock-time distribution of the post-lock pre-close mid
  touch — the input to deciding whether a provisional-mid early-entry rule is worth building.

---

## Table organization (shared Pine ↔ Edgeful template)
Decision-priority order, kept consistent across Pine table and Edgeful dashboard:
1. **SUGGESTED** — one-line synthesis at the top.
2. **① DIRECTION** — bias signals (formation ×2, close-dir, FVG, FVG→IFVG) with hit% + lift.
3. **② FAKE-OUT** — false-break%, contained, double-break, retrace.
4. **PLAYS** — the three setups: win · R:R · expectancy.
5. **③ TARGETS** — extension ladder (+ conditional) + break/mid timing.
6. **④ DAY TYPE** — mid-retest, gap, range terciles, day-of-week.
7. **RANGE Δ** — IB-size distribution.

All % cells use the traffic-light scheme: ≥60% green, 50–60% orange, <50% red. Counts shown as
"count (pct%)". Section headers carry tooltips.

---

## 4. Suggested table layout (DuckDB / parquet)

- `ib_sessions_config` — slot definitions (name, start, end, deadline, gap-ref, **time_basis**)
- `ib_facts` — one row per (symbol, trading_day, slot, **time_basis**); all of §2 incl. play
  results, timing buckets, range_pct, bias variants & gradings, **DST regime fields (§1.4)**,
  **mid-lock / split mid-touch / front-running fields (§2.10)**, realized direction fields
  (`realized_dir_break`, `realized_dir_close`, `realized_dir_ext`), and **FVG fields**: `fvg_low`,
  `fvg_high` (pattern extreme), inversion state, and **FVG entry-touch timing (§2.10a)**
- `ib_ext_detail` — long: (symbol, trading_day, slot, time_basis, side, level, hit, minutes)
- `ib_play_detail` — long: (symbol, trading_day, slot, time_basis, play, target_lvl, result,
  mfe, mae, realized_r, timeout_loss, loss_reason, with_bias)
- `ib_level_touch_detail` — long: (symbol, trading_day, slot, time_basis, level_pct, phase,
  first_touch_time, last_touch_time, touch_count) — **v5**
- *(removed v6)* `ib_fvg_detail` — per-touch FVG reuse catalog dropped; FVG bias + single inversion
  + entry-touch timing all live in `ib_facts` (§2.5 / §2.10a / §2.11).
- `ib_agg_*` — materialized aggregate views feeding each dashboard table
- `ib_agg_bias_compare` — per-variant DIR%/HIT%/LIFT/N + baselines
- `ib_agg_bias_conflict` — pairwise conflict matrix
- `ib_agg_no_signal` — no-signal chop statistics

Python builders write the parquet files into `data/derived/`; the Next.js/DuckDB-WASM dashboard
reads via the API proxy; design doc lives alongside `MACRO_RESEARCH_PIPELINE_DESIGN.md`.

Precalc input contract (implementation): when `df_1m_precalc` is supplied, builders may derive
missing helper columns (`timestamp`, `datetime`, `logical_date`, `bar_idx`,
`minutes_from_midnight`, `us_dst`, `uk_dst`) from the index if absent, to avoid hard failures.

---

## 5. Stat catalog — quick reference

- ✅ Range size (price %, points, ATR mult, percentile, terciles — full-sample + trailing)
- ✅ Opening gap, gap %, gap fill rate + time-to-fill (NY AM ref = prior RTH close, cross-key)
- ✅ Double breaks (+ order, + false/failed breaks per §2.3, both-sides rule)
- ✅ Streaks (directional, inside/outside days, cross-session agreement)
- ✅ Median time (to first break, to each extension, to mid retest) + mode clock time
- ✅ Mid hit % (+ retrace depth, fade vs trend split)
- ✅ **Front-running mid: lock timing, split first-touch (formation/outcome) + 5-min buckets, `early_mid_event` (v5/v6)**
- ✅ **Quarter-level touch rates {0/25/50/75/100}%, by phase, conditioned (v5)**
- ✅ Conditional extension ladder: P(N+0.5x | Nx hit)
- ✅ Bias accuracy per variant (incl. **dual formation**, **dual NY-AM FVG**) + lift + agreement lift
- ✅ Bias comparison split: `DIR%` vs `HIT%`, empirical baselines, no-signal buckets, conflict matrix
- ✅ **FVG: bias + single inversion via close-beyond-pattern-extreme; entry-touch timing (formation/outcome) (v6)**
- ✅ Three plays (breakout / retest-cont / fade-to-mid): win · R:R · expectancy; Play 3 touch-back fill
- ✅ Range-size terciles → break% + median ext + P75 stretch ext + 0.5x-hit
- ✅ First-break-dir = day-winner rate
- ✅ IB mid as % of daily range
- ✅ Regime conditioning: VIX bucket, DOW, range bucket, prior-day result, **DST regime (v5)**

**Delegated to Edgeful (beyond Pine):** full-ladder play expectancy; sample-starved multi-way
slicing; cross-session sequencing; dual NY-AM FVG at full sample; VIX/regime conditioning;
**DST validation (§3.10)**; **front-running + quarter-touch layer (§3.11)**; 20-year samples.

---

## 6. Open items

**Resolved:**
- Gap reference: NY AM → prior RTH close (cross-key); overnight → prior same-slot IB close (§2.2).
- Bias grading: 0.25x/0.5x/0.75x/1x, **order-sensitive, touch-based** stops, with leakage guard (§2.6).
- **Stops/targets are touch-based** everywhere (bias grading + all plays). Close-based tests exist
  in exactly **three** places: FVG invalidation (§2.5), Play 1 breakout entry confirmation (§2.8),
  and Play 3 fade touch-back fill confirmation (§2.8).
- **FVG (experienced-ICT reading):** invalidation / IFVG flip = **close beyond the 3-bar pattern
  extreme** (`fvg_low`/`fvg_high`), not the gap edge and not a wick; **single inversion** only;
  entry-touch defined for timing (§2.5/§2.10a).
- `play{n}_rr` **derived from the configured level**, not hard-coded (§2.8).
- Range / VIX buckets: terciles per (symbol, slot), **full-sample for tables, trailing for
  SUGGESTED** (§2.1/§2.7/§3.9).
- Formation bias: **compute both** firstreach and lasttouch, A/B in §3.2 (§2.5).
- Three plays defined with default levels; **Play 3 requires touch-back fill** (§2.8).
- Foreign slots are **event-anchored** via a US-DST ±1h ET shift; build both variants and
  validate (§1.4/§3.10). All data stays UTC→ET; reports carry `dst_regime`.
- NY-AM dual FVG: `bias_fvg_rth` (09:30) and `bias_fvg_1011` (**09:50 ICT macro → 11:00**, level
  persists, leakage-guarded) (§2.5/§2.6).
- **FVG per-touch catalog REMOVED** (no inversion count, no touch count); replaced by single inversion
  + entry-touch timing; `ib_fvg_detail` dropped (§2.10a/§2.11).
- Front-running mid + quarter touches: **measurement layer only**; canonical mid-retest unchanged
  (§2.10/§3.11).
- Event timing: capture both mode (**5-min bucket**) and median; mid + FVG entry-touch split by
  phase (§2.9/§2.10/§2.10a).

**Still to decide / validate during build:**
1. Globex outcome deadline (Tokyo open vs run to London).
2. `false_break_min_ext`: default 0.5x; test 0.25x.
3. Edgeful play-ladder structure (cover-the-queen %, TP1, TP2, runner trail) for full expectancy.
4. Whether the two formation variants are redundant in practice (§3.2 will show it) — and the
   broader "later extreme = momentum vs exhaustion" question.
5. DST: does event-anchoring change Tokyo/London stats enough to keep the anchored variant?
   (§3.10 decides; expectation is it matters most for Tokyo in the EST months.)
6. Whether `early_mid_event` is frequent enough to justify building the **provisional-mid
   early-entry tradeable layer** (§2.10/§3.11) — and if so, the live provisional-mid rule.
7. The MAE-driven Play 3 overshoot/stop refinement (parked; MFE/MAE already captured).
8. Manual back-test validation of three-play win rates and range-tercile targets.
9. Bias-comparison audit: hand-validate one conflict pair and one no-signal bucket on sample rows.
