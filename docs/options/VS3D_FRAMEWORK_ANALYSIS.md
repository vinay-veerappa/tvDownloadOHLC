# VS3D / VolSignals Framework — Analysis & Deferred Evaluation

**Date:** 2026-08-30
**Status:** Documented, not implemented. Parked as a research-track hypothesis; revisit when CBOE vendor data accumulates.
**Source page:** https://www.volsignals.com/trading (their "Trading with VS3D" live-education page, scraped 2026-08-30, Aug 28 data)
**Related:** `docs/options/LEVEL_TRANSLATION_VENDOR_COMPARISON.md` (§6 CBOE vendor feed), `scripts/options_research/cboe_vendor_fetch.py` (data infra that would feed this), `scripts/options_research/level_source_backtest.py` (harness that would score it)

## 1. What VS3D is

VolSignals sells a 0DTE SPX trading dashboard ("VS3D") built on one core object:
the **signed net market-maker position per strike** of the day's expiring
portfolio, snapshot at **yesterday's close, post-reconciliation**. Not the
standard max-gamma-wall model — despite "gamma" vocabulary, their wall logic is
**inverted** relative to ours.

Their published framework (12 rules, verbatim from the page):

1. **Dealer shorts are the range, dealer longs are the target.** "What is the
   range? It's the dealer's max short. What's the target inside the range?
   The max long." Hedging pushes price AWAY from max-short, TOWARD max-long.
2. **Expiring open interest drives the bus.** Read yesterday's reconciled
   expiring position. Same-day prints are noise: "massively overinflated
   volumes is noise. I'm looking for structure."
3. **Shape beats size.** Clustered long/short lobes with clear peaks are
   tradeable; alternating long/short/long is "fishbone: nothing to trade."
4. **Balance is the target, not the entry.** Never buy the long strike;
   short it as the fly body. "Short the pin, never long the pin."
5. **A test is a fork, not a signal.** At a short cluster: extend-through-then-
   reject OR get rejected at it. ~30 min of chewing decides. Rejection is the
   entry signal; reversion toward balance is the trade.
6. **In fast markets, treat balance levels like tests** (first ~90 min).
7. **Range lost → cut.** 3 crossings or 15–20 min beyond the level = hypothesis
   dead.
8. **Gamma is behavior, not direction.** Long gamma = fade the edges; negative
   gamma = downshift expectations.
9. **Charm is the one directional input, an afternoon tool.** Weakest at open,
   strongest into close. Their day split: open→London close = ignore charm;
   London close → 2 PM = entries (usually 11:00–11:30 ET); 2 PM → close =
   hold or fold. **Charm flip level** — below it passive flow turns to selling.
10. **The edge is a known flow about to flip.** Visible cohort buying +
    sideways price = invisible seller; later the visible buyer becomes the
    seller → knowable direction.
11. **Structure = fly.** Buy 1 wing at upper test, sell 2 at balance, buy 1 at
    lower test. ~15 pts wide (wider when straddle rich), pay $2.50–4.00, target
    2–4x, cut if range cracks.
12. **Being right is not the goal.** <5% of account per trade; best days = slow
    low-flow long-gamma clustered position; worst = chaotic morning, negative
    gamma, multi-expiry mess.

Their model output on the sample day (Aug 28 2026): SPX range 7650–7800,
balance levels 7775 (Strong) / 7750 / 7725 / 7710 (Weak) / 7675, test levels
7740 / 7755 / 7720 / 7700, charm flip at 7710, straddle $37.55.

## 2. How it differs from our GEX walls (the crux)

| Aspect | Our model | VS3D |
|---|---|---|
| Strike-level object | Unsigned total gamma (γ × OI) per strike | **Signed net dealer position** (long vs short) per strike |
| Max-gamma / max-short strike behavior | Wall that **holds** (repels) | "Test": price extends **through** then rejects |
| Max-long strike | (unnamed) | "Balance" = **pin target into close** |
| Expiry focus | Front/back blend across expiries | **Today's expiring 0DTE only**, yesterday's reconciled copy |
| Directional intraday bias | none from options | **Charm flip level** with three-part day playbook |
| Data | our RTD book / Schwab / (now) CBOE full chain | same CBOE data + their proprietary reconciliation |

These are **contrad, testable hypotheses**: ours says max-gamma strike is
respected; theirs says max-dealer-SHORT gets extended through and the dealer-
LONG strike is where price pins. The backtest harness can adjudicate directly
on the same 1m futures bars — no opinion needed, only sample size.

## 3. Why it's plausibly useful here — and where it fits

- **The signed-position object is the real gap in our stack.** Everything else
  (gamma regime, wall placement) we approximate. We have no dealer-long vs
  dealer-short classification, which flips the sign of expected flow at a
  strike.
- **Charm-flip is the biggest free win.** A per-strike theta aggregation from
  our archived CBOE chains (theta ships per contract) yields an afternoon
  directional-bias signal we currently have *nothing* for, and their
  London-close→2PM window maps cleanly onto our ET session structure.
- **Testable with zero new data sources.** Our CBOE archive
  (`data/options/vendors/chains`, from the fetcher below) + the existing
  `level_source_backtest.py` harness is sufficient to score the hypothesis.

**Honest limitation:** their edge depends on true customer-side direction
(dealer long vs short), derived from trade-tape reconciliation we cannot fully
reproduce. Our approximation (day-over-day OI deltas signed by bid/ask side of
last trade) is weaker — expected result is *noisier* versions of their levels.
That noisiness is acceptable for hypothesis-testing; it may be unacceptable for
live sizing, which is what their product actually sells.

## 4. How it would plug in (when revisited)

1. **Data:** already flowing — `cboe_vendor_fetch.py` core chains
   (anchors 09:33/11:33/13:33/15:48 ET). Needs per-contract theta kept (present
   in the chain payload) and day-over-day OI delta joining (already archived).
2. **Compute (new, ~1–2 days):** per-strike signed net-position proxy +
   cluster detection (lobes = fishbone test) + charm-flip level from theta
   aggregation → new `scripts/options_research/vs3d_proxy.py`.
3. **Score (existing harness):** extend `FAMILIES` in
   `level_source_backtest.py` with two new sources per family:
   `"VS3D_TEST"` (max-short strike; metric = extension-through-then-reject)
   and `"VS3D_BALANCE"` (max-long strike; metric = pin/hold into close).
4. **Verdict joins the 2-week CBOE review** (memory topic "CBOE vendor wall
   feed", review due 2026-09-13): three-way verdict — our walls vs CBOE raw
   vs VS3D-style signed structure.

## 5. Decision record

- **Not subscribing now.** No data access problem exists (their data source =
  our CBOE archive); the unreplicable part is their position reconciliation,
  and we don't yet know whether it matters (that's what the approximation test
  answers).
- **Free 7-day trial is the cheap validation** if wanted: dashboard hover
  comparison vs our computes for one week, before writing the proxy code.
- **Trigger to revisit:** CBOE core chains accumulating ≥2 weeks (from
  2026-08-30), or the 2026-09-13 review flag whichever comes first.