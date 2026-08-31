# ICT / SMC Intraday Price Action Strategies — Research Backlog F1

> **Purpose**: Every strategy here is a standalone hypothesis to test in isolation. Each test produces a **learning** (a conditional edge statement) that can then be composed into multiple strategies.
> **Validation standard**: 10+ years or 1000+ signals, % metrics (ADR-002), killzone/session stratification (ADR-021), prop-firm liquidation rules (ADR-020).
> **Status legend**: ⬜ Not tested · 🟡 Repo partially tested · ✅ Repo validated · ❌ Repo falsified

---

## Repo context already established (do not re-learn)

| Finding | Source |
|---|---|
| 7 standalone ICT daily-bias models measured **negative edge**; FTFC 92–99% WR; session-adaptive bias beats static | [ICT_BIAS_VALIDATION_ANALYSIS.md](../../architecture/ICT_BIAS_VALIDATION_ANALYSIS.md) |
| Liquidity → CISD → Retest 5-step pipeline is the authoritative execution frame (SL-1…SL-5, ET-1…ET-7) | [ICT_KNOWLEDGE_BASE.md](../ICT_KNOWLEDGE_BASE.md) |
| FVG+CISD rejection (HTF draw → LTF FVG → CISD+MSS) implemented, 1,152-arm sweep | [FVG_CISD_REJECTION_STRATEGY.md](../fvg_cisd_rejection/FVG_CISD_REJECTION_STRATEGY.md) |
| First 5m FVG post-10:00 = 95–98.7% WR when respected; iFVG flip = fade signal (1,932 sessions) | [STRATEGY_CONFLUENCE_PLAYBOOK.md](../STRATEGY_CONFLUENCE_PLAYBOOK.md) C3.1/C3.3 |
| Asia/London sweep → 82% probability of opposite-side sweep same session | [STRATEGY_CONFLUENCE_PLAYBOOK.md](../STRATEGY_CONFLUENCE_PLAYBOOK.md) C4.1 |

---

## S1. Turtle Soup / Swing Failure Pattern (SFP) — false-breakout fade
**Status**: ⬜ (Box Reversion hunter is a cousin — [reversal/README.md](../reversal/README.md) verified 9 signals / 10 days)

- **Theory** (Raschke/Connors "Street Smarts", later ICT-ified): price pierces a recent swing high/low (20-day extreme in the original; intraday session levels/swings here), grabs the resting stops, fails to hold, and snaps back inside the range. Trade the failure, not the break.
- **Entry rule**: wick beyond level, **body close back inside** the level → enter opposite direction on the reclaim close or first retest of the displacement leg.
- **Stop**: beyond the sweep extreme + buffer (SL-1 in repo convention).
- **Target**: opposite side of range / external liquidity. Claimed WR 60–70% at 1:2–1:3 (community-sourced, unverified).
- **Key differentiator from real breakout**: body close vs wick — *if price closes beyond the level, no Turtle Soup*.
- **Failure modes**: fading a genuine breakout in strong HTF trend; sweeping a level that wasn't the real draw (institutions continue past it); thin-session sweeps that mean-revert with no displacement.
- **Learning to extract**: does "sweep + body-close reclaim + MSS" beat "sweep + reclaim" alone? Does the setup WR flip by session (Asia/London sweeps vs PDH/PDL sweeps)? Does displacement magnitude filter the losers?
- **Sources**: [innercircletrader.net turtle soup](https://innercircletrader.net/tutorials/ict-turtle-soup-pattern/), [alchemymarkets](https://alchemymarkets.com/education/strategies/turtle-soup-strategy/), [fluxcharts](https://www.fluxcharts.com/articles/ict-turtle-soup-strategy-explained-how-to-identify-and-trade-it)

---

## S2. Trendline Liquidity Sweep → LH Breakout (CHoCH) (user image #2)
**Status**: ⬜ — repo has `trendline_structure.py` (measured-move engine) already doing pivot-anchored trendlines with zero lookahead; reuse it.

- **Theory**: an obvious trendline (≥3 touches, most-participant geometry) is a diagonal liquidity pool (see [LuxAlgo trendline-liquidity concept](https://www.luxalgo.com/library/concept/trendline-liquidity/)). Price sweeps below the falling line, then breaks the last LH — that LH breakout is the **Market Structure Shift (CHoCH)** that confirms reversal toward buy-side liquidity above.
- **Entry rule** (three-part):
  1. Trendline built from two most-recent confirmed swing pivots (matches `measured_move/core/measured_move.py` design);
  2. Sweep: price pierces the line with wick (close does NOT hold beyond);
  3. Confirmation: body-close beyond the last LH (for bullish) / LL (bearish) — i.e., an MSS fires.
- **Stop**: beyond the sweep extreme. **Target**: opposite range extreme / BSL pool (PDH, session high).
- **Failure modes**: many trendline breaks are real; no a-priori rule identifies the fake one (LuxAlgo's own honest caveat). Thin lines only you can see hold no liquidity.
- **Learning to extract**: does requiring BOTH line-sweep AND LH body-break beat either alone? Does the line's touch-count (3 vs 4+) change the sweep probability? Is the edge session-conditional (NY morning vs lunch)?
- **Sources**: [Trendline Liquidity (LuxAlgo Library)](https://www.luxalgo.com/library/concept/trendline-liquidity.md), [Liquidity Sweep concept](https://www.luxalgo.com/library/concept/liquidity-sweep.md)

---

## S3. Supply/Demand Bases — DBR, RBD, RBR, DBD (user image #1)
**Status**: ⬜ (adjacent: ICT FVG rejection implemented; box reversion implemented)

- **Terminology** (supply/demand school; ICT calls the same leg→base→leg the **Market Maker Model** / AMD-PO3):
  - **DBR** (Drop-Base-Rally) = demand reversal zone ← *user image bottom-right*
  - **RBR** (Rally-Base-Rally) = demand continuation ← *bottom-left*
  - **RBD** (Rally-Base-Drop) = supply reversal ← *top-right*
  - **DBD** (Drop-Base-Drop) = supply continuation ← *top-left*
- **Zone definition**: base = consecutive small-body consolidation (N bars, body/range ratio < X); zone = base body extent (or wick extent for refinement); exit leg must show **displacement** (leg height > k× base height).
- **Entry rule**: fresh (unmitigated) zone retest → candle reaction (rejection wick or engulf) → enter. Continuation variants (RBR/DBD) trend-gated; reversal variants (DBR/RBD) require a prior liquidity sweep for higher grade.
- **Stop**: beyond zone distal. **Target**: 2× leg or next opposing zone.
- **Failure modes**: mitigated zones (2nd+ touch decays); zones formed in chop; zones created without displacement.
- **Learning to extract**: does "fresh only" outperform "any touch"? Does zone grade (1st/2nd leg ordinal — repo already tags ordinals in measured_move) decay predictably? Does sweep-before-DBR meaningfully upgrade WR (i.e., is it the Turtle Soup overlap)?
- **Sources**: Market Maker Models (LuxAlgo [concept](https://www.luxalgo.com/library/concept/market-maker-models.md)), Set and Forget / CFT-style S/D pedagogy

---

## S4. Power of Three (PO3 / AMD) around the day's opens
**Status**: ⬜ (Morning Judas stats verified in nqstats; midnight open anchors exist in DailyNYLevels)

- **Theory** ([ICT PO3](https://innercircletrader.net/tutorials/ict-power-of-3/)): each day = Accumulation (range near open) → Manipulation (runs wrong-side liquidity) → Distribution (real move). Midnight open (00:00 ET) and 09:30 open are the anchors.
- **Testable variant**: (a) define accumulation range = first 30–60 min around midnight or RTH open; (b) manipulation = sweep of range opposite the HTF bias; (c) entry on reclaim + MSS; (d) target = manipulation extreme's opposite expansion (measured projection).
- **Edgeful evidence**: midnight-open retracement is a documented statistical behavior on ES/NQ ([edgeful report](https://www.edgeful.com/blog/posts/ICT-trading-strategy-midnight-open-retracement-report)) — repo can validate locally on 20 years of 1m.
- **Learning to extract**: does the manipulation leg reliably precede distribution (direction-flip probability)? Which open (midnight vs 09:30) has the better retracement statistics on NQ specifically? Interaction with IB compression regime (C1.2 quints)?
- **Failure mode**: not every day prints clean AMD (ICT instructors say it themselves); double-manipulation days whipsaw the model.

---

## S5. Silver Bullet time windows
**Status**: ⬜ (ICT killzone indicators exist in repo; killzone-gating is already the repo's known best filter)

- **Theory**: three 1-hour windows — 03:00–04:00, 10:00–11:00, 14:00–15:00 ET — where a session-range sweep → MSS → FVG retest sequence delivers one clean scalp (~20–30 pip / NQ-points equivalent). Highest-rated window: NY AM.
- **Testable variant**: first FVG formed inside window after a sweep, entered on 50% CE limit, stop beyond swept extreme, fixed 1:2.
- **Repo synergy**: C2.2 says 76% of losses pre-10:30 — so the 10:00–11:00 window gate is already the repo's own evidence-backed time filter. This test isolates *the window itself* as the edge.
- **Learning to extract**: WR by window (3 arms) on NQ 2015–2026; does sweep-then-MSS requirement matter, or is any FVG in the window profitable? (TTrades and others have done partial public backtests; repo should do its own.)
- **Sources**: [innercircletrader.net silver bullet](https://innercircletrader.net/tutorials/ict-silver-bullet-strategy/), [TTrades backtest video](https://www.youtube.com/watch?v=o0v4KQxZbpU), [LuxAlgo concept](https://www.luxalgo.com/library/concept/silver-bullet.md)

---

## S6. SMT Divergence (ES vs NQ correlated non-confirmation)
**Status**: ⬜ (multi-market scope selected by user; both symbols in live storage)

- **Theory**: ES and NQ are ~0.95 correlated; when one takes a prior high/low and the other refuses, the mover's break is suspect (stop-run, not continuation). Trade the **lagging** market in the reversal direction, or fade the mover.
- **Testable variant**: at each 5m swing high/low evaluation, check whether both instruments took the same extreme within ±N bars; classify divergent/non-divergent; measure subsequent MFE of the reversal hypothesis.
- **Learning to extract**: divergence at *which* structures (session highs vs PDH/PDL vs IB extremes) is informative? Lead time claim (~15–20 min on 2m) reproducible? Does SMT add signal beyond ICT sweep detection alone (i.e., is it redundant with the sweep itself)?
- **Sources**: [Bookmap NQ-vs-ES](https://bookmap.com/blog/nq-vs-es-why-they-move-together-until-they-dont), [SMT medium explainer](https://medium.com/@leooinvests/smt-divergence-reading-manipulated-markets-through-correlated-assets-c4206a974a99)

---

## S7. Killzone / macro-window conditioning (meta-learning test, cheap to run)
**Status**: 🟡 mostly built (macro windows defined in ICT_KNOWLEDGE_BASE §5; ICT macros feature exists in compute_ict_features)

- Rather than a standalone strategy, this test measures **how each of S1–S6 performs inside vs outside each macro/killzone window**. It is the composition harness: any conditional edge discovered here (e.g., "Turtle Soup works only 09:50–10:10") becomes a reusable *learning*.
- **Cheap first test**: reuse per-strategy signal CSVs, group PnL by 20-min macro bucket, run a session-adaptive WR test with Benjamini-Hochberg correction across buckets.