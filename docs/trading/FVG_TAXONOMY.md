# FVG Taxonomy — High-Probability Gap Qualifiers (HPG Study)

> Created 2026-08-30. Consolidates the HPG (High Probability Gap) research thread: ICT gap theory
> (breakaway / measuring / exhaustion), candle-anatomy qualifiers, time-anchored First Presentations,
> and MTF stacking. Research goal: **not every FVG matters — classify which ones do, then quantify.**
>
> Companion indicator: `scripts/indicators-pine/fvg_taxonomy/FVG_Taxonomy.pine`

---

## 0. Core claim (from ICT 2023 Advanced Gap Theory + user's chart studies)

> "Price usually respects the high, low, or mean threshold (midpoint) of gaps (FVG, BPR,…)."
> — ICT 2023 Mentorship, Advanced Gap Theory Introduction (forum.ictsharks.com/t/366)

An FVG in isolation is ~coin-flip (Secuora mechanical baseline: WR 29.4%, PF 0.43 on 2,232
unfiltered 5m trades). All edge lives in **qualifiers**. External backtests (LiquidityScan, Jun 2026)
put filled/confluence-qualified FVG fill probability at 40–60%. This taxonomy enumerates the
qualifiers ICT actually teaches.

**Unifying mechanism** (from ICT Trader Round Up, Apr 21 2026, t=01:04:11): stale anchor gaps are NOT
support/resistance. They are **catalysts**: price returns into a stale anchor FVG near a small
liquidity pool (relative equal H/L) → that touch triggers a run on the pool. The gap is a timing
device for a liquidity sweep, not a fade level.

---

## 1. Spatial qualifiers — gap's role in the dealing range

### 1.1 Breakaway Gap (first FVG of a new dealing range)
- **ICT 2022 Mentorship (Dealing Ranges, forum.ictsharks.com/t/511):** "A breakaway gap is a fair
  value gap that remains unfilled because the price rushes to remove liquidity in the opposite
  direction... When we fail to reach into an FVG and move away from it, then it's likely a
  breakaway gap and won't be traded back to immediately."
- User's chart annotation: *the first FVG in a dealing range is typically a breakaway gap, and when
  tested it tends to create a reaction. Same holds for the OB at that origin.*
- **Detection rule:** first FVG formed after a dealing range breaks (new swing low→high or
  high→low established). Validity = FVG + BOS confirmation + origin zone.
- **Behavior:** stays unfilled while trend runs → when price finally returns, expect a *reaction*
  (held = trend continuation from the gap; reclaimed through = breakout failing).
- **Holding mechanisms after revisit** (tradingfinder.com/education/forex/ict-breakaway-gaps/):
  Breaker Block, Inverse FVG, BPR — the three structures that form *at* the return and give the entry.

### 1.2 Measuring Gap (continuation / runaway gap) — the projection ruler
- **ICT 2023 Advanced Gap Theory:** a measuring gap forms **mid-way between inception and terminus**
  of a move (Infinity Trading notes: "ICT says a Measuring Gap is a FVG that forms half-way between
  Inception and Terminus"). It should remain open/unfilled.
- **Projection:** terminus ≈ `2 × measuringGap − inception` (gap is the midpoint of the move).
  The projected target must sit beyond liquidity (below SSL / above BSL) to be meaningful.
- **User's chart annotation:** "FVGs with an OD always are targets" — pairs with 1.3 below.
- Together with the breakaway gap, a trending day has a signature: **breakaway (start) → measuring
  (middle) → exhaustion (end)**. Classifying which of the three a fresh FVG is tells you whether
  the day is still in the middle of a move (targets live) or at the end.

### 1.3 Overlapping wick / OD (overlapping defense)
- An FVG whose zone overlaps the wick of an adjacent candle carries a "defense" — a precise
  sub-level inside the gap (usually overlapping wick extreme ≈ wick midpoint refinement).
- User's chart annotation: *FVGs with an OD always are targets.* The overlap wick level is the
  refined draw, not the full gap extent.

### 1.4 Opposite-direction third candle (weak displacement → trap/IFVG)
- For a strong FVG, candle 3 should close in the displacement direction (close confirmation:
  `close > high[2]` for bull). Candle 3 printing *against* the gap = no continuation conviction.
- Consequence: these gaps tend to be **consumed/swept** (the gap itself becomes the draw) and then
  act as a **breaker/inversion** — consistent with the user's chart where the FVG sat in the path of
  the measured move and was traded through. Tag these differently; do NOT fade them blindly.

---

## 2. Time-anchored qualifiers — which stale gap the algorithm calls back

### 2.1 First Presented FVG (FPFVG) — RTH
- First valid FVG forming 9:30–10:00 NY, on LTF (1m/5m). Published concept + TradingView indicator
  (TakingProphets). Some variants add a **"Held test"**: the gap must not be fully reclaimed early
  to remain a valid reference.
- The session's earliest institutional imbalance; used as reference/magnet through the day (and
  across days when unmitigated).

### 2.2 Midnight 1st presented FVG / NDOG complex
- Midnight = the algorithm's day-start reference (true day open).
- **NDOG** = prior 5pm close → 6pm reopen gap (some sources: prior-midnight open → today's open).
  ICT: "The NDOG functions identically to the NWOG" — a daily FVG the algorithm tends to address
  before delivering the session direction. On bullish days midnight open acts as dynamic support.
- Repo already tracks NWOG/NDOG/RTH gaps (ict_engine gaps feature) — this is about anchoring the
  *first FVG printed after midnight open* as a session anchor as well.

### 2.3 First FVG of any hour — Silver Bullet family
- ICT Silver Bullet spec: first FVG inside the window (03–04, 10–11, 14–15 ET), entry at CE
  (gap midpoint), 15–20 handle target. The "1st FVG of the hour" generalizes this to every hour.
- User holds significance for the first FVG of each hour, any timeframe.

### 2.4 Friday & Monday First Presentations — weekly anchor carry-forward (NEW, Apr 2026)
- **ICT Trader Round Up, Apr 21 2026** (x.com/i/spaces/1kJzDMpNZaaKv, t=01:04:11, 01:04:48, 01:06:32):
  - Carry forward the **First Presented FVGs of the last two Fridays and Mondays**.
  - "By utilizing those you can literally just trade volatility... trade without a bias": return to
    one of these anchor gaps near a relative-equal pool → run the pool. 15–20 handle objective.
  - Biased version: if price traded *below* Friday's or previous Monday's First Presentation and
    returns back into it **during the first dealing range (9:30–10:30 ET)** → catalyst to sell
    toward the HTF (daily/weekly) draw. "First catalyst to send price in the favor of the higher
    time frame draw."
  - Monday's First Presentation can be below last Friday's — use whichever is closer in proximity.
- This is the newest refinement (2026); almost no published quantification exists → **research
  frontier**. First thing to quantify in the HPG study.

---

## 3. Confluence qualifiers

### 3.1 MTF stacking (HTF FVG + nested LTF FVGs)
- LTF FVGs sitting inside an HTF FVG = multi-timeframe liquidity void ("cluster") = high-probability
  S/R zone (beelaa.com multi-timeframe FVG priority; VaultCharts stacked FVGs).
- Priority when timeframes conflict: **higher TF FVG wins**.

### 3.2 FVG ↔ BPR ↔ IFVG family
- **BPR:** overlap of opposing FVGs (bull + bear) — consolidation launchpad, precise low-risk entry.
- **IFVG:** an FVG closed through flips to opposite side. **Not every IFVG matters** — the ones that
  matter are those forming *at* breakaway-return points (per 1.1 holding mechanisms) and/or with
  MTF stacking.

---

## 4. Detection summary (rule-ready)

| Qualifier | Rule | Type |
|---|---|---|
| Breakaway gap (BAG) | Candle-anatomy (Arjo/MK definition, no swings needed): bearish = `c1.low <= c2.open` AND `c3.high >= c2.close` AND `c3.close < c2.low` → void spans c1.low↔c3.high around the origin displacement candle c2 (bullish mirror). Satisfies VI by construction (c3 body clears c2 body). c2 IS the dealing-range origin, so "first FVG of the dealing range" emerges naturally. Weak-c3 variant = same anchoring but c3 closes back inside c2's range. | spatial |
| Measuring gap | Unfilled FVG ≈ midpoint of inception→terminus move (CE within ~15% of swing midpoint) | spatial |
| OD wick | FVG overlaps adjacent candle wick → sub-level inside | anatomy |
| Opposite c3 | candle 3 closes against displacement direction | anatomy |
| FPFVG | first FVG 9:30–10:00 NY | time |
| Midnight 1st FVG | first FVG after midnight open | time |
| Hourly 1st FVG | first FVG of each clock hour | time |
| Fri/Mon First Presentation | last-2-weeks Fri+Mon first-presented FVGs, carry-forward | time |
| MTF stack | LTF FVG inside HTF FVG | confluence |
| BPR | overlap of opposing FVGs | confluence |
| IFVG | FVG closed-through → flip (filter: only at breakaway returns / stacked) | confluence |

## 5. Test plan (HPG study — next)

1. **Labeler first:** produce per-gap labels (all qualifiers above) from 1m live storage + historical.
   Vectorized in `pa.py` style; the fill/inversion tracking from `ib_fvg_detail` pipeline is reusable.
2. **Reaction metric:** for each qualifier cohort measure — P(reaction at touch), reaction size
   (statistical normalization per ADR-002: % not points), P(pool-take within window), P(HTF-draw
   follow-through). Baseline = unqualified FVG cohort.
3. **Specific ICT claims to test:**
   - Fri/Mon First Presentation: "price traded below anchor → return in 9:30–10:30 window →
     sell-off toward HTF draw" (measure P(catalyst) vs baseline).
   - Measuring gap terminus projection: does `2×gap − inception` hit beyond-liquidity terminus?
   - Breakaway return reaction vs generic FVG return reaction.
4. Harness: reuse `BacktestEngine` (scripts/analysis/range_strategy_comparison.py:509); data via
   `load_fused_data()` for deep history.

## 6. Sources

- forum.ictsharks.com/t/511 — ICT 2022 Mentorship Dealing Ranges (breakaway gap definition)
- forum.ictsharks.com/t/366 — ICT 2023 Advanced Gap Theory (measuring gap, respect thresholds)
- tradingfinder.com/education/forex/ict-breakaway-gaps/ — breakaway anatomy + holding mechanisms
- innercircletrader.net/tutorials/ict-breakaway-gap/ — BISI/SIBI variants (403'd, cite only)
- liquidityscan.io/blog/fvg-fill-probability-what-backtests-reveal-about-win-rates — 40–60% baseline
- secuora.net/strategy/fvg-strategy — unfiltered mechanical baseline (PF 0.43)
- aurora-x.app/concepts/first-presented-fvg — FPFVG definition
- ictkillzone.com/ict-ndog, ictkillzone.com/ict-midnight-open — midnight/NDOG complex
- x.com/i/spaces/1kJzDMpNZaaKv (Apr 21 2026, t=01:04–01:07) — Fri/Mon First Presentation carry-forward
- User chart annotations (2026-08-30) — breakaway/OD/opposite-c3 reading of live charts