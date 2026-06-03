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

## 1. Core concepts & keys

### 1.1 Logical trading day
All sessions are grouped by a **trading-day key that rolls at 18:00 ET** (CME convention).
A bar at 18:00 ET Monday and a bar at 10:00 ET Tuesday belong to the **same** logical
trading day. This makes "Globex IB bias → NY day outcome" a coherent same-key question.

```
trading_day = date of (timestamp_ET - 18 hours)   # so 18:00 Mon .. 17:59 Tue -> Mon
```

### 1.2 Session slots (all configurable)
| Slot        | IB window (ET) | Outcome deadline (ET) | Notes |
|-------------|----------------|------------------------|-------|
| Globex IB   | 18:00–19:00    | 20:00 (or London)      | overnight |
| Tokyo IB    | 20:00–21:00    | 02:00 (London open)    | Tokyo cash open 09:00 JST |
| London IB   | 03:00–04:00    | 06:00                  | London open 08:00 local |
| Midnight OR | 00:00–00:30    | 16:00 (EOD)            | ICT midnight open range; holds to EOD |
| NY AM IB    | 09:30–10:30    | 16:00                  | RTH initial balance |
| NY PM IB    | 13:30–14:30    | 16:00 (or 17:00)       | post-lunch range |

ICT also uses the **midnight open as a single line** (the 00:00 ET open price). Track both:
the 00:00–00:30 range (slot above) and the bare 00:00 open price level, so you can test
range-break stats vs simple "above/below midnight open" day-bias.

The schema must let you add arbitrary slots (name, start, end, deadline) without code
changes — store them as rows in a `sessions` config table.

### 1.3 Outcome window
For a given session, the **outcome window** runs from IB close to the session's outcome
deadline. All "did X happen" stats (extension hits, mid retest, break direction) are
measured **only within this window**, never spilling into the next session.

---

## 2. Per-session computed fields (the fact table)

One row per `(symbol, trading_day, session_slot)`. Columns:

### 2.1 Range geometry
- `ib_high`, `ib_low`, `ib_mid`, `ib_open`, `ib_close`
- `range_pts` = ib_high − ib_low
- `range_pct` = range_pts / ib_mid × 100
- `range_atr` = range_pts / ATR(14, daily)  — ATR-normalized, the cross-regime comparable
- `range_pctile_20`, `range_pctile_60` = percentile of range_pts vs trailing 20 / 60 sessions of same slot
- `range_bucket` = Small / Medium / Large by **terciles of `range_pct`** (decided). Bottom
  third = Small, middle = Medium, top third = Large. Using range_pct (not points) makes it
  cross-instrument comparable without per-symbol point thresholds. Compute the tercile
  cutpoints per (symbol, slot) over the full sample. Per the Pine build, buckets report
  break%, **median extension reached, P75 extension (stretch target)**, and 0.5x-hit% — i.e.
  both "should I trust the breakout" and "how far should I aim" per size.

### 2.2 Opening gap
- `prior_session_close` = for NY AM, use the **prior RTH close** (decided). For overnight
  sessions (Globex/Tokyo/London) use the prior same-slot IB close. Make the reference a
  per-slot config field.
- `gap_pts` = ib_open − prior_session_close
- `gap_pct` = gap_pts / prior_session_close × 100
- `gap_dir` = sign(gap_pts)
- `gap_filled` = did price trade back to prior_session_close within outcome window (bool)
- `gap_fill_minutes` = minutes from IB close to gap fill (null if unfilled)

### 2.3 Breakout / extension
- `first_break_dir` = +1 if IB high broken before IB low (within outcome window), −1 if low first, 0 if neither
- `first_break_minutes` = minutes from IB close to first break
- `double_break` = both boundaries taken out (bool); `double_break_order` = "HL" or "LH"
- `false_break_high`, `false_break_low`: a break is **false** if, after price breaks that
  boundary, EITHER (a) a bar later **closes beyond the opposite IB boundary** (full reversal),
  OR (b) the break side **never reaches the min extension** before the outcome deadline.
  Min-extension threshold is configurable (`false_break_min_ext`, default 0.5x; ICT also uses
  0.25x — test both, the data should reveal which separates real from fake breaks better).
- Extension hits — for each level L in {0.5,1,1.5,2,2.5,3,3.5,4} and each side {up,down}:
  - `ext_up_{L}_hit` (bool), `ext_up_{L}_minutes` (time-to-hit, null if not hit)
  - same for down
  - Extension price = ib_high + L×range_pts (up), ib_low − L×range_pts (down)
- `max_ext_up`, `max_ext_down` = furthest extension reached (in L units), within window
- `either_side_{L}_hit` = up OR down hit at level L (your "EITHER SIDE" column)

### 2.4 Mid / retrace
- `mid_retest` = after first break, did price return to ib_mid within window (bool)
- `mid_retest_minutes` = time from first break to mid retest
- `retrace_depth_pct` = deepest pullback into the range after first break, as % of range
- `behavior` = "trend" (broke & extended, shallow retrace) vs "fade" (returned to/through mid)
  — define by retrace_depth_pct threshold (e.g. ≥50% = fade)

### 2.5 Bias variants (one column each, value in {+1, −1, 0})
Compute **every** variant independently every session so they can be A/B'd:
- `bias_formation` = which IB extreme formed **later** in the window → push direction.
  High made after low (high is the later extreme ⇒ low formed first) = **bullish (+1)**;
  low made after high = bearish (−1). Tie → first-bar close direction.
  NOTE: matches the reference convention "low forms first ⇒ bullish ▲". (The Pine build
  originally had this inverted; corrected — verify Edgeful uses the same sign.)
  Open question the data should settle: is "later extreme = momentum/continuation" or is
  it "later extreme = exhaustion/fade"? A consistently sub-50% hit rate means it's a fade
  signal, which is itself tradeable.
- `bias_close_dir` = sign(ib_close − ib_open)
- `bias_fvg` = direction of the **first 5m FVG inside the IB window** (bullish gap = +1).
  FVG = classic 3-bar gap (bar[2].high < bar[0].low for bullish, etc.). Detect on **fixed 5m**.
- `bias_fvg_ifvg` = bias_fvg, but **flips** if the FVG is later closed through within the
  outcome window (inverse-FVG logic; close-based invalidation).
- NY AM only:
  - `bias_fvg_rth` = first FVG from 09:30
  - `bias_fvg_1011` = first FVG in the 10:00–11:00 window
  - track both separately so you can see which predicts NY AM extension better
- `bias_combined` = sign of sum of enabled variants (with a configurable weight vector)

### 2.6 Bias outcome grading (self-contained)
For each variant, grade against **two target levels, tracked separately** (decided):
`bias_correct_{variant}_05x` and `bias_correct_{variant}_1x` (bool) =
  the session's 0.5x (resp. 1x) extension on the bias side is hit within the outcome window
  **before** the opposite IB boundary is closed beyond. Storing both lets you compare whether
  the cheaper 0.5x target or the fuller 1x target gives a more reliable bias signal.

### 2.7 Conditioning keys (for slicing)
- `dow` = day of week
- `vix_close` (prior day) and `vix_bucket` (low/mid/high terciles)
- `prior_day_result` = sign of prior same-slot day's outcome
- `range_bucket` (from 2.1)

### 2.8 The three plays (per-day outcome, win/loss/no-setup)
The core decision framework. Each day, evaluate all three plays bar-by-bar within the
outcome window so target-before-stop ordering is correct. Store `play{1,2,3}_result` ∈
{+1 win, −1 loss, 0 no setup}, plus the realized excursion for richer Edgeful analysis.
All entry/target/stop levels are **configurable** (these are the Pine defaults):

- **① Breakout (continuation):** enter at the IB boundary on the break; target = `p1_tgt_ext`
  (default 1.0× on break side); stop = opposite IB boundary. Win = target hit before a
  close beyond the opposite boundary.
- **② Retest-continuation:** wait for a break, then a return to mid; enter at mid in the
  break direction; target = `p2_tgt_ext` (default 0.5× break side); stop = opposite boundary.
  Win = target reached after the mid touch. (This is the Edgeful Manip-style play.)
- **③ Fade-to-mid (mean reversion):** wait for an overshoot to `p3_overshoot_ext` (default
  0.25×) beyond the boundary; enter a fade at the boundary; target = mid; stop =
  `p3_stop_ext` (default 0.5×, further out). Win = reverts to mid before hitting the stop.

For each play also store: `play{n}_rr` (structural reward:risk in range units) and, for
Edgeful, the **realized MFE/MAE** so you can compute partial-target / runner expectancy
(the Pine version only does single-target win/loss; Edgeful should do the full ladder:
cover-the-queen at 75%, TP1 at 1:1, TP2 at 0.25x/0.5x ext, runner).

### 2.9 Event timing (mode + median)
- `first_break_bucket` = 15-min clock bucket (ET) of the first break → enables **mode**
  break time (most common clock slot), not just median minutes-after-IB.
- `mid_touch_bucket` = 15-min clock bucket of the mid touch → **mode** mid-touch time.
  These feed the profiler-style "when does it usually happen" view.

---

## 3. Aggregate stats (the dashboard tables)

All computed per `(symbol, session_slot)` and sliced by the conditioning keys in 2.7.
Report N, median, mode, P25/P75/P90, IQR on every distribution (match the Pine/Edgeful
convention already in use).

### 3.1 Extension table (the headline — image 1)
For each level: hit % up, hit % down, either-side %, and the **conditional ladder**:
`P(hit (L+0.5) | hit L)`. The conditional ladder is the most actionable single addition.

### 3.2 Bias accuracy table (the A/B harness — primary deliverable)
Per variant: hit rate, N, and **lift = hit_rate − 0.50**. Then:
- **Agreement lift**: hit rate when ≥2 variants agree vs when they disagree.
- Bias hit rate sliced by range_bucket, dow, vix_bucket.
- This table answers "does criterion X improve or degrade win rate" directly.

### 3.3 Geometry / gap table
Range %, range ATR, gap %, gap-fill rate, median gap-fill minutes — by slot, by dow.

### 3.4 Timing table
Median time-to-first-break, time-to-each-extension, time-to-mid-retest. Split trend vs
fade days. (Fast extension hits = trend regime signature.)

### 3.5 Mid / fade table
Mid retest %, median retrace depth, fade vs trend split. Connects to the existing Edgeful
Manip finding (72% mid retest, 58% continuation at mid retest entry).

### 3.6 Sequencing table
Directional streak distribution (N up-days → P(next up)), inside/outside IB days, and
**cross-session agreement**: Globex bias → NY AM bias agreement → NY day follow-through.
(Requires the 18:00 day-roll key; this is the highest-value cross-session stat.)

### 3.7 Day-of-week / range-size / formation tables
Direct replicas of the image-1 lower panels, per slot. DOW additionally shows the
**best-win-rate play per weekday** (which of the three plays won most). Range-size shows
break% + median ext + P75 ext + 0.5x-hit per tercile.

### 3.8 Three-plays comparison table (the decision centerpiece)
Per (symbol, slot): for each of the three plays, **win% · R:R · expectancy(R)**, where
expectancy = win × RR − loss. This is the table that says which setup to actually trade.
In Edgeful, extend beyond the Pine single-target version to the **full ladder expectancy**
(partial TPs + runner) and slice by range_bucket, bias-agreement, VIX, and DOW. The play
with the best expectancy in the current regime is the trade.

### 3.9 The SUGGESTED line (heuristic synthesis)
A simple cross-table: **bias direction × best-win-rate play** → one-line suggestion
(e.g. "Long · Breakout"). Coded as an editable lookup so wording/logic changes are trivial.
Explicitly a heuristic — the play table below it carries the real picture. Sub-50% dominant
bias flips the direction to a fade. In Edgeful, consider switching the selector from
highest-win-rate to **highest-expectancy**, which respects R:R.

---

## Table organization (shared Pine ↔ Edgeful template)
Both the Pine table and the Edgeful dashboard follow the same decision-priority order, so
they stay consistent:
1. **SUGGESTED** — one-line synthesis at the top.
2. **① DIRECTION** — bias signals (formation, close-dir, FVG, FVG→IFVG) with hit% + lift;
   formation follow-through.
3. **② FAKE-OUT** — false-break%, contained, double-break, retrace.
4. **PLAYS** — the three setups: win · R:R · expectancy.
5. **③ TARGETS** — extension ladder (up / down / either / continuation) + break/mid timing.
6. **④ DAY TYPE** — mid-retest, gap, range-size terciles, day-of-week.
7. **RANGE Δ** — IB-size distribution (median, P25/P75, today-vs-median).

All % cells use the traffic-light scheme: ≥60% green, 50–60% orange, <50% red. All counts
shown as "count (pct%)" so sample sizes are visible. Section headers carry tooltips
explaining their rows.

---

## 4. Suggested table layout (DuckDB / parquet)

- `ib_sessions_config` — slot definitions (editable: name, start, end, deadline, gap-ref)
- `ib_facts` — one row per (symbol, trading_day, slot); all of §2 incl. play results,
  timing buckets, range_pct, bias variants & gradings
- `ib_ext_detail` — long format: (symbol, trading_day, slot, side, level, hit, minutes)
  — easier for the conditional-ladder and time-to-hit aggregations than wide columns
- `ib_play_detail` — long format: (symbol, trading_day, slot, play, result, mfe, mae) —
  enables the full-ladder expectancy beyond simple win/loss
- `ib_agg_*` — materialized aggregate views feeding each dashboard table

Follow the existing pipeline pattern: Python builders write `ib_facts.parquet` and
`ib_ext_detail.parquet` into `data/derived/`; the Next.js/DuckDB-WASM dashboard reads via
the API proxy; design doc lives alongside `MACRO_RESEARCH_PIPELINE_DESIGN.md`.

---

## 5. Stat catalog — quick reference (what to compute)

Your list, confirmed and extended:

- ✅ Range size (price %, points, **ATR mult**, **percentile**, **terciles**)
- ✅ Opening gap, gap %, **gap fill rate + time-to-fill**
- ✅ Double breaks (+ order, + **false/failed breaks** per the §2.3 definition)
- ✅ Streaks (directional, **inside/outside days**, **cross-session agreement**)
- ✅ Median time (to first break, **to each extension**, to mid retest) + **mode clock time**
- ✅ Mid hit % (+ **retrace depth**, **fade vs trend split**)
- ✅ Conditional extension ladder: P(N+0.5x | Nx hit)
- ✅ Bias accuracy per variant + **lift vs 50%** + **agreement lift**
- ✅ Three plays (breakout / retest-cont / fade-to-mid): win · R:R · expectancy
- ✅ Range-size terciles → break% + median ext + P75 stretch ext + 0.5x-hit
- ✅ First-break-dir = day-winner rate
- ✅ IB mid as % of daily range
- ✅ Regime conditioning: VIX bucket, DOW, range bucket, prior-day result on every headline

**Delegated to Edgeful (beyond what Pine does, by design):**
- Full-ladder play expectancy (partial TPs + runner), not just single-target win/loss
- Multi-way slicing that's sample-starved in Pine: DOW × play, bias × gap-dir, etc.
- Cross-session sequencing (§3.6) — needs the 18:00 day-roll key across all slots
- Dual NY-AM FVG variants (first-RTH-FVG vs first-10–11-FVG) at full sample
- VIX/regime conditioning on every headline (Pine has no VIX feed)
- Validating Pine's raw-vs-bias-aware extension definitions on identical dates
- 20-year samples so DOW / range-bucket / agreement cells are statistically meaningful
  (in Pine these are noise at ~15 samples/cell; the layout is the template, not the truth)

---

## 6. Open items
**Resolved:**
- Gap reference: NY AM → prior RTH close; overnight slots → prior same-slot IB close (§2.2).
- Bias grading target: track **both 0.5x and 1x** separately (§2.6).
- Range buckets: **terciles of range_pct** per (symbol, slot) (§2.1).
- Formation bias sign corrected: low-forms-first ⇒ bullish (§2.5).
- Three plays defined with default levels (§2.8): ① breakout tgt 1x / stop opp boundary;
  ② retest-cont enter mid, tgt 0.5x / stop opp boundary; ③ fade enter boundary after 0.25x
  overshoot, tgt mid / stop 0.5x. All configurable.
- SUGGESTED selector: highest-win-rate play (consider highest-expectancy in Edgeful) (§3.9).
- Event timing: capture both **mode** (15-min clock bucket) and **median** (§2.9).

**Still to decide / validate during build:**
1. **Outcome-deadline per slot** (§1.2) — Tokyo→02:00, London→06:00, Midnight OR→EOD
   confirmed; confirm the Globex deadline (Tokyo open vs run to London).
2. **False-break min-extension threshold** (§2.3) — default 0.5x; test 0.25x (ICT min).
3. **Play ladder structure for Edgeful** (§2.8/§3.8) — define the partial-TP / runner rules
   for full expectancy (cover-the-queen %, TP1, TP2, runner trail).
4. **Formation vs Close-Dir redundancy** — in the Pine Globex sample they read nearly
   identically; confirm across all slots whether to keep both or drop one.
5. **Manual back-test validation** — the three-play win rates and range-tercile extension
   targets are the numbers to verify by hand first, since they drive SUGGESTED and sizing.
