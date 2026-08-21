# CISD Engine Logic Audit & Findings

> **Status:** Active audit. Last updated 2026-08-20.
> **Scope:** Comparison of three CISD implementations (tncylyv reference, our default pivot kernel, our strict canonical kernel) and a corrective action plan.

---

## 1. Background

A **Change in State of Delivery (CISD)** marks the moment the IPDA shifts from buy-side to sell-side (or vice versa). In all three implementations surveyed here, the trigger is conceptually the same:

1. Track a bullish or bearish "delivery run" — a contiguous series of same-direction candles.
2. Pick a reference **open price** from that run.
3. Fire a CISD event when `close` crosses that reference price against the run direction.

Where the implementations diverge is **which open** they pick, **how often** they re-anchor, and **what gating** they apply. These differences explain why we observe the tncylyv reference drawing **fewer but more meaningful** CISD levels than our indicator.

See also the older concept primer at [`docs/strategies/initial_balance_break/CSD_CISD.md`](CSD_CISD.md) for the ICT theory.

---

## 2. Implementations Surveyed

| Label | File | Used by |
|---|---|---|
| **tncylyv reference** | `scripts/indicators-pine/cisd_reference/CISD_by_tncylyv.pine` | Standalone TradingView study |
| **Our default pivot kernel** | `scripts/libs_py/cisd.py :: _compute_cisd_kernel` | Live NinjaTrader bot, TradingView indicator `IFVG_CISD_MTF_Indicator.pine`, default `compute_cisd()` |
| **Our strict canonical kernel** | `scripts/libs_py/cisd.py :: _compute_cisd_strict_kernel` | `compute_cisd(canonical=True)` opt-in only |

---

## 3. The Bug We Found

### Symptom
The tncylyv reference finds **fewer but more accurate** CISD levels. Our PineScript indicator fires **more** CISD events and **misses the levels that actually matter**.

### Root Cause (two compounding defects)

#### Defect 1 — Wrong reference open

| Implementation | Open chosen as the CISD level |
|---|---|
| tncylyv | **Extreme open** of the full delivery run (lowest open for a bull run, highest open for a bear run). This is the "last defense" — the open price nobody has broken. |
| Our default | **First** open in the backward walk (oldest candle of the run). Often far from the move origin and easily crossed by noise that isn't structurally meaningful. |
| Our strict | First open of the run. Same issue. |

**Effect:** Our levels sit at arbitrary candles inside the run. tncylyv's level sits at the most defended candle — the one whose open has never been touched by an opposite close during the entire delivery.

#### Defect 2 — Pivot-stacking instead of single continuous level

| Implementation | Re-arming behavior |
|---|---|
| tncylyv | **One continuous level per regime.** Every new extreme in the bias direction re-scans the full run (up to 500 bars) and re-anchors the level to the true extreme open. The level slides with the trend. |
| Our default | **One level per 3-bar pivot.** Every fresh opposite pivot arms a brand-new level. Intermediate pivots inside the same regime get armed too, producing a stack of lines — most of which are noise. |
| Our strict | One level per sweep. Same stacking problem, gated by sweep + body-close. |

**Effect:** We draw a line at every pivot, not just the pivot that originates the move. We also freeze the level at the pivot and never re-anchor, so the line we drew stops representing the true delivery origin as the run extends.

### Why tncylyv looks "more accurate"

- **Extreme open = the real OB origin.** The lowest open in a bull run is the candle that started the move; everything above is continuation. Crossing that open is a genuine state change. Crossing the 3rd candle's open in a 10-candle run is just noise.
- **Single sliding level = no false signals from intermediate pivots.** tncylyv draws exactly one line per leg and lets it drift with the trend. Our pivot kernel draws N lines per leg and treats each as a separate CISD, so 80% are spurious.
- **No pivot confirmation needed.** tncylyv fires on `close` cross of the extreme open. Our default kernel requires a 3-bar fractal pivot first — this *adds* a gate but doesn't fix the level selection, so we still pick the wrong open even when we arm.

---

## 4. Visual Comparison

### tncylyv: extreme open, continuous, re-anchoring

```
   Bullish regime (vibes = 1)
   ─────────────────────────────────────────────
                                                 ╱  ← new high → pain_threshold := high
                                              ╱╱
                                           ╱╱╱     ← RE-SCAN entire run,
                                        ╱╱╱          find LOWEST open of all bull candles
                                     ╱╱╱
        open=100                    ╱╱╱
        ↓                        ╱╱╱
        │╱╱╲    open=98         ╱╱╱     ← bagholder_entry = extreme open
        │  ╱╲    ↓            ╱╱╱        (single sliding line, one per leg)
        │  ╱ ╲   │╱╲         ╱╱╱
        │ ╱   ╲  │ ╱╲      ╱╱╱
        │╱     ╲_│╱_╲___╱╱╱________  ← "last defense": lowest open of the run
                              │
                              │ close < this → "longs_rekt" → -CISD (one line, one trigger)
```

### Our default kernel: first open, per-pivot, frozen

```
   ─────────────────────────────────────────────
              pivot1          pivot2         pivot3   ← every 3-bar pivot arms a NEW level
                ↓                ↓             ↓
                │                │             │
   open[t-3] ←  oldest open       │             │
   (origin)                      │             │
        ╲                        │             │
         ╲    ╲   ╲___           │             │
          ╲    ╲     ╲___       │             │
           ╲___ ╲        ╲___   │             │
                pivot low       │             │
                arm = open of oldest bearish candle in ≤25-bar walk
                                  ↓
                                  arm again (different level)
                                                ↓
                                                arm again (yet another level)
   → many levels stack, most are noise, the true move-origin level
     is only ONE of them and may be missed if no pivot sits exactly on it
```

---

## 5. Corrective Action

The fix is to mirror tncylyv's behavior in both the PineScript indicator and the Python kernels:

1. **Pick the extreme open** of the delivery run (lowest for bull, highest for bear), not the first open.
2. **Re-anchor on every new extreme** in the bias direction — walk the full run again and update the level.
3. **Keep one armed level per regime** — don't stack levels on every pivot.
4. **Remove the ≤25-bar cap** — scan the full contiguous run (tncylyv uses 500).
5. Optional: keep the 3-bar pivot gate as a *confirmation* of the swing, but do not use it as the arming event.

### Affected code

| File | Change |
|---|---|
| `scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Indicator.pine` | **DONE** — Rewrote CISD block as verbatim tncylyv port. |
| `scripts/libs_py/cisd.py :: _compute_cisd_kernel` | **TODO** — Replace the first-open backward walk with the extreme-open + per-regime re-arm logic. |
| `scripts/libs_py/cisd.py :: _compute_cisd_strict_kernel` | **TODO** — Same — keep the sweep + body-close gates but use the extreme open. |

### Validation plan

1. ~~Apply the PineScript fix first (single-file, easy to verify visually on TradingView).~~ DONE
2. ~~Compile-check with `pine_check`.~~ DONE (0 errors, 0 warnings)
3. ~~Load on a 5m NQ chart, compare the drawn CISD levels against the tncylyv reference loaded on the same chart.~~ DONE — visual parity confirmed.
4. Once visual parity is confirmed, port the same logic into `_compute_cisd_kernel` in `cisd.py`.
5. Re-run the existing backtests (`scripts/research/run_ifvg_cisd_backtest.py`) and confirm the trade count drops and PF/WR improve.
6. Re-run the diagnostic CSV comparison (`scripts/research/diagnose_cisd_bar_20260819.py`) to verify event timing matches.

---

## 6. Final Design (PineScript — implemented)

The PineScript indicator (`IFVG_CISD_MTF_Indicator.pine`) now uses a **verbatim port** of the tncylyv CISD engine. The design is:

### State variables

| Variable | Type | Purpose |
|---|---|---|
| `vibes` | `int` | Current regime: +1 bull, -1 bear, 0 uninit |
| `bagholder_entry` | `float` | The extreme open of the current delivery run (the CISD level) |
| `time_machine_setting` | `int` | The `bar_index` where the extreme open candle sits |
| `pain_threshold` | `float` | Running extreme in the bias direction (highest high for bull, lowest low for bear) |

### Two-function scan model

The engine uses **two distinct functions** depending on whether the current bar matches the regime bias:

1. **`consult_the_crystal_ball(bias)`** — used when the current bar's body matches the bias (or after a regime flip, when the flip candle IS the new bias). Starts scanning from bar[0] backward. **Never returns na** — if bar[0] doesn't match, falls back to `[open[0], bar_index]`.

2. **`archaeologist_jones(bias)`** — used when the current bar's body does NOT match the bias (e.g., new high on a red candle in a bull regime). Skips bar[0] and scans backward to find the first matching candle, then walks the run. **May return na** if no matching candle is found (caller must guard).

Both functions scan up to **500 bars** backward and track the **extreme open** across the contiguous same-direction delivery run:
- Bull run (bias=+1): tracks the **lowest** open
- Bear run (bias=-1): tracks the **highest** open

### Lifecycle

```
INIT (bar_index > 10, vibes == 0)
  ├─ Determine firstImpression from candle body
  └─ consult_the_crystal_ball(firstImpression) → set bagholder_entry, pain_threshold

EACH BAR
  ├─ RE-ANCHOR: if new extreme in bias direction
  │   ├─ Current bar matches bias → consult_the_crystal_ball
  │   └─ Current bar doesn't match → archaeologist_jones
  │
  ├─ FLIP CHECK: close crosses bagholder_entry against bias
  │   ├─ shorts_squeezed = vibes == -1 and close > bagholder_entry
  │   └─ longs_rekt = vibes == 1 and close < bagholder_entry
  │
  └─ ON FLIP:
      ├─ Draw line at bagholder_entry (the crossed level, BEFORE re-arm)
      ├─ Draw label (+CISD / -CISD)
      ├─ Strategy-grade trigger (with displacement + HTF filter)
      └─ Flip regime: consult_the_crystal_ball(new_bias) → re-arm
```

### Line drawing

Lines are drawn using `line.new()` (not `plot()`) on **every** regime flip:
- `x1 = time_machine_setting` (bar where the extreme open sits)
- `y1 = bagholder_entry` (the extreme open price)
- `x2 = bar_index + i_extendLines` (trigger bar, optionally extended)
- `y2 = bagholder_entry` (same price — horizontal line)
- Color: green for +CISD (bullish flip), red for -CISD (bearish flip)

The active CISD level is also shown via `plot(bagholder_entry, style=plot.style_linebr)` so it's visible between triggers.

### Strategy-grade trigger vs raw flip

The indicator separates two concepts:
- **Raw regime flip** (`shorts_squeezed` / `longs_rekt`): always draws a line, no filters
- **Strategy-grade trigger** (`bullCisdTrigger` / `bearCisdTrigger`): gated by displacement (`passesDisp`) and HTF trend alignment (`bullHtf` / `bearHtf`)

This ensures the CISD visualization always shows every state change (matching tncylyv), while the strategy only fires on qualified setups.

### Bugs fixed during implementation

1. **na deadlock**: `archaeologist_jones` can return `na` when no matching candle is found. Assigning `na` to `cisdLevel` kills all future triggers because `close > na` and `close < na` are both falsy in Pine. Fix: guard with `if not na(p1)` before assigning.

2. **if/if double-fire**: Using two separate `if` blocks for shorts_squeezed and longs_rekt (instead of `if/else if`) caused both to fire on the same bar — the second block used the already-overwritten level from the first. Fix: use `if ... else if`.

3. **Level snapshot timing**: Drawing the line after re-arming overwrote `cisdLevel` with the new regime's level, so the line was drawn at the wrong price. Fix: the tncylyv approach draws the line **inside** the flip block, before re-arming, using the current `bagholder_entry` which is still the old (crossed) level.

4. **Floating-point equality in extreme_shift loop**: The `for k = 0 to temporal_shift` loop uses `open[k] == extreme` to find which bar had the extreme open. Floating-point comparison can fail, leaving `extreme_shift = na` → `bar_index - na = na` → `line.new(na, ...)` fails silently. (Not yet fixed in the verbatim port — tncylyv has the same theoretical issue but it works in practice because the extreme value is always copied directly from an `open[k]` so the comparison is exact.)

---

## 7. Open Questions

- **Run length cap.** tncylyv uses 500. Our default uses 25. Is 500 ever too generous (pulls in stale opens from a prior leg)? Empirical test needed — run both and compare.
- **Pivot vs no pivot.** tncylyv arms without a pivot. Our default requires a 3-bar fractal. Which produces fewer false CISDs when combined with the extreme-open fix? Unknown until we test.
- **Sweep + body-close gating (strict kernel).** Keep it as an option, but the default should match tncylyv until proven otherwise.
- **Python port.** The PineScript is now verified. Next step is porting the same `consult_the_crystal_ball` / `archaeologist_jones` model into `cisd.py :: _compute_cisd_kernel`.

---

## 8. Parity Bug Fixes (2026-08-21)

Cross-platform parity review found three signal-generation bugs and two ICT-logic
defects. All fixed across Python / C# / PineScript.

### Fixed

1. **iFVG crossing condition (C# only).** C# `isBullIfvg`/`isBearIfvg` lacked the
   `close[1]` crossing guard, so the flag stayed `true` on every subsequent bar and
   the baseline variant over-fired (425 vs 131 trades). Added the crossing guard and a
   separate inversion pool that removes inverted zones (mirrors `ifvg.py`).

2. **Dead `legHasBpr`/`legHasIfvg` flags (C# + Pine).** These were declared and reset
   but never set `true`, so V1 always evaluated false (0 trades on NT8/TV). Now set
   from `isBullBpr`/`isBearBpr` and `isBullIfvg`/`isBearIfvg` during the leg.

3. **FVG directional-candle inconsistency.** Python required `c0 > o0` (bull) /
   `c0 < o0` (bear); C#/Pine did not. Added `require_directional_candle` to
   `compute_ifvg` and `compute_bpr` (default `False` to match C#/Pine).

4. **V1 logic (all platforms).** Changed from `priorLegHasBpr OR (priorLegHasIfvg AND
   FVG_count >= 1)` to `priorLegHasBpr OR priorLegHasIfvg`. The prior leg's BPR or
   IFVG is the reversal evidence; the FVG-count AND was internally inconsistent.

5. **V2 logic (all platforms).** Now counts **unmitigated** FVGs in the opposing
   delivery run (removed when filled) instead of raw FVG count.

### Entry mechanism (testable)

Added a 3-way entry mechanism across all platforms:

| Mechanism | Python | C# | Pine | Behavior |
|---|---|---|---|---|
| `market` | default | `EntryMechanism=0` | `"Market"` | Fill at signal bar close |
| `cisd_limit` | `entry_mechanism="cisd_limit"` | `EntryMechanism=1` | `"CISD Limit"` | Limit at CISD level; fills only on retrace |
| `breakout` | `entry_mechanism="breakout"` | `EntryMechanism=2` | `"Breakout"` | Stop entry beyond signal bar extreme |

The Python simulator (`simulate_trade_policy`) resolves the fill bar for each
mechanism; C# uses `EnterLongLimit`/`EnterLongStopMarket`; Pine uses `limit=`/`stop=`
on `strategy.entry`. This is the primary knob to validate which entry works best.

---

## 9. Backlog — Confluence & Target Enhancements

To be added one at a time after the parity bugs are confirmed fixed. Each item is a
separate, independently testable layer.

### 9.1 Multi-timeframe CISD confirmation (bias confluence)

- Compute CISD on 1m, 3m, and 5m simultaneously.
- Bias confluence score = how many TFs agree on the current delivery direction.
- Use as a **bias filter** (only trade with the majority TF direction) and/or a
  **signal-strength weight**.
- Goal: filter counter-trend CISD flips that only appear on one TF.

### 9.2 Multi-timeframe FVG confluence (entry refinement)

- Compute FVG/iFVG on 1m, 3m, 5m.
- Prefer entries where the execution-TF FVG overlaps a higher-TF FVG (stacked
  imbalance = stronger institutional level).
- Goal: find the best entry point within a confirmed bias.

### 9.3 Liquidity levels (targets & bias)

- Detect buy-side / sell-side liquidity pools (equal highs/lows, swing highs/lows,
  session highs/lows).
- Use liquidity pools as **targets** (price is drawn to liquidity) and as **bias
  context** (which side of liquidity is being swept).
- Goal: replace fixed R-multiple targets with liquidity-based targets where
  appropriate, and confirm CISD flips that occur at a liquidity sweep.

### 9.4 HTF FVG targets

- Track unmitigated HTF (15m/1h) FVGs as magnet targets.
- When a trade is in profit, extend the runner toward the next HTF FVG instead of a
  fixed 2.5R.
- Goal: capture larger runners on trend days while keeping the queen scale-out.

### Suggested order

1. 9.1 (bias confluence) — highest impact on false-signal reduction.
2. 9.2 (entry refinement) — pairs with the entry-mechanism testing.
3. 9.3 (liquidity) — targets + bias context.
4. 9.4 (HTF FVG targets) — runner extension.

Each layer should be validated in isolation (Python first, then port to C#/Pine) and
compared against the current baseline before stacking.