# Chart Patterns, Swing & Indicator-Based Strategies — Research Backlog F4

> Purpose, validation standard, and status legend as in [01_ict_smc_price_action.md](01_ict_smc_price_action.md).
> This is the "simple things" family the user explicitly requested — MA/HMA and other indicator strategies — plus classical chart patterns.

---

## Repo context already established

| Finding | Source |
|---|---|
| TheStrat 15m runners: 2-2 reversal + VWAP filter = WR 40.9%, PF 1.27, +$120k over 2yr NQ 5m; 2-1-2 continuation WR 46.8% | [the_strat/BACKTEST_RESULTS.md](../the_strat/BACKTEST_RESULTS.md) |
| Raw 5m Strat strategies failed in NT8 (WR 32.2%, −$30k) — timeframe + session windows were the fix | same |
| EMA Pullback hunter (8/21/55 stack) vectorized | [STRATEGY_CONFLUENCE_PLAYBOOK.md](../STRATEGY_CONFLUENCE_PLAYBOOK.md) §8.7 + reversal README |
| Measured Move trend engine (pivot-anchored trendlines, deterministic, zero-lookahead) w/ DI gate + ordinal tagging | [measured_move/MM_MEASURED_MOVE.md](../measured_move/MM_MEASURED_MOVE.md) |
| Supertrend winner config: ATR regime + time filter + 1.0× trail = PF 3.37; FVG/HTF confluence HURT Supertrend | STRATEGY_CONFLUENCE_PLAYBOOK §8.2 |
| Kaufman ER RSI + 2-bar hook = best mean-reversion oscillator (PF 1.81); Chande DMI & Connors RSI dead weight for BB | STRATEGY_CONFLUENCE_PLAYBOOK §8.1 |
| Al Brooks H2/L2 detectors exist in price_action suite | STRATEGY_CONFLUENCE_PLAYBOOK §4 |

---

## P1. Hull Moving Average — turning point (not crossover) system
**Status**: ⬜

- Alan Hull's own guidance ([QuantifiedStrategies backtest](https://www.quantifiedstrategies.com/hull-moving-average/), [TrendSpider](https://trendspider.com/learning-center/what-is-the-hull-moving-average/)): **do NOT use HMA crossovers** (both HMA lines have already de-lagged — the crossover loses meaning). Use **slope turning points**: rising HMA(200)-regime + HMA(20/50) turns up = long trigger; the turn often leads candlestick reversal patterns.
- Published backtest finding worth copying: HMA works well on *buy-on-weakness* (close below rising HMA) — i.e., HMA as pullback reference, not breakout line.
- **Testable variants** (NQ 5m + 15m): (a) HMA(55) slope-turn entries vs 9-EMA baseline (repo's incumbent); (b) HMA cone (20>50>200 alignment) as a bias gate wrapping existing hunters; (c) HMA-as-dynamic-S/R fade on 2nd touch.
- **Learning**: is HMA's lag reduction worth anything intraday, or does it just add whipsaw vs EMA? Compare against EMA Pullback on identical data/paths so the two occupy one trend-reference seat.

## P2. EMA stack pullback (8/21/55) — regime-conditional
**Status**: 🟡 hunter vectorized; untested arms below

- Popular variants ([GoatFunded roundup](https://www.goatfundedtrader.com/blog/best-moving-average-for-day-trading), [9/20 bone-zone writeup](https://www.bullsonwallstreet.com/post/first-pullback-trading-strategy)): "Bone Zone" = band between 9 & 20 EMA on 5m — enter first pullback holding the zone; 9/21/55 full-stack alignment for trend gate.
- **Testable variants**: (a) zone-entry (touch band) vs candle-entry (bullish close inside band); (b) one-pullback-per-session cap; (c) gate by IB regime router (the repo's proven C1.2 condition — pullbacks should work on expansion days only); (d) HMA(9)/HMA(20) zone as the P1 comparator arm.
- **Learning**: pullback count decay (1st pullback vs 2nd/3rd WR) on NQ intraday — mirrors measured_move's ordinal hypothesis but on MAs. If ordinal decay is steep, "first pullback only" becomes a shared rule across all trend-continuation strategies.

## P3. TheStrat extension — 15m structural runners + FTFC
**Status**: ✅ core validated (15m 2-2 + VWAP = PF 1.27; FTFC 92–99% per bias-validation doc)

- Remaining backlog: (a) 1-2-2d reversal variant (double inside → outside down) untested on 15m; (b) FTFC *violation* as an exit signal (not just entry); (c) TheStrat classifications as a **day-type pre-classifier** feeding DAILY_CLASSIFICATION.md R1/R2/DWP/DNP mapping.
- **Learning**: does 2-1-2d add trades without degrading PF vs the validated 2-2/2-1-2 pair? Does FTFC-break-at-open predict DNP days (a day-type learning reusable everywhere)?

## P4. Al Brooks second entries (H2/L2) with trend filter
**Status**: 🟡 detectors exist in price_action suite; never systematically backtested

- Theory ([Brooks FAQ](https://www.brookspriceaction.com/faq.php?dhtml=no&mode=faq2), [trasignal explainer](https://trasignal.com/blog/learn/al-brooks-2nd-entry-setup/)): H2 = second failed pullback attempt in a bull trend (bar whose high exceeds prior bar's high, second occurrence within the pullback); second entries are the reliable ones — first entries (H1/L1) are too noisy. EMA(20) gap bar / always-in direction as the trend gate.
- **Testable variants**: (a) H2-only vs H1+H2 (quantify Brooks' "wait for the second entry" claim); (b) trend gate = always-in from consecutive bar logic vs EMA(20) slope; (c) stop beyond signal bar vs 1-legged ATR.
- **Learning**: H1-vs-H2 WR delta is a *reusable confirmation-count learning* applicable to every setup family (does "wait for confirmation n=2" generalize?).

## P5. Measured move projection as universal target model
**Status**: 🟡 engine built + E34 falsification battery exists; adoption decision pending

- The engine (`trendline_structure.py`) projects a second leg = first leg from pivot anchors. Backlog: evaluate measured projection **as the TP module** for P2 pullbacks and P4 H2s (instead of fixed-R), per the 2-leg 50%/runner convention already coded.
- **Learning**: does structure-based TP beat fixed-R on pullback families? If yes, every F1/F2 strategy gains a shared exit module — the highest composition value in F4.

## P6. TTM Squeeze / Keltner release with regime & time gates
**Status**: ⬜ (KeltnerChannelSignals indicator exists; TTM-style BB-inside-KC squeeze not built)

- Theory ([StockCharts TTM](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/ttm-squeeze), [TOS backtests](https://tosindicators.com/ttm-squeeze)): BB(20,2) inside KC(20,1.5) = volatility compression; squeeze *fires* when BB exit KC; momentum histogram direction = trade direction. TOS backtests find per-symbol/per-timeframe instability (88–92% WR on some weekly setups, weak intraday) — the repo test is whether the squeeze adds anything on 5m/15m NQ *given the existing Kaufman-ER volatility regime gate*.
- **Testable variants**: (a) squeeze-fire entries with momentum direction; (b) squeeze as a *filter* on ORB (skip breakouts when squeeze is on — expansion should follow release); (c) hidden squeeze (BB inside KC but KC itself narrowing) as the higher-grade arm.
- **Learning**: squeeze as entry vs filter. Repo prior (Supertrend: "FVG/HTF confluence HURTS") suggests confluence-stacking overfits — test squeeze alone before stacking.
- **Related**: repo's own `volatility_leading.py` already has TTM Squeeze + Kaufman ER pieces — the delta here is wiring into a hunter.

## P7. Donchian / multi-level breakout (session extremes as channel)
**Status**: ⬜ (generic ORB partially covers; Donchian-style N-bar rolling extremes do not)

- Published ([QuantifiedStrategies Donchian](https://www.quantifiedstrategies.com/donchian-channel/), [TradingCode backtests](https://www.tradingcode.net/tradingview/donchian-channel-breakout/)): Donchian breakouts are PF-positive on daily futures (ES PF 1.63, CL 1.80, WR ~45%); intraday variants under-tested publicly.
- **Testable variant**: N-bar (20/55/100) intraday Donchian breakout on 5m with the repo's proven gates (time filter, ATR regime). Treat IB High/Low as a special-case Donchian(60-min).
- **Learning**: is intraday Donchian just ORB-with-longer-window (redundant with Q1), or does the rolling N-bar version capture lunch/PM breakouts ORB misses? If redundant → kill; if not → it's the PM-session breakout module.

## P8. Candle Science probability tables (Filter-then-Compute)
**Status**: 🟡 indicator exists (candle_science_v17_5.pine); statistical cutoffs documented (09:45/10:15) in pack-wargaming skill

- Backlog: port the FTC probability tables to the Python research pipeline so 3-candle pattern WRs can be conditioned on session/offset (aligning with the pack-wargaming statistical cutoff rules already in-repo).
- **Learning**: which 3-candle formations carry standalone predictive drift on NQ, and do their probabilities match the Pine implementation (parity check)?