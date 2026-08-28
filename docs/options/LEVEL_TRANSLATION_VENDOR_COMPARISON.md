# GEX Level Translation — Vendor Comparison & Aligned-Walls Hypothesis

**Date:** 2026-08-28
**Status:** Research confirmed; aligned-walls hypothesis pending backtest
**Related:** `scripts/streaming/options/futures_translator.py`, `scripts/options_research/level_source_backtest.py` (Phase A)

## 1. Purpose

Record how the industry translates GEX levels between products (SPX↔SPY↔ES, NDX↔QQQ↔NQ),
confirm our implementation matches or exceeds it, and register the **aligned-walls hypothesis**
as a quantifiable, backtestable claim before we build the level-source evaluation.

## 2. Vendor Methodologies

### SpotGamma (article: "GEX Levels for SPY, QQQ, ES and NQ", Aug 2026)

Simple arithmetic the trader applies mentally:

| Pair | Method |
|---|---|
| SPX → SPY | divide by 10 (fixed) |
| SPX → ES | additive — "apply directly, mentally adjust for the day's basis" |
| NDX → QQQ | divide by ~41 ("ratio drifts; check periodically") |
| NDX → NQ | additive — cash level + basis adjustment |

Conceptual basis: gamma is computed at the **complex level** — the S&P complex
(SPX + SPY + ES) and Nasdaq complex (NDX + QQQ + NQ) each hedge into the same
underlying market, so dealer gamma structure computed from index options shapes
price action in every product of that complex. Translation is "arithmetic, not
conceptual."

Also asserted (unquantified): SPY carries its own OI structure at round-dollar
strikes layered on top of the SPX map, and **"where they align (an SPX 5000 wall
over a SPY 500 wall) the level is strongest."**

### MenthorQ (Levels Conversion guide + TradingView indicator)

Two formal methods, user-selected:

- **Spread** = Futures Price − Index Price (additive)
- **Ratio** = Futures Price ÷ Index Price (multiplicative); e.g. QQQ 500 / NQ 21000 → ratio 42 → multiply every QQQ level

Conversion timing:

- **Auto mode**: ratio computed from **previous day's closing prices**. Documented con:
  ETF closes 16:00, futures close 17:00 — the two closes are from *different moments*,
  so the auto ratio can embed a mismatched basis snapshot.
- **Manual mode**: trader recomputes intraday during 09:31–16:00 ET when both trade.
  Documented pro: "tighter to the live market" on days when the basis moves.

Their operational rules: "the ratio only needs to be updated **once per day**";
use the same method across platforms or levels won't align.

## 3. Our Implementation (`futures_translator.translate_to_futures`)

| Aspect | Ours | SpotGamma | MenthorQ |
|---|---|---|---|
| Additive vs multiplicative | Auto: multiplicative when ratio deviates >2% from 1.0 | Fixed per pair, human-chosen | User picks spread or ratio |
| QQQ → NQ | Multiplicative (ratio ≈ 41) | ÷ ~41 | × ratio (~42) |
| SPX → ES | Additive (spread) | Additive | Either |
| Basis timing | **Today's simultaneous opening prices** (`fut_open − spot_open`, `USE_OPENING_BASIS=True`), captured once, persisted per session in `basis_anchors.json` | "day's basis" / mental estimate | Auto = prev-day closes (mismatch risk); Manual = intraday recompute |
| EM magnitude | ±EM scaled by ratio in multiplicative mode | not discussed | not discussed |

**Conclusion:** same fundamental math; our basis anchoring (today's simultaneous
opens) is strictly more precise than MenthorQ's prev-day-close auto mode and
SpotGamma's manual mental adjustment, with zero operator effort. MenthorQ's own
"update once per day" guidance validates our once-per-session anchor design.

## 4. The Aligned-Walls Hypothesis (to backtest)

> **Claim:** a dealer wall corroborated by two or more sources of the same
> complex (e.g. an NQ-native wall coinciding with a translated QQQ wall, or an
> SPX wall coinciding with a SPY wall at the mapped strike) holds better than
> either source alone.

SpotGamma states this anecdotally; no public backtest exists. This is a
quantifiable edge opportunity:

- **Metric:** for each level, compute `alignment_score` = number of independent
  source complexes producing a wall within tolerance (e.g. ≤ 0.1× EM) of it.
- **Test:** stratify hold-rate / first-touch-rejection rate by alignment_score.
- **Product:** if confirmed, publish `alignment_score` as a confidence weight on
  every unified level; use it to rank walls when they conflict.
- **Second metric (translation quality):** hold rate vs basis staleness —
  validates our opening-anchor against MenthorQ's prev-close approach.

## 5. Evaluation Plan

Phase A (immediately — clean history): SPX / SPY / SPY-translated→ES from the
Schwab cash path (valid back to 2026-05-11 in `data/options/unified_levels_*.json`).

Phase B (after 3–4 weeks of clean data post 2026-08-28 fixes): NQ/ES RTD-native
levels join the comparison — their history before the fix is polluted (fake OI,
frozen spot) and must not be scored.

Ground truth per level: 1m futures bars (`data/live/live_storage_-*.parquet`),
metrics = reachability (touch rate), first-touch hold rate, break continuation,
reversal magnitude after first touch.

## 6. Cross-Validation Against Vendors

MenthorQ publishes level sets (walls, HVL, 0DTE) on TradingView; SpotGamma has a
free daily SPX GEX chart. Both can be scraped/overlaid as an independent
"vendor wall" source in the same backtest harness — the vendor level becomes one
more `alignment_score` contributor rather than a separate evaluation track.