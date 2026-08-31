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

### 6.1 CBOE vendor feed (ACTIVE 2026-08-30) — primary cross-validation source

Unusual Whales Periscope was considered first: **not scrapable** (login-gated),
and its API is paid. Instead we use **CBOE's free delayed-quotes option chains**
(`https://cdn.cboe.com/api/global/delayed_quotes/options/{ROOT}.json`; index
roots need the underscore prefix: `_SPX`, `_NDX`, `_RUT`, `_DJX`, `_VIX`).
Full chain per root with per-contract **OI + IV + gamma** (verified working,
refreshed continuously, delayed ~15 min). No futures options (CME is bot-blocked);
CBOE covers the **cash universe only** — SPX/SPY/QQQ etc. For NQ/ES the vendor
signal is *translated* (QQQ→NQ, SPY/SPX→ES), the same translation we score above.

**Why it adds value beyond our existing stack** (dolt `post-no-preference/options`
local DB, Schwab API, TOS RTD):
- Dolt: EOD via `dolt pull`, **no per-contract OI** — cannot build gamma walls.
- Schwab: futures options **monthly-only, zero IV**; cash path OK but slow.
- RTD: real-time per-strike OI/IV but **COM topic budget caps strike count**
  (root cause of the fake-OI/frozen-spot bugs fixed 2026-08-28).
- CBOE: one HTTPS call = full chain (~28k SPX contracts), broker-independent,
  CBOE-computed greeks — a **methodology-independent second opinion**.

Also analyzed (2026-08-30, parked): **VS3D / VolSignals** ? signed dealer-position framework with inverted wall logic (tests extend-through, balance pins) + charm-flip bias. Full analysis and revisit triggers: [VS3D_FRAMEWORK_ANALYSIS.md](VS3D_FRAMEWORK_ANALYSIS.md).

Different dealer-wall definition caveat: raw max-gamma walls land on far round
strikes (SPX raw CW=8000 vs our CW 7725 on 2026-08-28). Near-spot band ranking
(±2%) is the comparable defintion (see §7 first results). Both definitions are
kept; the backtest decides which is predictive, not taste.

### 6.2 Infrastructure (`scripts/options_research/cboe_vendor_fetch.py`)

- **core**: every 15 min 09:33–15:48 ET Mon–Fri, roots `_SPX SPY _NDX QQQ _VIX`;
  computes call/put wall (max |gamma×OI×100×S²×0.01| per side), gamma flip,
  net/call/put GEX $mm, max pain, OI PCR → appends `data/options/vendors/cboe_walls.csv`.
  Raw chains archived only at anchors 09:33/11:33/13:33/15:48 ET.
- **weekly**: Saturday 11:00 ET — full root universe refresh from CBOE symbol CSV
  (3,027 roots), every root fetched (2958 OK; **69 structurally 403** = adjusted/
  unit/warrant symbols listed in `cboe_unservable_roots.txt`), one-week
  `cboe_weekly_roots_YYYY-MM-DD.csv`. Self-discovers CBOE's **429 rate limit**:
  3 req/s throttle + Retry-After backoff; abort if >25% failures.
- Scheduled: Windows tasks `TVODL\CBOE_vendor_core` (every 15 min) and
  `TVODL\CBOE_vendor_weekly` (Sat 11:00 ET). Both **self-guard** (ET window,
  stale-chain check ⇒ closed market auto-skips). Chains auto-pruned after 30 d.
- **Kill switch** when the experiment is judged valueless:
  `Disable-ScheduledTask -TaskPath \TVODL\ -TaskName CBOE_vendor_core` (+ `_weekly`).

### 6.3 First cross-validation result (2026-08-28 data, ran 2026-08-30)

`scripts/options_research/cboe_validate_now.py --date 20260828 --snapshot 1615`:

| Pair | Ours | CBOE raw | CBOE near-spot | Verdict |
|---|---|---|---|---|
| SPX CW | 7725 | 8000 (rank 7 of 62 in ±2% band) | 7700 | **disagree** |
| SPY CW | 770 | 770 (rank 1) | 770 | **agree exactly** |
| QQQ CW | 718 | 715 (rank 7/33) | 715 | near |

Interpretation: definitions differ (raw global max-gamma vs near-spot
concentration). This is exactly the signal the aligned-walls backtest needs —
agreement/discordance becomes part of `alignment_score`. No remediation of
either side before data says which definition wins.