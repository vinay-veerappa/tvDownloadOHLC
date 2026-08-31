# Statistical / Quant Intraday Strategies — Research Backlog F2

> Purpose, validation standard, and status legend as in [01_ict_smc_price_action.md](01_ict_smc_price_action.md).
> This family emphasizes strategies with published empirical evidence — cheaper to validate because the hypothesis is already numeric.

---

## Repo context already established

| Finding | Source |
|---|---|
| ORB v1–v6 vectorized; IBB (Initial Balance) play 1/2/3 canonical with wins (PF 15.9 expanded, 6.3 fade compressed) | [9_30_breakout/](../9_30_breakout/README.md), [initial_balance_break/](../initial_balance_break/STRATEGY_COMPENDIUM.md) |
| IB compression (<0.35x ATR) → fades win 73–75%; IB expansion (>0.75x ATR) → breakouts win 92–95% | STRATEGY_CONFLUENCE_PLAYBOOK C1.2 |
| IB Midpoint directional rule: 75%/68.4% day-color probability | STRATEGY_CONFLUENCE_PLAYBOOK C1.1 |
| 10:30 fence: 76% of losses before 10:30 | STRATEGY_CONFLUENCE_PLAYBOOK C2.2 |
| VWAP institutional suite vectorized w/ 10-yr validation runs | [vwap_reclaim/](../vwap_reclaim/README.md) |
| BB mean reversion retired; surviving core = "ES overnight VWAP-targeted mean reversion" | [measured_move/MM_MEASURED_MOVE.md](../measured_move/MM_MEASURED_MOVE.md) E-numbers |
| Kaufman-ER RSI + 2-bar hook = best BB config (PF 1.81, WR 60.7%); Wilder RSI short-only PF 2.12 | STRATEGY_CONFLUENCE_PLAYBOOK §8.1 |
| Supertrend + ATR regime + time filter + 1.0x trail = PF 3.37 | STRATEGY_CONFLUENCE_PLAYBOOK §8.2 |

---

## Q1. Opening Range Breakout — parametric sweep beyond current v6
**Status**: 🟡 repo has v6+v7; the backlog test is the *parameter frontier*, not the concept

- Published evidence: 5-min ORB ~53.8% WR across 1.17M simulated trades (YouTube mega-backtest); 15-min ORB on first-15m range is the classic [Build Alpha](https://www.buildalpha.com/opening-range-breakout/) / [QuantifiedStrategies](https://www.quantifiedstrategies.com/opening-range-breakout-strategy/) variant; edgeful documents ES 5m ORB +108%/6mo.
- **Unswept frontier for repo**: (a) OR duration X-axis (5m/15m/30m/60m) × (b) entry type (close-beyond vs wick-stop vs limit-retest) × (c) gap-context conditioning (gap-up into OR high = continuation-favoring per gap stats below). The repo's IBB evidence says regime routing (IB/ATR quint) is the real edge — test ORB *conditional on* the IB regime router rather than standalone.
- **Learning**: does ORB edge concentrate in expansion regime by construction (i.e., is standalone ORB just a crude IB-regime detector)?

## Q2. Gap fill fade — NQ-specific with fill ladder
**Status**: ⬜ (strong published numbers, zero repo implementation)

- Published evidence (2,791 NQ days 2015–2025, [tradingstats.net](https://tradingstats.net/gap-fill-strategy/)):
  - 60.3% of NQ gaps fill 100% by close; 25% fill by close = 86.6%; fill-by-noon = 51.9%
  - Small in-range gaps fill 77.8%; large out-of-range gaps fill 8.2% → **gap size & open location are the conditioning variables**
  - 43.3% fill 100% by 10:30 (first hour is where fades pay); fill adds only +8.4pp after noon
  - Rare overnight-opposite signal: gap down + overnight rally → 83.3% fill
  - MAE: median 44 pts, P90 203 pts → **fades need wide stops or partial-fill laddering**
- SPY-side evidence ([shareplanner](https://www.shareplanner.com/blog/strategies-for-trading/fading-the-gap-how-large-overnight-moves-in-spy-and-qqq-play-out-during-the-trading-day.html)): ~50% of 1%+ gaps fill intraday, 2%+ drop to ~30–33%; Monday gap-ups fill ~61%.
- **Learning to extract**: replicate the fill ladder on repo NQ data (20-yr 1m parquet); validate the "fill by noon or abandon" timing rule; test fade-with-25%-fill-first-target as the risk-reduction variant.

## Q3. VWAP band reversion (±2σ) with regime gate
**Status**: 🟡 VWAP suite exists; the ±2σ band-fade variant is explicitly not the retired BB family (VWAP bands ≠ rolling std over price)

- Published pattern ([CrossTrade full PineScript](https://crosstrade.io/learn/trading-strategies/vwap-reversion/)): price extends 2 session-σ beyond VWAP + ADX<25 + rejection candle → fade to VWAP; skip trend days; RTH-only (overnight VWAP too thin).
- **Repo-specific frontier**: repo already found the surviving BB core is *overnight VWAP-targeted* mean reversion on ES. Test whether session-±2σ band fades add orthogonal signal to the overnight-VWAP-target engine, or are the same edge dressed differently. Compare band fades with vs without the 0DTE +1 Expected-Move ceiling filter (C5.1) — options-informed fade is a repo-differentiated angle.
- **Learning**: is ±2σ band reversion distinct from Bollinger reversion (which failed)? Hypothesis: volume-weighted σ expands/contracts differently than rolling price σ; the difference may be the whole edge.

## Q4. Market Profile 80% rule — value area rotation
**Status**: ⬜

- Published rule ([pipSafe](https://www.pipsafe.com/the-value-area-80-rule/), [FTMO/Oanda](https://ftmo.oanda.com/blog/market-profile-master-the-80-trading-strategy-hidden-magnets/), [ThinkMarkets](https://www.thinkmarkets.com/en/trading-academy/technical-analysis/volume-profile-trading-key-shapes-and-strategies/)): open outside prior value area → acceptance back inside for 2 consecutive 30-min bars → ~80% probability of rotation across the entire value area (to VAH if re-entered at VAL).
- **Testable variant** (TPO vs Volume-profile value areas as separate arms): repo has no TPO; volume profile from RedTailVolumeProfile.cs parity + live-storage volume. Condition on IB regime (does 80% rule hold on expansion days? probably not — expected interaction).
- **Learning**: acceptance-bar threshold (2×30m) sensitivity; whether the rule's WR survives with volume-not-TPO value area; interaction with gap days (Q2 overlap: gap-back-into-value ≈ same trade).

## Q5. Prior-day / week level magnets (PDH/PDL/PWH/PWL)
**Status**: 🟡 levels exist in indicators + ICT features (`htf_levels`); not systematically validated as *targets* vs *entry triggers*

- Community stats are noisy but persistent: PDL/PDH are the most-traded intraday levels on index futures.
- **Testable variants**: (a) *magnet test* — P(touch within day | opened below PDH) conditional on gap direction; (b) *first-touch rejection test* — WR of 1:2 fade at first PDH/PDL touch by session bucket; (c) *sweep-continuation test* (already partially in C4.1's Asia/London analog).
- **Learning**: which prior-day level produces the cleanest first-touch reaction on NQ specifically; whether the midnight-open magnet (S4/edgeful) dominates PDH/PDL as the day's primary magnet.

## Q6. Lunch rotation / afternoon reversal statistic
**Status**: 🟡 noon-curve stats verified in nqstats; not composed into a rule

- Repo stat: lunch continuation breakouts suffer; algorithms run the 10:00 low/high during lunch before PM trend (C2.3).
- **Testable variant**: fade lunch-window (11:30–13:30) excursions beyond morning VWAP bands; or fade a lunch sweep of morning high/low back toward VWAP; gate the PM re-entry at 13:30.
- **Learning**: is there a standalone lunch-fade edge, or does lunch only matter as a *no-trade* window? (If the latter, that's still a learning — it hardens C2.2/C2.3 into routing rules.)

## Q7. Friday/OPEX/expiry conditioning of everything above
**Status**: ⬜ (repo owns options data + TOS RTD feed — a differentiated angle)

- 0DTE EM walls (C5.1) claim 85% containment at ±1 EM. Test: do ALL F2 fade strategies (Q2 gap fade, Q3 VWAP band fade, Q4 80% rule) improve when entry is at/beyond the 0DTE +1 EM level? This is the composition learning the repo is uniquely positioned to find.