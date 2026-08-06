# Line vs Apex & 3-Hour Block Sequencing — Master Domain Blueprint

> **Source**: NotebookLM Pack Transcripts, *Pack Oct Bootcamp*, & Daily Profiler SOP
> **Purpose**: Technical blueprint detailing 3-Hour Block Sequencing (09:00–12:00 / 12:00–15:00), 3-Hour Line (Trend Continuation) vs 3-Hour Apex (Reversal) signatures, 0-5 box 10 bps threshold tracking, and Monte Carlo price cloud interpretation.

---

## 1. Core Philosophy: Line vs Apex

Rather than relying on visual swing indicators (such as Cody's Valid H/Ls), Matt Mickey and Austin analyze intraday order flow using **3-Hour Block Sequencing**:
- **3-Hour Line (Continuation)**: Hourly candles (09:00, 10:00, 11:00) stack sequentially in one direction. Order flow maintains unbroken directional momentum.
- **3-Hour Apex (Reversal)**: Hour 2 (10:00 AM) reverses Hour 1 (09:00 AM) by sweeping Hour 1's extreme, rejecting past the 50% midpoint, and establishing a major daily pivot (HOD or LOD).

---

## 2. 3-Hour Block Structure & Quarters

The RTH session is divided into two primary 3-hour blocks:
- **Block 1 (Morning Expansion)**: 09:00 AM – 12:00 PM EST (09:00, 10:00, 11:00 hourly candles).
- **Block 2 (Afternoon Drift/Trend)**: 12:00 PM – 15:00 PM EST (12:00, 13:00, 14:00 hourly candles).

Each hourly candle is evaluated in **Quarters**:
- **Q1 (0-15m)**: Initial directional attempt & 0-5 min box establishment.
- **Q2 (15-30m)**: Mid-hour expansion or consolidation.
- **Q3 (30-45m)**: Secondary push or false breakout rejection.
- **Q4 (45-60m)**: Hourly candle close & setup for next hour's open.

### The 0-5 Box & 10 Basis Point (0.10%) Rule
- For any hourly candle, capture the High-to-Low range of the **first 5 minutes (0-5 Box)**.
- **RTH Momentum Threshold**: Price must breach the 0-5 box by at least **10 basis points (0.10%)** in Q1 to confirm true sustainable momentum.
- **False Breakout Rule**: If price fails to reach 10 bps and returns inside the 0-5 box, it flags a false breakout and establishes an **Instant High/Low**.

---

## 3. The 5-Stage Reversal Counter & Scoring System (Apex Verification)

To eliminate binary assumptions and measure reversal conviction, the 4-step counter is expanded into a **Weighted 5-Stage Scoring System**:

- **Step 0 (Daily Candle Science Trigger)**: Does price breach the $C_2$ Open price ("Line in the Sand") in the direction of the reversal?
- **Step 1**: Does price breach & accept outside the 09:30 RTH open range?
- **Step 2**: Does price accept past the 09:00 hour's 50% midpoint line?
- **Step 3**: Does the 10:00 AM hourly candle take out the 09:00 AM high or low?
- **Step 4 (Instant Extreme Rule)**: The 10:00 AM candle's $Q_1$ (0-15m) range **fails to breach its 0-5 box by $\ge 10$ bps** (or ticker-specific `momentum_threshold_ticks`) and reverses, establishing an **Instant High/Low**.

### Scoring & Regime Classification:
- **Score 0**: **Trend Locked (Line)** — Pure 1-sided momentum. Buy dips / sell rips.
- **Score 1 – 2**: **Reversal Watch / Alert** — Early warning. Tighten stops; do not enter breakout trades.
- **Score 3**: **Probable Apex** — High likelihood of major pivot. Prepare counter-trend setups.
- **Score 4 – 5**: **Confirmed Apex Reversal** — Reversal locked in. Target opposite session extremes or Goalpost sweeps.

---

## 4. Monte Carlo Price Cloud Interpretation

The Monte Carlo Cloud condenses 25,000 historical intraday 5-minute price trajectories ("wiggles") into:
- **Central Mean Path**: The highest-probability average intraday trajectory.
- **Upper / Lower Std-Dev Bands ($\pm 1\sigma, \pm 2\sigma$)**: Expected volatility boundaries.

### How Mickey Interprets the Monte Carlo Cloud:
1. **Firecracker / Trending Days**: Price rides along the $+1\sigma$ or $-1\sigma$ outer band without pulling back to the central mean line.
2. **Mean-Reversion / R1 Days**: Price continuously crosses the central mean line throughout the session (spending 4+ hours touching the 09:30 open print).
3. **Apex Reversals**: Price reaches the outer $+2\sigma$ band during 09:30–10:00 AM, exhausts, and reverts across the central mean line by midday.

---

## 5. Software Verification Checklist

To verify our Python implementation (`scripts/wargaming/profiler_feature_extractor.py`), the module must pass:

- [ ] **0-5 Box Range & 10 bps Calculation**: Computes 0-5 min range and calculates exact basis point breach percentage for each hour.
- [ ] **4-Step Counter Verification**: Evaluates Steps 1 through 4 sequentially on 1m OHLCV data for 10:00 AM candle.
- [ ] **3-Hour Line vs Apex Classification**: Correctly flags whether Block 1 (09:00–12:00) formed a Line or an Apex.

---
*Document Location: `docs/profiler/line_vs_apex_blueprint.md`*
